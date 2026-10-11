"""Reviewed exact Latin player batches with environment-specific target IDs."""

import json

from sqlalchemy import or_, select, text
from sqlalchemy.orm import Session

from katrain.web.core.models_db import KifuAlbum, KifuPlayer, KifuPlayerAlias, KifuRawPlayerValue
from katrain.web.kifu.catalog_player_second import _digest, _live_scope, _scope_rows


def _capture(db, inventory, allowlist, allowlist_sha256, environment):
    if environment not in ("test", "prod"):
        raise ValueError("environment must be test or prod")
    reviewed_formats = {
        "kifu-player-nonhan-first17-exact-allowlist-v1": 17,
        "kifu-player-nonhan-next18-exact-allowlist-v1": 18,
        "kifu-player-nonhan-ranks-41-60-safe15-exact-allowlist-v1": 15,
        "kifu-player-nonhan-ranks-61-80-exact-allowlist-v1": 15,
        "kifu-player-nonhan-ranks-81-100-exact-allowlist-v1": 14,
        "kifu-player-nonhan-ranks-101-120-safe14-exact-allowlist-v1": 14,
        "kifu-player-nonhan-ranks-121-140-exact-allowlist-v1": 16,
        "kifu-player-nonhan-ranks-141-160-exact-allowlist-v1": 17,
        "kifu-player-nonhan-ranks-161-180-corrected17-exact-allowlist-v1": 17,
        "kifu-player-nonhan-ranks-181-200-exact-allowlist-v1": 18,
        "kifu-player-nonhan-ranks-201-220-exact-allowlist-v1": 17,
        "kifu-player-nonhan-ranks-221-240-safe18-exact-allowlist-v1": 18,
        "kifu-player-nonhan-ranks-241-260-corrected17-exact-allowlist-v1": 17,
        "kifu-player-nonhan-ranks-261-280-safe17-exact-allowlist-v1": 17,
        "kifu-player-nonhan-ranks-281-300-corrected18-exact-allowlist-v1": 18,
        "kifu-player-nonhan-ranks-301-320-exact-allowlist-v1": 16,
        "kifu-player-nonhan-ranks-321-340-safe17-exact-allowlist-v1": 17,
        "kifu-player-nonhan-ranks-341-360-exact-allowlist-v1": 16,
        "kifu-player-nonhan-ranks-361-380-exact-allowlist-v1": 15,
        "kifu-player-nonhan-ranks-381-400-exact-allowlist-v1": 17,
    }
    expected_rows = reviewed_formats.get(allowlist.get("format"))
    if (expected_rows is None or len(allowlist["rows"]) != expected_rows
            or allowlist["summary"]["raw_values"] != expected_rows):
        raise ValueError("non-Han review format or row count differs")
    if inventory["counts"]["all"] != len(inventory["album_associations"]):
        raise ValueError("frozen game count differs")
    by_raw = {}
    new_names = set()
    for row in allowlist["rows"]:
        raw = row["raw_value"]
        if raw in by_raw or not row["identity_evidence_url"].startswith("https://"):
            raise ValueError("duplicate raw or missing identity source")
        by_raw[raw] = row
        target_id = row[f"target_player_id_{environment}"]
        catalog_action = row.get("catalog_action")
        if catalog_action is not None and catalog_action != (
                "create_catalog_player" if row["new_player_needed"] else "retain_observed_id"):
            raise ValueError(f"catalog rename or unsupported action needs separate review: {raw}")
        if row["new_player_needed"]:
            if target_id is not None or row["chinese_name"] in new_names:
                raise ValueError("new person needs one fresh Chinese name")
            new_names.add(row["chinese_name"])
        elif not isinstance(target_id, int):
            raise ValueError("existing person target ID missing")
        if row["expected_existing_fk"] != "NULL":
            raise ValueError("this batch requires every current slot to be unlinked")
    frozen = _scope_rows(inventory, {raw: raw for raw in by_raw})
    live = _live_scope(db, {raw: raw for raw in by_raw})
    if set(frozen) != set(by_raw) or set(live) != set(by_raw):
        raise ValueError("reviewed raw missing from frozen or live scope")
    staged = {raw: (status, metadata) for raw, status, metadata in db.execute(select(
        KifuRawPlayerValue.raw_value, KifuRawPlayerValue.review_status,
        KifuRawPlayerValue.review_metadata).where(KifuRawPlayerValue.raw_value.in_(by_raw)))}
    if set(staged) != set(by_raw) or any(value != ("pending", None) for value in staged.values()):
        raise ValueError("raw staging row already reviewed or missing")
    if new_names:
        if db.scalar(select(KifuPlayer.id).where(KifuPlayer.canonical_name.in_(new_names)).limit(1)) is not None:
            raise ValueError("new Chinese canonical name already exists")
        if db.scalar(select(KifuPlayerAlias.id).where(KifuPlayerAlias.alias.in_(new_names)).limit(1)) is not None:
            raise ValueError("new Chinese canonical name is an existing alias")
    opponent_fks = {album_id: (black_id, white_id) for album_id, black_id, white_id in db.execute(select(
        KifuAlbum.id, KifuAlbum.black_player_id, KifuAlbum.white_player_id).where(or_(
            KifuAlbum.player_black.in_(by_raw), KifuAlbum.player_white.in_(by_raw))))}
    entries = []
    for raw, row in by_raw.items():
        target_id = row[f"target_player_id_{environment}"]
        target = db.get(KifuPlayer, target_id) if target_id is not None else None
        if target_id is not None and target is None:
            raise ValueError(f"reviewed target ID absent: {raw}")
        expected, actual = frozen[raw], live[raw]
        if [slot[:-1] for slot in expected] != [slot[:-1] for slot in actual]:
            raise ValueError(f"album/date/source scope differs: {raw}")
        if len(actual) != row["expected_slots_each_environment"] or any(slot[-1] is not None for slot in actual):
            raise ValueError(f"slot count or existing FK differs: {raw}")
        if any(slot[4] == raw and slot[5] == raw for slot in actual):
            raise ValueError(f"self-opponent raw value: {raw}")
        if target_id is not None:
            for slot in actual:
                black_id, white_id = opponent_fks[slot[0]]
                opponent_id = white_id if slot[1] == "black" else black_id
                if opponent_id == target_id:
                    raise ValueError(f"opponent already linked to same person: {raw}")
        entries.append({
            "raw_value": raw, "chinese_name": row["chinese_name"],
            "target_id": target_id, "target_canonical_preimage": target.canonical_name if target else None,
            "new_player_needed": row["new_player_needed"],
            "identity_evidence_url": row["identity_evidence_url"],
            "slots": [[slot[0], slot[1], slot[2], slot[-1]] for slot in actual],
            "scope_sha256": _digest([slot[:-1] for slot in actual]),
        })
    expected_total = allowlist["summary"].get(
        f"slots_{environment}", allowlist["summary"].get("slots_each_environment")
    )
    if sum(len(entry["slots"]) for entry in entries) != expected_total:
        raise ValueError("reviewed total slot count differs")
    return {"format": 1, "environment": environment, "allowlist_sha256": allowlist_sha256,
            "frozen_inventory_sha256": inventory["sha256"], "entries": entries,
            "counts": {"games": inventory["counts"]["all"], "raw_values": len(entries),
                       "slots": expected_total,
                       "black_slots": sum(slot[1] == "black" for entry in entries for slot in entry["slots"]),
                       "white_slots": sum(slot[1] == "white" for entry in entries for slot in entry["slots"]),
                       "new_player_ids": len(new_names)}}


def capture_nonhan_plan(inventory, allowlist, allowlist_sha256, environment, engine):
    """Capture the full exact raw, source, FK, and catalog preimages without writes."""
    with Session(engine) as db:
        return _capture(db, inventory, allowlist, allowlist_sha256, environment)


def run_nonhan_plan(inventory, allowlist, allowlist_sha256, environment, plan, engine, *, apply=False):
    """Execute the captured plan in one transaction; default rolls back."""
    with Session(engine) as db:
        transaction = db.begin()
        try:
            if engine.dialect.name == "postgresql":
                db.execute(text("LOCK TABLE kifu_albums, kifu_album_sources, kifu_sources, kifu_players, "
                                "kifu_player_aliases, kifu_raw_player_values IN SHARE ROW EXCLUSIVE MODE"))
            if _capture(db, inventory, allowlist, allowlist_sha256, environment) != plan:
                raise ValueError("non-Han live preimages changed after capture")
            mapping = {}
            created = 0
            for entry in plan["entries"]:
                player_id = entry["target_id"]
                if entry["new_player_needed"]:
                    person = KifuPlayer(canonical_name=entry["chinese_name"])
                    db.add(person)
                    db.flush()
                    player_id = person.id
                    created += 1
                mapping[entry["raw_value"]] = (player_id, entry["identity_evidence_url"])
            if engine.dialect.name == "postgresql":
                db.execute(text("CREATE TEMP TABLE kifu_player_nonhan_map "
                                "(raw_value text PRIMARY KEY, player_id integer NOT NULL, "
                                "evidence_url text NOT NULL) ON COMMIT DROP"))
                db.execute(text("INSERT INTO kifu_player_nonhan_map (raw_value, player_id, evidence_url) "
                                "SELECT raw_value, player_id, evidence_url FROM "
                                "jsonb_to_recordset(CAST(:payload AS jsonb)) "
                                "AS m(raw_value text, player_id integer, evidence_url text)"),
                           {"payload": json.dumps([{"raw_value": raw, "player_id": id_, "evidence_url": url}
                                                   for raw, (id_, url) in mapping.items()], ensure_ascii=False)})
                black = db.execute(text("UPDATE kifu_albums AS a SET black_player_id = m.player_id "
                                        "FROM kifu_player_nonhan_map AS m WHERE a.player_black = m.raw_value "
                                        "AND a.black_player_id IS NULL")).rowcount
                white = db.execute(text("UPDATE kifu_albums AS a SET white_player_id = m.player_id "
                                        "FROM kifu_player_nonhan_map AS m WHERE a.player_white = m.raw_value "
                                        "AND a.white_player_id IS NULL")).rowcount
                raw_updated = db.execute(text(
                    "UPDATE kifu_raw_player_values AS r SET review_status = 'approved', "
                    "review_metadata = jsonb_build_object('kind','reviewed_nonhan_person_link',"
                    "'allowlist_sha256',:allowlist_sha256,'player_id',m.player_id,"
                    "'identity_evidence_url',m.evidence_url)::json "
                    "FROM kifu_player_nonhan_map AS m WHERE r.raw_value = m.raw_value "
                    "AND r.review_status = 'pending' AND r.review_metadata IS NULL"
                ), {"allowlist_sha256": allowlist_sha256}).rowcount
            else:
                black = white = raw_updated = 0
                for raw, (player_id, evidence_url) in mapping.items():
                    black += db.query(KifuAlbum).filter(KifuAlbum.player_black == raw,
                                                        KifuAlbum.black_player_id.is_(None)).update(
                                                            {KifuAlbum.black_player_id: player_id})
                    white += db.query(KifuAlbum).filter(KifuAlbum.player_white == raw,
                                                        KifuAlbum.white_player_id.is_(None)).update(
                                                            {KifuAlbum.white_player_id: player_id})
                    raw_updated += db.query(KifuRawPlayerValue).filter(
                        KifuRawPlayerValue.raw_value == raw, KifuRawPlayerValue.review_status == "pending",
                        KifuRawPlayerValue.review_metadata.is_(None)
                    ).update({KifuRawPlayerValue.review_status: "approved",
                              KifuRawPlayerValue.review_metadata: {
                                  "kind": "reviewed_nonhan_person_link", "allowlist_sha256": allowlist_sha256,
                                  "player_id": player_id, "identity_evidence_url": evidence_url,
                              }})
            if (black != plan["counts"]["black_slots"] or white != plan["counts"]["white_slots"]
                    or raw_updated != plan["counts"]["raw_values"]
                    or created != plan["counts"]["new_player_ids"]):
                raise ValueError("non-Han updated row counts differ from frozen plan")
            result = {"mode": "apply" if apply else "dry_run", "raw_values": raw_updated,
                      "black_fk_slots": black, "white_fk_slots": white, "new_fk_slots": black + white,
                      "new_player_ids": created}
            if apply:
                transaction.commit()
            else:
                transaction.rollback()
            return result
        except BaseException:
            transaction.rollback()
            raise
