#!/usr/bin/env python3
"""One-release web-only operator. Default: fresh read-only preflight, private evidence.

Run on the selected host with access to its local Docker socket. Never uses SSH,
pull/build, SQL, migrations, dependency expansion, container removal, or retries.
"""
import argparse
import copy
import fcntl
import hashlib
import http.client
import json
import os
from pathlib import Path
import re
import socket
import stat
import subprocess
import sys
import time
import urllib.parse

HOSTS = {"test": "ubuntu", "prod": "10-60-162-188"}
WEB = {"test": "katrain-web", "prod": "katrain-ucloud-katrain-web-1"}
MANIFEST = Path("/var/lib/ucloud-migration-20261027/input/runtime-replay/runtime-manifest.private.json")
MANIFEST_SHA = "0d8c789f371da95c619d1e72dd956f7431a3a13145cb51d03168a3eb04e0e2b6"
PROD_NAMES = {
    "smartbox-platform", "smartbox-kifu-postgres-1", "smartbox-kifu-api-b-1", "smartbox-kifu-api-1",
    "smartbox-admin-admin-console-1", "platform-postgres", "pitch-booking-worker-1",
    "pitch-booking-postgres-1", "pitch-booking-caddy-1", "pitch-booking-api-1",
    "katrain-ucloud-postgres-1", "katrain-ucloud-minio-1", "katrain-ucloud-katrain-web-1",
    "katrain-ucloud-katrain-cron-1", "katrain-ucloud-katrain-admin-1",
    "katrain-ucloud-katago-web-1", "katrain-ucloud-katago-cron-1",
}
ENDPOINT_KEYS = ("IPAMConfig", "Links", "Aliases", "DriverOpts", "GwPriority")
OCI_REVISION = "org.opencontainers.image.revision"
RELEASE_LABEL = "io.katrain.kifu-search.release"


class Refused(Exception):
    pass


def require(ok, message):
    if not ok:
        raise Refused(message)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def write_private(path, value):
    data = value if isinstance(value, bytes) else canonical(value) + b"\n"
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "wb") as f:
        os.fchmod(f.fileno(), 0o600)
        f.write(data)


def private_json(path):
    require(not path.is_symlink() and stat.S_IMODE(path.stat().st_mode) == 0o600,
            "private input must be a regular mode0600 file")
    require(path.is_file(), "private input must be a regular file")
    return json.loads(path.read_bytes())


def env_map(values):
    result = {}
    for item in values or []:
        key, sep, value = item.partition("=")
        require(sep and key not in result, "missing/duplicate environment key")
        result[key] = value
    return result


def patched_env(values, sha):
    require("KATRAIN_BUILD_SHA" in env_map(values), "live build SHA key is missing")
    return ["KATRAIN_BUILD_SHA=" + sha if s.startswith("KATRAIN_BUILD_SHA=") else s for s in values]


def endpoints(container):
    result = {}
    for name, ep in container["NetworkSettings"]["Networks"].items():
        result[name] = {k: copy.deepcopy(ep[k]) for k in ENDPOINT_KEYS if k in ep}
        # Keep service/container aliases; generated IDs are not stable DNS identities.
        if result[name].get("Aliases") is not None:
            result[name]["Aliases"] = [a for a in result[name]["Aliases"]
                                        if a not in {container["Id"], container["Id"][:12]}]
    return result


def fingerprint(container):
    return digest({"Id": container["Id"], "Image": container["Image"], "Config": container["Config"],
                   "HostConfig": container["HostConfig"], "Mounts": container["Mounts"],
                   "Endpoints": endpoints(container), "Name": container["Name"]})


class UnixHTTP(http.client.HTTPConnection):
    def connect(self):
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.settimeout(60)
        self.sock.connect("/var/run/docker.sock")


class Engine:
    def __init__(self, target):
        require(socket.gethostname() == HOSTS[target], "local host identity mismatch")
        require(not os.environ.get("DOCKER_HOST") and not os.environ.get("DOCKER_CONTEXT"),
                "unset Docker remote/context environment")
        require(self.call("GET", "/info", versioned=False)["Name"] == HOSTS[target],
                "Docker daemon identity mismatch")
        version = self.call("GET", "/version", versioned=False)
        require(tuple(map(int, version["ApiVersion"].split("."))) >= (1, 54), "Docker API >=1.54 required")

    def call(self, method, path, obj=None, absent=False, versioned=True):
        c = UnixHTTP("localhost", timeout=60)
        try:
            data = canonical(obj) if obj is not None else None
            c.request(method, ("/v1.54" if versioned else "") + path, body=data,
                      headers={"Content-Type": "application/json"} if data else {})
            r = c.getresponse()
            body = r.read()
            if absent and r.status == 404:
                return None
            require(200 <= r.status < 300, "Docker " + method + " failed: HTTP " + str(r.status))
            return json.loads(body) if body else None
        finally:
            c.close()

    def inspect(self, name, absent=False):
        return self.call("GET", "/containers/" + urllib.parse.quote(name, safe="") + "/json", absent=absent)

    def inventory(self):
        rows = self.call("GET", "/containers/json?all=true")
        return {c["Name"].lstrip("/"): c for row in rows for c in [self.inspect(row["Id"])]}


def nonweb_state(inventory, web, backup=None):
    return {name: {"Id": c["Id"], "Image": c["Image"], "StartedAt": c["State"]["StartedAt"],
                   "RestartCount": c["RestartCount"], "Running": c["State"]["Running"],
                   "Status": c["State"]["Status"]}
            for name, c in inventory.items() if name not in {web, backup}}


def validate_candidate(engine, old, args):
    image = engine.call("GET", "/images/" + args.image + "/json")
    require(image["Id"] == args.image, "candidate immutable image ID mismatch")
    cfg = image["Config"]
    require(cfg.get("User", "") == old["Config"].get("User", ""), "candidate image user differs from live user")
    require((cfg.get("Labels") or {}).get(OCI_REVISION) == args.sha, "candidate OCI revision must equal full release SHA")
    source = engine.call("GET", "/images/" + old["Image"] + "/json")
    require(all(image.get(k) == source.get(k) for k in ("Os", "Architecture", "Variant")),
            "candidate platform differs from live image")
    for key in ("StopSignal", "StopTimeout", "Shell"):
        require(cfg.get(key) == source["Config"].get(key), "candidate changes image default " + key)
    # Docker merges image defaults into create requests. Refuse unplanned new defaults.
    require(set(env_map(cfg.get("Env"))) <= set(env_map(old["Config"].get("Env"))),
            "candidate introduces new default environment keys")
    for key in ("ExposedPorts", "Volumes"):
        require(set(cfg.get(key) or {}) <= set(old["Config"].get(key) or {}), "candidate adds default " + key)
    require("Healthcheck" in old["Config"] or not cfg.get("Healthcheck"), "candidate introduces a healthcheck")
    allowed = {OCI_REVISION, RELEASE_LABEL} if args.target == "prod" else {OCI_REVISION}
    require(set(cfg.get("Labels") or {}) <= set(old["Config"].get("Labels") or {}) | allowed,
            "candidate introduces unreviewed default labels")
    return image


def prod_payload(old, args):
    cfg = copy.deepcopy(old["Config"])
    cfg["Image"] = args.image
    cfg["Env"] = patched_env(cfg["Env"], args.sha)
    if cfg.get("Hostname") == old["Id"][:12]:
        cfg.pop("Hostname")
    cfg.setdefault("Labels", {}).update({OCI_REVISION: args.sha, RELEASE_LABEL: args.sha})
    host = copy.deepcopy(old["HostConfig"])
    require(not host.get("AutoRemove") and not host.get("VolumesFrom") and not host.get("Links"),
            "unsupported auto-remove/container dependency")
    for key in ("IpcMode", "PidMode", "UTSMode", "NetworkMode"):
        require(not str(host.get(key, "")).startswith("container:"), "container namespace dependency")
    cfg.update({"HostConfig": host, "NetworkingConfig": {"EndpointsConfig": endpoints(old)}})
    return cfg


def compare_runtime(new, old, args, payload=None):
    require(new["Image"] == args.image and new["State"]["Running"], "new web image/running mismatch")
    expected_env = env_map(patched_env(old["Config"]["Env"], args.sha))
    require(env_map(new["Config"]["Env"]) == expected_env, "new web environment differs")
    for key, value in old["Config"].items():
        if key not in {"Image", "Env", "Hostname", "Labels"}:
            require(new["Config"].get(key) == value, "new web Config drift: " + key)
    # Docker may normalize unset OomKillDisable to false; neither disables its OOM killer.
    for key, value in old["HostConfig"].items():
        actual = new["HostConfig"].get(key)
        require(actual == value or (key == "OomKillDisable" and actual in (None, False) and value in (None, False)),
                "new web HostConfig drift: " + key)
    require(endpoints(new) == endpoints(old), "new web stable network endpoints differ")
    require(new["Mounts"] == old["Mounts"], "new web mounts differ")
    if payload:
        require(new["Config"]["Env"] == payload["Env"], "PROD ordered environment differs")
        require(new["Config"].get("Labels") == payload["Labels"], "PROD release labels differ")


def run_private(command, output):
    result = subprocess.run(command, capture_output=True, env={**os.environ, "DOCKER_HOST": "unix:///var/run/docker.sock"})
    write_private(output.with_suffix(output.suffix + ".stdout"), result.stdout)
    write_private(output.with_suffix(output.suffix + ".stderr"), result.stderr)
    require(result.returncode == 0, "Docker Compose command failed; details only in private evidence")
    return result.stdout


def compose_setup(old, args, out):
    labels = old["Config"].get("Labels") or {}
    require(labels.get("com.docker.compose.project") == "katrain" and
            labels.get("com.docker.compose.service") == "katrain-web", "TEST Compose ownership mismatch")
    files = labels.get("com.docker.compose.project.config_files", "").split(",")
    require(len(files) == 11 and len(set(files)) == 11 and all(Path(p).is_absolute() for p in files),
            "TEST expected exact eleven existing Compose paths")
    require(all(Path(p).is_file() for p in files), "TEST Compose source file missing")
    base = ["docker", "--host", "unix:///var/run/docker.sock", "compose", "--project-directory",
            labels["com.docker.compose.project.working_dir"], "-p", "katrain"]
    for path in files:
        base += ["-f", path]
    original = json.loads(run_private(base + ["config", "--format", "json"], out / "compose-before.private"))
    original_hash = run_private(base + ["config", "--hash", "katrain-web"], out / "compose-hash.private").decode().split()
    require(original_hash == ["katrain-web", labels.get("com.docker.compose.config-hash")],
            "TEST effective Compose config differs from live config hash")
    require(original["services"]["katrain-web"].get("environment") == env_map(old["Config"]["Env"]),
            "TEST effective Compose environment differs from live")
    override = out / "release.override.private.json"
    write_private(override, {"services": {"katrain-web": {"image": args.image,
                                                          "environment": {"KATRAIN_BUILD_SHA": args.sha}}}})
    candidate_args = base + ["-f", str(override)]
    candidate = json.loads(run_private(candidate_args + ["config", "--format", "json"], out / "compose-after.private"))
    expected = copy.deepcopy(original)
    expected["services"]["katrain-web"]["image"] = args.image
    expected["services"]["katrain-web"]["environment"]["KATRAIN_BUILD_SHA"] = args.sha
    require(candidate == expected, "TEST full effective config changed beyond web image/build SHA")
    return candidate_args, {p: hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in files}, candidate


def assert_cas(engine, old, args, before_state):
    current = engine.inspect(WEB[args.target])
    require(current["Id"] == args.expected_id and current["Image"] == args.expected_image,
            "web CAS identity/image changed")
    require(current["State"]["Running"] and fingerprint(current) == fingerprint(old), "web CAS runtime changed")
    require(nonweb_state(engine.inventory(), WEB[args.target]) == before_state, "non-web runtime changed before apply")


def execute(args):
    require(re.fullmatch(r"[0-9a-f]{40}", args.sha), "release SHA must be full 40-hex")
    require(re.fullmatch(r"sha256:[0-9a-f]{64}", args.image), "candidate must be full immutable image ID")
    require(re.fullmatch(r"[0-9a-f]{64}", args.expected_id), "expected old ID must be full 64-hex")
    require(re.fullmatch(r"sha256:[0-9a-f]{64}", args.expected_image), "expected old image must be immutable")
    out = Path(args.output)
    require(out.is_absolute() and not out.is_symlink(), "evidence output must be a new absolute directory")
    out.mkdir(mode=0o700, parents=False, exist_ok=False)
    engine = Engine(args.target)
    before = engine.inventory()
    old = before[WEB[args.target]]
    require(old["Id"] == args.expected_id and old["Image"] == args.expected_image, "initial web CAS mismatch")
    require(old["State"]["Running"] and not old["State"].get("Paused") and not old["State"].get("Restarting"),
            "web must be running and stable")
    require(args.image != old["Image"], "candidate image equals current web image")
    validate_candidate(engine, old, args)
    before_state = nonweb_state(before, WEB[args.target])
    write_private(out / "before-inspect.private.json", before)
    payload, compose_args, source_files, effective = None, None, None, None
    backup = None
    if args.target == "prod":
        require(set(before) == PROD_NAMES and all(c["State"]["Running"] for c in before.values()),
                "PROD expected exact seventeen running services")
        private_json(MANIFEST)
        require(hashlib.sha256(MANIFEST.read_bytes()).hexdigest() == MANIFEST_SHA, "frozen manifest file SHA changed")
        require(old["HostConfig"]["RestartPolicy"]["Name"] in {"no", "unless-stopped"},
                "stopped PROD backup could restart automatically")
        payload = prod_payload(old, args)
        write_private(out / "candidate-create.private.json", payload)
        backup = WEB[args.target] + "-before-kifu-search-" + args.sha[:12] + "-" + old["Id"][:12]
        require(engine.inspect(backup, absent=True) is None, "PROD backup name already exists; do not retry blindly")
    else:
        require("katrain-cron" in before and before["katrain-cron"]["State"]["Running"], "TEST collector is not running")
        compose_args, source_files, effective = compose_setup(old, args, out)
    receipt = {"Target": args.target, "Hostname": HOSTS[args.target], "Web": WEB[args.target],
               "OldID": old["Id"], "OldImage": old["Image"], "CandidateImage": args.image,
               "ReleaseSHA": args.sha, "Apply": args.apply, "Status": "preflight-passed",
               "NonWebCount": len(before_state), "Backup": backup,
               "FrozenManifestFileSHA256": MANIFEST_SHA if args.target == "prod" else None,
               "ComposeFiles": len(source_files) if source_files else None}
    write_private(out / "preflight.receipt.json", receipt)
    print(json.dumps(receipt, sort_keys=True), flush=True)
    if not args.apply:
        return
    # One local helper at a time. Identity/config CAS is repeated after taking the lock.
    lock_path = "/tmp/kifu-search-web-only-20261027.lock"
    fd = os.open(lock_path, os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    require(os.fstat(fd).st_uid == os.geteuid(), "apply lock has different owner")
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        assert_cas(engine, old, args, before_state)
        if args.target == "test":
            require(all(hashlib.sha256(Path(p).read_bytes()).hexdigest() == sha for p, sha in source_files.items()),
                    "TEST Compose source changed after preflight")
            again = json.loads(run_private(compose_args + ["config", "--format", "json"], out / "compose-cas.private"))
            require(again == effective, "TEST effective Compose config changed after preflight")
            assert_cas(engine, old, args, before_state)
            run_private(compose_args + ["up", "-d", "--no-deps", "--no-build", "--pull", "never",
                                        "--force-recreate", "katrain-web"], out / "compose-up.private")
        else:
            require(hashlib.sha256(MANIFEST.read_bytes()).hexdigest() == MANIFEST_SHA, "frozen manifest changed before apply")
            engine.call("POST", "/containers/" + old["Id"] + "/stop?t=30")
            stopped = engine.inspect(old["Id"])
            require(stopped["State"]["Status"] == "exited" and stopped["State"].get("ExitCode") == 0 and
                    not stopped["State"].get("OOMKilled"), "PROD web did not stop normally; leave it for inspection")
            require(fingerprint(stopped) == fingerprint(old), "PROD web config changed during stop")
            engine.call("POST", "/containers/" + old["Id"] + "/rename?name=" + backup)
            write_private(out / "backup.receipt.json", {"Backup": backup, "ID": old["Id"], "State": "stopped"})
            created = engine.call("POST", "/containers/create?name=" + WEB[args.target], payload)
            write_private(out / "create.receipt.json", {"NewID": created["Id"], "Backup": backup})
            engine.call("POST", "/containers/" + created["Id"] + "/start")
        # Bounded health wait; each inspect is read-only, and failure never retries a mutation.
        deadline = time.monotonic() + 120
        while True:
            new = engine.inspect(WEB[args.target])
            require(new["State"]["Running"], "new web exited; preserve backup/evidence and investigate")
            health = new["State"].get("Health", {}).get("Status")
            require(health != "unhealthy", "new web unhealthy; investigate without automatic retry")
            if health in (None, "healthy"):
                break
            require(time.monotonic() < deadline, "new web health deadline exceeded")
            time.sleep(2)
        compare_runtime(new, old, args, payload)
        after = engine.inventory()
        write_private(out / "after-inspect.private.json", after)
        require(nonweb_state(after, WEB[args.target], backup) == before_state, "non-web ID/start/restart/state changed")
        if backup:
            require(after[backup]["Id"] == old["Id"] and not after[backup]["State"]["Running"], "backup identity/state changed")
            require(hashlib.sha256(MANIFEST.read_bytes()).hexdigest() == MANIFEST_SHA, "frozen manifest changed after apply")
        receipt.update({"Status": "applied-runtime-preservation-passed", "NewID": new["Id"],
                        "Health": health, "NonWebIDStartRestart": "identical"})
        write_private(out / "applied.receipt.json", receipt)
        print(json.dumps(receipt, sort_keys=True), flush=True)
    finally:
        os.close(fd)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", choices=("test", "prod"), required=True)
    parser.add_argument("--image", required=True)
    parser.add_argument("--sha", required=True)
    parser.add_argument("--expected-id", required=True)
    parser.add_argument("--expected-image", required=True)
    parser.add_argument("--output", required=True, help="new absolute private evidence directory")
    parser.add_argument("--apply", action="store_true", help="explicitly replace only selected web")
    execute(parser.parse_args())


if __name__ == "__main__":
    os.umask(0o077)
    try:
        main()
    except Refused as exc:
        print("REFUSED: " + str(exc), file=sys.stderr)
        sys.exit(2)
    except Exception as exc:
        # Docker/Compose/OS exception text can contain credentials: never print it.
        print("FAILED CLOSED: " + type(exc).__name__ + "; no automatic retry/rollback; inspect private evidence", file=sys.stderr)
        sys.exit(3)
