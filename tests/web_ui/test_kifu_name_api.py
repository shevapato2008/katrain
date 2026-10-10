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
    KifuAlbumEventSelection,
    KifuEventSelectionBatch,
)
from tests.web_ui._kifu_selection_helpers import apply_reviewed_selection
from tests.web_ui.test_kifu_name_batch import engine  # noqa: F401
from katrain.web.kifu.provenance import sgf_sha256


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


def _list(db, q=None, lang="cn", page_size=20):
    return asyncio.run(kifu.list_kifu_albums(_request(), q=q, page=1, page_size=page_size, lang=lang, db=db))


def _assert_page_scoped_sgf_read(statements):
    """The preview may read SGF only through the bounded album page query."""
    reads = [statement.lower() for statement in statements if "sgf_content" in statement.lower()]
    assert len(reads) == 1
    assert "from kifu_albums" in reads[0]
    assert "order by" in reads[0]
    assert "limit" in reads[0]
    assert "offset" in reads[0]
    assert "count(" not in reads[0]


def _preserve_stored_locale(monkeypatch):
    """Exercise historical 11-language approval rules below the new UI fallback."""
    monkeypatch.setattr(kifu, "name_display_language", lambda lang: lang)


def test_linked_sgf_exact_title_list_detail_and_search(monkeypatch, engine):
    from katrain.web.kifu.name_batch import apply_bundle
    from tests.web_ui.test_kifu_name_candidates import registry
    from tests.web_ui.test_kifu_raw_event_title_translation import linked_reviewed_bundle

    monkeypatch.setenv("KIFU_STRICT_NAMES", "1")
    proposed, inv, research = linked_reviewed_bundle(
        engine, raw="28th Honinbo", lang="cn", display="第28届本因坊战")
    apply_bundle(engine, proposed, registry(), inv, research)
    with sessionmaker(bind=engine)() as db:
        page = _list(db, "第28届本因坊战", "cn")
        assert page.total == 1 and [item.id for item in page.items] == [11]
        assert page.items[0].display_event == "第28届本因坊战"
        detail = asyncio.run(kifu.get_kifu_album(_request(), 11, lang="cn", db=db))
        assert detail.display_event == "第28届本因坊战"


def test_nonprimary_ui_language_displays_english_kifu_names(monkeypatch):
    monkeypatch.setenv("KIFU_STRICT_NAMES", "1")
    engine, db = _db()
    try:
        player = KifuPlayer(canonical_name="Go Seigen")
        db.add(player)
        db.flush()
        for lang, display in (("en", "Go Seigen"), ("ko", "우칭위안"), ("ru", "Го Сэйгэн")):
            evidence = _evidence(db, "player", player.id, lang, display)
            db.add(KifuPlayerName(
                player_id=player.id, lang=lang, display_name=display, status="verified",
                decision_kind="conventional", generation_rule_version="test-v1", revision=1,
                evidence_id=evidence.id,
            ))
        album = KifuAlbum(
            player_black="Go Seigen", player_white="Opponent", black_player_id=player.id,
            round_name="Final", sgf_content="(;B[aa])", source_path="go.sgf",
        )
        db.add(album)
        db.commit()
        assert _list(db, lang="ko").items[0].display_player_black == "우칭위안"
        for lang in ("de", "es", "fr", "ru", "tr", "ua"):
            assert _list(db, lang=lang).items[0].display_player_black == "Go Seigen"
            assert asyncio.run(kifu.get_kifu_album(_request(), album.id, lang=lang, db=db)).display_player_black == (
                "Go Seigen"
            )
        assert _list(db, lang="ru").items[0].display_round_name == "Финал"
    finally:
        db.close()
        engine.dispose()


def test_reviewed_second_gn_event_display_search_and_sgf_drift(monkeypatch):
    monkeypatch.setenv("KIFU_STRICT_NAMES", "1")
    engine, db = _db()
    selected_raw = "第5届韩国最强棋士战预选"
    sgf = (
        "(;FF[4]SZ[19]SO[https://19x19.com]"
        f"GN[GNUGo3.8]GN[{selected_raw}]GC[{selected_raw} | 194手];B[aa])"
    )
    try:
        raw = KifuRawEventValue(raw_value=selected_raw, category="game_description", review_status="approved")
        db.add(raw)
        db.flush()
        for lang, display in (("cn", "韩国最强棋士战预选"), ("en", "Korean Strongest Qualifier")):
            evidence = _evidence(db, "raw_event", raw.id, lang, display)
            db.add(KifuRawEventName(
                raw_event_id=raw.id, lang=lang, display_name=display, status="verified",
                decision_kind="conventional", generation_rule_version="test-v1", revision=1,
                evidence_id=evidence.id,
            ))
        selected = KifuAlbum(
            player_black="Black", player_white="White", event="GNUGo3.8", sgf_content=sgf,
            source="https://19x19.com", source_path="data/kifu-album/19x19/selected.sgf",
        )
        unselected = KifuAlbum(
            player_black="Black", player_white="White", event="GNUGo3.8", sgf_content=sgf,
            source="https://19x19.com", source_path="data/kifu-album/19x19/unselected.sgf",
        )
        db.add_all([selected, unselected])
        db.flush()
        db.commit()
        apply_reviewed_selection(engine, selected.id)
        fake = KifuEventSelectionBatch(
            bundle_sha256="c" * 64, member_set_sha256="d" * 64, reviewed_artifact={},
            producer_id="fake-producer", reviewer_id="fake-reviewer",
            reviewed_at=datetime.now(timezone.utc), status="applied",
        )
        db.add(fake)
        db.flush()
        db.add(KifuAlbumEventSelection(
            album_id=unselected.id, batch_id=fake.id, selected_raw=selected_raw,
            sgf_sha256=sgf_sha256(sgf), property_name="GN", property_index=1,
            status="approved", rule_version="19x19-gnugo-second-gn-v1",
            reviewer_id="fake-reviewer", reviewed_at=datetime.now(timezone.utc),
        ))
        db.commit()

        by_id = {item.id: item for item in _list(db, lang="cn").items}
        assert by_id[selected.id].display_event == "韩国最强棋士战预选"
        assert by_id[unselected.id].display_event == "赛事名称待核实"
        assert asyncio.run(kifu.get_kifu_album(_request(), selected.id, lang="en", db=db)).display_event == (
            "Korean Strongest Qualifier"
        )
        for query in ("韩国最强棋士战预选", "Korean Strongest Qualifier", selected_raw):
            result = _list(db, query, "cn")
            assert result.total == 1
            assert [item.id for item in result.items] == [selected.id]

        selected.sgf_content += " "
        db.commit()
        assert asyncio.run(kifu.get_kifu_album(_request(), selected.id, lang="cn", db=db)).display_event == (
            "赛事名称待核实"
        )
        result = _list(db, "Korean Strongest Qualifier", "cn")
        assert result.total == 0
        assert result.items == []
    finally:
        db.close()
        engine.dispose()


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
    _preserve_stored_locale(monkeypatch)
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
    _preserve_stored_locale(monkeypatch)
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
            query_counts = []
            for lang in languages:
                statements.clear()
                page = _list(db, lang=lang)
                assert len(page.items) == 20
                assert all(
                    item.display_player_black == f"Player {lang}" and item.display_event == f"Cup {lang}"
                    for item in page.items
                )
                _assert_page_scoped_sgf_read(statements)
                query_counts.append(len(statements))
                assert len(statements) <= 10
            assert len(set(query_counts)) == 1
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


def test_strict_duplicate_gn_event_stays_unverified_despite_approved_program_label(monkeypatch):
    monkeypatch.setenv("KIFU_STRICT_NAMES", "1")
    engine, db = _db()
    try:
        raw = KifuRawEventValue(raw_value="GNUGo3.8", category="program_source_label", review_status="approved")
        db.add(raw)
        db.flush()
        evidence = _evidence(db, "raw_event", raw.id, "cn", "", decision="hidden")
        db.add(KifuRawEventName(
            raw_event_id=raw.id, lang="cn", display_name="", status="verified", decision_kind="hidden",
            generation_rule_version="test-v1", revision=1, evidence_id=evidence.id,
        ))
        program = KifuAlbum(
            player_black="Black", player_white="White", event="GNUGo3.8",
            sgf_content="(;SO[https://19x19.com]GN[GNUGo3.8]GC[GNUGo3.8])",
            source_path="program-only.sgf",
        )
        masked = KifuAlbum(
            player_black="Black", player_white="White", event="GNUGo3.8",
            sgf_content=("(;SO[https://19x19.com]GN[GNUGo3.8]"
                         "GN[第5届韩国最强棋士战预选]GC[第5届韩国最强棋士战预选 | 194手])"),
            source_path="masked-event.sgf",
        )
        db.add_all([program, masked])
        db.commit()

        statements = []

        def record_sql(_connection, _cursor, statement, _parameters, _context, _executemany):
            statements.append(statement)

        event.listen(engine, "before_cursor_execute", record_sql)
        try:
            items = {item.id: item for item in _list(db).items}
        finally:
            event.remove(engine, "before_cursor_execute", record_sql)
        assert sum("sgf_content" in statement for statement in statements) == 1
        assert items[program.id].display_event == ""
        assert items[masked.id].display_event == "赛事名称待核实"
        detail = asyncio.run(kifu.get_kifu_album(_request(), masked.id, lang="cn", db=db))
        assert detail.display_event == "赛事名称待核实"
        approvals = identity.strict_slot_approvals(db, [program, masked], "cn")
        assert approvals[program.id][2] == ("hidden", evidence.id)
        assert approvals[masked.id][2] is None

        coverage = coverage_report(engine, build_inventory(engine), languages=("cn",))
        assert coverage["languages"]["cn"]["by_decision"] == {"hidden": 1}
        assert {gap["album_id"] for gap in coverage["missing_examples"] if gap["slot"] == "event"} == {
            masked.id,
        }
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


def _reviewed_composition(db, count=1, owner_refs=False):
    """Store the importer schema, including immutable candidate/rule/scope bindings."""
    from katrain.web.kifu.name_candidates import canonical_sha256
    from katrain.web.kifu.name_composition import base_candidate_sha256

    series = KifuEvent(canonical_name="Honinbo")
    raw = KifuRawEventValue(raw_value="1st Honinbo", category="unclassified_pending", review_status="approved")
    db.add_all([series, raw])
    db.flush()
    albums = [
        KifuAlbum(
            player_black="Black",
            player_white="White",
            event=raw.raw_value,
            event_id=series.id,
            sgf_content="(;B[aa])",
            source_path=f"composed-{i}.sgf",
        )
        for i in range(count)
    ]
    db.add_all(albums)
    db.flush()
    series_owner = {"kind": "event", "ref": "honinbo"} if owner_refs else {"kind": "event", "id": series.id}
    raw_owner = {"kind": "raw_event", "ref": "honinbo-1"} if owner_refs else {"kind": "raw_event", "id": raw.id}
    for lang, base_display, display in (("cn", "本因坊战", "第1届本因坊战"), ("fr", "Honinbo", "1er Honinbo")):
        base_candidate = {
            "owner": series_owner,
            "lang": lang,
            "display_name": base_display,
            "decision_kind": "conventional",
        }
        base_evidence = _evidence(db, "event", series.id, lang, base_display)
        base_evidence.research_payload = {"candidate": base_candidate}
        base_name = KifuEventName(
            event_id=series.id,
            lang=lang,
            display_name=base_display,
            status="verified",
            decision_kind="conventional",
            generation_rule_version="test-v1",
            revision=1,
            evidence_id=base_evidence.id,
        )
        db.add(base_name)
        db.flush()
        base_hash = base_candidate_sha256(base_candidate)
        rule = {
            "content": {
                "series_owner": base_candidate["owner"],
                "lang": lang,
                "base_candidate_sha256": base_hash,
                "style": "test-style",
            },
            "approval": {"status": "approved"},
        }
        scope_entry = {
            "owner": raw_owner,
            "raw_value": raw.raw_value,
            "edition": 1,
            "occurrence_album_ids": [album.id for album in albums],
            "occurrence_sha256": canonical_sha256([album.id for album in albums]),
            "raw_scope_sha256": canonical_sha256([[album.id, "event"] for album in albums]),
        }
        scope = {
            "content": {"series_owner": base_candidate["owner"], "raws": [scope_entry]},
            "approval": {"status": "approved"},
        }
        dependencies = {
            "series_event_id": series.id,
            "base_name_id": base_name.id,
            "base_evidence_id": base_evidence.id,
            "base_revision": 1,
            "base_candidate_sha256": base_hash,
            "composition_rule_sha256": canonical_sha256(rule),
            "raw_scope_sha256": scope_entry["raw_scope_sha256"],
            "scope_sha256": canonical_sha256(scope),
        }
        candidate = {
            "owner": scope_entry["owner"],
            "raw_value": raw.raw_value,
            "lang": lang,
            "display_name": display,
            "decision_kind": "composed",
            "series_owner": base_candidate["owner"],
            "edition": 1,
            "base_candidate_sha256": base_hash,
            "composition_rule_sha256": dependencies["composition_rule_sha256"],
            "raw_scope_sha256": dependencies["raw_scope_sha256"],
        }
        evidence = _evidence(db, "raw_event", raw.id, lang, display, decision="composed")
        evidence.research_payload = {
            "candidate": candidate,
            "composition": {
                "version": "honinbo-composition-v1",
                "rule": rule,
                "scope": scope,
                "dependencies": dependencies,
            },
        }
        db.add(
            KifuRawEventName(
                raw_event_id=raw.id,
                lang=lang,
                display_name=display,
                status="verified",
                decision_kind="composed",
                generation_rule_version="test-v1",
                revision=1,
                evidence_id=evidence.id,
            )
        )
    db.commit()
    return series, raw, albums


@pytest.mark.parametrize("owner_refs", [False, True])
def test_strict_composed_display_search_and_queries_are_bounded(monkeypatch, owner_refs):
    from katrain.web.kifu import name_composition

    monkeypatch.setenv("KIFU_STRICT_NAMES", "1")
    monkeypatch.setattr(name_composition, "render_edition", lambda *args: pytest.fail("request rendered a name"))
    engine, db = _db()
    try:
        series, raw, albums = _reviewed_composition(db, count=20, owner_refs=owner_refs)
        outside = KifuAlbum(
            player_black="Black",
            player_white="White",
            event=raw.raw_value,
            event_id=series.id,
            sgf_content="(;B[aa])",
            source_path="outside-scope.sgf",
        )
        wrong = KifuAlbum(
            player_black="Black",
            player_white="White",
            event=raw.raw_value,
            sgf_content="(;B[aa])",
            source_path="unlinked.sgf",
        )
        db.add_all([outside, wrong])
        db.commit()
        statements = []

        def record_sql(_connection, _cursor, statement, _parameters, _context, _executemany):
            statements.append(statement)

        event.listen(engine, "before_cursor_execute", record_sql)
        try:
            page = _list(db, "1er Honinbo", "cn")
            page_statements = list(statements)
            statements.clear()
            first = _list(db, "1er Honinbo", "cn", page_size=1)
            first_statements = list(statements)
        finally:
            event.remove(engine, "before_cursor_execute", record_sql)
        assert page.total == 20
        assert {item.id for item in page.items} == {album.id for album in albums}
        assert all(item.display_event == "第1届本因坊战" for item in page.items)
        assert first.total == 20 and len(first.items) == 1
        assert len(page_statements) <= 28
        assert len(page_statements) <= len(first_statements) + 2
        _assert_page_scoped_sgf_read(page_statements)
        _assert_page_scoped_sgf_read(first_statements)
        assert (
            asyncio.run(kifu.get_kifu_album(_request(), outside.id, lang="cn", db=db)).display_event == "赛事名称待核实"
        )
        assert (
            asyncio.run(kifu.get_kifu_album(_request(), wrong.id, lang="cn", db=db)).display_event == "赛事名称待核实"
        )
    finally:
        db.close()
        engine.dispose()


def test_french_composed_search_keeps_its_own_approved_scope(monkeypatch):
    monkeypatch.setenv("KIFU_STRICT_NAMES", "1")
    engine, db = _db()
    try:
        series, raw, albums = _reviewed_composition(db)
        chinese = db.query(KifuRawEventName).filter_by(lang="cn").one()
        chinese.decision_kind = "conventional"
        db.get(KifuNameResearchEvidence, chinese.evidence_id).decision_kind = "conventional"
        outside = KifuAlbum(
            player_black="Black", player_white="White", event=raw.raw_value,
            event_id=series.id, sgf_content="(;B[bb])", source_path="outside-french-scope.sgf",
        )
        db.add(outside)
        db.commit()

        result = _list(db, "1er Honinbo", "cn")
        assert [item.id for item in result.items] == [albums[0].id]
        assert result.total == 1
    finally:
        db.close()
        engine.dispose()


def test_composed_selected_event_without_identity_does_not_enter_search(monkeypatch):
    _preserve_stored_locale(monkeypatch)
    monkeypatch.setenv("KIFU_STRICT_NAMES", "1")
    engine, db = _db()
    try:
        _, raw, albums = _reviewed_composition(db)
        chinese = db.query(KifuRawEventName).filter_by(lang="cn").one()
        chinese.decision_kind = "conventional"
        db.get(KifuNameResearchEvidence, chinese.evidence_id).decision_kind = "conventional"
        sgf = (
            "(;FF[4]SZ[19]SO[https://19x19.com]"
            f"GN[GNUGo3.8]GN[{raw.raw_value}]GC[{raw.raw_value} | 194手];B[aa])"
        )
        selected = KifuAlbum(
            player_black="Black", player_white="White", event="GNUGo3.8",
            sgf_content=sgf, source="https://19x19.com",
            source_path="data/kifu-album/19x19/composed-selected.sgf",
        )
        db.add(selected)
        db.commit()
        apply_reviewed_selection(engine, selected.id)
        assert identity.live_event_selections(db, [selected])[selected.id] == (raw.raw_value, None)
        assert asyncio.run(kifu.get_kifu_album(_request(), selected.id, lang="fr", db=db)).display_event == (
            "Nom du tournoi non vérifié"
        )

        result = _list(db, "1er Honinbo", "fr")
        assert [item.id for item in result.items] == [albums[0].id]
        assert result.total == 1
    finally:
        db.close()
        engine.dispose()


@pytest.mark.parametrize(
    "drift",
    [
        "pending",
        "raw_owner",
        "raw_value",
        "raw_evidence_owner",
        "raw_revision",
        "raw_evidence_revision",
        "base_missing",
        "base_pending",
        "base_lang",
        "base_name_id",
        "base_name_id_list",
        "base_evidence_id",
        "base_revision",
        "base_candidate",
        "base_display",
        "base_rule",
        "series_link",
        "series_dependency",
        "rule_hash",
        "rule_body",
        "scope_hash",
        "scope_body",
        "raw_scope_hash",
        "candidate_raw_scope",
        "candidate_raw",
        "candidate_lang",
        "candidate_owner",
        "candidate_series",
        "scope_owner",
        "version",
        "raw_scope_slot",
    ],
)
def test_strict_composed_dependency_drift_is_a_display_search_and_coverage_gap(monkeypatch, drift):
    _preserve_stored_locale(monkeypatch)
    from copy import deepcopy
    from katrain.web.kifu.name_candidates import canonical_sha256

    monkeypatch.setenv("KIFU_STRICT_NAMES", "1")
    engine, db = _db()
    try:
        series, raw, albums = _reviewed_composition(db)
        album = albums[0]
        name = db.query(KifuRawEventName).filter_by(lang="fr").one()
        evidence = db.get(KifuNameResearchEvidence, name.evidence_id)
        base = db.query(KifuEventName).filter_by(lang="fr").one()
        base_evidence = db.get(KifuNameResearchEvidence, base.evidence_id)
        payload = deepcopy(evidence.research_payload)
        dependency = payload["composition"]["dependencies"]
        if drift == "pending":
            evidence.review_status = "pending"
        elif drift == "raw_owner":
            raw.review_status = "pending"
        elif drift == "raw_value":
            raw.raw_value = "2nd Honinbo"
        elif drift == "raw_evidence_owner":
            other = KifuRawEventValue(raw_value="Other raw", category="unclassified_pending", review_status="approved")
            db.add(other)
            db.flush()
            evidence.raw_event_id = other.id
        elif drift == "raw_revision":
            name.revision += 1
        elif drift == "raw_evidence_revision":
            evidence.revision += 1
        elif drift == "base_missing":
            db.delete(base)
        elif drift == "base_pending":
            base_evidence.review_status = "pending"
        elif drift == "base_lang":
            base.lang = "de"
        elif drift in {"base_name_id", "base_evidence_id", "base_revision", "series_dependency"}:
            dependency["series_event_id" if drift == "series_dependency" else drift] += 100
        elif drift == "base_name_id_list":
            dependency["base_name_id"] = [base.id]
        elif drift == "base_candidate":
            base_evidence.research_payload = {"candidate": {"changed": True}}
        elif drift == "base_display":
            base.display_name = "Changed"
        elif drift == "base_rule":
            base.generation_rule_version = "changed"
        elif drift == "series_link":
            album.event_id = None
        elif drift == "rule_hash":
            dependency["composition_rule_sha256"] = "0" * 64
        elif drift == "rule_body":
            payload["composition"]["rule"]["content"]["style"] = "changed"
        elif drift == "scope_hash":
            dependency["scope_sha256"] = "0" * 64
        elif drift == "scope_body":
            payload["composition"]["scope"]["content"]["raws"][0]["edition"] = 2
        elif drift == "raw_scope_hash":
            dependency["raw_scope_sha256"] = "0" * 64
        elif drift == "raw_scope_slot":
            entry = payload["composition"]["scope"]["content"]["raws"][0]
            entry["raw_scope_sha256"] = canonical_sha256([[album.id, "selected_event"]])
            dependency["raw_scope_sha256"] = payload["candidate"]["raw_scope_sha256"] = entry["raw_scope_sha256"]
            dependency["scope_sha256"] = canonical_sha256(payload["composition"]["scope"])
        elif drift == "candidate_raw_scope":
            payload["candidate"]["raw_scope_sha256"] = "0" * 64
        elif drift == "candidate_raw":
            payload["candidate"]["raw_value"] = "2nd Honinbo"
        elif drift == "candidate_lang":
            payload["candidate"]["lang"] = "cn"
        elif drift == "candidate_owner":
            payload["candidate"]["owner"] = {"kind": "raw_event", "id": 999}
        elif drift == "candidate_series":
            payload["candidate"]["series_owner"] = {"kind": "event", "id": 999}
        elif drift == "scope_owner":
            payload["composition"]["scope"]["content"]["raws"][0]["owner"]["id"] = 999
        elif drift == "version":
            payload["composition"]["version"] = "unknown"
        evidence.research_payload = payload
        db.commit()
        detail = asyncio.run(kifu.get_kifu_album(_request(), album.id, lang="fr", db=db))
        assert detail.display_event == "Nom du tournoi non vérifié"
        assert _list(db, "1er Honinbo", "cn").total == 0
        assert identity.strict_slot_approvals(db, [album], "fr")[album.id][2] is None
        coverage = coverage_report(engine, build_inventory(engine), languages=("fr",))
        assert coverage["languages"]["fr"]["approved"] == 0
    finally:
        db.close()
        engine.dispose()


def test_composed_direct_event_scope_cannot_approve_a_selected_event_slot():
    engine, db = _db()
    try:
        series, raw, albums = _reviewed_composition(db)
        album = albums[0]
        selected = {album.id: (raw.raw_value, series.id)}
        assert identity.strict_slot_approvals(db, [album], "cn", selected_events=selected)[album.id][2] is None
        maps = identity.strict_display_maps(db, [album], "cn", selected_events=selected)
        assert (
            identity.resolve_strict_display(
                album,
                "cn",
                maps[0],
                maps[1],
                maps[2],
                maps[4],
                maps[5],
                selected_events=selected,
            )[2]
            == "赛事名称待核实"
        )
    finally:
        db.close()
        engine.dispose()


@pytest.mark.parametrize("strict", [False, True])
def test_translated_event_title_is_progressive_fallback_but_exact_raw_stays_first(monkeypatch, strict):
    monkeypatch.setenv("KIFU_STRICT_NAMES", "1" if strict else "0")
    engine, db = _db()
    raw_spelling = "48届韩国名人战决赛3番棋2局0-1"
    display = "한국 명인전"
    try:
        tournament = KifuEvent(canonical_name="韩国名人战")
        db.add(tournament)
        db.flush()
        core = _evidence(db, "event", tournament.id, "ko", display, decision="translated")
        core.generation_rule_version = "event-title-translation-v1"
        db.add(KifuEventName(
            event_id=tournament.id, lang="ko", display_name=display, status="verified",
            decision_kind="translated", generation_rule_version=core.generation_rule_version,
            revision=1, evidence_id=core.id,
        ))
        album = KifuAlbum(
            player_black="Black", player_white="White", event=raw_spelling, event_id=tournament.id,
            sgf_content="(;B[aa])", source_path="progressive-event-title.sgf",
        )
        db.add(album)
        db.commit()

        result = _list(db, display, "ko")
        assert result.total == 1 and [item.id for item in result.items] == [album.id]
        expected = "대회 이름 미확인" if strict else display
        assert result.items[0].display_event == expected
        assert result.items[0].event == raw_spelling
        assert asyncio.run(kifu.get_kifu_album(_request(), album.id, lang="ko", db=db)).display_event == expected
        assert identity.strict_slot_approvals(db, [album], "ko")[album.id][2] is None

        raw_display = "제48기 한국 명인전 결승 3번기 제2국 (0-1)"
        raw = KifuRawEventValue(raw_value=raw_spelling, category="game_description", review_status="approved")
        db.add(raw)
        db.flush()
        proof = _evidence(db, "raw_event", raw.id, "ko", raw_display)
        db.add(KifuRawEventName(
            raw_event_id=raw.id, lang="ko", display_name=raw_display, status="verified",
            decision_kind="conventional", generation_rule_version="test-v1", revision=1, evidence_id=proof.id,
        ))
        db.commit()
        assert _list(db, display, "ko").items[0].display_event == raw_display
        assert identity.strict_slot_approvals(db, [album], "ko")[album.id][2] == ("conventional", proof.id)
    finally:
        db.close()
        engine.dispose()


@pytest.mark.parametrize("raw_spelling,obscured", [
    ("JapanPromotionTournament,1934,Fall", False), ("GNUGo3.8", True),
])
def test_progressive_event_title_keeps_formal_and_obscured_guards(raw_spelling, obscured):
    album = SimpleNamespace(id=1, event=raw_spelling, event_id=3, black_player_id=None,
                            white_player_id=None, player_black="Black", player_white="White")
    resolved = identity.resolve_strict_display(
        album, "en", {}, {3: "Approved event title"}, {3: "Oteai"}, {}, {},
        obscured_event_ids={1} if obscured else set(), fallback_names=("Black", "White", raw_spelling),
    )
    assert resolved[2] == raw_spelling


def test_normal_mode_progressively_displays_and_searches_reviewed_raw_names(monkeypatch):
    _preserve_stored_locale(monkeypatch)
    monkeypatch.delenv("KIFU_STRICT_NAMES", raising=False)
    engine, db = _db()
    try:
        raw = KifuRawPlayerValue(raw_value="Reviewed A", category="readable", review_status="approved")
        event_raw = KifuRawEventValue(raw_value="Reviewed Match", category="game_description", review_status="approved")
        db.add_all([raw, event_raw])
        db.flush()
        for owner, owner_id, model, display in (
            ("raw_player", raw.id, KifuRawPlayerName, "Игрок А"),
            ("raw_event", event_raw.id, KifuRawEventName, "Матч А"),
        ):
            evidence = _evidence(db, owner, owner_id, "ru", display)
            db.add(model(**{f"{owner}_id": owner_id}, lang="ru", display_name=display,
                         status="verified", decision_kind="conventional", generation_rule_version="test-v1",
                         revision=1, evidence_id=evidence.id))
        approved = KifuAlbum(player_black="Reviewed A", player_white="Untouched B", event="Reviewed Match",
                             sgf_content="(;B[aa])", source_path="approved.sgf")
        untouched = KifuAlbum(player_black="Untouched A", player_white="Untouched B", event="Other Match",
                              sgf_content="(;B[bb])", source_path="untouched.sgf")
        db.add_all([approved, untouched])
        db.commit()
        result = {item.id: item for item in _list(db, lang="ru").items}
        assert result[approved.id].display_player_black == "Игрок А"
        assert result[approved.id].display_event == "Матч А"
        assert result[untouched.id].display_player_black == "Untouched A"
        detail = asyncio.run(kifu.get_kifu_album(_request(), approved.id, lang="ru", db=db))
        assert detail.display_event == "Матч А"
        for query in ("Игрок А", "Матч А"):
            assert [item.id for item in _list(db, query, "cn").items] == [approved.id]
        # A verified row without its exact approved evidence must never become an approved overlay.
        evidence.review_status = "pending"
        db.commit()
        assert _list(db, "Матч А").total == 0
        assert asyncio.run(kifu.get_kifu_album(_request(), approved.id, lang="ru", db=db)).display_event != "Матч А"
    finally:
        db.close()
        engine.dispose()


def test_normal_mode_composed_names_keep_exact_reviewed_album_scope(monkeypatch):
    _preserve_stored_locale(monkeypatch)
    monkeypatch.delenv("KIFU_STRICT_NAMES", raising=False)
    engine, db = _db()
    try:
        series, raw, albums = _reviewed_composition(db)
        outside = KifuAlbum(player_black="Black", player_white="White", event=raw.raw_value,
                            event_id=series.id, sgf_content="(;B[bb])", source_path="outside-normal.sgf")
        db.add(outside)
        db.commit()
        result = {item.id: item for item in _list(db, lang="fr").items}
        assert result[albums[0].id].display_event == "1er Honinbo"
        assert result[outside.id].display_event != "1er Honinbo"
        assert [item.id for item in _list(db, "1er Honinbo", "cn").items] == [albums[0].id]
        name = db.query(KifuRawEventName).filter_by(lang="fr").one()
        name.evidence_id = db.query(KifuEventName).filter_by(lang="fr").one().evidence_id
        db.commit()
        assert _list(db, "1er Honinbo", "cn").total == 0
        detail = asyncio.run(kifu.get_kifu_album(_request(), albums[0].id, lang="fr", db=db))
        assert detail.display_event != "1er Honinbo"
        assert detail.display_event != "Nom du tournoi non vérifié"
    finally:
        db.close()
        engine.dispose()


def test_normal_mode_does_not_fallback_to_revoked_canonical_name(monkeypatch):
    _preserve_stored_locale(monkeypatch)
    monkeypatch.delenv("KIFU_STRICT_NAMES", raising=False)
    engine, db = _db()
    try:
        player = KifuPlayer(canonical_name="Original Player")
        db.add(player)
        db.flush()
        evidence = _evidence(db, "player", player.id, "ru", "Новый игрок")
        db.add(KifuPlayerName(
            player_id=player.id, lang="ru", display_name="Новый игрок", status="verified",
            decision_kind="conventional", generation_rule_version="test-v1", revision=1,
            evidence_id=evidence.id,
        ))
        album = KifuAlbum(
            player_black="Original Player", player_white="Other Player", black_player_id=player.id,
            event="", sgf_content="(;B[aa])", source_path="revoked-canonical.sgf",
        )
        db.add(album)
        db.commit()
        assert asyncio.run(kifu.get_kifu_album(_request(), album.id, lang="ru", db=db)).display_player_black == "Новый игрок"
        evidence.review_status = "pending"
        db.commit()
        detail = asyncio.run(kifu.get_kifu_album(_request(), album.id, lang="ru", db=db))
        assert detail.display_player_black == "Original Player"
        assert _list(db, "Новый игрок", "ru").total == 0
    finally:
        db.close()
        engine.dispose()
