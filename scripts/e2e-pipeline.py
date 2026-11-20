#!/usr/bin/env python3
"""Gesamttest: lokale Test-Website -> Scraper (Browser-Rendering) -> Generator -> npm install -> next build -> Playwright.

    python scripts/e2e-pipeline.py              # mit Browser-Rendering
    python scripts/e2e-pipeline.py --no-render

Weitere Optionen gehen an den Scraper. Umgebungsvariable PORT (Standard 8790) für die Test-Website.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "outputs" / "e2e-pipeline-source"
WEBSITE = ROOT / "outputs" / "e2e-pipeline-website"
ENV = {**os.environ, "PYTHONIOENCODING": "utf-8"}


def venv_python() -> str:
    for candidate in (ROOT / ".venv" / "Scripts" / "python.exe", ROOT / ".venv" / "bin" / "python"):
        if candidate.exists():
            return str(candidate)
    return sys.executable


def main() -> int:
    if any(arg in ("-h", "--help") for arg in sys.argv[1:]):
        print(__doc__)
        return 0
    python = venv_python()
    port = os.environ.get("PORT", "8790")
    npm = shutil.which("npm")
    if npm is None:
        print("npm nicht gefunden - Node.js >= 20.9 installieren.", file=sys.stderr)
        return 1

    server = subprocess.Popen(
        [python, str(ROOT / "scraper" / "tests" / "fixture_server.py"), port],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        time.sleep(1)

        print("==> Scraper", flush=True)
        shutil.rmtree(SOURCE, ignore_errors=True)
        # Exit-Code bewusst ignoriert: die Validierung danach entscheidet
        subprocess.call(
            [python, "-m", "scraper", "--url", f"http://localhost:{port}/", "--output", str(SOURCE), "--delay", "0", *sys.argv[1:]],
            cwd=ROOT / "scraper",
            env=ENV,
        )
        if subprocess.call([python, "-m", "scraper", "validate", str(SOURCE)], cwd=ROOT / "scraper", env=ENV) != 0:
            return 1

        print("==> Generator + Build + Browser", flush=True)
        generator = ROOT / "generator"
        if not (generator / "node_modules").exists():
            if subprocess.call([npm, "install", "--no-audit", "--no-fund", "--loglevel=error"], cwd=generator) != 0:
                return 1
        return subprocess.call(
            [npm, "run", "--silent", "test:e2e", "--", "--source", str(SOURCE), "--output", str(WEBSITE)],
            cwd=generator,
        )
    finally:
        server.terminate()
        server.wait()


if __name__ == "__main__":
    sys.exit(main())
