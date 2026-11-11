#!/usr/bin/env bash
#
# One-command demo: scrape the practice catalogue politely, export the static
# dashboard + reports, build the site, serve it, and open a browser.
#
#   ./scripts/demo.sh            # full catalogue, simulated movement
#   PORT=4000 ./scripts/demo.sh  # different port
#   SKIP_SCRAPE=1 ./scripts/demo.sh
#   SCRAPE_ARGS="--max-pages 5 --simulate --ensure-history 7" ./scripts/demo.sh
#
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PORT="${PORT:-3000}"
SCRAPE_ARGS="${SCRAPE_ARGS:---simulate --ensure-history 14}"

for tool in uv pnpm curl; do
  if ! command -v "$tool" >/dev/null 2>&1; then
    echo "error: '$tool' is required but was not found in PATH." >&2
    echo "       Python: https://docs.astral.sh/uv/  Node: https://pnpm.io/installation" >&2
    exit 1
  fi
done

echo "==> Syncing Python environment"
uv sync

echo "==> Installing dashboard dependencies"
pnpm --dir web install --frozen-lockfile

if [[ "${SKIP_SCRAPE:-0}" != "1" ]]; then
  echo "==> Scraping books.toscrape.com (${SCRAPE_ARGS})"
  # Deliberately unquoted: SCRAPE_ARGS is a small, trusted flag list.
  uv run price-monitor scrape ${SCRAPE_ARGS}
else
  echo "==> Skipping scrape (SKIP_SCRAPE=1)"
fi

echo "==> Exporting dashboard JSON, CSV and Excel"
uv run price-monitor export

echo "==> Building static dashboard"
pnpm --dir web build

echo "==> Serving http://127.0.0.1:${PORT}"
(
  cd web
  node scripts/serve.mjs out "$PORT"
) &
SERVER_PID=$!

cleanup() {
  kill "$SERVER_PID" 2>/dev/null || true
  wait "$SERVER_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

for _ in $(seq 1 60); do
  if curl -fsS "http://127.0.0.1:${PORT}/" >/dev/null 2>&1; then
    break
  fi
  sleep 0.25
done

URL="http://127.0.0.1:${PORT}/"
if [[ "${NO_OPEN:-0}" == "1" ]]; then
  echo "Open ${URL} in your browser."
elif command -v open >/dev/null 2>&1; then
  open "$URL" || true
elif command -v xdg-open >/dev/null 2>&1; then
  xdg-open "$URL" >/dev/null 2>&1 || true
else
  echo "Open ${URL} in your browser."
fi

echo
echo "Price Monitor is running at ${URL}"
echo "Press Ctrl+C to stop."
wait "$SERVER_PID"
