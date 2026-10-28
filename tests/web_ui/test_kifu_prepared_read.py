"""Ready reads consume prepared decisions, preserving the public library contract."""

import asyncio
from hashlib import sha256
import importlib
from threading import Event

from fastapi import FastAPI
import httpx
import pytest
from sqlalchemy import delete, event, select, text, update
from sqlalchemy.orm import Session, sessionmaker

from katrain.cron.kifu_parameters import resolve_parameters
from katrain.web.api.v1.endpoints import kifu
from katrain.web.core import models_db as business
from katrain.web.kifu import prepared_models as prepared
from katrain.web.kifu.prepared_migration import apply_migration
from katrain.web.kifu.prepared_read import require_ready
from tests.web_ui.test_kifu_name_api import _evidence, _request
from tests.web_ui.test_kifu_name_batch import engine  # noqa: F401
from tests.web_ui.test_kifu_rank_snapshots_api import album as ranked_album
from tests.web_ui.test_kifu_prepare_search import prepare_pg_engine  # noqa: F401


@pytest.fixture
def catalog(engine, monkeypatch):
    """Extend the existing reviewed-name and frozen-rank fixtures with a small page."""
    monkeypatch.setenv("KIFU_STRICT_NAMES", "1")
    with Session(engine) as db:
        for lang, display in (
            ("cn", "吴清源"),
            ("tw", "吳清源"),
            ("jp", "呉清源"),
            ("ko", "우칭위안"),
            ("en", "Go Seigen"),
        ):
            evidence = _evidence(db, "player", 17, lang, display)
            db.add(
                business.KifuPlayerName(
                    player_id=17,
                    lang=lang,
                    display_name=display,
                    status="verified",
                    decision_kind="conventional",
                    generation_rule_version="test-v1",
                    revision=1,
                    evidence_id=evidence.id,
                )
            )
        first = db.get(business.KifuAlbum, 11)
        first.sgf_content = "(;SZ[19]RU[Japanese]KM[6.5];B[aa])"
        first.date_sort = "2026-02-03"
        first.round_name = "Final"
        first.move_count = 1
        first.search_text = "archive 2026"
        db.add_all(
            [
                business.KifuAlbum(
                    id=12,
                    player_black="Other",
                    player_white="Go Seigen",
                    white_player_id=17,
                    sgf_content="(;SZ[19]RU[Japanese]KM[6.5];B[bb])",
                    source_path="two.sgf",
                    move_count=1,
                    date_sort="2026-02-03",
                    round_name="Final",
                    search_text="archive 2026",
                ),
                business.KifuAlbum(
                    id=13,
                    player_black="Mystery",
                    player_white="Unknown",
                    event="Cup",
                    sgf_content="(;B[cc])",
                    source_path="undated.sgf",
                    date_sort=None,
                    search_text="undated",
                ),
                business.KifuAlbum(
                    id=14,
                    player_black="Hidden",
                    player_white="White",
                    black_player_id=17,
                    sgf_content="(;B[dd])",
                    source_path="hidden.sgf",
                    list_hidden_reason="review",
                ),
                business.KifuAlbum(
                    id=15,
                    player_black=first.player_black,
                    player_white=first.player_white,
                    black_player_id=17,
                    event=first.event,
                    sgf_content=first.sgf_content,
                    source_path="duplicate.sgf",
                    duplicate_of_id=11,
                    move_count=1,
                ),
            ]
        )
        source = business.KifuSource(source_key="CWI", display_name="CWI")
        db.add(source)
        db.flush()
        db.add(
            business.KifuAlbumSource(
                album_id=11, source_id=source.id, origin_path="one.sgf", match_method="source_path"
            )
        )
        for album_id, complete in ((11, True), (12, False)):
            record = db.get(business.KifuAlbum, album_id)
            parameters = resolve_parameters(record.sgf_content)
            job = business.KifuAnalysisJob(
                album_id=album_id,
                sgf_sha256=sha256(record.sgf_content.encode()).hexdigest(),
                model_sha256=kifu.KIFU_MODEL_SHA256,
                requested_visits=kifu.KIFU_VISITS,
                status="completed",
                total_moves=1,
                analyzed_moves=1,
                analysis_parameters=parameters,
            )
            db.add(job)
            db.flush()
            for number in (0, 1) if complete else (0,):
                db.add(
                    business.KifuAnalysisMove(
                        job_id=job.id,
                        move_number=number,
                        root_visits=kifu.KIFU_VISITS,
                        parameter_sha256=parameters["parameter_sha256"],
                    )
                )
        db.commit()
        ranked, _frozen = ranked_album(db)
        ranked_id = ranked.id
    return engine, ranked_id


def _prepare(engine):
    from katrain.web.kifu.prepare_search import prepare_all

    assert apply_migration(engine)["ok"]
    with engine.begin() as conn:
        prepare_all(conn)
        conn.execute(update(prepared.state).values(enabled=True))


def _forbid_online_proof(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("online proof")

    targets = {
        "katrain.web.kifu.identity": (
            "_qualified_name_rows",
            "entire_qualified_name_rows",
            "_entire_qualified_name_rows",
            "strict_matching_names",
            "matching_entity_ids",
            "live_event_selections",
            "strict_selected_event_search_ids",
            "strict_display_maps",
            "display_maps",
            "resolve_strict_display",
            "strict_slot_approvals",
            "_approved_raw_player_names",
            "_approved_raw_event_names",
            "strict_raw_player_search_clause",
            "strict_raw_event_search_clause",
            "obscured_program_event_ids",
        ),
        "katrain.web.api.v1.endpoints.kifu": (
            "strict_matching_names",
            "matching_entity_ids",
            "live_event_selections",
            "strict_selected_event_search_ids",
            "strict_display_maps",
            "display_maps",
            "resolve_strict_display",
            "_obscured_program_event_ids_loaded",
            "obscured_program_event_ids",
            "unique_exact_player_id",
            "public_player_id",
        ),
        "katrain.web.kifu.library_search": ("_qualified_name_rows", "matching_entity_ids"),
        "katrain.web.kifu.first_pass_cn": (
            "_hints",
            "search_raw_names",
            "valid_override_search_ids",
            "event_hints",
            "player_name",
        ),
        "katrain.web.kifu.compiled_first_pass": ("compile_first_pass", "read_compiled_first_pass"),
        "katrain.web.kifu.name_first_pass": ("persisted_eligible", "raw_scope_rows_many", "raw_player_scope_live"),
        "katrain.web.kifu.name_orthographic": ("persisted_batch_bindings", "persisted_name_eligible"),
        "katrain.web.kifu.name_transliteration": ("persisted_batch_bindings", "persisted_name_eligible"),
        "katrain.web.kifu.event_selection": ("verified_selection_rows",),
    }
    for module_name, names in targets.items():
        module = importlib.import_module(module_name)
        for name in names:
            if hasattr(module, name):
                monkeypatch.setattr(module, name, forbidden)


def _app(engine):
    app = FastAPI()
    app.include_router(kifu.router, prefix="/api/v1/kifu")
    factory = sessionmaker(bind=engine)
    app.dependency_overrides[kifu.get_kifu_session_factory] = lambda: factory

    def get_db():
        with factory() as db:
            yield db

    app.dependency_overrides[kifu.get_db] = get_db
    return app


@pytest.mark.parametrize("strict", [False, True])
@pytest.mark.parametrize("lang", ["cn", "tw", "jp", "ko", "en", "ru"])
def test_ready_pages_and_details_equal_legacy_full_contract_without_any_online_proof(
    catalog, monkeypatch, strict, lang
):
    engine, ranked_id = catalog
    monkeypatch.setenv("KIFU_STRICT_NAMES", "1" if strict else "0")
    params = [{"lang": lang, "page": page, "page_size": 2} for page in (1, 2, 3)]
    params += [{"lang": lang, "q": "吴清源"}, {"lang": lang, "player_id": 17}, {"lang": lang, "q": "2026"}]
    _prepare(engine)
    with Session(engine) as db:
        expected_pages = [kifu.read_album_page_legacy(db, **value).model_dump() for value in params]
        expected_details = {
            album_id: kifu.read_album_detail_legacy(db, album_id, lang=lang).model_dump()
            for album_id in (11, 14, 15, ranked_id)
        }
        _forbid_online_proof(monkeypatch)
        pages = [kifu.read_album_page(db, **value) for value in params]
        assert [page.model_dump() for page in pages] == expected_pages
        assert [item.id for page in pages[:2] for item in page.items] == [ranked_id, 12, 11, 13]
        assert pages[0].preview.id == ranked_id
        assert pages[0].preview.display_black_rank == "7p"
        assert pages[1].items[0].has_analysis
        assert not pages[0].items[1].has_analysis
        assert pages[1].items[0].sources == ["CWI"]
        for album_id, expected in expected_details.items():
            detail = asyncio.run(kifu.get_kifu_album(_request(), album_id, lang=lang, db=db))
            assert detail.model_dump() == expected
        if lang == "ru":
            assert pages[1].items[0].display_round_name == "Финал"
            assert pages[1].items[0].display_player_black == "Go Seigen"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "damage", ["not_ready", "coverage", "dirty", "policy", "missing_display", "invalid_display", "malformed_sources"]
)
async def test_enabled_incomplete_preparation_returns_503_instead_of_legacy_fallback(catalog, damage):
    engine, ranked_id = catalog
    _prepare(engine)
    with engine.begin() as conn:
        if damage == "not_ready":
            conn.execute(update(prepared.state).values(ready=False))
        elif damage == "coverage":
            conn.execute(update(prepared.state).values(initial_coverage_complete=False))
        elif damage == "dirty":
            conn.execute(prepared.dirty.insert().values(input_kind="kifu_players", input_key="17", reason="test"))
        elif damage == "policy":
            conn.execute(update(prepared.state).values(policy_signature="obsolete"))
        elif damage == "missing_display":
            conn.execute(delete(prepared.displays).where(prepared.displays.c.album_id == ranked_id))
        elif damage == "invalid_display":
            conn.execute(update(prepared.displays).where(prepared.displays.c.album_id == ranked_id).values(valid=False))
        else:
            conn.execute(
                update(prepared.displays)
                .where(prepared.displays.c.album_id == ranked_id)
                .values(strict_outputs={"sources": "invalid"})
            )
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=_app(engine)), base_url="http://test") as client:
        for path in ("/api/v1/kifu/albums", f"/api/v1/kifu/albums/{ranked_id}"):
            response = await client.get(path)
            assert response.status_code == 503
            assert response.json()["detail"]["code"] == "kifu_search_not_ready"


@pytest.mark.asyncio
async def test_ready_no_result_is_200_zero_and_missing_album_is_404_before_preparation_check(catalog, monkeypatch):
    engine, ranked_id = catalog
    _prepare(engine)
    _forbid_online_proof(monkeypatch)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=_app(engine)), base_url="http://test") as client:
        response = await client.get("/api/v1/kifu/albums?q=DOES_NOT_EXIST")
        assert response.status_code == 200
        assert response.json() == {"items": [], "total": 0, "page": 1, "page_size": 20, "preview": None}
        with engine.begin() as conn:
            conn.execute(update(prepared.state).values(ready=False))
        absent = await client.get("/api/v1/kifu/albums/999999")
        assert absent.status_code == 404
        present = await client.get(f"/api/v1/kifu/albums/{ranked_id}")
        assert present.status_code == 503
        assert present.json()["detail"]["code"] == "kifu_search_not_ready"


def test_explicit_disabled_state_keeps_the_legacy_reader(catalog):
    engine, _ranked_id = catalog
    with Session(engine) as db:
        expected = kifu.read_album_page(db).model_dump()
    assert apply_migration(engine)["ok"]
    with engine.begin() as conn:
        conn.execute(update(prepared.state).values(enabled=False, ready=False))
    with Session(engine) as db:
        assert kifu.read_album_page(db).model_dump() == expected


def test_ready_reads_current_bounded_rank_report_metadata_and_keep_content_binding(catalog, monkeypatch):
    engine, ranked_id = catalog
    _prepare(engine)
    with engine.begin() as conn:
        job_id = conn.scalar(select(business.KifuAnalysisJob.id).where(business.KifuAnalysisJob.album_id == 11))
        conn.execute(
            update(business.KifuAnalysisMove)
            .where(business.KifuAnalysisMove.job_id == job_id)
            .values(root_visits=kifu.KIFU_VISITS - 1)
        )
        conn.execute(
            update(business.KifuAlbumRankSnapshot)
            .where(business.KifuAlbumRankSnapshot.album_id == ranked_id, business.KifuAlbumRankSnapshot.side == "black")
            .values(snapshot_sha256="b" * 64)
        )
    _forbid_online_proof(monkeypatch)
    statements = []
    with Session(engine) as db:
        assert require_ready(db) is not None
        event.listen(engine, "before_cursor_execute", lambda _, __, sql, *args: statements.append(sql))
        page = kifu.read_album_page(db)
        by_id = {item.id: item for item in page.items}
        assert not by_id[11].has_analysis
        assert by_id[ranked_id].display_black_rank == ""
        assert by_id[ranked_id].black_rank_source is None
        assert page.preview.id == ranked_id and page.preview.black_rank_source is None
    album_pages = [sql for sql in statements if "sgf_content" in sql and "FROM kifu_albums" in sql]
    assert len(album_pages) == 1 and "LIMIT" in album_pages[0] and "OFFSET" in album_pages[0]
    projection = album_pages[0].split("FROM", 1)[0]
    assert not any(column in projection for column in ("created_at", "event_edition_id", "search_text"))
    assert not any(
        token in sql.lower()
        for sql in statements
        for token in (
            "research_payload",
            "reviewed_artifact",
            "kifu_name_changes",
            "kifu_name_research_evidence",
            "kifu_player_rank_history",
        )
    )


@pytest.mark.asyncio
async def test_readiness_exposes_actual_process_signature_and_db_gate_without_repurposing_health(catalog):
    from katrain.web.kifu.prepared_read import current_policy_signature

    engine, _ranked_id = catalog
    _prepare(engine)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=_app(engine)), base_url="http://test") as client:
        ready = await client.get("/api/v1/kifu/search-ready")
        assert ready.status_code == 200
        body = ready.json()
        assert body["kifu_search_ready"] is True
        assert body["runtime_policy_signature"] == body["policy_signature"] == current_policy_signature()
        assert body["enabled"] is body["ready"] is body["initial_coverage_complete"] is True
        assert set(body) == {
            "kifu_search_ready",
            "runtime_policy_signature",
            "policy_signature",
            "enabled",
            "ready",
            "initial_coverage_complete",
            "phase",
        }
        with engine.begin() as conn:
            conn.execute(update(prepared.state).values(policy_signature="obsolete"))
        stale = await client.get("/api/v1/kifu/search-ready")
        assert stale.status_code == 503
        assert stale.json()["runtime_policy_signature"] == current_policy_signature()
        assert stale.json()["policy_signature"] == "obsolete"
        assert stale.json()["kifu_search_ready"] is False


@pytest.mark.asyncio
@pytest.mark.parametrize("endpoint", ["list", "detail"])
async def test_board_proxy_preserves_prepared_not_ready_code_without_forwarding_arbitrary_error_text(endpoint):
    from unittest.mock import AsyncMock
    from fastapi import HTTPException
    from tests.web_ui.test_kifu_offline import _dispatcher, _request as remote_request

    request = httpx.Request("GET", "https://cloud.example/api/v1/kifu/albums")
    response = httpx.Response(
        503,
        request=request,
        json={
            "detail": {"code": "kifu_search_not_ready", "message": "PRIVATE_CLOUD_ERROR_TEXT"},
        },
    )
    remote = AsyncMock(side_effect=httpx.HTTPStatusError("unavailable", request=request, response=response))
    dispatcher = _dispatcher(**{"search" if endpoint == "list" else "get": remote})
    with pytest.raises(HTTPException) as error:
        if endpoint == "list":
            await kifu.list_kifu_albums(remote_request(dispatcher), q=None, page=1, page_size=20)
        else:
            await kifu.get_kifu_album(remote_request(dispatcher), 11, db=None)
    assert error.value.status_code == 503
    assert error.value.detail == {"code": "kifu_search_not_ready", "message": "Kifu search is not ready"}


def _compare_in_one_snapshot(engine, monkeypatch, queries, *, langs=("cn", "en")):
    _prepare(engine)
    with Session(engine) as db:
        for lang in langs:
            for query in queries:
                first = kifu.read_album_page_legacy(db, q=query, lang=lang, page_size=2)
                for page in range(1, (first.total + 1) // 2 + 2):
                    expected = (
                        first
                        if page == 1
                        else kifu.read_album_page_legacy(
                            db,
                            q=query,
                            lang=lang,
                            page_size=2,
                            page=page,
                        )
                    ).model_dump()
                    with monkeypatch.context() as reader_patch:
                        _forbid_online_proof(reader_patch)
                        actual = kifu.read_album_page(db, q=query, lang=lang, page_size=2, page=page).model_dump()
                    assert actual == expected, (query, lang, page)


@pytest.mark.parametrize("strict", [False, True])
def test_cross_domain_alias_unicode_exact_and_generic_search_keep_original_semantics(engine, monkeypatch, strict):
    from tests.web_ui.test_kifu_library_search import _name

    monkeypatch.setenv("KIFU_STRICT_NAMES", "1" if strict else "0")
    with Session(engine) as db:
        first = db.get(business.KifuPlayer, 17)
        others = [business.KifuPlayer(id=number, canonical_name=f"Person {number}") for number in (18, 19, 20)]
        tournament = business.KifuEvent(id=22, canonical_name="Raw formal")
        raw_player = business.KifuRawPlayerValue(
            id=23, raw_value="OneRaw", category="readable", review_status="approved"
        )
        raw_event = business.KifuRawEventValue(
            id=24, raw_value="OneEventRaw", category="readable", review_status="approved"
        )
        db.add_all([*others, tournament, raw_player, raw_event])
        db.flush()
        for kind, owner, model in (
            ("player", first, business.KifuPlayerName),
            ("event", tournament, business.KifuEventName),
            ("raw_player", raw_player, business.KifuRawPlayerName),
            ("raw_event", raw_event, business.KifuRawEventName),
        ):
            _name(db, kind, owner, model, display="OneToken")
        for owner, display in zip(others, ("Straße", "STRASSE", "ＡＢ")):
            _name(db, "player", owner, business.KifuPlayerName, display=display, lang="en")
        db.add_all(
            [
                business.KifuPlayerAlias(player_id=17, alias="Anchor alias", normalized_alias="anchor alias"),
                business.KifuEventAlias(event_id=22, alias="Anchor alias", normalized_alias="anchor alias"),
                business.KifuPlayerAlias(player_id=17, alias="Only alias", normalized_alias="only alias"),
            ]
        )
        values = [
            {"black_player_id": 17},
            {"event_id": 22, "event": "Raw formal"},
            {"player_black": "OneRaw"},
            {"event": "OneEventRaw"},
            {"player_black": "OneToken literal"},
            {"black_player_id": 18},
            {"black_player_id": 19},
            {"black_player_id": 20},
            {"player_black": "100% Real"},
            {"player_black": "underscore_name"},
            {"player_black": "HONINBO SHUSAKU"},
            {"search_text": "onetoken"},
        ]
        for number, value in enumerate(values, 12):
            db.add(
                business.KifuAlbum(
                    **(
                        {
                            "id": number,
                            "player_black": "X",
                            "player_white": "Y",
                            "sgf_content": "(;B[aa])",
                            "source_path": f"matrix-{number}.sgf",
                        }
                        | value
                    )
                )
            )
        db.commit()
    _compare_in_one_snapshot(
        engine,
        monkeypatch,
        (
            "OneToken",
            "Straße",
            "STRASSE",
            "strasse",
            "ＡＢ",
            "AB",
            "Anchor alias",
            "Only alias",
            "alias",
            "秀策",
            "本因坊秀策",
            "%",
            "_",
            "   ",
            "",
        ),
    )


@pytest.mark.parametrize("kind", ["raw_player", "raw_event", "shared_player", "linked_event", "composed"])
def test_finite_and_shared_names_match_full_legacy_scope_without_online_proof(engine, monkeypatch, kind):
    from katrain.web.kifu.name_batch import apply_bundle
    from tests.web_ui.test_kifu_name_api import _reviewed_composition
    from tests.web_ui.test_kifu_name_batch import registry
    from tests.web_ui.test_kifu_name_first_pass import (
        _share_raw_display,
        bound_raw_player_bundle,
        bound_shared_raw_event_bundle,
    )
    from tests.web_ui.test_kifu_prepare_search import _shared_player_bundle
    from tests.web_ui.test_kifu_raw_event_title_translation import (
        linked_reviewed_bundle,
        registry as raw_title_registry,
    )

    monkeypatch.setenv("KIFU_STRICT_NAMES", "1")
    if kind == "raw_player":
        inventory, bundle, research = bound_raw_player_bundle(engine, five_languages=True, second_raw=True)
        for candidate in bundle["candidates"]:
            if candidate["lang"] == "en":
                _share_raw_display(candidate)
        apply_bundle(engine, bundle, registry(), inventory, research)
        queries = ("Lee Wonhyuk", "李元赫", "이원혁", "李元赫九段")
    elif kind == "raw_event":
        inventory, bundle, research = bound_shared_raw_event_bundle(engine)
        apply_bundle(engine, bundle, registry(), inventory, research)
        queries = ("28th Honinbo Tournament", "28th Honinbo", "第28期本因坊战")
    elif kind == "shared_player":
        inventory, bundle, research = _shared_player_bundle(engine)
        apply_bundle(engine, bundle, registry(), inventory, research)
        queries = ("吴清源", "Other")
    elif kind == "linked_event":
        bundle, inventory, research = linked_reviewed_bundle(engine)
        apply_bundle(engine, bundle, raw_title_registry(), inventory, research)
        with Session(engine) as db:
            evidence = _evidence(db, "event", 19, "en", "28th Honinbo")
            db.add(
                business.KifuEventName(
                    event_id=19,
                    lang="en",
                    display_name="28th Honinbo",
                    status="verified",
                    decision_kind="conventional",
                    generation_rule_version="test-v1",
                    revision=1,
                    evidence_id=evidence.id,
                )
            )
            db.commit()
        queries = ("28th Honinbo", "Honinbo")
    else:
        with Session(engine) as db:
            series, raw, _albums = _reviewed_composition(db, count=2)
            db.add(
                business.KifuAlbum(
                    player_black="Black",
                    player_white="White",
                    event=raw.raw_value,
                    event_id=series.id,
                    sgf_content="(;B[aa])",
                    source_path="outside-composition.sgf",
                )
            )
            db.commit()
        queries = ("1er Honinbo", "第1届本因坊战", "Honinbo")
    _compare_in_one_snapshot(engine, monkeypatch, queries, langs=("cn", "en", "fr"))
    if kind == "raw_player":
        # One exact canonical identity can coexist with both reviewed raw scopes.
        with Session(engine) as db:
            evidence = _evidence(db, "player", 17, "en", "Lee Wonhyuk")
            db.add(
                business.KifuPlayerName(
                    player_id=17,
                    lang="en",
                    display_name="Lee Wonhyuk",
                    status="verified",
                    decision_kind="conventional",
                    generation_rule_version="test-v1",
                    revision=1,
                    evidence_id=evidence.id,
                )
            )
            db.commit()
        _compare_in_one_snapshot(engine, monkeypatch, ("Lee Wonhyuk",))
    if kind == "shared_player":
        from katrain.web.kifu.prepare_search import prepare_changed

        with engine.begin() as conn:
            # A/B remain eligible; a verified but unproved C revokes the exact
            # shared-token permission without making this a readiness failure.
            conn.execute(
                business.KifuPlayerName.__table__.insert().values(
                    player_id=19,
                    lang="cn",
                    display_name="吴清源",
                    status="verified",
                    decision_kind="generated",
                    generation_rule_version="user_authorized_first_pass_v1",
                    revision=1,
                )
            )
            prepare_changed(conn)
        _compare_in_one_snapshot(engine, monkeypatch, ("吴清源",))


@pytest.mark.parametrize("name_lang", ["en", "ru"])
def test_selected_event_exact_substring_and_case_keep_database_candidate_semantics(engine, monkeypatch, name_lang):
    from tests.web_ui._kifu_selection_helpers import apply_reviewed_selection

    monkeypatch.setenv("KIFU_STRICT_NAMES", "1")
    with Session(engine) as db:
        album = db.get(business.KifuAlbum, 11)
        album.source, album.source_path = "https://19x19.com", "data/kifu-album/19x19/one.sgf"
        album.sgf_content = "(;FF[4]SZ[19]SO[https://19x19.com]GN[GNUGo3.8]GN[Other]GC[Other | 1手])"
        db.get(business.KifuRawEventValue, 8).review_status = "approved"
        evidence = _evidence(db, "raw_event", 8, name_lang, "Another event")
        db.add(
            business.KifuRawEventName(
                raw_event_id=8,
                lang=name_lang,
                display_name="Another event",
                status="verified",
                decision_kind="conventional",
                generation_rule_version="test-v1",
                revision=1,
                evidence_id=evidence.id,
            )
        )
        db.commit()
    apply_reviewed_selection(engine, 11)
    _compare_in_one_snapshot(engine, monkeypatch, ("Another event", "Other", "the", "other", "OTHER", "%"))


def test_provisional_event_substring_keeps_original_python_case_semantics(engine, monkeypatch):
    from katrain.web.kifu import first_pass_cn

    monkeypatch.setenv("KIFU_STRICT_NAMES", "0")
    monkeypatch.setattr(first_pass_cn, "_hints", lambda: ({}, {("Raw Cup", None): "MixedCase Event"}, {}))
    with engine.begin() as conn:
        conn.execute(
            update(business.KifuAlbum)
            .where(business.KifuAlbum.id == 11)
            .values(
                event="Raw Cup",
                event_id=None,
                sgf_content="(;EV[Raw Cup])",
            )
        )
    _compare_in_one_snapshot(engine, monkeypatch, ("MixedCase", "mixedcase", "MIXEDCASE"))


@pytest.fixture
def reader_pg_engine(prepare_pg_engine):
    # The shared PG fixture creates only writer inputs. Page metadata stays real.
    business.Base.metadata.create_all(
        prepare_pg_engine,
        tables=[
            business.KifuPlayerRankHistory.__table__,
            business.KifuAlbumRankSnapshot.__table__,
            business.KifuAnalysisJob.__table__,
            business.KifuAnalysisMove.__table__,
        ],
    )
    return prepare_pg_engine


@pytest.mark.asyncio
async def test_pg_worker_count_and_page_share_repeatable_read_read_only_snapshot(reader_pg_engine, monkeypatch):
    engine = reader_pg_engine
    monkeypatch.setenv("KIFU_STRICT_NAMES", "1")
    with engine.begin() as conn:
        conn.execute(
            business.KifuAlbum.__table__.insert().values(
                id=12,
                player_black="Other",
                player_white="White",
                sgf_content="(;B[aa])",
                source_path="two.sgf",
            )
        )
    _prepare(engine)
    counted, release = Event(), Event()
    original_ready = kifu.require_ready
    observed = []

    def check_ready(db):
        observed.append(
            (
                db.scalar(text("SHOW transaction_isolation")),
                db.scalar(text("SHOW transaction_read_only")),
            )
        )
        db.connection().info["kifu_reader_snapshot_test"] = True
        return original_ready(db)

    def after_sql(conn, cursor, statement, parameters, context, executemany):
        if (
            conn.info.get("kifu_reader_snapshot_test")
            and not counted.is_set()
            and "count(kifu_albums.id)" in statement
            and "FROM kifu_albums" in statement
        ):
            counted.set()
            assert release.wait(5), "test did not release counted page"

    monkeypatch.setattr(kifu, "require_ready", check_ready)
    event.listen(engine, "after_cursor_execute", after_sql)
    request = None
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=_app(engine)), base_url="http://test") as client:
            request = asyncio.create_task(client.get("/api/v1/kifu/albums"))
            assert await asyncio.to_thread(counted.wait, 2)
            with engine.begin() as conn:
                conn.execute(
                    update(business.KifuAlbum).where(business.KifuAlbum.id == 12).values(list_hidden_reason="review")
                )
            release.set()
            first = await request
            assert first.status_code == 200
            assert first.json()["total"] == len(first.json()["items"]) == 2
            assert {item["id"] for item in first.json()["items"]} == {11, 12}
            assert (await client.get("/api/v1/kifu/albums")).status_code == 503
    finally:
        release.set()
        if request is not None:
            await request
        event.remove(engine, "after_cursor_execute", after_sql)
    assert observed and set(observed) == {("repeatable read", "on")}


@pytest.mark.asyncio
async def test_pg_state_candidates_and_display_remain_one_snapshot_across_committed_revoke(
    reader_pg_engine, monkeypatch
):
    from katrain.web.kifu.prepare_search import prepare_changed

    engine = reader_pg_engine
    monkeypatch.setenv("KIFU_STRICT_NAMES", "1")
    with Session(engine) as db:
        evidence = _evidence(db, "player", 17, "en", "Go Seigen")
        evidence_id = evidence.id
        db.add(
            business.KifuPlayerName(
                player_id=17,
                lang="en",
                display_name="Go Seigen",
                status="verified",
                decision_kind="conventional",
                generation_rule_version="test-v1",
                revision=1,
                evidence_id=evidence_id,
            )
        )
        db.commit()
    _prepare(engine)
    before_display, release = Event(), Event()
    original_displays = kifu.read_displays

    def read_displays(db, album_ids, lang):
        if not before_display.is_set():
            before_display.set()
            assert release.wait(5), "test did not release prepared display read"
        return original_displays(db, album_ids, lang)

    monkeypatch.setattr(kifu, "read_displays", read_displays)
    request = None
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=_app(engine)), base_url="http://test") as client:
            request = asyncio.create_task(client.get("/api/v1/kifu/albums?q=Go%20Seigen&lang=en"))
            assert await asyncio.to_thread(before_display.wait, 2)
            with engine.begin() as conn:
                conn.execute(
                    update(business.KifuNameResearchEvidence)
                    .where(business.KifuNameResearchEvidence.id == evidence_id)
                    .values(review_status="pending")
                )
                prepare_changed(conn)
            release.set()
            first = await request
            assert first.status_code == 200 and first.json()["total"] == 1
            assert first.json()["items"][0]["display_player_black"] == "Go Seigen"
            fresh = await client.get("/api/v1/kifu/albums?q=Go%20Seigen&lang=en")
            assert fresh.status_code == 200 and fresh.json()["total"] == 0
            all_current = await client.get("/api/v1/kifu/albums?lang=en")
            assert all_current.json()["items"][0]["display_player_black"] == "Player name unverified"
    finally:
        release.set()
        if request is not None:
            await request
