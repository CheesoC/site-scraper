"""Menus without <nav>: accordion/sidebar menus that only open the branch of the current page."""

from scraper.content import ContentExtractor
from scraper.navigation import NavigationAggregator, NavigationExtractor
from scraper.urls import URLNormalizer

BASE = "https://example.com/"


def accordion(open_section: str) -> str:
    """Accordion menu like many CMS render it: <h3> links, only the current section shows its sub pages."""
    subs = {
        "projekte": '<div><ul><li><a href="/projekte/kochen.html">Kochen</a></li><li><a href="/projekte/theater.html">Theater</a></li></ul></div>',
        "schule": '<div><ul><li><a href="/schule/gta.html">GTA</a></li></ul></div>',
    }
    return (
        "<html><body>"
        '<header class="head"><h1>Schule</h1></header>'
        '<menu id="accordion">'
        f'<h3><a href="/schule.html">Schule</a></h3>{subs["schule"] if open_section == "schule" else ""}'
        '<h3><a href="/news.html">News</a></h3>'
        f'<h3><a href="/projekte.html">Projekte</a></h3>{subs["projekte"] if open_section == "projekte" else ""}'
        '<h3><a href="/kontakt.html">Kontakt</a></h3>'
        "</menu>"
        "<div><h2>Willkommen</h2><p>Kurzer Text.</p></div>"
        "</body></html>"
    )


def tree(items):
    return [(i["label"], i["path"], tree(i["children"])) for i in items]


def extract(html: str, path: str):
    return NavigationExtractor(URLNormalizer(BASE)).extract(html, BASE + path.lstrip("/"))


def test_accordion_menu_is_main_menu_with_open_branch():
    nav = extract(accordion("projekte"), "/projekte.html")
    main = next(m for m in nav.menus if m["type"] == "main")
    assert tree(main["items"]) == [
        ("Schule", "/schule", []),
        ("News", "/news", []),
        ("Projekte", "/projekte", [("Kochen", "/projekte/kochen", []), ("Theater", "/projekte/theater", [])]),
        ("Kontakt", "/kontakt", []),
    ]


def test_sub_menus_of_all_pages_are_merged():
    agg = NavigationAggregator()
    for section, path in [("projekte", "/projekte.html"), ("projekte", "/projekte/kochen.html"), ("schule", "/schule.html"), ("", "/news.html")]:
        agg.add(extract(accordion(section), path))
    navigation, _ = agg.build()
    assert tree(navigation["main"]) == [
        ("Schule", "/schule", [("GTA", "/schule/gta", [])]),
        ("News", "/news", []),
        ("Projekte", "/projekte", [("Kochen", "/projekte/kochen", []), ("Theater", "/projekte/theater", [])]),
        ("Kontakt", "/kontakt", []),
    ]
    assert [i["order"] for i in navigation["main"][0]["children"]] == [0]
    # the variants are folded into the main menu instead of being listed as extra menus
    assert [m["type"] for m in navigation["menus"]] == ["main"]


def test_sidebar_showing_only_the_current_level_is_hung_in():
    """On sub pages the sidebar lists only the siblings - often the most common variant, but never the main menu."""
    siblings = (
        '<menu id="accordion"><h3><a href="/projekte/kochen.html">Kochen</a></h3>'
        '<div><ul><li><a href="/projekte/kochen/rezepte.html">Rezepte</a></li></ul></div>'
        '<h3><a href="/projekte/theater.html">Theater</a></h3></menu>'
    )
    agg = NavigationAggregator()
    agg.add(extract(accordion("projekte"), "/projekte.html"))
    for path in ("/projekte/kochen.html", "/projekte/kochen/rezepte.html", "/projekte/theater.html"):
        agg.add(extract(f"<html><body>{siblings}<p>Text</p></body></html>", path))
    navigation, _ = agg.build()
    assert tree(navigation["main"]) == [
        ("Schule", "/schule", []),
        ("News", "/news", []),
        ("Projekte", "/projekte", [("Kochen", "/projekte/kochen", [("Rezepte", "/projekte/kochen/rezepte", [])]), ("Theater", "/projekte/theater", [])]),
        ("Kontakt", "/kontakt", []),
    ]
    assert [m["type"] for m in navigation["menus"]] == ["main"]


def test_different_menus_are_not_merged():
    agg = NavigationAggregator()
    agg.add(extract('<nav class="main"><ul><li><a href="/a">A</a></li><li><a href="/b">B</a></li><li><a href="/c">C</a></li></ul></nav>', "/"))
    agg.add(extract('<nav class="main"><ul><li><a href="/a">A</a><ul><li><a href="/a/1">A1</a></li></ul></li><li><a href="/x">X</a></li><li><a href="/y">Y</a></li></ul></nav>', "/x"))
    navigation, _ = agg.build()
    assert tree(navigation["main"]) == [("A", "/a", []), ("B", "/b", []), ("C", "/c", [])]


def test_menu_never_ends_up_in_content():
    content = ContentExtractor(URLNormalizer(BASE)).extract(accordion("projekte"), BASE + "projekte.html")
    texts = str([s["blocks"] for s in content.sections])
    assert "Willkommen" in texts
    assert "Kochen" not in texts and "Kontakt" not in texts


def test_faq_accordion_stays_content():
    html = (
        "<html><body><main><div class='accordion'>"
        "<h3>Wann ist Anmeldeschluss?</h3><p>Bis zum 31. März, Formulare gibt es im <a href='/sekretariat'>Sekretariat</a>.</p>"
        "<h3>Gibt es Ganztagsangebote?</h3><p>Ja, an allen Tagen bis 16 Uhr, siehe <a href='/gta'>GTA</a> und <a href='/hort'>Hort</a>.</p>"
        "</div></main></body></html>"
    )
    content = ContentExtractor(URLNormalizer(BASE)).extract(html, BASE)
    assert "Anmeldeschluss" in str([s["blocks"] for s in content.sections])
    assert not [m for m in extract(html, "/").menus if m["type"] == "main"]
