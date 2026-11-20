#!/usr/bin/env bash
# Gesamttest: lokale Test-Website → Scraper (Browser-Rendering) → Generator → npm install → next build → Playwright.
#
#   scripts/e2e-pipeline.sh            # mit Browser-Rendering
#   scripts/e2e-pipeline.sh --no-render
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="${PYTHON:-}"
if [[ -z "$PYTHON" ]]; then
  if [[ -x "$ROOT/.venv/bin/python" ]]; then PYTHON="$ROOT/.venv/bin/python"; else PYTHON="python3"; fi
fi
PORT="${PORT:-8790}"

"$PYTHON" "$ROOT/scraper/tests/fixture_server.py" "$PORT" > /dev/null 2>&1 &
SERVER=$!
trap 'kill $SERVER 2>/dev/null || true' EXIT
sleep 1

echo "==> Scraper"
rm -rf "$ROOT/outputs/e2e-pipeline-source"
(cd "$ROOT/scraper" && "$PYTHON" -m scraper --url "http://localhost:$PORT/" --output "$ROOT/outputs/e2e-pipeline-source" --delay 0 "$@") || true
"$PYTHON" -m scraper validate "$ROOT/outputs/e2e-pipeline-source"

echo "==> Generator + Build + Browser"
[[ -d "$ROOT/generator/node_modules" ]] || (cd "$ROOT/generator" && npm install --no-audit --no-fund --loglevel=error)
cd "$ROOT/generator"
npm run --silent test:e2e -- --source "$ROOT/outputs/e2e-pipeline-source" --output "$ROOT/outputs/e2e-pipeline-website"
