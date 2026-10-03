"""Only draft displays may be added by the direct event translation pilot."""

import gzip
import json
from collections import Counter
from pathlib import Path

import pytest
from sqlalchemy import create_engine, select

from katrain.web.core.db import Base
from katrain.web.core.models_db import KifuRawEventName, KifuRawEventValue
from katrain.web.kifu.catalog_event_direct_cn import (
    VERSION, apply_direct_cn, dry_run_direct_cn, scope_sha256, translate_event,
)


def test_exact_core_translation_and_ambiguous_exclusions():
    assert translate_event("28th Honinbo") == "第28期本因坊战"
    assert translate_event("28thHoninbo") == "第28期本因坊战"
    assert translate_event("Honinbo,28th") == "第28期本因坊战"
    assert translate_event("Oteai 1927") == "1927年日本大手合"
    assert translate_event("Oteai") == "日本大手合"
    assert translate_event("14th Old Meijin") == "第14期旧名人战"
    assert translate_event("14th Meijin") == "第14期名人战"
    assert translate_event("10th Pro Best Ten") == "第10期职业十杰战"
    assert translate_event("Castle Game") is None
    assert translate_event("JapanPromotionTournament,1927,Spring") is None
    assert translate_event("28th Honinbo Final") is None
    assert translate_event("GNUGo3.8") is None


def test_dry_run_apply_is_insert_only_idempotent_and_preserves_raw(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'pilot.db'}")
    Base.metadata.create_all(engine)
    raw = KifuRawEventValue.__table__
    name = KifuRawEventName.__table__
    with engine.begin() as conn:
        conn.execute(raw.insert(), [
            {"id": 1, "raw_value": "28th Honinbo", "category": "unclassified_pending"},
            {"id": 2, "raw_value": "10th Judan", "category": "unclassified_pending"},
            {"id": 3, "raw_value": "Castle Game", "category": "unclassified_pending"},
            {"id": 4, "raw_value": "Oteai 1927", "category": "unclassified_pending"},
        ])
        conn.execute(name.insert().values(
            raw_event_id=2, lang="cn", display_name="既有译名", status="review",
            decision_kind="manual",
        ))
    preview = dry_run_direct_cn(engine)
    assert Counter(row["action"] for row in preview) == {"create": 2, "protected": 1, "skipped": 1}
    with engine.connect() as conn:
        assert conn.scalar(select(name.c.id).where(name.c.raw_event_id == 1)) is None

    pinned = scope_sha256({"28th Honinbo", "10th Judan", "Oteai 1927"})
    first = apply_direct_cn(engine, expected_scope_sha256=pinned)
    assert Counter(row["action"] for row in first) == Counter(row["action"] for row in preview)
    second = apply_direct_cn(engine, expected_scope_sha256=pinned)
    assert Counter(row["action"] for row in second) == {"unchanged": 2, "protected": 1, "skipped": 1}
    with engine.connect() as conn:
        assert conn.execute(select(raw.c.id, raw.c.raw_value).order_by(raw.c.id)).all() == [
            (1, "28th Honinbo"), (2, "10th Judan"), (3, "Castle Game"), (4, "Oteai 1927"),
        ]
        rows = {row["raw_event_id"]: row for row in conn.execute(select(name)).mappings()}
        assert len(rows) == 3
        assert rows[1]["display_name"] == "第28期本因坊战"
        assert rows[4]["display_name"] == "1927年日本大手合"
        assert rows[1]["status"] == rows[4]["status"] == "review"
        assert rows[1]["decision_kind"] == rows[4]["decision_kind"] == "direct_translation"
        assert rows[1]["generation_rule_version"] == rows[4]["generation_rule_version"] == VERSION
        assert rows[1]["evidence_id"] is rows[4]["evidence_id"] is None
        assert rows[2]["display_name"] == "既有译名"


def test_apply_rejects_a_live_raw_scope_change_atomically(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'scope.db'}")
    Base.metadata.create_all(engine)
    with engine.begin() as conn:
        conn.execute(KifuRawEventValue.__table__.insert().values(
            raw_value="28th Honinbo", category="unclassified_pending"
        ))
    wrong_scope = scope_sha256({"28th Honinbo", "10th Judan"})
    with pytest.raises(ValueError, match="scope differs"):
        apply_direct_cn(engine, expected_scope_sha256=wrong_scope)
    with engine.connect() as conn:
        assert conn.scalar(select(KifuRawEventName.id)) is None


def test_frozen_inventory_scope_when_available():
    path = Path("/tmp/kifu-five-prod-inventory-post7.json.gz")
    if not path.exists():
        return
    with gzip.open(path, "rt") as stream:
        inventory = json.load(stream)
    rows = inventory["scopes"]["all"]["values"]["event"]
    selected = [row for row in rows if translate_event(row["value"]) is not None]
    assert len(selected) == 599
    assert sum(row["occurrences"] for row in selected) == 20_153
