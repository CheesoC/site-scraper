"""Markdown rendering of content blocks (content.md is a readable reference, not normative)."""

from __future__ import annotations

import posixpath

MARK_WRAP = {"bold": "**", "italic": "_", "strike": "~~", "code": "`"}


def _escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("*", "\\*").replace("_", "\\_").replace("[", "\\[").replace("]", "\\]")


class MarkdownRenderer:
    def __init__(self, page_dir: str):
        self.page_dir = page_dir  # archive-relative directory of the page, e.g. pages/leistungen

    def asset(self, src: str | None, fallback: str) -> str:
        if not src:
            return fallback
        return posixpath.relpath(src, self.page_dir)

    def inline(self, nodes: list[dict]) -> str:
        out = []
        for node in nodes:
            kind = node["type"]
            if kind == "text":
                text = node["text"]
                if "code" in node.get("marks", []):
                    out.append(f"`{text}`")
                    continue
                text = _escape(text)
                for mark in node.get("marks", []):
                    wrap = MARK_WRAP.get(mark)
                    if wrap and text.strip():
                        stripped = text.strip()
                        text = text.replace(stripped, f"{wrap}{stripped}{wrap}", 1)
                out.append(text)
            elif kind == "link":
                target = node.get("path") or node["href"]
                out.append(f"[{self.inline(node['children'])}]({target})")
            elif kind == "break":
                out.append("  \n")
        return "".join(out)

    def blocks(self, blocks: list[dict], indent: str = "") -> list[str]:
        lines: list[str] = []
        for block in blocks:
            lines.extend(indent + line if line else "" for line in self.block(block))
            lines.append("")
        return lines

    def block(self, block: dict) -> list[str]:
        kind = block["type"]
        if kind == "heading":
            return ["#" * block["level"] + " " + self.inline(block["content"])]
        if kind == "paragraph":
            return [self.inline(block["content"])]
        if kind == "list":
            lines = []
            for index, item in enumerate(block["items"], start=1):
                bullet = f"{index}." if block["ordered"] else "-"
                lines.append(f"{bullet} {self.inline(item['content'])}")
                for sub in item.get("blocks", []):
                    lines.extend("    " + line for line in self.block(sub) if line)
            return lines
        if kind == "table":
            rows = block.get("head", []) + block["rows"]
            if not rows:
                return []
            width = max(len(r) for r in rows)
            render = lambda row: "| " + " | ".join(self.inline(c["content"]).replace("|", "\\|") for c in row + [{"content": []}] * (width - len(row))) + " |"
            lines = [render(rows[0]), "|" + " --- |" * width]
            lines.extend(render(r) for r in rows[1:])
            if block.get("caption"):
                lines.append("")
                lines.append(f"_{self.inline(block['caption'])}_")
            return lines
        if kind == "quote":
            inner = [line for line in self.blocks(block["blocks"])]
            if block.get("cite"):
                inner.append(f"— {self.inline(block['cite'])}")
            return ["> " + line if line else ">" for line in inner]
        if kind == "image":
            src = self.asset(block.get("src"), block["originalSrc"])
            text = f"![{_escape(block['alt'])}]({src})"
            if block.get("link"):
                text = f"[{text}]({block['link'].get('path') or block['link']['href']})"
            lines = [text]
            if block.get("caption"):
                lines.append(f"_{self.inline(block['caption'])}_")
            return lines
        if kind == "gallery":
            return [line for image in block["images"] for line in self.block(image)]
        if kind == "button":
            return [f"[{_escape(block['label'])}]({block.get('path') or block['href']})"]
        if kind == "embed":
            return [f"[{block.get('title') or block['provider']}]({block['url']})"]
        if kind == "code":
            return [f"```{block.get('language') or ''}", block["text"].rstrip("\n"), "```"]
        if kind == "divider":
            return ["---"]
        if kind == "card":
            return [line for line in self.blocks(block["blocks"]) if line is not None]
        if kind == "accordion":
            lines = []
            for item in block["items"]:
                lines.append(f"**{self.inline(item['title'])}**")
                lines.append("")
                lines.extend(self.blocks(item["blocks"]))
            return lines
        if kind == "form":
            lines = ["_Formular:_"]
            for field in block["fields"]:
                required = " *" if field.get("required") else ""
                lines.append(f"- {field.get('label') or field['name']}{required} ({field['inputType']})")
            if block.get("submitLabel"):
                lines.append(f"- [{block['submitLabel']}]")
            return lines
        if kind == "html":
            return [block["html"]]
        return []

    def page(self, content: dict) -> str:
        lines: list[str] = []
        for section in content["sections"]:
            lines.append(f"<!-- section: {section['id']} ({section['type']}) -->")
            lines.extend(self.blocks(section["blocks"]))
        text = "\n".join(lines)
        while "\n\n\n" in text:
            text = text.replace("\n\n\n", "\n\n")
        return text.strip() + "\n"
