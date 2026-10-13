"""Run one read-only capture in the exact patched administrative image.

Root stages this directory on each host and supplies that host's importer image ID.
"""

import argparse
import gzip
import hashlib
import json
from pathlib import Path
import re
import subprocess


D = Path(__file__).resolve().parent
WEB = {"TEST": "katrain-web", "PROD": "katrain-ucloud-katrain-web-1"}
WEB_IMAGES = {
    "TEST": "sha256:1f9c816c13f307987d44b66e0c5039391851104d4a0e89e5133f5d374f657547",
    "PROD": "sha256:fabec65da76101313ba5b96ae2f4116982f8b3b7722a3b76a9bec06721ab08ee",
}
MODULE_SHA256 = "0aab89aa5a93541dde26381254d3e9ff1a1a1dc6707b6089ba6fd6f473506b1f"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("environment", choices=tuple(WEB))
    parser.add_argument("--image-id", required=True, help="patched importer sha256:... Docker image ID")
    parser.add_argument("--post-owner", action="store_true")
    args = parser.parse_args()
    env, image = args.environment, args.image_id
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", image):
        parser.error("--image-id must be a full Docker image ID")
    output = D / (f"{env}-postowner-capture.json.gz" if args.post_owner else f"{env}-capture.json.gz")
    if output.exists():
        raise FileExistsError(output)
    web = json.loads(subprocess.check_output(["docker", "inspect", WEB[env]], text=True))[0]
    actual = subprocess.check_output(["docker", "image", "inspect", image, "--format", "{{.Id}}"], text=True).strip()
    if actual != image or web["Image"] != WEB_IMAGES[env]:
        raise RuntimeError("administrative image or existing web image differs from its pin")
    module_sha = subprocess.check_output([
        "docker", "run", "--rm", "--read-only", "--network", "none", "--entrypoint", "sha256sum", image,
        "/app/katrain/web/kifu/raw_event_translation.py"], text=True).split()[0]
    if module_sha != MODULE_SHA256:
        raise RuntimeError(f"native mixed-game module hash differs: {module_sha}")
    urls = [item.split("=", 1)[1] for item in web["Config"]["Env"]
            if item.startswith("KATRAIN_DATABASE_URL=")]
    if len(urls) != 1:
        raise RuntimeError("running web container lacks one database URL")
    command = ["docker", "run", "--rm", "--read-only", "--user", "0:0", "-i",
               "--network", "container:" + WEB[env], "--env-file", "/dev/stdin",
               "-v", str(D) + ":/work:ro", "-w", "/app", "--entrypoint", "python", image,
               "/work/capture.py", "--environment", env, "--stdout"]
    if args.post_owner:
        command += ["--stage", "post-owner"]
    completed = subprocess.run(command, input=("KATRAIN_DATABASE_URL=" + urls[0] + "\n").encode(),
                               capture_output=True)
    if completed.returncode:
        raise RuntimeError(re.sub(r"[A-Za-z][A-Za-z0-9+.-]*://\S+", "[redacted URL]",
                                  completed.stderr.decode(errors="replace")[-2000:]))
    result = json.loads(completed.stdout)
    expected = "post_owner_read_only" if args.post_owner else "unsigned_read_only"
    if result["environment"] != env or result["status"] != expected:
        raise RuntimeError("capture output identity differs")
    if not args.post_owner and result["raw_count_requested"] != 150:
        raise RuntimeError("pre-owner capture does not contain all 150 source titles")
    if args.post_owner and not result["ready_for_unsigned_name_review"]:
        raise RuntimeError("post-owner capture has scope drift or collisions")
    output.write_bytes(gzip.compress(completed.stdout, mtime=0))
    print(json.dumps({"environment": env, "capture": output.name,
                      "capture_sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
                      "raw_count_requested": result["raw_count_requested"],
                      "eligible_raw_count": result["eligible_raw_count"],
                      "current_null_games": result["current_null_games"],
                      "rejections": len(result["rejections"]),
                      "external_collisions": len(result["external_collisions"])}, ensure_ascii=False))


if __name__ == "__main__":
    main()
