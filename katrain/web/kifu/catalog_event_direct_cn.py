"""Draft Chinese displays for a finite set of raw English event names.

This creates review text only. Raw EV values, event identities, and album links
are never changed.
"""

import re
import hashlib
import json

from sqlalchemy import select, text
from sqlalchemy.engine import Engine

from katrain.web.core.models_db import KifuRawEventName, KifuRawEventValue
from katrain.web.kifu.name_structure import structure_event


VERSION = "event-direct-cn-v1"
CORE_CN = {
    "Oteai": "日本大手合",
    "Honinbo": "本因坊战",
    "Judan": "十段战",
    "Oza": "王座战",
    "Old Meijin": "旧名人战",
    "Pro Best Ten": "职业十杰战",
    "Nihon Ki-in Championship": "日本棋院选手权战",
    "Tengen": "天元战",
    "Meijin": "名人战",
    "Kisei": "棋圣战",
    "Gosei": "碁圣战",
}
GRAMMARS = frozenset({
    "english_ordinal_edition", "english_ordinal_suffix", "english_ordinal_joined",
    "oteai_year", "unparsed",
})
_ORDINAL = re.compile(r"([1-9][0-9]{0,2})(?:st|nd|rd|th)\Z", re.IGNORECASE)


def scope_sha256(raw_values: set[str]) -> str:
    """Bind an apply to the exact selected raw strings, regardless of DB IDs."""
    payload = json.dumps(sorted(raw_values, key=lambda value: value.encode("utf-8")),
                         ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def translate_event(raw: str) -> str | None:
    """Translate only exact supported cores with lossless, understood parts."""
    if not isinstance(raw, str):
        return None
    item = structure_event(raw)
    core = item["core"]
    if core not in CORE_CN or item["grammar"] not in GRAMMARS or item["exceptions"]:
        return None
    if "".join(part["text"] for part in item["parts"]) != raw:
        return None
    if item["grammar"] == "unparsed" and raw != core:
        return None
    parts = item["parts"]
    if len([part for part in parts if part["kind"] == "core"]) != 1:
        return None
    if item["grammar"] == "oteai_year" and core != "Oteai":
        return None
    if item["grammar"].startswith("english_ordinal") and (
        len(parts) != 2 or [part["kind"] for part in parts].count("edition") != 1
    ):
        return None
    result = []
    for part in parts:
        kind, value = part["kind"], part["value"]
        if kind == "core":
            result.append(CORE_CN[core])
        elif kind == "edition":
            match = _ORDINAL.fullmatch(value)
            if not match:
                return None
            result.append(f"第{int(match.group(1))}期")
        elif kind == "year" and re.fullmatch(r"[12][0-9]{3}", value):
            result.append(f"{value}年")
        elif kind == "season" and value in {"Spring", "Fall"}:
            result.append({"Spring": "春季", "Fall": "秋季"}[value])
        elif kind == "round" and re.fullmatch(r"[1-9][0-9]{0,2}轮", value):
            result.append(f"第{value}")
        else:
            return None
    # Source suffixes become natural Chinese prefixes.
    if item["grammar"] in {"english_ordinal_suffix", "oteai_year"}:
        result = [result[1], result[0]]
    return "".join(result)


def _plan(conn, *, lock: bool, expected_scope_sha256: str | None = None) -> list[dict]:
    raw_table = KifuRawEventValue.__table__
    name_table = KifuRawEventName.__table__
    raw_rows = conn.execute(select(raw_table.c.id, raw_table.c.raw_value).order_by(raw_table.c.id)).all()
    translated = {raw_id: value for raw_id, raw in raw_rows if (value := translate_event(raw)) is not None}
    selected_raw_values = {raw for raw_id, raw in raw_rows if raw_id in translated}
    if expected_scope_sha256 is not None and scope_sha256(selected_raw_values) != expected_scope_sha256:
        raise ValueError("direct event translation scope differs from the pinned raw values")
    if lock and translated:
        locked = conn.execute(select(raw_table.c.id, raw_table.c.raw_value)
                              .where(raw_table.c.id.in_(translated)).with_for_update()).all()
        if len(locked) != len(translated) or any(translate_event(raw) != translated[raw_id] for raw_id, raw in locked):
            raise ValueError("raw event changed during direct translation staging")
    name_query = select(name_table).where(name_table.c.lang == "cn", name_table.c.raw_event_id.in_(translated))
    if lock:
        name_query = name_query.with_for_update()
    existing = {row["raw_event_id"]: row for row in conn.execute(name_query).mappings()}
    report = []
    for raw_id, raw in raw_rows:
        display_name = translated.get(raw_id)
        if display_name is None:
            report.append({"raw_event_id": raw_id, "raw_value": raw, "action": "skipped"})
            continue
        prior = existing.get(raw_id)
        if prior is None:
            action = "create"
        elif (prior["display_name"] == display_name and prior["status"] == "review"
              and prior["decision_kind"] == "direct_translation"
              and prior["generation_rule_version"] == VERSION and prior["evidence_id"] is None):
            action = "unchanged"
        else:
            action = "protected"
        report.append({"raw_event_id": raw_id, "raw_value": raw, "display_name": display_name, "action": action})
    return report


def dry_run_direct_cn(engine: Engine) -> list[dict]:
    """Preview inserts and skipped/protected rows without writing."""
    with engine.connect() as conn:
        return _plan(conn, lock=False)


def apply_direct_cn(engine: Engine, *, expected_scope_sha256: str) -> list[dict]:
    """Insert missing draft names atomically; existing names are never overwritten."""
    with engine.begin() as conn:
        if conn.dialect.name == "postgresql":
            conn.execute(text("SELECT pg_advisory_xact_lock(618541673)"))
            conn.execute(text("LOCK TABLE kifu_raw_event_values IN SHARE MODE"))
            conn.execute(text("LOCK TABLE kifu_raw_event_names IN SHARE ROW EXCLUSIVE MODE"))
        report = _plan(conn, lock=True, expected_scope_sha256=expected_scope_sha256)
        for row in report:
            if row["action"] == "create":
                conn.execute(KifuRawEventName.__table__.insert().values(
                    raw_event_id=row["raw_event_id"], lang="cn", display_name=row["display_name"],
                    status="review", decision_kind="direct_translation",
                    generation_rule_version=VERSION, evidence_id=None,
                ))
        return report
