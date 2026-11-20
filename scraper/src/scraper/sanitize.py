"""Allowlist HTML sanitizer for fallback blocks (no scripts, styles or event handlers)."""

from __future__ import annotations

import copy
import re

from bs4 import BeautifulSoup, Comment, Tag

ALLOWED_TAGS = {
    "a", "abbr", "article", "aside", "b", "blockquote", "br", "caption", "cite", "code", "col", "colgroup",
    "dd", "del", "details", "dfn", "div", "dl", "dt", "em", "figcaption", "figure", "footer", "h1", "h2",
    "h3", "h4", "h5", "h6", "header", "hr", "i", "img", "ins", "kbd", "li", "mark", "ol", "p", "pre", "q",
    "s", "samp", "section", "small", "span", "strong", "sub", "summary", "sup", "table", "tbody", "td",
    "tfoot", "th", "thead", "time", "tr", "u", "ul",
}
DROP_WITH_CONTENT = {
    "script", "style", "noscript", "template", "iframe", "object", "embed", "applet", "frame", "frameset",
    "link", "meta", "base", "form", "input", "button", "select", "textarea", "option", "svg", "math",
    "canvas", "audio", "video", "source", "track", "head", "title",
}
ALLOWED_ATTRS = {
    "a": {"href", "title"},
    "img": {"src", "alt", "width", "height", "title"},
    "td": {"colspan", "rowspan"},
    "th": {"colspan", "rowspan", "scope"},
    "abbr": {"title"},
    "time": {"datetime"},
    "ol": {"start", "reversed"},
    "details": {"open"},
}
SAFE_URL = re.compile(r"^(?:https?:|mailto:|tel:|/|#|\.|[^:]*$)", re.IGNORECASE)


def sanitize_element(element: Tag, url_resolver=None) -> str:
    """Return a sanitized HTML string for a copy of `element`."""
    fragment = copy.copy(element)
    wrapper = BeautifulSoup("<div></div>", "lxml").div
    wrapper.append(fragment)
    _clean(wrapper, url_resolver)
    return "".join(str(child) for child in wrapper.contents).strip()


def sanitize_html(html: str, url_resolver=None) -> str:
    soup = BeautifulSoup(f"<div>{html}</div>", "lxml")
    wrapper = soup.div
    _clean(wrapper, url_resolver)
    return "".join(str(child) for child in wrapper.contents).strip()


def _clean(root: Tag, url_resolver) -> None:
    for comment in root.find_all(string=lambda s: isinstance(s, Comment)):
        comment.extract()
    for tag in list(root.find_all(True)):
        if tag.decomposed:
            continue  # already removed with an ancestor
        name = tag.name.lower()
        if name in DROP_WITH_CONTENT:
            tag.decompose()
            continue
        if name not in ALLOWED_TAGS:
            tag.unwrap()
            continue
        allowed = ALLOWED_ATTRS.get(name, set())
        for attr in list(tag.attrs):
            if attr.lower() not in allowed:
                del tag.attrs[attr]
        for attr in ("href", "src"):
            value = tag.get(attr)
            if value is None:
                continue
            value = str(value).strip()
            if not SAFE_URL.match(value) or value.lower().startswith(("javascript:", "data:", "vbscript:")):
                del tag.attrs[attr]
            elif url_resolver:
                tag[attr] = url_resolver(value)
