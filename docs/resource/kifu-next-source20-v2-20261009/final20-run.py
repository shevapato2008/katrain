"""Run only after root adds a reviewed execution approval beside this script."""

import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path


p = Path(__file__).resolve().parent
env, phase = sys.argv[1:]
assert env in {"PROD", "TEST"} and phase in {"baseline", "dry-run", "apply", "verify"}
manifest_bytes = (p / "final20-execution-proposed-manifest.json").read_bytes()
manifest = json.loads(manifest_bytes)
approval = json.loads((p / "root-final20-execution-approval.json").read_text())
assert approval["reviewer_id"] == "/root" and approval["allow_apply"] is True
assert approval["manifest_sha256"] == hashlib.sha256(manifest_bytes).hexdigest()
assert approval["image_ids"] == manifest["required_image_ids"]
assert approval["bundle_sha256"] == {e: manifest[e]["bundle_sha256"] for e in ("PROD", "TEST")}
for helper, expected_sha in manifest["helper_sha256"].items():
    assert hashlib.sha256((p / helper).read_bytes()).hexdigest() == expected_sha
image = manifest["required_image_ids"][env]
assert subprocess.check_output(["docker", "image", "inspect", image, "--format", "{{.Id}}"], text=True).strip() == image
web = "katrain-web" if env == "TEST" else "katrain-ucloud-katrain-web-1"
meta = json.loads(subprocess.check_output(["docker", "inspect", web], text=True))[0]
url = next(value.split("=", 1)[1] for value in meta["Config"]["Env"] if value.startswith("KATRAIN_DATABASE_URL="))
result = subprocess.run(["docker", "run", "--rm", "--read-only", "--user", "0:0",
                         "--network", "container:" + web, "-e", "KATRAIN_DATABASE_URL=" + url,
                         "-v", str(p) + ":/work:ro", "--entrypoint", "python", image,
                         "/work/final20-inner.py", env, phase], capture_output=True, text=True)
if result.returncode:
    print(re.sub(r"\w+://\S+", "[redacted URL]", result.stderr[-3000:]), file=sys.stderr)
    raise SystemExit(result.returncode)
data = json.loads(result.stdout)
receipt = p / f"{env}-{phase}.json"
assert not receipt.exists(), f"refusing to overwrite {receipt}"
receipt.write_text(result.stdout)
if phase == "dry-run":
    assert data.get("ready") and data.get("write_ready", True) and not data.get("errors")
if phase == "apply":
    assert data.get("status") == "applied"
if phase == "verify":
    assert data.get("passed") and data.get("read_qualified_count") == 100
print(json.dumps({"environment": env, "phase": phase, "passed": True,
                  "status": data.get("status"), "batch_id": data.get("batch_id"),
                  "change_count": data.get("change_count"), "verified_name_count": data.get("verified_name_count"),
                  "qualified_count": data.get("read_qualified_count"),
                  "complete_players_delta": data.get("complete_players_delta"),
                  "bundle_sha256": data.get("bundle_sha256")}, ensure_ascii=False))
