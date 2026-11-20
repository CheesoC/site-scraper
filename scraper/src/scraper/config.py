"""Crawl configuration."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path

DEFAULT_USER_AGENT = "site-scraper/0.1 (+https://github.com/CheesoC/site-scraper)"


@dataclass
class CrawlConfig:
    url: str
    output: Path
    max_depth: int = 10
    max_pages: int = 500
    allow_domains: list[str] = field(default_factory=list)
    scope_path: str | None = None  # None: directory of the start URL; "/" = whole host
    concurrency: int = 4
    delay: float = 0.5
    timeout: float = 30.0
    retries: int = 2
    render: bool = True
    download_images: bool = True
    max_asset_bytes: int = 25 * 1024 * 1024
    query_mode: str = "keep"  # keep (non-tracking params) | drop (all)
    use_sitemap: bool = True
    keep_html: bool = True
    user_agent: str = DEFAULT_USER_AGENT

    def to_report(self) -> dict:
        data = asdict(self)
        data["output"] = str(self.output)
        return data
