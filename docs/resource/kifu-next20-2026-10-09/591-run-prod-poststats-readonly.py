"""Run one bounded, read-only PROD post-591 progress report in pinned r3 importer."""

import base64
import gzip
import json
import re
import shlex
import subprocess
import time
from pathlib import Path


D = Path(__file__).parent
OLD = D.parent / "kifu-pending-tw20-2026-10-09"
PRIOR = D.parent / "kifu-next-throughput-2026-10-09"
HOST = "ucloud-v100"
CONTAINER = "katrain-ucloud-katrain-web-1"
IMAGE = "sha256:ed6112e7006cad941c52ab28f668af0235ddad2d9761128eeee745c63625c67e"
RECEIPTS = "/tmp/kifu-mixed20-root-20261009"


def encoded(raw):
    return base64.b64encode(gzip.compress(raw, mtime=0)).decode()


def main():
    baseline = json.loads((PRIOR / "590-PROD-progress-actual.json").read_text())
    bundle = json.loads(gzip.open(D / "PROD-mixed20-unsigned-bundle.json.gz", "rt").read())
    summary = json.loads((D / "PROD-mixed20-unsigned-summary.json").read_text())
    approved = bundle["candidates"]
    receipt_cmd = (
        "python3 -c " + shlex.quote(
            "import json; from pathlib import Path; p=Path(" + repr(RECEIPTS) + "); "
            "print(json.dumps({n:json.loads((p/('PROD-'+n+'.json')).read_text()) "
            "for n in ('apply','verify')}))"
        )
    )
    receipt_result = subprocess.run(
        ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8", HOST, receipt_cmd],
        capture_output=True, text=True, timeout=20, check=True,
    )
    receipts = json.loads(receipt_result.stdout)
    applied, verified = receipts["apply"], receipts["verify"]
    batch_id = applied["batch_id"]
    bundle_sha = summary["bundle_sha256"]
    if (baseline["applied_batch_id"] != 590 or baseline["players_done_count"] != 1667
        or len(approved) != 20 or len({row["owner"]["id"] for row in approved}) != 20
        or batch_id != 591 or applied["status"] != "applied"
        or not verified["passed"] or verified["bundle_sha256"] != bundle_sha
        or verified["verified_name_count"] != 20 or verified["complete_players_delta"] != 20
        or verified["album_count"] != 1568 or verified["existing_names_unchanged_count"] != 80):
        raise ValueError("actual PROD receipt, approved mixed20 bundle, or post-590 baseline differs")
    old_helper = (OLD / "post-progress-readonly.py").read_bytes()
    reader = (D / "post-mixed20-progress-readonly.py").read_bytes()
    setup = "\n".join([
        "import base64,gzip,json,sys,types",
        "p=types.ModuleType('progress')",
        "p.__file__='/tmp/post-progress-readonly.py'",
        "sys.modules['progress']=p",
        f"exec(compile(gzip.decompress(base64.b64decode('{encoded(old_helper)}')),p.__file__,'exec'),p.__dict__)",
        f"BASELINE=json.loads(gzip.decompress(base64.b64decode('{encoded(json.dumps(baseline,ensure_ascii=False).encode())}')))",
        f"APPROVED_CANDIDATES=json.loads(gzip.decompress(base64.b64decode('{encoded(json.dumps(approved,ensure_ascii=False).encode())}')))",
        f"ACTUAL_BATCH_ID={batch_id}",
        f"ACTUAL_BUNDLE_SHA256={bundle_sha!r}",
        f"exec(compile(gzip.decompress(base64.b64decode('{encoded(reader)}')),'post-mixed20-progress-readonly.py','exec'))",
    ])
    inspect = subprocess.run(
        ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8", HOST,
         f"docker image inspect --format '{{{{.Id}}}}' {IMAGE}"],
        capture_output=True, text=True, timeout=20,
    )
    if inspect.returncode or inspect.stdout.strip() != IMAGE:
        raise RuntimeError("Pinned r3 importer image unavailable; no post-591 statistics run")
    command = (f"docker inspect --format '{{{{range .Config.Env}}}}{{{{println .}}}}{{{{end}}}}' {CONTAINER}"
               " | grep '^KATRAIN_DATABASE_URL='"
               f" | docker run --rm --read-only -i --env-file /dev/stdin --network container:{CONTAINER}"
               f" --entrypoint python {IMAGE} -c {shlex.quote(setup)}")
    start = time.monotonic()
    result = subprocess.run(
        ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8", HOST, command],
        capture_output=True, timeout=1200,
    )
    elapsed = round(time.monotonic() - start, 3)
    if result.returncode:
        error = re.sub(r"\w+://\S+", "[redacted URL]", result.stderr.decode(errors="replace")[-3000:])
        raise RuntimeError(f"PROD read-only post-591 reader failed: {error}")
    data = json.loads(result.stdout.decode().strip().splitlines()[-1])
    progress, audit, names = data["progress"], data["audit"], data["live_target_names"]
    if (audit["bounded_scope"]["games"] != 1568 or audit["bounded_scope"]["slots"] != 1613
        or len(names) != 20 or progress["players_done_count"] != 1687):
        raise ValueError("post-591 actual scope, qualified names, or player count differs")
    audit["elapsed_seconds"] = elapsed
    for filename, content in [
        ("591-PROD-progress-actual.json", progress),
        ("591-PROD-progress-audit.json", audit),
        ("591-PROD-live-target-names.json", {"environment": "PROD", "batch_id": 591,
                                             "observed_at": progress["observed_at"], "rows": names}),
    ]:
        (D / filename).write_text(json.dumps(content, ensure_ascii=False, sort_keys=True, indent=2) + "\n")
    print(json.dumps({"elapsed_seconds": elapsed, "players_done": progress["players_done_count"],
                      "both_players_games": progress["both_players_five_lang_games"],
                      "strict_full_cards": progress["complete_five_lang_display_games"],
                      "bounded_scope": audit["bounded_scope"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
