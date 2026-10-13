"""Prepare a small, unsigned batch-592 transport from root-reviewed local files only."""

import gzip
import hashlib
import io
import json
import tarfile
from pathlib import Path

from katrain.web.kifu.name_candidates import validate_bundle
from katrain.web.kifu.name_evidence import registry_sha256


D = Path(__file__).resolve().parent
FILES = []
manifest = {}


def read(path):
    raw = path.read_bytes()
    return json.loads(gzip.decompress(raw) if path.suffix == ".gz" else raw)


def save(name, raw):
    path = D / name
    path.write_bytes(raw)
    FILES.append(path)
    return hashlib.sha256(raw).hexdigest()


def source_files(value):
    if isinstance(value, dict):
        for key, item in value.items():
            if key in {"body_path", "body_file", "content_file"} and isinstance(item, str):
                path = Path(item)
                if not path.is_absolute() and not path.exists():
                    path = D / path.name
                if not path.is_file():
                    raise ValueError(f"source capture missing: {item}")
            else:
                source_files(item)
    elif isinstance(value, list):
        for item in value:
            source_files(item)


for env in ("PROD", "TEST"):
    fresh = read(D / f"{env}-root-approved-fresh.json.gz")
    bundle = read(D / f"{env}-post591-final20-unsigned-bundle.json.gz")
    evidence = read(D / f"{env}-post591-final20-unsigned-evidence.json.gz")
    registry = fresh["registry"]
    inventory = fresh["inventory"]
    assert fresh["environment"] == env and fresh["preceding_batch_applied"] == 591
    assert len(bundle["candidates"]) == len(evidence) == 20
    assert bundle["registry_sha256"] == registry_sha256(registry)
    assert bundle["inventory_sha256"] == inventory["sha256"]
    assert {kind: sum(x["decision_kind"] == kind for x in bundle["candidates"])
            for kind in ("conventional", "generated")} == {"conventional": 18, "generated": 2}
    assert {lang: sum(x["lang"] == lang for x in bundle["candidates"])
            for lang in ("ko", "tw", "en")} == {"ko": 18, "tw": 1, "en": 1}
    assert len({x["owner"]["id"] for x in bundle["candidates"]}) == 20
    source_files(evidence)
    report = validate_bundle(bundle, registry, inventory, evidence,
                             approved_name_snapshot=fresh["approved_name_snapshot"])
    assert report["ready"] and report["write_ready"] and report["approved"] == 20
    manifest[env] = {
        "bundle_sha256": registry_sha256(bundle),
        "bundle_file_sha256": save(f"{env}-final20-bundle.json.gz", (D / f"{env}-post591-final20-unsigned-bundle.json.gz").read_bytes()),
        "inventory_file_sha256": save(f"{env}-final20-inventory.json.gz", gzip.compress(json.dumps(inventory, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(), mtime=0)),
        "evidence_file_sha256": save(f"{env}-final20-evidence.jsonl", ("\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) for row in evidence) + "\n").encode()),
        "registry_file_sha256": save(f"{env}-final20-registry.json", json.dumps(registry, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()),
        "source_review_file_sha256": fresh["source_review_file_sha256"],
        "root_fresh_file_sha256": hashlib.sha256((D / f"{env}-root-approved-fresh.json.gz").read_bytes()).hexdigest(),
        "inventory_sha256": inventory["sha256"],
        "registry_sha256": bundle["registry_sha256"],
    }

manifest["required_image_ids"] = {
    "PROD": "sha256:6ffe9b6dad44ae280dc756d8468f1695337ca786541976413b515e614ebab3c5",
    "TEST": "sha256:61ffcb3f86e9733b63eb7b25c2e34005e651e5ab1da4e7ad353d64f5815df1f1",
}
manifest["helper_sha256"] = {name: hashlib.sha256((D / name).read_bytes()).hexdigest()
                              for name in ("final20-inner.py", "final20-run.py")}
save("final20-execution-proposed-manifest.json", json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2).encode())
with tarfile.open(D / "final20-execution-transport.tar.gz", "w:gz") as tar:
    for path in FILES + [D / "final20-inner.py", D / "final20-run.py"]:
        tar.add(path, arcname=path.name)
print(json.dumps({"manifest": "final20-execution-proposed-manifest.json",
                  "transport": "final20-execution-transport.tar.gz",
                  "bundle_sha256": {env: manifest[env]["bundle_sha256"] for env in ("PROD", "TEST")}},
                 ensure_ascii=False, sort_keys=True))
