from pathlib import Path

import pytest

from scraper.navigation import NavigationAggregator, NavigationExtractor
from scraper.urls import URLNormalizer

FIXTURE = Path(__file__).parent / "fixtures" / "html" / "nav.html"


def tree(items):
    return [(i["label"], i["path"] or i["url"], tree(i["children"])) for i in items]


@pytest.fixture(scope="module")
def nav():
    extractor = NavigationExtractor(URLNormalizer("https://example.com/"))
    return extractor.extract(FIXTURE.read_text(), "https://example.com/leistungen/seo")


def menu(nav, menu_type):
    return next(m for m in nav.menus if m["type"] == menu_type)


def test_main_menu_keeps_dropdowns_and_mega_menu_groups(nav):
    main = menu(nav, "main")
    assert main["ambiguous"] is False
    assert tree(main["items"]) == [
        ("Start", "/", []),
        ("Leistungen", "/leistungen", [
            ("Webdesign", "/leistungen/webdesign", []),
            ("SEO", "/leistungen/seo", [("SEO-Audit", "/leistungen/seo/audit", [])]),
        ]),
        ("Unternehmen", None, [
            ("Über uns", None, [("Team", "/team", []), ("Geschichte", "/geschichte", [])]),
            ("Arbeiten", None, [("Jobs", "/jobs", [])]),
        ]),
        ("Shop", "https://shop.other.com/", []),
    ]
    shop = main["items"][3]
    assert shop["external"] is True and shop["path"] is None
    audit = main["items"][1]["children"][1]["children"][0]
    assert audit["depth"] == 2 and audit["order"] == 0


def test_other_menus(nav):
    assert [m["type"] for m in nav.menus] == ["utility", "main", "mobile", "footer"]
    footer = menu(nav, "footer")
    assert tree(footer["items"]) == [
        ("Rechtliches", None, [("Impressum", "/impressum", []), ("Datenschutz", "/datenschutz", [])]),
        ("Social", None, [("LinkedIn", "https://www.linkedin.com/company/x", [])]),
        ("Beispiel GmbH", "/", []),
    ]


def test_logo_cta_breadcrumbs(nav):
    assert nav.logo["path"] == "/" and nav.logo["imageUrl"] == "https://example.com/img/logo.svg"
    assert nav.logo_image.role == "logo"
    assert tree(nav.cta) == [("Projekt anfragen", "/kontakt", [])]
    assert tree(nav.breadcrumbs) == [("Start", "/", []), ("Leistungen", "/leistungen", []), ("SEO", "/leistungen/seo", [])]


def test_flat_dropdown_menu_is_marked_ambiguous():
    html = '<nav><a href="/a">A</a><div class="dropdown"><a href="/a/1">A1</a></div><a href="/b">B</a></nav>'
    result = NavigationExtractor(URLNormalizer("https://example.com/")).extract(html, "https://example.com/")
    assert result.menus[0]["type"] == "main"
    assert result.menus[0]["ambiguous"] is True
    assert [i["label"] for i in result.menus[0]["items"]] == ["A", "A1", "B"]


def test_jsonld_breadcrumbs():
    extractor = NavigationExtractor(URLNormalizer("https://example.com/"))
    extractor.extract("<html></html>", "https://example.com/a/b")
    data = [{"@type": "BreadcrumbList", "itemListElement": [
        {"position": 2, "name": "A", "item": "https://example.com/a"},
        {"position": 1, "name": "Home", "item": "https://example.com/"},
    ]}]
    assert tree(extractor.extract_jsonld_breadcrumbs(data)) == [("Home", "/", []), ("A", "/a", [])]


def test_aggregator_picks_most_common_and_drops_redundant_mobile(nav):
    extractor = NavigationExtractor(URLNormalizer("https://example.com/"))
    other = extractor.extract(
        '<header><nav class="main"><ul><li><a href="/x">X</a></li></ul></nav>'
        '<nav class="mobile"><a href="/x">X</a></nav></header>',
        "https://example.com/x",
    )
    agg = NavigationAggregator()
    agg.add(nav)
    agg.add(nav)
    agg.add(other)
    navigation, logo_image = agg.build()
    assert navigation["main"][0]["label"] == "Start"
    assert navigation["main"][0]["type"] == "main"
    assert navigation["footer"][0]["label"] == "Rechtliches"
    assert navigation["logo"]["path"] == "/"
    assert logo_image is nav.logo_image
    types = [(m["type"], m["pages"]) for m in navigation["menus"]]
    # the second main menu becomes "secondary", its mobile copy adds nothing and is dropped,
    # the mobile menu of the first page has the extra entry "Angebote" and is kept
    assert ("main", 2) in types and ("secondary", 1) in types and ("mobile", 2) in types
    assert len([t for t in types if t[0] == "mobile"]) == 1
