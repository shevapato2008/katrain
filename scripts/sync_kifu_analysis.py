"""Copy at most 60 existing professional reports between databases; never run an engine.

Export uses a read-only snapshot. Import defaults to a complete target preflight;
--apply uses the batch importer's locked, idempotent transaction for each game.
SGFs and personal reports are never written. KATRAIN_DATABASE_URL selects the DB.
"""

import argparse
import json

from sqlalchemy.orm import Session, sessionmaker

from scripts import kifu_batch_transfer as batch


def validate_games(games):
    batch.require(0 < len(games) <= 60, "Select between 1 and 60 professional reports")
    batch.require(len({g["album_id"] for g in games}) == len(games), "Repeated album ID")
    batch.require(len({g["sgf_sha256"] for g in games}) == len(games), "Repeated exact SGF")
    for game in games:
        album_id = game["album_id"]
        batch.require(type(album_id) is int and album_id > 0, "Invalid album ID")
        batch.require(batch.sgf_hash(game["sgf_content"]) == game["sgf_sha256"], f"{album_id}: SGF checksum mismatch")
        batch.require(
            len(batch.parsed_game(game["sgf_content"]).moves) == game["total_moves"],
            f"{album_id}: SGF move count mismatch",
        )
        batch.require(
            batch.timestamp(game["completed_at"]) >= batch.timestamp(game["started_at"]),
            f"{album_id}: invalid job timing",
        )
        batch.validate_moves(game, game["moves"])
    return games


def validate_reports(artifact):
    batch.require(artifact.get("format") == "kifu-report-sync-v1", "Unsupported report sync format")
    batch.require(
        artifact.get("model_sha256") == batch.MODEL_SHA256 and artifact.get("requested_visits") == batch.VISITS,
        "Report model/visits mismatch",
    )
    batch.require(
        artifact.get("reports_sha256") == batch.digest({k: v for k, v in artifact.items() if k != "reports_sha256"}),
        "Report checksum mismatch",
    )
    return validate_games(artifact["games"])


def export_reports(engine, album_ids):
    from katrain.cron.models import KifuAlbumDB as Album, KifuAnalysisJobDB as Job, KifuAnalysisMoveDB as Move

    batch.require(0 < len(album_ids) <= 60 and len(set(album_ids)) == len(album_ids), "Select 1–60 unique album IDs")
    games = []
    with batch.read_snapshot(engine) as conn, Session(bind=conn) as db:
        for album_id in album_ids:
            album = db.get(Album, album_id)
            batch.require(album is not None and album.duplicate_of_id is None, f"{album_id}: missing canonical album")
            sgf_sha256 = batch.sgf_hash(album.sgf_content)
            job = (
                db.query(Job)
                .filter_by(
                    album_id=album_id,
                    sgf_sha256=sgf_sha256,
                    model_sha256=batch.MODEL_SHA256,
                    requested_visits=batch.VISITS,
                    status="completed",
                )
                .one_or_none()
            )
            batch.require(job is not None, f"{album_id}: no completed identity for current SGF/model")
            batch.require(job.analyzed_moves == job.total_moves, f"{album_id}: incomplete progress")
            games.append(
                {
                    "album_id": album_id,
                    "sgf_content": album.sgf_content,
                    "sgf_sha256": sgf_sha256,
                    "total_moves": job.total_moves,
                    "started_at": batch.iso(job.started_at),
                    "completed_at": batch.iso(job.completed_at),
                    "moves": [
                        batch.move_payload(row)
                        for row in db.query(Move).filter_by(job_id=job.id).order_by(Move.move_number)
                    ],
                }
            )
    validate_games(games)
    body = {
        "format": "kifu-report-sync-v1",
        "model_sha256": batch.MODEL_SHA256,
        "requested_visits": batch.VISITS,
        "games": games,
    }
    return {**body, "reports_sha256": batch.digest(body)}


def import_reports(engine, games, *, apply=False):
    validate_games(games)
    sessions = sessionmaker(bind=engine, autoflush=False)
    outcomes = []
    # Reject any known target mismatch before the first write, including one late
    # in the roster. The importer rechecks under a row lock during each commit.
    for game in games:
        try:
            action = batch.import_game(sessions, game, game)
        except batch.BatchError as exc:
            raise batch.BatchError(f"{game['album_id']}: {exc}") from exc
        outcomes.append({"album_id": game["album_id"], "action": action})
    if apply:
        outcomes = [
            {"album_id": game["album_id"], "action": batch.import_game(sessions, game, game, apply=True)}
            for game in games
        ]
    return outcomes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    exporter = commands.add_parser("export", help="Read-only export of explicit completed professional reports")
    exporter.add_argument("--album-ids", type=int, nargs="+", required=True)
    exporter.add_argument("--output", required=True)
    importer = commands.add_parser("import", help="Preflight targets; write only with --apply")
    importer.add_argument("--reports")
    importer.add_argument("--batch-manifest")
    importer.add_argument("--batch-results", nargs=2)
    importer.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    engine = batch.production_engine()
    try:
        if args.command == "export":
            artifact = export_reports(engine, args.album_ids)
            batch.write_artifact(args.output, artifact)
            print(json.dumps({"reports_sha256": artifact["reports_sha256"], "games": len(artifact["games"])}))
        else:
            games = validate_reports(batch.read_artifact(args.reports)) if args.reports else []
            batch.require(
                bool(args.batch_manifest) == bool(args.batch_results), "Provide batch manifest and both results"
            )
            if args.batch_manifest:
                manifest = batch.read_artifact(args.batch_manifest)
                results = batch.validate_results(manifest, [batch.read_artifact(p) for p in args.batch_results])
                games += [{**g, **results[g["album_id"]]} for g in manifest["games"]]
            outcomes = import_reports(engine, games, apply=args.apply)
            print(json.dumps({"applied": args.apply, "games": outcomes}))
    except batch.BatchError as exc:
        parser.exit(1, f"Report sync rejected: {exc}\n")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
