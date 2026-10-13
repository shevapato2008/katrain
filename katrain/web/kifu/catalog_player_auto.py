"""Conservative bulk player IDs and album links for unambiguous Han names.

The created person rows and raw mappings are provisional preprocessing data.
The original SGF names remain intact. Review holds are never linked by this
module; separately verified identity and translated display names come later.
"""

from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import re
import unicodedata

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from katrain.web.core.models_db import KifuAlbum, KifuPlayer, KifuPlayerAlias, KifuRawPlayerValue
from katrain.web.kifu.catalog_player_bulk import _catalog_rows, _check_live_snapshot, build_player_manifest
from katrain.web.kifu.identity import normalize_alias


_HAN_NAME = re.compile(r"[\u3400-\u9fff]{2,5}\Z")
_QUALIFIED = re.compile(r"(.+?)(?:[（(](?:大|小|男|女|\d{2,4})[）)]|\d{2,4})\Z")
_CATALOG_TITLE = re.compile(r"(.+?)(?:名[誉譽]|挑战者|挑戰者|棋圣|棋聖|国棋|國棋)\Z")
_TITLE = re.compile(r"(?:名[誉譽]|挑战者|挑戰者|棋圣|棋聖|国棋|國棋|上届冠军|上屆冠軍)\Z")
_YEAR = re.compile(r"(\d{4})")


def _rule_sha256() -> str:
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def _key(value: str, simplify) -> str:
    return normalize_alias(simplify(unicodedata.normalize("NFKC", value))).replace(" ", "")


def build_safe_chinese_batch(inventory: dict, catalog: dict, simplify,
                             excluded_raw_values: set[str]) -> dict:
    """Classify every exact base-name group; propose only non-colliding 2–5 Han names."""
    manifest = build_player_manifest(inventory, catalog)
    players, aliases = _catalog_rows(catalog)
    player_names = dict(players)
    catalog_keys = defaultdict(set)
    for player_id, name in players:
        catalog_keys[_key(name, simplify)].add(player_id)
    for player_id, alias, _ in aliases:
        catalog_keys[_key(alias, simplify)].add(player_id)
    catalog_related_titles = set()
    all_group_bases = {row["base_name"] for row in manifest["groups"]}
    for _, name in players:
        match = _CATALOG_TITLE.fullmatch(name)
        if match and match.group(1) in all_group_bases:
            catalog_related_titles.add(match.group(1))

    groups = {row["base_name"]: row for row in manifest["groups"]
              if row["category"] == "readable_unlinked"}
    by_raw = {row["raw_value"]: row for row in manifest["raw_values"]}
    if not excluded_raw_values.issubset(by_raw):
        raise ValueError("reviewed exclusion contains raw spelling absent from inventory")
    key_bases = defaultdict(set)
    for base in groups:
        key_bases[_key(base, simplify)].add(base)
    qualified_bases = set()
    for base in groups:
        match = _QUALIFIED.fullmatch(base)
        if match and match.group(1) in groups:
            qualified_bases.add(match.group(1))

    columns = {name: index for index, name in enumerate(inventory["association_columns"])}
    years = defaultdict(set)
    sources = defaultdict(set)
    self_play = set()
    base_fk = defaultdict(set)
    for album in inventory["album_associations"]:
        black_raw, white_raw = album[columns["player_black"]], album[columns["player_white"]]
        black = by_raw.get(black_raw, {}).get("base_name")
        white = by_raw.get(white_raw, {}).get("base_name")
        if black and black == white:
            self_play.add(black)
        for raw, fk_column in ((black_raw, "black_player_id"), (white_raw, "white_player_id")):
            record = by_raw.get(raw)
            if not record:
                continue
            base = record["base_name"]
            player_id = album[columns[fk_column]]
            if player_id is not None:
                base_fk[base].add(player_id)
            date = album[columns["date_played"]]
            match = _YEAR.match(date or "")
            if match and int(match.group(1)) != 1900:  # source placeholder date
                years[base].add(int(match.group(1)))
            for source in album[columns["sources"]]:
                sources[base].add(source[2])

    selected, holds = [], []
    hold_groups = Counter()
    hold_slots = Counter()
    for base, group in groups.items():
        key = _key(base, simplify)
        catalog_ids = sorted(catalog_keys[key])
        fk_ids = sorted(base_fk[base])
        date_years = years[base]
        reasons = []
        if not _HAN_NAME.fullmatch(base) or _TITLE.search(base):
            reasons.append("not_clear_han_person_name")
        if len(key_bases[key]) > 1:
            reasons.append("han_variant_collision")
        if len(catalog_ids) > 1:
            reasons.append("catalog_id_collision")
        if len(fk_ids) > 1 or (fk_ids and catalog_ids and fk_ids != catalog_ids):
            reasons.append("existing_fk_conflict")
        if fk_ids and not catalog_ids:
            reasons.append("existing_fk_name_mismatch")
        if catalog_ids and not _HAN_NAME.fullmatch(player_names[catalog_ids[0]]):
            reasons.append("catalog_canonical_not_clear_han")
        if base in qualified_bases:
            reasons.append("homonym_qualifier")
        if base in catalog_related_titles:
            reasons.append("catalog_related_title_id")
        if base in self_play:
            reasons.append("same_name_opponents")
        if date_years and max(date_years) - min(date_years) > 80:
            reasons.append("date_span_over_80_years")
        if any(by_raw[raw]["status"] in ("collision_pending", "non_person_or_corrupt_pending")
               for raw in group["raw_values"]):
            reasons.append("raw_value_exception")
        if any(raw in excluded_raw_values for raw in group["raw_values"]):
            reasons.append("reviewed_non_person_raw")
        # If a pre-existing FK is unique, it is safe to retain the same ID.
        # For a new ID, use the simplified Han base as the default name.
        target = catalog_ids[0] if catalog_ids else fk_ids[0] if fk_ids else None
        item = {"base_name": base, "canonical_name": simplify(base), "raw_values": group["raw_values"],
                "slots": group["slots"], "existing_player_id": target,
                "existing_fk_ids": fk_ids, "source_keys": sorted(sources[base]),
                "first_year": min(date_years) if date_years else None,
                "last_year": max(date_years) if date_years else None}
        if reasons:
            item["reasons"] = reasons
            holds.append(item)
            for reason in reasons:
                hold_groups[reason] += 1
                hold_slots[reason] += group["slots"]
        else:
            selected.append(item)
    selected.sort(key=lambda item: (-item["slots"], item["base_name"].encode("utf-8")))
    holds.sort(key=lambda item: (-item["slots"], item["base_name"].encode("utf-8")))

    catalog_duplicates = [{"normalized_name": key, "ids": sorted(ids),
                           "names": [player_names[id_] for id_ in sorted(ids)]}
                          for key, ids in catalog_keys.items() if len(ids) > 1]
    catalog_duplicates.sort(key=lambda row: row["normalized_name"].encode("utf-8"))
    canonical_duplicates = defaultdict(list)
    for player_id, name in players:
        canonical_duplicates[normalize_alias(name)].append(player_id)
    canonical_duplicates = [{"canonical_name": name, "ids": ids}
                            for name, ids in canonical_duplicates.items() if len(ids) > 1]
    canonical_duplicates.sort(key=lambda row: row["canonical_name"].encode("utf-8"))
    return {"format": 1, "rule_sha256": _rule_sha256(),
            "reviewed_exclusions": sorted(excluded_raw_values, key=lambda value: value.encode("utf-8")),
            "inventory_sha256": manifest["inventory_sha256"],
            "catalog_digest": manifest["catalog_digest"],
            "counts": {**manifest["counts"], "selected_groups": len(selected),
                       "selected_raw_spellings": sum(len(row["raw_values"]) for row in selected),
                       "selected_slots": sum(row["slots"] for row in selected),
                       "new_player_ids": sum(row["existing_player_id"] is None for row in selected),
                       "reused_player_ids": len({row["existing_player_id"] for row in selected
                                                 if row["existing_player_id"] is not None}),
                       "hold_groups": len(holds), "hold_slots": sum(row["slots"] for row in holds),
                       "hold_reason_groups": dict(sorted(hold_groups.items())),
                       "hold_reason_slots": dict(sorted(hold_slots.items())),
                       "catalog_duplicate_keys": len(catalog_duplicates),
                       "catalog_canonical_duplicate_keys": len(canonical_duplicates),
                       "catalog_non_han_canonical": sum(not _HAN_NAME.fullmatch(name) for _, name in players)},
            "selected": selected, "holds": holds, "catalog_duplicates": catalog_duplicates,
            "catalog_canonical_duplicates": canonical_duplicates,
            "manifest": manifest}


def run_safe_chinese_batch(inventory: dict, batch: dict, engine, *, apply: bool) -> dict:
    """Dry-run or atomically insert provisional IDs and fill only NULL album FKs."""
    manifest = batch["manifest"]
    if (batch["rule_sha256"] != _rule_sha256()
            or batch["inventory_sha256"] != inventory["sha256"]
            or batch["catalog_digest"] != manifest["catalog_digest"]
            or batch["counts"]["selected_slots"] != sum(row["slots"] for row in batch["selected"])):
        raise ValueError("bulk player batch is inconsistent")
    by_raw = {row["raw_value"]: row for row in manifest["raw_values"]}
    chosen_raw = [raw for item in batch["selected"] for raw in item["raw_values"]]
    if len(chosen_raw) != len(set(chosen_raw)) or any(raw not in by_raw for raw in chosen_raw):
        raise ValueError("bulk player batch has duplicate or unknown raw spelling")
    with Session(engine) as db:
        transaction = db.begin()
        try:
            if engine.dialect.name == "postgresql":
                db.execute(text("LOCK TABLE kifu_albums, kifu_players, kifu_player_aliases, "
                                "kifu_raw_player_values IN SHARE ROW EXCLUSIVE MODE"))
            _check_live_snapshot(db, inventory, manifest)
            names_to_create = sorted({row["canonical_name"] for row in batch["selected"]
                                      if row["existing_player_id"] is None})
            if len(names_to_create) != sum(row["existing_player_id"] is None for row in batch["selected"]):
                raise ValueError("new Chinese canonical names collide")
            if names_to_create:
                if engine.dialect.name == "postgresql":
                    db.execute(text(
                        "INSERT INTO kifu_players (canonical_name) "
                        "SELECT canonical_name FROM "
                        "jsonb_to_recordset(CAST(:names_json AS jsonb)) AS n(canonical_name text)"
                    ), {"names_json": json.dumps([{"canonical_name": name} for name in names_to_create],
                                                ensure_ascii=False)})
                else:
                    db.execute(KifuPlayer.__table__.insert(),
                               [{"canonical_name": name} for name in names_to_create])
            created = {name: id_ for id_, name in db.execute(
                select(KifuPlayer.id, KifuPlayer.canonical_name).where(KifuPlayer.canonical_name.in_(names_to_create))
            )} if names_to_create else {}
            if len(created) != len(names_to_create):
                raise ValueError("new person ID insertion did not reconcile")
            mapping = {}
            for item in batch["selected"]:
                player_id = item["existing_player_id"] or created[item["canonical_name"]]
                for raw in item["raw_values"]:
                    mapping[raw] = player_id
            raw_rows = {raw: (status, metadata) for raw, status, metadata in db.execute(
                select(KifuRawPlayerValue.raw_value, KifuRawPlayerValue.review_status,
                       KifuRawPlayerValue.review_metadata)
                .where(KifuRawPlayerValue.raw_value.in_(chosen_raw))
            )}
            if len(raw_rows) != len(chosen_raw):
                raise ValueError("raw player staging rows missing")
            for raw in mapping:
                status, metadata = raw_rows[raw]
                if status != "pending" or metadata is not None:
                    raise ValueError(f"raw player review row has a pre-existing decision: {raw!r}")
            columns = {name: index for index, name in enumerate(inventory["association_columns"])}
            expected_links = sum(album[columns[raw_col]] in mapping and album[columns[id_col]] is None
                                 for album in inventory["album_associations"]
                                 for raw_col, id_col in (("player_black", "black_player_id"),
                                                         ("player_white", "white_player_id")))
            if engine.dialect.name == "postgresql":
                db.execute(text("CREATE TEMP TABLE kifu_player_bulk_map "
                                "(raw_value text PRIMARY KEY, player_id integer NOT NULL) ON COMMIT DROP"))
                db.execute(text(
                    "INSERT INTO kifu_player_bulk_map (raw_value, player_id) "
                    "SELECT raw_value, player_id FROM "
                    "jsonb_to_recordset(CAST(:mapping_json AS jsonb)) "
                    "AS m(raw_value text, player_id integer)"
                ), {"mapping_json": json.dumps([{"raw_value": raw, "player_id": id_}
                                                for raw, id_ in mapping.items()], ensure_ascii=False)})
                raw_updated = db.execute(text(
                    "UPDATE kifu_raw_player_values AS r SET review_metadata = "
                    "json_build_object('kind', 'provisional_person_link', 'player_id', m.player_id, "
                    "'inventory_sha256', :inventory_sha256) "
                    "FROM kifu_player_bulk_map AS m WHERE r.raw_value = m.raw_value "
                    "AND r.review_status = 'pending' AND r.review_metadata IS NULL"
                ), {"inventory_sha256": inventory["sha256"]}).rowcount
                if raw_updated != len(mapping):
                    raise ValueError("raw player metadata update count differs from frozen batch")
                black = db.execute(text("UPDATE kifu_albums AS a SET black_player_id = m.player_id "
                                        "FROM kifu_player_bulk_map AS m WHERE a.player_black = m.raw_value "
                                        "AND a.black_player_id IS NULL")).rowcount
                white = db.execute(text("UPDATE kifu_albums AS a SET white_player_id = m.player_id "
                                        "FROM kifu_player_bulk_map AS m WHERE a.player_white = m.raw_value "
                                        "AND a.white_player_id IS NULL")).rowcount
            else:
                black = white = 0
                for raw, player_id in mapping.items():
                    updated = db.execute(KifuRawPlayerValue.__table__.update().where(
                        KifuRawPlayerValue.raw_value == raw,
                        KifuRawPlayerValue.review_status == "pending",
                        KifuRawPlayerValue.review_metadata.is_(None),
                    ).values(review_metadata={"kind": "provisional_person_link", "player_id": player_id,
                                              "inventory_sha256": inventory["sha256"]}))
                    if updated.rowcount != 1:
                        raise ValueError(f"raw player metadata changed during batch: {raw!r}")
                    black += db.query(KifuAlbum).filter(KifuAlbum.player_black == raw,
                                                          KifuAlbum.black_player_id.is_(None)).update(
                                                              {KifuAlbum.black_player_id: player_id})
                    white += db.query(KifuAlbum).filter(KifuAlbum.player_white == raw,
                                                          KifuAlbum.white_player_id.is_(None)).update(
                                                              {KifuAlbum.white_player_id: player_id})
            if black + white != expected_links:
                raise ValueError("album link update count differs from frozen inventory")
            report = {"mode": "apply" if apply else "dry_run", "new_player_ids": len(created),
                      "selected_groups": len(batch["selected"]), "raw_spellings": len(mapping),
                      "new_album_links": black + white, "black_links": black, "white_links": white,
                      "selected_slots": batch["counts"]["selected_slots"]}
            if apply:
                transaction.commit()
            else:
                transaction.rollback()
        except BaseException:
            transaction.rollback()
            raise
    return report
