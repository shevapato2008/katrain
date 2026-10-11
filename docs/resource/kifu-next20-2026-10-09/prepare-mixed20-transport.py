"""Create unsigned CLI transport files for an already validated mixed20 bundle."""

import gzip
import hashlib
import json
from pathlib import Path

from katrain.web.kifu.name_candidates import canonical_sha256
from katrain.web.kifu.name_evidence import registry_sha256


D = Path(__file__).parent


def read(path):
    with gzip.open(path, "rt") if str(path).endswith(".gz") else open(path) as stream:
        return json.load(stream)


def compact(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def write_new(path, content):
    if path.exists():
        raise FileExistsError(path)
    path.write_bytes(content)


def prepare(environment):
    input_path = D / f"{environment}-mixed20-approved-input.json.gz"
    bundle_path = D / f"{environment}-mixed20-unsigned-bundle.json.gz"
    evidence_path = D / f"{environment}-mixed20-unsigned-evidence.json.gz"
    summary_path = D / f"{environment}-mixed20-unsigned-summary.json"
    data, bundle, evidence, summary = map(read, (input_path, bundle_path, evidence_path, summary_path))
    assert data["status"] == "root_approved_fresh_post590_pages"
    assert canonical_sha256(bundle) == summary["bundle_sha256"]
    assert canonical_sha256(evidence) == summary["evidence_sha256"]
    assert summary["validation"]["ready"] and summary["validation"]["write_ready"]
    assert summary["validation"]["approved"] == len(bundle["candidates"]) == len(evidence) == 20
    assert sum(row.get("evidence_kind") == "primary_orthographic" for row in evidence) == 17
    assert bundle["registry_sha256"] == registry_sha256(data["registry"])
    assert bundle["inventory_sha256"] == data["inventory"]["sha256"]
    assert bundle["catalog_sha256"] == data["catalog_sha256"]
    registry_path = D / f"{environment}-mixed20-source-registry.json"
    inventory_path = D / f"{environment}-mixed20-inventory.json.gz"
    snapshot_path = D / f"{environment}-mixed20-approved-name-snapshot.json.gz"
    jsonl_path = D / f"{environment}-mixed20-evidence.jsonl"
    write_new(registry_path, json.dumps(data["registry"], ensure_ascii=False, sort_keys=True, indent=2).encode() + b"\n")
    write_new(inventory_path, gzip.compress(compact(data["inventory"]), mtime=0))
    write_new(snapshot_path, gzip.compress(compact(data["approved_name_snapshot"]), mtime=0))
    write_new(jsonl_path, b"\n".join(compact(row) for row in evidence) + b"\n")
    names = [input_path.name, bundle_path.name, evidence_path.name, summary_path.name,
             registry_path.name, inventory_path.name, snapshot_path.name, jsonl_path.name,
             f"{environment}-mixed20-fresh-post590-pages.json.gz"]
    manifest = {
        "environment": environment,
        "status": "unsigned_transport_ready_outer_execution_approval_pending",
        "bundle_sha256": summary["bundle_sha256"],
        "approved": 20,
        "source_records": 20,
        "file_sha256": {name: hashlib.sha256((D / name).read_bytes()).hexdigest() for name in names},
    }
    manifest_path = D / f"{environment}-mixed20-transport-file-sha256.json"
    write_new(manifest_path, json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2).encode() + b"\n")
    print(environment, "transport ready", manifest["bundle_sha256"])


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("environment", choices=("TEST", "PROD"))
    args = parser.parse_args()
    prepare(args.environment)
