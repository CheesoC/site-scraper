#!/usr/bin/env python3
"""Richtet das Projekt ein (Linux, macOS, Windows; erneut ausführen ist unschädlich):

  1. Python-venv (.venv im Projektordner) mit den gepinnten Abhängigkeiten aus scraper/requirements-dev.txt
  2. Chromium für Playwright (Browser-Rendering des Scrapers)
  3. Node-Abhängigkeiten des Generators (npm ci nach package-lock.json)

    python scripts/setup.py [--no-browser] [--no-node]
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import venv
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VENV = ROOT / ".venv"
WINDOWS = os.name == "nt"
VENV_BIN = VENV / ("Scripts" if WINDOWS else "bin")
VENV_PY = VENV_BIN / ("python.exe" if WINDOWS else "python")
ENV = {**os.environ, "PYTHONIOENCODING": "utf-8"}


def run(cmd: list[str], cwd: Path = ROOT) -> None:
    subprocess.run(cmd, cwd=cwd, env=ENV, check=True)


def setup_python() -> None:
    print("==> Python", flush=True)
    if sys.version_info < (3, 11):
        sys.exit(f"Python >= 3.11 benötigt (gefunden: {sys.version.split()[0]})")
    if not VENV_PY.exists():
        print(f"    venv anlegen: {VENV}", flush=True)
        venv.create(VENV, with_pip=True)
    pip = [str(VENV_PY), "-m", "pip", "install", "--quiet"]
    run([*pip, "--upgrade", "pip"])
    run([*pip, "-r", str(ROOT / "scraper" / "requirements-dev.txt")])
    run([*pip, "--no-deps", "-e", str(ROOT / "scraper")])
    run([str(VENV_PY), "-c", "from importlib.metadata import version; print('    crawl4ai', version('crawl4ai'))"])


def setup_browser() -> None:
    print("==> Chromium für Playwright", flush=True)
    try:
        run([str(VENV_PY), "-m", "playwright", "install", "chromium"])
    except subprocess.CalledProcessError:
        print("    WARNUNG: Chromium konnte nicht installiert werden. Später erneut versuchen", file=sys.stderr)
        print("    oder den Scraper ohne Browser nutzen (--no-render).", file=sys.stderr)


def setup_node() -> None:
    print("==> Node (Generator)", flush=True)
    node, npm = shutil.which("node"), shutil.which("npm")
    if node is None or npm is None:
        sys.exit("Node.js >= 20.9 benötigt (nicht gefunden)")
    version = subprocess.run([node, "--version"], capture_output=True, text=True).stdout.strip()
    major, minor = (int(x) for x in version.lstrip("v").split(".")[:2])
    if (major, minor) < (20, 9):
        sys.exit(f"Node.js >= 20.9 benötigt (gefunden: {version})")
    lock = ROOT / "generator" / "package-lock.json"
    marker = ROOT / "generator" / "node_modules" / ".package-lock.json"
    if marker.exists() and marker.stat().st_mtime >= lock.stat().st_mtime:
        print("    node_modules aktuell")
        return
    run([npm, "ci", "--no-audit", "--no-fund", "--loglevel=error"], cwd=ROOT / "generator")


def main() -> int:
    parser = argparse.ArgumentParser(prog="python scripts/setup.py", description=__doc__.splitlines()[0])
    parser.add_argument("--no-browser", action="store_true", help="Chromium nicht installieren (Scraper dann nur mit --no-render)")
    parser.add_argument("--no-node", action="store_true", help="Node-Teil (Generator) überspringen")
    args = parser.parse_args()

    try:
        setup_python()
        if not args.no_browser:
            setup_browser()
        if not args.no_node:
            setup_node()
    except subprocess.CalledProcessError as exc:
        print(f"Fehler: {' '.join(map(str, exc.cmd))} (Exit {exc.returncode})", file=sys.stderr)
        return 1

    activate = r".\.venv\Scripts\Activate.ps1" if WINDOWS else "source .venv/bin/activate"
    print()
    print(f"Fertig. Aktivieren mit:  {activate}")
    print("Loslegen:                python redesign-tool.py create https://example.com")
    return 0


if __name__ == "__main__":
    sys.exit(main())
