"""CrawlValidator: completeness reports and schema validation of an archive."""

from __future__ import annotations

import json
import os
from pathlib import Path

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from . import SCHEMA_VERSION
from .config import CrawlConfig
from .crawler import CrawlState
from .exporter import ExportResult, write_json

SCHEMA_FILES = {
    "manifest": "manifest.schema.json",
    "navigation": "navigation.schema.json",
    "page": "page.schema.json",
    "sitemap": "sitemap.schema.json",
    "images": "images.schema.json",
    "report": "report.schema.json",
}


def schema_dir() -> Path:
    env = os.environ.get("SITE_SCRAPER_SCHEMA_DIR")
    if env:
        return Path(env)
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "schemas" / "v1"
        if (candidate / "page.schema.json").exists():
            return candidate
    raise FileNotFoundError("schemas/v1 not found – set SITE_SCRAPER_SCHEMA_DIR")


class SchemaSet:
    def __init__(self, directory: Path | None = None):
        directory = directory or schema_dir()
        registry = Registry()
        self.schemas = {}
        for name, filename in SCHEMA_FILES.items():
            schema = json.loads((directory / filename).read_text(encoding="utf-8"))
            self.schemas[name] = schema
            registry = registry.with_resource(schema["$id"], Resource.from_contents(schema))
        self.validators = {name: Draft202012Validator(schema, registry=registry) for name, schema in self.schemas.items()}

    def errors(self, name: str, data) -> list[str]:
        out = []
        for error in sorted(self.validators[name].iter_errors(data), key=lambda e: list(e.absolute_path)):
            location = "/".join(str(p) for p in error.absolute_path) or "(root)"
            out.append(f"{location}: {error.message[:300]}")
        return out


def validate_archive(root: Path, schemas: SchemaSet | None = None) -> list[str]:
    """Validate all files of an archive against Schema v1 and check cross references."""
    schemas = schemas or SchemaSet()
    root = Path(root)
    problems: list[str] = []

    def load(rel: str):
        path = root / rel
        if not path.exists():
            problems.append(f"{rel}: file missing")
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            problems.append(f"{rel}: invalid JSON ({exc})")
            return None

    def check(rel: str, schema: str):
        data = load(rel)
        if data is not None:
            if isinstance(data, dict) and str(data.get("schemaVersion", "")).split(".")[0] != SCHEMA_VERSION.split(".")[0]:
                problems.append(f"{rel}: unsupported schemaVersion {data.get('schemaVersion')!r} (expected {SCHEMA_VERSION})")
                return data
            problems.extend(f"{rel}: {e}" for e in schemas.errors(schema, data))
        return data

    manifest = check("manifest.json", "manifest")
    check("navigation.json", "navigation")
    check("sitemap.json", "sitemap")
    registry = check("assets/images.json", "images")
    for report in ("crawl-report", "failed-urls", "broken-links", "missing-assets"):
        if (root / "reports" / f"{report}.json").exists():
            check(f"reports/{report}.json", "report")
    if not manifest or "pages" not in manifest:
        return problems

    paths = set()
    for entry in manifest["pages"]:
        path = entry.get("path")
        if path in paths:
            problems.append(f"manifest.json: duplicate page path {path}")
        paths.add(path)
        content = check(entry["content"], "page") if entry.get("content") else None
        if content and content.get("path") != path:
            problems.append(f"{entry['content']}: path {content.get('path')!r} does not match manifest path {path!r}")
        for key in ("markdown", "html"):
            if entry.get(key) and not (root / entry[key]).exists():
                problems.append(f"manifest.json: {key} file of {path} missing ({entry[key]})")
        if entry.get("images"):
            images = check(entry["images"], "images")
            for image in (images or {}).get("images", []):
                if image.get("src") and not (root / image["src"]).exists():
                    problems.append(f"{entry['images']}: image file missing {image['src']}")
    for asset in (registry or {}).get("assets", []):
        if not (root / asset["file"]).exists():
            problems.append(f"assets/images.json: file missing {asset['file']}")
    return problems


def build_reports(config: CrawlConfig, state: CrawlState, export: ExportResult, schema_problems: list[str]) -> dict:
    output = Path(config.output)
    failed_items = [
        {"url": f["url"], "status": f.get("status"), "error": f.get("error"), "page": f.get("page")} for f in state.failed
    ]
    broken = []
    for link in export.unresolved_links:
        status = None
        for failure in state.failed:
            if failure["url"] == link["url"]:
                status = failure.get("status")
        if status is not None or link["reason"] != "not crawled":
            broken.append({"url": link["url"], "status": status, "error": link["reason"], "page": link["page"], "path": link["path"]})
    unique_broken = list({(b["url"], b["page"]): b for b in broken}.values())
    missing_assets = [{"url": a["url"], "status": None, "error": a.get("error"), "page": a.get("page")} for a in export.asset_failures]

    issues = []
    for item in state.skipped:
        if item["reason"] in ("max_pages", "max_depth"):
            continue
        issues.append({"type": "skipped", "message": item["reason"], "url": item["url"], "path": None})
    for item in state.documents:
        issues.append({"type": "document", "message": f"non-HTML resource ({item.get('contentType')})", "url": item["url"], "path": None})
    for nav in export.nav_without_page:
        issues.append({"type": "navigation-without-page", "message": f"navigation entry '{nav['label']}' has no exported page", "url": nav["url"], "path": nav["path"]})
    for path in export.empty_pages:
        issues.append({"type": "empty-page", "message": "no content blocks extracted", "url": None, "path": path})
    for url, error in (state.discovery.sitemap_errors if state.discovery else []):
        issues.append({"type": "sitemap", "message": error, "url": url, "path": None})
    for problem in schema_problems:
        issues.append({"type": "schema", "message": problem, "url": None, "path": None})

    limited = [i for i in state.skipped if i["reason"] in ("max_pages", "max_depth")]
    status = "complete"
    if state.limits_reached:
        status = "limited"
    if state.failed or schema_problems:
        status = "errors"
    stats = {
        "discovered": len(state.discovered),
        "sitemapUrls": len(state.discovery.urls) if state.discovery else 0,
        "exported": export.pages,
        "failed": len(state.failed),
        "skippedByLimits": len(limited),
        "skippedByRobots": sum(1 for i in state.skipped if i["reason"] == "robots.txt"),
        "skippedOther": sum(1 for i in state.skipped if i["reason"] not in ("max_pages", "max_depth", "robots.txt")),
        "documents": len(state.documents),
        "duplicates": state.duplicates,
        "aliases": len(state.aliases),
        "assets": export.assets,
        "assetsFailed": len(missing_assets),
        "brokenLinks": len(unique_broken),
        "unresolvedLinks": len(export.unresolved_links),
        "navigationWithoutPage": len(export.nav_without_page),
        "unsupportedBlocks": export.unsupported_blocks,
        "emptyPages": len(export.empty_pages),
        "renderErrors": state.render_errors,
        "schemaErrors": len(schema_problems),
    }
    report = {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "crawl",
        "status": status,
        "startedAt": state.started_at or None,
        "finishedAt": state.finished_at or None,
        "config": config.to_report(),
        "limitsReached": state.limits_reached,
        "stats": stats,
        "issues": issues,
    }
    reports = output / "reports"
    write_json(reports / "crawl-report.json", report)
    write_json(reports / "failed-urls.json", {"schemaVersion": SCHEMA_VERSION, "kind": "failed-urls", "items": failed_items})
    write_json(reports / "broken-links.json", {"schemaVersion": SCHEMA_VERSION, "kind": "broken-links", "items": unique_broken})
    write_json(reports / "missing-assets.json", {"schemaVersion": SCHEMA_VERSION, "kind": "missing-assets", "items": missing_assets})
    return report
