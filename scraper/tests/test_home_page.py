"""Choosing the home page "/" after a crawl (PageCrawler._promote_home)."""

from pathlib import Path

from scraper.config import CrawlConfig
from scraper.crawler import CrawledPage, PageCrawler

START = "https://cms.sachsen.schule/fsamzeisigwald/schule.html"


def crawler_with(paths: list[str], aliases: dict[str, str] | None = None, start: str = START) -> PageCrawler:
    crawler = PageCrawler(CrawlConfig(url=start, output=Path("unused")))
    for path in paths:
        page = CrawledPage(url="", final_url="", path=path, depth=0, status=200, html="", extraction=None, navigation=None, found_on=None)
        crawler.state.pages[path] = page
    for alias, target in (aliases or {}).items():
        crawler._add_alias(alias, target)
    return crawler


def test_real_home_page_is_kept():
    crawler = crawler_with(["/schule", "/"], {"/start": "/"})
    crawler._promote_home()
    assert list(crawler.state.pages) == ["/schule", "/"]
    assert crawler.state.pages["/"].aliases == ["/start"]


def test_redirect_target_of_root_becomes_home():
    crawler = crawler_with(["/schule", "/schule/gta", "/news"], {"/": "/schule", "/schule/index": "/schule"})
    crawler._promote_home()
    state = crawler.state
    assert list(state.pages) == ["/", "/schule/gta", "/news"]
    home = state.pages["/"]
    assert home.path == "/"
    assert home.aliases == ["/schule", "/schule/index"]
    assert state.aliases == {"/schule/index": "/", "/schule": "/"}


def test_start_page_becomes_home_if_root_unreachable():
    crawler = crawler_with(["/news", "/schule"])
    crawler._promote_home()
    assert list(crawler.state.pages) == ["/", "/news"]
    assert crawler.state.aliases == {"/schule": "/"}


def test_nothing_to_promote():
    crawler = crawler_with([])
    crawler._promote_home()
    assert crawler.state.pages == {}
    other = crawler_with(["/news"])  # start page not crawled, no root alias
    other._promote_home()
    assert list(other.state.pages) == ["/news"]
