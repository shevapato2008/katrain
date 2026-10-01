"""Strict kifu display and search require the exact approved evidence."""

import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from katrain.web.api.v1.endpoints import kifu
from katrain.web.kifu import identity
from katrain.web.kifu.name_coverage import coverage_report
from katrain.web.kifu.name_inventory import build_inventory
from katrain.web.core.models_db import (
    Base,
    KifuAlbum,
    KifuEvent,
    KifuEventName,
    KifuNameResearchEvidence,
    KifuNameSourceRegistry,
    KifuPlayer,
    KifuPlayerName,
    KifuRawPlayerValue,
    KifuRawPlayerName,
    KifuRawEventValue,
    KifuRawEventName,
)


def _request():
    return SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace()))


def _db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return engine, sessionmaker(bind=engine)()


def _evidence(db, owner, owner_id, lang, display, decision="conventional", revision=1, approved=True):
    registry = db.query(KifuNameSourceRegistry).first()
    if registry is None:
        registry = KifuNameSourceRegistry(version="test", sha256="a" * 64, registry={})
        db.add(registry)
        db.flush()
    row = KifuNameResearchEvidence(
        **{f"{owner}_id": owner_id},
        lang=lang,
        revision=revision,
        source_registry_id=registry.id,
        candidate_name=display,
        decision_kind=decision,
        generation_rule_version="test-v1",
        research_payload={},
        producer_id="producer",
        producer_model="gpt-6-luna",
        reviewer_id="reviewer" if approved else None,
        reviewer_model="gpt-6-sol" if approved else None,
        reviewed_at=datetime.now(timezone.utc) if approved else None,
        review_status="approved" if approved else "pending",
    )
    db.add(row)
    db.flush()
    return row


def _list(db, q=None, lang="cn"):
    return asyncio.run(kifu.list_kifu_albums(_request(), q=q, page=1, page_size=20, lang=lang, db=db))


def test_strict_display_checks_exact_evidence_and_never_leaks_raw(monkeypatch):
    monkeypatch.setenv("KIFU_STRICT_NAMES", "1")
    engine, db = _db()
    try:
        person = KifuPlayer(canonical_name="Go Seigen")
        other = KifuPlayer(canonical_name="Other")
        event_entity = KifuEvent(canonical_name="Oteai")
        db.add_all([person, other, event_entity])
        db.flush()
        good = _evidence(db, "player", person.id, "cn", "吴清源")
        _evidence(db, "player", other.id, "cn", "冒名")
        pending = _evidence(db, "event", event_entity.id, "cn", "大手合", approved=False)
        db.add_all(
            [
                KifuPlayerName(
                    player_id=person.id,
                    lang="cn",
                    display_name="吴清源",
                    status="verified",
                    decision_kind="conventional",
                    generation_rule_version="test-v1",
                    revision=1,
                    evidence_id=good.id,
                ),
                KifuPlayerName(
                    player_id=other.id,
                    lang="cn",
                    display_name="冒名",
                    status="verified",
                    decision_kind="conventional",
                    generation_rule_version="test-v1",
                    revision=1,
                    evidence_id=good.id,
                ),
                KifuEventName(
                    event_id=event_entity.id,
                    lang="cn",
                    display_name="大手合",
                    status="verified",
                    decision_kind="conventional",
                    generation_rule_version="test-v1",
                    revision=1,
                    evidence_id=pending.id,
                ),
                KifuAlbum(
                    player_black="Go Seigen",
                    player_white="SGF_BAD]BR[九段",
                    black_player_id=person.id,
                    event="JapanPromotionTournament,1934,Fall",
                    event_id=event_entity.id,
                    sgf_content="(;PB[Go Seigen])",
                    source_path="one.sgf",
                ),
                KifuAlbum(
                    player_black="Other",
                    player_white="Unknown",
                    black_player_id=other.id,
                    event="GNUGo3.8",
                    sgf_content="(;PB[Other])",
                    source_path="two.sgf",
                ),
            ]
        )
        db.commit()
        result = _list(db)
        by_raw = {item.player_black: item for item in result.items}
        assert by_raw["Go Seigen"].display_player_black == "吴清源"
        assert by_raw["Go Seigen"].display_player_white == "棋手姓名有误"
        assert by_raw["Go Seigen"].display_event == "赛事名称待核实"
        assert by_raw["Other"].display_player_black != "冒名"
        assert by_raw["Other"].display_player_white == "未知棋手"
        assert by_raw["Other"].display_event == "赛事名称待核实"
        assert by_raw["Go Seigen"].player_white == "SGF_BAD]BR[九段"
        detail = asyncio.run(kifu.get_kifu_album(_request(), by_raw["Go Seigen"].id, lang="cn", db=db))
        assert detail.sgf_content == "(;PB[Go Seigen])"
    finally:
        db.close()
        engine.dispose()


def test_strict_raw_name_is_scoped_to_exact_spelling_and_searchable(monkeypatch):
    monkeypatch.setenv("KIFU_STRICT_NAMES", "1")
    engine, db = _db()
    try:
        raw = KifuRawPlayerValue(raw_value="Unlinked A", category="readable", review_status="approved")
        db.add(raw)
        db.flush()
        ev = _evidence(db, "raw_player", raw.id, "ru", "Имя А")
        db.add(
            KifuRawPlayerName(
                raw_player_id=raw.id,
                lang="ru",
                display_name="Имя А",
                status="verified",
                decision_kind="conventional",
                generation_rule_version="test-v1",
                revision=1,
                evidence_id=ev.id,
            )
        )
        db.add_all(
            [
                KifuAlbum(
                    player_black="Unlinked A", player_white="Unknown", sgf_content="(;B[aa])", source_path="a.sgf"
                ),
                KifuAlbum(
                    player_black="Unlinked B", player_white="Unknown", sgf_content="(;B[bb])", source_path="b.sgf"
                ),
            ]
        )
        db.commit()
        assert {x.player_black: x.display_player_black for x in _list(db, lang="ru").items}["Unlinked A"] == "Имя А"
        assert [x.player_black for x in _list(db, "Имя А", "ru").items] == ["Unlinked A"]
    finally:
        db.close()
        engine.dispose()


def test_strict_cross_language_search_requires_approved_unambiguous_name(monkeypatch):
    monkeypatch.setenv("KIFU_STRICT_NAMES", "1")
    engine, db = _db()
    try:
        person = KifuPlayer(canonical_name="Go Seigen")
        other = KifuPlayer(canonical_name="Other")
        db.add_all([person, other])
        db.flush()
        for lang, display in (("cn", "吴清源"), ("en", "Go Seigen"), ("ru", "Го Сэйгэн")):
            evidence = _evidence(db, "player", person.id, lang, display)
            db.add(
                KifuPlayerName(
                    player_id=person.id,
                    lang=lang,
                    display_name=display,
                    status="verified",
                    decision_kind="conventional",
                    generation_rule_version="test-v1",
                    revision=1,
                    evidence_id=evidence.id,
                )
            )
        db.add_all(
            [
                KifuAlbum(
                    player_black="Go Seigen",
                    player_white="X",
                    black_player_id=person.id,
                    sgf_content="(;B[aa])",
                    source_path="go.sgf",
                ),
                KifuAlbum(
                    player_black="Other",
                    player_white="X",
                    black_player_id=other.id,
                    sgf_content="(;B[bb])",
                    source_path="other.sgf",
                ),
            ]
        )
        db.commit()
        for name in ("吴清源", "Go Seigen", "Го Сэйгэн"):
            assert [x.player_black for x in _list(db, name).items] == ["Go Seigen"]
        # A second identity with the same approved spelling makes expansion unsafe.
        evidence = _evidence(db, "player", other.id, "ru", "Го Сэйгэн")
        db.add(
            KifuPlayerName(
                player_id=other.id,
                lang="ru",
                display_name="Го Сэйгэн",
                status="verified",
                decision_kind="conventional",
                generation_rule_version="test-v1",
                revision=1,
                evidence_id=evidence.id,
            )
        )
        db.commit()
        assert _list(db, "Го Сэйгэн").total == 0
    finally:
        db.close()
        engine.dispose()


@pytest.mark.parametrize(
    "mismatch", ["owner", "lang", "status", "display", "decision", "revision", "rule", "signature"]
)
def test_strict_name_rejects_each_evidence_mismatch(monkeypatch, mismatch):
    monkeypatch.setenv("KIFU_STRICT_NAMES", "1")
    engine, db = _db()
    try:
        person = KifuPlayer(canonical_name="One")
        other = KifuPlayer(canonical_name="Two")
        db.add_all([person, other])
        db.flush()
        evidence = _evidence(
            db,
            "player",
            other.id if mismatch == "owner" else person.id,
            "en" if mismatch == "lang" else "cn",
            "吴清源",
            approved=mismatch != "status",
        )
        if mismatch == "signature":
            evidence.reviewer_model = None
        name = KifuPlayerName(
            player_id=person.id,
            lang="cn",
            display_name="错名" if mismatch == "display" else "吴清源",
            status="verified",
            decision_kind="generated" if mismatch == "decision" else "conventional",
            generation_rule_version="other" if mismatch == "rule" else "test-v1",
            revision=2 if mismatch == "revision" else 1,
            evidence_id=evidence.id,
        )
        db.add_all(
            [
                name,
                KifuAlbum(
                    player_black="One",
                    player_white="Unknown",
                    black_player_id=person.id,
                    sgf_content="(;B[aa])",
                    source_path="one.sgf",
                ),
            ]
        )
        db.commit()
        assert _list(db).items[0].display_player_black == "棋手姓名待核实"
    finally:
        db.close()
        engine.dispose()


def test_strict_cwi_wrong_link_never_returns_raw_event(monkeypatch):
    monkeypatch.setenv("KIFU_STRICT_NAMES", "1")
    engine, db = _db()
    try:
        wrong = KifuEvent(canonical_name="Samsung Cup")
        db.add(wrong)
        db.flush()
        evidence = _evidence(db, "event", wrong.id, "cn", "三星杯")
        db.add_all(
            [
                KifuEventName(
                    event_id=wrong.id,
                    lang="cn",
                    display_name="三星杯",
                    status="verified",
                    decision_kind="conventional",
                    generation_rule_version="test-v1",
                    revision=1,
                    evidence_id=evidence.id,
                ),
                KifuAlbum(
                    player_black="Unknown",
                    player_white="Unknown",
                    event="JapanPromotionTournament,1934,Fall",
                    event_id=wrong.id,
                    sgf_content="(;B[aa])",
                    source_path="wrong.sgf",
                ),
            ]
        )
        db.commit()
        assert _list(db).items[0].display_event == "赛事名称待核实"
    finally:
        db.close()
        engine.dispose()


def test_strict_page_batches_twenty_albums_in_all_languages(monkeypatch):
    monkeypatch.setenv("KIFU_STRICT_NAMES", "1")
    engine, db = _db()
    try:
        player = KifuPlayer(canonical_name="One")
        tournament = KifuEvent(canonical_name="Cup")
        db.add_all([player, tournament])
        db.flush()
        languages = sorted(kifu.LANGUAGES)
        for lang in languages:
            for owner, owner_id, model, key, prefix in (
                ("player", player.id, KifuPlayerName, "player_id", "Player"),
                ("event", tournament.id, KifuEventName, "event_id", "Cup"),
            ):
                display = f"{prefix} {lang}"
                evidence = _evidence(db, owner, owner_id, lang, display)
                db.add(
                    model(
                        **{key: owner_id},
                        lang=lang,
                        display_name=display,
                        status="verified",
                        decision_kind="conventional",
                        generation_rule_version="test-v1",
                        revision=1,
                        evidence_id=evidence.id,
                    )
                )
        for index in range(20):
            db.add(
                KifuAlbum(
                    player_black="One",
                    player_white="One",
                    black_player_id=player.id,
                    white_player_id=player.id,
                    event="Cup",
                    event_id=tournament.id,
                    sgf_content="(;B[aa])",
                    source_path=f"{index}.sgf",
                )
            )
        db.commit()
        statements = []

        def record_sql(_connection, _cursor, statement, _parameters, _context, _executemany):
            statements.append(statement)

        event.listen(engine, "before_cursor_execute", record_sql)
        try:
            for lang in languages:
                statements.clear()
                page = _list(db, lang=lang)
                assert len(page.items) == 20
                assert all(
                    item.display_player_black == f"Player {lang}" and item.display_event == f"Cup {lang}"
                    for item in page.items
                )
                assert len(statements) <= 7
        finally:
            event.remove(engine, "before_cursor_execute", record_sql)
    finally:
        db.close()
        engine.dispose()


def test_strict_approved_program_label_is_hidden(monkeypatch):
    monkeypatch.setenv("KIFU_STRICT_NAMES", "1")
    engine, db = _db()
    try:
        raw = KifuRawEventValue(raw_value="GNUGo3.8", category="program_source_label", review_status="approved")
        db.add(raw)
        db.flush()
        evidence = _evidence(db, "raw_event", raw.id, "cn", "", decision="hidden")
        db.add_all(
            [
                KifuRawEventName(
                    raw_event_id=raw.id,
                    lang="cn",
                    display_name="",
                    status="verified",
                    decision_kind="hidden",
                    generation_rule_version="test-v1",
                    revision=1,
                    evidence_id=evidence.id,
                ),
                KifuAlbum(
                    player_black="Unknown",
                    player_white="Unknown",
                    event="GNUGo3.8",
                    sgf_content="(;B[aa])",
                    source_path="program.sgf",
                ),
            ]
        )
        db.commit()
        assert _list(db).items[0].display_event == ""
    finally:
        db.close()
        engine.dispose()


def test_strict_cwi_edition_requires_exact_approved_raw_display(monkeypatch):
    monkeypatch.setenv("KIFU_STRICT_NAMES", "1")
    engine, db = _db()
    try:
        tournament = KifuEvent(canonical_name="Oteai")
        db.add(tournament)
        db.flush()
        evidence = _evidence(db, "event", tournament.id, "cn", "大手合")
        db.add(
            KifuEventName(
                event_id=tournament.id,
                lang="cn",
                display_name="大手合",
                status="verified",
                decision_kind="conventional",
                generation_rule_version="test-v1",
                revision=1,
                evidence_id=evidence.id,
            )
        )
        raw_spelling = "JapanPromotionTournament,1934,Fall"
        album = KifuAlbum(
            player_black="Unknown",
            player_white="Unknown",
            event=raw_spelling,
            event_id=tournament.id,
            sgf_content="(;B[aa])",
            source_path="cwi.sgf",
        )
        db.add(album)
        db.commit()
        assert _list(db).items[0].display_event == "赛事名称待核实"
        assert identity.strict_slot_approvals(db, [album], "cn")[album.id][2] is None

        raw = KifuRawEventValue(raw_value=raw_spelling, category="formal_event_candidate", review_status="approved")
        db.add(raw)
        db.flush()
        raw_evidence = _evidence(db, "raw_event", raw.id, "cn", "1934年秋季大手合")
        db.add(
            KifuRawEventName(
                raw_event_id=raw.id,
                lang="cn",
                display_name="1934年秋季大手合",
                status="verified",
                decision_kind="conventional",
                generation_rule_version="test-v1",
                revision=1,
                evidence_id=raw_evidence.id,
            )
        )
        db.commit()
        assert _list(db).items[0].display_event == "1934年秋季大手合"
        assert identity.strict_slot_approvals(db, [album], "cn")[album.id][2] == ("conventional", raw_evidence.id)
    finally:
        db.close()
        engine.dispose()


@pytest.mark.parametrize(
    "raw_spelling, display",
    [
        ("Oteai 1960", "大手合 · 1960"),
        ("1934年第十二届日本大手合第3轮", "1934年第十二届大手合第3轮"),
    ],
)
@pytest.mark.parametrize("approved", [False, True])
def test_strict_linked_event_preserves_only_approved_structural_display(monkeypatch, raw_spelling, display, approved):
    monkeypatch.setenv("KIFU_STRICT_NAMES", "1")
    engine, db = _db()
    try:
        tournament = KifuEvent(canonical_name="Oteai")
        raw = KifuRawEventValue(raw_value=raw_spelling, category="formal_event_candidate", review_status="approved")
        db.add_all([tournament, raw])
        db.flush()
        core_evidence = _evidence(db, "event", tournament.id, "cn", "大手合")
        raw_evidence = _evidence(db, "raw_event", raw.id, "cn", display, approved=approved)
        db.add_all(
            [
                KifuEventName(
                    event_id=tournament.id,
                    lang="cn",
                    display_name="大手合",
                    status="verified",
                    decision_kind="conventional",
                    generation_rule_version="test-v1",
                    revision=1,
                    evidence_id=core_evidence.id,
                ),
                KifuRawEventName(
                    raw_event_id=raw.id,
                    lang="cn",
                    display_name=display,
                    status="verified",
                    decision_kind="conventional",
                    generation_rule_version="test-v1",
                    revision=1,
                    evidence_id=raw_evidence.id,
                ),
            ]
        )
        album = KifuAlbum(
            player_black="Unknown",
            player_white="Unknown",
            event=raw_spelling,
            event_id=tournament.id,
            sgf_content="(;B[aa])",
            source_path="structured-event.sgf",
        )
        db.add(album)
        db.commit()

        item = _list(db).items[0]
        assert item.event == raw_spelling
        assert item.display_event == (display if approved else "赛事名称待核实")
        assert identity.strict_slot_approvals(db, [album], "cn")[album.id][2] == (
            ("conventional", raw_evidence.id) if approved else None
        )
        coverage = coverage_report(engine, build_inventory(engine), languages=("cn",))
        assert coverage["languages"]["cn"]["approved"] == int(approved)
        assert any(gap["slot"] == "event" for gap in coverage["missing_examples"]) is not approved
    finally:
        db.close()
        engine.dispose()


def test_strict_ambiguous_raw_translation_does_not_join_different_spellings(monkeypatch):
    monkeypatch.setenv("KIFU_STRICT_NAMES", "1")
    engine, db = _db()
    try:
        for index, raw_spelling in enumerate(("Unlinked A", "Unlinked B")):
            raw = KifuRawPlayerValue(raw_value=raw_spelling, category="readable", review_status="approved")
            db.add(raw)
            db.flush()
            evidence = _evidence(db, "raw_player", raw.id, "ru", "Общее имя")
            db.add(
                KifuRawPlayerName(
                    raw_player_id=raw.id,
                    lang="ru",
                    display_name="Общее имя",
                    status="verified",
                    decision_kind="conventional",
                    generation_rule_version="test-v1",
                    revision=1,
                    evidence_id=evidence.id,
                )
            )
            db.add(
                KifuAlbum(
                    player_black=raw_spelling,
                    player_white="Unknown",
                    sgf_content="(;B[aa])",
                    source_path=f"raw-{index}.sgf",
                )
            )
        db.commit()
        assert _list(db, "Общее имя", "ru").total == 0
        assert [item.player_black for item in _list(db, "Unlinked A", "ru").items] == ["Unlinked A"]
    finally:
        db.close()
        engine.dispose()
