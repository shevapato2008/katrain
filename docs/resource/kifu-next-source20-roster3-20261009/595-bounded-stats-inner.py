"""Read-only batch-595 progress delta for the captured 158 player albums."""

from collections import Counter, defaultdict
from datetime import datetime, timezone
import gzip
import hashlib
import json
import os
from pathlib import Path

from sqlalchemy import Column, String, create_engine, func, select, text
from sqlalchemy.orm import Session, column_property, defer

from katrain.web.core.models_db import (KifuAlbum, KifuEvent, KifuEventName, KifuNameBatch,
                                        KifuNameChange, KifuPlayer, KifuPlayerName)
from katrain.web.kifu.identity import (PRIMARY_NAME_LANGUAGES, _approved_names, _qualified_name_rows,
                                      live_event_selections, obscured_program_event_ids, strict_slot_approvals)
from katrain.web.kifu.name_evidence import registry_sha256


if not __debug__:
    raise RuntimeError("bounded stats assertions must be enabled")
D = Path("/work")
LANGUAGES = sorted(PRIMARY_NAME_LANGUAGES)
if not hasattr(KifuAlbum, "list_hidden_reason"):
    KifuAlbum.__table__.append_column(Column("list_hidden_reason", String(64)))
    KifuAlbum.list_hidden_reason = column_property(KifuAlbum.__table__.c.list_hidden_reason)


def catalog_completion(db, entity, name_model, field):
    owners = dict(db.execute(select(entity.id, entity.canonical_name)).all())
    qualified = defaultdict(set)
    for name, _ in _qualified_name_rows(db, _approved_names(db, name_model, field), name_model, field):
        if name.lang in PRIMARY_NAME_LANGUAGES:
            qualified[getattr(name, field)].add(name.lang)
    return owners, {pid for pid in owners if qualified[pid] == PRIMARY_NAME_LANGUAGES}


def captured_physical_guard(conn, capture, targets):
    expected = {}
    for row in capture["rows"]:
        for album in row["linked_album_members"]:
            image = {key: value for key, value in album.items() if key != "side"}
            assert expected.setdefault(image["id"], image) == image
    ids = list(targets)
    actual = []
    for row in conn.execute(text("SELECT * FROM kifu_albums "
                                 "WHERE black_player_id = ANY(:ids) OR white_player_id = ANY(:ids) ORDER BY id"),
                            {"ids": ids}).mappings():
        image = {key: value.isoformat() if hasattr(value, "isoformat") else value
                 for key, value in row.items()}
        image["sgf_utf8_sha256"] = hashlib.sha256(image.pop("sgf_content").encode("utf-8")).hexdigest()
        actual.append(image)
    assert len(actual) == len(expected) == capture["unique_albums"] == 158
    assert sum(int(row["black_player_id"] in targets) + int(row["white_player_id"] in targets)
               for row in actual) == capture["game_slots"] == 160
    assert sorted(actual[0]) == capture["scoped_album_physical_columns"]
    assert actual == [expected[key] for key in sorted(expected)]
    return sorted(expected)


def bounded(db, album_ids, targets):
    target_ids = set(targets)
    count = Counter()
    for start in range(0, len(album_ids), 200):
        page = album_ids[start:start + 200]
        albums = (db.query(KifuAlbum).options(defer(KifuAlbum.sgf_content), defer(KifuAlbum.search_text))
                  .filter(KifuAlbum.id.in_(page)).order_by(KifuAlbum.id).all())
        assert [album.id for album in albums] == page
        selected = live_event_selections(db, albums)
        obscured = obscured_program_event_ids(db, albums, selected_events=selected)
        counts = {album.id: [[0, 0, 0], [0, 0, 0]] for album in albums}
        for lang in LANGUAGES:
            approvals = strict_slot_approvals(db, albums, lang,
                                              selected_events=selected, obscured_event_ids=obscured)
            for album in albums:
                after = approvals[album.id]
                before = list(after)
                if targets.get(album.black_player_id) == lang:
                    before[0] = None
                if targets.get(album.white_player_id) == lang:
                    before[1] = None
                for which, values in enumerate((before, after)):
                    for slot, value in enumerate(values):
                        counts[album.id][which][slot] += value is not None
        for album in albums:
            count["games"] += 1
            count["slots"] += int(album.black_player_id in target_ids) + int(album.white_player_id in target_ids)
            event_raw, event_id = selected.get(album.id, (album.event, album.event_id))
            for label, values in zip(("before", "after"), counts[album.id]):
                black, white, event = [value == len(LANGUAGES) for value in values]
                if black and white:
                    count[label + "_both"] += 1
                    if event_id:
                        count[label + "_formal"] += event
                    elif (event_raw or "").strip():
                        count[label + "_raw"] += event
                    else:
                        count[label + "_hidden_event_both"] += 1
    assert count["games"] == 158 and count["slots"] == 160
    return dict(count)


def report(engine):
    manifest = json.loads((D / "595-closure-proposed-manifest.json").read_text())
    baseline_path = D / "595-PROD-baseline-594-progress.json.gz"
    bundle_path = D / "PROD-next16-bundle.json.gz"
    capture_path = D / "PROD-next16-current-scoped-readonly.json.gz"
    assert hashlib.sha256(baseline_path.read_bytes()).hexdigest() == manifest["baseline_progress_sha256"]
    assert hashlib.sha256(bundle_path.read_bytes()).hexdigest() == manifest["PROD"]["bundle_file_sha256"]
    assert hashlib.sha256(capture_path.read_bytes()).hexdigest() == manifest["PROD"]["capture_file_sha256"]
    baseline = json.loads(gzip.decompress(baseline_path.read_bytes()))
    bundle = json.loads(gzip.decompress(bundle_path.read_bytes()))
    capture = json.loads(gzip.decompress(capture_path.read_bytes()))
    applied = json.loads((D / "PROD-apply.json").read_text())
    verified = json.loads((D / "PROD-verify.json").read_text())
    sha = registry_sha256(bundle)
    assert sha == manifest["PROD"]["bundle_sha256"]
    targets = {row["owner"]["id"]: row["lang"] for row in bundle["candidates"]}
    expected_names = {row["owner"]["id"]: row["display_name"] for row in bundle["candidates"]}
    assert baseline["applied_batch_id"] == 594 and baseline["players_done_count"] == 1707
    assert len(targets) == len(expected_names) == 16 and capture["unique_albums"] == 158
    assert capture["game_slots"] == 160
    assert applied["status"] == "applied" and applied["batch_id"] == 595
    assert verified["passed"] and verified["bundle_sha256"] == sha
    assert verified["album_count"] == 158 and verified["game_slots"] == 160
    assert verified["verified_name_count"] == verified["complete_players_delta"] == 16
    assert verified["read_qualified_count"] == 80
    old_done = {row["player_id"] for row in baseline["players_done"]}
    old_events = {row["event_id"] for row in baseline["events_done"]}
    assert not old_done.intersection(targets)
    with engine.connect().execution_options(isolation_level="REPEATABLE READ") as conn:
        with conn.begin():
            conn.execute(text("SET TRANSACTION READ ONLY"))
            album_ids = captured_physical_guard(conn, capture, targets)
            with Session(bind=conn) as db:
                batch = db.get(KifuNameBatch, 595)
                assert batch is not None and batch.status == "applied" and batch.bundle_sha256 == sha
                ledger = Counter(db.scalars(select(KifuNameChange.target_table).where(
                    KifuNameChange.batch_id == 595)).all())
                assert ledger["kifu_player_names"] == ledger["kifu_name_research_evidence"] == 16
                assert set(ledger) <= {"kifu_player_names", "kifu_name_research_evidence",
                                       "kifu_name_source_registry"}
                players, done = catalog_completion(db, KifuPlayer, KifuPlayerName, "player_id")
                events, event_done = catalog_completion(db, KifuEvent, KifuEventName, "event_id")
                assert done == old_done | set(targets) and event_done == old_events
                assert len(players) == baseline["player_total"] and len(events) == baseline["event_total"]
                qualified = {name.player_id: name for name, _ in _qualified_name_rows(
                    db, _approved_names(db, KifuPlayerName, "player_id", set(targets)),
                    KifuPlayerName, "player_id") if name.lang == targets[name.player_id]}
                assert set(qualified) == set(targets)
                assert all(qualified[pid].display_name == expected_names[pid] and
                           qualified[pid].decision_kind == "conventional" for pid in targets)
                games, black, white, linked_events = db.execute(select(
                    func.count(KifuAlbum.id), func.count(KifuAlbum.black_player_id),
                    func.count(KifuAlbum.white_player_id), func.count(KifuAlbum.event_id))).one()
                assert games == baseline["games"] and black + white == baseline["linked_player_slots"]
                assert linked_events == baseline["linked_event_games"]
                delta = bounded(db, album_ids, targets)
                direct = db.execute(select(func.count(KifuAlbum.id)).where(
                    KifuAlbum.black_player_id.in_(done), KifuAlbum.white_player_id.in_(done),
                    KifuAlbum.event_id.in_(event_done))).scalar_one()
    current = dict(baseline)
    current["observed_at"] = datetime.now(timezone.utc).isoformat()
    current["baseline_batch_id"] = 594
    current["applied_batch_id"] = 595
    current["players_done"] = [{"canonical_name": players[pid], "languages": LANGUAGES, "player_id": pid}
                               for pid in sorted(done, key=lambda pid: (players[pid], pid))]
    current["players_done_count"] = len(done)
    current["both_players_five_lang_games"] += delta.get("after_both", 0) - delta.get("before_both", 0)
    current["complete_five_lang_games"] += delta.get("after_formal", 0) - delta.get("before_formal", 0)
    current["complete_five_lang_raw_games"] += delta.get("after_raw", 0) - delta.get("before_raw", 0)
    current["complete_five_lang_display_games"] = (current["complete_five_lang_games"] +
                                                  current["complete_five_lang_raw_games"])
    current["base_entity_names_games"] = direct
    current["coverage_method"] = ("批次595后 r5 native strict_slot_approvals；仅在158局受影响棋谱模拟批次前16个"
                                  "目标语言名字未合格，计算实际增量；其余棋局继承实际594基线")
    for key, denominator in (("players_done_count", "player_total"),
                             ("both_players_five_lang_games", "games"),
                             ("complete_five_lang_games", "games"),
                             ("complete_five_lang_raw_games", "games"),
                             ("complete_five_lang_display_games", "games"),
                             ("base_entity_names_games", "games")):
        current[key + "_pct"] = round(100 * current[key] / current[denominator], 4)
    assert current["players_done_count"] == 1723
    assert current["complete_five_lang_display_games"] >= baseline["complete_five_lang_display_games"]
    audit = {"environment": "PROD", "batch_id": 595, "bundle_sha256": sha, "read_only": True,
             "method": "r5 native strict_slot_approvals with only 16 target name cells masked before",
             "bounded_scope": delta, "ledger_targets": dict(ledger), "baseline_batch_id": 594,
             "players_done_before": 1707, "players_done_after": 1723,
             "base_entity_names_games": direct}
    return {"progress": current, "audit": audit}


if __name__ == "__main__":
    engine = create_engine(os.environ["KATRAIN_DATABASE_URL"],
                           connect_args={"options": "-c default_transaction_read_only=on"})
    try:
        print(json.dumps(report(engine), ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    finally:
        engine.dispose()
