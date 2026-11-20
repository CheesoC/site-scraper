"""ContentExporter: writes the standardized Content Archive (Schema v1.0)."""

from __future__ import annotations

import asyncio
import json
import logging
import shutil
from dataclasses import dataclass, field
from pathlib import Path

import httpx

from . import SCHEMA_VERSION, __version__
from .assets import AssetDownloader, AssetRecord
from .config import CrawlConfig
from .content import ImageRef, plain_text
from .crawler import CrawlState
from .markdown import MarkdownRenderer
from .navigation import NavigationAggregator
from .urls import DirAllocator, URLNormalizer, is_private_host

log = logging.getLogger(__name__)

MANAGED_ENTRIES = ("manifest.json", "navigation.json", "sitemap.json", "pages", "assets", "reports")


@dataclass
class ExportResult:
    output: Path
    pages: int = 0
    assets: int = 0
    asset_failures: list[dict] = field(default_factory=list)  # {url, error, page}
    unresolved_links: list[dict] = field(default_factory=list)  # {page, url, path, reason}
    nav_without_page: list[dict] = field(default_factory=list)  # {label, url, path}
    unsupported_blocks: int = 0
    empty_pages: list[str] = field(default_factory=list)


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


class ContentExporter:
    def __init__(self, config: CrawlConfig, normalizer: URLNormalizer, state: CrawlState):
        self.config = config
        self.normalizer = normalizer
        self.state = state
        self.output = Path(config.output)
        self.result = ExportResult(output=self.output)
        self.failed_by_path = {}
        for item in state.failed:
            self.failed_by_path[self.normalizer.to_path(item["url"])] = item
        self.skipped_by_path = {self.normalizer.to_path(item["url"]): item for item in state.skipped}

    # ------------------------------------------------------------------ run
    async def export(self) -> ExportResult:
        self.prepare_output()
        pages = self.ordered_pages()
        allocator = DirAllocator()
        dirs = {page.path: allocator.allocate(page.path) for page in pages}

        aggregator = NavigationAggregator()
        for page in pages:
            aggregator.add(page.navigation)
        navigation, logo_image = aggregator.build()

        records = await self.download_assets(pages, logo_image)

        # navigation.json
        for menu in [navigation["main"], navigation["footer"], navigation["cta"]] + [m["items"] for m in navigation["menus"]]:
            self.resolve_nav(menu, report=menu is navigation["main"] or menu is navigation["footer"])
        if navigation["logo"]:
            logo = navigation["logo"]
            logo["path"] = self.resolve_href(logo["href"], logo["href"])[0] if not logo["external"] else None
            if logo_image is not None:
                record = records.get(id(logo_image))
                logo["image"] = record.file if record else None
        write_json(self.output / "navigation.json", navigation)

        registry: dict[str, AssetRecord] = {}
        manifest_pages = []
        renderer_cache = {}
        for page in pages:
            directory = dirs[page.path]
            extraction = page.extraction
            # assets -> blocks
            page_images = []
            for order, ref in enumerate(extraction.images):
                record = records.get(id(ref))
                if record is not None:
                    ref.block["src"] = record.file
                    if page.path not in record.pages:
                        record.pages.append(page.path)
                    registry[record.sha256] = record
                caption = ref.block.get("caption")
                page_images.append(
                    {
                        "originalUrl": ref.block["originalSrc"],
                        "src": ref.block["src"],
                        "assetId": record.id if record else None,
                        "alt": ref.block["alt"],
                        "caption": plain_text(caption) if caption else None,
                        "sectionId": ref.section_id,
                        "blockIndex": ref.block_index,
                        "order": order,
                        "role": ref.role if ref.role in ("content", "background", "logo", "icon") else "content",
                    }
                )
            meta = extraction.meta
            og_ref = getattr(page, "_og_ref", None)
            if og_ref is not None:
                record = records.get(id(og_ref))
                if record is not None:
                    meta["og"]["image"] = record.file
                    registry[record.sha256] = record
                    if page.path not in record.pages:
                        record.pages.append(page.path)
            # links
            self.resolve_blocks(extraction.sections, page)
            breadcrumbs = [dict(item) for item in page.navigation.breadcrumbs]
            self.resolve_nav(breadcrumbs, report=False)
            content = {
                "schemaVersion": SCHEMA_VERSION,
                "path": page.path,
                "url": page.final_url,
                "title": extraction.title or page.path,
                "meta": meta,
                "sections": extraction.sections,
            }
            if breadcrumbs:
                content["breadcrumbs"] = breadcrumbs
            if not extraction.sections:
                self.result.empty_pages.append(page.path)
            self.result.unsupported_blocks += sum(1 for block in extraction.iter_blocks() if block["type"] == "html")

            base = self.output / directory
            write_json(base / "content.json", content)
            renderer = renderer_cache.setdefault(directory, MarkdownRenderer(directory))
            (base / "content.md").write_text(renderer.page(content), encoding="utf-8")
            html_rel = None
            if self.config.keep_html:
                html_rel = f"{directory}/original.html"
                (base / "original.html").write_text(page.html, encoding="utf-8")
            write_json(base / "images.json", {"schemaVersion": SCHEMA_VERSION, "kind": "page", "path": page.path, "images": page_images})
            manifest_pages.append(
                {
                    "path": page.path,
                    "title": content["title"],
                    "originalUrl": page.url,
                    "finalUrl": page.final_url,
                    "normalizedUrl": page.final_url,
                    "canonical": meta.get("canonical"),
                    "aliases": sorted(page.aliases),
                    "dir": directory,
                    "content": f"{directory}/content.json",
                    "markdown": f"{directory}/content.md",
                    "html": html_rel,
                    "images": f"{directory}/images.json",
                    "depth": page.depth,
                    "status": page.status,
                }
            )

        if logo_image is not None and records.get(id(logo_image)):
            record = records[id(logo_image)]
            registry[record.sha256] = record
            for page in pages:
                if page.path not in record.pages:
                    record.pages.append(page.path)
        write_json(
            self.output / "assets" / "images.json",
            {"schemaVersion": SCHEMA_VERSION, "kind": "registry", "assets": [r.to_json() for r in registry.values()]},
        )
        self.result.assets = len(registry)
        write_json(self.output / "sitemap.json", self.sitemap(pages))
        home = self.state.pages.get("/") or (pages[0] if pages else None)
        write_json(
            self.output / "manifest.json",
            {
                "schemaVersion": SCHEMA_VERSION,
                "sourceUrl": self.normalizer.start_url,
                "crawledAt": self.state.started_at or None,
                "producer": {"name": "site-scraper", "version": __version__},
                "site": {
                    "name": (navigation["logo"] or {}).get("label") or (home.extraction.meta.get("og", {}).get("title") if home else None) or (home.extraction.title if home else None),
                    "lang": home.extraction.meta.get("lang") if home else None,
                    "homePath": "/" if "/" in self.state.pages else (pages[0].path if pages else "/"),
                },
                "files": {
                    "navigation": "navigation.json",
                    "sitemap": "sitemap.json",
                    "assets": "assets/images.json",
                    "report": "reports/crawl-report.json",
                },
                "pages": manifest_pages,
            },
        )
        self.result.pages = len(pages)
        return self.result

    def prepare_output(self) -> None:
        self.output.mkdir(parents=True, exist_ok=True)
        for name in MANAGED_ENTRIES:
            target = self.output / name
            if target.is_dir():
                shutil.rmtree(target)
            elif target.exists():
                target.unlink()

    def ordered_pages(self):
        pages = list(self.state.pages.values())
        pages.sort(key=lambda p: (p.path != "/",))  # home first, otherwise crawl order
        return pages

    # --------------------------------------------------------------- assets
    async def download_assets(self, pages, logo_image: ImageRef | None) -> dict[int, AssetRecord]:
        """Download all referenced images. Returns id(ImageRef) -> AssetRecord."""
        records: dict[int, AssetRecord] = {}
        if not self.config.download_images:
            return records
        refs: list[tuple[ImageRef, str]] = []
        for page in pages:
            refs.extend((ref, page.path) for ref in page.extraction.images)
            og_url = page.extraction.meta.get("og", {}).get("imageUrl")
            if og_url:
                og_ref = ImageRef(block={"originalSrc": og_url}, url=og_url, role="og")
                page._og_ref = og_ref
                refs.append((og_ref, page.path))
        if logo_image is not None:
            refs.append((logo_image, "/"))
        allow_private = is_private_host(self.normalizer.host)
        headers = {"User-Agent": self.config.user_agent}
        async with httpx.AsyncClient(headers=headers, timeout=self.config.timeout, follow_redirects=True) as client:
            downloader = AssetDownloader(self.output, client, self.config.max_asset_bytes, allow_private, concurrency=max(2, self.config.concurrency * 2))
            results = await asyncio.gather(*(downloader.get(ref.url, ref.data) for ref, _ in refs))
        for (ref, page_path), record in zip(refs, results):
            if record is not None:
                records[id(ref)] = record
            else:
                self.result.asset_failures.append({"url": ref.block.get("originalSrc", ref.url), "error": downloader.failures.get(ref.url), "page": page_path})
        # one entry per failing URL and page
        seen = set()
        unique = []
        for item in self.result.asset_failures:
            key = (item["url"], item["page"])
            if key not in seen:
                seen.add(key)
                unique.append(item)
        self.result.asset_failures = unique
        return records

    # ---------------------------------------------------------------- links
    def resolve_href(self, href: str, base: str) -> tuple[str | None, bool, str | None, bool]:
        """Return (local path or None, external, normalized url, is_page)."""
        info = self.normalizer.classify(href, base)
        if info is None or info.url is None:
            return None, info is not None, None, False  # mailto:, tel: ... are external
        if not info.internal:
            return None, True, info.url, False
        target = self.normalizer.to_path(info.url)
        target = self.state.aliases.get(target, target)
        if target in self.state.pages:
            return target + (f"#{info.fragment}" if info.fragment else ""), False, info.url, info.is_page
        return None, False, info.url, info.is_page

    def resolve_target(self, node: dict, href_key: str, page) -> None:
        href = node.get(href_key)
        if not href:
            node["path"] = None
            return
        path, external, url, is_page = self.resolve_href(href, page.final_url if page else self.normalizer.start_url)
        node["path"] = path
        node["external"] = external
        if path is None and not external and url and is_page and page is not None:
            self.result.unresolved_links.append({"page": page.path, "url": url, "path": self.normalizer.to_path(url), "reason": self.why_missing(url)})

    def why_missing(self, url: str) -> str:
        path = self.normalizer.to_path(url)
        if path in self.failed_by_path:
            item = self.failed_by_path[path]
            return item.get("error") or f"HTTP {item.get('status')}"
        if path in self.skipped_by_path:
            return f"not crawled ({self.skipped_by_path[path]['reason']})"
        return "not crawled"

    def resolve_blocks(self, value, page) -> None:
        if isinstance(value, dict):
            if "href" in value and "external" in value and "path" in value:
                self.resolve_target(value, "href", page)
            for child in value.values():
                if isinstance(child, (dict, list)):
                    self.resolve_blocks(child, page)
        elif isinstance(value, list):
            for child in value:
                self.resolve_blocks(child, page)

    def resolve_nav(self, items: list[dict], report: bool) -> None:
        for item in items:
            if item.get("url"):
                path, external, url, is_page = self.resolve_href(item["url"], self.normalizer.start_url)
                item["path"] = path
                item["external"] = external
                if report and path is None and not external and is_page:
                    self.result.nav_without_page.append({"label": item["label"], "url": item["url"], "path": self.normalizer.to_path(url) if url else None})
            else:
                item["path"] = None
            self.resolve_nav(item["children"], report)

    # -------------------------------------------------------------- sitemap
    def sitemap(self, pages) -> dict:
        titles = {page.path: page.extraction.title or None for page in pages}
        tree = {"path": "/", "segment": "", "title": titles.get("/"), "exported": "/" in titles, "children": []}
        for path in titles:
            if path == "/":
                continue
            node = tree
            parts = path.strip("/").split("/")
            for i, segment in enumerate(parts):
                sub = "/" + "/".join(parts[: i + 1])
                child = next((c for c in node["children"] if c["path"] == sub), None)
                if child is None:
                    child = {"path": sub, "segment": segment, "title": titles.get(sub), "exported": sub in titles, "children": []}
                    node["children"].append(child)
                node = child
        links = {}
        for page in pages:
            targets = []
            for path in page.out_links:
                path = self.state.aliases.get(path, path)
                if path in self.state.pages and path != page.path and path not in targets:
                    targets.append(path)
            links[page.path] = targets
        return {"schemaVersion": SCHEMA_VERSION, "tree": tree, "links": links}
