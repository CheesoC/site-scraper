"""End-to-end: crawl the local fixture site and validate the archive."""

import json
import os

import pytest

from fixture_server import serve
from scraper.cli import crawl
from scraper.config import CrawlConfig
from scraper.validator import validate_archive


def load(root, rel):
    return json.loads((root / rel).read_text(encoding="utf-8"))


async def run(tmp_path, render: bool):
    output = tmp_path / "archive"
    with serve() as url:
        code = await crawl(CrawlConfig(url=url + "/", output=output, render=render, delay=0, concurrency=3, timeout=20))
    return code, output


def check_archive(output, expect_js_page: bool):
    assert validate_archive(output) == []
    manifest = load(output, "manifest.json")
    paths = [p["path"] for p in manifest["pages"]]
    expected = {"/", "/leistungen", "/leistungen/webdesign", "/leistungen/seo", "/ueber-uns", "/kontakt", "/impressum", "/nur-sitemap"}
    if expect_js_page:
        expected.add("/js-seite")
    assert set(paths) == expected
    assert paths[0] == "/"
    assert "/intern/geheim" not in paths  # robots.txt
    kontakt = next(p for p in manifest["pages"] if p["path"] == "/kontakt")
    assert kontakt["aliases"] == ["/alt-seite"]  # redirect

    navigation = load(output, "navigation.json")
    main = [(i["label"], i["path"], [c["path"] for c in i["children"]]) for i in navigation["main"]]
    assert main == [
        ("Start", "/", []),
        ("Leistungen", "/leistungen", ["/leistungen/webdesign", "/leistungen/seo"]),
        ("Über uns", "/ueber-uns", []),
        ("Kontakt", "/kontakt", []),
    ]
    assert navigation["footer"][0]["label"] == "Rechtliches"
    assert navigation["footer"][0]["children"][1]["external"] is True
    assert navigation["logo"]["image"].startswith("assets/images/")
    assert (output / navigation["logo"]["image"]).exists()

    home = load(output, "pages/index/content.json")
    assert [s["type"] for s in home["sections"]][:2] == ["hero", "cards"]
    link = home["sections"][0]["blocks"][1]["content"][3]
    assert link["type"] == "link" and link["path"] == "/leistungen/seo"
    hero_image = home["sections"][0]["blocks"][2]
    assert hero_image["src"].startswith("assets/images/") and (output / hero_image["src"]).exists()

    about = load(output, "pages/ueber-uns/content.json")
    gallery = next(b for s in about["sections"] for b in s["blocks"] if b["type"] == "gallery")
    assert [i["alt"] for i in gallery["images"]] == ["Team 1", "Team 2", "Team 3"]
    assert all(i["src"] for i in gallery["images"])  # lazy images downloaded

    leistungen = load(output, "pages/leistungen/content.json")
    assert [b["label"] for b in leistungen["breadcrumbs"]] == ["Start", "Leistungen"]
    assert any(b["type"] == "accordion" for s in leistungen["sections"] for b in s["blocks"])

    report = load(output, "reports/crawl-report.json")
    assert report["status"] == "errors"  # /fehlt returns 404
    assert report["stats"]["failed"] == 1 and report["stats"]["assetsFailed"] == 0
    failed = load(output, "reports/failed-urls.json")["items"]
    assert failed[0]["url"].endswith("/fehlt") and failed[0]["status"] == 404
    broken = {b["path"] for b in load(output, "reports/broken-links.json")["items"]}
    assert "/fehlt" in broken
    assert any(i["type"] == "document" and i["url"].endswith("flyer.pdf") for i in report["issues"])
    assert (output / "pages/index/content.md").read_text().startswith("<!-- section:")
    assert (output / "pages/index/original.html").exists()


async def test_static_crawl(tmp_path):
    code, output = await run(tmp_path, render=False)
    assert code == 0
    check_archive(output, expect_js_page=False)


def chromium_available() -> bool:
    """True if the Chromium build expected by the installed Playwright version exists."""
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            return os.path.exists(p.chromium.executable_path)
    except Exception:
        return False


@pytest.mark.browser
@pytest.mark.skipif(not chromium_available(), reason="Chromium for Playwright not installed")
async def test_rendered_crawl_finds_javascript_links(tmp_path):
    code, output = await run(tmp_path, render=True)
    assert code == 0
    check_archive(output, expect_js_page=True)
