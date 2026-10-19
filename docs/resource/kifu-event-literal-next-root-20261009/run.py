"""Run one pinned native Docker read-only capture on its remote host.

Stage this entire directory on the target host, then invoke TEST or PROD
sequentially after the root confirms the r4 service deployment. The web
container supplies its database URL without printing it.
"""

import argparse
import gzip
import hashlib
import json
from pathlib import Path
import re
import subprocess


D = Path(__file__).resolve().parent
CONFIG = {
    "TEST": {
        "web": "katrain-web",
        "image": "sha256:b606992b2f6c6ce6a7c00bd6c49f1a9fcc7330fc5ee44dd426bd6ecf30267e48",
    },
    "PROD": {
        "web": "katrain-ucloud-katrain-web-1",
        "image": "sha256:02e58b41bac1ca2bdb4cd0aa1d15a319c63781e098b0cb1523dbbc318f2bc7bc",
    },
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("environment", choices=tuple(CONFIG))
    parser.add_argument("--post-owner", action="store_true", help="capture the approved 122-owner name scope")
    args = parser.parse_args()
    env = args.environment
    cfg = CONFIG[env]
    output = D / (f"{env}-postowner-capture.json.gz" if args.post_owner else f"{env}-capture.json.gz")
    if output.exists():
        raise FileExistsError(output)
    actual = subprocess.check_output(
        ["docker", "image", "inspect", cfg["image"], "--format", "{{.Id}}"], text=True).strip()
    if actual != cfg["image"]:
        raise RuntimeError("pinned native importer image ID changed")
    web = json.loads(subprocess.check_output(["docker", "inspect", cfg["web"]], text=True))[0]
    matches = [value.split("=", 1)[1] for value in web["Config"]["Env"]
               if value.startswith("KATRAIN_DATABASE_URL=")]
    if len(matches) != 1:
        raise RuntimeError("running web container lacks one database URL")
    command = ["docker", "run", "--rm", "--read-only", "--user", "0:0", "-i",
               "--network", "container:" + cfg["web"], "--env-file", "/dev/stdin",
               "-v", str(D) + ":/work:ro", "-w", "/app", "--entrypoint", "python",
               cfg["image"], "/work/capture.py", "--environment", env, "--stdout"]
    if args.post_owner:
        command.extend(["--stage", "post-owner"])
    completed = subprocess.run(command, input=("KATRAIN_DATABASE_URL=" + matches[0] + "\n").encode(),
                               capture_output=True)
    if completed.returncode:
        stderr = completed.stderr.decode(errors="replace")[-2000:]
        raise RuntimeError(re.sub(r"\w+://\S+", "[redacted URL]", stderr))
    data = json.loads(completed.stdout)
    expected_status = "post_owner_read_only" if args.post_owner else "unsigned_read_only"
    expected_count = 122 if args.post_owner else 150
    if data["environment"] != env or data["status"] != expected_status or data["raw_count_requested"] != expected_count:
        raise RuntimeError("capture output identity or finite count differs")
    if args.post_owner and not data["ready_for_unsigned_name_review"]:
        raise RuntimeError("post-owner capture has rejected owners, scope drift, or collisions")
    output.write_bytes(gzip.compress(completed.stdout, mtime=0))
    print(json.dumps({"environment": env, "capture": output.name,
                      "capture_sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
                      "compressed_bytes": output.stat().st_size,
                      "raw_count_requested": data["raw_count_requested"],
                      "eligible_raw_count": data["eligible_raw_count"],
                      "current_null_games": data["current_null_games"],
                      "rejections": len(data["rejections"]),
                      "external_collisions": len(data["external_collisions"]),
                      "ready_for_unsigned_owner_review": data["ready_for_unsigned_owner_review"]},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
