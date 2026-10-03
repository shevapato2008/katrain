"""Seed four source-checked player identities without linking any games."""

from sqlalchemy import select
from sqlalchemy.engine import Engine

from katrain.web.core.models_db import KifuPlayer, KifuPlayerAlias, KifuRawPlayerValue
from katrain.web.kifu.identity import normalize_alias


# These sources establish the person and spelling, not a reviewed display name.
PLAYER_SOURCES = {
    "常昊": "https://www.weiqi.org.cn/player/professional",
    "加藤正夫": "https://www.nihonkiin.or.jp/player/htm/ki000002.html",
    "大竹英雄": "https://www.nihonkiin.or.jp/player/htm/ki000008.html",
    "藤泽秀行": "https://www.nihonkiin.or.jp/player/htm/ki000005.htm",
}


def _plan(conn) -> list[dict]:
    canonical_rows = conn.execute(select(KifuPlayer.id, KifuPlayer.canonical_name)).all()
    alias_rows = conn.execute(
        select(KifuPlayerAlias.player_id, KifuPlayerAlias.alias, KifuPlayerAlias.normalized_alias)
    ).all()
    raw_anchors = set(
        conn.scalars(select(KifuRawPlayerValue.raw_value).where(KifuRawPlayerValue.raw_value.in_(PLAYER_SOURCES)))
    )

    report = []
    for name, source_url in PLAYER_SOURCES.items():
        if name not in raw_anchors:
            raise ValueError(f"missing exact raw Chinese player anchor: {name!r}")
        target = normalize_alias(name)
        canonical_matches = [
            (player_id, value) for player_id, value in canonical_rows if normalize_alias(value) == target
        ]
        alias_matches = [
            (player_id, value)
            for player_id, value, normalized in alias_rows
            if normalized == target or normalize_alias(value) == target
        ]
        if alias_matches or len(canonical_matches) > 1 or (canonical_matches and canonical_matches[0][1] != name):
            raise ValueError(f"normalized player canonical/alias collision: {name!r}")
        report.append(
            {
                "canonical_name": name,
                "source_url": source_url,
                "action": "already_exists" if canonical_matches else "create",
                "id": canonical_matches[0][0] if canonical_matches else None,
            }
        )
    return report


def dry_run_player_seed(engine: Engine) -> list[dict]:
    """Validate the full batch and report proposed inserts without writing."""
    with engine.connect() as conn:
        return _plan(conn)


def apply_player_seed(engine: Engine) -> list[dict]:
    """Insert missing identities atomically and safely on repeated runs."""
    with engine.begin() as conn:
        if conn.dialect.name == "postgresql":
            conn.exec_driver_sql(
                "LOCK TABLE kifu_players, kifu_player_aliases, kifu_raw_player_values IN SHARE ROW EXCLUSIVE MODE"
            )
        report = _plan(conn)
        for row in report:
            if row["action"] == "create":
                row["id"] = conn.execute(
                    KifuPlayer.__table__.insert().values(canonical_name=row["canonical_name"]).returning(KifuPlayer.id)
                ).scalar_one()
        return report
