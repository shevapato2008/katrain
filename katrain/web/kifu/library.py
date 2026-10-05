"""Bounded library-page metadata; never load analysis JSON for a list."""

import hashlib

from sqlalchemy import func

from katrain.web.core.models_db import KifuAlbum, KifuAnalysisJob, KifuAnalysisMove


def report_availability(db, records, model_sha256, visits):
    """Verify identity and every stored position in one aggregate over this page."""
    if not records:
        return {}
    canonical_ids = {r.duplicate_of_id or r.id for r in records}
    canonicals = {r.id: r for r in records if r.id in canonical_ids}
    missing = canonical_ids - canonicals.keys()
    if missing:
        canonicals.update({r.id: r for r in db.query(KifuAlbum).filter(KifuAlbum.id.in_(missing)).all()})
    ids = canonical_ids | {r.id for r in records}
    rows = (
        db.query(
            KifuAnalysisJob.album_id,
            KifuAnalysisJob.sgf_sha256,
            KifuAnalysisJob.total_moves,
            func.count(KifuAnalysisMove.id),
            func.min(KifuAnalysisMove.move_number),
            func.max(KifuAnalysisMove.move_number),
            func.min(KifuAnalysisMove.root_visits),
            func.count(KifuAnalysisMove.root_visits),
        )
        .join(KifuAnalysisMove, KifuAnalysisMove.job_id == KifuAnalysisJob.id)
        .filter(
            KifuAnalysisJob.album_id.in_(ids),
            KifuAnalysisJob.status == "completed",
            KifuAnalysisJob.model_sha256 == model_sha256,
            KifuAnalysisJob.requested_visits == visits,
        )
        .group_by(KifuAnalysisJob.id)
        .all()
    )
    complete = {
        (album_id, sgf_hash, total)
        for album_id, sgf_hash, total, count, first, last, depth, depth_count in rows
        if count == total + 1 and first == 0 and last == total and depth_count == count and depth >= visits
    }
    result = {}
    for record in records:
        canonical = canonicals.get(record.duplicate_of_id or record.id)
        if canonical is None or canonical.duplicate_of_id or canonical.sgf_content != record.sgf_content:
            canonical = record
        digest = hashlib.sha256(record.sgf_content.encode("utf-8")).hexdigest()
        result[record.id] = (canonical.id, digest, canonical.move_count) in complete
    return result
