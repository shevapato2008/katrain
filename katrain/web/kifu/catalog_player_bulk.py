"""Deterministic, full-library player review manifest and narrow decision staging.

A shared spelling, rank-stripped name, or existing album FK is a review clue,
not proof that two game records describe the same person. Only an explicit
reviewed decision can mark a raw spelling as associated with a person here.
"""

from collections import Counter, defaultdict
import hashlib
import json

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from katrain.web.core.models_db import KifuAlbum, KifuPlayer, KifuPlayerAlias, KifuRawPlayerValue
from katrain.web.kifu.catalog_preprocess_players import prepare_player_raw_values
from katrain.web.kifu.identity import normalize_alias


def _digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode("utf-8")).hexdigest()


def _catalog_rows(catalog):
    players = sorted((row["id"], row["canonical_name"]) for row in catalog["kifu_players"])
    aliases = sorted((row["player_id"], row["alias"], row["normalized_alias"])
                     for row in catalog["kifu_player_aliases"])
    if len(players) != len({row[0] for row in players}) or any(row[0] not in dict(players) for row in aliases):
        raise ValueError("invalid player catalog snapshot")
    return players, aliases


def build_player_manifest(inventory: dict, catalog: dict) -> dict:
    """Cover every black/white slot and expose every unresolved spelling."""
    prepared = prepare_player_raw_values(inventory)
    players, aliases = _catalog_rows(catalog)
    catalog_by_key = defaultdict(set)
    for player_id, name in players:
        catalog_by_key[normalize_alias(name)].add(player_id)
    for player_id, alias, _ in aliases:
        catalog_by_key[normalize_alias(alias)].add(player_id)

    columns = {name: index for index, name in enumerate(inventory["association_columns"])}
    existing_fk = defaultdict(Counter)
    linked_slots = 0
    for album in inventory["album_associations"]:
        for raw_column, id_column in (("player_black", "black_player_id"), ("player_white", "white_player_id")):
            raw, player_id = album[columns[raw_column]], album[columns[id_column]]
            if player_id is not None:
                if player_id not in dict(players):
                    raise ValueError(f"album FK refers to absent player ID {player_id}")
                existing_fk[raw][player_id] += 1
                linked_slots += 1

    records = []
    groups = defaultdict(list)
    status_counts = Counter()
    status_slots = Counter()
    category_slots = Counter()
    for row in prepared:
        raw = row["raw_value"]
        parsed = row["parsed_data"]
        base = parsed["base_name"]
        anchors = sorted(catalog_by_key[normalize_alias(base)]) if row["category"] == "readable_unlinked" else []
        fk_counts = existing_fk.get(raw, Counter())
        fk_ids = sorted(fk_counts)
        if row["category"] != "readable_unlinked":
            status = "non_person_or_corrupt_pending"
        elif len(fk_ids) > 1 or len(anchors) > 1 or (fk_ids and anchors and fk_ids != anchors):
            status = "collision_pending"
        elif fk_ids:
            status = "existing_fk_clue_pending"
        elif anchors:
            status = "catalog_spelling_clue_pending"
        else:
            status = "unanchored_pending"
        record = {
            "raw_value": raw, "base_name": base, "embedded_rank": parsed["embedded_rank"],
            "category": row["category"], "slots": parsed["slot_count"],
            "catalog_candidate_ids": anchors, "existing_fk_counts": dict(sorted(fk_counts.items())),
            "status": status,
        }
        records.append(record)
        groups[(row["category"], base)].append(raw)
        status_counts[status] += 1
        status_slots[status] += parsed["slot_count"]
        category_slots[row["category"]] += parsed["slot_count"]

    group_rows = []
    by_raw = {row["raw_value"]: row for row in records}
    for (category, base), raw_values in groups.items():
        raw_values.sort(key=lambda raw: (-by_raw[raw]["slots"], raw.encode("utf-8")))
        group_rows.append({"category": category, "base_name": base, "raw_values": raw_values,
                           "slots": sum(by_raw[raw]["slots"] for raw in raw_values),
                           "rank_variant_candidate": len(raw_values) > 1 and category == "readable_unlinked"})
    group_rows.sort(key=lambda row: (-row["slots"], row["base_name"].encode("utf-8"), row["category"]))
    slots = sum(row["slots"] for row in records)
    if slots != 2 * inventory["counts"]["all"]:
        raise ValueError("player slot count does not reconcile")
    return {
        "format": 1, "inventory_sha256": inventory["sha256"],
        "catalog_digest": _digest({"players": players, "aliases": aliases}),
        "catalog_players": players, "catalog_aliases": aliases,
        "counts": {"games": inventory["counts"]["all"], "player_slots": slots,
                   "raw_spellings": len(records), "groups": len(group_rows),
                   "existing_fk_slots": linked_slots,
                   "status_spellings": dict(sorted(status_counts.items())),
                   "status_slots": dict(sorted(status_slots.items())),
                   "category_slots": dict(sorted(category_slots.items())),
                   "rank_variant_groups": sum(row["rank_variant_candidate"] for row in group_rows)},
        "raw_values": records, "groups": group_rows,
    }


def _check_live_snapshot(db: Session, inventory: dict, manifest: dict):
    columns = {name: index for index, name in enumerate(inventory["association_columns"])}
    expected = sorted((row[columns["id"]], row[columns["player_black"]], row[columns["player_white"]],
                       row[columns["black_player_id"]], row[columns["white_player_id"]])
                      for row in inventory["album_associations"])
    actual = db.execute(select(KifuAlbum.id, KifuAlbum.player_black, KifuAlbum.player_white,
                               KifuAlbum.black_player_id, KifuAlbum.white_player_id).order_by(KifuAlbum.id)
                        .execution_options(stream_results=True))
    for old, current in zip(expected, actual, strict=True):
        if old != tuple(current):
            raise ValueError("live player album snapshot differs from frozen inventory")
    catalog = {"kifu_players": [dict(id=id_, canonical_name=name) for id_, name in
                                  db.execute(select(KifuPlayer.id, KifuPlayer.canonical_name))],
               "kifu_player_aliases": [dict(player_id=id_, alias=alias, normalized_alias=normalized)
                                       for id_, alias, normalized in db.execute(select(
                                           KifuPlayerAlias.player_id, KifuPlayerAlias.alias,
                                           KifuPlayerAlias.normalized_alias))]}
    players, aliases = _catalog_rows(catalog)
    if _digest({"players": players, "aliases": aliases}) != manifest["catalog_digest"]:
        raise ValueError("live player catalog differs from manifest")


def stage_player_decisions(inventory: dict, manifest: dict, decisions: list[dict], engine,
                           *, apply: bool = False) -> dict:
    """Preview or atomically stage independently reviewed raw-to-person decisions.

    This writes only raw-value review status and metadata, never catalog IDs,
    aliases, translations, or album foreign keys.
    """
    if manifest != build_player_manifest(inventory, {
        "kifu_players": [dict(id=id_, canonical_name=name) for id_, name in manifest["catalog_players"]],
        "kifu_player_aliases": [dict(player_id=id_, alias=alias, normalized_alias=normalized)
                                for id_, alias, normalized in manifest["catalog_aliases"]],
    }):
        raise ValueError("manifest does not match frozen inventory")
    by_raw = {row["raw_value"]: row for row in manifest["raw_values"]}
    player_names = dict(manifest["catalog_players"])
    seen = set()
    for decision in decisions:
        raw = decision.get("raw_value")
        if raw in seen or raw not in by_raw:
            raise ValueError("duplicate or unknown raw player decision")
        seen.add(raw)
        record = by_raw[raw]
        if record["status"] in ("collision_pending", "non_person_or_corrupt_pending"):
            raise ValueError(f"raw player requires separate collision/exception review: {raw!r}")
        player_id = decision.get("player_id")
        if (not isinstance(player_id, int) or player_names.get(player_id) != decision.get("canonical_name")
                or not any("CJK UNIFIED IDEOGRAPH" in __import__("unicodedata").name(char, "")
                           for char in decision["canonical_name"])):
            raise ValueError(f"decision needs an existing Chinese-canonical person ID: {raw!r}")
        if record["existing_fk_counts"] and set(record["existing_fk_counts"]) != {player_id}:
            raise ValueError(f"decision disagrees with existing player FK: {raw!r}")
        if record["catalog_candidate_ids"] and record["catalog_candidate_ids"] != [player_id]:
            raise ValueError(f"decision disagrees with catalog spelling anchor: {raw!r}")
        if not (isinstance(decision.get("source_url"), str)
                and decision["source_url"].startswith(("https://", "http://"))
                and isinstance(decision.get("reviewer"), str) and decision["reviewer"].strip()
                and isinstance(decision.get("identity_reason"), str) and decision["identity_reason"].strip()):
            raise ValueError(f"decision needs source URL, reviewer, and specific identity reason: {raw!r}")

    with Session(engine) as db:
        transaction = db.begin()
        try:
            if engine.dialect.name == "postgresql":
                db.execute(text("LOCK TABLE kifu_albums IN SHARE MODE"))
                db.execute(text("LOCK TABLE kifu_players, kifu_player_aliases, kifu_raw_player_values "
                                "IN SHARE ROW EXCLUSIVE MODE"))
            _check_live_snapshot(db, inventory, manifest)
            planned = []
            for decision in decisions:
                raw = decision["raw_value"]
                stored = db.scalar(select(KifuRawPlayerValue).where(KifuRawPlayerValue.raw_value == raw))
                if stored is None:
                    raise ValueError(f"raw player staging row missing: {raw!r}")
                metadata = {"kind": "verified_person", "player_id": decision["player_id"],
                            "canonical_name": decision["canonical_name"], "source_url": decision["source_url"],
                            "reviewer": decision["reviewer"], "identity_reason": decision["identity_reason"],
                            "inventory_sha256": manifest["inventory_sha256"]}
                if stored.review_status == "approved" and stored.review_metadata == metadata:
                    action = "unchanged"
                elif stored.review_status == "pending" and stored.review_metadata is None:
                    action = "approve"
                    stored.review_status = "approved"
                    stored.review_metadata = metadata
                else:
                    raise ValueError(f"raw player already reviewed or has metadata: {raw!r}")
                planned.append({"raw_value": raw, "player_id": decision["player_id"], "action": action})
            if apply:
                transaction.commit()
            else:
                transaction.rollback()
        except BaseException:
            transaction.rollback()
            raise
    return {"mode": "apply" if apply else "dry_run", "decisions": len(planned),
            "approved": sum(row["action"] == "approve" for row in planned),
            "unchanged": sum(row["action"] == "unchanged" for row in planned), "rows": planned}
