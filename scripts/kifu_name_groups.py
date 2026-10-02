"""Group a full read-only kifu inventory into pending event review manifests."""

import argparse
import gzip
import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from katrain.web.kifu.name_structure import build_event_group_manifest


def _open_json(path: Path, mode: str):
    opener = gzip.open if path.suffix == ".gz" else open
    return opener(path, mode + "t", encoding="utf-8")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--expected-inventory-artifact-sha256",
                        help="independently pinned canonical JSON SHA-256; required for v3 inventories")
    args = parser.parse_args(argv)
    with _open_json(args.inventory, "r") as stream:
        manifest = build_event_group_manifest(
            json.load(stream), expected_artifact_sha256=args.expected_inventory_artifact_sha256,
        )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=args.output.parent, prefix=".kifu-groups-", delete=False) as stream:
            temporary = Path(stream.name)
        opener = gzip.open if args.output.suffix == ".gz" else open
        with opener(temporary, "wt", encoding="utf-8") as stream:
            json.dump(manifest, stream, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        os.replace(temporary, args.output)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()
    print(json.dumps({key: manifest[key] for key in ("inventory_sha256", "group_count", "sha256")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
