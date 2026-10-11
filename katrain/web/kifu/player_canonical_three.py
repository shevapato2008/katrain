"""Apply only the three independently reviewed, exact player FK slot members."""

import hashlib
import gzip
import json
from datetime import datetime
from pathlib import Path
import re
import unicodedata

from sqlalchemy import or_, select, text, update
from sqlalchemy.orm import Session

from katrain.web.core.models_db import (
    KifuAlbum, KifuAlbumSource, KifuEvent, KifuPlayer, KifuPlayerAlias, KifuPlayerName,
    KifuRawPlayerValue, KifuSource,
)


NAMES = frozenset(("周鹤洋", "赵善津", "工藤纪夫"))
MIXED11_OPPONENT_ALBUMS = frozenset((7189, 8956, 61465, 66226, 66241, 132947, 134184, 134220))
NEXT_EVENT_ALBUMS = frozenset((36687, 36688, 36755, 65378, 65387, 66039, 66058, 66326, 103013))
NEXT_EVENT_TARGET_ID = 75
NEXT_EVENT_TARGET_NAME = "中日围棋对抗赛"
ROOT = Path(__file__).resolve().parents[3]
NEXT_EVENT_SHA256 = {
    "rebase_decision": "aa2e104ca58ee2f884a1566fe38b664d74298960ed3616af1d51c6b3625d78b9",
    "decision": "84eace6d50f3029fc4dcd353b1b3e31dece649376c6fccae2d595263c32d5088",
    "compared_plan_file": "b2336ca4c02f6a26bfb3144ad5cef4c604f7776900b9b0554bd42dc78567698e",
    "compared_plan": "7e54d349be3e252ddc27894af82b40221567f494f05d932459ca80ffa6fd6262",
    "applied_record": "a7563b87c403edddde31070f2367dc9e341f78a671816b9fc643c2eee5449822",
    "capture_file": {
        "test": "f0550288d7a54c8b952a31c744eec5eec896898775f1bee63a9e8f7caeba6192",
        "prod": "bebc8048bda346a743be6717f9a7323c40c44753f0f4fe0020c25819e2e5cd25",
    },
}
NEXT15_REBASE_SHA256 = "d7fabd4e9a27a8afe0f18687c9b28ed04dd0e6ff09c69ed31aae4f290180afcf"
NEXT15_DECISION_SHA256 = "a3f3f0661de87d949216bd23269016c2e920d1540ae466392a1ce23b88726560"
NEXT15_APPLIED_SHA256 = "5a815e46041e2deccf470274a9ed000d861ed645285218c3f4affa2ffaa0bb13"
NEXT15_PLAN_SHA256 = {
    "test": "c4d65f3a1a0fab1462bb2314b7e8462bc32ec564c64d33219996bdfc55ed0ef5",
    "prod": "eccf4a8a38595ceea6d33d8a33f719818560d3cb62e189e0bca9ac06ea2b0076",
}
INTERVENING_SHA256 = {
    "test": {
        "mixed11": "1ab5318de70a4d1f0cffa0f2beb98fb5912c95efe60d4c10a7d596d5513d5321",
        "event": "6a33ee4f7b55ed6158ec1824c489721272845e65d3d0dd2fd2f49d0700afc6a2",
        "event_plan": "fa154418e27a3cc70158ae226a7ecf4fdb1564ce3021271ae94f654d8da84d2a",
    },
    "prod": {
        "mixed11": "e49f76c817a8990978faeb5aa2e9bf4c05f35e9fb95da7001e860b1d8df284a1",
        "event": "98f74e646899ddaa25e404b35165543065faaa6dc94f7b24e2fee828be230db4",
        "event_plan": "8038151d0959cbd58691574071195b9664ced593879b0d8c2c34a3a78a609cea",
    },
}
TABLES = {
    "catalog_preimage": KifuPlayer,
    "catalog_alias_preimage": KifuPlayerAlias,
    "catalog_names_preimage": KifuPlayerName,
    "raw_staging_preimage": KifuRawPlayerValue,
    "album_sources_preimage": KifuAlbumSource,
    "sources_preimage": KifuSource,
}


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode()).hexdigest()


def _json_value(value):
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


def _row(obj, columns):
    return {column: _json_value(getattr(obj, column)) for column in columns}


def validate_review(review, environment):
    if review.get("format") != "kifu-player-exact-canonical-three-independent-review-v1":
        raise ValueError("review format differs")
    if review.get("environment") != environment.upper() or set(review["targets"]) != NAMES:
        raise ValueError("review environment or targets differ")
    candidates, holds = review["candidate_slots"], review["held_slots"]
    if review["candidate_slot_columns"] != ["album_id", "side", "raw_name", "date_played", "old_fk", "target_id"]:
        raise ValueError("candidate columns differ")
    if len(candidates) != 1529 or len(holds) != 580 or len(review["live_album_preimage"]) != 2105:
        raise ValueError("review counts differ")
    if digest(candidates) != review["approved_slot_sha256"] or digest(holds) != review["held_slot_sha256"]:
        raise ValueError("review member hash differs")
    approved = {(r[0], r[1]) for r in candidates}
    held = {(r["album_id"], r["side"]) for r in holds}
    if len(approved) != len(candidates) or len(held) != len(holds) or approved & held:
        raise ValueError("duplicate or overlapping slot member")
    if any(r[2] not in NAMES or r[4] is not None or r[5] != review["targets"][r[2]]
           for r in candidates):
        raise ValueError("candidate identity or NULL preimage differs")
    if any(r["raw_name"] not in NAMES or r["old_fk"] is not None or
           r["would_target_id"] != review["targets"][r["raw_name"]] for r in holds):
        raise ValueError("HOLD identity or NULL preimage differs")
    original = {r["id"]: r for r in review["live_album_preimage"]}
    if len(original) != 2105:
        raise ValueError("duplicate original album")
    all_slots = {(r["id"], side) for r in original.values() for side, raw, fk in
                 (("black", r["player_black"], r["black_player_id"]),
                  ("white", r["player_white"], r["white_player_id"]))
                 if raw in NAMES and fk is None}
    if approved | held != all_slots:
        raise ValueError("frozen NULL scope differs")
    for album_id, side, raw, date, old_fk, target in candidates:
        row = original[album_id]
        if row[f"player_{side}"] != raw or row["date_played"] != date or row[f"{side}_player_id"] is not None:
            raise ValueError("candidate album preimage differs")
    for hold in holds:
        row = original[hold["album_id"]]
        if (row[f"player_{hold['side']}"] != hold["raw_name"] or
                row["date_played"] != hold["date"] or
                row["sgf_sha256"] != hold["sgf_sha256"]):
            raise ValueError("HOLD album/SGF preimage differs")
    return original


def _pinned_json(path, sha256):
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != sha256:
        raise ValueError(f"intervening evidence SHA differs: {path}")
    return json.loads(gzip.decompress(data) if data[:2] == b"\x1f\x8b" else data)


def approved_intervening_deltas(review, environment, original):
    """Resolve exact committed changes from two separately approved frozen plans."""
    pins = INTERVENING_SHA256[environment]
    mixed = _pinned_json(ROOT / f"docs/resource/kifu-player-highfreq-mixed11-revised-{environment.upper()}-plan-2026-10-04.json.gz",
                         pins["mixed11"])
    event = _pinned_json(ROOT / f"docs/resource/kifu-event-japanese-major-next-{environment.upper()}-capture-2026-10-04.json",
                         pins["event"])
    if mixed["environment"] != environment or event["environment"] != environment.upper():
        raise ValueError("intervening evidence environment differs")
    if event["sha256"] != pins["event_plan"] or event["mixed11_plan_sha256"] != pins["mixed11"]:
        raise ValueError("intervening plan chain differs")
    deltas = {}
    approved = {(r[0], r[1]) for r in review["candidate_slots"]}
    for album_id, side, raw, date, old, target in mixed["candidate_slots"]:
        if album_id not in MIXED11_OPPONENT_ALBUMS:
            continue
        column = f"{side}_player_id"
        if album_id not in original or (album_id, side) in approved or old is not None or target is None:
            raise ValueError("mixed11 intersection differs")
        if original[album_id][column] != old or original[album_id][f"player_{side}"] != raw:
            raise ValueError("mixed11 frozen opponent preimage differs")
        deltas[(album_id, column)] = (old, target)
    if {album_id for album_id, column in deltas} != MIXED11_OPPONENT_ALBUMS or len(deltas) != 8:
        raise ValueError("mixed11 intersection member set differs")
    event_count = 0
    for row in event["approved"]:
        album_id, old, target = row[0], row[3], row[8]
        if album_id not in original:
            continue
        if old is not None or target is None or original[album_id]["event_id"] != old:
            raise ValueError("event frozen preimage differs")
        deltas[(album_id, "event_id")] = (old, target)
        event_count += 1
    if event_count != 47:
        raise ValueError("event intersection member set differs")
    rebase = _pinned_json(ROOT / "docs/resource/kifu-player-canonical-three-next-event-rebase-independent-decision-2026-10-04.json",
                          NEXT_EVENT_SHA256["rebase_decision"])
    next_decision = _pinned_json(ROOT / "docs/resource/kifu-event-next-scope-independent-decision-astra-2026-10-04.json",
                                 NEXT_EVENT_SHA256["decision"])
    next_plan = _pinned_json(ROOT / "docs/resource/kifu-event-next-scope-compared-plan-2026-10-04.json",
                             NEXT_EVENT_SHA256["compared_plan_file"])
    applied_record = ROOT / "docs/resource/kifu-event-next-scope-applied-2026-10-04.md"
    if hashlib.sha256(applied_record.read_bytes()).hexdigest() != NEXT_EVENT_SHA256["applied_record"]:
        raise ValueError("next event applied record SHA differs")
    capture = _pinned_json(ROOT / f"docs/resource/kifu-event-next-scope-{environment.upper()}-capture-2026-10-04.json",
                           NEXT_EVENT_SHA256["capture_file"][environment])
    if (next_plan["sha256"] != NEXT_EVENT_SHA256["compared_plan"] or
            digest({k: v for k, v in next_plan.items() if k != "sha256"}) != next_plan["sha256"] or
            next_plan["decision_sha256"] != NEXT_EVENT_SHA256["decision"] or
            next_decision["decision_summary"]["approved_event_type_only"] != 743):
        raise ValueError("next event decision/plan chain differs")
    env_plan = next_plan[environment.upper()]
    if (env_plan["environment"] != environment.upper() or env_plan["database"] != (
            "katrain_db" if environment == "test" else "katrain_prod_20260725") or
            digest({k: v for k, v in env_plan.items() if k != "sha256"}) != env_plan["sha256"] or
            capture != env_plan or rebase["input_pins"]["next_event_compared_plan"]["file_sha256"] !=
            NEXT_EVENT_SHA256["compared_plan_file"]):
        raise ValueError("next event environment/database differs")
    reviewed = {row["id"]: row for row in next_decision["approved"]}
    planned = {row["id"]: row for row in env_plan["rows"]}
    intersection = set(env_plan["approved_ids"]) & set(original)
    rebase_rows = {row["album_id"]: row for row in rebase["allowed_deltas"]}
    player_approved = {(row[0], row[1]): row[5] for row in review["candidate_slots"]}
    player_held = {(row["album_id"], row["side"]) for row in review["held_slots"]}
    if (intersection != NEXT_EVENT_ALBUMS or set(rebase_rows) != intersection or
            set(deltas) & {(i, "event_id") for i in intersection} or
            any(i in MIXED11_OPPONENT_ALBUMS for i in intersection) or
            set(env_plan["held_ids"]) & intersection):
        raise ValueError("next event intersection differs or overlaps earlier event batch")
    for album_id in intersection:
        decision_row, plan_row = reviewed[album_id], planned[album_id]
        rebase_row = rebase_rows[album_id]
        side = rebase_row["player_side"]
        player_slot = (album_id, side)
        expected_player_fk = player_approved.get(player_slot)
        if (decision_row["target_event_key"] != "china_japan_regular_exchange" or
                decision_row["decision"] != "approve_event_type_only" or
                decision_row["target_event_edition_id"] is not None or
                decision_row["before"]["event_id"] is not None or plan_row["event_id"] is not None or
                original[album_id]["event_id"] is not None or
                decision_row["sgf_sha256"] != original[album_id]["sgf_sha256"] or
                plan_row["sgf_sha256"] != original[album_id]["sgf_sha256"] or
                any(plan_row[key] != original[album_id][key] for key in set(plan_row) & set(original[album_id])) or
                any(decision_row[key] != plan_row[key] for key in
                    ("id", "event", "date_played", "date_sort", "source", "source_path",
                     "player_black", "player_white", "result", "sgf_md5", "sgf_sha256")) or
                any(decision_row["before"][key] != plan_row[key] for key in
                    ("event_id", "event_edition_id", "duplicate_of_id")) or
                rebase_row["frozen_album_row_sha256"][environment.upper()] !=
                    original[album_id]["album_row_sha256"] or
                rebase_row["sgf_sha256"] != original[album_id]["sgf_sha256"] or
                rebase_row["column"] != "event_id" or rebase_row["frozen_preimage"] is not None or
                rebase_row["required_current_postimage"] != NEXT_EVENT_TARGET_ID or
                rebase_row["player_fk_before_three_batch"] is not None or
                (player_slot not in player_held and player_slot not in player_approved) or
                rebase_row["player_fk_after_three_batch"][environment.upper()] != expected_player_fk or
                (rebase_row["player_status"] == "HOLD") != (player_slot in player_held) or
                (rebase_row["player_status"] == "approved") != (player_slot in player_approved)):
            raise ValueError("next event exact album preimage differs")
        deltas[(album_id, "event_id")] = (None, NEXT_EVENT_TARGET_ID)
    if len(deltas) != 64 or sum(column == "event_id" for _, column in deltas) != 56 or len({i for i, _ in deltas}) != 62:
        raise ValueError("combined intervening delta cardinality differs")
    next15_rebase = _pinned_json(ROOT / "docs/resource/kifu-player-canonical-three-next15-rebase-independent-decision-2026-10-04.json",
                                 NEXT15_REBASE_SHA256)
    next15_decision = _pinned_json(ROOT / "docs/resource/kifu-player-next15-independent-decision-astra-2026-10-04.json",
                                   NEXT15_DECISION_SHA256)
    next15_plan = _pinned_json(ROOT / f"docs/resource/kifu-player-next15-{environment.upper()}-plan-2026-10-04.json.gz",
                               NEXT15_PLAN_SHA256[environment])
    applied_record = ROOT / "docs/resource/kifu-player-next15-applied-2026-10-04.md"
    if hashlib.sha256(applied_record.read_bytes()).hexdigest() != NEXT15_APPLIED_SHA256:
        raise ValueError("next15 applied record SHA differs")
    environment_review = next15_rebase["environments"][environment.upper()]
    if (next15_plan["format"] != "kifu-player-next15-exact-plan-v1" or
            next15_plan["environment"] != environment or next15_plan["database"] != environment_review["database"] or
            next15_plan["review_sha256"] != NEXT15_DECISION_SHA256 or
            next15_plan["counts"] != {"approved_raws": 13, "candidate_slots": 5423, "held_slots": 31,
                                      "new_ids": 6, "protected_slots": 0, "whole_raw_held_slots": 811} or
            environment_review["next15_plan"]["file_sha256"] != NEXT15_PLAN_SHA256[environment] or
            next15_rebase["input_pins"]["next15_decision"]["file_sha256"] != NEXT15_DECISION_SHA256):
        raise ValueError("next15 evidence chain differs")
    next15_members = {(row[0], row[1]): row for row in next15_plan["candidate_slots"] if row[0] in original}
    rebase_members = {(row["album_id"], row["side"]): row for row in next15_rebase["allowed_deltas"]}
    if (set(next15_members) != set(rebase_members) or len(rebase_members) != 19 or
            {i for i, _ in rebase_members} & {i for i, _ in deltas} or
            any((i, f"{side}_player_id") in deltas for i, side in rebase_members)):
        raise ValueError("next15 exact intersection differs")
    next15_entries = {entry["raw"]: entry for entry in next15_decision["entries"]}
    next15_sgf = {row[0]: row for row in next15_plan["sgf"]}
    source_keys = {row["id"]: row["source_key"] for row in review["sources_preimage"]}
    source_rows = {}
    for row in review["album_sources_preimage"]:
        source_rows.setdefault(row["album_id"], []).append([
            row["id"], row["source_id"], source_keys[row["source_id"]], row["origin_path"], row["match_method"]])
    for album_id, side in rebase_members:
        row = next15_members[(album_id, side)]
        selected = rebase_members[(album_id, side)]
        frozen = original[album_id]
        other = "white" if side == "black" else "black"
        opposite_slot = (album_id, other)
        entry = next15_entries[row[2]]
        target = environment_review["targets"].get(row[2])
        if (target is None or entry["decision"] != "approved_exact_identity_subject_to_slot_guards" or
                (entry[f"{environment}_target"] != "new" and entry[f"{environment}_target"] != target["id"]) or
                (entry[f"{environment}_target"] == "new" and row[2] != "周俊勋") or
                (opposite_slot in player_approved) == (opposite_slot in player_held) or
                selected["three_player_opposite_slot"]["side"] != other or
                selected["three_player_opposite_slot"]["raw_name"] != frozen[f"player_{other}"] or
                selected["three_player_opposite_slot"]["status"] !=
                    ("approved" if opposite_slot in player_approved else "HOLD") or
                selected["three_player_opposite_slot"]["frozen_fk"] != frozen[f"{other}_player_id"] or
                (album_id, side) in player_approved or (album_id, side) in player_held or
                row[2] != selected["raw_name"] or row[3] != selected["date_played"] or
                row[4:7] != [frozen["player_black"], frozen["player_white"], frozen["duplicate_of_id"]] or
                sorted(row[7]) != sorted(source_rows.get(album_id, [])) or row[8] is not None or
                frozen[f"player_{side}"] != row[2] or frozen[f"{side}_player_id"] is not None or
                selected["column"] != f"{side}_player_id" or selected["frozen_preimage"] is not None or
                selected["required_current_postimage"][environment.upper()] != target["id"] or
                selected["player_black"] != frozen["player_black"] or
                selected["player_white"] != frozen["player_white"] or
                selected["sgf_sha256"] != frozen["sgf_sha256"] or
                selected["frozen_album_row_sha256"][environment.upper()] != frozen["album_row_sha256"] or
                next15_sgf[album_id] != [album_id, frozen["sgf_sha256"], frozen["source_path"], frozen["event"]]):
            raise ValueError("next15 exact opponent preimage differs")
        deltas[(album_id, f"{side}_player_id")] = (None, target["id"])
    if len(deltas) != 83 or sum(column == "event_id" for _, column in deltas) != 56 or len({i for i, _ in deltas}) != 81:
        raise ValueError("final intervening delta cardinality differs")
    return deltas


def _event_catalog_guard(db):
    event = db.get(KifuEvent, NEXT_EVENT_TARGET_ID)
    if event is None or event.canonical_name != NEXT_EVENT_TARGET_NAME:
        raise ValueError("intervening event target catalog differs")


def _next15_target_bindings(environment):
    rebase = _pinned_json(ROOT / "docs/resource/kifu-player-canonical-three-next15-rebase-independent-decision-2026-10-04.json",
                          NEXT15_REBASE_SHA256)
    return rebase["environments"][environment.upper()]["targets"]


def _next15_catalog_guard(db, environment):
    for raw, target in _next15_target_bindings(environment).items():
        player = db.get(KifuPlayer, target["id"])
        if player is None or player.canonical_name != target["canonical_name"]:
            raise ValueError(f"next15 target catalog differs: {raw}")


def _ancillary(db, review):
    result = {}
    targets = set(review["targets"].values())
    album_ids = {r["id"] for r in review["live_album_preimage"]}
    for key, model in TABLES.items():
        if key == "catalog_preimage":
            query = select(model).where(model.id.in_(targets))
        elif key in ("catalog_alias_preimage", "catalog_names_preimage"):
            query = select(model).where(model.player_id.in_(targets))
        elif key == "raw_staging_preimage":
            query = select(model).where(model.raw_value.in_(NAMES))
        elif key == "album_sources_preimage":
            query = select(model).where(model.album_id.in_(album_ids))
        else:
            source_ids = {r["id"] for r in review["sources_preimage"]}
            query = select(model).where(model.id.in_(source_ids))
        columns = list(review[key][0]) if review[key] else []
        result[key] = sorted((_row(obj, columns) for obj in db.scalars(query)), key=lambda row: row["id"])
    return result


def _ancillary_preimage_equal(key, live, frozen):
    if key != "album_sources_preimage":
        return live == frozen
    if len(live) != len(frozen):
        return False
    try:
        return all(
            {field: value for field, value in current.items() if field != "created_at"} ==
            {field: value for field, value in original.items() if field != "created_at"}
            and _parse_created_at(current["created_at"]) == _parse_created_at(original["created_at"])
            for current, original in zip(live, frozen)
        )
    except (KeyError, TypeError, ValueError):
        return False


def _parse_created_at(value):
    # Python 3.10 rejects some PostgreSQL timestamps with fewer than six fraction digits.
    padded = re.sub(r"\.(\d{1,5})(?=[+-]\d{2}:\d{2}$)",
                    lambda match: "." + match.group(1).ljust(6, "0"), value)
    parsed = datetime.fromisoformat(padded)
    if parsed.tzinfo is None:
        raise ValueError("created_at must include a timezone")
    return parsed


def _albums(db, review):
    query = select(KifuAlbum).where(or_(KifuAlbum.player_black.in_(NAMES),
                                        KifuAlbum.player_white.in_(NAMES)))
    columns = [key for key in review["live_album_preimage"][0] if key not in ("album_row_sha256", "sgf_sha256")]
    return {album.id: {**_row(album, columns), "sgf_sha256": hashlib.sha256(album.sgf_content.encode()).hexdigest()}
            for album in db.scalars(query)}


def _identity_key(value):
    # Complete OpenCC t2s inverse character variants for these three audited names.
    # Scope this mapping to collision detection; raw match/write selection stays literal.
    return unicodedata.normalize("NFKC", value).casefold().translate(str.maketrans("週趙紀鶴", "周赵纪鹤"))


def _collision_guard(db, review):
    owners = review["targets"]
    expected = {_identity_key(raw): target for raw, target in owners.items()}
    if len(expected) != 3:
        raise ValueError("normalized target collision")
    for player_id, spelling in db.execute(select(KifuPlayer.id, KifuPlayer.canonical_name)):
        target = expected.get(_identity_key(spelling))
        if target is not None and player_id != target:
            raise ValueError("normalized canonical collision")
    for player_id, spelling, normalized in db.execute(select(
            KifuPlayerAlias.player_id, KifuPlayerAlias.alias, KifuPlayerAlias.normalized_alias)):
        for value in (spelling, normalized):
            if value and (target := expected.get(_identity_key(value))) is not None and player_id != target:
                raise ValueError("normalized alias collision")
    for player_id, lang, spelling in db.execute(select(
            KifuPlayerName.player_id, KifuPlayerName.lang, KifuPlayerName.display_name).where(
                KifuPlayerName.lang.in_(("cn", "tw", "jp")))):
        if (target := expected.get(_identity_key(spelling))) is not None and player_id != target:
            raise ValueError("normalized display-name collision")


def _capture(db, review, environment, review_file_sha256):
    original = validate_review(review, environment)
    deltas = approved_intervening_deltas(review, environment, original)
    current = _albums(db, review)
    if set(current) != set(original):
        raise ValueError("current exact raw album scope differs")
    for album_id, row in current.items():
        frozen = original[album_id]
        for column, value in row.items():
            if (album_id, column) in deltas:
                if value != deltas[(album_id, column)][1]:
                    raise ValueError(f"intervening approved postimage differs: {album_id}/{column}")
                continue
            if value != frozen[column]:
                raise ValueError(f"frozen album preimage differs: {album_id}/{column}")
    ancillary = _ancillary(db, review)
    for key in TABLES:
        if not _ancillary_preimage_equal(key, ancillary[key], sorted(review[key], key=lambda row: row["id"])):
            raise ValueError(f"{key} differs")
    _collision_guard(db, review)
    _event_catalog_guard(db)
    _next15_catalog_guard(db, environment)
    return {"format": "kifu-player-canonical-three-exact-plan-v1", "environment": environment,
            "database": db.scalar(text("SELECT current_database()")) if db.bind.dialect.name == "postgresql" else "sqlite-test",
            "review_file_sha256": review_file_sha256,
            "approved_slot_sha256": review["approved_slot_sha256"],
            "held_slot_sha256": review["held_slot_sha256"],
            "intervening_evidence_sha256": INTERVENING_SHA256[environment],
            "next_event_evidence_sha256": NEXT_EVENT_SHA256,
            "next15_evidence_sha256": {"rebase_decision": NEXT15_REBASE_SHA256,
                                        "identity_decision": NEXT15_DECISION_SHA256,
                                        "applied_record": NEXT15_APPLIED_SHA256,
                                        "environment_plan": NEXT15_PLAN_SHA256[environment]},
            "next15_target_bindings": _next15_target_bindings(environment),
            "albums": [current[key] for key in sorted(current)], "ancillary": ancillary,
            "counts": {"candidate_slots": len(review["candidate_slots"]), "held_slots": len(review["held_slots"])}}


def capture(engine, review, environment, review_file_sha256):
    with Session(engine) as db:
        if engine.dialect.name == "postgresql":
            db.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"))
        return _capture(db, review, environment, review_file_sha256)


def _verify_final(engine, review, plan, *, applied):
    """Read a new transaction after rollback or commit, including every held slot."""
    expected = {row["id"]: dict(row) for row in plan["albums"]}
    if applied:
        for album_id, side, raw, date, old_fk, target in review["candidate_slots"]:
            expected[album_id][f"{side}_player_id"] = target
    with Session(engine) as db:
        if engine.dialect.name == "postgresql":
            db.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"))
        if _albums(db, review) != expected or _ancillary(db, review) != plan["ancillary"]:
            raise ValueError("independent posttransaction album/catalog/source verification differs")
        _collision_guard(db, review)
        _event_catalog_guard(db)
        _next15_catalog_guard(db, plan["environment"])
        if db.bind.dialect.name == "postgresql" and db.scalar(text("SELECT current_database()")) != plan["database"]:
            raise ValueError("independent posttransaction database differs")


def run(engine, review, environment, review_file_sha256, plan, *, apply=False,
        plan_sha256=None, approved_plan_sha256=None):
    if apply and (not plan_sha256 or plan_sha256 != approved_plan_sha256):
        raise ValueError("separate plan SHA approval required")
    if plan.get("format") != "kifu-player-canonical-three-exact-plan-v1":
        raise ValueError("plan format differs")
    with Session(engine) as db:
        tx = db.begin()
        try:
            if engine.dialect.name == "postgresql":
                db.execute(text("LOCK TABLE kifu_albums,kifu_album_sources,kifu_sources,kifu_events,kifu_players,"
                                "kifu_player_aliases,kifu_player_names,kifu_raw_player_values "
                                "IN SHARE ROW EXCLUSIVE MODE"))
            if _capture(db, review, environment, review_file_sha256) != plan:
                raise ValueError("current plan preimage differs")
            for album_id, side, raw, date, old_fk, target in review["candidate_slots"]:
                field = KifuAlbum.black_player_id if side == "black" else KifuAlbum.white_player_id
                raw_field = KifuAlbum.player_black if side == "black" else KifuAlbum.player_white
                changed = db.execute(update(KifuAlbum).where(KifuAlbum.id == album_id,
                    raw_field == raw, KifuAlbum.date_played == date, field.is_(None)).values({field: target}))
                if changed.rowcount != 1:
                    raise ValueError(f"slot compare-and-swap failed: {album_id}/{side}")
            db.flush()
            expected = {row["id"]: dict(row) for row in plan["albums"]}
            for album_id, side, raw, date, old_fk, target in review["candidate_slots"]:
                expected[album_id][f"{side}_player_id"] = target
            if _albums(db, review) != expected or _ancillary(db, review) != plan["ancillary"]:
                raise ValueError("postwrite scope differs")
            result = {"committed": apply, **plan["counts"]}
            tx.commit() if apply else tx.rollback()
        except BaseException:
            tx.rollback()
            raise
    try:
        _verify_final(engine, review, plan, applied=apply)
    except BaseException as exc:
        if apply:
            raise RuntimeError("commit succeeded; independent postcommit verification failed") from exc
        raise
    return result
