"""Refresh strict progress after batch 589 using only its affected games."""

import argparse
import gzip
import importlib.util
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import create_engine, func, or_, select, text
from sqlalchemy.orm import Session, defer

HERE = Path(__file__).resolve().parent
BASELINE = HERE / "PROD-progress-actual.json"
BUNDLE = HERE / "PROD-589-unsigned-bundle.json.gz"
EXPECTED_SHA = "ebc1a45c8aad3ffcc0fafa05df07861918019fa4b8c8396dc5fbb278fbfb25f1"

spec = importlib.util.spec_from_file_location("tw20_progress", HERE / "post-progress-readonly.py")
progress = importlib.util.module_from_spec(spec)
spec.loader.exec_module(progress)

KifuAlbum = progress.KifuAlbum
KifuNameBatch = progress.KifuNameBatch
KifuPlayer = progress.KifuPlayer
KifuPlayerName = progress.KifuPlayerName
KifuEvent = progress.KifuEvent


def measure(db, ids, newly_missing, page_size):
    last_id = 0
    result = {key: 0 for key in (
        "games", "slots", "before_both", "after_both", "before_formal", "after_formal",
        "before_raw", "after_raw", "before_hidden_event_both", "after_hidden_event_both",
    )}
    while True:
        albums = (db.query(KifuAlbum)
                  .options(defer(KifuAlbum.sgf_content), defer(KifuAlbum.search_text))
                  .filter(KifuAlbum.id > last_id)
                  .filter(or_(KifuAlbum.black_player_id.in_(ids), KifuAlbum.white_player_id.in_(ids)))
                  .order_by(KifuAlbum.id).limit(page_size).all())
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
                if newly_missing.get(album.black_player_id) == language:
                    before[0] = None
                if newly_missing.get(album.white_player_id) == language:
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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--audit-output", type=Path, required=True)
    parser.add_argument("--live-names-output", type=Path, required=True)
    parser.add_argument("--page-size", type=int, default=300)
    args = parser.parse_args()
    baseline = json.loads(BASELINE.read_text())
    bundle = json.load(gzip.open(BUNDLE, "rt"))
    newly_missing = {row["owner"]["id"]: row["lang"] for row in bundle["candidates"]}
    ids = set(newly_missing)
    if len(ids) != 20 or any(row.get("name_preimage_sha256") is not None for row in bundle["candidates"]):
        raise ValueError("batch 589 must contain 20 new single-language names")
    old_done = {row["player_id"] for row in baseline["players_done"]}
    old_events = {row["event_id"] for row in baseline["events_done"]}
    engine = create_engine(os.environ["KATRAIN_DATABASE_URL"])
    connection = engine.connect().execution_options(isolation_level="REPEATABLE READ")
    try:
        with connection.begin():
            connection.execute(text("SET TRANSACTION READ ONLY"))
            with Session(bind=connection) as db:
                batch = db.get(KifuNameBatch, 589)
                if batch is None or batch.status != "applied" or batch.bundle_sha256 != EXPECTED_SHA:
                    raise ValueError("expected applied batch 589 is absent")
                players, player_done = progress._catalog_completion(
                    db, KifuPlayer, KifuPlayerName, "player_id"
                )
                events, event_done = progress._catalog_completion(
                    db, KifuEvent, progress.KifuEventName, "event_id"
                )
                if (player_done != old_done or event_done != old_events
                    or len(players) != baseline["player_total"] or len(events) != baseline["event_total"]):
                    raise ValueError(
                        "global qualified catalog differs beyond batch 589: "
                        f"player extra {sorted(player_done - old_done)}, "
                        f"player missing {sorted(old_done - player_done)}, "
                        f"event extra {sorted(event_done - old_events)}, "
                        f"event missing {sorted(old_events - event_done)}, "
                        f"totals {len(players)}/{len(events)}"
                    )
                live = {}
                for row in db.execute(select(KifuPlayerName).where(KifuPlayerName.player_id.in_(ids))).scalars():
                    if newly_missing[row.player_id] == row.lang:
                        live[row.player_id] = {
                            "owner_id": row.player_id, "lang": row.lang, "display_name": row.display_name,
                            "status": row.status, "reference_url": row.reference_url,
                            "decision_kind": row.decision_kind, "evidence_id": row.evidence_id,
                        }
                expected_names = {(row["owner"]["id"], row["lang"], row["display_name"])
                                  for row in bundle["candidates"]}
                if {(row["owner_id"], row["lang"], row["display_name"]) for row in live.values()} != expected_names:
                    raise ValueError("live batch 589 name values differ from approved candidates")
                qualified_new = set()
                for language in set(newly_missing.values()):
                    language_ids = {owner_id for owner_id, lang in newly_missing.items() if lang == language}
                    for name, _ in progress._qualified_name_rows(
                        db, progress._approved_names(db, KifuPlayerName, "player_id", language_ids, language),
                        KifuPlayerName, "player_id"
                    ):
                        qualified_new.add((name.player_id, name.lang, name.display_name))
                if qualified_new != expected_names:
                    raise ValueError("one or more new batch 589 cells fail native qualification")
                bounded = measure(db, ids, newly_missing, args.page_size)
                if bounded["games"] != 1869:
                    raise ValueError("batch 589 affected game scope changed")
                games, linked_black, linked_white, linked_events = db.execute(select(
                    func.count(KifuAlbum.id), func.count(KifuAlbum.black_player_id),
                    func.count(KifuAlbum.white_player_id), func.count(KifuAlbum.event_id)
                )).one()
                if (games != baseline["games"] or linked_black + linked_white != baseline["linked_player_slots"]
                    or linked_events != baseline["linked_event_games"]):
                    raise ValueError("catalog or game associations changed")
                direct = db.execute(select(func.count(KifuAlbum.id)).where(
                    KifuAlbum.black_player_id.in_(player_done), KifuAlbum.white_player_id.in_(player_done),
                    KifuAlbum.event_id.in_(event_done)
                )).scalar_one()
    finally:
        connection.close()
        engine.dispose()
    current = dict(baseline)
    current["observed_at"] = datetime.now(timezone.utc).isoformat()
    current["applied_batch_id"] = 589
    current["baseline_batch_id"] = 588
    current["players_done"] = [
        {"canonical_name": players[owner_id], "languages": progress.LANGUAGES, "player_id": owner_id}
        for owner_id in sorted(player_done, key=lambda owner_id: (players[owner_id], owner_id))
    ]
    current["players_done_count"] = len(player_done)
    current["both_players_five_lang_games"] += bounded["after_both"] - bounded["before_both"]
    current["complete_five_lang_games"] += bounded["after_formal"] - bounded["before_formal"]
    current["complete_five_lang_raw_games"] += bounded["after_raw"] - bounded["before_raw"]
    current["complete_five_lang_display_games"] = (current["complete_five_lang_games"]
                                                  + current["complete_five_lang_raw_games"])
    current["base_entity_names_games"] = direct
    current["base_entity_names_games_pct"] = round(100 * direct / current["games"], 4)
    for key, denominator in (("players_done_count", "player_total"),
                             ("both_players_five_lang_games", "games"),
                             ("complete_five_lang_games", "games"),
                             ("complete_five_lang_raw_games", "games"),
                             ("complete_five_lang_display_games", "games")):
        current[key + "_pct"] = round(100 * current[key] / current[denominator], 4)
    args.output.write_text(json.dumps(current, ensure_ascii=False, sort_keys=True, indent=2) + "\n")
    args.audit_output.write_text(json.dumps({
        "environment": "PROD", "batch_id": 589, "bundle_sha256": EXPECTED_SHA,
        "bounded_scope": bounded, "player_count_before": len(old_done),
        "player_count_after": len(player_done), "base_entity_names_games": direct,
        "method": "r2 product strict_slot_approvals, batch 589 preimage simulated by omitting only 20 new language slots",
    }, ensure_ascii=False, sort_keys=True, indent=2) + "\n")
    args.live_names_output.write_text(json.dumps({"environment": "PROD", "batch_id": 589,
                                                  "observed_at": current["observed_at"],
                                                  "rows": sorted(live.values(), key=lambda row: row["owner_id"])},
                                                 ensure_ascii=False, sort_keys=True, indent=2) + "\n")
    print(json.dumps({"players": len(player_done), "bounded": bounded,
                      "strict_full_cards": current["complete_five_lang_display_games"],
                      "base_entity_names_games": direct}, ensure_ascii=False))


if __name__ == "__main__":
    main()
