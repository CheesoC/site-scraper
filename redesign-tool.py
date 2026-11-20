#!/usr/bin/env python3
"""Gesamtskript: Scraper + Generator in einem Schritt (Linux, macOS, Windows).

    python redesign-tool.py create https://example.com [--name NAME] [--scope PFAD] [weitere Scraper-Optionen]

Ergebnis: outputs/<name>-source (Archiv) und outputs/<name>-website (Next.js-Projekt).
Existiert die Website schon, werden nur ihre Inhalte aktualisiert (sync) - das Design bleibt erhalten.
Alle unbekannten Optionen (z. B. --max-pages 100, --no-render) gehen an den Scraper.
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent


def venv_python() -> str:
    """Python der Projekt-venv, sonst der aktuelle Interpreter."""
    for candidate in (ROOT / ".venv" / "Scripts" / "python.exe", ROOT / ".venv" / "bin" / "python"):
        if candidate.exists():
            return str(candidate)
    return sys.executable


def default_name(url: str, scope: str | None) -> str:
    """Host plus Bereich, z. B. https://cms.sachsen.schule/fsamzeisigwald/x.html -> cms-sachsen-schule-fsamzeisigwald."""
    parts = urlsplit(url if "://" in url else "https://" + url)
    host = (parts.hostname or "site").removeprefix("www.")
    if scope is None:
        scope = parts.path[: parts.path.rfind("/") + 1]
    return re.sub(r"[^a-z0-9]+", "-", f"{host} {scope}".lower()).strip("-")


def run(cmd: list[str], cwd: Path) -> int:
    return subprocess.call(cmd, cwd=cwd, env={**os.environ, "PYTHONIOENCODING": "utf-8"})


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="python redesign-tool.py",
        description="Scraper + Generator in einem Schritt. Unbekannte Optionen gehen an den Scraper.",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    create = sub.add_parser("create", help="Website erfassen und Next.js-Projekt erzeugen bzw. aktualisieren")
    create.add_argument("url", help="Start-URL")
    create.add_argument("--name", help="Ordnername unter outputs/ (Standard: aus Host und Bereich)")
    create.add_argument("--scope", help="nur Seiten unterhalb dieses Pfads erfassen, wird zur Wurzel '/'")
    args, scraper_args = parser.parse_known_args()

    if args.scope is not None:
        scraper_args += ["--scope", args.scope]
    name = args.name or default_name(args.url, args.scope)
    source_dir = ROOT / "outputs" / f"{name}-source"
    website_dir = ROOT / "outputs" / f"{name}-website"

    print(f"==> 1/2 Scraper: {args.url} -> outputs/{name}-source", flush=True)
    status = run([venv_python(), "-m", "scraper", "--url", args.url, "--output", str(source_dir), *scraper_args], ROOT / "scraper")
    if not (source_dir / "manifest.json").exists():
        print(f"Scraper hat kein Archiv erzeugt (Exit {status}).")
        return 1
    if status != 0:
        print(f"Hinweis: Der Crawl meldet Probleme - siehe outputs/{name}-source/reports/. Es geht trotzdem weiter.")

    npm = shutil.which("npm")
    if npm is None:
        print("npm nicht gefunden - Node.js >= 20.9 installieren.")
        return 1
    generator = ROOT / "generator"
    if not (generator / "node_modules").exists():
        if run([npm, "install", "--no-audit", "--no-fund", "--loglevel=error"], generator) != 0:
            return 1
    if (website_dir / ".redesign-tool.json").exists():
        print(f"==> 2/2 Generator: Inhalte aktualisieren (sync) -> outputs/{name}-website", flush=True)
        cmd = [npm, "run", "--silent", "sync", "--", "--source", str(source_dir), "--project", str(website_dir)]
    else:
        print(f"==> 2/2 Generator: Website erzeugen -> outputs/{name}-website", flush=True)
        cmd = [npm, "run", "--silent", "generate", "--", "--source", str(source_dir), "--output", str(website_dir)]
    if run(cmd, generator) != 0:
        return 1

    print()
    print("Fertig. Starten mit:")
    print(f"  cd outputs/{name}-website")
    print("  npm install")
    print("  npm run dev")
    return 0


if __name__ == "__main__":
    sys.exit(main())
