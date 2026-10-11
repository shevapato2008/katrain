"""Preimage-checked second player batch from an exact reviewed raw-name allowlist.

The seven legacy duplicate IDs retain their translation rows for later review.
Only game links, reviewed raw mappings, three canonical names, and one new ID
are changed. The original SGF spellings are never edited.
"""

from collections import Counter, defaultdict
import hashlib
import json

from sqlalchemy import or_, select, text
from sqlalchemy.orm import Session

from katrain.web.core.models_db import (
    KifuAlbum, KifuAlbumSource, KifuNameResearchEvidence, KifuPlayer, KifuPlayerAlias,
    KifuPlayerName, KifuRawPlayerValue, KifuSource,
)


def _digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode("utf-8")).hexdigest()


def _scope_rows(inventory, raw_to_group):
    columns = {name: index for index, name in enumerate(inventory["association_columns"])}
    groups = defaultdict(list)
    for row in inventory["album_associations"]:
        for side, raw_col, fk_col in (("black", "player_black", "black_player_id"),
                                       ("white", "player_white", "white_player_id")):
            raw = row[columns[raw_col]]
            if raw in raw_to_group:
                groups[raw_to_group[raw]].append([
                    row[columns["id"]], side, raw, row[columns["date_played"]],
                    row[columns["player_black"]], row[columns["player_white"]],
                    row[columns["duplicate_of_id"]], sorted(row[columns["sources"]]),
                    row[columns[fk_col]],
                ])
    return {name: sorted(rows) for name, rows in groups.items()}


def _live_scope(db, raw_to_group):
    raw_values = list(raw_to_group)
    albums = db.execute(select(KifuAlbum.id, KifuAlbum.duplicate_of_id, KifuAlbum.player_black,
                               KifuAlbum.player_white, KifuAlbum.date_played,
                               KifuAlbum.black_player_id, KifuAlbum.white_player_id).where(or_(
                                   KifuAlbum.player_black.in_(raw_values), KifuAlbum.player_white.in_(raw_values)
                               ))).all()
    sources = defaultdict(list)
    source_rows = db.execute(select(KifuAlbumSource.id, KifuAlbumSource.album_id, KifuAlbumSource.source_id,
                                    KifuSource.source_key, KifuAlbumSource.origin_path,
                                    KifuAlbumSource.match_method).join(KifuSource).join(
                                        KifuAlbum, KifuAlbum.id == KifuAlbumSource.album_id).where(or_(
                                            KifuAlbum.player_black.in_(raw_values),
                                            KifuAlbum.player_white.in_(raw_values)
                                        )).order_by(KifuAlbumSource.id))
    for source_id, album_id, dataset_id, key, path, method in source_rows:
        sources[album_id].append([source_id, dataset_id, key, path, method])
    groups = defaultdict(list)
    for album_id, duplicate, black, white, date, black_id, white_id in albums:
        for side, raw, player_id in (("black", black, black_id), ("white", white, white_id)):
            if raw in raw_to_group:
                groups[raw_to_group[raw]].append([
                    album_id, side, raw, date, black, white, duplicate,
                    sorted(sources[album_id]), player_id,
                ])
    return {name: sorted(rows) for name, rows in groups.items()}


def _name_rows(db, ids):
    if not ids:
        return []
    result = db.execute(select(KifuPlayerName.id, KifuPlayerName.player_id, KifuPlayerName.lang,
                               KifuPlayerName.display_name, KifuPlayerName.status,
                               KifuPlayerName.reference_url, KifuPlayerName.reference_kind,
                               KifuPlayerName.verified_at, KifuPlayerName.decision_kind,
                               KifuPlayerName.generation_rule_version, KifuPlayerName.revision,
                               KifuPlayerName.evidence_id).where(KifuPlayerName.player_id.in_(ids)).order_by(
                                   KifuPlayerName.player_id, KifuPlayerName.lang))
    return [[value.isoformat() if hasattr(value, "isoformat") else value for value in row] for row in result]


def _capture(db, inventory, reviewed, original_catalog, review_sha256):
    if reviewed.get("format") != "kifu-player-second-batch-review-v2" or len(reviewed["decisions"]) != 20:
        raise ValueError("second-batch review format or group count differs")
    if inventory["counts"]["all"] != len(inventory["album_associations"]):
        raise ValueError("frozen game count differs")
    old_names = {row["id"]: row["canonical_name"] for row in original_catalog["kifu_players"]}
    names = set()
    raw_to_group = {}
    excluded = set()
    for decision in reviewed["decisions"]:
        name = decision["canonical_chinese_name"]
        if name in names or decision["reviewed_name_identity"] != "same_person_for_allowlisted_raw_values":
            raise ValueError("duplicate or unreviewed group")
        names.add(name)
        if decision["game_fk_decision"] != "approved_after_fresh_snapshot_preflight":
            raise ValueError(f"game FK decision pending: {name}")
        target = decision["proposed_target"]
        old_id = target["player_id"]
        if old_id is not None and old_names.get(old_id) != target["current_canonical_name"]:
            raise ValueError(f"original catalog target differs: {name}")
        if target["new_canonical_name"] != name:
            raise ValueError(f"non-Chinese target differs: {name}")
        for duplicate_id in decision["duplicate_catalog_ids_to_fold"]:
            if duplicate_id not in old_names:
                raise ValueError(f"original duplicate ID absent: {duplicate_id}")
        for item in decision["raw_allowlist"]:
            raw = item["raw_value"]
            if raw in raw_to_group or item["name_identity_decision"] != "same_person":
                raise ValueError("duplicate or unreviewed raw spelling")
            raw_to_group[raw] = name
        excluded.update(item["raw_value"] for item in decision["excluded_prefix_raw_values"])
    if set(raw_to_group) & excluded or len(raw_to_group) != reviewed["summary"]["raw_allowlist_values"]:
        raise ValueError("allowlist/exclusion collision or count differs")

    frozen = _scope_rows(inventory, raw_to_group)
    live = _live_scope(db, raw_to_group)
    if set(frozen) != names or set(live) != names:
        raise ValueError("reviewed group missing from frozen or live game scope")
    players = defaultdict(list)
    for player_id, canonical in db.execute(select(KifuPlayer.id, KifuPlayer.canonical_name)):
        players[canonical].append(player_id)
    raw_rows = {raw: (status, metadata) for raw, status, metadata in db.execute(select(
        KifuRawPlayerValue.raw_value, KifuRawPlayerValue.review_status,
        KifuRawPlayerValue.review_metadata).where(KifuRawPlayerValue.raw_value.in_(raw_to_group)))}
    if set(raw_rows) != set(raw_to_group) or any(row != ("pending", None) for row in raw_rows.values()):
        raise ValueError("reviewed raw staging preimage differs")
    entries = []
    for decision in reviewed["decisions"]:
        name = decision["canonical_chinese_name"]
        target = decision["proposed_target"]
        old_name = target["current_canonical_name"]
        if old_name is None:
            if players[name]:
                raise ValueError(f"new target already exists: {name}")
            target_id = None
        else:
            if len(players[old_name]) != 1:
                raise ValueError(f"target name is absent or ambiguous: {old_name}")
            target_id = players[old_name][0]
            if old_name != name and players[name]:
                raise ValueError(f"renamed target already exists: {name}")
        duplicate_ids = []
        for original_id in decision["duplicate_catalog_ids_to_fold"]:
            duplicate_name = old_names[original_id]
            if len(players[duplicate_name]) != 1:
                raise ValueError(f"duplicate name is absent or ambiguous: {duplicate_name}")
            duplicate_ids.append(players[duplicate_name][0])
        expected = frozen[name]
        actual = live[name]
        if [row[:-1] for row in expected] != [row[:-1] for row in actual]:
            raise ValueError(f"live album/date/source scope differs: {name}")
        if len(expected) != decision["allowlisted_slots"] or len(expected) != decision["scope_review"]["slot_count"]:
            raise ValueError(f"reviewed scope count differs: {name}")
        counts = Counter(row[2] for row in expected)
        if counts != Counter({row["raw_value"]: row["slots"] for row in decision["raw_allowlist"]}):
            raise ValueError(f"reviewed exact raw counts differ: {name}")
        source_counts = Counter(key for row in expected for _, _, key, _, _ in row[7])
        if source_counts != decision["scope_review"]["source_key_counts"]:
            raise ValueError(f"reviewed source scope differs: {name}")
        allowed_ids = {None, target_id, *duplicate_ids}
        if any(row[-1] not in allowed_ids for row in actual):
            raise ValueError(f"conflicting live FK in reviewed scope: {name}")
        if any(row[-1] in duplicate_ids for row in actual):
            raise ValueError(f"old duplicate FK requires separate migration: {name}")
        if (sum(row[-1] == target_id for row in actual if target_id is not None)
                != decision["scope_review"].get("existing_target_fk_slots", 0)):
            raise ValueError(f"reviewed existing FK count differs: {name}")
        # No reviewed game may become a same-person black/white pairing.
        own_raw = {item["raw_value"] for item in decision["raw_allowlist"]}
        if any(row[4] in own_raw and row[5] in own_raw for row in actual):
            raise ValueError(f"self-opponent in reviewed scope: {name}")
        # Existing references outside this allowlist must not be rewritten.
        ref_counts = {}
        for duplicate_id in duplicate_ids:
            ref_counts[str(duplicate_id)] = {
                "album_black": db.scalar(select(text("count(*)")).select_from(KifuAlbum).where(
                    KifuAlbum.black_player_id == duplicate_id)),
                "album_white": db.scalar(select(text("count(*)")).select_from(KifuAlbum).where(
                    KifuAlbum.white_player_id == duplicate_id)),
                "aliases": db.scalar(select(text("count(*)")).select_from(KifuPlayerAlias).where(
                    KifuPlayerAlias.player_id == duplicate_id)),
                "evidence": db.scalar(select(text("count(*)")).select_from(KifuNameResearchEvidence).where(
                    KifuNameResearchEvidence.player_id == duplicate_id)),
            }
        if any(count for refs in ref_counts.values() for count in refs.values()):
            raise ValueError(f"old duplicate ID has new references requiring review: {name}")
        name_rows = _name_rows(db, [target_id, *duplicate_ids] if target_id is not None else duplicate_ids)
        entries.append({
            "name": name, "action": target["action"], "target_id": target_id,
            "old_canonical_name": old_name, "duplicate_ids_held": duplicate_ids,
            "duplicate_reference_counts": ref_counts, "translation_preimages_held": name_rows,
            "raw_values": sorted(own_raw, key=lambda value: value.encode("utf-8")),
            "slots": [[row[0], row[1], row[2], row[-1]] for row in actual],
            "scope_sha256": _digest([row[:-1] for row in actual]),
            "frozen_existing_fk_slots": sum(row[-1] is not None for row in expected),
            "live_existing_target_fk_slots": sum(row[-1] == target_id for row in actual if target_id is not None),
            "live_existing_duplicate_fk_slots": sum(row[-1] in duplicate_ids for row in actual),
            "null_slots_to_link": sum(row[-1] is None for row in actual),
        })
    if sum(len(row["slots"]) for row in entries) != reviewed["summary"]["raw_allowlist_slots"]:
        raise ValueError("second-batch reviewed total scope differs")
    return {
        "format": 1, "review_sha256": review_sha256,
        "review_inventory_file_sha256": reviewed["input"]["inventory_sha256"],
        "frozen_inventory_sha256": inventory["sha256"], "groups": entries,
        "counts": {"games": inventory["counts"]["all"], "groups": len(entries),
                   "raw_values": len(raw_to_group), "reviewed_slots": sum(len(row["slots"]) for row in entries),
                   "new_fk_slots": sum(row["null_slots_to_link"] for row in entries),
                   "existing_target_fk_slots": sum(row["live_existing_target_fk_slots"] for row in entries),
                   "existing_duplicate_fk_slots": sum(row["live_existing_duplicate_fk_slots"] for row in entries),
                   "renames": sum(row["action"] == "rename_player" for row in entries),
                   "new_ids": sum(row["action"] == "create_player" for row in entries),
                   "duplicate_ids_held": sum(len(row["duplicate_ids_held"]) for row in entries)},
    }


def capture_second_plan(inventory, reviewed, original_catalog, review_sha256, engine):
    """Read and compare every reviewed exact slot to a current database snapshot."""
    with Session(engine) as db:
        return _capture(db, inventory, reviewed, original_catalog, review_sha256)


def run_second_plan(inventory, reviewed, original_catalog, review_sha256, plan, engine, *, apply=False):
    """Recheck full preimages under locks and dry-run or commit one atomic batch."""
    with Session(engine) as db:
        transaction = db.begin()
        try:
            if engine.dialect.name == "postgresql":
                db.execute(text("LOCK TABLE kifu_albums, kifu_album_sources, kifu_sources, kifu_players, "
                                "kifu_player_aliases, kifu_player_names, kifu_name_research_evidence, "
                                "kifu_raw_player_values IN SHARE ROW EXCLUSIVE MODE"))
            if _capture(db, inventory, reviewed, original_catalog, review_sha256) != plan:
                raise ValueError("second-batch live preimages changed after capture")
            mapping = {}
            renamed = created = 0
            for group in plan["groups"]:
                player_id = group["target_id"]
                if group["action"] == "create_player":
                    person = KifuPlayer(canonical_name=group["name"])
                    db.add(person)
                    db.flush()
                    player_id = person.id
                    created += 1
                elif group["action"] == "rename_player":
                    updated = db.query(KifuPlayer).filter(
                        KifuPlayer.id == player_id,
                        KifuPlayer.canonical_name == group["old_canonical_name"]
                    ).update({KifuPlayer.canonical_name: group["name"]})
                    if updated != 1:
                        raise ValueError("canonical rename preimage changed")
                    renamed += 1
                elif group["action"] != "retain_player":
                    raise ValueError("unknown target action")
                for raw in group["raw_values"]:
                    mapping[raw] = player_id
            if engine.dialect.name == "postgresql":
                db.execute(text("CREATE TEMP TABLE kifu_player_second_map "
                                "(raw_value text PRIMARY KEY, player_id integer NOT NULL) ON COMMIT DROP"))
                db.execute(text("INSERT INTO kifu_player_second_map (raw_value, player_id) "
                                "SELECT raw_value, player_id FROM "
                                "jsonb_to_recordset(CAST(:payload AS jsonb)) AS m(raw_value text, player_id integer)"),
                           {"payload": json.dumps([{"raw_value": raw, "player_id": id_}
                                                   for raw, id_ in mapping.items()], ensure_ascii=False)})
                black = db.execute(text("UPDATE kifu_albums AS a SET black_player_id = m.player_id "
                                        "FROM kifu_player_second_map AS m WHERE a.player_black = m.raw_value "
                                        "AND a.black_player_id IS NULL")).rowcount
                white = db.execute(text("UPDATE kifu_albums AS a SET white_player_id = m.player_id "
                                        "FROM kifu_player_second_map AS m WHERE a.player_white = m.raw_value "
                                        "AND a.white_player_id IS NULL")).rowcount
                raw_updated = db.execute(text(
                    "UPDATE kifu_raw_player_values AS r SET review_status = 'approved', "
                    "review_metadata = jsonb_build_object('kind','reviewed_person_link',"
                    "'review_sha256',:review_sha256,'player_id',m.player_id)::json "
                    "FROM kifu_player_second_map AS m WHERE r.raw_value = m.raw_value "
                    "AND r.review_status = 'pending' AND r.review_metadata IS NULL"
                ), {"review_sha256": review_sha256}).rowcount
            else:
                black = white = raw_updated = 0
                for raw, player_id in mapping.items():
                    black += db.query(KifuAlbum).filter(KifuAlbum.player_black == raw,
                                                        KifuAlbum.black_player_id.is_(None)).update(
                                                            {KifuAlbum.black_player_id: player_id})
                    white += db.query(KifuAlbum).filter(KifuAlbum.player_white == raw,
                                                        KifuAlbum.white_player_id.is_(None)).update(
                                                            {KifuAlbum.white_player_id: player_id})
                    raw_updated += db.query(KifuRawPlayerValue).filter(
                        KifuRawPlayerValue.raw_value == raw,
                        KifuRawPlayerValue.review_status == "pending",
                        KifuRawPlayerValue.review_metadata.is_(None)
                    ).update({KifuRawPlayerValue.review_status: "approved",
                              KifuRawPlayerValue.review_metadata: {
                                  "kind": "reviewed_person_link", "review_sha256": review_sha256,
                                  "player_id": player_id,
                              }})
            if (black + white != plan["counts"]["new_fk_slots"]
                    or raw_updated != plan["counts"]["raw_values"]
                    or renamed != plan["counts"]["renames"] or created != plan["counts"]["new_ids"]):
                raise ValueError("second-batch changed-row counts differ from plan")
            result = {"mode": "apply" if apply else "dry_run", "black_fk_slots": black,
                      "white_fk_slots": white, "new_fk_slots": black + white,
                      "raw_values_approved": raw_updated, "canonical_names_renamed": renamed,
                      "new_player_ids": created, "duplicate_ids_held": plan["counts"]["duplicate_ids_held"]}
            if apply:
                transaction.commit()
            else:
                transaction.rollback()
            return result
        except BaseException:
            transaction.rollback()
            raise
