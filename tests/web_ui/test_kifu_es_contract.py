"""Complete list contract and the ES consistency boundary."""

from copy import deepcopy
from hashlib import sha256

from sqlalchemy import select, update
from sqlalchemy.orm import Session, sessionmaker
from katrain.cron.kifu_parameters import resolve_parameters
from katrain.web.core import models_db as business
from tests.web_ui.test_kifu_name_api import _evidence
from tests.web_ui.test_kifu_name_batch import engine  # noqa: F401
from tests.web_ui.test_kifu_rank_snapshots_api import album as ranked_album

import pytest
from fastapi import HTTPException

from katrain.web.api.v1.endpoints import kifu


class FakeSearch:
    def __init__(self, *, epoch=1, final_epoch=None, status="ready", hits=None, total=0, error=False):
        self.state = {"doc_kind": "sync_state", "schema_version": "kifu-search-v1", "strict_mode": False,
                      "status": status, "epoch": epoch, "target_index": "test-v1"}
        self.final_epoch = epoch if final_epoch is None else final_epoch
        self.hits, self.total, self.error = hits or [], total, error
        self.calls = []

    async def mget(self, ids, *, index=None):
        self.calls.append(("mget", ids, index))
        return {"docs": [{"_id": ident, "_index": "test-v1", "found": ident == "sync-state",
                          **({"_source": deepcopy(self.state)} if ident == "sync-state" else {}),
                          **({"error": {"type": "unavailable"}} if self.error and ident != "sync-state" else {})}
                         for ident in ids]}

    async def search(self, body, *, index):
        self.calls.append(("search", body, index))
        return {"timed_out": False, "_shards": {"failed": 0},
                "hits": {"total": {"value": self.total, "relation": "eq"}, "hits": self.hits}}

    async def get_document(self, ident, *, index):
        self.calls.append(("get", ident, index))
        return {"_id": ident, "_index": index, "found": True,
                "_source": {**self.state, "epoch": self.final_epoch}}


@pytest.fixture(autouse=True)
def nonstrict(monkeypatch):
    monkeypatch.setenv("KIFU_STRICT_NAMES", "0")


@pytest.mark.asyncio
async def test_empty_page_preserves_exact_total_page_and_null_preview():
    client = FakeSearch()
    result = await kifu.read_album_page_elasticsearch(client, None, q="nonexistent", page=2, page_size=20)
    assert result.model_dump() == {"items": [], "total": 0, "page": 2, "page_size": 20, "preview": None}
    assert [call[0] for call in client.calls] == ["mget", "search", "get"]
    assert all(call[2] == "test-v1" for call in client.calls[1:])


@pytest.mark.asyncio
@pytest.mark.parametrize("changes", [{"status": "pending"}, {"final_epoch": 3}, {"error": True}])
async def test_pending_aba_and_partial_classification_failure_never_return_empty_200(changes):
    with pytest.raises(HTTPException) as raised:
        await kifu.read_album_page_elasticsearch(FakeSearch(**changes), None, q="name")
    assert raised.value.status_code == 503
    assert raised.value.detail["code"] == "search_unavailable"


@pytest.mark.asyncio
async def test_out_of_window_empty_page_uses_total_only_and_preserves_page():
    client = FakeSearch(total=42)
    result = await kifu.read_album_page_elasticsearch(client, None, page=100000, page_size=100)
    assert result.total == 42 and result.page == 100000 and result.items == [] and result.preview is None
    body = next(call[1] for call in client.calls if call[0] == "search")
    assert body["size"] == 0 and "from" not in body


@pytest.mark.asyncio
@pytest.mark.parametrize("bad_result", [
    {"timed_out": True}, {"_shards": {"failed": 1}},
    {"hits": {"total": {"value": 1, "relation": "gte"}, "hits": []}},
])
async def test_partial_search_fails_closed(bad_result):
    client = FakeSearch()
    original = client.search

    async def search(body, *, index):
        return {**(await original(body, index=index)), **bad_result}

    client.search = search
    with pytest.raises(HTTPException) as raised:
        await kifu.read_album_page_elasticsearch(client, None)
    assert raised.value.status_code == 503


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



@pytest.mark.asyncio
@pytest.mark.parametrize("lang", kifu.LANGUAGES)
async def test_every_nonempty_page_keeps_complete_contract_and_exact_preview(catalog, lang):
    from katrain.web.kifu.search_projection import build_projection_context, project_album_batch
    engine, ranked_id = catalog
    with Session(engine) as db:
        db.get(business.KifuAlbum, ranked_id).date_sort = "2025-01-01"
        db.commit()
        records = db.query(business.KifuAlbum).filter(
            business.KifuAlbum.duplicate_of_id.is_(None), business.KifuAlbum.list_hidden_reason.is_(None)
        ).order_by(business.KifuAlbum.date_sort.desc().nulls_last(), business.KifuAlbum.id.desc()).all()
        docs = project_album_batch(build_projection_context(db, True), records)
        expected = kifu.read_album_page_legacy(db, page_size=3, lang=lang).model_dump()
    # This real page puts an analyzed game and bound rank/report overlays in
    # non-first rows. The async reader must enrich every row, not just preview.
    client = FakeSearch(hits=docs[:3], total=len(docs))
    client.state["strict_mode"] = True
    result = await kifu.read_album_page_elasticsearch(client, sessionmaker(bind=engine), page_size=3, lang=lang)
    assert result.model_dump() == expected
    assert result.preview.id == result.items[0].id
    assert sha256(result.preview.sgf_content.encode()).hexdigest() == sha256(expected["preview"]["sgf_content"].encode()).hexdigest()
    assert result.items[1].has_analysis
    assert result.items[2].black_rank_source is not None


def test_current_page_report_and_rank_binding_are_rechecked(catalog):
    from katrain.web.kifu.search_projection import build_projection_context, project_album_batch
    engine, ranked_id = catalog
    with Session(engine) as db:
        records = db.query(business.KifuAlbum).filter(business.KifuAlbum.id.in_([11, ranked_id])).all()
        docs = project_album_batch(build_projection_context(db, True), records)
    with engine.begin() as conn:
        job_id = conn.scalar(select(business.KifuAnalysisJob.id).where(business.KifuAnalysisJob.album_id == 11))
        conn.execute(update(business.KifuAnalysisMove).where(business.KifuAnalysisMove.job_id == job_id)
                     .values(root_visits=kifu.KIFU_VISITS - 1))
        conn.execute(update(business.KifuAlbumRankSnapshot).where(
            business.KifuAlbumRankSnapshot.album_id == ranked_id, business.KifuAlbumRankSnapshot.side == "black"
        ).values(snapshot_sha256="b" * 64))
    result = kifu._enrich_elasticsearch_page(sessionmaker(bind=engine), docs, 2, 1, 20, "cn")
    by_id = {item.id: item for item in result.items}
    assert not by_id[11].has_analysis
    assert by_id[ranked_id].black_rank_source is None
