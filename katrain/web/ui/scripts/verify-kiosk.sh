#!/usr/bin/env bash
# Verify the kiosk-2d dist contains no three.js / @react-three code.
# Exits 0 on clean, 1 on any match.
set -euo pipefail

DIST="${DIST:-../static-kiosk-2d}"

if [[ ! -d "$DIST" ]]; then
  echo "❌ $DIST not found. Run 'npm run build:kiosk-2d' first." >&2
  exit 1
fi

fail=0

# Minified three.js uses the `THREE.` namespace prefix.
if matches=$(grep -l "THREE\." "$DIST"/assets/*.js 2>/dev/null); then
  echo "❌ Found THREE. in:" >&2
  echo "$matches" >&2
  fail=1
fi

# Source-string residue check — dynamic import paths that survived minification.
if matches=$(grep -El '["'"'"']three["'"'"']|@react-three' "$DIST"/assets/*.js 2>/dev/null); then
  echo "❌ Found three / @react-three import string in:" >&2
  echo "$matches" >&2
  fail=1
fi

if [[ $fail -eq 0 ]]; then
  size=$(du -sh "$DIST" | cut -f1)
  echo "✅ no three.js in $DIST ($size total)"
fi

exit $fail
