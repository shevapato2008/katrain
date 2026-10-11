import copy
import gzip
import hashlib
import json
from pathlib import Path

import pytest

from scripts.apply_kifu_japanese_major_exact import (
    MIXED11_PLAN_SHA,
    REBASED_PLAYER_FK_SHA,
    checked_decision,
    digest,
)


DECISION = Path(__file__).resolve().parents[2] / "docs/resource/kifu-event-japanese-major-next-independent-decision-astra-2026-10-04.json"


def decision():
    return json.loads(DECISION.read_text())


def test_frozen_scope_and_environment_specific_player_fk():
    scope = decision()
    approved, held, prod = checked_decision(scope, "PROD")
    _, _, test = checked_decision(scope, "TEST")
    assert (len(approved), len(held)) == (1839, 1360)
    assert all(row[9] is None for row in approved)
    assert {row[0] for row in approved}.isdisjoint({row[0] for row in held})
    assert prod["player_fk_preimages_sha256"] != test["player_fk_preimages_sha256"]
    assert digest(prod["player_fk_preimages"]) == prod["player_fk_preimages_sha256"]
    assert digest(test["player_fk_preimages"]) == test["player_fk_preimages_sha256"]


def test_tampered_assignment_or_hold_rejected():
    scope = decision()
    scope["approved_albums"][0][8] = 29
    with pytest.raises(ValueError, match="decision differs"):
        checked_decision(scope, "PROD")
    scope = decision()
    scope["held_rows"].pop()
    with pytest.raises(ValueError, match="decision differs"):
        checked_decision(scope, "TEST")


def test_environment_binding_rejected_even_with_rehashed_decision():
    scope = copy.deepcopy(decision())
    scope["environment_catalogs"]["TEST"]["player_fk_preimages"] = scope["environment_catalogs"]["PROD"]["player_fk_preimages"]
    scope["decision_sha256"] = digest({k: v for k, v in scope.items() if k != "decision_sha256"})
    with pytest.raises(ValueError, match="independent decision differs"):
        checked_decision(scope, "TEST")


@pytest.mark.parametrize("environment", ["TEST", "PROD"])
def test_rebased_fk_image_is_exactly_the_reviewed_mixed11_delta(environment):
    scope = decision()
    original = scope["environment_catalogs"][environment]["player_fk_preimages"]
    path = DECISION.parent / f"kifu-player-highfreq-mixed11-revised-{environment}-plan-2026-10-04.json.gz"
    raw = path.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == MIXED11_PLAN_SHA[environment]
    mixed = json.loads(gzip.decompress(raw))
    ids = {row[0] for row in original}
    changed = [row for row in mixed["candidate_slots"] if row[0] in ids]
    assert len(changed) == 90
    assert len({row[0] for row in changed}) == 89
    expected = {row[0]: row.copy() for row in original}
    for album_id, side, raw_name, date, old_fk, new_fk in changed:
        row = expected[album_id]
        assert old_fk is None
        assert row[1 if side == "black" else 2] is None
        approved = next((r for r in scope["approved_albums"] if r[0] == album_id), None)
        held = next((r for r in scope["held_rows"] if r[0] == album_id), None)
        album = approved or held
        assert album is not None and album[2] == date
        guard = next(r for r in scope["sgf_guards"] if r[0] == album_id)
        assert guard[1 if side == "black" else 2] == raw_name
        row[1 if side == "black" else 2] = new_fk
    assert digest([expected[row[0]] for row in original]) == REBASED_PLAYER_FK_SHA[environment]
