"""Root-only pinned Docker runner for post-595 bounded stats and player pages."""

import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path


if not __debug__:
    raise RuntimeError("closure runner assertions must be enabled")
D = Path(__file__).resolve().parent
env, phase = sys.argv[1:]
assert env in {"PROD", "TEST"} and phase in {"stats", "pages-preview", "pages-apply", "pages-verify"}
assert phase != "stats" or env == "PROD"
manifest = json.loads((D / "595-closure-proposed-manifest.json").read_text())
for filename, expected in manifest["helper_sha256"].items():
    assert hashlib.sha256((D / filename).read_bytes()).hexdigest() == expected
assert hashlib.sha256((D / "595-pages-proposed-plan.json").read_bytes()).hexdigest() == manifest["pages_plan_sha256"]
assert hashlib.sha256((D / "player_pages.py").read_bytes()).hexdigest() == manifest["pinned_player_pages_sha256"]
if phase == "stats":
    assert hashlib.sha256((D / "595-PROD-baseline-594-progress.json.gz").read_bytes()).hexdigest() == manifest["baseline_progress_sha256"]
image = manifest["required_image_ids"][env]
assert subprocess.check_output(["docker", "image", "inspect", image, "--format", "{{.Id}}"],
                               text=True).strip() == image
web = "katrain-web" if env == "TEST" else "katrain-ucloud-katrain-web-1"
meta = json.loads(subprocess.check_output(["docker", "inspect", web], text=True))[0]
urls = [value.split("=", 1)[1] for value in meta["Config"]["Env"]
        if value.startswith("KATRAIN_DATABASE_URL=")]
assert len(urls) == 1
script = "595-bounded-stats-inner.py" if phase == "stats" else "595-pages-inner.py"
args = ["/work/" + script] + ([] if phase == "stats" else [env, phase.removeprefix("pages-")])
command = ["docker", "run", "--rm", "--read-only", "--user", "0:0", "-i",
           "--network", "container:" + web, "--env-file", "/dev/stdin",
           "-v", str(D) + ":/work:ro"]
if phase != "stats":
    command += ["-v", str(D / "player_pages.py") + ":/app/katrain/web/kifu/player_pages.py:ro"]
command += ["-w", "/app", "--entrypoint", "python", image, *args]
completed = subprocess.run(command, input=("KATRAIN_DATABASE_URL=" + urls[0] + "\n").encode(),
                           capture_output=True)
if completed.returncode:
    stderr = completed.stderr.decode(errors="replace")[-3000:]
    print(re.sub(r"[A-Za-z][A-Za-z0-9+.-]*://\S+", "[redacted URL]", stderr), file=sys.stderr)
    raise SystemExit(completed.returncode)
data = json.loads(completed.stdout)
if phase == "stats":
    audit = data["audit"]
    assert audit["environment"] == "PROD" and audit["batch_id"] == 595 and audit["read_only"]
    assert audit["bounded_scope"]["games"] == 158 and audit["bounded_scope"]["slots"] == 160
    receipts = {"595-PROD-progress-actual.json": data["progress"],
                "595-PROD-bounded-stats.json": audit}
    for filename in receipts:
        assert not (D / filename).exists(), f"refusing to overwrite {filename}"
    for filename, value in receipts.items():
        (D / filename).write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n")
    print(json.dumps({"environment": "PROD", "phase": "stats", "players_done": data["progress"]["players_done_count"],
                      "strict_cards": data["progress"]["complete_five_lang_display_games"],
                      "bounded_scope": audit["bounded_scope"]}, ensure_ascii=False))
else:
    page_phase = phase.removeprefix("pages-")
    assert data["environment"] == env and data["phase"] == page_phase
    if page_phase == "verify":
        assert data["passed"] and data["players_checked"] == 16
    else:
        report = data["preview"] if page_phase == "preview" else data["report"]
        assert report["players_scanned"] == 16
        assert report["committed"] == (page_phase == "apply")
    receipt = D / f"{env}-pages-{page_phase}.json"
    assert not receipt.exists(), f"refusing to overwrite {receipt}"
    receipt.write_text(completed.stdout.decode())
    print(json.dumps({"environment": env, "phase": page_phase, "passed": True,
                      "players_scanned": data.get("report", data.get("preview", {})).get("players_scanned"),
                      "pages_added": data.get("report", data.get("preview", {})).get("pages_added")},
                     ensure_ascii=False))
