"""Command line interface.

    python -m scraper --url https://example.com --output ./outputs/example-source
    python -m scraper validate ./outputs/example-source
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

from .config import CrawlConfig


def crawl_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m scraper",
        description="Erfasst eine Website als Content-Archiv (Schema v1.0). Unterbefehl: 'validate <archiv>'.",
    )
    parser.add_argument("--url", required=True, help="Start-URL der Website")
    parser.add_argument("--output", required=True, type=Path, help="Ausgabeverzeichnis des Archivs")
    parser.add_argument("--max-depth", type=int, default=10, help="maximale Link-Tiefe (Standard: 10)")
    parser.add_argument("--max-pages", type=int, default=500, help="maximale Anzahl Seitenabrufe (Standard: 500)")
    parser.add_argument("--allow-domain", action="append", default=[], metavar="DOMAIN", help="weitere erlaubte (Sub-)Domain, z. B. blog.example.com oder *.example.com; mehrfach möglich")
    parser.add_argument("--concurrency", type=int, default=4, help="parallele Abrufe (Standard: 4)")
    parser.add_argument("--delay", type=float, default=0.5, help="Mindestabstand pro Abruf in Sekunden (Standard: 0.5; robots.txt Crawl-delay hat Vorrang)")
    parser.add_argument("--timeout", type=float, default=30.0, help="Timeout pro Abruf in Sekunden")
    parser.add_argument("--retries", type=int, default=2, help="Wiederholungen bei temporären Fehlern")
    parser.add_argument("--no-render", action="store_true", help="kein Browser-Rendering (nur statisches HTML per HTTP)")
    parser.add_argument("--no-images", action="store_true", help="keine Bilder herunterladen")
    parser.add_argument("--no-sitemap", action="store_true", help="Sitemaps nicht auswerten")
    parser.add_argument("--no-html", action="store_true", help="original.html nicht speichern")
    parser.add_argument("--drop-query", action="store_true", help="alle Query-Parameter verwerfen (Standard: nur Tracking-Parameter)")
    parser.add_argument("--max-asset-mb", type=float, default=25, help="maximale Größe pro Bild in MB")
    parser.add_argument("-v", "--verbose", action="store_true")
    return parser


def run_crawl(args: argparse.Namespace) -> int:
    url = args.url if "://" in args.url else "https://" + args.url
    config = CrawlConfig(
        url=url,
        output=args.output,
        max_depth=args.max_depth,
        max_pages=args.max_pages,
        allow_domains=args.allow_domain,
        concurrency=args.concurrency,
        delay=args.delay,
        timeout=args.timeout,
        retries=args.retries,
        render=not args.no_render,
        download_images=not args.no_images,
        use_sitemap=not args.no_sitemap,
        keep_html=not args.no_html,
        query_mode="drop" if args.drop_query else "keep",
        max_asset_bytes=int(args.max_asset_mb * 1024 * 1024),
    )
    return asyncio.run(crawl(config))


async def crawl(config: CrawlConfig) -> int:
    from .crawler import PageCrawler
    from .exporter import ContentExporter
    from .urls import URLNormalizer
    from .validator import build_reports, validate_archive

    normalizer = URLNormalizer(config.url, config.allow_domains, config.query_mode)
    print(f"Crawle {normalizer.start_url} ({'Browser-Rendering' if config.render else 'statisch'}) …", flush=True)
    state = await PageCrawler(config, normalizer).run()
    print(f"  {len(state.pages)} Seiten erfasst, {len(state.failed)} fehlgeschlagen. Exportiere …", flush=True)
    export = await ContentExporter(config, normalizer, state).export()
    problems = validate_archive(config.output)
    report = build_reports(config, state, export, problems)
    stats = report["stats"]
    print(f"Fertig: {config.output}")
    print(f"  Status: {report['status']}" + (f" (Limits: {', '.join(report['limitsReached'])})" if report["limitsReached"] else ""))
    print(f"  Seiten: {stats['exported']} exportiert / {stats['discovered']} entdeckt / {stats['failed']} fehlgeschlagen")
    print(f"  Bilder: {stats['assets']} gespeichert / {stats['assetsFailed']} fehlgeschlagen")
    print(f"  Links:  {stats['brokenLinks']} defekt, {stats['navigationWithoutPage']} Navigationseinträge ohne Seite")
    if problems:
        print(f"  Schema: {len(problems)} Probleme, z. B. {problems[0]}")
    return 0 if stats["exported"] > 0 and not problems else 1


def run_validate(argv: list[str]) -> int:
    from .validator import validate_archive

    parser = argparse.ArgumentParser(prog="python -m scraper validate", description="Prüft ein Archiv gegen Content Schema v1.0.")
    parser.add_argument("archive", type=Path)
    args = parser.parse_args(argv)
    problems = validate_archive(args.archive)
    if problems:
        print(f"{len(problems)} Problem(e) in {args.archive}:")
        for problem in problems[:200]:
            print(f"  - {problem}")
        return 1
    print(f"OK: {args.archive} entspricht Content Schema v1.0")
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "validate":
        return run_validate(argv[1:])
    args = crawl_parser().parse_args(argv)
    logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    return run_crawl(args)
