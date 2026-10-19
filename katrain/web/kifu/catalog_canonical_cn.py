"""Narrow, repeatable canonical-name correction for six reviewed catalog rows.

The decisions are pinned to stable IDs and exact English preimages. The Chinese
spellings come from docs/resource/kifu-name-seed.json; verified localized names
and album references are deliberately outside this helper's write set.
"""

from dataclasses import dataclass

from sqlalchemy import select, update
from sqlalchemy.engine import Engine

from katrain.web.core.models_db import KifuEvent, KifuEventAlias, KifuPlayer, KifuPlayerAlias
from katrain.web.kifu.identity import normalize_alias


@dataclass(frozen=True)
class CanonicalDecision:
    kind: str
    id: int | None
    old: str
    new: str


DECISIONS = (
    CanonicalDecision("player", 1, "Go Seigen", "吴清源"),
    CanonicalDecision("player", 2, "Honinbo Dosaku", "本因坊道策"),
    CanonicalDecision("player", 3, "Honinbo Jowa", "本因坊丈和"),
    CanonicalDecision("player", 4, "Honinbo Shusaku", "本因坊秀策"),
    CanonicalDecision("player", 5, "Kitani Minoru", "木谷实"),
    # TEST and PROD imported Oteai with different IDs; resolve its unique preimage.
    CanonicalDecision("event", None, "Oteai", "大手合"),
)


def _plan(conn):
    snapshots = {}
    for kind, model, alias_model, owner_column in (
        ("player", KifuPlayer, KifuPlayerAlias, KifuPlayerAlias.player_id),
        ("event", KifuEvent, KifuEventAlias, KifuEventAlias.event_id),
    ):
        names = conn.execute(select(model.id, model.canonical_name)).all()
        aliases = conn.execute(select(owner_column, alias_model.alias, alias_model.normalized_alias)).all()
        snapshots[kind] = (model, alias_model, owner_column, names, aliases)

    report = []
    for decision in DECISIONS:
        _, _, _, names, aliases = snapshots[decision.kind]
        if decision.id is None:
            matches = [(entity_id, name) for entity_id, name in names if name in (decision.old, decision.new)]
            if len(matches) != 1:
                raise ValueError(f"{decision.kind} canonical preimage is not unique: {decision.old!r}")
            decision_id, current = matches[0]
        else:
            decision_id = decision.id
            current = dict(names).get(decision_id)
        if current not in (decision.old, decision.new):
            raise ValueError(
                f"{decision.kind} {decision_id} canonical preimage differs: expected "
                f"{decision.old!r} or already applied {decision.new!r}, got {current!r}"
            )

        target = normalize_alias(decision.new)
        canonical_conflict = any(
            other_id != decision_id and normalize_alias(name) == target for other_id, name in names
        )
        alias_conflict = any(
            other_id != decision_id and (normalized == target or normalize_alias(alias) == target)
            for other_id, alias, normalized in aliases
        )
        if canonical_conflict or alias_conflict:
            raise ValueError(f"{decision.kind} {decision_id} Chinese canonical collision: {decision.new!r}")

        old_key = normalize_alias(decision.old)
        english_collision = any(
            other_id != decision_id and normalize_alias(name) == old_key for other_id, name in names
        ) or any(
            other_id != decision_id and (normalized == old_key or normalize_alias(alias) == old_key)
            for other_id, alias, normalized in aliases
        )
        own_alias = any(
            owner_id == decision_id and (normalized == old_key or normalize_alias(alias) == old_key)
            for owner_id, alias, normalized in aliases
        )
        if english_collision:
            english_alias = "collision_skipped"
        elif own_alias:
            english_alias = "existing"
        elif current == decision.new:
            english_alias = "missing"
        else:
            english_alias = "create"
        report.append({
            "kind": decision.kind,
            "id": decision_id,
            "old": decision.old,
            "new": decision.new,
            "action": "already_applied" if current == decision.new else "rename",
            "english_alias": english_alias,
        })
    return report, snapshots


def dry_run_canonical_cn(engine: Engine) -> list[dict]:
    """Validate all six pinned rows and describe the writes without changing data."""
    with engine.connect() as conn:
        report, _ = _plan(conn)
        return report


def apply_canonical_cn(engine: Engine) -> list[dict]:
    """Apply the validated correction atomically; safe to repeat after success."""
    with engine.begin() as conn:
        report, snapshots = _plan(conn)
        for row in report:
            model, alias_model, owner_column, _, _ = snapshots[row["kind"]]
            if row["action"] == "rename":
                result = conn.execute(
                    update(model).where(model.id == row["id"], model.canonical_name == row["old"])
                    .values(canonical_name=row["new"])
                )
                if result.rowcount != 1:
                    raise ValueError(f"{row['kind']} {row['id']} canonical preimage changed during apply")
            if row["english_alias"] == "create":
                conn.execute(alias_model.__table__.insert().values(
                    **{owner_column.key: row["id"]},
                    alias=row["old"],
                    normalized_alias=normalize_alias(row["old"]),
                ))
        return report
