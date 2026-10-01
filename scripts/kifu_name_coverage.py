"""Audit all eleven kifu display languages against a pinned, read-only inventory."""

import argparse
import gzip
import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import create_engine

from katrain.web.kifu.name_coverage import coverage_report


def _load(path: Path) -> dict:
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as handle:
        return json.load(handle)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--inventory", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--missing-output", required=True, type=Path)
    args = parser.parse_args(argv)
    if args.output.resolve() == args.missing_output.resolve():
        parser.error("output and missing-output must be different paths")
    inventory = _load(args.inventory)
    engine = create_engine(args.database_url)
    report_tmp = None
    missing_tmp = None
    try:
        with tempfile.NamedTemporaryFile(dir=args.output.parent, prefix=".kifu-coverage-", delete=False) as handle:
            report_tmp = Path(handle.name)
        with tempfile.NamedTemporaryFile(
            dir=args.missing_output.parent, prefix=".kifu-missing-", delete=False
        ) as handle:
            missing_tmp = Path(handle.name)
        with gzip.open(missing_tmp, "wt", encoding="utf-8") as missing_handle:
            report = coverage_report(
                engine, inventory,
                missing_sink=lambda gap: missing_handle.write(json.dumps(gap, ensure_ascii=False) + "\n"),
            )
        report_tmp.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        os.replace(missing_tmp, args.missing_output)
        os.replace(report_tmp, args.output)
        print(json.dumps({"albums": report["albums"], "complete": report["complete"],
                          "missing": {lang: values["missing"] for lang, values in report["languages"].items()}},
                         ensure_ascii=False))
        return 0 if report["complete"] else 2
    finally:
        engine.dispose()
        for path in (report_tmp, missing_tmp):
            if path is not None and path.exists():
                path.unlink()


if __name__ == "__main__":
    raise SystemExit(main())
