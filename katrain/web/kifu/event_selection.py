"""Exact duplicate-GN rule and reversible, independently reviewed event selections."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import re

from sqlalchemy import select

from katrain.core.sgf_parser import ParseError, SGF
from katrain.web.core.models_db import KifuAlbum, KifuAlbumEventSelection, KifuEventSelectionBatch
from katrain.web.kifu.name_candidates import canonical_sha256
from katrain.web.kifu.name_parse import parse_event
from katrain.web.kifu.provenance import classify_source_path, sgf_sha256


class EventSelectionError(ValueError):
    """The reviewed selection does not match the live album or audit evidence."""


RULE_VERSION = "19x19-gnugo-second-gn-v1"
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_MEMBER_KEYS = {
    "album_id",
    "old_event",
    "old_event_id",
    "old_source",
    "old_source_path",
    "old_date_played",
    "old_round_name",
    "old_board_size",
    "sgf_sha256",
    "property_name",
    "property_index",
    "selected_raw",
    "rule_version",
}
_REVIEW_KEYS = {
    "reviewer_id",
    "reviewer_model",
    "reviewed_at",
    "review_conclusion",
    "evidence_scope",
    "status",
    "member_set_sha256",
    "basis",
    "review_signature",
}
_BUNDLE_KEYS = {
    "selection_format",
    "rule_version",
    "members",
    "member_set_sha256",
    "producer_id",
    "producer_model",
    "produced_at",
    "scope_frozen_at",
    "review",
}
_EVIDENCE_SCOPE_KEYS = {"member_set_sha256", "album_count", "reviewed_material"}
_ALBUM_PREIMAGE = {
    "event": "old_event",
    "event_id": "old_event_id",
    "source": "old_source",
    "source_path": "old_source_path",
    "date_played": "old_date_played",
    "round_name": "old_round_name",
    "board_size": "old_board_size",
}


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise EventSelectionError(message)


def _timestamp(value: object, label: str) -> datetime:
    _require(isinstance(value, str), f"{label} is required")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise EventSelectionError(f"{label} is invalid") from exc
    _require(parsed.tzinfo is not None, f"{label} needs a timezone")
    return parsed


def selected_second_gn(root, source_folder: str) -> str | None:
    """Return GN[1] only for the audited 19x19 program-label pattern."""
    game_names = root.get_list_property("GN") or []
    game_comments = root.get_list_property("GC") or []
    if (
        "EV" not in root.properties
        and source_folder == "19x19"
        and root.get_property("SO") == "https://19x19.com"
        and len(game_names) == 2
        and game_names[0] == "GNUGo3.8"
        and game_names[1]
        and parse_event(game_names[1], None).category not in {"program_source_label", "corrupt_data"}
        and len(game_comments) == 1
        and (game_comments[0] == game_names[1] or game_comments[0].startswith(game_names[1] + " | "))
    ):
        return game_names[1]
    return None


def validate_bundle(bundle: dict) -> dict:
    """Validate the finite artifact and its independently signed member set offline."""
    _require(isinstance(bundle, dict) and set(bundle) == _BUNDLE_KEYS, "selection bundle fields differ")
    _require(
        bundle["selection_format"] == 1 and bundle["rule_version"] == RULE_VERSION,
        "selection bundle rule version differs",
    )
    members = bundle["members"]
    _require(isinstance(members, list) and members, "finite members are required")
    _require(
        isinstance(bundle["producer_id"], str) and bool(bundle["producer_id"].strip()), "producer identity is required"
    )
    _require(
        isinstance(bundle["producer_model"], str) and bool(bundle["producer_model"].strip()),
        "actual producer model is required",
    )
    produced_at = _timestamp(bundle["produced_at"], "production time")
    frozen_at = _timestamp(bundle["scope_frozen_at"], "scope freeze time")
    _require(produced_at <= frozen_at, "scope freeze precedes production")
    ids = []
    for index, member in enumerate(members):
        _require(isinstance(member, dict) and set(member) == _MEMBER_KEYS, f"member[{index}] fields differ")
        album_id = member["album_id"]
        _require(type(album_id) is int and album_id > 0, f"member[{index}] album ID invalid")
        ids.append(album_id)
        _require(
            member["old_event"] == "GNUGo3.8" and member["old_event_id"] is None,
            f"member[{index}] legacy event preimage differs",
        )
        _require(
            member["old_board_size"] == 19
            and member["old_source"] == "https://19x19.com"
            and isinstance(member["old_source_path"], str)
            and classify_source_path(member["old_source_path"]) == "19x19",
            f"member[{index}] source preimage differs",
        )
        _require(
            member["property_name"] == "GN"
            and member["property_index"] == 1
            and member["rule_version"] == RULE_VERSION,
            f"member[{index}] selection rule differs",
        )
        _require(
            isinstance(member["selected_raw"], str) and bool(member["selected_raw"].strip()),
            f"member[{index}] selected value is empty",
        )
        _require(
            isinstance(member["sgf_sha256"], str) and _SHA256.fullmatch(member["sgf_sha256"]) is not None,
            f"member[{index}] SGF SHA-256 invalid",
        )
        for field in ("old_date_played", "old_round_name"):
            _require(member[field] is None or isinstance(member[field], str), f"member[{index}] {field} invalid")
    _require(ids == sorted(set(ids)), "duplicate or unsorted member IDs")
    member_hash = canonical_sha256(members)
    _require(bundle["member_set_sha256"] == member_hash, "member set hash mismatch")
    review = bundle["review"]
    _require(isinstance(review, dict) and set(review) == _REVIEW_KEYS, "review signature fields differ")
    _require(
        review["status"] == "approved" and review["member_set_sha256"] == member_hash,
        "member set lacks approved independent review",
    )
    _require(
        isinstance(review["reviewer_id"], str)
        and bool(review["reviewer_id"].strip())
        and review["reviewer_id"] != bundle["producer_id"],
        "reviewer must differ from producer",
    )
    _require(
        isinstance(review["reviewer_model"], str) and bool(review["reviewer_model"].strip()),
        "actual reviewer model is required",
    )
    _require(review["review_conclusion"] == "approved_second_gn_selection", "explicit review conclusion differs")
    scope = review["evidence_scope"]
    _require(
        isinstance(scope, dict)
        and set(scope) == _EVIDENCE_SCOPE_KEYS
        and scope["member_set_sha256"] == member_hash
        and scope["album_count"] == len(members)
        and isinstance(scope["reviewed_material"], str)
        and bool(scope["reviewed_material"].strip()),
        "review evidence scope does not bind the frozen member set",
    )
    _require(isinstance(review["basis"], str) and bool(review["basis"].strip()), "review basis is required")
    reviewed_at = _timestamp(review["reviewed_at"], "review time")
    _require(reviewed_at > frozen_at, "review precedes or coincides with scope freeze")
    signed = {key: value for key, value in review.items() if key != "review_signature"}
    _require(review["review_signature"] == canonical_sha256(signed), "independent review signature mismatch")
    return {
        "ready": True,
        "member_count": len(members),
        "member_set_sha256": member_hash,
        "bundle_sha256": canonical_sha256(bundle),
    }


def _album_preimage(album: dict, member: dict) -> None:
    for current_key, member_key in _ALBUM_PREIMAGE.items():
        _require(album[current_key] == member[member_key], f"album {member['album_id']} {current_key} preimage changed")
    _require(
        sgf_sha256(album["sgf_content"]) == member["sgf_sha256"], f"album {member['album_id']} SGF preimage changed"
    )
    try:
        root = SGF.parse_sgf(album["sgf_content"])
        selected = selected_second_gn(root, classify_source_path(album["source_path"]))
    except (ParseError, ValueError, TypeError, AttributeError, IndexError) as exc:
        raise EventSelectionError(f"album {member['album_id']} SGF cannot be checked") from exc
    _require(
        selected is not None and selected == member["selected_raw"],
        f"album {member['album_id']} reviewed GN[1] differs from SGF",
    )


def _image(row) -> dict:
    return {key: value.isoformat() if isinstance(value, datetime) else value for key, value in row.items()}


def _inspect(conn, bundle: dict) -> dict:
    result = validate_bundle(bundle)
    albums = KifuAlbum.__table__
    selections = KifuAlbumEventSelection.__table__
    for member in bundle["members"]:
        album = conn.execute(select(albums).where(albums.c.id == member["album_id"])).mappings().one_or_none()
        _require(album is not None, f"album {member['album_id']} preimage missing")
        _album_preimage(album, member)
        current = conn.execute(
            select(selections.c.album_id).where(selections.c.album_id == member["album_id"])
        ).scalar_one_or_none()
        _require(current is None, f"album {member['album_id']} already selected")
    return {**result, "status": "ready"}


def dry_run_bundle(engine, bundle: dict) -> dict:
    """Read every live preimage without writing or migrating the catalog."""
    with engine.connect() as conn:
        return _inspect(conn, bundle)


@contextmanager
def _locked_write(engine):
    conn = engine.connect()
    try:
        if engine.dialect.name == "postgresql":
            conn = conn.execution_options(isolation_level="READ COMMITTED")
            conn.begin()
            conn.exec_driver_sql("SELECT pg_advisory_xact_lock(%s)", (720220261003,))
            conn.exec_driver_sql(
                "LOCK TABLE kifu_albums, kifu_album_event_selections, "
                "kifu_event_selection_batches IN SHARE ROW EXCLUSIVE MODE"
            )
        elif engine.dialect.name == "sqlite":
            conn.exec_driver_sql("PRAGMA foreign_keys=ON")
            _require(
                conn.exec_driver_sql("PRAGMA foreign_keys").scalar_one() == 1, "SQLite foreign keys must be enabled"
            )
            conn.exec_driver_sql("BEGIN IMMEDIATE")
        else:
            raise EventSelectionError("Only PostgreSQL and SQLite are supported")
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def apply_bundle(engine, bundle: dict) -> dict:
    """Atomically add only the reviewed derived selections after live rechecks."""
    report = validate_bundle(bundle)
    batches = KifuEventSelectionBatch.__table__
    selections = KifuAlbumEventSelection.__table__
    with _locked_write(engine) as conn:
        prior = (
            conn.execute(select(batches).where(batches.c.bundle_sha256 == report["bundle_sha256"]))
            .mappings()
            .one_or_none()
        )
        if prior is not None:
            _require(
                prior["status"] == "applied" and prior["reviewed_artifact"]["bundle"] == bundle,
                "bundle was undone or its audit artifact changed",
            )
            for member in bundle["members"]:
                album = (
                    conn.execute(select(KifuAlbum.__table__).where(KifuAlbum.id == member["album_id"]))
                    .mappings()
                    .one_or_none()
                )
                _require(album is not None, f"album {member['album_id']} changed since apply")
                try:
                    _album_preimage(album, member)
                except EventSelectionError as exc:
                    raise EventSelectionError(f"album {member['album_id']} changed since apply") from exc
            for expected in prior["reviewed_artifact"]["after_images"]:
                current = (
                    conn.execute(select(selections).where(selections.c.album_id == expected["album_id"]))
                    .mappings()
                    .one_or_none()
                )
                _require(
                    current is not None and _image(current) == expected,
                    f"selection for album {expected['album_id']} changed since apply",
                )
            return {
                "status": "already_applied",
                "batch_id": prior["id"],
                "change_count": 0,
                "bundle_sha256": report["bundle_sha256"],
            }
        _inspect(conn, bundle)
        review = bundle["review"]
        reviewed_at = datetime.fromisoformat(review["reviewed_at"].replace("Z", "+00:00"))
        artifact = {"bundle": bundle, "before_images": bundle["members"], "after_images": []}
        batch_id = conn.execute(
            batches.insert().values(
                bundle_sha256=report["bundle_sha256"],
                member_set_sha256=report["member_set_sha256"],
                reviewed_artifact=artifact,
                producer_id=bundle["producer_id"],
                reviewer_id=review["reviewer_id"],
                reviewed_at=reviewed_at,
                status="applied",
                applied_at=datetime.now(timezone.utc),
            )
        ).inserted_primary_key[0]
        for member in bundle["members"]:
            conn.execute(
                selections.insert().values(
                    album_id=member["album_id"],
                    event_id=None,
                    batch_id=batch_id,
                    selected_raw=member["selected_raw"],
                    sgf_sha256=member["sgf_sha256"],
                    property_name="GN",
                    property_index=1,
                    status="approved",
                    rule_version=RULE_VERSION,
                    reviewer_id=review["reviewer_id"],
                    reviewed_at=reviewed_at,
                )
            )
            after = conn.execute(select(selections).where(selections.c.album_id == member["album_id"])).mappings().one()
            artifact["after_images"].append(_image(after))
        conn.execute(batches.update().where(batches.c.id == batch_id).values(reviewed_artifact=artifact))
        return {
            "status": "applied",
            "batch_id": batch_id,
            "change_count": len(bundle["members"]),
            "bundle_sha256": report["bundle_sha256"],
        }


def batch_status(engine, batch_id: int) -> dict:
    with engine.connect() as conn:
        batch = (
            conn.execute(select(KifuEventSelectionBatch.__table__).where(KifuEventSelectionBatch.id == batch_id))
            .mappings()
            .one_or_none()
        )
        _require(batch is not None, f"batch {batch_id} not found")
        return {
            "batch_id": batch_id,
            "status": batch["status"],
            "bundle_sha256": batch["bundle_sha256"],
            "member_set_sha256": batch["member_set_sha256"],
            "member_count": len(batch["reviewed_artifact"]["before_images"]),
        }


def undo_batch(engine, batch_id: int) -> dict:
    """Remove this batch only if every album and selection still matches its after-image."""
    batches = KifuEventSelectionBatch.__table__
    selections = KifuAlbumEventSelection.__table__
    albums = KifuAlbum.__table__
    with _locked_write(engine) as conn:
        batch = conn.execute(select(batches).where(batches.c.id == batch_id)).mappings().one_or_none()
        _require(batch is not None, f"batch {batch_id} not found")
        _require(batch["status"] == "applied", "batch is not applied")
        artifact = batch["reviewed_artifact"]
        before = artifact["before_images"]
        after = artifact["after_images"]
        _require(
            canonical_sha256(artifact["bundle"]) == batch["bundle_sha256"]
            and canonical_sha256(before) == batch["member_set_sha256"]
            and before == artifact["bundle"]["members"]
            and len(before) == len(after),
            "batch audit images changed",
        )
        for member, expected in zip(before, after):
            album = conn.execute(select(albums).where(albums.c.id == member["album_id"])).mappings().one_or_none()
            _require(album is not None, f"album {member['album_id']} changed since apply")
            try:
                _album_preimage(album, member)
            except EventSelectionError as exc:
                raise EventSelectionError(f"album {member['album_id']} changed since apply") from exc
            row = (
                conn.execute(select(selections).where(selections.c.album_id == member["album_id"]))
                .mappings()
                .one_or_none()
            )
            _require(
                row is not None and _image(row) == expected,
                f"selection for album {member['album_id']} changed since apply",
            )
        for member in before:
            conn.execute(selections.delete().where(selections.c.album_id == member["album_id"]))
        conn.execute(
            batches.update()
            .where(batches.c.id == batch_id)
            .values(status="undone", undone_at=datetime.now(timezone.utc))
        )
        return {"status": "undone", "batch_id": batch_id, "reverted": len(before)}
