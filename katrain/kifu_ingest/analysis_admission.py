"""Persist professional report admission alongside a newly published album."""

from hashlib import sha256

from sqlalchemy import select

from katrain.cron.kifu_parameters import KIFU_VISITS, ParameterError, resolve_parameters
from katrain.cron.kifu_replay import parse_professional_replay
from katrain.kifu_ingest.ranks import FORMAT_V2, is_historical_snapshot
from katrain.web.core.models_db import KifuAlbum, KifuAnalysisJob


HOURLY_ANALYSIS_MARKER = "hourly_deep_analysis"
AUTO_ANALYSIS_DISABLED_ERROR = "CRON_KIFU_AUTO_ANALYSIS_ENABLED must be enabled for a marked hourly publication"


def supports_hourly_analysis(manifest):
    """Only current native hourly publications can carry the verified marker."""
    return (
        manifest.get("format") == FORMAT_V2
        and manifest.get("mode", "publish") == "publish"
        and any(
            is_historical_snapshot(snapshot)
            for game in manifest["games"]
            for snapshot in game["rank_snapshots"].values()
        )
    )


def admit_new_albums(conn, results, model_sha256):
    inserted = [row for row in results if row["action"] == "inserted"]
    album_ids = {row["album_id"] for row in inserted if row["source_key"] == "19x19"}
    if not album_ids:
        return
    # A new preferred source can become canonical for an existing game.
    duplicate = KifuAlbum.__table__.alias("historical_duplicate")
    historical_game = (
        select(duplicate.c.id)
        .where(
            duplicate.c.duplicate_of_id == KifuAlbum.id,
            duplicate.c.id.not_in({row["album_id"] for row in inserted}),
        )
        .exists()
    )
    albums = conn.execute(
        select(KifuAlbum.id, KifuAlbum.sgf_content, KifuAlbum.move_count)
        .where(KifuAlbum.id.in_(album_ids), KifuAlbum.duplicate_of_id.is_(None), ~historical_game)
        .order_by(KifuAlbum.id)
    )
    jobs = KifuAnalysisJob.__table__
    for album in albums:
        identity = {
            "album_id": album.id,
            "sgf_sha256": sha256(album.sgf_content.encode("utf-8")).hexdigest(),
            "model_sha256": model_sha256,
            "requested_visits": KIFU_VISITS,
        }
        if conn.scalar(select(jobs.c.id).filter_by(**identity)) is not None:
            continue

        status, parameters, error = "pending", None, None
        try:
            parameters = resolve_parameters(album.sgf_content)
            parse_professional_replay(album.sgf_content, expected_moves=album.move_count, required_board_size=19)
        except ParameterError as exc:
            status, error = "failed", str(exc)
        conn.execute(
            jobs.insert().values(
                **identity,
                status=status,
                analysis_parameters=parameters,
                error_message=error,
                total_moves=album.move_count,
            )
        )
