from pathlib import Path

import pytest

from scraper.content import ContentExtractor, plain_text
from scraper.urls import URLNormalizer

FIXTURE = Path(__file__).parent / "fixtures" / "html" / "rich.html"


@pytest.fixture(scope="module")
def page():
    extractor = ContentExtractor(URLNormalizer("https://example.com/"))
    return extractor.extract(FIXTURE.read_text(encoding="utf-8"), "https://example.com/leistungen")


def blocks_of(page, section_type):
    return next(s for s in page.sections if s["type"] == section_type)["blocks"]


def test_meta(page):
    assert page.title == "Leistungen | Beispiel GmbH"
    assert page.meta["description"] == "Unsere Leistungen im Überblick."
    assert page.meta["canonical"] == "https://example.com/leistungen"
    assert page.meta["lang"] == "de"
    assert page.meta["h1"] == "Unsere Leistungen"
    assert page.meta["og"]["imageUrl"] == "https://example.com/media/og.jpg"
    assert page.meta["structuredData"][0]["@type"] == "Organization"


def test_section_order_and_types(page):
    assert [s["type"] for s in page.sections] == ["hero", "cards", "content", "faq", "gallery", "form"]
    assert page.sections[0]["id"] == "intro"
    assert page.sections[0]["source"]["classes"] == ["hero"]


def test_header_footer_nav_cookie_and_scripts_are_not_content(page):
    text = " ".join(plain_text(b.get("content", [])) for s in page.sections for b in s["blocks"])
    for unwanted in ("Cookies", "Impressum", "alert(1)", "Start ›"):
        assert unwanted not in text


def test_hero_rich_text_and_button(page):
    bg, heading, paragraph, button = blocks_of(page, "hero")
    assert bg["type"] == "image" and bg["role"] == "background"
    assert heading["content"][1] == {"type": "text", "text": "Leistungen", "marks": ["italic"]}
    nodes = paragraph["content"]
    assert {"type": "text", "text": "Webdesign", "marks": ["bold"]} in nodes
    link = next(n for n in nodes if n["type"] == "link")
    assert link["path"] == "/leistungen/seo#top" and link["external"] is False
    assert {"type": "break"} in nodes
    assert button == {
        "type": "button",
        "label": "Jetzt anfragen",
        "href": "https://example.com/kontakt",
        "path": "/kontakt",
        "external": False,
        "variant": "primary",
    }


def test_cards_with_lazy_and_srcset_images(page):
    heading, *cards = blocks_of(page, "cards")
    assert heading["type"] == "heading" and len(cards) == 3
    assert cards[0]["blocks"][0]["originalSrc"] == "https://example.com/media/web.png"
    assert cards[1]["blocks"][0]["originalSrc"] == "https://example.com/media/seo-800.png"
    assert cards[2]["link"]["path"] == "/leistungen/hosting"


def test_content_blocks(page):
    blocks = blocks_of(page, "content")
    assert [b["type"] for b in blocks] == ["heading", "table", "list", "image", "quote", "embed", "html", "divider", "code"]
    table = blocks[1]
    assert plain_text(table["head"][0][1]["content"]) == "Preis"
    assert table["rows"][1][0]["colspan"] == 2
    nested = blocks[2]["items"][1]["blocks"][0]
    assert nested["type"] == "list" and len(nested["items"]) == 2
    assert plain_text(blocks[3]["caption"]) == "Unser Team"
    assert plain_text(blocks[4]["cite"]) == "Anna M."
    assert blocks[5]["provider"] == "youtube"
    assert blocks[6]["text"] == "Interaktive Grafik: Umsatz 2024"
    assert blocks[8] == {"type": "code", "text": "console.log(1)", "language": "js"}


def test_faq_accordion_merged(page):
    accordion = blocks_of(page, "faq")[1]
    assert accordion["type"] == "accordion" and len(accordion["items"]) == 2
    assert plain_text(accordion["items"][0]["title"]) == "Wie lange dauert es?"


def test_gallery_and_form(page):
    gallery = blocks_of(page, "gallery")[0]
    assert gallery["type"] == "gallery" and [i["alt"] for i in gallery["images"]] == ["1", "2", "3"]
    form = blocks_of(page, "form")[1]
    assert [f["name"] for f in form["fields"]] == ["name", "email", "thema", "msg"]
    assert form["fields"][0]["label"] == "Name" and form["fields"][0]["required"]
    assert form["fields"][1]["label"] == "E-Mail"
    assert form["submitLabel"] == "Senden"


def test_image_refs_have_section_assignment(page):
    refs = {r.url: r for r in page.images}
    assert refs["https://example.com/media/hero-bg.jpg"].section_id == "intro"
    assert refs["https://example.com/media/hero-bg.jpg"].block_index == 0
    assert refs["https://example.com/media/team.jpg"].block_index == 3
    assert "https://example.com/media/logo.svg" not in refs  # header logo belongs to navigation


def test_flat_content_is_split_at_headings():
    html = "<body><h1>A</h1><p>a</p><h2>B</h2><p>b</p><h2>C</h2><p>c</p></body>"
    page = ContentExtractor(URLNormalizer("https://example.com/")).extract(html, "https://example.com/")
    assert len(page.sections) == 3
    assert [plain_text(s["blocks"][0]["content"]) for s in page.sections] == ["A", "B", "C"]


def test_unknown_inline_text_is_kept():
    html = "<main><custom-widget><span>Wichtiger Hinweis</span></custom-widget><div>Loser Text <b>fett</b></div></main>"
    page = ContentExtractor(URLNormalizer("https://example.com/")).extract(html, "https://example.com/")
    texts = [plain_text(b["content"]) for s in page.sections for b in s["blocks"]]
    assert texts == ["Wichtiger Hinweis", "Loser Text fett"]
