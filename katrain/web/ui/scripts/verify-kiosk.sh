#!/usr/bin/env bash
# Verify the kiosk-2d dist stays within the board boundary:
#  - no three.js / @react-three (3D board removed from kiosk on 2026-07-13 to free Mali GPU)
#  - no /galaxy/* routes (Galaxy-only pages/links must be DCE'd out)
#  - no non-board /api/v1/live calls (kiosk talks to /api/v1/board/live only)
# Exits 0 on clean, 1 on any match.
set -euo pipefail

DIST="${DIST:-../static-kiosk-2d}"

if [[ ! -d "$DIST" ]]; then
  echo "❌ $DIST not found. Run 'npm run build:kiosk-2d' first." >&2
  exit 1
fi

fail=0

# three.js residue — the kiosk 3D board was removed; three/@react-three must be fully DCE'd out.
if matches=$(grep -lE "THREE\.|from *[\"']three[\"']|@react-three" "$DIST"/assets/*.js 2>/dev/null); then
  echo "❌ Found three.js / @react-three in kiosk dist (3D must not be in the kiosk build):" >&2
  echo "$matches" >&2
  fail=1
fi

# Galaxy route residue — kiosk must not link to or route any /galaxy/* page.
if matches=$(grep -l "/galaxy/" "$DIST"/assets/*.js 2>/dev/null); then
  echo "❌ Found /galaxy/ route in:" >&2
  echo "$matches" >&2
  fail=1
fi

# Live API base — kiosk reads only through the board proxy (/api/v1/board/live).
# Strip the legitimate board base first, then any remaining /api/v1/live is a leak.
for f in "$DIST"/assets/*.js; do
  [[ -e "$f" ]] || continue
  if sed 's#/api/v1/board/live#_#g' "$f" | grep -q "/api/v1/live"; then
    echo "❌ Found non-board /api/v1/live call in: $f" >&2
    fail=1
  fi
done

if [[ $fail -eq 0 ]]; then
  size=$(du -sh "$DIST" | cut -f1)
  echo "✅ kiosk boundary clean — no three.js / /galaxy/ / non-board live API in $DIST ($size total)"
fi

exit $fail
