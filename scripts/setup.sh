#!/usr/bin/env bash
# Richtet das Projekt ein (idempotent – erneut ausführen ist unschädlich):
#   1. Python-venv (.venv im Repo-Root) mit den gepinnten Abhängigkeiten aus scraper/requirements-dev.txt
#   2. Chromium für Playwright (Browser-Rendering des Scrapers)
#   3. Node-Abhängigkeiten des Generators (npm ci nach package-lock.json)
#
#   scripts/setup.sh [--no-browser] [--no-node]
#
# Umgebungsvariablen: PYTHON (Standard: python3), VENV_DIR (Standard: <repo>/.venv)
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="${PYTHON:-python3}"
VENV_DIR="${VENV_DIR:-$ROOT/.venv}"
WITH_BROWSER=1
WITH_NODE=1
for arg in "$@"; do
  case "$arg" in
    --no-browser) WITH_BROWSER=0 ;;
    --no-node) WITH_NODE=0 ;;
    -h|--help) sed -n '2,9p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "Unbekannte Option: $arg" >&2; exit 1 ;;
  esac
done

echo "==> Python"
"$PYTHON" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)' \
  || { echo "Python >= 3.11 benötigt ($("$PYTHON" --version 2>&1))" >&2; exit 1; }
if [[ ! -x "$VENV_DIR/bin/python" ]]; then
  echo "    venv anlegen: $VENV_DIR"
  "$PYTHON" -m venv "$VENV_DIR"
fi
"$VENV_DIR/bin/python" -m pip install --quiet --upgrade pip
"$VENV_DIR/bin/python" -m pip install --quiet -r "$ROOT/scraper/requirements-dev.txt"
"$VENV_DIR/bin/python" -m pip install --quiet --no-deps -e "$ROOT/scraper"
echo "    $("$VENV_DIR/bin/python" -m pip show crawl4ai | grep -E '^Version' | sed 's/Version: /crawl4ai /')"

if [[ $WITH_BROWSER -eq 1 ]]; then
  echo "==> Chromium für Playwright"
  if ! "$VENV_DIR/bin/python" -m playwright install chromium; then
    echo "    WARNUNG: Chromium konnte nicht installiert werden. Später erneut versuchen" >&2
    echo "    oder den Scraper ohne Browser nutzen (--no-render)." >&2
  fi
fi

if [[ $WITH_NODE -eq 1 ]]; then
  echo "==> Node (Generator)"
  command -v node >/dev/null || { echo "Node.js >= 20.9 benötigt (nicht gefunden)" >&2; exit 1; }
  node -e 'const [a,b]=process.versions.node.split(".").map(Number);process.exit(a>20||(a===20&&b>=9)?0:1)' \
    || { echo "Node.js >= 20.9 benötigt ($(node --version))" >&2; exit 1; }
  lock="$ROOT/generator/package-lock.json"
  marker="$ROOT/generator/node_modules/.package-lock.json"
  if [[ ! -f "$marker" || "$lock" -nt "$marker" ]]; then
    (cd "$ROOT/generator" && npm ci --no-audit --no-fund --loglevel=error)
  else
    echo "    node_modules aktuell"
  fi
fi

echo
echo "Fertig. Aktivieren mit:  source ${VENV_DIR#$ROOT/}/bin/activate"
echo "Loslegen:                ./redesign-tool create https://example.com"
