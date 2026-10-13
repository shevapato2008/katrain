"""Frozen, exact-raw player links for the independently reviewed next 15 names."""

import hashlib
import unicodedata

from sqlalchemy import or_, select, text, update
from sqlalchemy.orm import Session

from katrain.core.sgf_parser import SGF
from katrain.web.core.models_db import KifuAlbum, KifuPlayer, KifuPlayerAlias, KifuPlayerName, KifuRawPlayerValue
from katrain.web.kifu.catalog_player_second import _live_scope, _scope_rows


def _key(value):
    return unicodedata.normalize("NFKC", value).casefold().strip()


def _entries(decision, environment):
    if decision.get("format") != "kifu-player-independent-identity-target-decision-v1":
        raise ValueError("identity decision format differs")
    entries = decision["entries"]
    if len({entry["raw"] for entry in entries}) != len(entries):
        raise ValueError("duplicate exact raw")
    approved = [entry for entry in entries if entry["decision"] == "approved_exact_identity_subject_to_slot_guards"]
    if len({_key(entry["canonical"]) for entry in approved}) != len(approved):
        raise ValueError("duplicate approved canonical")
    if any(entry["decision"] not in {"approved_exact_identity_subject_to_slot_guards", "hold"} for entry in entries):
        raise ValueError("unknown identity decision")
    for entry in approved:
        target = entry[f"{environment}_target"]
        if target != "new" and (not isinstance(target, int) or target <= 0):
            raise ValueError("invalid approved target")
    return entries, approved


def _catalog(db, entries, environment):
    approved = [e for e in entries if e["decision"] != "hold"]
    spellings = {_key(name) for e in approved for name in
                 (e["raw"], e["canonical"], e.get("official_name"), e.get("current_canonical")) if name}
    ids = {e[f"{environment}_target"] for e in approved if e[f"{environment}_target"] != "new"}
    players = [list(row) for row in db.execute(select(KifuPlayer.id, KifuPlayer.canonical_name).order_by(KifuPlayer.id))]
    aliases = [list(row) for row in db.execute(select(KifuPlayerAlias.id, KifuPlayerAlias.player_id,
                                                     KifuPlayerAlias.alias, KifuPlayerAlias.normalized_alias)
                                            .order_by(KifuPlayerAlias.id))]
    names = [list(row) for row in db.execute(select(KifuPlayerName.id, KifuPlayerName.player_id,
                                                   KifuPlayerName.lang, KifuPlayerName.display_name,
                                                   KifuPlayerName.status, KifuPlayerName.reference_url,
                                                   KifuPlayerName.reference_kind, KifuPlayerName.decision_kind,
                                                   KifuPlayerName.evidence_id).order_by(KifuPlayerName.id))]
    for entry in approved:
        target = entry[f"{environment}_target"]
        current = entry.get("current_canonical", entry["canonical"])
        entry_spellings = {_key(name) for name in
                           (entry["raw"], entry["canonical"], entry.get("official_name"), current) if name}
        if target == "new":
            if any(_key(name) in entry_spellings for _, name in players):
                raise ValueError(f"new canonical collision: {entry['raw']}")
        elif [target, current] not in players:
            raise ValueError(f"existing target preimage differs: {entry['raw']}")
        for row in players:
            if _key(row[1]) in entry_spellings:
                if row[0] != target:
                    raise ValueError(f"canonical collision: {entry['raw']}")
        for row in aliases:
            if (_key(row[2]) in entry_spellings or _key(row[3]) in entry_spellings) and row[1] != target:
                raise ValueError(f"alias collision: {entry['raw']}")
        for row in names:
            if _key(row[3]) in entry_spellings and row[1] != target:
                raise ValueError(f"display-name collision: {entry['raw']}")
    return {"target_players": [r for r in players if r[0] in ids],
            "collision_players": [r for r in players if _key(r[1]) in spellings],
            "target_aliases": [r for r in aliases if r[1] in ids],
            "collision_aliases": [r for r in aliases if _key(r[2]) in spellings or _key(r[3]) in spellings],
            "target_names": [r for r in names if r[1] in ids],
            "collision_names": [r for r in names if _key(r[3]) in spellings]}


def _capture(db, inventory, decision, environment, review_sha256):
    entries, approved = _entries(decision, environment)
    raw_map = {e["raw"]: e["raw"] for e in entries}
    frozen = _scope_rows(inventory, raw_map)
    live = _live_scope(db, raw_map)
    if set(frozen) != set(raw_map) or set(live) != set(raw_map):
        raise ValueError("frozen/live raw scope missing")
    albums = {album.id: album for album in db.scalars(select(KifuAlbum).where(or_(
        KifuAlbum.player_black.in_(raw_map), KifuAlbum.player_white.in_(raw_map))))}
    by_raw = {e["raw"]: e for e in entries}
    known_holds = {(h["album_id"], h["side"]): h for e in entries for h in e["known_slot_holds"]}
    if len(known_holds) != sum(len(e["known_slot_holds"]) for e in entries):
        raise ValueError("duplicate known hold")
    candidate, held, protected, whole_held = [], [], [], []
    sgf = []
    for entry in entries:
        raw = entry["raw"]
        if len(frozen[raw]) != entry["slots"] or [r[:-1] for r in frozen[raw]] != [r[:-1] for r in live[raw]]:
            raise ValueError(f"frozen/live scope differs: {raw}")
        for row in live[raw]:
            album = albums[row[0]]
            sgf.append([row[0], hashlib.sha256(album.sgf_content.encode()).hexdigest(),
                        album.source_path, album.event])
            if entry["decision"] == "hold":
                whole_held.append(row)
                continue
            try:
                root = SGF.parse_sgf(album.sgf_content)
                pb, pw, dt = (root.get_property(key) for key in ("PB", "PW", "DT"))
                sgf_conflict = (pb, pw, dt) != (album.player_black, album.player_white, album.date_played)
            except Exception:
                sgf_conflict = True
            target = entry[f"{environment}_target"]
            other_side = "white" if row[1] == "black" else "black"
            opponent = row[5] if row[1] == "black" else row[4]
            opponent_fk = getattr(album, f"{other_side}_player_id")
            known = known_holds.get((row[0], row[1]))
            if known and any(known[k] != value for k, value in
                             (("raw", raw), ("date_played", row[3]), ("black", row[4]), ("white", row[5]),
                              ("event", album.event))):
                raise ValueError("known hold preimage differs")
            same_person = (opponent == raw or opponent == entry["canonical"] or
                           opponent == entry.get("current_canonical") or
                           (target != "new" and opponent_fk == target) or
                           (target != "new" and opponent in by_raw and
                            by_raw[opponent][f"{environment}_target"] == target))
            impossible = (row[3] == "1900-01-01" or not row[3] or
                          (entry.get("birth_date") and row[3][:10] < entry["birth_date"]) or
                          (entry.get("last_game_date") and row[3][:10] > entry["last_game_date"]))
            if known or same_person or impossible or sgf_conflict:
                reason = (known["reason"] if known else "same_person_opponent" if same_person else
                          "impossible_date" if impossible else "sgf_player_or_date_conflict")
                held.append([*row, reason])
            elif row[-1] is None:
                candidate.append(row)
            elif row[-1] == target:
                protected.append(row)
            else:
                raise ValueError(f"conflicting existing FK: {row[0]}/{row[1]}")
    if set(known_holds) != {(r[0], r[1]) for r in held if (r[0], r[1]) in known_holds}:
        raise ValueError("known hold scope missing")
    totals = decision.get("totals")
    if totals and (len(approved) != totals["approved_raws"] or
                   len(known_holds) != totals["known_slot_holds"] or
                   len(whole_held) != totals["whole_raw_held_slots"] or
                   len(candidate) > totals["maximum_candidate_slots_after_known_holds"]):
        raise ValueError("reviewed decision totals differ")
    catalog = _catalog(db, entries, environment)
    raw_rows = [list(row) for row in db.execute(select(KifuRawPlayerValue.id, KifuRawPlayerValue.raw_value,
                        KifuRawPlayerValue.review_status, KifuRawPlayerValue.review_metadata)
                        .where(KifuRawPlayerValue.raw_value.in_(raw_map)).order_by(KifuRawPlayerValue.id))]
    if {r[1] for r in raw_rows} != set(raw_map):
        raise ValueError("raw staging scope missing")
    for _, raw, status, metadata in raw_rows:
        if raw in {e["raw"] for e in approved}:
            target = by_raw[raw][f"{environment}_target"]
            if status != "pending" or (isinstance(metadata, dict) and
                                       metadata.get("player_id") not in (None, target)):
                raise ValueError(f"raw staging target/status conflict: {raw}")
            if metadata is not None and not isinstance(metadata, dict):
                raise ValueError(f"raw staging metadata conflict: {raw}")
    return {"format": "kifu-player-next15-exact-plan-v1", "environment": environment,
            "database": db.scalar(text("SELECT current_database()")) if db.bind.dialect.name == "postgresql" else "sqlite-test",
            "review_sha256": review_sha256, "inventory_sha256": inventory["sha256"],
            "catalog": catalog, "raw_rows": raw_rows, "live_scope": live,
            "sgf": [list(x) for x in sorted(set(tuple(x) for x in sgf))],
            "candidate_slots": candidate, "held_slots": held, "protected_slots": protected,
            "whole_raw_held_slots": whole_held,
            "counts": {"approved_raws": len(approved), "new_ids": sum(e[f"{environment}_target"] == "new" for e in approved),
                       "candidate_slots": len(candidate), "held_slots": len(held),
                       "protected_slots": len(protected), "whole_raw_held_slots": len(whole_held)}}


def capture(engine, inventory, decision, environment, review_sha256):
    with Session(engine) as db:
        if engine.dialect.name == "postgresql":
            db.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"))
        return _capture(db, inventory, decision, environment, review_sha256)


def run(engine, inventory, decision, environment, review_sha256, plan, *, apply=False,
        plan_sha256=None, approved_plan_sha256=None):
    if apply and (not plan_sha256 or approved_plan_sha256 != plan_sha256):
        raise ValueError("separate plan SHA approval required")
    if plan.get("format") != "kifu-player-next15-exact-plan-v1" or plan.get("environment") != environment:
        raise ValueError("plan environment/format differs")
    with Session(engine) as db:
        tx = db.begin()
        try:
            if engine.dialect.name == "postgresql":
                db.execute(text("LOCK TABLE kifu_albums,kifu_album_sources,kifu_sources,kifu_players,"
                                "kifu_player_aliases,kifu_player_names,kifu_raw_player_values IN SHARE ROW EXCLUSIVE MODE"))
            if _capture(db, inventory, decision, environment, review_sha256) != plan:
                raise ValueError("live preimage changed")
            targets = {}
            for entry in decision["entries"]:
                if entry["decision"] == "hold":
                    continue
                target = entry[f"{environment}_target"]
                if target == "new":
                    person = KifuPlayer(canonical_name=entry["canonical"])
                    db.add(person)
                    db.flush()
                    target = person.id
                targets[entry["raw"]] = target
            for row in plan["candidate_slots"]:
                album_id, side, raw, date, black, white, duplicate, sources, old_fk = row
                field = KifuAlbum.black_player_id if side == "black" else KifuAlbum.white_player_id
                raw_field = KifuAlbum.player_black if side == "black" else KifuAlbum.player_white
                changed = db.execute(update(KifuAlbum).where(KifuAlbum.id == album_id, raw_field == raw,
                    KifuAlbum.date_played == date, field.is_(None)).values({field: targets[raw]}))
                if changed.rowcount != 1:
                    raise ValueError("slot compare-and-swap failed")
            db.flush()
            desired = {(r[0], r[1]): targets[r[2]] for r in plan["candidate_slots"]}
            after = _live_scope(db, {e["raw"]: e["raw"] for e in decision["entries"]})
            for raw, rows in plan["live_scope"].items():
                if after[raw] != [r[:-1] + [desired.get((r[0], r[1]), r[-1])] for r in rows]:
                    raise ValueError("postwrite scope differs")
            if _catalog_after(db, decision["entries"], environment, plan["catalog"], targets) is False:
                raise ValueError("postwrite catalog differs")
            result = {"committed": apply, **plan["counts"], "created_ids": {raw: targets[raw] for raw in targets
                      if next(e for e in decision["entries"] if e["raw"] == raw)[f"{environment}_target"] == "new"}}
            tx.commit() if apply else tx.rollback()
            return result
        except BaseException:
            tx.rollback()
            raise


def _catalog_after(db, entries, environment, before, targets):
    # Recheck every old translation and alias; newly created identities have no inferred translations.
    ids = {e[f"{environment}_target"] for e in entries if e["decision"] != "hold"
           and e[f"{environment}_target"] != "new"}
    players = [list(r) for r in db.execute(select(KifuPlayer.id, KifuPlayer.canonical_name)
                                           .where(KifuPlayer.id.in_(ids)).order_by(KifuPlayer.id))]
    aliases = [list(r) for r in db.execute(select(KifuPlayerAlias.id, KifuPlayerAlias.player_id,
                                                KifuPlayerAlias.alias, KifuPlayerAlias.normalized_alias)
                                       .where(KifuPlayerAlias.player_id.in_(ids)).order_by(KifuPlayerAlias.id))]
    names = [list(r) for r in db.execute(select(KifuPlayerName.id, KifuPlayerName.player_id,
                                              KifuPlayerName.lang, KifuPlayerName.display_name,
                                              KifuPlayerName.status, KifuPlayerName.reference_url,
                                              KifuPlayerName.reference_kind, KifuPlayerName.decision_kind,
                                              KifuPlayerName.evidence_id)
                                     .where(KifuPlayerName.player_id.in_(ids)).order_by(KifuPlayerName.id))]
    if (players != before["target_players"] or aliases != before["target_aliases"]
            or names != before["target_names"]):
        return False
    return all(db.get(KifuPlayer, targets[e["raw"]]).canonical_name == e["canonical"]
               for e in entries if e["decision"] != "hold" and e[f"{environment}_target"] == "new")
