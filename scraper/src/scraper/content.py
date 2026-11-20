"""ContentExtractor: turns a rendered HTML page into ordered sections and blocks (Content Schema v1.0).

Principles
* Document order is preserved: sections and blocks follow the DOM order.
* Rule based: semantic HTML first (h1-h6, p, ul, table, figure, details, ...), light heuristics for
  section types (hero, cards, faq, ...).
* No information loss: content that cannot be mapped to a block type is kept as a sanitized
  ``html`` fallback block.
"""

from __future__ import annotations

import base64
from html import escape
import hashlib
import json
import re
from dataclasses import dataclass, field
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Comment, Doctype, NavigableString, ProcessingInstruction, Tag

from .sanitize import sanitize_element
from .urls import URLNormalizer, slugify

HEADINGS = {"h1", "h2", "h3", "h4", "h5", "h6"}
MARK_TAGS = {
    "strong": "bold", "b": "bold", "em": "italic", "i": "italic", "cite": "italic", "dfn": "italic",
    "u": "underline", "ins": "underline", "s": "strike", "del": "strike", "strike": "strike",
    "code": "code", "kbd": "code", "samp": "code", "tt": "code", "var": "italic",
    "sub": "sub", "sup": "sup", "mark": "mark",
}
INLINE_TAGS = set(MARK_TAGS) | {
    "a", "abbr", "bdi", "bdo", "data", "q", "small", "span", "time", "label", "font", "big", "wbr", "br",
    "output", "acronym", "nobr",
}
SKIP_TAGS = {
    "script", "style", "noscript", "template", "link", "meta", "head", "title", "base", "source", "track",
    "param", "map", "area", "dialog", "slot",
}
FORM_CONTROLS = {"input", "option", "optgroup", "datalist", "select", "textarea", "label", "output", "meter", "progress"}
CONTAINER_TAGS = {
    "div", "section", "article", "aside", "header", "footer", "main", "fieldset", "address", "center",
    "hgroup", "search", "legend", "caption", "body", "html",
}
BLOCK_DESCENDANTS = HEADINGS | {
    "p", "div", "ul", "ol", "dl", "table", "img", "picture", "figure", "section", "article", "blockquote",
    "pre", "iframe", "video", "audio", "form", "details", "hr", "header", "footer", "aside",
}
EMBED_TAGS = {"iframe", "video", "audio", "object", "embed"}
FALLBACK_TAGS = {"canvas", "math", "marquee", "applet", "frameset", "frame", "object", "embed", "portal"}

LAZY_SRC_ATTRS = ("data-src", "data-lazy-src", "data-original", "data-lazy", "data-url", "data-echo", "data-full-src", "data-hi-res-src")
LAZY_SRCSET_ATTRS = ("data-srcset", "data-lazy-srcset", "srcset")
BG_ATTRS = ("data-scraper-bg", "data-bg", "data-background", "data-bg-src", "data-background-image")
BG_URL_RE = re.compile(r"url\(\s*(['\"]?)(.*?)\1\s*\)", re.IGNORECASE)
BUTTON_CLASS_RE = re.compile(r"(^|[\s_-])(btn|button|cta|call-to-action)([\s_-]|$)", re.IGNORECASE)
SKIP_CLASS_RE = re.compile(
    r"(^|[\s_-])(cookie|cookies|consent|gdpr|cmp|cc-window|cookiebot|onetrust|sr-only|visually-hidden|screen-reader-text|skip-link)([\s_-]|$)",
    re.IGNORECASE,
)
BREADCRUMB_RE = re.compile(r"breadcrumb", re.IGNORECASE)
WS_RE = re.compile(r"\s+")

SECTION_KEYWORDS = [
    ("faq", re.compile(r"faq|accordion|fragen|questions", re.I)),
    ("testimonials", re.compile(r"testimonial|review|kundenstimme|referenz|bewertung|quote", re.I)),
    ("gallery", re.compile(r"gallery|galerie|carousel|slider|swiper|lightbox", re.I)),
    ("hero", re.compile(r"hero|banner|jumbotron|stage|masthead|intro-?header|keyvisual|key-visual", re.I)),
    ("cta", re.compile(r"(^|[\s_-])cta|call-to-action|newsletter", re.I)),
    ("cards", re.compile(r"cards?|features?|services?|leistungen|grid|tiles|kacheln|teaser", re.I)),
]


@dataclass
class ImageRef:
    block: dict
    url: str  # absolute URL or data: URI
    section_id: str | None = None
    block_index: int | None = None
    role: str = "content"
    data: bytes | None = None  # inline SVG / data URI payload


@dataclass
class LinkRef:
    node: dict  # dict with href/path/external keys that will be resolved by the exporter
    url: str | None  # normalized URL (None for non-http links)
    fragment: str = ""
    internal: bool = False
    is_page: bool = False


@dataclass
class PageExtraction:
    title: str
    meta: dict
    sections: list[dict]
    images: list[ImageRef] = field(default_factory=list)
    links: list[LinkRef] = field(default_factory=list)
    unsupported: list[str] = field(default_factory=list)
    text_length: int = 0

    def iter_blocks(self):
        def walk(blocks):
            for block in blocks:
                yield block
                for key in ("blocks",):
                    if key in block:
                        yield from walk(block[key])
                if block["type"] == "list":
                    for item in block["items"]:
                        yield from walk(item.get("blocks", []))
                if block["type"] == "accordion":
                    for item in block["items"]:
                        yield from walk(item["blocks"])
                if block["type"] == "gallery":
                    yield from block["images"]

        for section in self.sections:
            yield from walk(section["blocks"])


def collapse(text: str) -> str:
    return WS_RE.sub(" ", text)


def class_string(el: Tag) -> str:
    classes = el.get("class") or []
    if isinstance(classes, str):
        classes = classes.split()
    return " ".join(classes) + " " + str(el.get("id") or "")


def plain_text(nodes: list[dict]) -> str:
    out = []
    for node in nodes:
        if node["type"] == "text":
            out.append(node["text"])
        elif node["type"] == "link":
            out.append(plain_text(node["children"]))
        else:
            out.append("\n")
    return "".join(out)


def parse_srcset(value: str) -> list[tuple[str, float]]:
    candidates = []
    for part in re.split(r",\s+(?=\S)", value.strip()):
        bits = part.strip().split()
        if not bits:
            continue
        url, weight = bits[0].rstrip(","), 1.0
        if len(bits) > 1:
            descriptor = bits[-1].lower()
            try:
                if descriptor.endswith("w"):
                    weight = float(descriptor[:-1])
                elif descriptor.endswith("x"):
                    weight = float(descriptor[:-1]) * 1000
            except ValueError:
                pass
        candidates.append((url, weight))
    return candidates


def to_int(value) -> int | None:
    if value is None:
        return None
    match = re.match(r"\s*(\d+)", str(value))
    return int(match.group(1)) if match else None


def is_placeholder(src: str) -> bool:
    lowered = src.lower()
    return lowered.startswith("data:") and len(src) < 200 or "placeholder" in lowered or "blank.gif" in lowered or "spacer.gif" in lowered


class ContentExtractor:
    def __init__(self, normalizer: URLNormalizer):
        self.normalizer = normalizer

    # ================================================================ public
    def extract(self, html: str, page_url: str) -> PageExtraction:
        soup = BeautifulSoup(html, "lxml")
        base_tag = soup.find("base", href=True)
        self.base = urljoin(page_url, base_tag["href"]) if base_tag else page_url
        self.page_url = page_url
        self.images: list[ImageRef] = []
        self.links: list[LinkRef] = []
        self.unsupported: list[str] = []
        self._section_ids: set[str] = set()

        meta = self.extract_meta(soup)
        main = self.find_main(soup)
        sections = self.build_sections(main)
        for section in sections:
            for index, block in enumerate(section["blocks"]):
                for ref in self.images:
                    if ref.section_id is None and _contains(block, ref.block):
                        ref.section_id = section["id"]
                        ref.block_index = index
        text_length = sum(len(plain_text(b.get("content", []))) for s in sections for b in s["blocks"] if "content" in b)
        title = meta.get("title") or meta.get("h1") or ""
        return PageExtraction(
            title=title,
            meta=meta,
            sections=sections,
            images=self.images,
            links=self.links,
            unsupported=self.unsupported,
            text_length=text_length,
        )

    # ================================================================== meta
    def extract_meta(self, soup: BeautifulSoup) -> dict:
        def meta_content(*names: str) -> str | None:
            for name in names:
                tag = soup.find("meta", attrs={"property": name}) or soup.find("meta", attrs={"name": name})
                if tag and tag.get("content"):
                    return collapse(tag["content"]).strip()
            return None

        title_tag = soup.find("title")
        canonical = None
        for link in soup.find_all("link", href=True):
            rel = link.get("rel") or []
            rel = rel if isinstance(rel, list) else [rel]
            if "canonical" in [r.lower() for r in rel]:
                canonical = urljoin(self.base, link["href"])
                break
        html_tag = soup.find("html")
        h1 = soup.find("h1")
        og_image_url = meta_content("og:image", "og:image:url", "twitter:image")
        if og_image_url:
            og_image_url = urljoin(self.base, og_image_url)
        structured = []
        for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
            try:
                data = json.loads(script.string or script.get_text() or "")
            except (ValueError, TypeError):
                continue
            if isinstance(data, list):
                structured.extend(data)
            else:
                structured.append(data)
        return {
            "title": collapse(title_tag.get_text()).strip() if title_tag else None,
            "description": meta_content("description"),
            "canonical": canonical,
            "lang": (html_tag.get("lang") or None) if html_tag else None,
            "h1": collapse(h1.get_text(" ")).strip() if h1 else None,
            "robots": meta_content("robots"),
            "og": {
                "title": meta_content("og:title"),
                "description": meta_content("og:description"),
                "image": None,
                "imageUrl": og_image_url,
                "type": meta_content("og:type"),
                "url": meta_content("og:url"),
            },
            "structuredData": structured,
        }

    # ============================================================ main area
    def find_main(self, soup: BeautifulSoup) -> Tag:
        body = soup.body or soup
        for tag in list(body.find_all(True)):
            if tag.decomposed:
                continue
            if self.should_skip(tag):
                tag.decompose()
        main = body.find("main") or body.find(attrs={"role": "main"})
        if main is None:
            articles = body.find_all("article")
            body_len = len(body.get_text(" ", strip=True)) or 1
            if len(articles) == 1 and len(articles[0].get_text(" ", strip=True)) / body_len > 0.5:
                main = articles[0]
        if main is None:
            main = body
            for selector in ("header", "footer", "[role=banner]", "[role=contentinfo]"):
                for tag in main.select(selector):
                    # only page-level header/footer, not <header> of an article/section
                    if tag.find_parent(["article", "section", "main"]) is None:
                        tag.decompose()
        for tag in main.select("nav, [role=navigation]"):
            tag.decompose()
        for tag in main.find_all(class_=BREADCRUMB_RE):
            tag.decompose()
        return main

    def should_skip(self, tag: Tag) -> bool:
        if tag.name in SKIP_TAGS:
            return True
        if tag.get("aria-hidden") == "true" and tag.name not in ("img", "svg", "picture"):
            return True
        if tag.name == "svg":
            return False
        cls = class_string(tag)
        if cls.strip() and SKIP_CLASS_RE.search(cls):
            return True
        return False

    # ============================================================== sections
    def build_sections(self, main: Tag) -> list[dict]:
        container = main
        while True:
            children = self.element_children(container)
            texts = [c for c in container.children if isinstance(c, NavigableString) and str(c).strip() and not isinstance(c, Comment)]
            if len(children) == 1 and not texts and children[0].name in CONTAINER_TAGS | {"div"}:
                container = children[0]
                continue
            break
        sections: list[dict] = []
        self._collect_sections(container, sections, top=True)
        return [s for s in sections if s["blocks"]]

    def element_children(self, el: Tag) -> list[Tag]:
        return [c for c in el.children if isinstance(c, Tag) and c.name not in SKIP_TAGS]

    def is_section_wrapper(self, el: Tag) -> bool:
        children = self.element_children(el)
        sectionish = [c for c in children if c.name in ("section", "article")]
        return len(sectionish) >= 2 and len(sectionish) >= len(children) - 1

    def _collect_sections(self, container: Tag, sections: list[dict], top: bool) -> None:
        loose: list = []

        def flush_loose():
            if not loose:
                return
            blocks = self.walk_nodes(loose)
            for chunk in self.split_by_headings(blocks):
                sections.append(self.make_section(None, chunk, len(sections)))
            loose.clear()

        for child in container.children:
            if isinstance(child, Tag) and child.name in SKIP_TAGS:
                continue
            is_container = isinstance(child, Tag) and (
                child.name in ("section", "article", "aside", "header", "footer", "form")
                or (child.name in CONTAINER_TAGS or "-" in child.name) and self.has_block_content(child)
            )
            if not is_container:
                loose.append(child)
                continue
            flush_loose()
            if self.is_section_wrapper(child):
                self._collect_sections(child, sections, top=False)
                continue
            blocks = self.block(child)
            chunks = self.split_by_headings(blocks) if child.name in ("div",) and not self.card_grid_items(child) else [blocks]
            for chunk in chunks:
                sections.append(self.make_section(child, chunk, len(sections)))
        flush_loose()

    def has_block_content(self, el: Tag) -> bool:
        return el.find(BLOCK_DESCENDANTS) is not None or bool(el.get_text(strip=True))

    @staticmethod
    def split_by_headings(blocks: list[dict]) -> list[list[dict]]:
        """Split a flat block list at h1/h2 headings (only if there are at least two of them)."""
        top_heads = [i for i, b in enumerate(blocks) if b["type"] == "heading" and b["level"] <= 2]
        if len(top_heads) < 2:
            return [blocks] if blocks else []
        chunks, current = [], []
        for block in blocks:
            if block["type"] == "heading" and block["level"] <= 2 and current:
                chunks.append(current)
                current = []
            current.append(block)
        if current:
            chunks.append(current)
        return chunks

    def make_section(self, el: Tag | None, blocks: list[dict], index: int) -> dict:
        raw_id = slugify(str(el.get("id"))) if el is not None and el.get("id") else f"section-{index + 1}"
        section_id = raw_id
        n = 2
        while section_id in self._section_ids:
            section_id = f"{raw_id}-{n}"
            n += 1
        self._section_ids.add(section_id)
        section = {"id": section_id, "type": self.classify_section(el, blocks, index), "blocks": blocks}
        if el is not None:
            classes = el.get("class") or []
            section["source"] = {
                "tag": el.name,
                "id": el.get("id") or None,
                "classes": classes if isinstance(classes, list) else str(classes).split(),
            }
        return section

    def classify_section(self, el: Tag | None, blocks: list[dict], index: int) -> str:
        types = [b["type"] for b in blocks]
        hint = class_string(el) if el is not None else ""
        heading_text = " ".join(plain_text(b["content"]) for b in blocks if b["type"] == "heading")
        text_len = sum(len(plain_text(b.get("content", []))) for b in blocks)
        if el is not None and el.name == "form" or "form" in types and text_len < 400:
            return "form"
        if "accordion" in types and (types.count("accordion") * 3 >= len(types) or re.search(r"faq|fragen|questions", heading_text + hint, re.I)):
            return "faq"
        if "card" in types:
            if re.search(r"testimonial|review|kundenstimme|referenz|bewertung", hint + heading_text, re.I) or all(
                any(c["type"] == "quote" for c in b["blocks"]) for b in blocks if b["type"] == "card"
            ):
                return "testimonials"
            return "cards"
        if types.count("quote") >= 2:
            return "testimonials"
        if "gallery" in types or (types.count("image") >= 3 and text_len < 200):
            return "gallery"
        for name, pattern in SECTION_KEYWORDS:
            if hint.strip() and pattern.search(hint):
                if name == "hero" or name in ("faq", "testimonials", "gallery", "cta"):
                    return name
        has_h1 = any(b["type"] == "heading" and b["level"] == 1 for b in blocks)
        has_media = "image" in types or "embed" in types
        if index == 0 and has_h1 and (has_media or "button" in types) and text_len < 1200:
            return "hero"
        if "button" in types and text_len < 350 and len(blocks) <= 5 and index > 0:
            return "cta"
        if any(t in types for t in ("heading", "paragraph", "list", "table", "quote", "code", "image")):
            return "content"
        return "generic"

    # ================================================================ blocks
    def walk(self, el: Tag) -> list[dict]:
        blocks = self.background_blocks(el)
        if (items := self.card_grid_items(el)) is not None:
            return blocks + self.post_process(self.cards_from(items, el))
        return blocks + self.walk_nodes(list(el.children))

    def walk_nodes(self, nodes: list) -> list[dict]:
        blocks: list[dict] = []
        buffer: list[dict] = []

        def flush():
            content = self.clean_inline(buffer)
            if content:
                blocks.append({"type": "paragraph", "content": content})
            buffer.clear()

        for child in nodes:
            if isinstance(child, (Comment, Doctype, ProcessingInstruction)):
                continue
            if isinstance(child, NavigableString):
                buffer.append({"type": "text", "text": collapse(str(child))})
                continue
            if not isinstance(child, Tag) or self.should_skip(child):
                continue
            name = child.name
            if name in INLINE_TAGS:
                has_blocks = name != "br" and child.find(BLOCK_DESCENDANTS) is not None
                if name == "a":
                    if has_blocks:
                        flush()
                        blocks.extend(self.linked_blocks(child))
                        continue
                    if self.is_button(child) and not plain_text(self.clean_inline(buffer)).strip():
                        flush()
                        button = self.button_block(child)
                        if button:
                            blocks.append(button)
                        continue
                elif has_blocks:
                    flush()
                    blocks.extend(self.walk(child))
                    continue
                buffer.extend(self.inline(child, frozenset()))
                continue
            if name == "svg" and buffer and not self.svg_is_content(child):
                continue
            flush()
            blocks.extend(self.block(child))
        flush()
        return self.post_process(blocks)

    def block(self, el: Tag) -> list[dict]:
        name = el.name
        if name in HEADINGS:
            content = self.clean_inline(self.inline(el, frozenset()))
            images = [b for img in el.find_all(["img", "picture"]) for b in self.image_blocks(img)]
            if not content:
                return images
            return [{"type": "heading", "level": int(name[1]), "content": content, "anchor": el.get("id") or None}] + images
        if name == "p":
            return self.walk_nodes(list(el.children))
        if name in ("ul", "ol", "menu"):
            items = self.card_grid_items(el)
            if items is not None:
                return self.cards_from(items, el)
            return [self.list_block(el)]
        if name == "dl":
            return [self.definition_list(el)]
        if name == "table":
            return self.table_block(el)
        if name == "blockquote":
            return [self.quote_block(el)]
        if name == "figure":
            return self.figure_blocks(el)
        if name in ("img", "picture"):
            return self.image_blocks(el)
        if name == "svg":
            return self.svg_blocks(el)
        if name in ("iframe", "video", "audio"):
            embed = self.embed_block(el)
            return [embed] if embed else []
        if name == "pre":
            code = el.find("code")
            classes = " ".join((code or el).get("class") or [])
            lang = re.search(r"(?:language|lang)-([\w+-]+)", classes)
            return [{"type": "code", "text": el.get_text(), "language": lang.group(1) if lang else None}]
        if name == "hr":
            return [{"type": "divider"}]
        if name == "details":
            return [self.details_block(el)]
        if name == "form":
            return self.form_blocks(el)
        if name == "button":
            return self.html_button(el)
        if name in FORM_CONTROLS - {"label"}:
            return []
        if name in FALLBACK_TAGS:
            return self.fallback(el, f"unsupported element <{name}>")
        if name in CONTAINER_TAGS or name in ("li", "dd", "dt", "td", "th", "tr", "tbody", "thead", "tfoot", "summary", "nav", "figcaption") or "-" in name:
            return self.walk(el)
        # unknown element: keep its content
        if el.find(True) is None and el.get_text(strip=True):
            return [{"type": "paragraph", "content": self.clean_inline(self.inline(el, frozenset()))}]
        return self.walk(el)

    def post_process(self, blocks: list[dict]) -> list[dict]:
        out: list[dict] = []
        for block in blocks:
            if block["type"] == "paragraph" and not block["content"]:
                continue
            if block["type"] == "accordion" and out and out[-1]["type"] == "accordion" and block.get("_details") and out[-1].get("_details"):
                out[-1]["items"].extend(block["items"])
                continue
            out.append(block)
        # galleries: >= 3 consecutive content images
        merged: list[dict] = []
        run: list[dict] = []

        def flush_run():
            if len(run) >= 3:
                merged.append({"type": "gallery", "images": list(run)})
            else:
                merged.extend(run)
            run.clear()

        for block in out:
            if block["type"] == "image" and block.get("role", "content") == "content" and not block.get("link"):
                run.append(block)
                continue
            flush_run()
            merged.append(block)
        flush_run()
        for block in merged:
            block.pop("_details", None)
        return merged

    # ---------------------------------------------------------------- inline
    def inline(self, el: Tag, marks: frozenset) -> list[dict]:
        name = el.name
        if name == "br":
            return [{"type": "break"}]
        if name == "a":
            node = self.link_node(el, marks)
            return [node] if node else self.inline_children(el, marks)
        if name in MARK_TAGS:
            marks = marks | {MARK_TAGS[name]}
        if name == "q":
            return [{"type": "text", "text": "„"}] + self.inline_children(el, marks) + [{"type": "text", "text": "“"}]
        return self.inline_children(el, marks)

    def inline_children(self, el: Tag, marks: frozenset) -> list[dict]:
        out: list[dict] = []
        for child in el.children:
            if isinstance(child, (Comment, Doctype, ProcessingInstruction)):
                continue
            if isinstance(child, NavigableString):
                node = {"type": "text", "text": collapse(str(child))}
                if marks:
                    node["marks"] = sorted(marks)
                out.append(node)
            elif isinstance(child, Tag):
                if self.should_skip(child) or child.name in ("img", "picture", "svg", "iframe", "video", "audio", "button") or child.name in FORM_CONTROLS - {"label"}:
                    continue
                out.extend(self.inline(child, marks))
        return out

    @staticmethod
    def clean_inline(nodes: list[dict]) -> list[dict]:
        """Merge adjacent text nodes, collapse whitespace and trim the edges."""
        merged: list[dict] = []
        for node in nodes:
            if node["type"] == "text":
                if merged and merged[-1]["type"] == "text" and merged[-1].get("marks") == node.get("marks"):
                    merged[-1] = {**merged[-1], "text": collapse(merged[-1]["text"] + node["text"])}
                    continue
                if merged and merged[-1]["type"] == "text" and merged[-1]["text"].endswith(" ") and node["text"].startswith(" "):
                    node = {**node, "text": node["text"].lstrip(" ")}
                merged.append(dict(node))
            elif node["type"] == "link":
                node["children"] = ContentExtractor.clean_inline(node["children"]) or [{"type": "text", "text": node["href"]}]
                merged.append(node)
            else:
                merged.append(node)
        # trim around edges and breaks
        for i, node in enumerate(merged):
            if node["type"] != "text":
                continue
            if i == 0 or merged[i - 1]["type"] == "break":
                node["text"] = node["text"].lstrip()
            if i == len(merged) - 1 or merged[i + 1]["type"] == "break":
                node["text"] = node["text"].rstrip()
        merged = [n for n in merged if not (n["type"] == "text" and n["text"] == "")]
        while merged and merged[0]["type"] == "break":
            merged.pop(0)
        while merged and merged[-1]["type"] == "break":
            merged.pop()
        if not plain_text(merged).strip():
            return []
        return merged

    # ----------------------------------------------------------------- links
    def link_target(self, href: str | None) -> dict | None:
        """Create a link target dict {href, path, external} and register it for later resolution."""
        if href is None:
            return None
        info = self.normalizer.classify(str(href), self.base)
        if info is None:
            return None
        target = {"href": info.href, "path": None, "external": not info.internal}
        if info.internal and info.url:
            target["path"] = self.normalizer.to_path(info.url) + (f"#{info.fragment}" if info.fragment else "")
        self.links.append(LinkRef(node=target, url=info.url, fragment=info.fragment, internal=info.internal, is_page=info.is_page))
        return target

    def link_node(self, el: Tag, marks: frozenset) -> dict | None:
        target = self.link_target(el.get("href"))
        if target is None:
            return None
        children = self.inline_children(el, marks)
        node = {"type": "link", **target, "children": children}
        if el.get("title"):
            node["title"] = collapse(el["title"]).strip()
        # keep identity with the registered LinkRef so that resolution updates this node
        self.links[-1].node = node
        return node

    def is_button(self, el: Tag) -> bool:
        cls = class_string(el)
        return bool(BUTTON_CLASS_RE.search(cls)) or el.get("role") == "button"

    def button_block(self, el: Tag) -> dict | None:
        label = collapse(el.get_text(" ")).strip() or collapse(el.get("aria-label") or el.get("title") or "").strip()
        if not label:
            return None
        target = self.link_target(el.get("href")) or {"href": str(el.get("href") or ""), "path": None, "external": False}
        cls = class_string(el).lower()
        variant = "secondary" if re.search(r"secondary|outline|ghost|light", cls) else "primary"
        block = {"type": "button", "label": label, **target, "variant": variant}
        if self.links and self.links[-1].node is target:
            self.links[-1].node = block
        return block

    def html_button(self, el: Tag) -> list[dict]:
        if el.get("aria-expanded") is not None or el.get("aria-controls") or el.get("data-toggle") or el.get("data-bs-toggle"):
            return []
        if (el.get("type") or "").lower() in ("submit", "reset"):
            return []
        label = collapse(el.get_text(" ")).strip()
        if not label:
            return []
        href = el.get("data-href") or el.get("formaction")
        target = self.link_target(href) if href else None
        target = target or {"href": "", "path": None, "external": False}
        block = {"type": "button", "label": label, **target, "variant": "primary"}
        if href and self.links and self.links[-1].node is target:
            self.links[-1].node = block
        return [block]

    def linked_blocks(self, a: Tag) -> list[dict]:
        """<a> wrapping block content: linked image(s) or a linked card."""
        text = a.get_text(strip=True)
        images = a.find_all(["img", "picture"])
        if not text and images:
            blocks = []
            for img in images:
                if img.name == "img" and img.find_parent("picture") is not None:
                    continue
                for block in self.image_blocks(img):
                    block["link"] = self.link_target(a.get("href"))
                    blocks.append(block)
            return blocks
        target = self.link_target(a.get("href"))
        inner = self.walk(a)
        return [{"type": "card", "blocks": inner, "link": target}]

    # ------------------------------------------------------------ lists etc.
    def list_block(self, el: Tag) -> dict:
        items = []
        for li in el.find_all("li", recursive=False) or [c for c in self.element_children(el) if c.name != "li"]:
            inline_nodes: list[dict] = []
            nested: list[dict] = []
            for child in li.children:
                if isinstance(child, (Comment, Doctype)):
                    continue
                if isinstance(child, NavigableString):
                    inline_nodes.append({"type": "text", "text": collapse(str(child))})
                elif isinstance(child, Tag) and not self.should_skip(child):
                    if child.name in INLINE_TAGS and child.find(BLOCK_DESCENDANTS) is None:
                        inline_nodes.extend(self.inline(child, frozenset()))
                    elif child.name == "p" and not nested and child.find(BLOCK_DESCENDANTS - {"p"}) is None:
                        if inline_nodes:
                            inline_nodes.append({"type": "break"})
                        inline_nodes.extend(self.inline_children(child, frozenset()))
                    else:
                        nested.extend(self.block(child) if child.name not in INLINE_TAGS else self.walk(child))
            item = {"content": self.clean_inline(inline_nodes)}
            if nested:
                item["blocks"] = nested
            if item["content"] or nested:
                items.append(item)
        return {"type": "list", "ordered": el.name == "ol", "items": items}

    def definition_list(self, el: Tag) -> dict:
        items: list[dict] = []
        for child in self.element_children(el):
            target = child
            if child.name == "div":  # <dl><div><dt/><dd/></div></dl>
                for sub in self.element_children(child):
                    self._dl_entry(sub, items)
                continue
            self._dl_entry(target, items)
        return {"type": "accordion", "items": items}

    def _dl_entry(self, el: Tag, items: list[dict]) -> None:
        if el.name == "dt":
            items.append({"title": self.clean_inline(self.inline(el, frozenset())), "blocks": []})
        elif el.name == "dd":
            if not items:
                items.append({"title": [], "blocks": []})
            items[-1]["blocks"].extend(self.walk(el))

    def details_block(self, el: Tag) -> dict:
        summary = el.find("summary")
        title = self.clean_inline(self.inline(summary, frozenset())) if summary else []
        body = [c for c in el.children if c is not summary]
        return {"type": "accordion", "items": [{"title": title, "blocks": self.walk_nodes(body)}], "_details": True}

    def table_block(self, el: Tag) -> list[dict]:
        if el.find("table") is not None or (el.get("role") == "presentation"):
            # layout table -> keep the cell contents as normal blocks
            blocks: list[dict] = []
            for cell in el.find_all(["td", "th"]):
                if cell.find_parent("table") is el:
                    blocks.extend(self.walk(cell))
            return blocks
        rows = [tr for tr in el.find_all("tr") if tr.find_parent("table") is el]
        head, body = [], []
        for tr in rows:
            cells = []
            for cell in tr.find_all(["td", "th"], recursive=False):
                entry = {"content": self.clean_inline(self.inline_children(cell, frozenset()))}
                if cell.name == "th":
                    entry["header"] = True
                for attr in ("colspan", "rowspan"):
                    value = to_int(cell.get(attr))
                    if value and value > 1:
                        entry[attr] = value
                cells.append(entry)
            in_head = tr.find_parent("thead") is not None
            if in_head or (not head and not body and cells and all(c.get("header") for c in cells)):
                head.append(cells)
            else:
                body.append(cells)
        block = {"type": "table", "rows": body}
        if head:
            block["head"] = head
        caption = el.find("caption")
        if caption:
            block["caption"] = self.clean_inline(self.inline(caption, frozenset()))
        images = [b for img in el.find_all("img") for b in self.image_blocks(img)]
        return [block] + images

    def quote_block(self, el: Tag, cite_el: Tag | None = None) -> dict:
        cite_tags = [t for t in el.find_all(["cite", "footer"]) if t.name == "footer" or t.parent is el]
        cite_nodes: list[dict] = []
        for tag in cite_tags:
            cite_nodes.extend(self.inline(tag, frozenset()))
            tag.extract()
        if cite_el is not None:
            cite_nodes.extend(self.inline(cite_el, frozenset()))
        block = {"type": "quote", "blocks": self.walk(el)}
        cite = self.clean_inline(cite_nodes)
        if cite:
            block["cite"] = cite
        return block

    def figure_blocks(self, el: Tag) -> list[dict]:
        caption_el = el.find("figcaption")
        quote = el.find("blockquote")
        if quote is not None:
            return [self.quote_block(quote, caption_el)]
        caption = self.clean_inline(self.inline(caption_el, frozenset())) if caption_el else []
        if caption_el is not None:
            caption_el.extract()
        blocks = self.walk(el)
        image_blocks = [b for b in blocks if b["type"] == "image"]
        if caption and len(image_blocks) == 1:
            image_blocks[0]["caption"] = caption
        elif caption:
            blocks.append({"type": "paragraph", "content": caption})
        return blocks

    # --------------------------------------------------------------- images
    def image_source(self, el: Tag) -> tuple[str | None, int | None, int | None]:
        img = el.find("img") if el.name == "picture" else el
        candidates: list[tuple[str, float]] = []
        sources = el.find_all("source") if el.name == "picture" else []
        if img is not None:
            for attr in LAZY_SRCSET_ATTRS:
                if img.get(attr):
                    candidates.extend(parse_srcset(img[attr]))
        if not candidates:
            for source in sources:
                media_type = (source.get("type") or "").lower()
                for attr in ("data-srcset", "srcset"):
                    if source.get(attr) and "avif" not in media_type:
                        candidates.extend(parse_srcset(source[attr]))
                if candidates:
                    break
        candidates = [c for c in candidates if not is_placeholder(c[0])]
        src = None
        if candidates:
            src = max(candidates, key=lambda c: c[1])[0]
        if src is None and img is not None:
            for attr in LAZY_SRC_ATTRS + ("src",):
                value = img.get(attr)
                if value and not is_placeholder(str(value)):
                    src = str(value).strip()
                    break
        if src is None and img is not None and img.get("src", "").startswith("data:") and len(img["src"]) >= 200:
            src = img["src"]
        if not src:
            return None, None, None
        if not src.startswith("data:"):
            src = urljoin(self.base, src)
        width = to_int(img.get("width")) if img is not None else None
        height = to_int(img.get("height")) if img is not None else None
        return src, width, height

    def image_blocks(self, el: Tag, role: str | None = None) -> list[dict]:
        src, width, height = self.image_source(el)
        if not src:
            return []
        img = el.find("img") if el.name == "picture" else el
        alt = collapse((img.get("alt") if img is not None else "") or "").strip()
        if role is None:
            cls = class_string(img) if img is not None else ""
            role = "logo" if re.search(r"logo", cls + " " + alt + " " + src.rsplit("/", 1)[-1], re.I) else "content"
            if role == "content" and width and height and width <= 32 and height <= 32:
                role = "icon"
        data = None
        original = src
        if src.startswith("data:"):
            data = decode_data_uri(src)
            original = f"data:sha256,{hashlib.sha256(data or b'').hexdigest()}"
        block = {"type": "image", "src": None, "originalSrc": original, "alt": alt, "width": width, "height": height, "role": role}
        title = img.get("title") if img is not None else None
        if title and not alt:
            block["alt"] = collapse(title).strip()
        self.images.append(ImageRef(block=block, url=src, role=role, data=data))
        return [block]

    def background_blocks(self, el: Tag) -> list[dict]:
        urls: list[str] = []
        for attr in BG_ATTRS:
            if el.get(attr):
                value = str(el[attr])
                urls.extend(m.group(2) for m in BG_URL_RE.finditer(value)) if "url(" in value else urls.append(value)
        style = el.get("style") or ""
        if "url(" in style and "background" in style.lower():
            urls.extend(m.group(2) for m in BG_URL_RE.finditer(style))
        blocks = []
        for url in dict.fromkeys(u.strip() for u in urls if u.strip()):
            if url.startswith("data:") and len(url) < 200:
                continue
            absolute = url if url.startswith("data:") else urljoin(self.base, url)
            data = decode_data_uri(absolute) if absolute.startswith("data:") else None
            original = f"data:sha256,{hashlib.sha256(data or b'').hexdigest()}" if data is not None else absolute
            block = {"type": "image", "src": None, "originalSrc": original, "alt": "", "width": None, "height": None, "role": "background"}
            self.images.append(ImageRef(block=block, url=absolute, role="background", data=data))
            blocks.append(block)
        return blocks

    def svg_is_content(self, el: Tag) -> bool:
        if el.get("role") == "img" or el.get("aria-label") or el.find("title"):
            width, height = to_int(el.get("width")), to_int(el.get("height"))
            return not (width and height and width < 24 and height < 24)
        return False

    def svg_blocks(self, el: Tag) -> list[dict]:
        if not self.svg_is_content(el):
            return []
        markup = str(el)
        if "xmlns=" not in markup.split(">", 1)[0]:
            markup = markup.replace("<svg", '<svg xmlns="http://www.w3.org/2000/svg"', 1)
        data = markup.encode("utf-8")
        title = el.find("title")
        alt = collapse(el.get("aria-label") or (title.get_text() if title else "")).strip()
        cls = class_string(el)
        role = "logo" if re.search(r"logo", cls + alt, re.I) else "content"
        block = {
            "type": "image",
            "src": None,
            "originalSrc": f"inline-svg:sha256,{hashlib.sha256(data).hexdigest()}",
            "alt": alt,
            "width": to_int(el.get("width")),
            "height": to_int(el.get("height")),
            "role": role,
        }
        self.images.append(ImageRef(block=block, url=block["originalSrc"], role=role, data=data))
        return [block]

    # ---------------------------------------------------------------- embeds
    def embed_block(self, el: Tag) -> dict | None:
        name = el.name
        src = el.get("src") or el.get("data-src") or el.get("data-lazy-src")
        if not src and name in ("video", "audio"):
            source = el.find("source", src=True)
            src = source["src"] if source else None
        if not src:
            return None
        url = urljoin(self.base, src)
        lowered = url.lower()
        if name in ("video", "audio"):
            provider = name
        elif "youtube.com" in lowered or "youtube-nocookie.com" in lowered or "youtu.be" in lowered:
            provider = "youtube"
        elif "vimeo.com" in lowered:
            provider = "vimeo"
        elif "google.com/maps" in lowered or "maps.google" in lowered or "openstreetmap.org" in lowered:
            provider = "map"
        else:
            provider = "iframe"
        poster = el.get("poster")
        return {
            "type": "embed",
            "provider": provider,
            "url": url,
            "title": collapse(el.get("title") or el.get("aria-label") or "").strip() or None,
            "poster": urljoin(self.base, poster) if poster else None,
            "width": to_int(el.get("width")),
            "height": to_int(el.get("height")),
        }

    # ----------------------------------------------------------------- forms
    def form_blocks(self, el: Tag) -> list[dict]:
        labels = {lbl.get("for"): collapse(lbl.get_text(" ")).strip() for lbl in el.find_all("label") if lbl.get("for")}
        fields = []
        for field_el in el.find_all(["input", "select", "textarea"]):
            input_type = (field_el.get("type") or "text").lower() if field_el.name == "input" else field_el.name
            if input_type in ("hidden", "submit", "button", "image", "reset"):
                continue
            label = labels.get(field_el.get("id"))
            if not label:
                parent_label = field_el.find_parent("label")
                label = collapse(parent_label.get_text(" ")).strip() if parent_label else None
            label = label or field_el.get("aria-label") or None
            entry = {
                "name": field_el.get("name") or field_el.get("id") or f"field-{len(fields) + 1}",
                "label": label,
                "inputType": input_type,
                "required": field_el.has_attr("required") or field_el.get("aria-required") == "true",
                "placeholder": field_el.get("placeholder") or None,
            }
            if field_el.name == "select":
                entry["options"] = [collapse(o.get_text()).strip() for o in field_el.find_all("option") if o.get_text(strip=True)]
            fields.append(entry)
        submit = el.find(["button"], attrs={"type": lambda t: t in (None, "submit")}) or el.find("input", attrs={"type": "submit"})
        submit_label = None
        if submit is not None:
            submit_label = collapse(submit.get_text(" ") if submit.name == "button" else submit.get("value") or "").strip() or None
        action = el.get("action")
        blocks: list[dict] = []
        # texts inside the form (headings, hints) are kept before the form block
        for child in el.find_all(list(HEADINGS) + ["p"]):
            if child.find_parent("label") is None:
                blocks.extend(self.block(child))
        if fields:
            blocks.append(
                {
                    "type": "form",
                    "action": urljoin(self.base, action) if action else None,
                    "method": (el.get("method") or "get").lower(),
                    "submitLabel": submit_label,
                    "fields": fields,
                }
            )
        return blocks

    # ----------------------------------------------------------------- cards
    CARD_TAGS = {"div", "li", "article", "a", "figure", "aside"}

    def card_grid_items(self, el: Tag) -> list[Tag] | None:
        """Return the children of `el` if they look like a grid of cards (features, services, teasers...)."""
        children = self.element_children(el)
        if el.name in ("ul", "ol"):
            if any(c.name != "li" for c in children):
                return None
        candidates = [c for c in children if c.name not in HEADINGS and c.name != "p"]
        if len(candidates) < 2 or any(c.name not in self.CARD_TAGS and "-" not in c.name for c in candidates):
            return None
        # intro headings/paragraphs are only allowed before the cards
        first_candidate = children.index(candidates[0])
        if any(c.name in HEADINGS or c.name == "p" for c in children[first_candidate:]):
            return None
        cardlike = 0
        for child in candidates:
            has_heading = child.find(list(HEADINGS)) is not None or (child.find(["strong", "b"]) is not None and child.find("p") is not None)
            has_media = child.find(["img", "picture", "svg"]) is not None or "url(" in str(child.get("style") or "")
            has_text = child.find("p") is not None
            has_link = child.name == "a" or child.find("a") is not None
            features = int(has_heading) + int(has_media) + int(has_text) + int(has_link)
            if has_heading and features >= 2 and len(child.get_text(" ", strip=True)) < 1500 and child.find(["section", "table", "form"]) is None:
                cardlike += 1
        if cardlike < max(2, 0.8 * len(candidates)):
            return None
        return children

    def cards_from(self, children: list[Tag], parent: Tag) -> list[dict]:
        blocks: list[dict] = []
        for child in children:
            if child.name in HEADINGS or child.name == "p":
                blocks.extend(self.block(child))
                continue
            if child.name == "a":
                blocks.extend(self.linked_blocks(child))
                continue
            inner = self.walk(child) if child.name != "li" else self.walk_nodes(list(child.children))
            if not inner:
                continue
            link = None
            if inner and len(inner) == 1 and inner[0]["type"] == "card":
                blocks.append(inner[0])
                continue
            blocks.append({"type": "card", "blocks": inner, "link": link})
        return blocks

    # -------------------------------------------------------------- fallback
    def fallback(self, el: Tag, reason: str) -> list[dict]:
        text = collapse(el.get_text(" ")).strip()
        if not text:
            return []
        self.unsupported.append(reason)
        html = sanitize_element(el, url_resolver=lambda u: urljoin(self.base, u))
        if not html.strip():
            html = f"<p>{escape(text)}</p>"
        return [{"type": "html", "html": html, "text": text, "reason": reason}]


def decode_data_uri(uri: str) -> bytes | None:
    try:
        header, payload = uri.split(",", 1)
    except ValueError:
        return None
    if ";base64" in header:
        try:
            return base64.b64decode(payload)
        except ValueError:
            return None
    from urllib.parse import unquote_to_bytes

    return unquote_to_bytes(payload)


def _contains(block: dict, target: dict) -> bool:
    if block is target:
        return True
    for value in block.values():
        if isinstance(value, dict) and _contains(value, target):
            return True
        if isinstance(value, list):
            for item in value:
                if isinstance(item, dict) and _contains(item, target):
                    return True
    return False
