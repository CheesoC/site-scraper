import gzip

import httpx

from scraper.discovery import URLDiscovery, parse_sitemap
from scraper.urls import URLNormalizer

INDEX = b"""<?xml version="1.0"?>
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <sitemap><loc>https://example.com/sitemap-pages.xml.gz</loc></sitemap>
</sitemapindex>"""

PAGES = b"""<?xml version="1.0"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://example.com/</loc></url>
  <url><loc>https://example.com/leistungen/?utm_source=x</loc></url>
  <url><loc>https://example.com/leistungen</loc></url>
  <url><loc>https://example.com/files/flyer.pdf</loc></url>
  <url><loc>https://other.com/page</loc></url>
</urlset>"""

ROBOTS = """User-agent: *
Disallow: /intern/
Crawl-delay: 2
Sitemap: https://example.com/sitemap-index.xml
"""


def handler(request: httpx.Request) -> httpx.Response:
    path = request.url.path
    if path == "/robots.txt":
        return httpx.Response(200, text=ROBOTS)
    if path == "/sitemap-index.xml":
        return httpx.Response(200, content=INDEX)
    if path == "/sitemap-pages.xml.gz":
        return httpx.Response(200, content=gzip.compress(PAGES))
    return httpx.Response(404)


async def test_discovery_reads_robots_and_nested_sitemaps():
    normalizer = URLNormalizer("https://example.com/")
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        discovery = URLDiscovery(normalizer, client, "site-scraper")
        result = await discovery.discover()
    assert result.robots_found
    assert result.crawl_delay == 2
    assert result.urls == ["https://example.com/", "https://example.com/leistungen"]
    assert "https://example.com/sitemap-pages.xml.gz" in result.sitemaps
    assert not discovery.allowed("https://example.com/intern/geheim")
    assert discovery.allowed("https://example.com/leistungen")
    # the default /sitemap.xml returned 404 -> not an error
    assert result.sitemap_errors == []


async def test_discovery_without_robots_allows_everything():
    normalizer = URLNormalizer("https://example.com/")
    transport = httpx.MockTransport(lambda r: httpx.Response(404))
    async with httpx.AsyncClient(transport=transport) as client:
        discovery = URLDiscovery(normalizer, client, "site-scraper")
        result = await discovery.discover()
    assert not result.robots_found
    assert result.urls == []
    assert discovery.allowed("https://example.com/anything")


def test_parse_plain_text_sitemap():
    children, urls = parse_sitemap(b"https://example.com/a\nnot a url\nhttps://example.com/b\n")
    assert children == [] and urls == ["https://example.com/a", "https://example.com/b"]
