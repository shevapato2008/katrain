"""Explicit small-batch admission for professional kifu analysis.

Dry run by default. Full-corpus admission is intentionally unavailable.
"""

import argparse
import hashlib
import json
from pathlib import Path

from sqlalchemy.exc import IntegrityError

from katrain.cron.config import KATAGO_EXPECTED_MODEL_SHA256
from katrain.cron.db import SessionLocal
from katrain.cron.models import KifuAlbumDB, KifuAnalysisJobDB, KifuAnalysisMoveDB
from katrain.cron.sgf import parse_game
from katrain.cron.kifu_parameters import ParameterError, resolve_parameters, validate_parameters


def load_evidence(path):
    """Read reviewed assertions only; no built-in guesses or automatic verification."""
    if not path:
        return {}
    entries = json.loads(Path(path).read_text())
    if not isinstance(entries, list) or any(not isinstance(e, dict) or not e.get("sgf_sha256") for e in entries):
        raise ValueError("Evidence file must be a JSON list of exact-SGF assertions")
    result = {e["sgf_sha256"]: e for e in entries}
    if len(result) != len(entries):
        raise ValueError("Duplicate SGF evidence assertions")
    return result


def admit_album(db, album, model_sha256, *, evidence=None, reanalyze=False, apply=False):
    """Keep the existing job key; replacing parameters atomically removes ALL positions.

    Stop workers and back up affected jobs/moves before --reanalyze --apply.
    No operation modifies original album metadata/SGF or personal reports.
    """
    if apply:
        album = db.query(KifuAlbumDB).filter_by(id=album.id).populate_existing().with_for_update().one()
    if album.duplicate_of_id is not None:
        raise ParameterError("invalid_album", "Admission requires a canonical album")
    parsed = parse_game(album.sgf_content)
    if parsed.dropped_midgame_setup or parsed.invalid_moves or not parsed.moves:
        raise ParameterError("invalid_sgf", "SGF cannot be replayed faithfully")
    sha = hashlib.sha256(album.sgf_content.encode("utf-8")).hexdigest()
    identity = dict(album_id=album.id, sgf_sha256=sha, model_sha256=model_sha256, requested_visits=2000)
    query = db.query(KifuAnalysisJobDB).filter_by(**identity)
    existing = (query.populate_existing().with_for_update() if apply else query).first()
    parameters = None
    if existing and evidence is None:
        try:
            parameters = validate_parameters(album.sgf_content, existing.analysis_parameters)
        except ParameterError:
            pass
    parameters = parameters or resolve_parameters(album.sgf_content, evidence)
    if existing and not reanalyze:
        validate_parameters(album.sgf_content, existing.analysis_parameters)
        if existing.analysis_parameters != parameters:
            raise ParameterError("parameter_mismatch", "Existing job parameters differ; use --reanalyze after backup")
        stale = (
            db.query(KifuAnalysisMoveDB)
            .filter(
                KifuAnalysisMoveDB.job_id == existing.id,
                (KifuAnalysisMoveDB.parameter_sha256.is_(None))
                | (KifuAnalysisMoveDB.parameter_sha256 != parameters["parameter_sha256"]),
            )
            .first()
        )
        if stale:
            raise ParameterError("parameter_mismatch", "Existing positions require --reanalyze after backup")
        return f"existing job {existing.id} ({existing.status})"
    action = "reset" if existing else "admit"
    if apply:
        if existing:
            db.query(KifuAnalysisMoveDB).filter_by(job_id=existing.id).delete(synchronize_session=False)
            existing.analysis_parameters = parameters
            existing.status = "pending"
            existing.total_moves = len(parsed.moves)
            existing.analyzed_moves = existing.retry_count = 0
            existing.error_message = existing.started_at = existing.completed_at = None
        else:
            db.add(
                KifuAnalysisJobDB(
                    **identity,
                    analysis_parameters=parameters,
                    status="pending",
                    total_moves=len(parsed.moves),
                    analyzed_moves=0,
                )
            )
        db.commit()
    return f"{action}: {len(parsed.moves)} moves, {parameters['rules']}, komi {parameters['komi']}, 2000 visits"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("album_ids", nargs="+", type=int, help="At most 20 explicitly selected album IDs")
    parser.add_argument("--apply", action="store_true", help="Insert idempotent jobs")
    parser.add_argument("--evidence-json", help="Reviewed exact-SGF evidence assertions (JSON list)")
    parser.add_argument(
        "--reanalyze", action="store_true", help="After backup/worker stop: discard all old positions and reset"
    )
    args = parser.parse_args()
    if not 1 <= len(args.album_ids) <= 20:
        parser.error("Select 1–20 album IDs per run")
    if not KATAGO_EXPECTED_MODEL_SHA256:
        parser.error("KATAGO_EXPECTED_MODEL_SHA256 must pin the deployed transformer")
    evidence_by_sha = load_evidence(args.evidence_json)

    seen: set[int] = set()
    with SessionLocal() as db:
        for requested_id in args.album_ids:
            requested = db.query(KifuAlbumDB).filter(KifuAlbumDB.id == requested_id).first()
            if requested is None:
                print(f"{requested_id}: missing")
                continue
            canonical_id = requested.duplicate_of_id or requested.id
            canonical = db.query(KifuAlbumDB).filter(KifuAlbumDB.id == canonical_id).first()
            if canonical is None or canonical.duplicate_of_id is not None or canonical.sgf_content != requested.sgf_content:
                print(f"{requested_id}: invalid duplicate link or SGF changed")
                continue
            if canonical_id in seen:
                print(f"{requested_id}: already selected canonical {canonical_id}")
                continue
            seen.add(canonical_id)
            sha = hashlib.sha256(canonical.sgf_content.encode("utf-8")).hexdigest()
            try:
                result = admit_album(
                    db,
                    canonical,
                    KATAGO_EXPECTED_MODEL_SHA256,
                    evidence=evidence_by_sha.get(sha),
                    reanalyze=args.reanalyze,
                    apply=args.apply,
                )
                print(f"{requested_id}: {result}{'' if args.apply else ' (dry run)'}")
            except ParameterError as exc:
                db.rollback()
                print(f"{requested_id}: unresolved: {exc}")
            except IntegrityError:
                db.rollback()
                print(f"{requested_id}: concurrent admission already exists")


if __name__ == "__main__":
    main()
