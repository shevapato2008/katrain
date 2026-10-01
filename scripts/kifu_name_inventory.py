"""Write a read-only kifu name inventory from a database snapshot."""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import create_engine

from katrain.web.kifu.name_inventory import build_inventory


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    engine = create_engine(args.database_url)
    try:
        result = build_inventory(engine)
    finally:
        engine.dispose()
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                key: result[key]
                for key in ("database_identifier", "snapshot_time", "counts", "distinct_values", "sha256")
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
