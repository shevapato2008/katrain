"""Run the bounded post-590 statistics reader in the pinned PROD r2 importer."""

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
HOST = "ucloud-v100"
CONTAINER = "katrain-ucloud-katrain-web-1"
IMAGE = "sha256:b1966627c63c7f7004c7de84a8e278c3f975c57554093c677d38b1c4ec7a8590"


def encoded(raw):
    return base64.b64encode(gzip.compress(raw, mtime=0)).decode()


def main():
    baseline = json.loads((OLD / "PROD-progress-after589-actual.json").read_text())
    approved = json.loads((D / "PROD-ko20-candidates.approved.json").read_text())
    expected_ids = {row["owner"]["id"] for row in approved}
    gaps = json.loads((OLD / "PROD-old-ko-proof-gap-readonly.json").read_text())["rows"]
    if baseline["players_done_count"] != 1647 or len(gaps) != 28 or len(expected_ids) != 20:
        raise ValueError("local post-589 baseline or approved KO20 scope changed")
    if not expected_ids <= {row["player_id"] for row in gaps}:
        raise ValueError("KO20 scope is not contained in the previously observed 28 gaps")
    old_helper = (OLD / "post-progress-readonly.py").read_bytes()
    reader = (D / "590-post-progress-readonly.py").read_bytes()
    setup = "\n".join([
        "import base64,gzip,json,sys,types",
        "p=types.ModuleType('progress')",
        "p.__file__='/tmp/post-progress-readonly.py'",
        "sys.modules['progress']=p",
        f"exec(compile(gzip.decompress(base64.b64decode('{encoded(old_helper)}')),p.__file__,'exec'),p.__dict__)",
        f"BASELINE=json.loads(gzip.decompress(base64.b64decode('{encoded(json.dumps(baseline,ensure_ascii=False).encode())}')))",
        f"APPROVED_CANDIDATES=json.loads(gzip.decompress(base64.b64decode('{encoded(json.dumps(approved,ensure_ascii=False).encode())}')))",
        f"exec(compile(gzip.decompress(base64.b64decode('{encoded(reader)}')),'590-post-progress-readonly.py','exec'))",
    ])
    inspect = subprocess.run(
        ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8", HOST,
         f"docker image inspect --format '{{{{.Id}}}}' {IMAGE}"],
        capture_output=True, text=True, timeout=20,
    )
    if inspect.returncode or inspect.stdout.strip() != IMAGE:
        raise RuntimeError("Pinned r2 importer image is unavailable; post-590 statistics not run")
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
        error = result.stderr.decode(errors="replace")[-3000:]
        error = re.sub(r"\w+://\S+", "[redacted URL]", error)
        raise RuntimeError(f"PROD read-only post-590 reader failed: {error}")
    data = json.loads(result.stdout.decode().strip().splitlines()[-1])
    progress, audit, names = data["progress"], data["audit"], data["live_ko_names"]
    if audit["bounded_scope"]["games"] != 4406 or len(names) != 20:
        raise ValueError("post-590 actual scope or live-name count mismatch")
    if progress["players_done_count"] != 1667 or progress["unqualified_legacy_ko_count"] != 8:
        raise ValueError("post-590 native completion count or old KO gap count mismatch")
    audit["elapsed_seconds"] = elapsed
    for filename, content in [
        ("590-PROD-progress-actual.json", progress),
        ("590-PROD-progress-audit.json", audit),
        ("590-PROD-live-ko-names.json", {"environment": "PROD", "batch_id": 590,
                                          "observed_at": progress["observed_at"], "rows": names}),
    ]:
        (D / filename).write_text(json.dumps(content, ensure_ascii=False, sort_keys=True, indent=2) + "\n")
    print(json.dumps({"elapsed_seconds": elapsed, "players_done": progress["players_done_count"],
                      "both_players_games": progress["both_players_five_lang_games"],
                      "strict_full_cards": progress["complete_five_lang_display_games"],
                      "bounded_scope": audit["bounded_scope"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
