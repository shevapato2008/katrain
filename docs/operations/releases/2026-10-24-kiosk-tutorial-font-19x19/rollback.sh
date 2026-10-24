#!/usr/bin/env bash
set -euo pipefail
release=/mnt/data/smartbox-deployments/20261024-kiosk-tutorial-19x19-09ee7f59f
runtime=/root/smartbox-software/vendor/katrain
dropin=/etc/systemd/system/smartbox-katrain.service.d/zzzzzzz-kiosk-tutorial-19x19-release.conf
python=/opt/smartbox/venv-katrain/bin/python
rollback() {
  echo 'activation failed; restoring prior source/static and restarting only KaTrain' >&2
  systemctl stop smartbox-katrain.service || true
  rsync -a "$release/rollback/runtime/" "$runtime/"
  RELEASE_DIR="$release" RUNTIME_DIR="$runtime" "$python" - <<'PY'
from pathlib import Path
import json,os,shutil
r=Path(os.environ['RELEASE_DIR']);d=Path(os.environ['RUNTIME_DIR'])
for name in json.loads((r/'rollback/runtime-files.json').read_text())['absent']:
 (d/name).unlink(missing_ok=True)
for name in ['.smartbox-deployed-commit','.smartbox-release.json']:
 old=r/'rollback'/name
 if old.exists():shutil.copy2(old,d/name)
 else:(d/name).unlink(missing_ok=True)
old=r/'rollback/.smartbox-deploy-revisions'
if old.exists():shutil.copy2(old,Path('/root/smartbox-software/.smartbox-deploy-revisions'))
PY
  rsync -a --delete "$release/rollback/static/" "$runtime/katrain/web/static/"
  rsync -a --delete "$release/rollback/static-kiosk-2d/" "$runtime/katrain/web/static-kiosk-2d/"
  rm -f -- "$dropin"
  systemctl daemon-reload
  systemctl start smartbox-katrain.service
}
rollback
