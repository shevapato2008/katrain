"""After apply, refresh ret163-style progress using native names and only TW20 games.

Run inside the pinned name importer with KATRAIN_DATABASE_URL set. This script
does not write to PostgreSQL. It refuses a changed catalog/album baseline.
"""

import argparse
import json
import os
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import Column, String, create_engine, func, or_, select, text
from sqlalchemy.orm import Session, column_property, defer

from katrain.web.core.models_db import (
    KifuAlbum, KifuAlbumEventSelection, KifuEvent, KifuEventName, KifuNameBatch,
    KifuPlayer, KifuPlayerName,
)
from katrain.web.kifu.identity import (
    PRIMARY_NAME_LANGUAGES, _approved_names, _approved_raw_event_names,
    _approved_raw_player_names, _empty_event, _qualified_name_rows,
    _raw_event_map, _raw_event_value, _raw_player_slot,
    live_event_selections, obscured_program_event_ids, strict_slot_approvals,
)
from katrain.web.kifu.name_parse import parse_event
from katrain.web.kifu.name_structure import structure_event


HERE = Path(__file__).parent
IDS = {
    "PROD": {6752, 6765, 6768, 5365, 5211, 3993, 6713, 6447, 5581, 6376,
             5893, 4552, 3906, 5933, 4023, 4572, 5040, 4801, 6215, 6458},
    "TEST": {12521, 12534, 12537, 11141, 10991, 9789, 12482, 12211, 11354, 12142,
             11662, 10342, 9703, 11702, 9819, 10362, 10822, 10588, 11981, 12222},
}
BUNDLES = {
    "PROD": "f3dd90706ac81fa93cbb24624765ffc3a4420a07fc68fffc8b56b60a879e833b",
    "TEST": "3a1674c16863a0e95dd7782156b0b05cd757afdd429e5b01519d649324bffec0",
}
OLD_KO_WITHOUT_NATIVE_PROOF = {3771, 3778, 3792, 3900, 3902, 4121, 4266, 4421,
                               4499, 4568, 4587, 4842, 5158, 5237, 5244, 5413,
                               5877, 6252, 6260, 6261, 6270, 6496, 6581, 6608,
                               6627, 6631, 6635, 6642}
LANGUAGES = sorted(PRIMARY_NAME_LANGUAGES)

# The pinned importer carries the current identity reader with an older album
# mapping. Add the existing database column to this process's read-only mapper.
if not hasattr(KifuAlbum, "list_hidden_reason"):
    KifuAlbum.__table__.append_column(Column("list_hidden_reason", String(64)))
    KifuAlbum.list_hidden_reason = column_property(KifuAlbum.__table__.c.list_hidden_reason)


def _catalog_completion(db, entity, name_model, id_field):
    people = dict(db.execute(select(entity.id, entity.canonical_name)).all())
    languages = defaultdict(set)
    rows = _qualified_name_rows(db, _approved_names(db, name_model, id_field), name_model, id_field)
    for name, _ in rows:
        if name.lang in PRIMARY_NAME_LANGUAGES:
            languages[getattr(name, id_field)].add(name.lang)
    done = {owner_id for owner_id in people if languages[owner_id] == PRIMARY_NAME_LANGUAGES}
    return people, done


class _CachedApprovals:
    """One snapshot of product-qualified names; retain product's per-album scope checks."""

    def __init__(self, db):
        self.players = {}
        self.events = {}
        self.raw_players = {}
        self.raw_events = {}
        for language in LANGUAGES:
            self.players[language] = {
                name.player_id: (name.decision_kind, name.evidence_id)
                for name, _ in _qualified_name_rows(
                    db, _approved_names(db, KifuPlayerName, "player_id", lang=language),
                    KifuPlayerName, "player_id"
                )
            }
            self.events[language] = {
                name.event_id: (name.decision_kind, name.evidence_id)
                for name, _ in _qualified_name_rows(
                    db, _approved_names(db, KifuEventName, "event_id", lang=language),
                    KifuEventName, "event_id"
                )
            }
            self.raw_players[language] = {
                raw: ((name.decision_kind, name.evidence_id), scope)
                for name, raw, scope in _approved_raw_player_names(db, lang=language)
            }
            by_raw = defaultdict(list)
            for row in _approved_raw_event_names(db, lang=language):
                by_raw[row[1]].append(row)
            self.raw_events[language] = by_raw
        self.canonical_events = dict(db.execute(select(KifuEvent.id, KifuEvent.canonical_name)).all())

    def approvals(self, db, albums, language, selected, obscured):
        raw_values = {album.event or "" for album in albums}
        raw_values.update(raw for raw, _ in selected.values())
        rows = [row for raw in raw_values for row in self.raw_events[language].get(raw, ())]
        selected_ids = (
            {album_id for (album_id,) in db.query(KifuAlbumEventSelection.album_id).filter(
                KifuAlbumEventSelection.album_id.in_([album.id for album in albums]))}
            if any(name.decision_kind == "translated" for name, _, _ in rows) else set()
        )
        raw_events = _raw_event_map(rows, albums, selected, approvals=True, selected_ids=selected_ids)
        players = self.players[language]
        events = self.events[language]
        raw_players = self.raw_players[language]
        result = {}
        for album in albums:
            event_raw, event_id = selected.get(album.id, (album.event, album.event_id))
            black = players.get(album.black_player_id) if album.black_player_id else _raw_player_slot(raw_players, album, "black")
            white = players.get(album.white_player_id) if album.white_player_id else _raw_player_slot(raw_players, album, "white")
            if event_id:
                event_approval = events.get(event_id)
                if parse_event(event_raw, None).category == "formal_event_candidate":
                    event_approval = (
                        _raw_event_value(raw_events, album.id, event_raw, event_id)
                        if event_approval and self.canonical_events.get(event_id) == "Oteai"
                        else None
                    )
                elif event_approval:
                    event_approval = _raw_event_value(
                        raw_events, album.id, event_raw, event_id,
                        None if structure_event(event_raw or "")["components"] else event_approval,
                    )
            else:
                event_approval = (("hidden", None) if _empty_event(event_raw)
                                  else _raw_event_value(raw_events, album.id, event_raw or "", event_id))
            if album.id in obscured:
                event_approval = None
            result[album.id] = black, white, event_approval
        return result


def _affected_completion(db, ids, page_size, cached=None):
    if page_size < 1:
        raise ValueError("page size must be positive")
    last_id = 0
    pages = 0
    result = {"affected_games": 0, "affected_slots": 0, "both_players": 0,
              "formal_cards": 0, "raw_cards": 0, "hidden_event_both_players": 0,
              "formal_event_games": 0, "raw_event_games": 0}
    while True:
        query = (db.query(KifuAlbum)
                 .options(defer(KifuAlbum.sgf_content), defer(KifuAlbum.search_text))
                 .filter(KifuAlbum.id > last_id))
        if ids is not None:
            query = query.filter(or_(KifuAlbum.black_player_id.in_(ids), KifuAlbum.white_player_id.in_(ids)))
        albums = query.order_by(KifuAlbum.id).limit(page_size).all()
        if not albums:
            break
        selected = live_event_selections(db, albums)
        obscured = obscured_program_event_ids(db, albums, selected_events=selected)
        counts = {album.id: [0, 0, 0] for album in albums}
        for language in LANGUAGES:
            approvals = (cached.approvals(db, albums, language, selected, obscured) if cached else
                         strict_slot_approvals(db, albums, language,
                                               selected_events=selected, obscured_event_ids=obscured))
            for album in albums:
                for index, approval in enumerate(approvals[album.id]):
                    counts[album.id][index] += approval is not None
        for album in albums:
            result["affected_games"] += 1
            if ids is not None:
                result["affected_slots"] += ((album.black_player_id in ids) + (album.white_player_id in ids))
            complete = [value == len(LANGUAGES) for value in counts[album.id]]
            event_raw, event_id = selected.get(album.id, (album.event, album.event_id))
            if event_id:
                result["formal_event_games"] += complete[2]
                if all(complete[:2]):
                    result["formal_cards"] += complete[2]
            elif (event_raw or "").strip():
                result["raw_event_games"] += complete[2]
                if all(complete[:2]):
                    result["raw_cards"] += complete[2]
            elif all(complete[:2]):
                result["hidden_event_both_players"] += 1
            result["both_players"] += all(complete[:2])
        last_id = albums[-1].id
        pages += 1
        if ids is None and pages % 20 == 0:
            print(f"full native scan: {result['affected_games']} albums checked", flush=True)
    return result


def report(engine, environment, batch_id, baseline, page_size=300, full_native=False, cached_native=False):
    target_ids = IDS[environment]
    old_players = {row["player_id"] for row in baseline["players_done"]}
    old_events = {row["event_id"] for row in baseline["events_done"]}
    if old_players & target_ids:
        raise ValueError("ret163 baseline already contains a TW20 target")
    connection = engine.connect().execution_options(isolation_level="REPEATABLE READ")
    try:
        with connection.begin():
            connection.execute(text("SET TRANSACTION READ ONLY"))
            with Session(bind=connection) as db:
                batch = db.get(KifuNameBatch, batch_id)
                if batch is None or batch.status != "applied" or batch.bundle_sha256 != BUNDLES[environment]:
                    raise ValueError("expected TW20 bundle is not applied")
                players, player_done = _catalog_completion(db, KifuPlayer, KifuPlayerName, "player_id")
                events, event_done = _catalog_completion(db, KifuEvent, KifuEventName, "event_id")
                if not target_ids <= player_done:
                    raise ValueError(f"TW20 targets missing complete names: {sorted(target_ids - player_done)}")
                expected_done = old_players | target_ids
                if full_native and environment == "PROD":
                    expected_done -= OLD_KO_WITHOUT_NATIVE_PROOF
                if (len(players) != baseline["player_total"] or len(events) != baseline["event_total"]
                    or player_done != expected_done or event_done != old_events):
                    raise ValueError(
                        "catalog completion changed outside the approved TW20 scope: "
                        f"player totals {len(players)}/{baseline['player_total']}, "
                        f"event totals {len(events)}/{baseline['event_total']}, "
                        f"player unexpected count {len(player_done - old_players - target_ids)}, "
                        f"player missing {sorted(expected_done - player_done)}, "
                        f"event unexpected count {len(event_done - old_events)}, "
                        f"event missing count {len(old_events - event_done)}"
                    )
                games, linked_black, linked_white, linked_events = db.execute(select(
                    func.count(KifuAlbum.id), func.count(KifuAlbum.black_player_id),
                    func.count(KifuAlbum.white_player_id), func.count(KifuAlbum.event_id)
                )).one()
                if (games != baseline["games"]
                    or linked_black + linked_white != baseline["linked_player_slots"]
                    or linked_events != baseline["linked_event_games"]):
                    raise ValueError("game or FK totals changed since the ret163 baseline")
                cached = _CachedApprovals(db) if cached_native else None
                if cached:
                    print("qualified name cache ready; comparing sample pages", flush=True)
                if cached:
                    for sample_start in (0, 80000, 170000):
                        sample = (db.query(KifuAlbum)
                                  .options(defer(KifuAlbum.sgf_content), defer(KifuAlbum.search_text))
                                  .filter(KifuAlbum.id > sample_start)
                                  .order_by(KifuAlbum.id).limit(3).all())
                        selected = live_event_selections(db, sample)
                        obscured = obscured_program_event_ids(db, sample, selected_events=selected)
                        for language in LANGUAGES:
                            direct = strict_slot_approvals(
                                db, sample, language, selected_events=selected, obscured_event_ids=obscured
                            )
                            if cached.approvals(db, sample, language, selected, obscured) != direct:
                                raise ValueError(f"cached reader differs from product at {sample_start}/{language}")
                delta = _affected_completion(db, target_ids, page_size, cached)
                if delta["affected_slots"] != 1185 or delta["affected_games"] != 1158:
                    raise ValueError("TW20 album scope changed since the frozen inventory")
                native = _affected_completion(db, None, page_size, cached) if full_native else None
                if native and native["affected_games"] != games:
                    raise ValueError("full native scan missed albums")
    finally:
        connection.close()
    updated = dict(baseline)
    updated["observed_at"] = datetime.now(timezone.utc).isoformat()
    updated["players_done"] = [
        {"canonical_name": players[owner_id], "languages": LANGUAGES, "player_id": owner_id}
        for owner_id in sorted(player_done, key=lambda owner_id: (players[owner_id], owner_id))
    ]
    updated["events_done"] = [
        {"canonical_name": events[owner_id], "event_id": owner_id, "languages": LANGUAGES}
        for owner_id in sorted(event_done, key=lambda owner_id: (events[owner_id], owner_id))
    ]
    if native:
        updated.update({
            "players_done_count": len(player_done),
            "events_done_count": len(event_done),
            "both_players_five_lang_games": native["both_players"],
            "complete_five_lang_games": native["formal_cards"],
            "complete_five_lang_raw_games": native["raw_cards"],
            "complete_five_lang_display_games": native["formal_cards"] + native["raw_cards"],
            "event_five_lang_games": native["formal_event_games"],
            "raw_event_five_lang_games": native["raw_event_games"],
        })
    else:
        for key, amount in (
            ("players_done_count", 20),
            ("both_players_five_lang_games", delta["both_players"]),
            ("complete_five_lang_games", delta["formal_cards"]),
            ("complete_five_lang_raw_games", delta["raw_cards"]),
            ("complete_five_lang_display_games", delta["formal_cards"] + delta["raw_cards"]),
        ):
            updated[key] = baseline[key] + amount
    if updated["complete_five_lang_display_games"] != (
        updated["complete_five_lang_games"] + updated["complete_five_lang_raw_games"]
    ):
        raise ValueError("formal/raw display card counts do not reconcile")
    for key, denominator in (
        ("players_done_count", "player_total"),
        ("events_done_count", "event_total"),
        ("both_players_five_lang_games", "games"),
        ("complete_five_lang_games", "games"),
        ("complete_five_lang_raw_games", "games"),
        ("complete_five_lang_display_games", "games"),
        ("event_five_lang_games", "games"),
        ("raw_event_five_lang_games", "games"),
    ):
        updated[key + "_pct"] = round(updated[key] * 100 / updated[denominator], 4)
    return updated, {"bounded_tw20": delta, "full_native": native,
                     "old_ko_without_native_proof": sorted(OLD_KO_WITHOUT_NATIVE_PROOF) if native else []}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--environment", choices=("PROD", "TEST"), required=True)
    parser.add_argument("--batch-id", type=int, required=True)
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--audit-output", type=Path)
    parser.add_argument("--page-size", type=int, default=300)
    parser.add_argument("--full-native", action="store_true",
                        help="Recompute global strict coverage when the archived progress used older eligibility")
    parser.add_argument("--cached-native", action="store_true",
                        help="Cache product-qualified names once and compare three sample pages")
    args = parser.parse_args()
    baseline_path = args.baseline or HERE / f"{args.environment}-ret163-progress-baseline.json"
    baseline = json.loads(baseline_path.read_text())
    database_url = os.environ.get("KATRAIN_DATABASE_URL")
    if not database_url:
        raise ValueError("KATRAIN_DATABASE_URL must be set in the importer process")
    engine = create_engine(database_url)
    try:
        current, delta = report(engine, args.environment, args.batch_id, baseline, args.page_size,
                                args.full_native, args.cached_native)
    finally:
        engine.dispose()
    args.output.write_text(json.dumps(current, ensure_ascii=False, sort_keys=True, indent=2) + "\n")
    if args.audit_output:
        args.audit_output.write_text(json.dumps({"environment": args.environment, "batch_id": args.batch_id,
                                                "bundle_sha256": BUNDLES[args.environment],
                                                "bounded_delta": delta}, ensure_ascii=False,
                                               sort_keys=True, indent=2) + "\n")
    print(json.dumps({"players": current["players_done_count"], "events": current["events_done_count"],
                      "both_players": current["both_players_five_lang_games"],
                      "formal_cards": current["complete_five_lang_games"],
                      "raw_cards": current["complete_five_lang_raw_games"],
                      "full_display_cards": current["complete_five_lang_display_games"],
                      "bounded_delta": delta}, ensure_ascii=False))


if __name__ == "__main__":
    main()
