#!/usr/bin/env python3
"""Private inspect replay preparation/operator. No shell, Compose, SSH, or remote Docker.

prepare writes only local private artifacts. replay defaults to offline dry-run.
Only replay --apply --phase staging|activate can contact /var/run/docker.sock.
"""
import argparse
import copy
import hashlib
import http.client
import ipaddress
import json
import os
from pathlib import Path
import socket
import stat
import subprocess
import sys
import urllib.parse

TARGET = "10-60-162-188"
ROOT = Path("/Users/fan/.local/share/ucloud-migration/2026-10-26")
ALLOW = {
    "katrain-ucloud-katrain-web-1", "smartbox-admin-admin-console-1", "smartbox-platform",
    "katrain-ucloud-katrain-admin-1", "katrain-ucloud-katrain-cron-1",
    "katrain-ucloud-katago-cron-1", "pitch-booking-caddy-1", "pitch-booking-worker-1",
    "pitch-booking-api-1", "katrain-ucloud-katago-web-1", "platform-postgres",
    "pitch-booking-postgres-1", "katrain-ucloud-minio-1", "smartbox-kifu-api-1",
    "smartbox-kifu-api-b-1", "smartbox-kifu-postgres-1", "katrain-ucloud-postgres-1",
}
EXCLUDED = {"katrain-ucloud-minio-setup-1", "smartbox-kifu-init-1", "smartbox-kifu-importer-1"}
STAGE_START = {
    "platform-postgres", "pitch-booking-postgres-1", "smartbox-kifu-postgres-1",
    "katrain-ucloud-postgres-1", "katrain-ucloud-minio-1", "katrain-ucloud-katago-web-1", "katrain-ucloud-katago-cron-1",
}
ISOLATED_WEB = {
    "katrain-ucloud-katrain-web-1", "smartbox-admin-admin-console-1", "smartbox-platform",
    "katrain-ucloud-katrain-admin-1", "pitch-booking-caddy-1", "pitch-booking-api-1",
    "smartbox-kifu-api-1", "smartbox-kifu-api-b-1",
}
LABEL = "io.ucloud.inspect-replay"
# These exact source images inherit old Compose ownership labels at Docker create.
# Explicit empty overrides prevent rejoining the unavailable old Compose projects.
COMPOSE_LABEL_DEFAULT_IMAGES = {
    "sha256:28f423c069fc439faa2b486eeb88d0a4c8297a221bdc407518661347acdf3ac0",
    "sha256:471818775e4743ea00dd07f95a77ac6782c9e4d0ede399b46d460093b0e16c29",
    "sha256:9760261da8ffebc648abb630f63f9f73d436ee26fe594b440f1a22f35f7c4d10",
}
COMPOSE_LABEL_DEFAULT_KEYS = ("com.docker.compose.project", "com.docker.compose.service", "com.docker.compose.version")
ENDPOINT_KEYS = ("IPAMConfig", "Links", "Aliases", "DriverOpts", "GwPriority")
NETWORK_KEYS = ("Driver", "Internal", "Attachable", "Ingress", "EnableIPv4", "EnableIPv6", "IPAM", "Options", "ConfigOnly", "ConfigFrom")
MEDIA_PATCH = {
    "katrain-ucloud-katrain-web-1": {"KATRAIN_S3_PUBLIC_BASE_URL": ["https://v100-preview.sailorvoyage.top/media", "https://modelstella.com/media"]},
    "katrain-ucloud-katrain-admin-1": {"KATRAIN_S3_PUBLIC_BASE_URL": ["https://v100-preview.sailorvoyage.top/media", "https://modelstella.com/media"]},
    "smartbox-admin-admin-console-1": {"SMARTBOX_ADMIN_MEDIA_ORIGINS": ["https://v100-preview.sailorvoyage.top", "https://modelstella.com"]},
}


class Refused(Exception):
    pass


def require(ok, message):
    if not ok:
        raise Refused(message)


def canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def digest(obj):
    return hashlib.sha256(canonical(obj)).hexdigest()


def private_read(path):
    path = Path(path)
    require(not path.is_symlink(), "private input may not be a symlink")
    require(stat.S_IMODE(path.stat().st_mode) == 0o600, "private input must be mode 0600")
    return json.loads(path.read_text())


def private_write(path, value, is_json=True):
    path = Path(path)
    require(not path.is_symlink(), "output may not be a symlink")
    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    os.fchmod(fd, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(json.dumps(value, ensure_ascii=False, indent=2) + "\n" if is_json else value)


def stage_bindings(bindings):
    out = {}
    for port, values in (bindings or {}).items():
        kept = []
        for item in values or []:
            host = item.get("HostIp", "")
            require(host == "10.8.0.3" or (host and ipaddress.ip_address(host).is_loopback),
                    "unexpected original public/wildcard host binding")
            if host != "10.8.0.3":
                kept.append(copy.deepcopy(item))
        if kept:
            out[port] = kept
    return out


def payload(record, phase):
    p = copy.deepcopy(record["Create"])
    if p["Image"] in COMPOSE_LABEL_DEFAULT_IMAGES:
        p.setdefault("Labels", {}).update({key: "" for key in COMPOSE_LABEL_DEFAULT_KEYS})
    if phase == "staging":
        p["HostConfig"]["PortBindings"] = stage_bindings(p["HostConfig"].get("PortBindings"))
        p["HostConfig"]["RestartPolicy"] = {"Name": "no", "MaximumRetryCount": 0}
    fingerprint = digest(p)
    p.setdefault("Labels", {}).update({LABEL: "2026-10-26", LABEL + ".phase": phase,
                                       LABEL + ".spec": fingerprint})
    return p


def controlled_patch(m, args):
    m = copy.deepcopy(m)
    changes = []
    if args.env_overrides:
        overrides = private_read(args.env_overrides)
        require(isinstance(overrides, dict) and overrides, "env overrides must be a nonempty container/key object")
        for name, pairs in overrides.items():
            require(name in MEDIA_PATCH and isinstance(pairs, dict) and pairs, "env override container not allowlisted")
            for key, replacement in pairs.items():
                require(key in MEDIA_PATCH[name] and replacement == MEDIA_PATCH[name][key][1], "env override key/value not allowlisted")
                env = m["Containers"][name]["Create"]["Env"]
                matches = [i for i, value in enumerate(env) if value.partition("=")[0] == key]
                require(len(matches) == 1 and env[matches[0]] == key + "=" + MEDIA_PATCH[name][key][0], "env override source differs from approved original")
                env[matches[0]] = key + "=" + replacement
                changes.append(name + ":" + key)
    if args.allow_minio_loopback:
        host = m["Containers"]["katrain-ucloud-minio-1"]["Create"]["HostConfig"]
        require(host.get("PortBindings") == {"9000/tcp": [{"HostIp": "10.8.0.3", "HostPort": "9000"}],
                                               "9001/tcp": [{"HostIp": "127.0.0.1", "HostPort": "9001"}]},
                "MinIO original bindings differ from authoritative inspect")
        host["PortBindings"]["9000/tcp"].append({"HostIp": "127.0.0.1", "HostPort": "9000"})
        changes.append("katrain-ucloud-minio-1:127.0.0.1:9000->9000/tcp")
    return m, changes


def validate_manifest(m):
    require(m.get("Schema") == 1 and m.get("TargetHostname") == TARGET, "wrong manifest schema/target")
    require(set(m["Containers"]) == ALLOW, "container allowlist mismatch")
    require(set(m["Excluded"]) == EXCLUDED, "excluded list mismatch")
    require(len(m["ImageIDs"]) == 16, "expected exactly 16 immutable image IDs")
    require(set(m["ImageIDs"]) == {r["Create"]["Image"] for r in m["Containers"].values()}, "image list mismatch")
    require(len(m["Networks"]) == 7 and len(m["Exports"]["Volumes"]) == 8 and len(m["Exports"]["Binds"]) == 4,
            "unexpected network/export count")
    for name, r in m["Containers"].items():
        p = r["Create"]
        require(p["Image"].startswith("sha256:") and len(p["Image"]) == 71, "image must be immutable sha256")
        require(not any(k.startswith("com.docker.compose.") for k in p.get("Labels", {})), "legacy Compose ownership retained")
        require(set(p["NetworkingConfig"]["EndpointsConfig"]) <= set(m["Networks"]), "unknown container network")
        h = p["HostConfig"]
        require(not h.get("PublishAllPorts") and not h.get("AutoRemove"), "unsafe implicit port publish/autoremove")
        require(not h.get("VolumesFrom") and not h.get("Links"), "container ID dependencies unsupported")
        stage_bindings(h.get("PortBindings"))
        # Do not let an unchanged secret URL accidentally point to an old/external PG.
        nets = set(p["NetworkingConfig"]["EndpointsConfig"])
        pg_hosts = set()
        for other, other_r in m["Containers"].items():
            if "postgres" not in other:
                continue
            for net, ep in other_r["Create"]["NetworkingConfig"]["EndpointsConfig"].items():
                if net in nets:
                    pg_hosts.add(other)
                    pg_hosts.update(ep.get("Aliases") or [])
        for e in p.get("Env") or []:
            k, _, v = e.partition("=")
            if ("DATABASE" in k.upper() or "POSTGRES" in k.upper()) and "://" in v:
                require(urllib.parse.urlsplit(v).hostname in pg_hosts, "database URL points outside same-network replay PG")


def prepare(args):
    source = private_read(args.source)
    raw = private_read(args.inventory)
    require(len(source) == 20, "expected 20 original inspect records")
    running = {c["Name"].lstrip("/"): c for c in source if c["State"]["Running"]}
    stopped = {c["Name"].lstrip("/") for c in source if not c["State"]["Running"]}
    require(set(running) == ALLOW and stopped == EXCLUDED, "original state/allowlist mismatch")
    require(raw["network_inspect"]["returncode"] == 0, "network inspect failed")
    network_raw = json.loads(raw["network_inspect"]["stdout"])
    network_names = {n for c in running.values() for n in c["NetworkSettings"]["Networks"]}
    networks = {}
    for n in network_raw:
        if n["Name"] not in network_names:
            continue
        networks[n["Name"]] = {"Builtin": n["Name"] == "bridge", "Create": {k: copy.deepcopy(n[k]) for k in NETWORK_KEYS if k in n},
                                "OriginalLabels": copy.deepcopy(n.get("Labels") or {})}
    containers = {}
    volumes, binds = {}, {}
    image_users = {}
    checks = []
    for name, c in running.items():
        cfg, host = copy.deepcopy(c["Config"]), copy.deepcopy(c["HostConfig"])
        original_labels = cfg.pop("Labels", {}) or {}
        cfg["Labels"] = {k: v for k, v in original_labels.items() if not k.startswith("com.docker.compose.")}
        cfg["Image"] = c["Image"]
        changes = ["Image: tag -> exact image ID", "compose labels -> private provenance only"]
        if cfg.get("Hostname") == c["Id"][:12]:
            cfg.pop("Hostname")
            changes.append("autogenerated old container hostname omitted")
        for key in ("Dns", "DnsOptions", "DnsSearch", "ContainerIDFile"):
            require(not host.get(key), "nonempty nonportable DNS/container-ID field needs review")
            host.pop(key, None)
        for key in ("IpcMode", "PidMode", "UTSMode", "NetworkMode"):
            require(not str(host.get(key, "")).startswith("container:"), "old container namespace dependency")
        eps = {n: {k: copy.deepcopy(ep[k]) for k in ENDPOINT_KEYS if k in ep}
               for n, ep in c["NetworkSettings"]["Networks"].items()}
        cfg.update({"HostConfig": host, "NetworkingConfig": {"EndpointsConfig": eps}})
        containers[name] = {"Create": cfg, "OriginalLabels": original_labels,
                            "Mounts": copy.deepcopy(c["Mounts"]), "ControlledDifferences": changes}
        image_users.setdefault(c["Image"], []).append(name)
        for mount in c["Mounts"]:
            group = volumes if mount["Type"] == "volume" else binds
            require(mount["Type"] in {"volume", "bind"}, "unhandled mount type")
            key = mount["Name"] if mount["Type"] == "volume" else mount["Source"]
            group.setdefault(key, {"Source": mount["Source"], "Consumers": []})["Consumers"].append(
                {"Container": name, "Destination": mount["Destination"], "Mode": mount["Mode"], "RW": mount["RW"], "Propagation": mount["Propagation"]})
        # Compare exact in-memory objects. Never log env/command contents or secret hashes.
        preserved_cfg = set(c["Config"]) - {"Image", "Hostname", "Labels"}
        require(all(cfg[k] == c["Config"][k] for k in preserved_cfg), "Config preservation failure")
        preserved_host = set(c["HostConfig"]) - {"Dns", "DnsOptions", "DnsSearch", "ContainerIDFile"}
        require(all(host[k] == c["HostConfig"][k] for k in preserved_host), "HostConfig preservation failure")
        require(all(eps[n][k] == ep[k] for n, ep in c["NetworkSettings"]["Networks"].items() for k in ENDPOINT_KEYS if k in ep), "endpoint preservation failure")
        checks.append({"Name": name, "EnvCommandUserWorkdirHealthcheck": "exact", "HostConfigResourcesMounts": "exact", "NetworkAliasesIPAMDriverOpts": "exact", "ImageID": c["Image"],
                       "OriginalRestart": host["RestartPolicy"], "FinalPortBindings": host.get("PortBindings"), "StagingPortBindings": stage_bindings(host.get("PortBindings"))})
    m = {"Schema": 1, "TargetHostname": TARGET, "SourceInspectSHA256": hashlib.sha256(Path(args.source).read_bytes()).hexdigest(),
         "SourceNetworkSnapshotSHA256": digest(network_raw), "Containers": containers, "Networks": networks,
         "ImageIDs": sorted(image_users), "Excluded": sorted(EXCLUDED), "Exports": {"Volumes": volumes, "Binds": binds},
         "AnticipatedPatch": {"EnabledByDefault": False, "EnvAllowlist": MEDIA_PATCH,
                              "MinioLoopbackBinding": {"9000/tcp": [{"HostIp": "127.0.0.1", "HostPort": "9000"}]},
                              "ApprovalRequired": "ControlledMediaPatchApproved"}}
    validate_manifest(m)
    out = Path(args.output)
    require(not out.is_symlink(), "output directory may not be a symlink")
    out.mkdir(mode=0o700, parents=True, exist_ok=True)
    out.chmod(0o700)
    private_write(out / "runtime-manifest.private.json", m)
    private_write(out / "networks-source.private.json", network_raw)
    private_write(out / "exports.metadata.json", {"ImageIDs": image_users, **m["Exports"]})
    private_write(out / "preservation-checks.private.json", checks)
    private_write(out / "runtime_replay.py", Path(__file__).read_text(), False)
    gate = {"TargetHostname": TARGET, "ManifestSHA256": digest(m), "RestoredVolumes": [], "RestoredBinds": [],
            "PublicIngressDisabled": False, "ReceiversDisabled": False, "BackgroundWritersDisabled": False,
            "NoOldDatabaseRoutes": False, "IsolatedWebApproved": False, "PitchSchemaAtHeadVerified": False,
            "PitchAlembicNoChangeApproved": False, "OldWritersFenced": False, "FinalDataVerified": False,
            "VPNCutoverOwnershipConfirmed": False, "IngressCutoverApproved": False, "ControlledMediaPatchApproved": False}
    private_write(out / "gates.TEMPLATE.private.json", gate)
    private_write(out / "media-env-overrides.TEMPLATE.private.json", {name: {key: pair[1] for key, pair in pairs.items()} for name, pairs in MEDIA_PATCH.items()})
    private_write(out / "dry-run-diff-report.md", report(m, checks), False)
    print("Prepared private manifest/operator/report: 17 containers, 16 immutable images, 3 excluded, 8 volumes, 4 binds, 7 networks. No Docker connection.")


def report(m, checks):
    lines = ["# Runtime replay dry-run diff (metadata only)", "", "Validation: PASS — 20 source inspect / 17 running / 16 immutable images / 3 excluded; 8 volumes / 4 binds / 7 networks.",
             "", "Config.Env (literal ordered strings), Entrypoint, Cmd, User, WorkingDir, Healthcheck, ExposedPorts, Volumes and other Config fields match source exactly, except Image pinning, autogenerated hostname and legacy Compose ownership labels.",
             "HostConfig is exact including Runtime, DeviceRequests/GPU, ReadonlyRootfs, ShmSize, Ulimits, CapAdd/CapDrop, security, resources, Binds/Mounts, logs and final restart/ports. Only empty DNS/ContainerIDFile fields are omitted.",
             "Endpoints preserve exact network membership, aliases, IPAMConfig, Links, DriverOpts and GwPriority. Dynamic old IDs/IP/MAC/sandbox/DNSNames are not replayed. Network driver, actual subnets/gateways, Internal, IPAM and options are preserved. Built-in bridge must already match; no silent replacement.",
             "", "Staging controlled differences: original 10.8.0.3 bindings omitted; original loopback bindings retained; restart=no for every staged container. No wildcard/public expansion, dummy VPN, old VPN activation, cron/Pitch worker/receiver startup. Activation recreation restores ALL original bindings/restart, including original restart=no.",
             "Stage start allowlist is DB/MinIO/GPU-web only. Explicit --allow-isolated-web plus affirmative gates can additionally start listed web/platform/APIs. Pitch API further requires schema=head verification and explicit approval that original alembic entrypoint makes no schema change. No command override is used.",
             "", "Excluded (never created, started or dependency-expanded): " + ", ".join(sorted(EXCLUDED)), "", "| Container | Config/env/command | Host/resources/mounts | aliases | restart final | staging VPN bindings removed |", "| --- | --- | --- | --- | --- | --- |"]
    for c in checks:
        original = sum(len(x or []) for x in (c["FinalPortBindings"] or {}).values())
        staged = sum(len(x or []) for x in c["StagingPortBindings"].values())
        lines.append(f"| {c['Name']} | exact | exact | exact | {c['OriginalRestart']['Name']} | {original-staged} |")
    lines += ["", "## Exact exports", "", "Volumes (data must be restored consistently before operator can create/start; operator never auto-creates blank volumes):"]
    lines += ["- " + name + " — " + meta["Source"] for name, meta in sorted(m["Exports"]["Volumes"].items())]
    lines += ["", "Bind paths (same paths, owner/mode retained by transfer):"] + ["- " + p for p in sorted(m["Exports"]["Binds"])]
    lines += ["", "Immutable images:"] + ["- " + i for i in m["ImageIDs"]]
    lines += ["", "## Operator / maintenance", "", "Use python3 runtime_replay.py replay --manifest runtime-manifest.private.json (offline dry-run; no socket access); invoking runtime_replay.py with no arguments also dry-runs. --phase staging or --phase activate still dry-runs unless --apply is also given. Select explicit --container names; no implicit all/dependencies. --action create/start/recreate-final only. recreate-final is activation-only and is the required transition from staged loopback/restart=no to original VPN bindings/restart. It replaces only this operator's labeled, source-matching staged container; data volumes are never removed.",
              "", "All writes require local hostname AND Docker daemon Name 10-60-162-188, local unix socket only, exact image/volume/bind/network checks, and a mode0600 gate file tied to this manifest. Copy gates.TEMPLATE.private.json to a separate reviewed gate file; every placeholder is fail-closed. Never set a declaration true until its condition has been independently verified. Staging requires no 10.8.0.3 host address and ingress/receiver/background writers disabled. Application tests must avoid real accounts and paid/model requests. Activation requires old writers fenced, final data verified, VPN ownership transferred, ingress cutover approved; Pitch API has its own schema gate.",
              "", "The maintenance entry point is this private Engine API manifest/operator, not old Compose. Old com.docker.compose.* labels are retained only as OriginalLabels provenance, removed from active ownership, and replaced by operator phase/spec labels. For the three exact source images that embed project/service/version defaults, payload retains those three keys with explicit empty values so Docker cannot inherit old Compose ownership; full Labels and operator/spec comparison stays strict. Historical Compose paths/overlays may be unavailable; do not run the old compose up. Approved runtime edits must update/review this manifest and gates, then recreate the selected allowlisted container.",
              "", "Anticipated media patch is OFF by default: --env-overrides accepts only web + Go-admin KATRAIN_S3_PUBLIC_BASE_URL old preview URL -> https://modelstella.com/media and unified admin SMARTBOX_ADMIN_MEDIA_ORIGINS old preview origin -> https://modelstella.com. --allow-minio-loopback adds only 127.0.0.1:9000->9000/tcp; authoritative MinIO inspect already has VPN 10.8.0.3:9000 and loopback 127.0.0.1:9001, both preserved in final phase (older inventory prose omitted them). Any other env key/value/container or port change is refused. Explicit patch application additionally requires ControlledMediaPatchApproved=true and gates ManifestSHA256 matching the effective (patched) manifest; base env/port preservation otherwise remains exact. No bucket policy is changed. New-host Nginx /media proxy is outside this container operator and must be separately reviewed/applied by controller.",
              "", "This artifact was generated and locally dry-run/validated only. No target/old-host connection, container create/start, PostgreSQL operation, model call, data transfer or deployment was performed.", ""]
    return "\n".join(lines)


class UnixHTTP(http.client.HTTPConnection):
    def connect(self):
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.settimeout(60)
        self.sock.connect("/var/run/docker.sock")


class Engine:
    def __init__(self):
        require(socket.gethostname() == TARGET, "refusing write: local hostname is not approved new host")
        require(not os.environ.get("DOCKER_HOST") and not os.environ.get("DOCKER_CONTEXT"), "unset Docker remote/context environment")
        require(self.call("GET", "/info", versioned=False)["Name"] == TARGET, "refusing: Docker daemon identity mismatch")
        version = self.call("GET", "/version", versioned=False)
        require(tuple(map(int, version["ApiVersion"].split("."))) >= (1, 54), "Docker API >=1.54 required for exact replay")

    def call(self, method, path, obj=None, absent=False, versioned=True):
        c = UnixHTTP("localhost", timeout=60)
        data = canonical(obj) if obj is not None else None
        try:
            c.request(method, ("/v1.54" if versioned else "") + path, body=data,
                      headers={"Content-Type": "application/json"} if data is not None else {})
            r = c.getresponse()
            body = r.read()
            if absent and r.status == 404:
                return None
            # Docker error bodies can include secret configuration; never print them.
            idempotent_state = method == "POST" and path.split("?")[0].endswith(("/start", "/stop")) and r.status == 304
            require(200 <= r.status < 300 or idempotent_state, "Docker request refused: " + method + " " + path.split("?")[0] + " HTTP " + str(r.status))
            return json.loads(body) if body else None
        finally:
            c.close()


def network_equal(actual, wanted):
    return all(actual.get(k) == v for k, v in wanted.items())


def require_gates(args, m, selected, changes):
    require(args.gate_file, "--apply requires reviewed --gate-file")
    g = private_read(args.gate_file)
    require(g.get("TargetHostname") == TARGET and g.get("ManifestSHA256") == digest(m), "gate target/manifest mismatch")
    required = ["PublicIngressDisabled", "ReceiversDisabled", "BackgroundWritersDisabled", "NoOldDatabaseRoutes"] if args.phase == "staging" else ["OldWritersFenced", "FinalDataVerified", "VPNCutoverOwnershipConfirmed", "IngressCutoverApproved"]
    if changes:
        required.append("ControlledMediaPatchApproved")
    if args.phase == "staging" and args.action == "start" and set(selected) & ISOLATED_WEB:
        required.append("IsolatedWebApproved")
    if args.action == "start" and "pitch-booking-api-1" in selected:
        required += ["PitchSchemaAtHeadVerified", "PitchAlembicNoChangeApproved"]
    for k in required:
        require(g.get(k) is True, "gate not satisfied: " + k)
    for name in selected:
        for mount in m["Containers"][name]["Mounts"]:
            k, value = ("RestoredVolumes", mount["Name"]) if mount["Type"] == "volume" else ("RestoredBinds", mount["Source"])
            require(value in g.get(k, []), "mount restoration attestation missing: " + value)
    result = subprocess.run(["ip", "-j", "address", "show"], check=True, capture_output=True, text=True)
    addresses = json.loads(result.stdout)
    vpn_present = any(a.get("local") == "10.8.0.3" for i in addresses for a in i.get("addr_info", []))
    if args.phase == "staging":
        require(not vpn_present, "old VPN identity is present during staging")
    elif any(b.get("HostIp") == "10.8.0.3" for name in selected
             for values in (m["Containers"][name]["Create"]["HostConfig"].get("PortBindings") or {}).values()
             for b in values or []):
        require(vpn_present, "original VPN binding address missing; refusing before replacing any staged container")


def verify_existing(actual, expected, allowed_phases, record):
    labels = actual["Config"].get("Labels") or {}
    require(labels.get(LABEL) == "2026-10-26" and labels.get(LABEL + ".phase") in allowed_phases,
            "existing container is not owned by this operator/phase")
    prior = payload(record, labels[LABEL + ".phase"])
    require(labels.get(LABEL + ".spec") == prior["Labels"][LABEL + ".spec"], "existing operator spec label mismatch")
    require(actual["Image"] == prior["Image"], "existing immutable image mismatch")
    for k, v in prior.items():
        if k not in {"HostConfig", "NetworkingConfig"}:
            require(actual["Config"].get(k) == v, "existing Config drift: " + k)
    for k, v in prior["HostConfig"].items():
        actual_value = actual["HostConfig"].get(k)
        matches = actual_value == v
        if k == "OomKillDisable":
            # Docker 29 may report unset (OOM killer enabled) as false after create.
            # Compare only here; preserve literal source/payload and spec fingerprint.
            matches = (actual_value is True and v is True) or (
                (actual_value is None or actual_value is False) and (v is None or v is False)
            )
        require(matches, "existing HostConfig drift: " + k)
    require(set(actual["NetworkSettings"]["Networks"]) == set(prior["NetworkingConfig"]["EndpointsConfig"]), "existing network membership drift")
    for net, ep in prior["NetworkingConfig"]["EndpointsConfig"].items():
        for k, v in ep.items():
            require(actual["NetworkSettings"]["Networks"][net].get(k) == v, "existing endpoint drift: " + k)


def replay(args):
    m = private_read(args.manifest)
    validate_manifest(m)
    m, changes = controlled_patch(m, args)
    validate_manifest(m)
    selected = args.container or sorted(ALLOW)
    require(len(set(selected)) == len(selected) and set(selected) <= ALLOW, "unknown/duplicate container; excluded tasks can never be selected")
    require(args.action != "recreate-final" or args.phase == "activate", "recreate-final is activation-only")
    if args.phase == "staging" and args.action == "start":
        allowed = STAGE_START | (ISOLATED_WEB if args.allow_isolated_web else set())
        require(set(selected) <= allowed, "staging start denied (cron/worker/receiver or missing --allow-isolated-web)")
    phase = args.phase if args.phase != "dry-run" else "staging"
    if changes:
        print(json.dumps({"ControlledPatch": changes, "EffectiveManifestSHA256": digest(m), "DefaultEnabled": False}, sort_keys=True))
    # No private payload, env values or commands are ever printed.
    for name in selected:
        p = payload(m["Containers"][name], phase)
        print(json.dumps({"Container": name, "Phase": args.phase, "Action": args.action, "ImageID": p["Image"],
                          "Restart": p["HostConfig"]["RestartPolicy"]["Name"], "PortBindings": p["HostConfig"].get("PortBindings"),
                          "Networks": sorted(p["NetworkingConfig"]["EndpointsConfig"]), "Apply": bool(args.apply)}, sort_keys=True))
    if not args.apply:
        print("OFFLINE DRY RUN: no socket/host access, create/start/stop/remove/network/data operations.")
        return
    require(args.phase in {"staging", "activate"}, "--apply requires explicit --phase staging|activate")
    require(args.container, "--apply requires explicit --container selection (no implicit all)")
    engine = Engine()
    require_gates(args, m, selected, changes)
    needed_networks = {n for name in selected for n in m["Containers"][name]["Create"]["NetworkingConfig"]["EndpointsConfig"]}
    missing_networks = []
    # Complete every read-only precondition before any mutation.
    for net in sorted(needed_networks):
        rec = m["Networks"][net]
        actual = engine.call("GET", "/networks/" + urllib.parse.quote(net, safe=""), absent=True)
        if actual is None:
            require(not rec["Builtin"], "required built-in network missing")
            missing_networks.append(net)
        else:
            require(network_equal(actual, rec["Create"]), "existing network differs: " + net)
    for name in selected:
        rec = m["Containers"][name]
        p = payload(rec, args.phase)
        require(engine.call("GET", "/images/" + p["Image"] + "/json")["Id"] == p["Image"], "exact image missing")
        for mount in rec["Mounts"]:
            if mount["Type"] == "volume":
                volume = engine.call("GET", "/volumes/" + urllib.parse.quote(mount["Name"], safe=""))
                require(volume["Name"] == mount["Name"] and volume["Driver"] == "local" and volume["Mountpoint"] == mount["Source"], "volume identity/path mismatch")
            else:
                require(Path(mount["Source"]).exists(), "bind source missing: " + mount["Source"])
        actual = engine.call("GET", "/containers/" + name + "/json", absent=True)
        if args.action == "create":
            require(actual is None, "container already exists; use explicit recreate-final after review")
        else:
            require(actual is not None, "container must exist before start/recreate-final")
            verify_existing(actual, p, {args.phase} if args.action == "start" else {"staging"}, rec)
    for net in missing_networks:
        body = copy.deepcopy(m["Networks"][net]["Create"])
        body.update({"Name": net, "Labels": {LABEL: "2026-10-26"}})
        engine.call("POST", "/networks/create", body)
    for name in selected:
        p = payload(m["Containers"][name], args.phase)
        if args.action == "recreate-final":
            engine.call("POST", "/containers/" + name + "/stop?t=30")
            engine.call("DELETE", "/containers/" + name + "?v=false&force=false")
        if args.action in {"create", "recreate-final"}:
            engine.call("POST", "/containers/create?name=" + name, p)
        else:
            engine.call("POST", "/containers/" + name + "/start")
        print("Applied " + args.action + ": " + name)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command")
    prep = sub.add_parser("prepare", help="local private files only; no Docker connection")
    prep.add_argument("--source", default=str(ROOT / "docker-containers.private.json"))
    prep.add_argument("--inventory", default=str(ROOT / "runtime-inventory/old-runtime.private.json"))
    prep.add_argument("--output", default=str(ROOT / "runtime-replay"))
    run = sub.add_parser("replay", help="offline dry-run by default")
    run.add_argument("--manifest", default=str(Path(__file__).parent / "runtime-manifest.private.json"))
    run.add_argument("--phase", choices=("dry-run", "staging", "activate"), default="dry-run")
    run.add_argument("--action", choices=("create", "start", "recreate-final"), default="create")
    run.add_argument("--container", action="append")
    run.add_argument("--apply", action="store_true")
    run.add_argument("--allow-isolated-web", action="store_true")
    run.add_argument("--gate-file")
    run.add_argument("--env-overrides", help="private JSON; only exact anticipated media env patch accepted")
    run.add_argument("--allow-minio-loopback", action="store_true", help="explicit anticipated 127.0.0.1:9000 MinIO binding")
    args = parser.parse_args(sys.argv[1:] or ["replay"])
    require(args.command is not None, "choose prepare or replay (replay is offline dry-run by default)")
    if args.command == "prepare":
        prepare(args)
    else:
        replay(args)


if __name__ == "__main__":
    try:
        main()
    except Refused as exc:
        print("REFUSED: " + str(exc), file=sys.stderr)
        sys.exit(2)
    except Exception as exc:
        # Unhandled exceptions may include private data in messages; type only.
        print("FAILED CLOSED: " + type(exc).__name__ + " (private details suppressed)", file=sys.stderr)
        sys.exit(3)
