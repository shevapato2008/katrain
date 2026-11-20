#!/bin/zsh
cd "$(dirname "$0")" || exit 1
if curl --silent --fail --max-time 2 http://127.0.0.1:18950/manifest.json >/dev/null; then
  open 'http://127.0.0.1:18950/?demo=20261115-v2#chapter=2'
  exit 0
fi
(sleep 1; open 'http://127.0.0.1:18950/?demo=20261115-v2#chapter=2') &
exec python3 serve.py --port 18950
