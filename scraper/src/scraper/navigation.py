"""NavigationExtractor: real navigation structures from the DOM (never "all links").

Per page the extractor finds menus in <header>, <nav>/[role=navigation] and <footer>, keeps the
hierarchy of nested lists (dropdowns, mega menus), the logo link, header CTAs and breadcrumbs.
NavigationAggregator consolidates the per-page results into the site-wide navigation.json.
"""

from __future__ import annotations

import copy
import json
import re
from collections import Counter
from dataclasses import dataclass, field
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag

from .content import BUTTON_CLASS_RE, ContentExtractor, ImageRef, class_string, collapse
from .urls import URLNormalizer

HEADINGS = ["h1", "h2", "h3", "h4", "h5", "h6"]
BREADCRUMB_RE = re.compile(r"breadcrumb|brotkrume|crumbs", re.I)
MAIN_HINT = re.compile(r"(^|[\s_-])(main|primary|haupt|hauptmen|global|site-nav|menu-main|main-menu|navbar)", re.I)
MOBILE_HINT = re.compile(r"mobile|offcanvas|off-canvas|drawer|burger|hamburger|slideout|mm-menu|sidenav-mobile", re.I)
UTILITY_HINT = re.compile(r"(^|[\s_-])(top|meta|utility|service|lang|language|sprache|social|account|topbar|top-bar)([\s_-]|$)", re.I)
FOOTER_HINT = re.compile(r"footer", re.I)
DROPDOWN_HINT = re.compile(r"dropdown|submenu|sub-menu|mega|flyout|subnav", re.I)
LOGO_HINT = re.compile(r"logo|brand|wordmark", re.I)
SKIP_HINT = re.compile(r"cookie|consent|gdpr|skip-link|sr-only|visually-hidden", re.I)


@dataclass
class PageNavigation:
    menus: list[dict] = field(default_factory=list)
    logo: dict | None = None
    logo_image: ImageRef | None = None
    cta: list[dict] = field(default_factory=list)
    breadcrumbs: list[dict] = field(default_factory=list)


class NavigationExtractor:
    def __init__(self, normalizer: URLNormalizer):
        self.normalizer = normalizer
        self.helper = ContentExtractor(normalizer)

    # ---------------------------------------------------------------- public
    def extract(self, html: str, page_url: str) -> PageNavigation:
        soup = BeautifulSoup(html, "lxml")
        for tag in soup(["script", "style", "noscript", "template"]):
            tag.decompose()
        for tag in list(soup.find_all(True)):
            if not tag.decomposed and SKIP_HINT.search(class_string(tag)):
                tag.decompose()
        base_tag = soup.find("base", href=True)
        self.base = urljoin(page_url, base_tag["href"]) if base_tag else page_url
        self.page_url = page_url
        self.helper.base = self.base
        self.helper.page_url = page_url
        self.helper.images = []
        self.helper.links = []
        self.helper.unsupported = []

        result = PageNavigation()
        body = soup.body or soup
        result.breadcrumbs = self.extract_breadcrumbs(soup)
        header = self.find_page_header(body)
        footer = self.find_page_footer(body)

        nav_elements = [
            el for el in body.select("nav, [role=navigation]")
            if not BREADCRUMB_RE.search(class_string(el) + " " + str(el.get("aria-label") or ""))
            and not (footer is not None and (el is footer or footer in el.parents))
        ]
        # outermost navigation elements only
        nav_elements = [el for el in nav_elements if not any(other in el.parents for other in nav_elements)]

        if header is not None and not any(header in el.parents for el in nav_elements):
            items, ambiguous = self.parse_menu(header, exclude_logo=True)
            if len([i for i in self.flatten(items)]) >= 2:
                result.menus.append(self.menu("main", items, ambiguous, header, label=None))

        for el in nav_elements:
            items, ambiguous = self.parse_menu(el)
            if not items:
                continue
            menu_type = self.classify_nav(el, header)
            label = collapse(str(el.get("aria-label") or "")).strip() or None
            result.menus.append(self.menu(menu_type, items, ambiguous, el, label=label))

        self.pick_main(result.menus)

        if footer is not None:
            items = self.parse_footer(footer)
            if items:
                result.menus.append(self.menu("footer", items, False, footer, label=None))

        result.logo, result.logo_image = self.extract_logo(header or body)
        result.cta = self.extract_cta(header, result.logo)
        return result

    # ------------------------------------------------------------- landmarks
    @staticmethod
    def find_page_header(body: Tag) -> Tag | None:
        for el in body.select("header, [role=banner]"):
            if el.find_parent(["article", "section", "main", "footer"]) is None:
                return el
        return None

    @staticmethod
    def find_page_footer(body: Tag) -> Tag | None:
        candidates = [el for el in body.select("footer, [role=contentinfo]") if el.find_parent(["article", "section", "main", "header"]) is None]
        return candidates[-1] if candidates else None

    def classify_nav(self, el: Tag, header: Tag | None) -> str:
        hints = class_string(el) + " " + str(el.get("aria-label") or "")
        for parent in list(el.parents)[:3]:
            if isinstance(parent, Tag):
                hints += " " + class_string(parent)
        if MOBILE_HINT.search(hints):
            return "mobile"
        if FOOTER_HINT.search(hints):
            return "footer"
        if UTILITY_HINT.search(hints):
            return "utility"
        if MAIN_HINT.search(hints):
            return "main"
        if header is not None and header in el.parents:
            return "main"
        return "secondary"

    def pick_main(self, menus: list[dict]) -> None:
        """Exactly one main menu per page: prefer an explicit hint, then the biggest header menu."""
        mains = [m for m in menus if m["type"] == "main"]
        if not mains:
            candidates = [m for m in menus if m["type"] == "secondary" and len(self.flatten(m["items"])) >= 2]
            if candidates:
                candidates[0]["type"] = "main"
            return
        if len(mains) == 1:
            return
        explicit = [m for m in mains if m.get("_explicit")]
        chosen = explicit[0] if explicit else max(mains, key=lambda m: len(self.flatten(m["items"])))
        for menu in mains:
            if menu is not chosen:
                menu["type"] = "secondary"

    def menu(self, menu_type: str, items: list[dict], ambiguous: bool, el: Tag, label: str | None) -> dict:
        menu = {
            "type": menu_type,
            "label": label,
            "selector": self.selector(el),
            "ambiguous": ambiguous,
            "items": items,
        }
        if MAIN_HINT.search(class_string(el) + " " + str(el.get("aria-label") or "")):
            menu["_explicit"] = True
        return menu

    @staticmethod
    def selector(el: Tag) -> str:
        parts = []
        node = el
        while isinstance(node, Tag) and node.name not in ("body", "html", "[document]") and len(parts) < 4:
            part = node.name
            if node.get("id"):
                part += f"#{node['id']}"
            elif node.get("class"):
                classes = node["class"] if isinstance(node["class"], list) else str(node["class"]).split()
                part += "".join(f".{c}" for c in classes[:2])
            parts.append(part)
            node = node.parent
        return " > ".join(reversed(parts))

    # ----------------------------------------------------------------- menus
    def parse_menu(self, el: Tag, exclude_logo: bool = False) -> tuple[list[dict], bool]:
        lists = self.top_lists(el)
        if lists:
            items: list[dict] = []
            for lst in lists:
                if exclude_logo and LOGO_HINT.search(class_string(lst)):
                    continue
                items.extend(self.parse_list(lst))
            return self.finalize(items), False
        anchors = [a for a in el.find_all("a", href=True)]
        items = []
        for a in anchors:
            if exclude_logo and self.is_logo_anchor(a):
                continue
            item = self.item_from_anchor(a)
            if item:
                items.append(item)
        ambiguous = el.find(class_=DROPDOWN_HINT) is not None
        return self.finalize(items), ambiguous

    @staticmethod
    def top_lists(el: Tag) -> list[Tag]:
        lists = el.find_all(["ul", "ol"])
        return [lst for lst in lists if not any(p in lists for p in lst.parents)]

    def parse_list(self, lst: Tag) -> list[dict]:
        items = []
        for li in lst.find_all("li", recursive=False):
            nested = [sub for sub in li.find_all(["ul", "ol"]) if sub.find_parent("li") is li]
            anchor = next((a for a in li.find_all("a", href=True) if not any(n in a.parents for n in nested)), None)
            if anchor is not None:
                item = self.item_from_anchor(anchor)
            else:
                label = self.own_text(li, nested)
                item = self.make_item(label, None) if label else None
            children: list[dict] = []
            for sub in nested:
                sub_items = self.parse_list(sub)
                group_label = self.group_label(sub, stop=li)
                if group_label and len(nested) > 1:
                    group = self.make_item(group_label, None)
                    group["children"] = sub_items
                    children.append(group)
                else:
                    children.extend(sub_items)
            if item is None:
                if not children:
                    continue
                item = self.make_item("", None)
            item["children"] = children
            items.append(item)
        return items

    def own_text(self, li: Tag, nested: list[Tag]) -> str:
        """Label of a list item without link: its first own text (not the text of nested menus)."""
        for child in li.children:
            if isinstance(child, Tag):
                if any(n is child or child in n.parents or n in child.parents for n in nested):
                    continue
                text = collapse(child.get_text(" ")).strip()
            else:
                text = collapse(str(child)).strip()
            if text:
                return text
        return ""

    def group_label(self, lst: Tag, stop: Tag | None = None) -> str | None:
        """Heading-like text directly before a list (mega menu columns, footer columns)."""
        node = lst
        for _ in range(3):
            prev = node.find_previous_sibling(True)
            while prev is not None and prev.name in ("ul", "ol"):
                prev = None
            if prev is not None:
                if prev.name in HEADINGS or prev.name in ("strong", "b", "p", "span", "div", "button", "summary"):
                    if prev.find("a") is None and prev.find(["ul", "ol"]) is None:
                        text = collapse(prev.get_text(" ")).strip()
                        if 0 < len(text) <= 60:
                            return text
                return None
            node = node.parent
            if node is None or node is stop or node.name in ("footer", "nav", "header", "body"):
                return None
        return None

    def label_for(self, a: Tag) -> str:
        label = collapse(a.get_text(" ")).strip()
        if not label:
            label = collapse(str(a.get("aria-label") or a.get("title") or "")).strip()
        if not label:
            img = a.find("img")
            if img is not None:
                label = collapse(str(img.get("alt") or "")).strip()
        if not label:
            svg_title = a.find("title")
            if svg_title is not None:
                label = collapse(svg_title.get_text()).strip()
        return label

    def item_from_anchor(self, a: Tag) -> dict | None:
        label = self.label_for(a)
        href = a.get("href")
        if not label:
            return None
        return self.make_item(label, href)

    def make_item(self, label: str, href: str | None) -> dict:
        url, path, external = None, None, False
        href_value = str(href or "").strip()
        if href_value and href_value != "#":
            info = self.normalizer.classify(href_value, self.base)
            if info is not None:
                url = info.href
                external = not info.internal
                if info.internal and info.url:
                    path = self.normalizer.to_path(info.url) + (f"#{info.fragment}" if info.fragment else "")
        return {"label": label, "url": url, "path": path, "external": external, "order": 0, "depth": 0, "children": []}

    def finalize(self, items: list[dict], depth: int = 0, menu_type: str | None = None) -> list[dict]:
        for order, item in enumerate(items):
            item["order"] = order
            item["depth"] = depth
            if menu_type:
                item["type"] = menu_type
            self.finalize(item["children"], depth + 1, menu_type)
        return items

    @staticmethod
    def flatten(items: list[dict]) -> list[dict]:
        out = []
        for item in items:
            out.append(item)
            out.extend(NavigationExtractor.flatten(item["children"]))
        return out

    # ---------------------------------------------------------------- footer
    def parse_footer(self, footer: Tag) -> list[dict]:
        items: list[dict] = []
        lists = self.top_lists(footer)
        if lists:
            for lst in lists:
                sub_items = self.parse_list(lst)
                if not sub_items:
                    continue
                label = self.group_label(lst)
                if label:
                    group = self.make_item(label, None)
                    group["children"] = sub_items
                    items.append(group)
                else:
                    items.extend(sub_items)
            for a in footer.find_all("a", href=True):
                if a.find_parent(["ul", "ol"]) is None:
                    item = self.item_from_anchor(a)
                    if item:
                        items.append(item)
            return self.finalize(items)
        # no lists: group anchors by the closest preceding heading
        current_group: dict | None = None
        for el in footer.find_all(HEADINGS + ["a"]):
            if el.name in HEADINGS:
                if el.find("a") is not None:
                    continue
                text = collapse(el.get_text(" ")).strip()
                if text:
                    current_group = self.make_item(text, None)
                    items.append(current_group)
                continue
            item = self.item_from_anchor(el)
            if not item:
                continue
            if current_group is not None:
                current_group["children"].append(item)
            else:
                items.append(item)
        items = [i for i in items if i["url"] or i["children"]]
        return self.finalize(items)

    # ------------------------------------------------------------ logo / cta
    def is_logo_anchor(self, a: Tag) -> bool:
        hints = class_string(a) + " " + " ".join(class_string(c) + " " + str(c.get("alt") or "") + " " + str(c.get("src") or "") for c in a.find_all(["img", "svg"]))
        if LOGO_HINT.search(hints):
            return True
        if a.find(["img", "svg"]) is not None:
            info = self.normalizer.classify(str(a.get("href") or ""), self.base)
            if info and info.internal and info.url and self.normalizer.to_path(info.url) == "/":
                return True
        return False

    def extract_logo(self, scope: Tag) -> tuple[dict | None, ImageRef | None]:
        anchor = next((a for a in scope.find_all("a", href=True) if self.is_logo_anchor(a)), None)
        if anchor is None:
            return None, None
        info = self.normalizer.classify(str(anchor["href"]), self.base)
        if info is None:
            return None, None
        logo = {
            "href": info.href,
            "path": self.normalizer.to_path(info.url) if info.internal and info.url else None,
            "external": not info.internal,
            "label": self.label_for(anchor) or None,
            "image": None,
            "imageUrl": None,
            "alt": None,
        }
        image_ref = None
        before = len(self.helper.images)
        img = anchor.find(["picture", "img"])
        if img is not None:
            self.helper.image_blocks(img, role="logo")
        else:
            svg = anchor.find("svg")
            if svg is not None:
                svg = copy.copy(svg)
                if not self.helper.svg_is_content(svg):
                    svg["role"] = "img"
                self.helper.svg_blocks(svg)
        if len(self.helper.images) > before:
            image_ref = self.helper.images[-1]
            image_ref.role = "logo"
            image_ref.block["role"] = "logo"
            logo["imageUrl"] = image_ref.block["originalSrc"]
            logo["alt"] = image_ref.block["alt"] or logo["label"]
        return logo, image_ref

    def extract_cta(self, header: Tag | None, logo: dict | None) -> list[dict]:
        if header is None:
            return []
        items = []
        for a in header.find_all("a", href=True):
            if BUTTON_CLASS_RE.search(class_string(a)) and not self.is_logo_anchor(a):
                item = self.item_from_anchor(a)
                if item:
                    items.append(item)
        return self.finalize(items, menu_type="cta")

    # ----------------------------------------------------------- breadcrumbs
    def extract_breadcrumbs(self, soup: BeautifulSoup) -> list[dict]:
        candidates = [
            el for el in soup.find_all(True)
            if (BREADCRUMB_RE.search(class_string(el) + " " + str(el.get("aria-label") or "")) or "BreadcrumbList" in str(el.get("itemtype") or ""))
            and el.name in ("nav", "ol", "ul", "div", "p", "section")
        ]
        candidates = [el for el in candidates if not any(other in el.parents for other in candidates)]
        if candidates:
            el = candidates[0]
            items = []
            for a in el.find_all("a", href=True):
                item = self.item_from_anchor(a)
                if item:
                    items.append(item)
            # trailing current page (plain text after the last link)
            last_text = None
            lis = el.find_all("li")
            if lis and lis[-1].find("a") is None:
                last_text = collapse(lis[-1].get_text(" ")).strip()
            elif not lis:
                tail = el.find_all(string=True)
                if tail:
                    last_anchor = el.find_all("a")[-1] if el.find_all("a") else None
                    texts = [str(t) for t in tail if last_anchor is None or last_anchor not in t.parents]
                    after = collapse(" ".join(texts[-1:])).strip(" ›>/»|- ")
                    last_text = after or None
            if last_text and (not items or items[-1]["label"] != last_text):
                items.append(self.make_item(last_text, self.page_url))
            return self.finalize(items, menu_type="breadcrumb")
        return []  # JSON-LD breadcrumbs: see extract_jsonld_breadcrumbs()

    def extract_jsonld_breadcrumbs(self, structured: list) -> list[dict]:
        for entry in structured:
            graph = entry.get("@graph", [entry]) if isinstance(entry, dict) else []
            for node in graph:
                if isinstance(node, dict) and node.get("@type") == "BreadcrumbList":
                    elements = sorted(node.get("itemListElement", []), key=lambda e: e.get("position", 0) if isinstance(e, dict) else 0)
                    items = []
                    for element in elements:
                        if not isinstance(element, dict):
                            continue
                        target = element.get("item")
                        href = target.get("@id") if isinstance(target, dict) else target
                        name = element.get("name") or (target.get("name") if isinstance(target, dict) else None)
                        if name:
                            items.append(self.make_item(collapse(str(name)).strip(), href))
                    return self.finalize(items, menu_type="breadcrumb")
        return []


def _signature(items: list[dict]) -> str:
    def simplify(entries):
        return [[i["label"], i["path"] or i["url"], simplify(i["children"])] for i in entries]

    return json.dumps(simplify(items), ensure_ascii=False)


class NavigationAggregator:
    """Collects per-page navigation and builds the site-wide navigation.json."""

    def __init__(self):
        self.menus: dict[tuple[str, str], dict] = {}
        self.counts: Counter = Counter()
        self.logos: Counter = Counter()
        self.logo_data: dict[str, tuple[dict, ImageRef | None]] = {}
        self.ctas: Counter = Counter()
        self.cta_data: dict[str, list[dict]] = {}
        self.order: list[tuple[str, str]] = []

    def add(self, nav: PageNavigation) -> None:
        for menu in nav.menus:
            key = (menu["type"], _signature(menu["items"]))
            if key not in self.menus:
                self.menus[key] = menu
                self.order.append(key)
            self.counts[key] += 1
        if nav.logo:
            key = json.dumps([nav.logo["href"], nav.logo["imageUrl"]])
            self.logos[key] += 1
            self.logo_data.setdefault(key, (nav.logo, nav.logo_image))
        if nav.cta:
            key = _signature(nav.cta)
            self.ctas[key] += 1
            self.cta_data.setdefault(key, nav.cta)

    def best(self, menu_type: str) -> dict | None:
        keys = [k for k in self.order if k[0] == menu_type]
        if not keys:
            return None
        return self.menus[max(keys, key=lambda k: (self.counts[k], -self.order.index(k)))]

    def build(self) -> tuple[dict, ImageRef | None]:
        main = self.best("main")
        footer = self.best("footer")
        desktop_entries = {
            (i["label"], i["path"] or i["url"])
            for key, menu in self.menus.items()
            if key[0] != "mobile"
            for i in NavigationExtractor.flatten(menu["items"])
        }
        menus = []
        for key in self.order:
            menu = self.menus[key]
            if menu["type"] == "mobile":
                entries = {(i["label"], i["path"] or i["url"]) for i in NavigationExtractor.flatten(menu["items"])}
                if entries <= desktop_entries:
                    continue  # mobile menu without additional entries
            if menu["type"] in ("main", "footer") and menu is not (main if menu["type"] == "main" else footer):
                menu = {**menu, "type": "secondary"}
            menus.append((key, menu))
        out_menus = []
        for index, (key, menu) in enumerate(menus, start=1):
            entry = {
                "id": f"menu-{index}",
                "type": menu["type"],
                "label": menu.get("label"),
                "selector": menu.get("selector"),
                "ambiguous": bool(menu.get("ambiguous")),
                "pages": self.counts[key],
                "items": self._typed(menu["items"], menu["type"]),
            }
            out_menus.append(entry)
        logo, logo_image = (None, None)
        if self.logos:
            logo, logo_image = self.logo_data[self.logos.most_common(1)[0][0]]
        cta = self.cta_data[self.ctas.most_common(1)[0][0]] if self.ctas else []
        navigation = {
            "schemaVersion": "1.0",
            "main": self._typed(main["items"], "main") if main else [],
            "footer": self._typed(footer["items"], "footer") if footer else [],
            "logo": logo,
            "cta": self._typed(cta, "cta"),
            "menus": out_menus,
        }
        return navigation, logo_image

    def _typed(self, items: list[dict], menu_type: str) -> list[dict]:
        out = []
        for item in items:
            copy_item = {k: v for k, v in item.items() if k != "children"}
            copy_item["type"] = menu_type
            copy_item["children"] = self._typed(item["children"], menu_type)
            out.append(copy_item)
        return out
