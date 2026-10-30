"""The ES projection preserves existing qualification and finite-slot decisions."""

import json

import pytest
from sqlalchemy import event

from katrain.web.core.models_db import (
    KifuAlbum,
    KifuAlbumSource,
    KifuEvent,
    KifuEventName,
    KifuPlayer,
    KifuPlayerAlias,
    KifuPlayerName,
    KifuRawPlayerName,
    KifuRawPlayerValue,
    KifuSource,
)
from tests.web_ui.test_kifu_library_search import _name, _player
from tests.web_ui.test_kifu_name_api import _db


@pytest.fixture
def db():
    engine, session = _db()
    yield session
    session.close()
    engine.dispose()


def album(db, **values):
    count = db.query(KifuAlbum).count()
    row = KifuAlbum(player_black="Black", player_white="White", sgf_content="(;)", source_path=f"{count}.sgf")
    for key, value in values.items():
        setattr(row, key, value)
    db.add(row)
    db.commit()
    return row


def projected(db, records, strict=True):
    from katrain.web.kifu.search_projection import build_projection_context, project_album_batch

    context = build_projection_context(db, strict)
    return context, [doc["_source"] for doc in project_album_batch(context, records)]


def classify(context, q):
    from katrain.web.kifu.search_documents import term_document_id

    documents = {doc["_id"]: doc["_source"] for doc in context.classification_documents()}
    return documents[term_document_id(q)]["classification"]


def test_album_projection_keeps_source_once_five_names_and_partial_dates(db):
    player = _player(db)
    for lang, display in (
        ("cn", "王星昊"),
        ("tw", "王星昊"),
        ("en", "Wang Xinghao"),
        ("jp", "王星昊"),
        ("ko", "왕싱하오"),
    ):
        _name(db, "player", player, KifuPlayerName, display=display, lang=lang)
    row = album(db, black_player_id=player.id, date_sort="1926-00-00", date_played="1926", round_name="Final")
    source = KifuSource(source_key="gogod")
    db.add(source)
    db.flush()
    db.add(KifuAlbumSource(album_id=row.id, source_id=source.id, origin_path="book.sgf", match_method="exact"))
    db.commit()
    _, docs = projected(db, [row])
    doc = docs[0]
    assert doc["date_sort"] == "1926-00-00" and doc["list_visible"] is True
    assert set(doc["display"]) == {"cn", "tw", "en", "jp", "ko"}
    assert doc["display"]["ko"]["player_black"] == "왕싱하오"
    assert doc["metadata"]["sources"] == ["gogod"]
    assert "sources" not in doc["display"]["en"]
    assert "sgf_content" not in json.dumps(doc) and "source_path" not in doc["metadata"]
    from katrain.web.kifu.search_projection import display_for_language

    assert display_for_language(doc, "ru")["player_black"] == "Wang Xinghao"
    assert display_for_language(doc, "ru")["round_name"] == "Финал"


def test_exact_zero_game_classification_is_not_generic_and_black_white_are_equal(db):
    player = _player(db)
    _name(db, "player", player, KifuPlayerName)
    row = album(db, white_player_id=player.id, list_hidden_reason="review")
    context, docs = projected(db, [row])
    classification = classify(context, "王星昊")
    assert classification["mode"] == "exact_player"
    assert classification["player_ids"] == [player.id]
    assert docs[0]["list_visible"] is False
    from katrain.web.kifu.search_terms import compile_query

    query = compile_query(classification, "王星昊", None)
    encoded = json.dumps(query)
    assert '"black_player_id"' in encoded and '"white_player_id"' in encoded
    assert '"search_text"' not in encoded and '"player_black_lower"' not in encoded
    assert '"match"' not in encoded
    assert query["sort"] == [{"date_sort": {"order": "desc", "missing": "_last"}}, {"id": "desc"}]


def test_verified_only_name_never_becomes_public_or_approved_display(db):
    player = _player(db)
    db.add(KifuPlayerName(player_id=player.id, lang="cn", display_name="冒名", status="verified"))
    db.commit()
    row = album(db, black_player_id=player.id, player_black="Unverified A")
    context, docs = projected(db, [row])
    assert docs[0]["display"]["cn"]["player_black"] == "棋手姓名待核实"
    from katrain.web.kifu.search_documents import public_player_document_id

    by_id = {d["_id"]: d["_source"] for d in context.classification_documents()}
    assert by_id[public_player_document_id(player.id)]["classification"]["public"] is False
    from katrain.web.kifu.search_terms import compile_query

    compiled = compile_query({"public": False}, None, player.id)
    assert "match_none" in json.dumps(compiled)


def test_exact_term_encoding_does_not_fold_width_or_sharp_s(db):
    player = _player(db)
    _name(db, "player", player, KifuPlayerName, display="Straße", lang="en")
    context, _ = projected(db, [])
    from katrain.web.kifu.search_documents import term_document_id

    assert term_document_id("Straße") == term_document_id("STRAßE")
    assert term_document_id("Straße") != term_document_id("STRASSE")
    assert term_document_id("Ａ") != term_document_id("A")
    assert classify(context, "Straße")["mode"] == "exact_player"


def test_raw_player_ids_only_apply_to_unlinked_exact_slots(db):
    owner = KifuRawPlayerValue(raw_value="Unlinked", category="readable", review_status="approved")
    db.add(owner)
    db.flush()
    name = _name(db, "raw_player", owner, KifuRawPlayerName, display="原始棋手")
    linked = _player(db)
    a = album(db, player_black="Unlinked")
    b = album(db, player_black="Unlinked", black_player_id=linked.id)
    context, docs = projected(db, [a, b])
    assert docs[0]["raw_player_name_ids"] == [name.id]
    assert docs[1]["raw_player_name_ids"] == []
    assert classify(context, "原始棋手")["raw_player_name_ids"] == [name.id]


def test_unapproved_same_name_collision_cannot_union_owner_ids(db):
    for _ in range(2):
        player = _player(db)
        _name(db, "player", player, KifuPlayerName, display="同名")
    context, _ = projected(db, [])
    assert classify(context, "同名")["mode"] == "generic"
    assert classify(context, "同名")["player_ids"] == []


def test_generic_historical_hints_are_not_applied_to_exact_or_strict_queries():
    from katrain.web.kifu.search_terms import compile_query

    generic = json.dumps(compile_query({"mode": "generic", "strict": False}, "本因坊秀策", None))
    assert "shusaku" in generic and "yasuda eisai" in generic
    strict = json.dumps(compile_query({"mode": "generic", "strict": True}, "本因坊秀策", None))
    exact = json.dumps(compile_query({"mode": "exact_player", "player_ids": [3]}, "本因坊秀策", None))
    assert "shusaku" not in strict and "shusaku" not in exact
    assert '"constant_score"' in generic and '"_score"' in generic


def test_generic_wildcards_are_literal_and_all_queries_filter_album_visibility():
    from katrain.web.kifu.search_terms import compile_query

    for classification, q, player_id in (
        ({}, None, None),
        ({"public": True}, None, 3),
        ({"mode": "generic"}, r"A*?\\x", None),
    ):
        result = compile_query(classification, q, player_id)
        assert {"term": {"doc_kind": "album"}} in result["query"]["bool"]["filter"]
        assert {"term": {"list_visible": True}} in result["query"]["bool"]["filter"]
    encoded = json.dumps(result)
    assert r"a\\*\\?\\\\\\\\x" in encoded


def test_context_qualifies_once_and_batch_reads_no_prepared_relations(db, monkeypatch):
    from katrain.web.kifu import identity
    from katrain.web.kifu.search_projection import build_projection_context, project_album_batch

    player = _player(db)
    _name(db, "player", player, KifuPlayerName)
    row = album(db, black_player_id=player.id)
    calls = []
    original = identity._qualified_name_rows

    def qualified(*args, **kwargs):
        calls.append(args[2].__name__)
        return original(*args, **kwargs)

    monkeypatch.setattr(identity, "_qualified_name_rows", qualified)
    statements = []
    event.listen(db.bind, "before_cursor_execute", lambda *args: statements.append(args[2]))
    context = build_projection_context(db, True)
    before = list(calls)
    project_album_batch(context, [row])
    project_album_batch(context, [row])
    assert calls == before
    assert calls.count("KifuPlayerName") == 1 and calls.count("KifuEventName") == 1
    assert not any("kifu_prepared" in sql.lower() or "kifu_search_" in sql.lower() for sql in statements)


def test_event_words_are_five_language_or_of_per_field_and_only_in_generic():
    from katrain.web.kifu.search_terms import compile_query

    body = compile_query({"mode": "generic"}, "天元戦 挑戦手合", None)

    def matches(value):
        if isinstance(value, dict):
            yield from value.get("match", {}).items()
            for child in value.values():
                yield from matches(child)
        elif isinstance(value, list):
            for child in value:
                yield from matches(child)

    clauses = dict(matches(body))
    assert set(clauses) == {f"display.{lang}.event.words" for lang in ("cn", "tw", "en", "jp", "ko")}
    assert all(
        options == {"query": "天元戦 挑戦手合", "operator": "and", "zero_terms_query": "none"}
        for options in clauses.values()
    )
    for mode, fields in (
        ("exact_player", {"player_ids": [1]}),
        ("exact_event", {"event_ids": [2]}),
        ("exact_raw_event", {"raw_event_name_ids": [3]}),
    ):
        assert not dict(matches(compile_query({"mode": mode, **fields}, "天元戦 挑戦手合", None)))


def test_exact_and_alias_id_namespaces_never_collide_and_long_names_fit_es():
    from katrain.web.kifu.search_documents import alias_document_id, term_document_id

    assert alias_document_id("Player") != term_document_id("alias:player")
    assert len(term_document_id("名" * 512).encode()) <= 512


def test_classification_actions_delete_revoked_old_keys(db):
    from katrain.web.kifu.search_documents import alias_document_id, term_document_id

    context, _ = projected(db, [])
    actions = {value["_id"]: value for value in context.classification_actions(set(), {"Old Name"})}
    assert actions[term_document_id("Old Name")] == {"_op_type": "delete", "_id": term_document_id("Old Name")}
    assert actions[alias_document_id("Old Name")] == {"_op_type": "delete", "_id": alias_document_id("Old Name")}


def test_progressive_display_and_provisional_union_keep_source_semantics(db, monkeypatch):
    from katrain.web.kifu import first_pass_cn

    monkeypatch.setattr(first_pass_cn, "_hints", lambda: ({"Original A": "提示名"}, {("Cup", None): "提示赛事"}, {}))
    row = album(db, player_black="Original A", event="Cup")
    context, docs = projected(db, [row], strict=False)
    assert docs[0]["display"]["cn"]["player_black"] == "提示名"
    assert docs[0]["display"]["en"]["player_black"] == "Original A"
    assert docs[0]["provisional_player_names"] == ["提示名"]
    assert docs[0]["provisional_event_names"] == ["提示赛事"]


def test_finite_context_qualifies_page_owners_and_exact_cross_domain_collisions_only(db, monkeypatch):
    from katrain.web.kifu import identity
    from katrain.web.kifu.search_projection import build_projection_context, project_album_batch

    player = _player(db)
    opponent = _player(db)
    unrelated = _player(db)
    _name(db, "player", player, KifuPlayerName, display="Shared")
    _name(db, "player", opponent, KifuPlayerName, display="Opponent")
    _name(db, "player", unrelated, KifuPlayerName, display="Unrelated")
    tournament = KifuEvent(canonical_name="Cup")
    db.add(tournament)
    db.flush()
    _name(db, "event", tournament, KifuEventName, display="Shared")
    row = album(db, black_player_id=player.id, white_player_id=opponent.id)
    calls = []
    original = identity._qualified_name_rows

    def qualified(*args, **kwargs):
        values = original(*args, **kwargs)
        calls.extend(name.display_name for name, *_ in values)
        return values

    monkeypatch.setattr(identity, "_qualified_name_rows", qualified)
    context = build_projection_context(db, True, records=[row], owner_refs={("player", player.id)}, terms={"Shared"})
    doc = project_album_batch(context, [row])[0]["_source"]
    assert "Unrelated" not in calls
    assert doc["display"]["cn"]["player_white"] == "Opponent"
    assert classify(context, "Shared")["mode"] == "generic"


def test_legacy_multiple_alias_owners_remain_generic_not_authorized_shared_group():
    from katrain.web.kifu.search_terms import merge_classifications

    merged = merge_classifications({}, {"strict": False, "player_ids": [1, 2], "event_ids": []})
    assert merged["mode"] == "generic"


def test_authorized_shared_player_ids_are_preserved_without_counting_games():
    from types import SimpleNamespace
    from katrain.web.kifu.search_terms import classify_qualified_names

    rows = [(SimpleNamespace(id=value, player_id=value), None) for value in (4, 7)]
    result = classify_qualified_names(rows, [], [], [], shared_player_ids={4, 7})
    assert result["mode"] == "shared_players" and result["player_ids"] == [4, 7]
    assert classify_qualified_names(rows, [], [], [], shared_player_ids={4, 8})["player_ids"] == []


def test_reviewed_selected_event_projection_rejects_sgf_drift(db):
    from katrain.web.core.models_db import KifuRawEventName, KifuRawEventValue
    from katrain.web.kifu.search_projection import build_projection_context, project_album_batch
    from tests.web_ui._kifu_selection_helpers import apply_reviewed_selection

    raw_text = "第5届韩国最强棋士战预选"
    raw = KifuRawEventValue(raw_value=raw_text, category="game_description", review_status="approved")
    db.add(raw)
    db.flush()
    name = _name(db, "raw_event", raw, KifuRawEventName, display="韩国最强棋士战预选")
    row = album(
        db,
        event="GNUGo3.8",
        source="https://19x19.com",
        source_path="data/kifu-album/19x19/selected.sgf",
        sgf_content=f"(;FF[4]SZ[19]SO[https://19x19.com]GN[GNUGo3.8]GN[{raw_text}]GC[{raw_text} | 194手];B[aa])",
    )
    apply_reviewed_selection(db.bind, row.id)
    context = build_projection_context(db, True, records=[row], terms={"韩国最强棋士战预选"})
    source = project_album_batch(context, [row])[0]["_source"]
    assert source["selected_event_name_ids"] == [name.id]
    assert source["selected_event_raw_lower"] == raw_text.lower()
    assert source["display"]["cn"]["event"] == "韩国最强棋士战预选"
    row.sgf_content = row.sgf_content.replace(";B[aa]", ";B[bb]")
    db.commit()
    drifted = project_album_batch(build_projection_context(db, True), [row])[0]["_source"]
    assert drifted["selected_event_name_ids"] == []
    assert "selected_event_raw_lower" not in drifted
    assert drifted["display"]["cn"]["event"] == "赛事名称待核实"


def test_real_reviewed_raw_player_finite_scope_is_reused_for_five_languages(tmp_path, monkeypatch):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from katrain.web.core.models_db import Base
    from katrain.web.kifu.name_batch import apply_bundle
    from katrain.web.kifu.search_projection import build_projection_context, project_album_batch
    from tests.web_ui.test_kifu_name_first_pass import bound_raw_player_bundle, db_registry

    engine = create_engine(f"sqlite:///{tmp_path / 'raw.db'}")
    Base.metadata.create_all(engine)
    with engine.begin() as conn:
        conn.execute(KifuPlayer.__table__.insert().values(id=17, canonical_name="吴清源"))
        conn.execute(
            KifuAlbum.__table__.insert().values(
                id=11,
                black_player_id=17,
                player_black="Go Seigen",
                player_white="Other",
                sgf_content="(;)",
                source_path="one.sgf",
            )
        )
    try:
        inv, bundle, research = bound_raw_player_bundle(engine, five_languages=True)
        apply_bundle(engine, bundle, db_registry(), inv, research)
        with Session(engine) as session:
            records = session.query(KifuAlbum).order_by(KifuAlbum.id).all()
            context = build_projection_context(session, True, records=records)
            docs = {doc["_source"]["id"]: doc["_source"] for doc in project_album_batch(context, records)}
            assert len(docs[12]["raw_player_name_ids"]) == 5
            assert len(docs[15]["raw_player_name_ids"]) == 5
            assert docs[13]["raw_player_name_ids"] == [] and docs[14]["raw_player_name_ids"] == []
            assert docs[12]["display"]["ko"]["player_black"] == "이원혁"
            assert docs[15]["display"]["en"]["player_white"] == "Lee Wonhyuk"
    finally:
        engine.dispose()


def test_qualified_raw_player_only_generic_branch_does_not_analyze_event_words():
    from types import SimpleNamespace
    from katrain.web.kifu.search_terms import classify_qualified_names, compile_query

    name = SimpleNamespace(id=4, raw_player_id=3, decision_kind="conventional", generation_rule_version="test-v1")
    classification = classify_qualified_names([], [], [(name, "Original", None)], [])
    assert classification["mode"] == "generic"
    assert '"match"' not in json.dumps(compile_query(classification, "Complete Name", None))


def test_provisional_event_cap_is_based_on_raw_definitions_and_is_case_sensitive(db, monkeypatch):
    from katrain.web.kifu import first_pass_cn
    from katrain.web.kifu.search_terms import compile_query

    events = {(f"Raw {number}", None): "Common Cup Stage" for number in range(201)}
    events[("Lower", None)] = "lower cup"
    monkeypatch.setattr(first_pass_cn, "_hints", lambda: ({}, events, {}))
    context, _ = projected(db, [], strict=False)
    classification = classify(context, "Cup")
    assert "Cup" in classification["provisional_event_disabled_queries"]
    assert "cup" not in classification["provisional_event_disabled_queries"]
    body = compile_query({**classification, "include_provisional": True}, "Cup", None)
    assert "provisional_event_names" not in json.dumps(body)
    assert "provisional_event_names" in json.dumps(
        compile_query({**classification, "include_provisional": True}, "cup", None)
    )


def test_exact_event_retains_existing_cn_hint_union_without_new_event_analysis():
    from katrain.web.kifu.search_terms import compile_query

    body = compile_query(
        {"mode": "exact_event", "event_ids": [2], "strict": False, "include_provisional": True}, "Cup", None
    )
    assert "provisional_event_names" in json.dumps(body)
    assert '"match"' not in json.dumps(body)


def test_exact_selected_literal_branch_is_independent_of_other_album_batches():
    from katrain.web.kifu.search_terms import compile_query

    body = compile_query({"mode": "exact_player", "player_ids": [4]}, "王星昊", None)
    assert "selected_event_raw_lower" in json.dumps(body)
    assert "search_text" not in json.dumps(body)


def test_generated_tw_supplement_does_not_create_normalized_alias_equivalence(monkeypatch):
    from sqlalchemy.orm import Session
    from katrain.web.kifu.name_batch import apply_bundle
    from katrain.web.kifu.search_documents import alias_document_id
    from tests.web_ui.test_kifu_name_orthographic import fixture
    from tests.web_ui.test_kifu_name_transliteration import registry

    engine, bundle, research, inventory = fixture()
    try:
        apply_bundle(engine, bundle, registry(), inventory, research)
        with Session(engine) as db:
            context, _ = projected(db, [], strict=False)
            display = bundle["candidates"][0]["display_name"]
            docs = {entry["_id"]: entry["_source"] for entry in context.classification_documents()}
            assert alias_document_id(display) not in docs
    finally:
        engine.dispose()


def test_empty_legacy_name_keeps_original_progressive_source_fallback(db, monkeypatch):
    from katrain.web.kifu import first_pass_cn

    monkeypatch.setattr(first_pass_cn, "_hints", lambda: ({}, {}, {}))
    player = KifuPlayer(canonical_name="王星昊")
    tournament = KifuEvent(canonical_name="Canonical Cup")
    db.add_all([player, tournament])
    db.flush()
    db.add_all(
        [
            KifuPlayerName(player_id=player.id, lang="cn", display_name="", status="verified"),
            KifuEventName(event_id=tournament.id, lang="cn", display_name="", status="verified"),
        ]
    )
    db.commit()
    row = album(db, player_black="Source Player", black_player_id=player.id, event="Raw Cup", event_id=tournament.id)
    _, docs = projected(db, [row], strict=False)
    assert docs[0]["display"]["cn"]["player_black"] == "Source Player"
    assert docs[0]["display"]["cn"]["event"] == "Raw Cup"
