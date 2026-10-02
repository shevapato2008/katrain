"""A reviewed raw spelling may apply to only the signed game slots."""

from copy import deepcopy
from types import SimpleNamespace

import pytest

from katrain.web.kifu.name_candidates import canonical_sha256
from katrain.web.kifu.name_evidence import EvidenceError, validate_transliteration_anchor
from katrain.web.kifu.name_raw_player_scope import (
    prepare_raw_player_scope, raw_player_scope_slot, validate_raw_player_scope,
)
from tests.web_ui.test_kifu_name_transliteration import two_publisher_anchor
from tests.web_ui.test_kifu_name_api import _db, _evidence, _list
from katrain.web.core.models_db import KifuAlbum, KifuNameBatch, KifuPlayer, KifuRawPlayerName, KifuRawPlayerValue
from katrain.web.kifu import identity
from katrain.web.kifu.name_coverage import coverage_report
from katrain.web.kifu.name_inventory import build_inventory


def _scope():
    context = {"player_black": "李元赫", "player_white": "Other", "event": "Cup",
               "round_name": None, "black_rank": None, "white_rank": None,
               "date_played": "2024-01-01", "black_player_id": None, "white_player_id": None,
               "event_id": None, "duplicate_of_id": None}
    content = {"inventory_sha256": "a" * 64, "raw_value": "李元赫",
               "applicability_basis": "Reviewed every listed slot for a shared written and spoken rendering",
               "slots": [{"album_id": 1, "slot": "black", "context": context}]}
    return {"content": content, "approval": {
        "status": "approved", "content_sha256": canonical_sha256(content),
        "producer_id": "producer", "producer_model": "gpt-6-luna",
        "produced_at": "2026-10-03T10:00:00Z", "reviewer_id": "reviewer",
        "reviewer_model": "gpt-6-sol", "reviewed_at": "2026-10-03T11:00:00Z",
        "conclusion": "approved_raw_display_scope"}}


def test_signed_raw_scope_excludes_new_same_string_linked_and_changed_context():
    scope = _scope()
    assert validate_raw_player_scope(scope, "a" * 64, "李元赫", {(1, "black")}, {1: scope["content"]["slots"][0]["context"]})
    album = SimpleNamespace(id=1, **scope["content"]["slots"][0]["context"])
    assert raw_player_scope_slot(scope, album, "black", "李元赫")
    assert not raw_player_scope_slot(scope, SimpleNamespace(**{**vars(album), "id": 2}), "black", "李元赫")
    assert not raw_player_scope_slot(scope, SimpleNamespace(**{**vars(album), "black_player_id": 12}), "black", "李元赫")
    assert not raw_player_scope_slot(scope, SimpleNamespace(**{**vars(album), "event": "Other Cup"}), "black", "李元赫")
    assert not raw_player_scope_slot(scope, album, "white", "李元赫")


def test_prepared_scope_checks_signature_once_for_all_members(monkeypatch):
    from katrain.web.kifu import name_raw_player_scope

    scope = _scope()
    second = deepcopy(scope["content"]["slots"][0])
    second["album_id"] = 2
    scope["content"]["slots"].append(second)
    scope["approval"]["content_sha256"] = canonical_sha256(scope["content"])
    original = name_raw_player_scope.validate_transliteration_review
    calls = []

    def checked(*args):
        calls.append(1)
        return original(*args)

    monkeypatch.setattr(name_raw_player_scope, "validate_transliteration_review", checked)
    prepared = prepare_raw_player_scope(scope)
    for album_id in (1, 2):
        album = SimpleNamespace(id=album_id, **second["context"])
        assert raw_player_scope_slot(prepared, album, "black", "李元赫")
    assert len(calls) == 1


def test_raw_v3_anchor_binds_exact_spelling_scope_and_reading_reason():
    anchor = two_publisher_anchor()
    content = anchor["content"]
    content.update(anchor_format=3, owner={"kind": "raw_player", "ref": "li-yuanhe"},
                   raw_value="李元赫", raw_display_scope_sha256="a" * 64,
                   original_language_basis="Reviewed Simplified Chinese spelling across signed slots",
                   reading_applicability_basis="Reviewed published reading for signed slots",
                   spelling_exceptions_basis="No known conflicting readings in signed slots")
    anchor["approval"]["content_sha256"] = canonical_sha256(content)
    validate_transliteration_anchor(anchor)
    for field in ("raw_value", "raw_display_scope_sha256", "reading_applicability_basis"):
        bad = deepcopy(anchor)
        bad["content"].pop(field)
        bad["approval"]["content_sha256"] = canonical_sha256(bad["content"])
        with pytest.raises(EvidenceError):
            validate_transliteration_anchor(bad)


def test_scoped_raw_display_search_and_coverage_agree_on_one_unlinked_slot(monkeypatch):
    monkeypatch.setenv("KIFU_STRICT_NAMES", "1")
    engine, db = _db()
    try:
        raw = KifuRawPlayerValue(raw_value="李元赫", category="readable_unlinked", review_status="approved")
        player = KifuPlayer(canonical_name="Someone else")
        db.add_all([raw, player])
        db.flush()
        albums = [KifuAlbum(player_black="李元赫", player_white="Other", event="Cup",
                            sgf_content="(;B[aa])", source_path=f"scope-{index}.sgf") for index in range(3)]
        albums[1].black_player_id = player.id
        db.add_all(albums)
        db.flush()
        scope = _scope()
        scope["content"]["slots"][0]["album_id"] = albums[0].id
        scope["content"]["slots"][0]["context"] = {
            field: getattr(albums[0], field) for field in (
                "duplicate_of_id", "player_black", "player_white", "event", "round_name",
                "black_rank", "white_rank", "date_played", "black_player_id", "white_player_id", "event_id")}
        scope["approval"]["content_sha256"] = canonical_sha256(scope["content"])
        scope_hash = canonical_sha256(scope)
        candidate = {"owner": {"kind": "raw_player", "id": raw.id}, "lang": "ru",
                     "raw_value": "李元赫", "display_name": "Li Yuanhe", "decision_kind": "conventional",
                     "raw_display_scope_sha256": scope_hash}
        research = {"raw_display_scope_sha256": scope_hash}
        bundle = {"inventory_sha256": "a" * 64, "owners": [{"owner": candidate["owner"],
                    "raw_display_scope": scope}], "candidates": [candidate]}
        batch = KifuNameBatch(bundle_sha256=canonical_sha256(bundle), inventory_sha256="a" * 64,
                              source_registry_id=_evidence(db, "raw_player", raw.id, "cn", "临时").source_registry_id,
                              reviewed_artifact={"bundle": bundle}, status="applied")
        db.add(batch)
        db.flush()
        evidence = _evidence(db, "raw_player", raw.id, "ru", "Li Yuanhe")
        evidence.research_payload = {"candidate": candidate, "research": research,
                                     "raw_display_scope": {"batch_id": batch.id, "scope_sha256": scope_hash}}
        db.add(KifuRawPlayerName(raw_player_id=raw.id, lang="ru", display_name="Li Yuanhe",
                                 status="verified", decision_kind="conventional",
                                 generation_rule_version="test-v1", revision=1, evidence_id=evidence.id))
        db.commit()

        displayed = {item.id: item.display_player_black for item in _list(db, lang="ru").items}
        assert displayed[albums[0].id] == "Li Yuanhe"
        assert all(displayed[album.id] == "Имя игрока не проверено" for album in albums[1:])
        assert [item.id for item in _list(db, "Li Yuanhe", "ru").items] == [albums[0].id]
        approvals = identity.strict_slot_approvals(db, albums, "ru")
        assert approvals[albums[0].id][0] is not None
        assert all(approvals[album.id][0] is None for album in albums[1:])
        report = coverage_report(engine, build_inventory(engine), languages=("ru",))
        assert report["languages"]["ru"]["approved"] == 1
        search_clause = identity.strict_raw_player_search_clause(db, {"李元赫"}, "Li Yuanhe")
        db.query(KifuAlbum).filter(KifuAlbum.id == albums[0].id).update({KifuAlbum.event: "Changed Cup"})
        assert db.query(KifuAlbum.id).filter(search_clause).all() == []
        db.commit()
        assert _list(db, "Li Yuanhe", "ru").total == 0
    finally:
        db.close()
        engine.dispose()
