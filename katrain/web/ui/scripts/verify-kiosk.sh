#!/usr/bin/env bash
# Verify the kiosk-2d dist stays within the board boundary:
#  - no /galaxy/* routes (Galaxy-only pages/links must be DCE'd out)
#  - no non-board /api/v1/live calls (kiosk talks to /api/v1/board/live only)
# Exits 0 on clean, 1 on any match.
#
# NOTE: three.js is now intentionally bundled in the kiosk build (3D Go board).
# We no longer fail on THREE. / 'three' / @react-three. The galaxy-route and
# non-board live-API guards below still apply.
set -euo pipefail

DIST="${DIST:-../static-kiosk-2d}"

if [[ ! -d "$DIST" ]]; then
  echo "❌ $DIST not found. Run 'npm run build:kiosk-2d' first." >&2
  exit 1
fi

fail=0

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
  echo "✅ kiosk boundary clean — no /galaxy/ / non-board live API in $DIST ($size total)"
fi

exit $fail
