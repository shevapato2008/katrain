"""Exact, reviewed eight-family player links and duplicate-ID repoints."""

from __future__ import annotations

from collections import Counter
import hashlib
import json
import unicodedata

from sqlalchemy import or_, select, text, update
from sqlalchemy.orm import Session

from katrain.web.core.models_db import (
    KifuAlbum, KifuNameResearchEvidence, KifuPlayer, KifuPlayerAlias, KifuPlayerName, KifuRawPlayerValue,
)
from katrain.web.kifu.catalog_player_second import _live_scope, _scope_rows


def _digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _normalized(value):
    return unicodedata.normalize("NFKC", value).casefold().strip()


def _catalog_preimage(db, ids):
    players = [[row.id, row.canonical_name] for row in db.execute(
        select(KifuPlayer.id, KifuPlayer.canonical_name).where(KifuPlayer.id.in_(ids)).order_by(KifuPlayer.id))]
    aliases = [[row.id, row.player_id, row.alias, row.normalized_alias] for row in db.execute(
        select(KifuPlayerAlias.id, KifuPlayerAlias.player_id, KifuPlayerAlias.alias,
               KifuPlayerAlias.normalized_alias).where(KifuPlayerAlias.player_id.in_(ids)).order_by(KifuPlayerAlias.id))]
    names = [[row.id, row.player_id, row.lang, row.display_name, row.status, row.reference_url,
              row.reference_kind, row.decision_kind, row.evidence_id] for row in db.execute(
        select(KifuPlayerName.id, KifuPlayerName.player_id, KifuPlayerName.lang,
               KifuPlayerName.display_name, KifuPlayerName.status, KifuPlayerName.reference_url,
               KifuPlayerName.reference_kind, KifuPlayerName.decision_kind, KifuPlayerName.evidence_id)
        .where(KifuPlayerName.player_id.in_(ids)).order_by(KifuPlayerName.id))]
    evidence = [[row.id, row.player_id, row.raw_player_id, row.lang, row.revision, row.candidate_name,
                 row.decision_kind, row.review_status, _digest(row.research_payload)] for row in db.execute(
        select(KifuNameResearchEvidence.id, KifuNameResearchEvidence.player_id,
               KifuNameResearchEvidence.raw_player_id, KifuNameResearchEvidence.lang,
               KifuNameResearchEvidence.revision, KifuNameResearchEvidence.candidate_name,
               KifuNameResearchEvidence.decision_kind, KifuNameResearchEvidence.review_status,
               KifuNameResearchEvidence.research_payload).where(KifuNameResearchEvidence.player_id.in_(ids))
        .order_by(KifuNameResearchEvidence.id))]
    return {"players": players, "aliases": aliases, "names": names, "evidence": evidence}


def _capture(db, inventory, review, review_sha256, environment):
    if environment not in ("test", "prod") or review.get("format") != "kifu-player-multi-id-family-review-v1":
        raise ValueError("unreviewed environment or review format")
    families = review["families"]
    if len(families) != 8 or inventory["counts"]["all"] != len(inventory["album_associations"]):
        raise ValueError("family or frozen inventory count differs")
    by_raw = {}
    old_to_family = {}
    ids = set()
    for family in families:
        survivor = family[f"survivor_id_{environment}"]
        ids.add(survivor)
        for old_id in family[f"retire_ids_{environment}"]:
            if old_id in old_to_family:
                raise ValueError("duplicate old ID")
            old_to_family[old_id] = family
            ids.add(old_id)
        for raw in family["safe_exact_raw"]:
            if raw["raw_value"] in by_raw or not family["evidence_url"].startswith("https://"):
                raise ValueError("duplicate reviewed raw or missing identity evidence")
            by_raw[raw["raw_value"]] = family
    held = {item["raw_value"] for family in families for item in family["hold_exact_raw"]}
    if held & by_raw.keys():
        raise ValueError("hold/raw collision")
    frozen = _scope_rows(inventory, {raw: raw for raw in by_raw})
    live = _live_scope(db, {raw: raw for raw in by_raw})
    if set(frozen) != set(by_raw) or set(live) != set(by_raw):
        raise ValueError("reviewed exact raw scope absent")
    catalog = _catalog_preimage(db, ids)
    players = {row[0]: row[1] for row in catalog["players"]}
    if set(players) != ids:
        raise ValueError("reviewed player ID absent")
    for family in families:
        survivor = family[f"survivor_id_{environment}"]
        prior = family["catalog_refs_live"][environment][0]["canonical_name"]
        if players[survivor] != prior:
            raise ValueError(f"survivor canonical preimage changed: {survivor}")
        for old in family[f"retire_ids_{environment}"]:
            expected = next(x["canonical_name"] for x in family["catalog_refs_live"][environment] if x["id"] == old)
            if players[old] != expected:
                raise ValueError(f"old catalog canonical preimage changed: {old}")
    # No reviewed target name may resolve to a different identity, including translations.
    rename_families = [f for f in families if players[f[f"survivor_id_{environment}"]] != f["canonical_chinese_name"]]
    if len(rename_families) != 2:
        raise ValueError("expected exactly two canonical corrections")
    for family in rename_families:
        survivor = family[f"survivor_id_{environment}"]
        desired = family["canonical_chinese_name"]
        old_name = players[survivor]
        if db.scalar(select(KifuPlayer.id).where(KifuPlayer.canonical_name == desired, KifuPlayer.id != survivor).limit(1)):
            raise ValueError(f"canonical collision: {desired}")
        for spelling in (desired, old_name):
            norm = _normalized(spelling)
            if db.scalar(select(KifuPlayerAlias.id).where(KifuPlayerAlias.normalized_alias == norm,
                                                            KifuPlayerAlias.player_id != survivor).limit(1)):
                raise ValueError(f"alias collision: {spelling}")
            if db.scalar(select(KifuPlayerName.id).where(KifuPlayerName.display_name == spelling,
                                                          KifuPlayerName.player_id != survivor).limit(1)):
                raise ValueError(f"translation collision: {spelling}")
            if db.scalar(select(KifuNameResearchEvidence.id).where(
                    KifuNameResearchEvidence.candidate_name == spelling,
                    KifuNameResearchEvidence.player_id.is_not(None),
                    KifuNameResearchEvidence.player_id != survivor,
                    KifuNameResearchEvidence.review_status == "approved").limit(1)):
                raise ValueError(f"approved evidence collision: {spelling}")
    for raw, family in by_raw.items():
        survivor = family[f"survivor_id_{environment}"]
        if db.scalar(select(KifuPlayer.id).where(KifuPlayer.canonical_name == raw,
                                                  KifuPlayer.id != survivor).limit(1)):
            raise ValueError(f"raw matches a different player canonical: {raw}")
        if db.scalar(select(KifuPlayerAlias.id).where(KifuPlayerAlias.normalized_alias == _normalized(raw),
                                                       KifuPlayerAlias.player_id != survivor).limit(1)):
            raise ValueError(f"raw alias belongs to a different player: {raw}")
    new_slots = []
    for raw, family in by_raw.items():
        expected = frozen[raw]
        actual = live[raw]
        reviewed_count = next(item["slots"] for item in family["safe_exact_raw"] if item["raw_value"] == raw)
        if len(expected) != reviewed_count or [row[:-1] for row in expected] != [row[:-1] for row in actual]:
            raise ValueError(f"frozen/live scope differs: {raw}")
        if any(row[-1] is not None for row in actual):
            raise ValueError(f"new slot is already linked: {raw}")
        survivor = family[f"survivor_id_{environment}"]
        for row in actual:
            album = db.get(KifuAlbum, row[0])
            opponent_id = album.white_player_id if row[1] == "black" else album.black_player_id
            opponent_raw = row[5] if row[1] == "black" else row[4]
            if opponent_id == survivor or (opponent_raw in by_raw and by_raw[opponent_raw] is family):
                raise ValueError(f"same-person opponent in reviewed slot: {row[:3]}")
        new_slots.extend([[*row, survivor] for row in actual])
    # Capture every old-ID album FK, then compare each row against the frozen
    # full raw/date/source scope; only the reviewed 20 slots may be repointed.
    old_ids = set(old_to_family)
    old_album_rows = db.execute(select(KifuAlbum.id, KifuAlbum.player_black, KifuAlbum.player_white,
                                       KifuAlbum.black_player_id, KifuAlbum.white_player_id).where(or_(
        KifuAlbum.black_player_id.in_(old_ids), KifuAlbum.white_player_id.in_(old_ids)))).all()
    old_raws = {raw for _, black, white, black_id, white_id in old_album_rows
                for raw, player_id in ((black, black_id), (white, white_id)) if player_id in old_ids}
    old_frozen = _scope_rows(inventory, {raw: raw for raw in old_raws})
    old_live = _live_scope(db, {raw: raw for raw in old_raws})
    old_slots = []
    for raw in old_raws:
        if [row[:-1] for row in old_frozen[raw]] != [row[:-1] for row in old_live[raw]]:
            raise ValueError(f"old FK raw scope diverged: {raw}")
        for row in old_live[raw]:
            if row[-1] in old_ids:
                family = old_to_family[row[-1]]
                album = db.get(KifuAlbum, row[0])
                opponent_id = album.white_player_id if row[1] == "black" else album.black_player_id
                if opponent_id == family[f"survivor_id_{environment}"] or opponent_id in family[f"retire_ids_{environment}"]:
                    raise ValueError(f"same-person opponent on old FK: {row[:3]}")
                old_slots.append([*row, family[f"survivor_id_{environment}"]])
    old_slots.sort()
    new_slots.sort()
    for family in families:
        count = sum(row[-2] in family[f"retire_ids_{environment}"] for row in old_slots)
        if count != family["existing_fk_repoint_slots_each_environment"]:
            raise ValueError(f"old FK count differs: {family['family']}")
    if len(new_slots) != 504 or len(old_slots) != 20:
        raise ValueError("reviewed 504/20 slot count differs")
    held_scope = _live_scope(db, {raw: raw for raw in held})
    if sum(len(value) for value in held_scope.values()) != 8 or any(row[-1] is not None for value in held_scope.values() for row in value):
        raise ValueError("malformed Cho hold scope changed")
    # Verify protected Iwata/Maeda legacy slots and preserve their FK.
    protected_spec = {"岩田达明": [(32802, "black"), (32803, "white"), (32873, "white"), (32882, "black"),
                                 (136112, "black"), (140851, "black"), (140852, "white"), (140853, "black")],
                      "前田陈尔": [(123996, "white")]}
    protected = []
    for family in families:
        for album_id, side in protected_spec.get(family["family"], []):
            album = db.get(KifuAlbum, album_id)
            current = album.black_player_id if side == "black" else album.white_player_id
            if current != family[f"survivor_id_{environment}"]:
                raise ValueError(f"protected legacy FK changed: {album_id}/{side}")
            protected.append([album_id, side, album.player_black if side == "black" else album.player_white,
                              album.date_played, current])
    raw_rows = [[row.id, row.raw_value, row.review_status, row.review_metadata] for row in db.execute(
        select(KifuRawPlayerValue.id, KifuRawPlayerValue.raw_value, KifuRawPlayerValue.review_status,
               KifuRawPlayerValue.review_metadata).where(KifuRawPlayerValue.raw_value.in_(by_raw)).order_by(KifuRawPlayerValue.id))]
    if {row[1] for row in raw_rows} != set(by_raw) or any(row[2:] != ["pending", None] for row in raw_rows):
        raise ValueError("new raw review metadata differs")
    all_metadata = [[row.id, row.raw_value, row.review_status, row.review_metadata] for row in db.execute(
        select(KifuRawPlayerValue.id, KifuRawPlayerValue.raw_value, KifuRawPlayerValue.review_status,
               KifuRawPlayerValue.review_metadata)) if isinstance(row.review_metadata, dict)
        and row.review_metadata.get("player_id") in old_ids]
    if {row[1] for row in all_metadata} - old_raws:
        raise ValueError("old-ID metadata refers to unreviewed raw")
    old_raw_to_ids = {raw: {row[-1] for row in old_live[raw] if row[-1] in old_ids} for raw in old_raws}
    for _, raw, _, metadata in all_metadata:
        if metadata["player_id"] not in old_raw_to_ids[raw]:
            raise ValueError("metadata player ID differs from old album FK")
    plan = {"format": "kifu-player-family-exact-v1", "environment": environment,
            "review_sha256": review_sha256, "inventory_sha256": inventory["sha256"],
            "catalog": catalog, "new_slots": new_slots, "old_slots": old_slots,
            "held_slots": sorted([row[:4] for value in held_scope.values() for row in value]),
            "protected_slots": sorted(protected), "new_raw_rows": raw_rows,
            "old_metadata_rows": sorted(all_metadata),
            "counts": {"games": inventory["counts"]["all"], "families": 8, "new_fk_slots": 504,
                       "repoint_fk_slots": 20, "canonical_corrections": 2, "new_player_ids": 0,
                       "metadata_repoints": len(all_metadata), "held_slots": 8}}
    return plan


def capture_family_plan(inventory, review, review_sha256, environment, engine):
    with Session(engine) as db:
        return _capture(db, inventory, review, review_sha256, environment)


def run_family_plan(inventory, review, review_sha256, environment, plan, engine, *, apply=False,
                    approved_plan_sha256=None, plan_sha256=None):
    if plan.get("format") != "kifu-player-family-exact-v1" or plan.get("environment") != environment:
        raise ValueError("plan environment/format differs")
    if apply and (not plan_sha256 or approved_plan_sha256 != plan_sha256):
        raise ValueError("apply requires separate exact plan SHA approval")
    with Session(engine) as db:
        transaction = db.begin()
        try:
            if engine.dialect.name == "postgresql":
                db.execute(text("LOCK TABLE kifu_albums, kifu_album_sources, kifu_sources, kifu_players, "
                                "kifu_player_aliases, kifu_player_names, kifu_name_research_evidence, "
                                "kifu_raw_player_values IN SHARE ROW EXCLUSIVE MODE"))
            if _capture(db, inventory, review, review_sha256, environment) != plan:
                raise ValueError("family live preimages changed after capture")
            players = {row[0]: row[1] for row in plan["catalog"]["players"]}
            aliases = {(row[1], row[3]) for row in plan["catalog"]["aliases"]}
            for family in review["families"]:
                survivor = family[f"survivor_id_{environment}"]
                desired = family["canonical_chinese_name"]
                if players[survivor] == desired:
                    continue
                old_name = players[survivor]
                if (survivor, _normalized(old_name)) not in aliases:
                    db.add(KifuPlayerAlias(player_id=survivor, alias=old_name,
                                           normalized_alias=_normalized(old_name)))
                changed = db.execute(update(KifuPlayer).where(KifuPlayer.id == survivor,
                    KifuPlayer.canonical_name == old_name).values(canonical_name=desired))
                if changed.rowcount != 1:
                    raise ValueError(f"canonical compare-and-swap failed: {survivor}")
            db.flush()
            for row in plan["new_slots"] + plan["old_slots"]:
                album_id, side, raw, date, black, white, duplicate, sources, old_fk, new_fk = row
                album = db.get(KifuAlbum, album_id)
                if (album.date_played != date or album.player_black != black or album.player_white != white
                        or album.duplicate_of_id != duplicate):
                    raise ValueError(f"album preimage changed: {album_id}")
                field = KifuAlbum.black_player_id if side == "black" else KifuAlbum.white_player_id
                raw_field = KifuAlbum.player_black if side == "black" else KifuAlbum.player_white
                result = db.execute(update(KifuAlbum).where(KifuAlbum.id == album_id, raw_field == raw,
                                                             field == old_fk).values({field: new_fk}))
                if result.rowcount != 1:
                    raise ValueError(f"slot compare-and-swap failed: {album_id}/{side}")
            family_by_raw = {item["raw_value"]: family for family in review["families"]
                             for item in family["safe_exact_raw"]}
            for raw_id, raw, status, metadata in plan["new_raw_rows"]:
                family = family_by_raw[raw]
                new_metadata = {"kind": "reviewed_family_exact_link", "player_id": family[f"survivor_id_{environment}"],
                                "identity_evidence_url": family["evidence_url"], "review_sha256": review_sha256}
                result = db.execute(update(KifuRawPlayerValue).where(KifuRawPlayerValue.id == raw_id,
                    KifuRawPlayerValue.raw_value == raw, KifuRawPlayerValue.review_status == "pending",
                    KifuRawPlayerValue.review_metadata.is_(None)).values(
                        review_status="approved", review_metadata=new_metadata))
                if result.rowcount != 1:
                    raise ValueError(f"new raw metadata changed: {raw}")
            old_to_target = {old: family[f"survivor_id_{environment}"] for family in review["families"]
                             for old in family[f"retire_ids_{environment}"]}
            for raw_id, raw, status, metadata in plan["old_metadata_rows"]:
                revised = dict(metadata)
                revised["player_id"] = old_to_target[metadata["player_id"]]
                result = db.execute(update(KifuRawPlayerValue).where(KifuRawPlayerValue.id == raw_id,
                    KifuRawPlayerValue.raw_value == raw, KifuRawPlayerValue.review_status == status)
                    .values(review_metadata=revised))
                if result.rowcount != 1:
                    raise ValueError(f"old metadata compare-and-swap failed: {raw}")
            result = {"mode": "apply" if apply else "dry_run", **plan["counts"]}
            if apply:
                transaction.commit()
            else:
                transaction.rollback()
            return result
        except BaseException:
            transaction.rollback()
            raise
