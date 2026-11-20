"""PageCrawler: breadth-first crawl of one site within the configured limits."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from .config import CrawlConfig
from .content import ContentExtractor, PageExtraction
from .discovery import DiscoveryResult, URLDiscovery
from .fetchers import BrowserFetcher, FetchResult, HttpFetcher, fetch_with_retries
from .navigation import NavigationExtractor, PageNavigation
from .urls import URLNormalizer

log = logging.getLogger(__name__)


@dataclass
class CrawledPage:
    url: str  # URL as discovered (normalized)
    final_url: str  # normalized URL after redirects
    path: str
    depth: int
    status: int | None
    html: str
    extraction: PageExtraction
    navigation: PageNavigation
    found_on: str | None
    out_links: list[str] = field(default_factory=list)  # internal page paths linked from this page
    aliases: list[str] = field(default_factory=list)
    content_hash: str = ""


@dataclass
class CrawlState:
    started_at: str = ""
    finished_at: str = ""
    pages: dict[str, CrawledPage] = field(default_factory=dict)  # path -> page, in crawl order
    aliases: dict[str, str] = field(default_factory=dict)  # other path -> exported path
    failed: list[dict] = field(default_factory=list)  # {url, status, error, page}
    skipped: list[dict] = field(default_factory=list)  # {url, reason, page}
    documents: list[dict] = field(default_factory=list)  # non-HTML internal resources {url, contentType, page}
    discovered: dict[str, str | None] = field(default_factory=dict)  # url -> found on (path or "sitemap")
    limits_reached: list[str] = field(default_factory=list)
    render_errors: int = 0
    discovery: DiscoveryResult | None = None
    duplicates: int = 0


def page_links(html: str, base: str, normalizer: URLNormalizer) -> list[tuple[str, bool]]:
    """All links of a page as (normalized URL, is_internal_page)."""
    soup = BeautifulSoup(html, "lxml")
    base_tag = soup.find("base", href=True)
    if base_tag:
        base = urljoin(base, base_tag["href"])
    out = []
    for tag in soup.find_all(["a", "area"], href=True):
        info = normalizer.classify(str(tag["href"]), base)
        if info is None or info.url is None:
            continue
        out.append((info.url, info.internal and info.is_page))
    return out


class PageCrawler:
    def __init__(self, config: CrawlConfig, normalizer: URLNormalizer | None = None):
        self.config = config
        self.normalizer = normalizer or URLNormalizer(config.url, config.allow_domains, config.query_mode)
        self.state = CrawlState()
        self._attempts = 0
        self._lock = asyncio.Lock()
        self._hashes: dict[str, str] = {}

    # ------------------------------------------------------------------ run
    async def run(self) -> CrawlState:
        cfg = self.config
        self.state.started_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        headers = {"User-Agent": cfg.user_agent, "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.5"}
        async with httpx.AsyncClient(headers=headers, timeout=cfg.timeout, follow_redirects=True) as client:
            discovery = URLDiscovery(self.normalizer, client, cfg.user_agent)
            self.discovery = discovery
            self.state.discovery = await discovery.discover(use_sitemap=cfg.use_sitemap)
            delay = cfg.delay
            concurrency = max(1, cfg.concurrency)
            if self.state.discovery.crawl_delay:
                delay = max(delay, self.state.discovery.crawl_delay)
                concurrency = 1
            fetcher = BrowserFetcher(cfg.user_agent, cfg.timeout, client) if cfg.render else HttpFetcher(client)
            async with fetcher:
                queue: asyncio.Queue = asyncio.Queue()
                self._enqueue(queue, self.normalizer.start_url, 0, None)
                for url in self.state.discovery.urls:
                    self._enqueue(queue, url, 1, "sitemap")
                workers = [asyncio.create_task(self._worker(queue, fetcher, delay)) for _ in range(concurrency)]
                await queue.join()
                for worker in workers:
                    worker.cancel()
                await asyncio.gather(*workers, return_exceptions=True)
        self.state.finished_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        return self.state

    def _enqueue(self, queue: asyncio.Queue, url: str, depth: int, found_on: str | None) -> None:
        if url in self.state.discovered:
            return
        self.state.discovered[url] = found_on
        if depth > self.config.max_depth:
            self._limit("max_depth")
            self.state.skipped.append({"url": url, "reason": "max_depth", "page": found_on})
            return
        if not self.discovery.allowed(url):
            self.state.skipped.append({"url": url, "reason": "robots.txt", "page": found_on})
            return
        queue.put_nowait((url, depth, found_on))

    def _limit(self, name: str) -> None:
        if name not in self.state.limits_reached:
            self.state.limits_reached.append(name)

    async def _worker(self, queue: asyncio.Queue, fetcher, delay: float) -> None:
        while True:
            url, depth, found_on = await queue.get()
            try:
                async with self._lock:
                    if self._attempts >= self.config.max_pages:
                        self._limit("max_pages")
                        self.state.skipped.append({"url": url, "reason": "max_pages", "page": found_on})
                        continue
                    self._attempts += 1
                started = time.monotonic()
                result = await fetch_with_retries(fetcher, url, self.config.retries)
                await self._handle(queue, result, url, depth, found_on)
                elapsed = time.monotonic() - started
                if delay > elapsed:
                    await asyncio.sleep(delay - elapsed)
            except Exception as exc:  # never let one page kill the crawl
                log.exception("unexpected error for %s", url)
                self.state.failed.append({"url": url, "status": None, "error": f"internal error: {exc}", "page": found_on})
            finally:
                queue.task_done()

    # -------------------------------------------------------------- results
    async def _handle(self, queue: asyncio.Queue, result: FetchResult, url: str, depth: int, found_on: str | None) -> None:
        state = self.state
        if not result.ok:
            if result.error and result.error.startswith("not html"):
                state.documents.append({"url": url, "contentType": result.content_type, "page": found_on})
                return
            if result.error and result.error.startswith("render error"):
                state.render_errors += 1
            state.failed.append({"url": url, "status": result.status, "error": result.error, "page": found_on})
            log.warning("failed %s: %s", url, result.error)
            return

        final = self.normalizer.normalize(result.final_url) or url
        if not self.normalizer.is_internal(final):
            state.skipped.append({"url": url, "reason": f"redirects off-site to {final}", "page": found_on})
            return
        original_path = self.normalizer.to_path(url)
        path = self.normalizer.to_path(final)
        if final != url and final not in state.discovered:
            state.discovered[final] = found_on
        if not self.discovery.allowed(final):
            state.skipped.append({"url": final, "reason": "robots.txt", "page": found_on})
            return

        extraction, navigation, links = await asyncio.to_thread(self._process_html, result.html, final)

        async with self._lock:
            target = self._duplicate_of(path, extraction)
            if target is not None:
                state.duplicates += 1
                for alias in {original_path, path} - {target}:
                    self._add_alias(alias, target)
                self._follow(queue, links, depth, target)
                return
            page = CrawledPage(
                url=url,
                final_url=final,
                path=path,
                depth=depth,
                status=result.status,
                html=result.html,
                extraction=extraction,
                navigation=navigation,
                found_on=found_on,
                content_hash=self._hash(extraction),
            )
            state.pages[path] = page
            self._hashes.setdefault(page.content_hash, path)
            if original_path != path:
                self._add_alias(original_path, path)
            log.info("page %s (%d sections)", path, len(extraction.sections))
            page.out_links = self._follow(queue, links, depth, path)

    def _follow(self, queue: asyncio.Queue, links: list[tuple[str, bool]], depth: int, path: str) -> list[str]:
        out: list[str] = []
        for link_url, is_page in links:
            if not is_page:
                continue
            target = self.normalizer.to_path(link_url)
            if target != path and target not in out:
                out.append(target)
            self._enqueue(queue, link_url, depth + 1, path)
        return out

    def _add_alias(self, alias: str, target: str) -> None:
        if alias == target or alias in self.state.pages:
            return
        self.state.aliases[alias] = target
        page = self.state.pages.get(target)
        if page is not None and alias not in page.aliases:
            page.aliases.append(alias)

    def _duplicate_of(self, path: str, extraction: PageExtraction) -> str | None:
        """Exported path this page duplicates (same path, canonical or identical query variant)."""
        if path in self.state.pages:
            return path
        if path in self.state.aliases:
            return self.state.aliases[path]
        canonical = extraction.meta.get("canonical")
        if canonical:
            normalized = self.normalizer.normalize(canonical)
            if normalized and self.normalizer.is_internal(normalized):
                canonical_path = self.normalizer.to_path(normalized)
                if canonical_path != path and canonical_path in self.state.pages:
                    return canonical_path
        if "/q-" in path:
            existing = self._hashes.get(self._hash(extraction))
            if existing:
                return existing
        return None

    @staticmethod
    def _hash(extraction: PageExtraction) -> str:
        payload = json.dumps(extraction.sections, sort_keys=True, ensure_ascii=False, default=str)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def _process_html(self, html: str, url: str) -> tuple[PageExtraction, PageNavigation, list[tuple[str, bool]]]:
        extraction = ContentExtractor(self.normalizer).extract(html, url)
        nav_extractor = NavigationExtractor(self.normalizer)
        navigation = nav_extractor.extract(html, url)
        if not navigation.breadcrumbs and extraction.meta.get("structuredData"):
            navigation.breadcrumbs = nav_extractor.extract_jsonld_breadcrumbs(extraction.meta["structuredData"])
        return extraction, navigation, page_links(html, url, self.normalizer)
