"""Exact second-batch new33 player links after committed firstbatch and event514."""

import json

from sqlalchemy import text, update
from sqlalchemy.orm import Session

from katrain.web.core.models_db import KifuAlbum, KifuPlayer
from katrain.web.kifu import player_new33_firstbatch as first


DECISION_PATH = "docs/resource/kifu-player-new33-secondbatch-independent-slot-decision-astra-2026-10-04.json"
DECISION_SHA = "dde6d06c6ada0b1520a9854a212a8a28de3e72809abffe2ccc2945e44bb795fb"
REBASE_PATH = "docs/resource/kifu-player-new33-secondbatch-committed-batches-exact-rebase-2026-10-04.json"
REBASE_SHA = "70d57853166704203003935186c68de1e78e6f2382db8a1e29d2c1df1af06509"
DATABASES = first.DATABASES
FORMAT = "kifu-player-new33-secondbatch-exact-plan-v1"


def _members(rows):
    return first._digest([[row["album_id"], row["side"], row["raw"]] for row in rows])


def _checked_members(decision, rebase, frozen):
    if (decision["format"] != "kifu-player-new33-independent-exact-slot-decision-secondbatch-v1"
            or rebase["format"] != "kifu-player-new33-secondbatch-committed-batches-exact-rebase-v1"
            or rebase["base_slot_decision"]["file_sha256"] != DECISION_SHA):
        raise ValueError("secondbatch decision/rebase identity differs")
    approved, held, excluded = (decision[key] for key in ("approved_slots", "held_slots", "excluded_slots"))
    if ((len(approved), len(held), len(excluded)) != (2755, 543, 4075)
            or _members(approved) != decision["approved_slot_members_sha256"]
            or _members(held) != decision["held_slot_members_sha256"]
            or _members(excluded) != decision["excluded_slot_members_sha256"]):
        raise ValueError("secondbatch exact slot membership differs")
    target_fields = ("album_id", "side", "raw", "target_canonical_name", "target_ids")
    if first._digest([{key: row[key] for key in target_fields} for row in approved]) != decision[
            "approved_slot_targets_sha256"]:
        raise ValueError("secondbatch exact target membership differs")
    groups = [set((row["album_id"], row["side"], row["raw"]) for row in rows)
              for rows in (approved, held, excluded)]
    frozen_keys = {(row["album_id"], row["side"], row["raw"]) for row in frozen["test"]["slots"]}
    if any(len(group) != count for group, count in zip(groups, (2755, 543, 4075))) or any(
            groups[i] & groups[j] for i, j in ((0, 1), (0, 2), (1, 2))) or set.union(*groups) != frozen_keys:
        raise ValueError("secondbatch approved/HOLD/excluded partition differs")
    unchanged = rebase["unchanged_approved_and_hold_membership"]
    for key in ("approved_slots", "held_slots", "excluded_slots", "approved_slot_members_sha256",
                "held_slot_members_sha256", "excluded_slot_members_sha256", "approved_slot_targets_sha256"):
        if unchanged[key] != (len(decision[key]) if key.endswith("_slots") else decision[key]):
            raise ValueError("committed rebase changed decision membership")
    if first._digest(rebase["effective_remaining_slot_preimages"]) != rebase["effective_remaining_slot_preimages_sha256"]:
        raise ValueError("effective remaining slot preimage hash differs")


def _apply_committed(environment, frozen, decision, rebase, first_decision, first_expected):
    env = rebase["environment_evidence"][environment]
    if env["database"] != DATABASES[environment]:
        raise ValueError("committed environment database differs")
    first_plan_info, event_plan_info, actual_info = (env[key] for key in (
        "firstbatch_applied_plan", "next514_applied_plan", "actual_cross_batch_postimage"))
    first_plan = first._pin(first_plan_info["path"], first_plan_info["file_sha256"])
    event_plan = first._pin(event_plan_info["path"], event_plan_info["file_sha256"])
    actual8 = first._pin(actual_info["path"], actual_info["file_sha256"])
    if (first_plan["database"] != env["database"] or first_plan["environment"] != environment
            or first_plan["decision_sha256"] != first.DECISION_SHA
            or first_plan["supplement_sha256"] != first.SUPPLEMENT_SHA
            or first_plan["snapshot"] != first_expected
            or event_plan["database"] != env["database"] or event_plan["environment"] != environment
            or event_plan["decision_sha256"] != rebase["next514_event_decision"]["file_sha256"]
            or actual8["database"] != env["database"] or actual8["environment"] != environment):
        raise ValueError("committed applied plan or actual capture identity differs")
    additions = env["new_player_catalog_rows"]
    if len(additions) != 7 or first._digest(additions) != env["new_player_catalog_rows_sha256"]:
        raise ValueError("firstbatch new player catalog rows differ")
    target_ids = {item["raw"]: item["target_ids"][environment] for item in first_decision["identities"]}
    target_ids.update({row["canonical_name"]: row["id"] for row in additions})
    first_approved = first_decision["approved_slots"]
    expected_changes = {(row["album_id"], row["side"] + "_player_id"): target_ids[row["raw"]]
                        for row in first_approved}
    before = {row["id"]: row for row in first_plan["snapshot"]["albums"]}
    first_deltas = rebase["firstbatch_exact_full_capture_album_deltas"][environment]
    observed_changes = {}
    if len(first_deltas) != 1439:
        raise ValueError("firstbatch full-album delta scope differs")
    for delta in first_deltas:
        album_id = delta["album_id"]
        old = before[album_id]
        if first._digest(old) != delta["before_complete_album_sha256"] or sorted(delta["changes"]) != sorted(
                delta["changed_columns"]):
            raise ValueError(f"firstbatch album preimage differs: {album_id}")
        after = dict(old)
        for column, transition in delta["changes"].items():
            if (column not in ("black_player_id", "white_player_id") or transition["from"] is not None
                    or old[column] is not None):
                raise ValueError(f"firstbatch player transition differs: {album_id}/{column}")
            after[column] = transition["to"]
            observed_changes[(album_id, column)] = transition["to"]
        if first._digest(after) != delta["after_firstbatch_complete_album_sha256"]:
            raise ValueError(f"firstbatch album postimage differs: {album_id}")
    if observed_changes != expected_changes:
        raise ValueError("firstbatch exact FK membership/targets differ")
    current = first._after(first_plan, first_approved, target_ids, additions)
    current_albums = {row["id"]: row for row in current["albums"]}
    for delta in first_deltas:
        if first._digest(current_albums[delta["album_id"]]) != delta["after_firstbatch_complete_album_sha256"]:
            raise ValueError(f"firstbatch replay differs: {delta['album_id']}")
    if (event_plan["snapshot"]["events"] != current["events"]
            or event_plan["snapshot"]["editions"] != current["event_editions"]
            or event_plan["snapshot"]["sources"] != current["sources"]):
        raise ValueError("next514 global preimage differs")
    event_plan_albums = {row["id"]: row for row in event_plan["snapshot"]["albums"]}
    event_deltas = rebase["next514_exact_full_capture_album_deltas"][environment]
    new_events = env["new_event_catalog_rows"]
    target_events = {row["id"]: row for row in current["events"] + new_events}
    if (len(event_deltas) != 6 or set(event_plan_albums) & set(current_albums)
            != {row["album_id"] for row in event_deltas}):
        raise ValueError("next514 full-scope delta count differs")
    for delta in event_deltas:
        album_id = delta["album_id"]
        row = current_albums[album_id]
        if (delta["changed_columns"] != ["event_id"] or delta["before_event_id"] is not None
                or delta["after_event_id"] not in (75, 86, 87)
                or target_events[delta["after_event_id"]]["canonical_name"] != delta["target_event_canonical_name"]
                or row["event_id"] is not None or row["event_edition_id"] != delta["event_edition_id"]
                or event_plan_albums[album_id] != row
                or first._digest(row) != delta["before_complete_album_sha256"]):
            raise ValueError(f"next514 album preimage differs: {album_id}")
        row["event_id"] = delta["after_event_id"]
        if first._digest(row) != delta["after_complete_album_sha256"]:
            raise ValueError(f"next514 album postimage differs: {album_id}")
    if (len(new_events) != 2 or first._digest(new_events) != env["new_event_catalog_rows_sha256"]
            or first._digest(env["verified_existing_event_75_row"]) != env["verified_existing_event_75_row_sha256"]
            or env["verified_existing_event_75_row"] not in current["events"]
            or {row["id"] for row in new_events} & {row["id"] for row in current["events"]}):
        raise ValueError("next514 event catalog additions differ")
    current["events"] = first._sorted(current["events"] + new_events)
    if (actual8["new_player_catalog"] != additions or actual8["event_catalog"] != first._sorted(
            [env["verified_existing_event_75_row"]] + new_events) or actual8["sources"] != current["sources"]):
        raise ValueError("eight-row actual catalog/source differs")
    actual_rows = {row["id"]: row for row in actual8["albums"]}
    actual_associations = {row["album_id"]: row for row in actual8["album_sources"]}
    expected_associations = {row["album_id"]: row for row in current["album_sources"]}
    fresh = rebase["fresh_eight_row_actual_rebases"][environment]
    if len(fresh) != 8 or set(actual_rows) != {row["album_id"] for row in fresh}:
        raise ValueError("eight-row actual membership differs")
    for item in fresh:
        album_id = item["album_id"]
        row = current_albums[album_id]
        if (actual_rows[album_id] != row or first._digest(row) != item["derived_current_complete_album_sha256"]
                or first._digest(actual_rows[album_id]) != item["actual_current_complete_album_sha256"]
                or first._sha(row["sgf_content"].encode()) != item["actual_sgf_sha256"]
                or actual_associations[album_id] != expected_associations[album_id]
                or first._digest([actual_associations[album_id]]) != item["actual_source_associations_sha256"]):
            raise ValueError(f"eight-row actual postimage differs: {album_id}")
    guards = rebase["expected_global_guard_digests"][environment]
    for label, value in {
        "full_original_7168_album_expected_scope_sha256": current["albums"],
        "full_current_player_catalog_expected_sha256": current["catalog"],
        "full_current_players_expected_sha256": current["catalog"]["players"],
        "full_unchanged_aliases_expected_sha256": current["catalog"]["aliases"],
        "full_unchanged_names_expected_sha256": current["catalog"]["names"],
        "full_global_events_expected_sha256": current["events"],
        "full_global_event_editions_expected_sha256": current["event_editions"],
        "all_33_raw_staging_expected_sha256": current["raw_staging"],
        "source_catalog_expected_sha256": current["sources"],
        "original_7168_source_associations_expected_sha256": current["album_sources"],
    }.items():
        if first._digest(value) != guards[label]:
            raise ValueError(f"full current {label} differs")
    return current


def _check_remaining(environment, frozen, decision, rebase, current):
    approved, held = decision["approved_slots"], decision["held_slots"]
    reviewed = {(row["album_id"], row["side"], row["raw"]): row for row in approved + held}
    effective = rebase["effective_remaining_slot_preimages"]
    slots = {(row["album_id"], row["side"], row["raw"]): row for row in current["slots"]}
    albums = {row["id"]: row for row in current["albums"]}
    original_albums = {row["id"]: row for row in frozen[environment]["albums"]}
    original_slots = {(row["album_id"], row["side"], row["raw"]): row for row in frozen[environment]["slots"]}
    players = {row["id"]: row for row in current["catalog"]["players"]}
    associations = {}
    for row in current["album_sources"]:
        associations.setdefault(row["album_id"], []).append(row)
    if len(effective) != 3298 or set(reviewed) != {(row["album_id"], row["side"], row["raw"]) for row in effective}:
        raise ValueError("remaining exact slot scope differs")
    identities = {item["raw"]: item for item in decision["identities"]}
    approved_keys = {(row["album_id"], row["side"], row["raw"]) for row in approved}
    if len(identities) != 16:
        raise ValueError("secondbatch identity scope differs")
    for entry in effective:
        album_id, side, raw = entry["album_id"], entry["side"], entry["raw"]
        key = (album_id, side, raw)
        decision_row = reviewed[key]
        original = original_albums[album_id]
        original_guard = decision_row["preimages"][environment]
        current_row = albums[album_id]
        slot = slots[key]
        guard = entry["environments"][environment]
        opponent_side = "white" if side == "black" else "black"
        opponent_fk = current_row[opponent_side + "_player_id"]
        opponent = players.get(opponent_fk)
        if (entry["decision"] != decision_row["decision"]
                or decision_row["old_fk"] is not None or original[side + "_player_id"] is not None
                or decision_row["date_played"] != original["date_played"]
                or decision_row["rank"] != original[side + "_rank"]
                or decision_row["event"] != original["event"]
                or decision_row["opponent_raw"] != original["player_" + opponent_side]
                or decision_row["opponent_rank"] != original[opponent_side + "_rank"]
                or decision_row["sgf_sha256"] != original["sgf_sha256"]
                or first._digest(first._base(original, decision["database_album_columns"]))
                != original_guard["album_row_sha256"]
                or first._digest(original_slots[key]) != original_guard["captured_slot_sha256"]
                or guard["expected_current_own_fk"] is not None
                or guard["expected_current_opponent_fk"] != opponent_fk
                or guard["expected_current_event_id"] != current_row["event_id"]
                or guard["expected_current_event_edition_id"] != current_row["event_edition_id"]
                or first._digest(current_row) != guard["expected_complete_database_album_row_sha256"]
                or first._digest(slot) != guard["expected_current_slot_record_sha256"]
                or first._digest(associations.get(album_id, [])) != guard["source_associations_sha256"]
                or first._sha(current_row["sgf_content"].encode()) != guard["sgf_sha256"]
                or (opponent is None and guard["expected_opponent_catalog_row_sha256"] is not None)
                or (opponent is not None and first._digest(opponent) != guard["expected_opponent_catalog_row_sha256"])):
            raise ValueError(f"effective remaining slot preimage differs: {environment}/{album_id}/{side}")
        identity = identities[raw]
        if key in approved_keys:
            if (decision_row["decision"] != "APPROVE_EXACT_NULL_PLAYER_FK"
                    or decision_row["target_canonical_name"] != identity["chinese_canonical"]
                    or decision_row["target_ids"][environment] is not None):
                raise ValueError(f"approved secondbatch target differs: {album_id}/{side}")
        elif decision_row["decision"] == "APPROVE_EXACT_NULL_PLAYER_FK":
            raise ValueError(f"HOLD secondbatch slot approved: {album_id}/{side}")


def evidence(environment):
    if environment not in DATABASES:
        raise ValueError("unknown environment")
    decision = first._pin(DECISION_PATH, DECISION_SHA)
    rebase = first._pin(REBASE_PATH, REBASE_SHA)
    for item in decision["inputs"].values():
        first._pin(item["path"], item["file_sha256"])
    for key in ("original_capture", "next3_prior_exact_rebase", "firstbatch_applied_receipt",
                "next514_event_decision", "next514_applied_receipt"):
        item = rebase[key]
        first._pin(item["path"], item["file_sha256"])
    if (rebase["original_capture"]["file_sha256"] != decision["inputs"]["exact_capture"]["file_sha256"]
            or rebase["next3_prior_exact_rebase"]["file_sha256"] != decision["inputs"]["next3_exact_rebase"]["file_sha256"]):
        raise ValueError("secondbatch original evidence pins differ")
    frozen = first._pin(decision["inputs"]["exact_capture"]["path"],
                        decision["inputs"]["exact_capture"]["file_sha256"])
    _checked_members(decision, rebase, frozen)
    expected_by_env = {}
    for candidate in DATABASES:
        _, first_decision, _, first_expected = first.evidence(candidate)
        expected_by_env[candidate] = _apply_committed(candidate, frozen, decision, rebase,
                                                       first_decision, first_expected)
        _check_remaining(candidate, frozen, decision, rebase, expected_by_env[candidate])
    return frozen, decision, rebase, expected_by_env[environment]


def validate_snapshot(snapshot, expected):
    for label in ("albums", "slots", "album_sources", "sources", "events", "event_editions", "raw_staging"):
        if snapshot[label] != expected[label]:
            raise ValueError(f"{label} preimage differs")
    for label in ("players", "aliases", "names"):
        if snapshot["catalog"][label] != expected["catalog"][label]:
            raise ValueError(f"{label} catalog preimage differs")


def _capture(db, environment, frozen, expected):
    database = first._database(db, environment)
    snapshot = first._snapshot(db, frozen[environment], expected)
    validate_snapshot(snapshot, expected)
    return {"format": FORMAT, "environment": environment, "database": database,
            "decision_sha256": DECISION_SHA, "rebase_sha256": REBASE_SHA,
            "snapshot": snapshot, "counts": {"approved": 2755, "held": 3167}}


def capture(engine, environment):
    frozen, _, _, expected = evidence(environment)
    with Session(engine) as db:
        if engine.dialect.name == "postgresql":
            db.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"))
        return _capture(db, environment, frozen, expected)


def run(engine, environment, plan, *, apply=False, plan_sha256=None, approved_plan_sha256=None):
    if apply and (not plan_sha256 or plan_sha256 != approved_plan_sha256):
        raise ValueError("separately approved plan SHA required")
    frozen, decision, _, expected = evidence(environment)
    if (plan.get("format") != FORMAT or plan.get("environment") != environment
            or plan.get("decision_sha256") != DECISION_SHA or plan.get("rebase_sha256") != REBASE_SHA):
        raise ValueError("plan identity differs")
    approved = decision["approved_slots"]
    new_names = {item["raw"]: item["chinese_canonical"] for item in decision["identities"]}
    if len(new_names) != 16 or any(item["target_ids"][environment] is not None for item in decision["identities"]):
        raise ValueError("new canonical scope differs")
    with Session(engine) as db:
        tx = db.begin()
        try:
            if engine.dialect.name == "postgresql":
                db.execute(text("LOCK TABLE kifu_albums,kifu_album_sources,kifu_sources,kifu_players,"
                                "kifu_player_aliases,kifu_player_names,kifu_raw_player_values,kifu_events,"
                                "kifu_event_editions IN SHARE ROW EXCLUSIVE MODE"))
            if _capture(db, environment, frozen, expected) != plan:
                raise ValueError("full captured plan preimage differs")
            targets = {}
            for raw, canonical in new_names.items():
                obj = KifuPlayer(canonical_name=canonical)
                db.add(obj)
                db.flush()
                targets[raw] = obj.id
            if len(set(targets.values())) != 16:
                raise ValueError("distinct new player IDs differ")
            for row in approved:
                side = row["side"]
                field = KifuAlbum.black_player_id if side == "black" else KifuAlbum.white_player_id
                raw_field = KifuAlbum.player_black if side == "black" else KifuAlbum.player_white
                changed = db.execute(update(KifuAlbum).where(
                    KifuAlbum.id == row["album_id"], raw_field == row["raw"],
                    KifuAlbum.date_played == row["date_played"], field.is_(None))
                    .values({field: targets[row["raw"]]}))
                if changed.rowcount != 1:
                    raise ValueError(f"slot CAS failed: {row['album_id']}/{side}")
            db.flush()
            actual = first._snapshot(db, frozen[environment], expected)
            additions = [row for row in actual["catalog"]["players"] if row["id"] in set(targets.values())]
            if len(additions) != 16 or {row["canonical_name"] for row in additions} != set(new_names.values()):
                raise ValueError("created secondbatch player catalog differs")
            wanted = first._after(plan, approved, targets, additions)
            if actual != wanted:
                raise ValueError("in-transaction full postimage differs")
            tx.commit() if apply else tx.rollback()
        except BaseException:
            tx.rollback()
            raise
    with Session(engine) as independent:
        if engine.dialect.name == "postgresql":
            independent.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"))
        final = first._snapshot(independent, frozen[environment], expected)
        if first._database(independent, environment) != plan["database"] or final != (wanted if apply else plan["snapshot"]):
            raise RuntimeError("independent posttransaction full-scope verification differs")
    return {"committed": apply, "created_player_ids": targets if apply else {}, **plan["counts"]}
