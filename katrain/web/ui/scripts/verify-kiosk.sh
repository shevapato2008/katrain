#!/usr/bin/env bash
# Verify the kiosk-2d dist stays within the board boundary:
#  - no three.js / @react-three (3D board removed from kiosk on 2026-07-13 to free Mali GPU)
#  - no /galaxy/* routes (Galaxy-only pages/links must be DCE'd out)
#  - no live API path at all (the kiosk has no live module; the board proxy was removed 2026-09-23)
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

# Live — the kiosk has no live module (Fan 2026-09-22) and the board proxy /api/v1/board/live is gone.
# Any /api/v1/live or /api/v1/board/live string left in the kiosk dist is a call that would 404 on the box.
if matches=$(grep -lE "/api/v1/(board/)?live" "$DIST"/assets/*.js 2>/dev/null); then
  echo "❌ Found live API path in kiosk dist (kiosk has no live module):" >&2
  echo "$matches" >&2
  fail=1
fi

# Strict appliance builds must not retain any JS-readable bearer-token path.
# Legacy kiosk/Galaxy builds intentionally keep their historical localStorage contract.
if [[ "${VITE_BOX_SSO_STRICT:-false}" == "true" ]]; then
  if ! node - "$DIST" <<'NODE'
const fs = require('fs');
const path = require('path');
const assets = path.join(process.argv[2], 'assets');
const forbidden = /localStorage\.(?:getItem|setItem)\((["'`])token\1/;
const offenders = fs.readdirSync(assets)
  .filter((name) => name.endsWith('.js'))
  .filter((name) => forbidden.test(fs.readFileSync(path.join(assets, name), 'utf8')));
if (offenders.length) {
  console.error(`legacy localStorage token access remains in: ${offenders.join(', ')}`);
  process.exit(1);
}
NODE
  then
    echo "❌ strict Box SSO build contains legacy localStorage token reads/writes" >&2
    fail=1
  else
    echo "✅ strict Box SSO boundary clean — no legacy localStorage token reads/writes"
  fi
fi

if [[ $fail -eq 0 ]]; then
  size=$(du -sh "$DIST" | cut -f1)
  echo "✅ kiosk boundary clean — no three.js / /galaxy/ / live API in $DIST ($size total)"
fi

exit $fail
