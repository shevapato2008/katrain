"""Freeze one rank-only correction for three explicitly authorized source games.

Build is read-only unless --output is given. Applying an existing frozen file is
restricted to the local TEST workflow; PROD uses the verified native receiver.
This module never constructs Stage or StateStore and never searches SGF files.
"""

from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
import argparse
import json
import os
from pathlib import Path
import stat
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select

from katrain.core.sgf_parser import SGF
from katrain.kifu_ingest.catalog import lookup_qualified_identities, publish_manifest
from katrain.kifu_ingest.ranks import (
    FORMAT_V2,
    MAX_MANIFEST_BYTES,
    freeze_game_ranks,
    validate_manifest_ranks,
    validate_rank_snapshot,
)
from katrain.web.core.models_db import (
    KifuAlbum,
    KifuAlbumRankSnapshot,
    KifuAlbumSource,
    KifuNameBatch,
    KifuPlayer,
    KifuPlayerRankHistory,
    KifuSource,
)
from katrain.web.kifu.name_candidates import canonical_sha256
from katrain.web.kifu.player_ranks import _row_fact, lookup_library_rank_facts


PINNED_ORIGINALS = {
    "91694911": {
        "sgf_sha256": "b044277aaac3223d3304fee2b958358418a83624d8c817fedb850c1994d845c2",
        "manifest_sha256": "0dbd77cb3a4290768ad9955542a51a8dc85cc6517231a0778faf06b42417d8fb",
    },
    "91638738": {
        "sgf_sha256": "0da65da0d6d75d9839585fdeac0f3860929e019ca03d7445c42887324a9bfd8f",
        "manifest_sha256": "2608c873a1f62fade6f3e5b5964befb69e43d32009920c3a7793c3c198920e1e",
    },
    "91637528": {
        "sgf_sha256": "97edeb6666a08122e24940c7d4e303f7c1a2f4f4dfb8c94b2dc7b7ef762557d8",
        "manifest_sha256": "c14e011c14dbca7511ae472e0c70c0f3fda4f0cb3ef2ba42e7dbe348de924824",
    },
}
PUBLICATION_KEY = "rank-only-19x19-91637528-91638738-91694911-v1"


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _safe_path(path):
    path = Path(path).absolute()
    for candidate in (path, path.resolve()):
        _require(
            not any(candidate.parts[n : n + 2] == ("data", "kifu-album") for n in range(len(candidate.parts) - 1)),
            "album filesystem access is forbidden",
        )
    _require(not path.is_symlink(), "JSON symlink is unsafe")
    return path


def _read_json(path):
    path = _safe_path(path)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as handle:
        info = os.fstat(handle.fileno())
        _require(
            stat.S_ISREG(info.st_mode) and 0 < info.st_size <= MAX_MANIFEST_BYTES, "JSON must be a bounded regular file"
        )
        raw = handle.read(info.st_size + 1)
        _require(
            len(raw) == info.st_size and os.fstat(handle.fileno()).st_size == info.st_size, "JSON changed during read"
        )
    value = json.loads(raw)
    _require(isinstance(value, dict), "JSON must contain an object")
    return value


def _check_game(game):
    item = game.get("source_item_id")
    _require(
        game.get("source_key") == "19x19" and item in PINNED_ORIGINALS, "source is outside exact correction whitelist"
    )
    content = game.get("sgf_content")
    _require(
        isinstance(content, str)
        and sha256(content.encode("utf-8")).hexdigest()
        == game.get("sgf_sha256")
        == PINNED_ORIGINALS[item]["sgf_sha256"],
        "original SGF hash mismatch",
    )
    root = SGF.parse_sgf(content)
    for side, prop in (("black", "BR"), ("white", "WR")):
        _require(
            game.get("metadata", {}).get(f"{side}_rank") in (None, "") and not any(root.get_list_property(prop) or []),
            "original raw rank must be empty",
        )
        owner = game.get("identities", {}).get(side)
        _require(
            isinstance(owner, dict)
            and set(owner) == {"canonical_name"}
            and isinstance(owner["canonical_name"], str)
            and owner["canonical_name"],
            "original canonical player identity missing",
        )
    return item


def _original_games(paths):
    _require(len(paths) == len(PINNED_ORIGINALS), "provide exactly three original packages")
    manifests = {}
    for path in paths:
        original = _read_json(path)
        digest = canonical_sha256(original)
        _require(
            digest in {pin["manifest_sha256"] for pin in PINNED_ORIGINALS.values()} and digest not in manifests,
            "original package digest is unpinned or duplicated",
        )
        manifests[digest] = original
    result = []
    for item, pin in sorted(PINNED_ORIGINALS.items()):
        original = manifests.get(pin["manifest_sha256"], {})
        matches = [
            game
            for game in original.get("games", [])
            if game.get("source_key") == "19x19" and game.get("source_item_id") == item
        ]
        _require(len(matches) == 1, "original package has no exact unique source member")
        game = deepcopy(matches[0])
        _check_game(game)
        result.append(game)
    return result


def _local_preimage(conn, game):
    """Read exact original native authority and current overlay; never use a portable numeric ID."""
    item = game["source_item_id"]
    digest = PINNED_ORIGINALS[item]["manifest_sha256"]
    batch = (
        conn.execute(select(KifuNameBatch.__table__).where(KifuNameBatch.bundle_sha256 == digest))
        .mappings()
        .one_or_none()
    )
    _require(batch is not None and batch["status"] == "applied", "original native batch is not applied")
    artifact = batch["reviewed_artifact"]
    _require(
        artifact.get("publication_format") in {"kifu-incremental-manifest-v1", FORMAT_V2}
        and artifact.get("manifest_sha256") == digest,
        "original native artifact mismatch",
    )
    logical = [
        record
        for record in artifact.get("logical_manifest", {}).get("games", [])
        if record.get("source_key") == "19x19" and record.get("source_item_id") == item
    ]
    _require(
        logical == [{key: value for key, value in game.items() if key != "sgf_content"}],
        "original logical game differs from pinned package",
    )
    sources = [
        source
        for source in artifact.get("sources", [])
        if source.get("source_key") == "19x19" and source.get("source_item_id") == item
    ]
    _require(len(sources) == 1, "original exact source receipt missing")
    source = sources[0]
    _require(
        all(
            source.get(key) == game.get(key)
            for key in ("source_key", "source_item_id", "origin_path", "raw_sha256", "sgf_sha256")
        ),
        "original source receipt differs from package",
    )
    album_id = source["album_id"]
    album = conn.execute(select(KifuAlbum.__table__).where(KifuAlbum.id == album_id)).mappings().one_or_none()
    _require(
        album is not None and album["duplicate_of_id"] is None and album["list_hidden_reason"] is None,
        "original album is not public",
    )
    _require(
        album["sgf_content"] == game["sgf_content"]
        and sha256(album["sgf_content"].encode("utf-8")).hexdigest() == source["album_sgf_sha256"],
        "original album SGF preimage changed",
    )
    _require(all(album.get(key) == value for key, value in game["metadata"].items()), "album metadata preimage changed")
    link = conn.scalar(
        select(KifuAlbumSource.id)
        .join(KifuSource, KifuSource.id == KifuAlbumSource.source_id)
        .where(
            KifuAlbumSource.album_id == album_id,
            KifuSource.source_key == "19x19",
            KifuAlbumSource.origin_path == game["origin_path"],
        )
    )
    _require(link is not None, "original source link missing")
    members = [
        record
        for record in artifact.get("receipt", {}).get("games", [])
        if record.get("source_key") == "19x19" and record.get("source_item_id") == item
    ]
    _require(len(members) == 1 and members[0].get("album_id") == album_id, "original receipt album binding changed")
    players, expected = {}, {"black": None, "white": None}
    for side in ("black", "white"):
        _require(album[f"{side}_rank"] == game["metadata"].get(f"{side}_rank"), "album raw rank preimage changed")
        player_id = album[f"{side}_player_id"]
        canonical = conn.scalar(select(KifuPlayer.canonical_name).where(KifuPlayer.id == player_id))
        _require(canonical == game["identities"][side]["canonical_name"], "album canonical FK identity changed")
        players[side] = {"id": player_id, "canonical_name": canonical}
        row = (
            conn.execute(
                select(KifuAlbumRankSnapshot.__table__).where(
                    KifuAlbumRankSnapshot.album_id == album_id, KifuAlbumRankSnapshot.side == side
                )
            )
            .mappings()
            .one_or_none()
        )
        if row is not None:
            snapshot = validate_rank_snapshot(row["snapshot"])
            _require(
                snapshot["content_sha256"] == row["snapshot_sha256"]
                and snapshot["player_ref"] == game["identities"][side]
                and snapshot["source_ref"]
                == {"source_key": "19x19", "source_item_id": item, "sgf_sha256": game["sgf_sha256"], "slot": side}
                and snapshot["raw_rank"] == "",
                "existing rank snapshot preimage mismatch",
            )
            fact_sha = snapshot["rank_fact_sha256"]
            _require((fact_sha is None) == (row["rank_fact_id"] is None), "existing rank fact link changed")
            if fact_sha:
                history = (
                    conn.execute(
                        select(KifuPlayerRankHistory.__table__).where(KifuPlayerRankHistory.id == row["rank_fact_id"])
                    )
                    .mappings()
                    .one_or_none()
                )
                _require(
                    history is not None
                    and history["player_id"] == player_id
                    and _row_fact(history, canonical)["content_sha256"] == fact_sha,
                    "existing immutable rank fact changed",
                )
            expected[side] = row["snapshot_sha256"]
    return players, expected


def build_correction(engine, originals, *, matched_at=None):
    """Read three native preimages and at most six already-bound player profiles."""
    games = _original_games(originals)
    preimages = {}
    with engine.connect() as conn:
        if conn.dialect.name == "postgresql":
            conn.exec_driver_sql("SET TRANSACTION READ ONLY")
            conn.exec_driver_sql("SET LOCAL statement_timeout = '5s'")
        for game in games:
            preimages[game["source_item_id"]] = _local_preimage(conn, game)
    resolved = lookup_qualified_identities(
        engine, player_values={game["metadata"][f"player_{side}"] for game in games for side in ("black", "white")}
    )
    requested = {}
    for game in games:
        players, _ = preimages[game["source_item_id"]]
        for side in ("black", "white"):
            match = resolved["player"].get(game["metadata"][f"player_{side}"], {})
            _require(
                match.get("status") in {"qualified", "missing_qualified_five_languages"}
                and all(match.get(key) == value for key, value in players[side].items()),
                "resolved player does not match actual local slot FK",
            )
            requested[match["id"]] = match
    matched_at = matched_at or datetime.now(timezone.utc).isoformat()
    library = lookup_library_rank_facts(engine, list(requested.values()), observed_at=matched_at)
    facts = {
        requested[player_id]["canonical_name"]: result["fact"]
        for player_id, result in library.items()
        if player_id in requested and result.get("status") == "qualified"
    }
    manifest = {
        "format": FORMAT_V2,
        "mode": "rank_only",
        "publication_key": PUBLICATION_KEY,
        "games": games,
        "decisions": [],
        "rank_facts": {},
    }
    for game in games:
        frozen = freeze_game_ranks(game, library_facts=facts, matched_at=matched_at)
        game.update({key: frozen[key] for key in ("rank_snapshots", "rank_observations")})
        game["rank_correction"] = {
            "original_manifest_sha256": PINNED_ORIGINALS[game["source_item_id"]]["manifest_sha256"],
            "expected_snapshots": preimages[game["source_item_id"]][1],
        }
        manifest["rank_facts"].update(frozen["rank_facts"])
    return validate_correction(manifest)


def validate_correction(manifest, expected_sha256=None):
    """Validate frozen immutable bindings; native apply/replay owns live CAS."""
    _require(
        manifest.get("format") == FORMAT_V2
        and manifest.get("mode") == "rank_only"
        and manifest.get("publication_key") == PUBLICATION_KEY
        and manifest.get("decisions") == [],
        "not the finite rank-only correction",
    )
    games = manifest.get("games", [])
    _require(
        len(games) == len(PINNED_ORIGINALS) and {game.get("source_item_id") for game in games} == set(PINNED_ORIGINALS),
        "correction must contain exact three source IDs",
    )
    for game in games:
        item = _check_game(game)
        _require(
            "album_id" not in game
            and game.get("rank_correction", {}).get("original_manifest_sha256")
            == PINNED_ORIGINALS[item]["manifest_sha256"],
            "correction original authority mismatch",
        )
    validate_manifest_ranks(manifest)
    if expected_sha256 is not None:
        _require(canonical_sha256(manifest) == expected_sha256, "frozen manifest hash mismatch")
    return manifest


def freeze_output(path, manifest):
    """Link complete fsynced bytes once; never overwrite a frozen package."""
    validate_correction(manifest)
    path = _safe_path(path)
    _require(not path.exists(), "correction output already exists")
    raw = json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False).encode("utf-8") + b"\n"
    _require(len(raw) <= MAX_MANIFEST_BYTES, "correction file exceeds receiver limit")
    fd, temporary = tempfile.mkstemp(prefix=".rank-correction-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temporary, path)
        except FileExistsError as exc:
            raise ValueError("correction output already exists") from exc
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        os.unlink(temporary)


def _engine(database_url=None):
    from sqlalchemy import create_engine
    from katrain.web.core.config import settings

    return create_engine(database_url or settings.DATABASE_URL)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    build = commands.add_parser("build", help="read-only summary, or freeze once with --output")
    build.add_argument("--original", action="append", default=[], help="exact original package; repeat three times")
    build.add_argument("--output", help="new immutable output, or reuse an existing frozen output")
    build.add_argument("--database-url", help="TEST database override; defaults to configured database")
    apply = commands.add_parser("apply-existing", help="explicit local TEST native apply/replay")
    apply.add_argument("--manifest", required=True)
    apply.add_argument("--expected-sha256", required=True)
    apply.add_argument("--apply", action="store_true")
    apply.add_argument("--target", choices=["test"])
    apply.add_argument("--database-url")
    args = parser.parse_args(argv)
    try:
        if args.command == "build":
            existing = args.output is not None and _safe_path(args.output).exists()
            manifest = (
                validate_correction(_read_json(args.output))
                if existing
                else build_correction(_engine(args.database_url), args.original)
            )
            if args.output and not existing:
                freeze_output(args.output, manifest)
            result = {
                "status": "frozen" if args.output else "dry_run",
                "manifest_sha256": canonical_sha256(manifest),
                "games": len(manifest["games"]),
                "source_ids": [game["source_item_id"] for game in manifest["games"]],
                "ranks": {
                    game["source_item_id"]: {
                        side: game["rank_snapshots"][side]["display_rank"] for side in ("black", "white")
                    }
                    for game in manifest["games"]
                },
            }
            if args.output:
                result["path"] = str(_safe_path(args.output))
        else:
            _require(args.apply and args.target == "test", "local application requires --apply --target test")
            manifest = validate_correction(_read_json(args.manifest), args.expected_sha256)
            receipt = publish_manifest(
                _engine(args.database_url), manifest, expected_manifest_sha256=args.expected_sha256
            )
            result = {"status": "applied", "manifest_sha256": args.expected_sha256, "receipt": receipt}
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
