"""Exact reviewed NULL-slot links, with full scope and protected-slot preimages."""

import json

from sqlalchemy import select, text, update
from sqlalchemy.orm import Session
from katrain.web.core.models_db import KifuAlbum, KifuPlayer, KifuPlayerAlias, KifuRawPlayerValue
from katrain.web.kifu.catalog_player_second import _live_scope, _scope_rows
from katrain.web.kifu.catalog_player_family import _catalog_preimage, _normalized


def _capture(db, inventory, spec, review_sha256, environment):
    if environment != spec["environment"]:
        raise ValueError("environment differs")
    mapping = spec["exact_raw_to_canonical"]
    targets = spec["targets"]
    frozen = _scope_rows(inventory, {r: r for r in mapping})
    live = _live_scope(db, {r: r for r in mapping})
    if set(frozen) != set(mapping) or set(live) != set(mapping):
        raise ValueError("raw scope missing")
    for raw in mapping:
        if [r[:-1] for r in frozen[raw]] != [r[:-1] for r in live[raw]]:
            raise ValueError("frozen scope differs")
    slots = {(r[0], r[1]): r for rows in live.values() for r in rows}
    expected = {}
    for rows in [spec["candidate_slots"], spec["protected_already_linked"], spec["held_slots"]]:
        for r in rows:
            key = tuple(r[:2])
            if key in expected:
                raise ValueError("duplicate slot")
            expected[key] = r
            actual = slots.get(key)
            if actual is None or [actual[0], actual[1], actual[2], actual[3], actual[-1]] != r[:5]:
                raise ValueError("slot preimage differs")
    if set(expected) != set(slots):
        raise ValueError("unreviewed slot in exact raw scope")
    ids = set(targets.values())
    # Capture titles and any other explicitly protected catalog rows without mutating them.
    ids.update(spec.get("protected_catalog_ids", []))
    catalog = _catalog_preimage(db, ids)
    names = dict(catalog["players"])
    for name, id_ in targets.items():
        if names.get(id_) != name:
            raise ValueError("canonical target differs")
        if (
            db.scalar(select(KifuPlayer.id).where(KifuPlayer.canonical_name == name, KifuPlayer.id != id_).limit(1))
            is not None
        ):
            raise ValueError("canonical duplicate identity conflict")
        aliases = (
            db.execute(select(KifuPlayerAlias.player_id).where(KifuPlayerAlias.normalized_alias == _normalized(name)))
            .scalars()
            .all()
        )
        if any(a != id_ for a in aliases):
            raise ValueError("target alias identity conflict")
    if len(names) != len(ids):
        raise ValueError("protected catalog ID absent")
    exact_raw_catalog = {}
    for raw, name in mapping.items():
        target = targets[name]
        canonicals = [
            list(r)
            for r in db.execute(
                select(KifuPlayer.id, KifuPlayer.canonical_name)
                .where(KifuPlayer.canonical_name == raw)
                .order_by(KifuPlayer.id)
            ).all()
        ]
        aliases = [
            list(r)
            for r in db.execute(
                select(
                    KifuPlayerAlias.id,
                    KifuPlayerAlias.player_id,
                    KifuPlayerAlias.alias,
                    KifuPlayerAlias.normalized_alias,
                )
                .where(KifuPlayerAlias.normalized_alias == _normalized(raw))
                .order_by(KifuPlayerAlias.id)
            ).all()
        ]
        if any(r[0] != target for r in canonicals):
            raise ValueError(f"exact raw canonical identity conflict: {raw}")
        if any(r[1] != target for r in aliases):
            raise ValueError(f"exact raw alias identity conflict: {raw}")
        exact_raw_catalog[raw] = {"target_id": target, "canonicals": canonicals, "aliases": aliases}
    opponent_rows = {
        r.id: r
        for r in db.execute(
            select(KifuAlbum.id, KifuAlbum.black_player_id, KifuAlbum.white_player_id).where(
                KifuAlbum.id.in_({r[0] for r in spec["candidate_slots"]})
            )
        ).all()
    }
    for r in spec["candidate_slots"]:
        target = targets[mapping[r[2]]]
        if r[-1] != target or r[4] is not None:
            raise ValueError("invalid candidate target")
        actual = slots[tuple(r[:2])]
        opponent = actual[5] if r[1] == "black" else actual[4]
        album = opponent_rows[r[0]]
        opponent_fk = album.white_player_id if r[1] == "black" else album.black_player_id
        if opponent_fk == target or (opponent in mapping and targets[mapping[opponent]] == target):
            raise ValueError("same-person opponent")
    for r in spec["protected_already_linked"]:
        if r[4] != targets[mapping[r[2]]]:
            raise ValueError("protected FK identity conflict")
    raw_rows = [
        [r.id, r.raw_value, r.review_status, r.review_metadata]
        for r in db.execute(
            select(KifuRawPlayerValue).where(KifuRawPlayerValue.raw_value.in_(mapping)).order_by(KifuRawPlayerValue.id)
        ).scalars()
    ]
    if {r[1] for r in raw_rows} != set(mapping):
        raise ValueError("raw staging missing")
    for _, raw, status, metadata in raw_rows:
        if status not in ("pending", "approved"):
            raise ValueError("raw status conflict")
        if metadata is not None and (
            not isinstance(metadata, dict) or metadata.get("player_id") != targets[mapping[raw]]
        ):
            raise ValueError("raw metadata identity conflict")
        if status == "approved" and any(h[2] == raw for h in spec["held_slots"]):
            raise ValueError("held raw already approved")
    return {
        "format": "kifu-player-exact-slot-plan-v1",
        "environment": environment,
        "review_sha256": review_sha256,
        "catalog": catalog,
        "exact_raw_catalog": exact_raw_catalog,
        "live_scope": live,
        "raw_rows": raw_rows,
        "candidate_slots": spec["candidate_slots"],
        "protected_slots": spec["protected_already_linked"],
        "held_slots": spec["held_slots"],
        "counts": {
            "new_fk_slots": len(spec["candidate_slots"]),
            "protected_slots": len(spec["protected_already_linked"]),
            "held_slots": len(spec["held_slots"]),
            "raw_values": len(mapping),
        },
    }


def capture_exact_plan(inventory, spec, review_sha256, environment, engine):
    with Session(engine) as db:
        return _capture(db, inventory, spec, review_sha256, environment)


def run_exact_plan(
    inventory,
    spec,
    review_sha256,
    environment,
    plan,
    engine,
    *,
    apply=False,
    plan_sha256=None,
    approved_plan_sha256=None,
):
    if apply and (not plan_sha256 or approved_plan_sha256 != plan_sha256):
        raise ValueError("separate exact SHA approval required")
    with Session(engine) as db:
        tx = db.begin()
        try:
            if engine.dialect.name == "postgresql":
                db.execute(
                    text(
                        "LOCK TABLE kifu_albums, kifu_album_sources, kifu_sources, kifu_players, kifu_player_aliases, kifu_player_names, kifu_name_research_evidence, kifu_raw_player_values IN SHARE ROW EXCLUSIVE MODE"
                    )
                )
            if _capture(db, inventory, spec, review_sha256, environment) != plan:
                raise ValueError("live preimage changed")
            if engine.dialect.name == "postgresql":
                db.execute(
                    text(
                        "CREATE TEMP TABLE kifu_player_exact_slots (album_id integer, side text, raw text, date text, target integer, PRIMARY KEY(album_id,side)) ON COMMIT DROP"
                    )
                )
                payload = [
                    dict(album_id=r[0], side=r[1], raw=r[2], date=r[3], target=r[5]) for r in plan["candidate_slots"]
                ]
                db.execute(
                    text(
                        "INSERT INTO kifu_player_exact_slots SELECT * FROM jsonb_to_recordset(CAST(:payload AS jsonb)) AS m(album_id integer,side text,raw text,date text,target integer)"
                    ),
                    {"payload": json.dumps(payload, ensure_ascii=False)},
                )
                changed = 0
                for side in ("black", "white"):
                    changed += db.execute(
                        text(
                            f"UPDATE kifu_albums a SET {side}_player_id=m.target FROM kifu_player_exact_slots m WHERE m.side=:side AND a.id=m.album_id AND a.player_{side}=m.raw AND a.date_played IS NOT DISTINCT FROM m.date AND a.{side}_player_id IS NULL"
                        ),
                        {"side": side},
                    ).rowcount
                if changed != len(plan["candidate_slots"]):
                    raise ValueError("slot compare-and-swap failed")
            else:
                for album_id, side, raw, date, old, target in plan["candidate_slots"]:
                    field = KifuAlbum.black_player_id if side == "black" else KifuAlbum.white_player_id
                    raw_field = KifuAlbum.player_black if side == "black" else KifuAlbum.player_white
                    changed = db.execute(
                        update(KifuAlbum)
                        .where(
                            KifuAlbum.id == album_id, raw_field == raw, KifuAlbum.date_played == date, field.is_(None)
                        )
                        .values({field: target})
                    )
                    if changed.rowcount != 1:
                        raise ValueError("slot compare-and-swap failed")
            for id_, raw, status, metadata in plan["raw_rows"]:
                holds = sorted({h[0] for h in plan["held_slots"] if h[2] == raw})
                value = dict(metadata or {})
                value.update(
                    kind="reviewed_exact_slot_person_link",
                    player_id=spec["targets"][spec["exact_raw_to_canonical"][raw]],
                    review_sha256=review_sha256,
                    held_album_ids=holds,
                )
                staged = db.get(KifuRawPlayerValue, id_)
                staged.review_metadata = value
                staged.review_status = "pending" if holds else "approved"
            db.flush()
            # Actual SQL changes are checked before rollback/commit, including held/protected FKs and names.
            after = _live_scope(db, {r: r for r in spec["exact_raw_to_canonical"]})
            desired = {tuple(r[:2]): r[-1] for r in plan["candidate_slots"]}
            for raw, rows in plan["live_scope"].items():
                expected = [r[:-1] + [desired.get(tuple(r[:2]), r[-1])] for r in rows]
                if after[raw] != expected:
                    raise ValueError("postwrite scope mismatch")
            if _catalog_preimage(db, {r[0] for r in plan["catalog"]["players"]}) != plan["catalog"]:
                raise ValueError("catalog changed")
            result = dict(plan["counts"], applied=apply)
            tx.commit() if apply else tx.rollback()
            return result
        except Exception:
            tx.rollback()
            raise
