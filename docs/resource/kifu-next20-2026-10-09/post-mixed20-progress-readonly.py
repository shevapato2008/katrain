"""Read-only bounded strict-coverage delta after approved PROD mixed20 batch.

The remote runner injects `progress` from the existing progress helper and
passes the actual post-590 baseline. This module only emits JSON to stdout.
"""

import json
from datetime import datetime, timezone

from sqlalchemy import func, or_, select, text
from sqlalchemy.orm import Session, defer

import progress


EXPECTED_BATCH = ACTUAL_BATCH_ID
EXPECTED_BUNDLE_SHA256 = ACTUAL_BUNDLE_SHA256
EXPECTED_GAMES = 1568
EXPECTED_SLOTS = 1613


def measure(db, ids, page_size=300):
    last_id = 0
    result = {key: 0 for key in (
        "games", "slots", "before_both", "after_both", "before_formal", "after_formal",
        "before_raw", "after_raw", "before_hidden_event_both", "after_hidden_event_both",
    )}
    while True:
        albums = (db.query(progress.KifuAlbum)
                  .options(defer(progress.KifuAlbum.sgf_content), defer(progress.KifuAlbum.search_text))
                  .filter(progress.KifuAlbum.id > last_id)
                  .filter(or_(progress.KifuAlbum.black_player_id.in_(ids),
                              progress.KifuAlbum.white_player_id.in_(ids)))
                  .order_by(progress.KifuAlbum.id).limit(page_size).all())
        if not albums:
            break
        selected = progress.live_event_selections(db, albums)
        obscured = progress.obscured_program_event_ids(db, albums, selected_events=selected)
        counts = {album.id: [[0, 0, 0], [0, 0, 0]] for album in albums}
        for language in progress.LANGUAGES:
            approvals = progress.strict_slot_approvals(
                db, albums, language, selected_events=selected, obscured_event_ids=obscured
            )
            for album in albums:
                after = approvals[album.id]
                before = list(after)
                if language == TARGET_LANGS.get(album.black_player_id):
                    before[0] = None
                if language == TARGET_LANGS.get(album.white_player_id):
                    before[1] = None
                for which, values in enumerate((before, after)):
                    for slot, value in enumerate(values):
                        counts[album.id][which][slot] += value is not None
        for album in albums:
            result["games"] += 1
            result["slots"] += (album.black_player_id in ids) + (album.white_player_id in ids)
            event_raw, event_id = selected.get(album.id, (album.event, album.event_id))
            for label, values in zip(("before", "after"), counts[album.id]):
                black, white, event = [value == len(progress.LANGUAGES) for value in values]
                if not black or not white:
                    continue
                result[label + "_both"] += 1
                if event_id:
                    result[label + "_formal"] += event
                elif (event_raw or "").strip():
                    result[label + "_raw"] += event
                else:
                    result[label + "_hidden_event_both"] += 1
        last_id = albums[-1].id
    return result


def report(engine, baseline):
    expected_ids = {row["owner"]["id"]: row["display_name"]
                    for row in APPROVED_CANDIDATES}
    if len(expected_ids) != 20 or len(APPROVED_CANDIDATES) != 20:
        raise ValueError("approved batch 591 candidates must be exactly 20 distinct owners")
    ids = set(expected_ids)
    global TARGET_LANGS
    TARGET_LANGS = {row["owner"]["id"]: row["lang"] for row in APPROVED_CANDIDATES}
    old_done = {row["player_id"] for row in baseline["players_done"]}
    old_events = {row["event_id"] for row in baseline["events_done"]}
    if ids & old_done or baseline["applied_batch_id"] != 590:
        raise ValueError("post-590 baseline or old target proof scope differs")
    connection = engine.connect().execution_options(isolation_level="REPEATABLE READ")
    try:
        with connection.begin():
            connection.execute(text("SET TRANSACTION READ ONLY"))
            with Session(bind=connection) as db:
                batch = db.get(progress.KifuNameBatch, EXPECTED_BATCH)
                if batch is None or batch.status != "applied" or batch.bundle_sha256 != EXPECTED_BUNDLE_SHA256:
                    raise ValueError("expected applied PROD batch 591 absent or bundle mismatch")
                players, done = progress._catalog_completion(
                    db, progress.KifuPlayer, progress.KifuPlayerName, "player_id"
                )
                events, event_done = progress._catalog_completion(
                    db, progress.KifuEvent, progress.KifuEventName, "event_id"
                )
                if (done != old_done | ids or event_done != old_events
                    or len(players) != baseline["player_total"] or len(events) != baseline["event_total"]):
                    raise ValueError("native qualified catalog differs beyond approved mixed20 scope")
                qualified = {
                    name.player_id: name
                    for name, _ in progress._qualified_name_rows(
                        db, progress._approved_names(db, progress.KifuPlayerName, "player_id", ids),
                        progress.KifuPlayerName, "player_id"
                    ) if name.lang == TARGET_LANGS[name.player_id]
                }
                if set(qualified) != ids or any(qualified[i].display_name != expected_ids[i] for i in ids):
                    raise ValueError("the 20 current target name cells differ from approved values or fail native proof")
                names = [{"owner_id": i, "lang": TARGET_LANGS[i], "display_name": qualified[i].display_name,
                          "status": qualified[i].status, "reference_url": qualified[i].reference_url,
                          "decision_kind": qualified[i].decision_kind, "evidence_id": qualified[i].evidence_id}
                         for i in sorted(ids)]
                if any(row["status"] != "verified" or row["decision_kind"] != "generated" for row in names):
                    raise ValueError("mixed20 generated names changed status or decision kind")
                games, black, white, linked_event = db.execute(select(
                    func.count(progress.KifuAlbum.id), func.count(progress.KifuAlbum.black_player_id),
                    func.count(progress.KifuAlbum.white_player_id), func.count(progress.KifuAlbum.event_id)
                )).one()
                if (games != baseline["games"] or black + white != baseline["linked_player_slots"]
                    or linked_event != baseline["linked_event_games"]):
                    raise ValueError("album or foreign-key totals changed from post-590 baseline")
                bounded = measure(db, ids)
                if bounded["games"] != EXPECTED_GAMES or bounded["slots"] != EXPECTED_SLOTS:
                    raise ValueError("mixed20 affected game or slot scope changed")
                if bounded["before_both"] > bounded["after_both"]:
                    raise ValueError("post-mixed20 player qualification reduced bounded strict coverage")
                direct = db.execute(select(func.count(progress.KifuAlbum.id)).where(
                    progress.KifuAlbum.black_player_id.in_(done),
                    progress.KifuAlbum.white_player_id.in_(done),
                    progress.KifuAlbum.event_id.in_(event_done)
                )).scalar_one()
    finally:
        connection.close()
    current = dict(baseline)
    current["observed_at"] = datetime.now(timezone.utc).isoformat()
    current["applied_batch_id"] = EXPECTED_BATCH
    current["baseline_batch_id"] = 590
    current["players_done"] = [
        {"canonical_name": players[i], "languages": progress.LANGUAGES, "player_id": i}
        for i in sorted(done, key=lambda i: (players[i], i))
    ]
    current["players_done_count"] = len(done)
    current["both_players_five_lang_games"] += bounded["after_both"] - bounded["before_both"]
    current["complete_five_lang_games"] += bounded["after_formal"] - bounded["before_formal"]
    current["complete_five_lang_raw_games"] += bounded["after_raw"] - bounded["before_raw"]
    current["complete_five_lang_display_games"] = (current["complete_five_lang_games"]
                                                  + current["complete_five_lang_raw_games"])
    current["base_entity_names_games"] = direct
    current["base_entity_names_games_pct"] = round(100 * direct / current["games"], 4)
    current["unqualified_legacy_ko_count"] = 8
    current["coverage_method"] = (
        "批次591后 r3 native strict_slot_approvals；仅在1568局受影响棋谱模拟批次前各目标语言未合格，计算实际增量；其余棋局继承实际590基线，未作独立全库严格卡片扫描"
    )
    for key, denominator in (("players_done_count", "player_total"),
                             ("both_players_five_lang_games", "games"),
                             ("complete_five_lang_games", "games"),
                             ("complete_five_lang_raw_games", "games"),
                             ("complete_five_lang_display_games", "games")):
        current[key + "_pct"] = round(100 * current[key] / current[denominator], 4)
    audit = {"environment": "PROD", "batch_id": EXPECTED_BATCH,
             "bundle_sha256": EXPECTED_BUNDLE_SHA256,
             "read_only": True, "method": "r3 native strict_slot_approvals with bounded pre-proof mixed20 target slot mask",
             "bounded_scope": bounded,
             "players_done_before": len(old_done), "players_done_after": len(done),
             "base_entity_names_games": direct,
             "note": "No independent global strict-card scan. All other album contributions inherit the actual post-590 baseline."}
    return current, audit, names


if __name__ == "__main__":
    from sqlalchemy import create_engine
    import os
    engine = create_engine(os.environ["KATRAIN_DATABASE_URL"],
                           connect_args={"options": "-c default_transaction_read_only=on"})
    try:
        current, audit, names = report(engine, BASELINE)
    finally:
        engine.dispose()
    print(json.dumps({"progress": current, "audit": audit, "live_target_names": names},
                     ensure_ascii=False, sort_keys=True, default=str))
