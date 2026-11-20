"""Page fetchers: Crawl4AI/Playwright (rendered) and httpx (static HTML)."""

from __future__ import annotations

import asyncio
import logging
import os
import re
from dataclasses import dataclass

import httpx

log = logging.getLogger(__name__)

HTML_TYPES = ("text/html", "application/xhtml+xml")

# Runs in the page before the HTML is captured: open public <details>, resolve lazy images and
# mark computed CSS background images (large elements only) so the extractor can see them.
PREPARE_PAGE_JS = r"""
(() => {
  document.querySelectorAll('details').forEach(d => { d.open = true; });
  document.querySelectorAll('img[loading="lazy"]').forEach(img => { img.loading = 'eager'; });
  const all = document.body ? document.body.querySelectorAll('*') : [];
  let marked = 0;
  for (const el of all) {
    if (marked > 400) break;
    const bg = getComputedStyle(el).backgroundImage;
    if (!bg || bg === 'none' || bg.indexOf('url(') === -1) continue;
    const rect = el.getBoundingClientRect();
    if (rect.width < 120 || rect.height < 80) continue;
    el.setAttribute('data-scraper-bg', bg);
    marked++;
  }
})();
"""


@dataclass
class FetchResult:
    url: str
    final_url: str
    status: int | None
    html: str | None
    content_type: str | None = None
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None and self.status is not None and self.status < 400 and self.html is not None

    @property
    def retryable(self) -> bool:
        return self.status in (408, 425, 429, 500, 502, 503, 504) or (self.status is None and self.error is not None)


class HttpFetcher:
    """Plain HTTP fetcher (no JavaScript)."""

    def __init__(self, client: httpx.AsyncClient):
        self.client = client

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return None

    async def fetch(self, url: str) -> FetchResult:
        try:
            response = await self.client.get(url)
        except httpx.HTTPError as exc:
            return FetchResult(url=url, final_url=url, status=None, html=None, error=f"{type(exc).__name__}: {exc}")
        content_type = response.headers.get("content-type", "").split(";")[0].strip().lower()
        final_url = str(response.url)
        if response.status_code >= 400:
            return FetchResult(url, final_url, response.status_code, None, content_type, error=f"HTTP {response.status_code}")
        if content_type and content_type not in HTML_TYPES:
            return FetchResult(url, final_url, response.status_code, None, content_type, error=f"not html ({content_type})")
        return FetchResult(url, final_url, response.status_code, response.text, content_type)


class BrowserFetcher:
    """Renders pages with Crawl4AI (Playwright/Chromium): JavaScript, lazy loading, dynamic content."""

    def __init__(self, user_agent: str, timeout: float, client: httpx.AsyncClient):
        self.user_agent = user_agent
        self.timeout = timeout
        self.client = client  # used for a cheap HEAD check (content type) before rendering
        self.crawler = None

    async def __aenter__(self):
        os.environ.setdefault("CRAWL4AI_NO_CLOUD_NOTICE", "1")
        from crawl4ai import AsyncWebCrawler, BrowserConfig

        config = BrowserConfig(headless=True, verbose=False, user_agent=self.user_agent, text_mode=False)
        self.crawler = AsyncWebCrawler(config=config)
        await self.crawler.__aenter__()
        return self

    async def __aexit__(self, *exc):
        if self.crawler is not None:
            await self.crawler.__aexit__(*exc)

    async def fetch(self, url: str) -> FetchResult:
        from crawl4ai import CacheMode, CrawlerRunConfig

        # Skip rendering for non-HTML resources (PDFs, images...) that slipped through extension checks
        try:
            head = await self.client.head(url)
            content_type = head.headers.get("content-type", "").split(";")[0].strip().lower()
            if head.status_code < 400 and content_type and content_type not in HTML_TYPES:
                return FetchResult(url, str(head.url), head.status_code, None, content_type, error=f"not html ({content_type})")
        except httpx.HTTPError:
            pass  # let the browser try

        run = CrawlerRunConfig(
            cache_mode=CacheMode.BYPASS,
            wait_until="load",
            page_timeout=int(self.timeout * 1000),
            scan_full_page=True,
            scroll_delay=0.15,
            delay_before_return_html=0.3,
            js_code=[PREPARE_PAGE_JS],
            remove_overlay_elements=False,
            verbose=False,
        )
        try:
            result = await self.crawler.arun(url, config=run)
        except Exception as exc:  # Playwright errors, timeouts
            return FetchResult(url=url, final_url=url, status=None, html=None, error=f"render error: {short_error(str(exc))}")
        status = result.status_code
        final_url = result.redirected_url or result.url or url
        headers = {k.lower(): v for k, v in (result.response_headers or {}).items()}
        content_type = headers.get("content-type", "text/html").split(";")[0].strip().lower()
        html = result.html or None
        if status is not None and status >= 400:
            return FetchResult(url, final_url, status, None, content_type, error=f"HTTP {status}")
        if html is None:
            return FetchResult(url, final_url, status, None, content_type, error="render error: " + short_error(result.error_message or "empty response"))
        # Crawl4AI flags near-empty pages as "blocked"; we still keep the HTML if the server answered 2xx/3xx
        return FetchResult(url, final_url, status or 200, html, content_type)


def short_error(message: str, limit: int = 300) -> str:
    """Crawl4AI/Playwright errors contain code context and call logs; keep the meaningful part."""
    match = re.search(r"net::ERR_[A-Z_]+", message)
    if match:
        return match.group(0)
    for line in message.splitlines():
        line = line.strip()
        if line and not line.lower().startswith(("unexpected error in", "error: failed on navigating")):
            return line[:limit]
    return message.strip()[:limit]


async def fetch_with_retries(fetcher, url: str, retries: int, backoff: float = 1.0) -> FetchResult:
    result = await fetcher.fetch(url)
    attempt = 0
    while not result.ok and result.retryable and attempt < retries:
        attempt += 1
        await asyncio.sleep(backoff * (2 ** (attempt - 1)))
        result = await fetcher.fetch(url)
    return result
