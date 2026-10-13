"""Run one bounded, read-only PROD post-592 progress report in pinned r5 importer."""

import argparse
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
PRIOR = D.parent / "kifu-next20-2026-10-09"
HOST = "ucloud-v100"
CONTAINER = "katrain-ucloud-katrain-web-1"
IMAGE = "sha256:6ffe9b6dad44ae280dc756d8468f1695337ca786541976413b515e614ebab3c5"


def encoded(raw):
    return base64.b64encode(gzip.compress(raw, mtime=0)).decode()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root-receipts-dir", required=True, help="remote directory containing actual PROD apply/verify JSON")
    args = parser.parse_args()
    baseline = json.loads((PRIOR / "591-PROD-progress-actual.json").read_text())
    bundle = json.loads(gzip.open(D / "PROD-post591-final20-unsigned-bundle.json.gz", "rt").read())
    approved = bundle["candidates"]
    from katrain.web.kifu.name_evidence import registry_sha256
    bundle_sha = registry_sha256(bundle)
    receipt_cmd = (
        "python3 -c " + shlex.quote(
            "import json; from pathlib import Path; p=Path(" + repr(args.root_receipts_dir) + "); "
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
    if (baseline["applied_batch_id"] != 591 or baseline["players_done_count"] != 1687
        or len(approved) != 20 or len({row["owner"]["id"] for row in approved}) != 20
        or batch_id != 592 or applied["status"] != "applied"
        or not verified["passed"] or verified["bundle_sha256"] != bundle_sha
        or verified["verified_name_count"] != 20 or verified["complete_players_delta"] != 20
        or verified["album_count"] != 609 or verified["game_slots"] != 614
        or verified["qualified_old_unchanged_count"] != 80
        or verified["read_qualified_count"] != 100):
        raise ValueError("actual PROD receipt, approved final20 bundle, or post-591 baseline differs")
    old_helper = (OLD / "post-progress-readonly.py").read_bytes()
    reader = (D / "592-post-progress-readonly.py").read_bytes()
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
        f"exec(compile(gzip.decompress(base64.b64decode('{encoded(reader)}')),'592-post-progress-readonly.py','exec'))",
    ])
    inspect = subprocess.run(
        ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8", HOST,
         f"docker image inspect --format '{{{{.Id}}}}' {IMAGE}"],
        capture_output=True, text=True, timeout=20,
    )
    if inspect.returncode or inspect.stdout.strip() != IMAGE:
        raise RuntimeError("Pinned r5 importer image unavailable; no post-592 statistics run")
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
        raise RuntimeError(f"PROD read-only post-592 reader failed: {error}")
    data = json.loads(result.stdout.decode().strip().splitlines()[-1])
    progress, audit, names = data["progress"], data["audit"], data["live_target_names"]
    if (audit["bounded_scope"]["games"] != 609 or audit["bounded_scope"]["slots"] != 614
        or len(names) != 20 or progress["players_done_count"] != 1707):
        raise ValueError("post-592 actual scope, qualified names, or player count differs")
    audit["elapsed_seconds"] = elapsed
    for filename, content in [
        ("592-PROD-progress-actual.json", progress),
        ("592-PROD-progress-audit.json", audit),
        ("592-PROD-live-target-names.json", {"environment": "PROD", "batch_id": 592,
                                             "observed_at": progress["observed_at"], "rows": names}),
    ]:
        (D / filename).write_text(json.dumps(content, ensure_ascii=False, sort_keys=True, indent=2) + "\n")
    print(json.dumps({"elapsed_seconds": elapsed, "players_done": progress["players_done_count"],
                      "both_players_games": progress["both_players_five_lang_games"],
                      "strict_full_cards": progress["complete_five_lang_display_games"],
                      "bounded_scope": audit["bounded_scope"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
