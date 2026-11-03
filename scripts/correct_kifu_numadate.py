"""Prepare, verify or apply the fixed PROD Numadate canonical correction."""

import argparse
import json
import os
import stat
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sqlalchemy import create_engine
from katrain.web.kifu import numadate_canonical_correction as correction
from katrain.web.kifu.source_rank_normalization import require
from scripts.repair_historical_kifu_ranks import _path, _open_private, _write_handle


def _read(path):
    fd = os.open(_path(path), os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as handle:
        info = os.fstat(handle.fileno())
        require(
            stat.S_ISREG(info.st_mode) and 0 < info.st_size <= correction.MAX_AUTHORITY_BYTES,
            "correction private artifact resource limit",
        )
        raw = handle.read(info.st_size + 1)
        require(
            len(raw) == info.st_size and os.fstat(handle.fileno()).st_size == info.st_size,
            "correction private artifact changed while reading",
        )
    return json.loads(raw)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "verify", "apply"))
    parser.add_argument("--inputs")
    parser.add_argument("--plan")
    parser.add_argument("--expected-sha256")
    parser.add_argument("--output")
    args = parser.parse_args(argv)
    engine = None
    try:
        from katrain.web.core.config import settings

        engine = create_engine(settings.DATABASE_URL, echo=False, hide_parameters=True)
        require(
            engine.dialect.name == "postgresql" and engine.url.database == correction.PROD_DATABASE,
            "canonical correction CLI requires the configured PROD PostgreSQL database",
        )
        if args.action == "prepare":
            require(
                args.inputs and args.output and not args.plan and not args.expected_sha256,
                "prepare requires --inputs and --output",
            )
            inputs = _read(args.inputs)
            require(
                set(inputs) == {"matched_at", "identity_review", "name_package", "original_package"},
                "correction input fields invalid",
            )
            plan = correction.prepare_correction(engine, **inputs)
            with _open_private(args.output) as handle:
                _write_handle(handle, plan)
            print(
                json.dumps(
                    {
                        "status": "prepared_requires_independent_final_approval",
                        "content_sha256": plan["content_sha256"],
                        "mutation_counts": plan["approved_counts"],
                    },
                    sort_keys=True,
                )
            )
        else:
            require(
                args.plan and args.expected_sha256 and not args.inputs and not args.output,
                "verify/apply requires --plan and --expected-sha256",
            )
            plan = _read(args.plan)
            correction._validate_plan(plan)
            require(correction.digest(plan) == args.expected_sha256, "reviewed plan SHA mismatch")
            if args.action == "apply":
                result = correction.apply_correction(engine, plan, expected_sha256=args.expected_sha256)
            else:
                with correction._readonly(engine) as conn:
                    batch = conn.execute(
                        correction.select(correction.m.KifuNameBatch.id).where(
                            correction.m.KifuNameBatch.bundle_sha256 == args.expected_sha256
                        )
                    ).scalar_one_or_none()
                    require(batch is not None, "correction applied batch missing")
                    result = correction.verify_correction(conn, batch)["receipt"]
            print(json.dumps(result, sort_keys=True))
        return 0
    except Exception as exc:
        from katrain.web.kifu.search_sync import SearchIndexPending

        if isinstance(exc, SearchIndexPending):
            child_sha = correction.digest(plan["name_package"]["bundle"])
            print(
                json.dumps(
                    {
                        "status": "search_pending",
                        "plan_sha256": args.expected_sha256,
                        "operation_type": "name_apply",
                        "operation_ref": {"bundle_sha256": child_sha},
                        "recovery": "search_sync.recover_pending",
                    }
                ),
                file=sys.stderr,
            )
            return 3
        # SQLAlchemy errors can contain statement parameters or connection URLs.
        print("canonical correction refused; exact scope, approval or authority validation failed", file=sys.stderr)
        return 2
    finally:
        if engine is not None:
            engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
