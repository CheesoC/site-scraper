"""Builds examples/sample-website-source – a small, schema-valid Content Archive v1.0.

The archive is committed; this script only exists to regenerate it consistently:

    python examples/build_sample.py
"""

from __future__ import annotations

import hashlib
import json
import struct
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent / "sample-website-source"
BASE = "https://www.beispiel-agentur.de"
V = "1.0"


def t(text, *marks):
    node = {"type": "text", "text": text}
    if marks:
        node["marks"] = list(marks)
    return node


def link(path, *children, external=False, href=None):
    return {
        "type": "link",
        "href": href or BASE + path,
        "path": None if external else path,
        "external": external,
        "children": list(children),
    }


def h(level, text):
    return {"type": "heading", "level": level, "content": [t(text)]}


def p(*content):
    return {"type": "paragraph", "content": list(content)}


def nav(label, path, order, depth=0, children=None, type_="main", external=False, url=None):
    return {
        "label": label,
        "url": url if url is not None else (BASE + path if path else None),
        "path": None if external else path,
        "external": external,
        "order": order,
        "depth": depth,
        "type": type_,
        "children": children or [],
    }


def png(width, height, rgb):
    raw = b"".join(b"\x00" + bytes(rgb) * width for _ in range(height))

    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)

    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw))
        + chunk(b"IEND", b"")
    )


ASSETS = {
    "logo.svg": (
        b'<svg xmlns="http://www.w3.org/2000/svg" width="120" height="32" viewBox="0 0 120 32">'
        b'<rect width="32" height="32" rx="6" fill="#2563eb"/><text x="40" y="22" font-family="sans-serif" '
        b'font-size="16">Beispiel</text></svg>',
        "image/svg+xml",
        (120, 32),
    ),
    "hero.png": (png(64, 32, (37, 99, 235)), "image/png", (64, 32)),
    "webdesign.png": (png(32, 32, (16, 185, 129)), "image/png", (32, 32)),
    "seo.png": (png(32, 32, (245, 158, 11)), "image/png", (32, 32)),
    "team-1.png": (png(24, 24, (236, 72, 153)), "image/png", (24, 24)),
    "team-2.png": (png(24, 24, (139, 92, 246)), "image/png", (24, 24)),
}
registry: dict[str, dict] = {}


def asset(name):
    data, ctype, (w, hgt) = ASSETS[name]
    sha = hashlib.sha256(data).hexdigest()
    file = f"assets/images/{sha[:8]}-{name}"
    if name not in registry:
        registry[name] = {
            "id": sha[:16],
            "file": file,
            "originalUrls": [f"{BASE}/media/{name}"],
            "contentType": ctype,
            "bytes": len(data),
            "sha256": sha,
            "width": w,
            "height": hgt,
            "pages": [],
            "_data": data,
        }
    return registry[name]


def img(name, alt, caption=None, role="content"):
    a = asset(name)
    block = {
        "type": "image",
        "src": a["file"],
        "originalSrc": a["originalUrls"][0],
        "alt": alt,
        "width": a["width"],
        "height": a["height"],
        "role": role,
    }
    if caption:
        block["caption"] = [t(caption)]
    return block


CTA_SECTION = {
    "id": "cta",
    "type": "cta",
    "blocks": [
        h(2, "Bereit für Ihr Projekt?"),
        p(t("Wir freuen uns auf Ihre Nachricht.")),
        {"type": "button", "label": "Kontakt aufnehmen", "href": BASE + "/kontakt", "path": "/kontakt", "external": False, "variant": "primary"},
    ],
}

PAGES = [
    {
        "path": "/",
        "dir": "index",
        "title": "Beispiel Agentur – Webdesign & SEO",
        "description": "Wir gestalten Websites, die gefunden werden.",
        "sections": [
            {
                "id": "hero",
                "type": "hero",
                "source": {"tag": "section", "id": "hero", "classes": ["hero"]},
                "blocks": [
                    h(1, "Websites, die gefunden werden"),
                    p(t("Wir sind eine "), t("unabhängige", "italic"), t(" Agentur für "), t("Webdesign", "bold"), t(" und "), link("/leistungen/seo", t("SEO")), t(".")),
                    img("hero.png", "Abstrakte Illustration einer Website", role="background"),
                    {"type": "button", "label": "Leistungen ansehen", "href": BASE + "/leistungen", "path": "/leistungen", "external": False, "variant": "primary"},
                ],
            },
            {
                "id": "features",
                "type": "cards",
                "blocks": [
                    h(2, "Unsere Leistungen"),
                    {
                        "type": "card",
                        "link": {"href": BASE + "/leistungen/webdesign", "path": "/leistungen/webdesign", "external": False},
                        "blocks": [img("webdesign.png", "Webdesign Icon", role="icon"), h(3, "Webdesign"), p(t("Moderne, schnelle und barrierearme Websites."))],
                    },
                    {
                        "type": "card",
                        "link": {"href": BASE + "/leistungen/seo", "path": "/leistungen/seo", "external": False},
                        "blocks": [img("seo.png", "SEO Icon", role="icon"), h(3, "SEO"), p(t("Sichtbarkeit in Suchmaschinen, nachhaltig."))],
                    },
                ],
            },
            {
                "id": "testimonials",
                "type": "testimonials",
                "blocks": [
                    h(2, "Das sagen unsere Kunden"),
                    {"type": "quote", "blocks": [p(t("Schnell, zuverlässig und kreativ."))], "cite": [t("Anna M., Bäckerei Müller")]},
                ],
            },
            CTA_SECTION,
        ],
    },
    {
        "path": "/leistungen",
        "dir": "leistungen",
        "title": "Unsere Leistungen",
        "description": "Unsere Leistungen im Überblick.",
        "breadcrumbs": [("Start", "/"), ("Leistungen", "/leistungen")],
        "sections": [
            {
                "id": "s1",
                "type": "content",
                "blocks": [
                    h(1, "Unsere Leistungen"),
                    p(t("Unsere Leistungen im Überblick.")),
                    img("hero.png", "Unsere Leistungen", caption="Ein Überblick"),
                    h(2, "Webdesign"),
                    p(t("Individuelle Websites. "), link("/leistungen/webdesign", t("Mehr erfahren"))),
                    img("webdesign.png", "Webdesign"),
                    h(2, "SEO"),
                    p(t("Technisches SEO, Content und Monitoring. "), link("/leistungen/seo", t("Mehr erfahren"))),
                    {
                        "type": "table",
                        "caption": [t("Pakete")],
                        "head": [[{"content": [t("Paket")], "header": True}, {"content": [t("Preis")], "header": True}]],
                        "rows": [
                            [{"content": [t("Start")]}, {"content": [t("ab 1.900 €")]}],
                            [{"content": [t("Business", "bold")]}, {"content": [t("ab 4.900 €")]}],
                        ],
                    },
                ],
            },
            CTA_SECTION,
        ],
    },
    {
        "path": "/leistungen/webdesign",
        "dir": "leistungen/webdesign",
        "title": "Webdesign",
        "description": "Websites mit System.",
        "breadcrumbs": [("Start", "/"), ("Leistungen", "/leistungen"), ("Webdesign", "/leistungen/webdesign")],
        "sections": [
            {
                "id": "s1",
                "type": "content",
                "blocks": [
                    h(1, "Webdesign"),
                    p(t("So arbeiten wir:")),
                    {
                        "type": "list",
                        "ordered": True,
                        "items": [
                            {"content": [t("Analyse")]},
                            {
                                "content": [t("Konzept")],
                                "blocks": [{"type": "list", "ordered": False, "items": [{"content": [t("Sitemap")]}, {"content": [t("Wireframes")]}]}],
                            },
                            {"content": [t("Umsetzung")]},
                        ],
                    },
                    {"type": "divider"},
                    {"type": "embed", "provider": "youtube", "url": "https://www.youtube.com/embed/dQw4w9WgXcQ", "title": "Unser Prozess im Video"},
                    {"type": "code", "text": "<h1>Hallo Welt</h1>", "language": "html"},
                ],
            }
        ],
    },
    {
        "path": "/leistungen/seo",
        "dir": "leistungen/seo",
        "title": "SEO",
        "description": "Gefunden werden.",
        "breadcrumbs": [("Start", "/"), ("Leistungen", "/leistungen"), ("SEO", "/leistungen/seo")],
        "sections": [
            {"id": "s1", "type": "content", "blocks": [h(1, "SEO"), p(t("Suchmaschinenoptimierung mit Plan."), {"type": "break"}, t("Ohne Tricks."))]},
            {
                "id": "faq",
                "type": "faq",
                "blocks": [
                    h(2, "Häufige Fragen"),
                    {
                        "type": "accordion",
                        "items": [
                            {"title": [t("Wie lange dauert SEO?")], "blocks": [p(t("Erste Ergebnisse meist nach 3–6 Monaten."))]},
                            {"title": [t("Was kostet SEO?")], "blocks": [p(t("Siehe "), link("/leistungen", t("Pakete")), t("."))]},
                        ],
                    },
                ],
            },
            {
                "id": "legacy",
                "type": "generic",
                "blocks": [
                    {"type": "html", "html": "<div><span>Widget-Inhalt</span> <abbr title=\"Search Engine Optimization\">SEO</abbr></div>", "text": "Widget-Inhalt SEO", "reason": "unclassified element <div class=\"widget\">"},
                ],
            },
        ],
    },
    {
        "path": "/ueber-uns",
        "dir": "ueber-uns",
        "title": "Über uns",
        "description": "Das Team hinter der Agentur.",
        "sections": [
            {"id": "s1", "type": "content", "blocks": [h(1, "Über uns"), p(t("Seit 2012 in Musterstadt."))]},
            {
                "id": "team",
                "type": "gallery",
                "blocks": [
                    h(2, "Team"),
                    {"type": "gallery", "images": [img("team-1.png", "Erika Muster", caption="Erika Muster, Design"), img("team-2.png", "Max Muster", caption="Max Muster, Entwicklung")]},
                ],
            },
        ],
    },
    {
        "path": "/kontakt",
        "dir": "kontakt",
        "title": "Kontakt",
        "description": "So erreichen Sie uns.",
        "sections": [
            {
                "id": "s1",
                "type": "content",
                "blocks": [
                    h(1, "Kontakt"),
                    p(t("Telefon: "), link("", t("+49 123 456789"), external=True, href="tel:+49123456789"), {"type": "break"}, t("E-Mail: "), link("", t("hallo@beispiel-agentur.de"), external=True, href="mailto:hallo@beispiel-agentur.de")),
                ],
            },
            {
                "id": "form",
                "type": "form",
                "blocks": [
                    {
                        "type": "form",
                        "action": BASE + "/kontakt/senden",
                        "method": "post",
                        "submitLabel": "Absenden",
                        "fields": [
                            {"name": "name", "label": "Name", "inputType": "text", "required": True},
                            {"name": "email", "label": "E-Mail", "inputType": "email", "required": True},
                            {"name": "thema", "label": "Thema", "inputType": "select", "required": False, "options": ["Webdesign", "SEO"]},
                            {"name": "nachricht", "label": "Nachricht", "inputType": "textarea", "required": True},
                        ],
                    },
                    {"type": "embed", "provider": "map", "url": "https://www.openstreetmap.org/export/embed.html?bbox=13.3,52.5,13.4,52.6", "title": "Anfahrt"},
                ],
            },
        ],
    },
    {
        "path": "/impressum",
        "dir": "impressum",
        "title": "Impressum",
        "description": None,
        "sections": [{"id": "s1", "type": "content", "blocks": [h(1, "Impressum"), p(t("Beispiel Agentur GmbH"), {"type": "break"}, t("Musterstraße 1, 12345 Musterstadt"))]}],
    },
]

NAVIGATION = {
    "schemaVersion": V,
    "main": [
        nav("Start", "/", 0),
        nav(
            "Leistungen",
            "/leistungen",
            1,
            children=[nav("Webdesign", "/leistungen/webdesign", 0, depth=1), nav("SEO", "/leistungen/seo", 1, depth=1)],
        ),
        nav("Über uns", "/ueber-uns", 2),
        nav("Kontakt", "/kontakt", 3),
    ],
    "footer": [
        nav(
            "Agentur",
            None,
            0,
            type_="footer",
            children=[nav("Über uns", "/ueber-uns", 0, 1, type_="footer"), nav("Kontakt", "/kontakt", 1, 1, type_="footer")],
        ),
        nav(
            "Rechtliches",
            None,
            1,
            type_="footer",
            children=[
                nav("Impressum", "/impressum", 0, 1, type_="footer"),
                nav("LinkedIn", None, 1, 1, type_="footer", external=True, url="https://www.linkedin.com/"),
            ],
        ),
    ],
    "logo": None,
    "cta": [nav("Projekt anfragen", "/kontakt", 0, type_="cta")],
    "menus": [],
}


def iter_images(blocks, section_id, out, counter):
    for index, block in enumerate(blocks):
        kind = block["type"]
        if kind == "image":
            counter[0] += 1
            out.append((block, section_id, index, counter[0] - 1))
        elif kind == "gallery":
            for image in block["images"]:
                counter[0] += 1
                out.append((image, section_id, index, counter[0] - 1))
        for key in ("blocks",):
            if key in block:
                iter_images(block[key], section_id, out, counter)
        if kind == "accordion":
            for item in block["items"]:
                iter_images(item["blocks"], section_id, out, counter)


def text_of(nodes):
    out = []
    for node in nodes:
        if node["type"] == "text":
            out.append(node["text"])
        elif node["type"] == "link":
            out.append(text_of(node["children"]))
        else:
            out.append("\n")
    return "".join(out)


def markdown(page):
    lines = []
    for section in page["sections"]:
        for block in section["blocks"]:
            if block["type"] == "heading":
                lines.append("#" * block["level"] + " " + text_of(block["content"]))
            elif block["type"] == "paragraph":
                lines.append(text_of(block["content"]))
            elif block["type"] == "image":
                lines.append(f"![{block['alt']}]({block['originalSrc']})")
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def write(rel, data):
    target = ROOT / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(data, bytes):
        target.write_bytes(data)
    elif isinstance(data, str):
        target.write_text(data, encoding="utf-8")
    else:
        target.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main():
    import shutil

    if ROOT.exists():
        shutil.rmtree(ROOT)
    logo = asset("logo.svg")
    NAVIGATION["logo"] = {
        "href": BASE + "/",
        "path": "/",
        "external": False,
        "label": "Beispiel Agentur",
        "image": logo["file"],
        "imageUrl": logo["originalUrls"][0],
        "alt": "Beispiel Agentur Logo",
    }
    logo["pages"] = [page["path"] for page in PAGES]
    NAVIGATION["menus"] = [
        {"id": "menu-1", "type": "main", "label": "Hauptmenü", "selector": "header nav", "ambiguous": False, "pages": len(PAGES), "items": NAVIGATION["main"]},
        {"id": "menu-2", "type": "footer", "label": None, "selector": "footer", "ambiguous": False, "pages": len(PAGES), "items": NAVIGATION["footer"]},
    ]

    manifest_pages = []
    links = {}
    for page in PAGES:
        crumbs = [nav(label, path, i, type_="breadcrumb") for i, (label, path) in enumerate(page.get("breadcrumbs", []))]
        h1 = next((text_of(b["content"]) for s in page["sections"] for b in s["blocks"] if b["type"] == "heading" and b["level"] == 1), None)
        content = {
            "schemaVersion": V,
            "path": page["path"],
            "url": BASE + page["path"],
            "title": page["title"],
            "meta": {
                "title": page["title"],
                "description": page["description"],
                "canonical": BASE + page["path"],
                "lang": "de",
                "h1": h1,
                "robots": None,
                "og": {"title": page["title"], "description": page["description"], "image": None, "imageUrl": None, "type": "website", "url": BASE + page["path"]},
                "structuredData": [],
            },
            "sections": page["sections"],
        }
        if crumbs:
            content["breadcrumbs"] = crumbs
        found = []
        for section in page["sections"]:
            iter_images(section["blocks"], section["id"], found, [0] if not found else [len(found)])
        images = []
        for order, (block, section_id, block_index, _) in enumerate(found):
            images.append(
                {
                    "originalUrl": block["originalSrc"],
                    "src": block["src"],
                    "assetId": next(a["id"] for a in registry.values() if a["file"] == block["src"]),
                    "alt": block["alt"],
                    "caption": text_of(block["caption"]) if block.get("caption") else None,
                    "sectionId": section_id,
                    "blockIndex": block_index,
                    "order": order,
                    "role": block.get("role", "content"),
                }
            )
            for a in registry.values():
                if a["file"] == block["src"] and page["path"] not in a["pages"]:
                    a["pages"].append(page["path"])
        d = "pages/" + page["dir"]
        write(f"{d}/content.json", content)
        write(f"{d}/content.md", markdown(content))
        write(f"{d}/original.html", f"<!doctype html><html lang=\"de\"><head><title>{page['title']}</title></head><body><main><h1>{h1}</h1></main></body></html>\n")
        write(f"{d}/images.json", {"schemaVersion": V, "kind": "page", "path": page["path"], "images": images})
        manifest_pages.append(
            {
                "path": page["path"],
                "title": page["title"],
                "originalUrl": BASE + page["path"],
                "finalUrl": BASE + page["path"],
                "normalizedUrl": BASE + page["path"],
                "canonical": BASE + page["path"],
                "aliases": [page["path"] + ".html"] if page["path"] == "/impressum" else [],
                "dir": d,
                "content": f"{d}/content.json",
                "markdown": f"{d}/content.md",
                "html": f"{d}/original.html",
                "images": f"{d}/images.json",
                "depth": page["path"].count("/") if page["path"] != "/" else 0,
                "status": 200,
            }
        )
        out_links = set()

        def collect(node):
            if isinstance(node, dict):
                if node.get("type") in ("link", "button") and node.get("path"):
                    out_links.add(node["path"])
                if "link" in node and isinstance(node["link"], dict) and node["link"].get("path"):
                    out_links.add(node["link"]["path"])
                for value in node.values():
                    collect(value)
            elif isinstance(node, list):
                for value in node:
                    collect(value)

        collect(page["sections"])
        links[page["path"]] = sorted(out_links)

    for a in registry.values():
        write(a["file"], a.pop("_data"))
    write("assets/images.json", {"schemaVersion": V, "kind": "registry", "assets": list(registry.values())})
    write("navigation.json", NAVIGATION)

    titles = {p["path"]: p["title"] for p in PAGES}
    tree = {"path": "/", "segment": "", "title": titles["/"], "exported": True, "children": []}
    for path in sorted(titles):
        if path == "/":
            continue
        node = tree
        parts = path.strip("/").split("/")
        for i, seg in enumerate(parts):
            sub = "/" + "/".join(parts[: i + 1])
            child = next((c for c in node["children"] if c["path"] == sub), None)
            if child is None:
                child = {"path": sub, "segment": seg, "title": titles.get(sub), "exported": sub in titles, "children": []}
                node["children"].append(child)
            node = child
    write("sitemap.json", {"schemaVersion": V, "tree": tree, "links": links})

    write(
        "manifest.json",
        {
            "schemaVersion": V,
            "sourceUrl": BASE + "/",
            "crawledAt": "2026-11-20T12:00:00Z",
            "producer": {"name": "examples/build_sample.py", "version": "1.0"},
            "site": {"name": "Beispiel Agentur", "lang": "de", "homePath": "/"},
            "files": {"navigation": "navigation.json", "sitemap": "sitemap.json", "assets": "assets/images.json", "report": "reports/crawl-report.json"},
            "pages": manifest_pages,
        },
    )
    write(
        "reports/crawl-report.json",
        {
            "schemaVersion": V,
            "kind": "crawl",
            "status": "complete",
            "startedAt": "2026-11-20T12:00:00Z",
            "finishedAt": "2026-11-20T12:00:05Z",
            "config": {"maxPages": 100, "maxDepth": 5},
            "limitsReached": [],
            "stats": {"discovered": len(PAGES), "exported": len(PAGES), "failed": 0, "assets": len(registry), "assetsFailed": 0, "brokenLinks": 0},
            "issues": [],
        },
    )
    for kind in ("failed-urls", "broken-links", "missing-assets"):
        write(f"reports/{kind}.json", {"schemaVersion": V, "kind": kind, "items": []})
    print(f"wrote {len(PAGES)} pages, {len(registry)} assets to {ROOT}")


if __name__ == "__main__":
    main()
