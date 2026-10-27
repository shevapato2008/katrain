"""Conservative player candidates must keep the full compatible search fallback."""

from datetime import datetime, timezone

import pytest
from sqlalchemy import event

from katrain.web.core.models_db import (
    KifuAlbum,
    KifuAlbumEventSelection,
    KifuEvent,
    KifuEventName,
    KifuNameResearchEvidence,
    KifuPlayer,
    KifuPlayerName,
    KifuPlayerAlias,
    KifuEventAlias,
    KifuRawEventName,
    KifuRawEventValue,
    KifuRawPlayerName,
    KifuRawPlayerValue,
)
from katrain.web.kifu import library_search
from tests.web_ui.test_kifu_name_api import _db, _evidence


@pytest.fixture
def db():
    engine, session = _db()
    yield session
    session.close()
    engine.dispose()


def _name(db, kind, owner, model, display="王星昊", lang="cn", approved=True, decision="conventional"):
    evidence = _evidence(db, kind, owner.id, lang, display, approved=approved, decision=decision)
    row = model(
        **{f"{kind}_id": owner.id},
        lang=lang,
        display_name=display,
        status="verified",
        decision_kind=decision,
        generation_rule_version="test-v1",
        revision=1,
        evidence_id=evidence.id,
    )
    db.add(row)
    db.commit()
    return row


def _player(db):
    player = KifuPlayer(canonical_name="Wang Xinghao")
    db.add(player)
    db.flush()
    return player


def test_exact_player_candidate_qualifies_one_owner_across_languages_without_unrelated_json(db):
    player = _player(db)
    for lang in ("cn", "tw", "jp"):
        _name(db, "player", player, KifuPlayerName, lang=lang)
    statements = []
    event.listen(db.bind, "before_cursor_execute", lambda *args: statements.append(args[2]))
    assert library_search.unique_exact_player_id(db, "王星昊", strict=True) == player.id
    candidate_sql = next(sql for sql in statements if "UNION ALL" in sql.upper())
    assert "research_payload" not in candidate_sql
    assert "bundle" not in candidate_sql
    assert not any("research_payload" in sql and "kifu_raw_event_names" in sql for sql in statements)


@pytest.mark.parametrize("kind", ["player", "event", "raw_player", "raw_event"])
def test_exact_player_candidate_falls_back_on_other_domain_or_owner(db, kind):
    player = _player(db)
    _name(db, "player", player, KifuPlayerName)
    model, name_model = {
        "player": (KifuPlayer, KifuPlayerName),
        "event": (KifuEvent, KifuEventName),
        "raw_player": (KifuRawPlayerValue, KifuRawPlayerName),
        "raw_event": (KifuRawEventValue, KifuRawEventName),
    }[kind]
    owner = model(
        **(
            {"canonical_name": "Other"}
            if kind in {"player", "event"}
            else {"raw_value": "Other", "category": "readable", "review_status": "approved"}
        )
    )
    db.add(owner)
    db.flush()
    _name(db, kind, owner, name_model)
    assert library_search.unique_exact_player_id(db, "王星昊", strict=True) is None


def test_exact_player_candidate_rejects_pending_or_changed_evidence(db):
    player = _player(db)
    row = _name(db, "player", player, KifuPlayerName, approved=False)
    assert library_search.unique_exact_player_id(db, "王星昊", strict=True) is None
    assert not library_search.public_player_id(db, player.id)

    evidence = db.get(KifuNameResearchEvidence, row.evidence_id)
    evidence.review_status = "approved"
    evidence.reviewer_id = "reviewer"
    evidence.reviewer_model = "gpt-6-sol"
    evidence.reviewed_at = datetime.now(timezone.utc)
    db.commit()
    assert library_search.public_player_id(db, player.id)
    row.revision += 1
    db.commit()
    assert library_search.unique_exact_player_id(db, "王星昊", strict=True) is None
    assert not library_search.public_player_id(db, player.id)


@pytest.mark.parametrize("decision", ["hidden", "error", "placeholder"])
def test_explicit_player_id_does_not_expose_nonpublic_approved_identity(db, decision):
    player = _player(db)
    _name(db, "player", player, KifuPlayerName, decision=decision)
    assert not library_search.public_player_id(db, player.id)


def test_explicit_player_id_requires_an_existing_identity_even_with_orphaned_names(db):
    player = _player(db)
    _name(db, "player", player, KifuPlayerName)
    player_id = player.id
    db.delete(player)
    db.commit()
    assert not library_search.public_player_id(db, player_id)


def test_exact_player_candidate_allows_non_strict_only_with_compatible_legacy_aliases(db):
    player = _player(db)
    _name(db, "player", player, KifuPlayerName)
    assert library_search.unique_exact_player_id(db, "王星昊", strict=False) == player.id
    db.add(KifuPlayerAlias(player_id=player.id, alias="王星昊", normalized_alias="王星昊"))
    db.commit()
    assert library_search.unique_exact_player_id(db, "王星昊", strict=False) == player.id
    tournament = KifuEvent(canonical_name="Cup")
    db.add(tournament)
    db.flush()
    db.add(KifuEventAlias(event_id=tournament.id, alias="王星昊", normalized_alias="王星昊"))
    db.commit()
    assert library_search.unique_exact_player_id(db, "王星昊", strict=False) is None


@pytest.mark.parametrize("during_proof", [False, True])
def test_exact_player_candidate_falls_back_for_potential_selected_raw_match(db, monkeypatch, during_proof):
    player = _player(db)
    _name(db, "player", player, KifuPlayerName)

    def add_selection():
        db.add(
            KifuAlbumEventSelection(
                album_id=999,
                batch_id=999,
                selected_raw="王星昊杯",
                sgf_sha256="a" * 64,
                status="approved",
                property_name="GN",
                property_index=1,
                rule_version="test",
                reviewer_id="reviewer",
                reviewed_at=datetime.now(timezone.utc),
            )
        )
        db.commit()

    if during_proof:
        original = library_search._qualified_name_rows

        def qualify(*args, **kwargs):
            rows = original(*args, **kwargs)
            add_selection()
            return rows

        monkeypatch.setattr(library_search, "_qualified_name_rows", qualify)
    else:
        add_selection()
    assert library_search.unique_exact_player_id(db, "王星昊", strict=True) is None


@pytest.mark.parametrize("strict", [False, True])
def test_unique_player_list_skips_unrelated_search_proofs_and_id_filter_requires_public_name(db, monkeypatch, strict):
    from katrain.web.api.v1.endpoints import kifu

    monkeypatch.setenv("KIFU_STRICT_NAMES", "1" if strict else "0")
    player = _player(db)
    _name(db, "player", player, KifuPlayerName)
    other = _player(db)
    db.add_all(
        [
            KifuAlbum(
                player_black="Wang",
                player_white="Other",
                black_player_id=player.id,
                sgf_content="(;B[aa])",
                source_path="wang.sgf",
                date_sort="2026-01-01",
            ),
            KifuAlbum(
                player_black="Private",
                player_white="Other",
                black_player_id=other.id,
                sgf_content="(;B[bb])",
                source_path="private.sgf",
                date_sort="2026-01-02",
            ),
        ]
    )
    db.commit()

    def unrelated(*args, **kwargs):
        pytest.fail("unique exact player must not run unrelated name/event search proof")

    monkeypatch.setattr(kifu, "strict_matching_names", unrelated)
    monkeypatch.setattr(kifu, "strict_selected_event_search_ids", unrelated)
    page = kifu.read_album_page(db, q="王星昊")
    assert page.total == 1
    assert [row.player_black for row in page.items] == ["Wang"]
    assert page.preview.id == page.items[0].id
    assert kifu.read_album_page(db, player_id=player.id).total == 1
    assert kifu.read_album_page(db, player_id=other.id).total == 0
    assert kifu.read_album_page(db, player_id=987654321).total == 0
