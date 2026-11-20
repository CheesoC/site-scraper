"""URLDiscovery: robots.txt rules and XML sitemaps."""

from __future__ import annotations

import gzip
import logging
from dataclasses import dataclass, field
from urllib.parse import urljoin
from urllib.robotparser import RobotFileParser

import httpx
from lxml import etree

from .urls import URLNormalizer

log = logging.getLogger(__name__)

MAX_SITEMAP_BYTES = 50 * 1024 * 1024
MAX_SITEMAPS = 200


@dataclass
class DiscoveryResult:
    robots_found: bool = False
    crawl_delay: float | None = None
    sitemaps: list[str] = field(default_factory=list)
    sitemap_errors: list[tuple[str, str]] = field(default_factory=list)
    urls: list[str] = field(default_factory=list)  # normalized, internal, deduplicated


class URLDiscovery:
    def __init__(self, normalizer: URLNormalizer, client: httpx.AsyncClient, user_agent: str):
        self.normalizer = normalizer
        self.client = client
        self.user_agent = user_agent
        self.robots = RobotFileParser()
        self.robots.allow_all = True  # until robots.txt was loaded

    @property
    def root(self) -> str:
        return f"{self.normalizer.scheme}://{self.normalizer.netloc}/"

    def allowed(self, url: str) -> bool:
        try:
            return self.robots.can_fetch(self.user_agent, url)
        except Exception:  # pragma: no cover - defensive
            return True

    async def load_robots(self, result: DiscoveryResult) -> None:
        robots_url = urljoin(self.root, "/robots.txt")
        try:
            response = await self.client.get(robots_url)
        except httpx.HTTPError as exc:
            log.info("robots.txt not reachable: %s", exc)
            return
        if response.status_code in (401, 403):
            # access to robots.txt forbidden -> treat as "disallow all" (RFC 9309 recommends this for 4xx except 404)
            self.robots = RobotFileParser()
            self.robots.disallow_all = True
            result.robots_found = True
            return
        if response.status_code >= 400:
            return
        parser = RobotFileParser()
        parser.parse(response.text.splitlines())
        self.robots = parser
        result.robots_found = True
        try:
            delay = parser.crawl_delay(self.user_agent)
            result.crawl_delay = float(delay) if delay is not None else None
        except Exception:
            result.crawl_delay = None
        for sitemap in parser.site_maps() or []:
            if sitemap not in result.sitemaps:
                result.sitemaps.append(sitemap)

    async def discover(self, use_sitemap: bool = True) -> DiscoveryResult:
        result = DiscoveryResult()
        await self.load_robots(result)
        if not use_sitemap:
            return result
        default = urljoin(self.root, "/sitemap.xml")
        if default not in result.sitemaps:
            result.sitemaps.append(default)
        seen_sitemaps: set[str] = set()
        seen_urls: set[str] = set()
        queue = list(result.sitemaps)
        while queue and len(seen_sitemaps) < MAX_SITEMAPS:
            sitemap_url = queue.pop(0)
            if sitemap_url in seen_sitemaps:
                continue
            seen_sitemaps.add(sitemap_url)
            try:
                children, urls = await self._fetch_sitemap(sitemap_url)
            except Exception as exc:  # network, parse errors
                if sitemap_url != default or not isinstance(exc, FileNotFoundError):
                    result.sitemap_errors.append((sitemap_url, str(exc)))
                continue
            for child in children:
                if child not in seen_sitemaps:
                    queue.append(child)
                    if child not in result.sitemaps:
                        result.sitemaps.append(child)
            for loc in urls:
                normalized = self.normalizer.normalize(loc)
                if not normalized or not self.normalizer.is_internal(normalized):
                    continue
                if not self.normalizer.looks_like_page(normalized) or normalized in seen_urls:
                    continue
                seen_urls.add(normalized)
                result.urls.append(normalized)
        return result

    async def _fetch_sitemap(self, url: str) -> tuple[list[str], list[str]]:
        response = await self.client.get(url)
        if response.status_code == 404:
            raise FileNotFoundError(f"{url}: 404")
        if response.status_code >= 400:
            raise RuntimeError(f"HTTP {response.status_code}")
        data = response.content
        if len(data) > MAX_SITEMAP_BYTES:
            raise RuntimeError("sitemap too large")
        if data[:2] == b"\x1f\x8b":
            data = gzip.decompress(data)[:MAX_SITEMAP_BYTES]
        return parse_sitemap(data)


def parse_sitemap(data: bytes) -> tuple[list[str], list[str]]:
    """Return (child sitemaps, page urls) of a sitemap or sitemap index document."""
    stripped = data.lstrip()
    if not stripped.startswith(b"<"):
        # plain text sitemap: one URL per line
        lines = [line.strip() for line in data.decode("utf-8", "replace").splitlines()]
        return [], [line for line in lines if line.startswith(("http://", "https://"))]
    parser = etree.XMLParser(recover=True, resolve_entities=False, no_network=True, huge_tree=False)
    root = etree.fromstring(stripped, parser=parser)
    if root is None:
        raise RuntimeError("invalid sitemap XML")
    tag = etree.QName(root).localname.lower()
    locs = [
        (el.text or "").strip()
        for el in root.iter()
        if isinstance(el.tag, str) and etree.QName(el).localname.lower() == "loc" and (el.text or "").strip()
    ]
    if tag == "sitemapindex":
        return locs, []
    return [], locs
