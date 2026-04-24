#!/usr/bin/env bash
# launch-kiosk.sh — Boot a local Chromium in kiosk mode against the 2D-only build.
#
# Usage:
#   bash scripts/launch-kiosk.sh
#   PORT=9191 RES=1920x1080 bash scripts/launch-kiosk.sh
#
# Prereq: cd katrain/web/ui && npm run build:kiosk-2d
# Backend note: the SPA calls /api/* — if you want working data, run KataGo server at :8000
#   and the FastAPI backend at :8001 alongside (outside this script's scope).

set -euo pipefail

PORT="${PORT:-9190}"
RES="${RES:-1280x800}"
STATIC_DIR="${STATIC_DIR:-katrain/web/static-kiosk-2d}"
ROUTE="${ROUTE:-/kiosk/login}"

if [[ ! -d "$STATIC_DIR" ]]; then
  echo "❌ $STATIC_DIR not found. Run: cd katrain/web/ui && npm run build:kiosk-2d" >&2
  exit 1
fi

# Find chromium / chrome.
CHROME=""
for candidate in chromium chromium-browser google-chrome chrome \
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  "/Applications/Chromium.app/Contents/MacOS/Chromium"; do
  if command -v "$candidate" >/dev/null 2>&1 || [[ -x "$candidate" ]]; then
    CHROME="$candidate"
    break
  fi
done

if [[ -z "$CHROME" ]]; then
  echo "❌ No chromium / chrome binary found on PATH." >&2
  exit 1
fi

# Boot static server (background).
npx --yes http-server "$STATIC_DIR" -p "$PORT" --silent -c-1 &
SERVER_PID=$!
trap "kill $SERVER_PID 2>/dev/null || true" EXIT
sleep 1

URL="http://localhost:${PORT}${ROUTE}"
echo "→ Launching kiosk: $URL (res=$RES, chrome=$CHROME)"

"$CHROME" \
  --kiosk \
  --app="$URL" \
  --window-size="${RES/x/,}" \
  --window-position=0,0 \
  --disable-pinch \
  --overscroll-history-navigation=0 \
  --no-first-run \
  --no-default-browser-check \
  --user-data-dir=/tmp/smartbox-kiosk-profile
