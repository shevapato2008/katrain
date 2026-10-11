"""Exact preimage repair of provisional player links that are not people."""

from collections import defaultdict

from sqlalchemy import or_, select, text
from sqlalchemy.orm import Session

from katrain.web.core.models_db import (
    KifuAlbum, KifuNameResearchEvidence, KifuPlayer, KifuPlayerAlias, KifuPlayerName, KifuRawPlayerValue,
)


def _expected_slots(inventory, raw_values):
    columns = {name: index for index, name in enumerate(inventory["association_columns"])}
    slots = defaultdict(list)
    for row in inventory["album_associations"]:
        for color, raw_column, fk_column in (("black", "player_black", "black_player_id"),
                                             ("white", "player_white", "white_player_id")):
            raw = row[columns[raw_column]]
            if raw in raw_values:
                old_fk = row[columns[fk_column]]
                if old_fk is not None:
                    raise ValueError(f"repair requires a formerly NULL slot: {raw!r}")
                slots[raw].append([row[columns["id"]], color])
    return {raw: sorted(values) for raw, values in slots.items()}


def _capture(db: Session, inventory: dict, batch: dict, exclusions: list[dict]) -> dict:
    if inventory["sha256"] != batch["inventory_sha256"]:
        raise ValueError("repair inventory and original batch differ")
    selected = {raw: group for group in batch["selected"] for raw in group["raw_values"]}
    original_names = dict(batch["manifest"]["catalog_players"])
    requested = {}
    for item in exclusions:
        raw, reason = item.get("raw_value"), item.get("reason")
        if raw in requested or raw not in selected or not isinstance(reason, str) or not reason.strip():
            raise ValueError("duplicate, unknown, or unexplained repair raw value")
        requested[raw] = reason
    if not requested:
        raise ValueError("empty repair list")
    frozen_slots = _expected_slots(inventory, requested)
    if set(frozen_slots) != set(requested):
        raise ValueError("repair raw value absent from frozen album slots")

    raw_rows = {row.raw_value: row for row in db.scalars(
        select(KifuRawPlayerValue).where(KifuRawPlayerValue.raw_value.in_(requested))
    )}
    if len(raw_rows) != len(requested):
        raise ValueError("repair raw staging row missing")
    current_slots = defaultdict(list)
    current = db.execute(select(KifuAlbum.id, KifuAlbum.player_black, KifuAlbum.player_white,
                                KifuAlbum.black_player_id, KifuAlbum.white_player_id).where(or_(
                                    KifuAlbum.player_black.in_(requested), KifuAlbum.player_white.in_(requested)
                                )))
    for album_id, black, white, black_id, white_id in current:
        if black in requested:
            current_slots[black].append([album_id, "black", black_id])
        if white in requested:
            current_slots[white].append([album_id, "white", white_id])

    entries = []
    for raw in sorted(requested, key=lambda value: value.encode("utf-8")):
        stored = raw_rows[raw]
        metadata = stored.review_metadata
        if (stored.review_status != "pending" or not isinstance(metadata, dict)
                or metadata.get("kind") != "provisional_person_link"
                or metadata.get("inventory_sha256") != inventory["sha256"]
                or not isinstance(metadata.get("player_id"), int)):
            raise ValueError(f"repair raw metadata preimage differs: {raw!r}")
        player_id = metadata["player_id"]
        group = selected[raw]
        person = db.get(KifuPlayer, player_id)
        expected_name = (group["canonical_name"] if group["existing_player_id"] is None
                         else original_names[group["existing_player_id"]])
        if person is None or person.canonical_name != expected_name:
            raise ValueError(f"repair player ID/canonical preimage differs: {raw!r}")
        if group["existing_player_id"] is not None and group["existing_player_id"] != player_id:
            raise ValueError(f"repair reused player ID differs: {raw!r}")
        seen = sorted(current_slots[raw])
        expected = sorted([album_id, color, player_id] for album_id, color in frozen_slots[raw])
        if seen != expected:
            raise ValueError(f"repair album FK preimage differs: {raw!r}")
        entries.append({"raw_value": raw, "reason": requested[raw], "base_name": group["base_name"],
                        "player_id": player_id, "canonical_name": person.canonical_name,
                        "raw_id": stored.id, "review_metadata": metadata, "slots": frozen_slots[raw],
                        "created_by_batch": group["existing_player_id"] is None})

    by_id = defaultdict(list)
    for entry in entries:
        by_id[entry["player_id"]].append(entry)
    created_ids = []
    for player_id, owner_entries in by_id.items():
        if not all(entry["created_by_batch"] for entry in owner_entries):
            continue
        group = selected[owner_entries[0]["raw_value"]]
        if {entry["raw_value"] for entry in owner_entries} != set(group["raw_values"]):
            raise ValueError(f"repair does not cover every raw variant of new player ID {player_id}")
        linked = db.execute(select(KifuAlbum.id, KifuAlbum.black_player_id, KifuAlbum.white_player_id).where(or_(
            KifuAlbum.black_player_id == player_id, KifuAlbum.white_player_id == player_id
        ))).all()
        actual_refs = sorted([album_id, color] for album_id, black_id, white_id in linked
                             for color, value in (("black", black_id), ("white", white_id)) if value == player_id)
        expected_refs = sorted(slot for entry in owner_entries for slot in entry["slots"])
        if actual_refs != expected_refs:
            raise ValueError(f"new player ID {player_id} has other album references")
        for model, column in ((KifuPlayerAlias, KifuPlayerAlias.player_id),
                              (KifuPlayerName, KifuPlayerName.player_id),
                              (KifuNameResearchEvidence, KifuNameResearchEvidence.player_id)):
            if db.scalar(select(model.id).where(column == player_id).limit(1)) is not None:
                raise ValueError(f"new player ID {player_id} has reviewed references")
        created_ids.append(player_id)
    return {"format": 1, "inventory_sha256": inventory["sha256"],
            "original_batch_rule_sha256": batch["rule_sha256"],
            "counts": {"raw_values": len(entries), "album_slots": sum(len(row["slots"]) for row in entries),
                       "new_ids_to_delete": len(created_ids),
                       "reused_ids_to_keep": len(by_id) - len(created_ids)},
            "entries": entries, "delete_player_ids": sorted(created_ids)}


def capture_repair_plan(inventory: dict, batch: dict, exclusions: list[dict], engine) -> dict:
    """Read current TEST/PROD preimages without changing the database."""
    with Session(engine) as db:
        return _capture(db, inventory, batch, exclusions)


def run_repair_plan(inventory: dict, batch: dict, plan: dict, engine, *, apply: bool) -> dict:
    """Recheck every captured preimage, then atomically undo only listed links."""
    exclusions = [{"raw_value": row["raw_value"], "reason": row["reason"]} for row in plan["entries"]]
    with Session(engine) as db:
        transaction = db.begin()
        try:
            if engine.dialect.name == "postgresql":
                db.execute(text("LOCK TABLE kifu_albums, kifu_players, kifu_player_aliases, "
                                "kifu_player_names, kifu_name_research_evidence, kifu_raw_player_values "
                                "IN SHARE ROW EXCLUSIVE MODE"))
            if _capture(db, inventory, batch, exclusions) != plan:
                raise ValueError("repair preimages changed after capture")
            raw_to_id = {row["raw_value"]: row["player_id"] for row in plan["entries"]}
            if engine.dialect.name == "postgresql":
                import json

                db.execute(text("CREATE TEMP TABLE kifu_player_repair_map "
                                "(raw_value text PRIMARY KEY, player_id integer NOT NULL) ON COMMIT DROP"))
                db.execute(text(
                    "INSERT INTO kifu_player_repair_map (raw_value, player_id) "
                    "SELECT raw_value, player_id FROM "
                    "jsonb_to_recordset(CAST(:payload AS jsonb)) AS m(raw_value text, player_id integer)"
                ), {"payload": json.dumps([{"raw_value": raw, "player_id": id_}
                                            for raw, id_ in raw_to_id.items()], ensure_ascii=False)})
                black = db.execute(text("UPDATE kifu_albums AS a SET black_player_id = NULL "
                                        "FROM kifu_player_repair_map AS m WHERE a.player_black = m.raw_value "
                                        "AND a.black_player_id = m.player_id")).rowcount
                white = db.execute(text("UPDATE kifu_albums AS a SET white_player_id = NULL "
                                        "FROM kifu_player_repair_map AS m WHERE a.player_white = m.raw_value "
                                        "AND a.white_player_id = m.player_id")).rowcount
                raw_updated = db.execute(text("UPDATE kifu_raw_player_values AS r SET review_metadata = NULL "
                                              "FROM kifu_player_repair_map AS m WHERE r.raw_value = m.raw_value "
                                              "AND r.review_status = 'pending'")).rowcount
            else:
                black = white = raw_updated = 0
                for raw, player_id in raw_to_id.items():
                    black += db.query(KifuAlbum).filter(KifuAlbum.player_black == raw,
                                                          KifuAlbum.black_player_id == player_id).update(
                                                              {KifuAlbum.black_player_id: None})
                    white += db.query(KifuAlbum).filter(KifuAlbum.player_white == raw,
                                                          KifuAlbum.white_player_id == player_id).update(
                                                              {KifuAlbum.white_player_id: None})
                    raw_updated += db.query(KifuRawPlayerValue).filter(KifuRawPlayerValue.raw_value == raw,
                                                                         KifuRawPlayerValue.review_status == "pending")\
                        .update({KifuRawPlayerValue.review_metadata: None})
            if black + white != plan["counts"]["album_slots"] or raw_updated != plan["counts"]["raw_values"]:
                raise ValueError("repair update counts differ from frozen plan")
            deleted = 0
            if plan["delete_player_ids"]:
                deleted = db.query(KifuPlayer).filter(KifuPlayer.id.in_(plan["delete_player_ids"])).delete(
                    synchronize_session=False)
            if deleted != plan["counts"]["new_ids_to_delete"]:
                raise ValueError("repair player delete count differs from frozen plan")
            result = {"mode": "apply" if apply else "dry_run", "raw_values": raw_updated,
                      "album_slots_restored_to_null": black + white, "black_slots": black, "white_slots": white,
                      "provisional_ids_deleted": deleted,
                      "reused_ids_kept": plan["counts"]["reused_ids_to_keep"]}
            if apply:
                transaction.commit()
            else:
                transaction.rollback()
        except BaseException:
            transaction.rollback()
            raise
    return result
