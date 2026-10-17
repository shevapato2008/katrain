"""Recognition import tests use only temporary source files and isolated SQLite."""

import copy
import json
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, event, select, update
from sqlalchemy.orm import sessionmaker

from katrain.web.core.models_db import (
    AdminAuditLog,
    BoardPayloadHistory,
    TutorialBook,
    TutorialChapter,
    TutorialFigure,
    TutorialSection,
)
from katrain.web.tutorials.recognition_models import TutorialRecognitionCandidate
from katrain.web.tutorials.source_models import TutorialSourceBook, TutorialSourceFigure, TutorialSourcePage
from katrain.web.tutorials import recognition_catalog_import as importer


def raw(ident="p011-f01", index=1):
    return {
        "id": ident,
        "page": 11,
        "ref_index": index,
        "label": "1图",
        "text": "source prose",
        "result": {
            "payload": {
                "size": 19,
                "stones": {"B": [[14, 2]], "W": []},
                "labels": {"14,2": "W41"},
                "letters": {},
                "shapes": {},
                "unknown_stones": [[17, 7]],
            },
            "viewport": {"col": 7, "row": 0, "cols": 12, "rows": 19},
            "complete": True,
            "confidence": 1,
            "origin_uncertain": False,
            "notes": "uncertain color",
            "inferences": ["origin"],
            "uncertainties": ["unknown color"],
        },
        "review_crop": "assets/review.png",
        "needs_review": False,
    }


def write_inputs(tmp_path, figures=None):
    refs = [
        {
            "type": "figure_ref",
            "label": f"{i}图",
            "bbox": {"x_min": 0.1, "x_max": 0.5, "y_min": 0.1 * i, "y_max": 0.1 * i + 0.05},
        }
        for i in range(1, 4)
    ]
    book = {
        "title": "test",
        "chapters": [
            {"title": "chapter", "sections": [{"title": "section", "pages": [{"page": 11, "elements": refs}]}]}
        ],
    }
    book_path = tmp_path / "book.json"
    book_path.write_text(json.dumps(book), encoding="utf-8")
    page_path = tmp_path / "page_011.png"
    page_path.write_bytes(b"isolated source page image")
    value = {
        "sources": {str(book_path): importer.file_sha256(book_path)},
        "pages": [
            {
                "page": 11,
                "references": refs,
                "detection_status": "complete",
                "input_image": str(page_path),
                "page_sha256": importer.file_sha256(page_path),
            }
        ],
        "figures": figures if figures is not None else [raw()],
    }
    result_path = tmp_path / "results.json"
    result_path.write_text(json.dumps(value), encoding="utf-8")
    return importer.load_recognition(result_path, book_path), value, result_path, book_path


@pytest.fixture
def catalog(tmp_path):
    batch, value, result_path, book_path = write_inputs(tmp_path)
    engine = create_engine("sqlite:///:memory:")

    @event.listens_for(engine, "connect")
    def foreign_keys(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")

    tables = [
        TutorialBook,
        TutorialChapter,
        TutorialSection,
        TutorialFigure,
        BoardPayloadHistory,
        AdminAuditLog,
        TutorialSourceBook,
        TutorialSourceFigure,
        TutorialSourcePage,
        TutorialRecognitionCandidate,
    ]
    for model in tables:
        model.__table__.create(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    with sessions.begin() as db:
        db.add(TutorialBook(id=4, title="test", slug="test", category="中盘", asset_dir="assets"))
        db.flush()
        db.add(TutorialChapter(id=10, book_id=4, chapter_number="1", title="chapter", order=1))
        db.flush()
        db.add(TutorialSection(id=20, chapter_id=10, section_number="1", title="section", order=1))
        db.flush()
        db.add(TutorialFigure(id=1274, section_id=20, page=11, figure_label="1图", order=1))
        db.add(
            TutorialSourceBook(
                id=9,
                source_namespace="curriculum",
                catalog_id="ishida-judgement",
                book_id=4,
                source_json_sha256=batch.source_json_sha256,
                assets_manifest_sha256="b" * 64,
                source_metadata={},
                matching_evidence={},
            )
        )
        db.flush()
        for i in range(1, 4):
            db.add(
                TutorialSourceFigure(
                    id=1000 + i,
                    source_book_id=9,
                    source_figure_id=f"page11-physical-{i}",
                    source_pointer=f"/chapters/0/sections/0/pages/0/elements/{i-1}",
                    page=11,
                    figure_id=1274 if i == 1 else None,
                    match_reason="legacy_mapped" if i == 1 else "legacy_section_missing",
                    source_metadata={"section": {"pointer": "/chapters/0/sections/0", "title": "section"}},
                )
            )
        db.add(
            TutorialSourcePage(
                source_book_id=9,
                page=11,
                page_image_path="assets/page_011.png",
                image_sha256=batch.pages[0]["page_sha256"],
                text_fragments=[],
                page_context_text="page prose",
            )
        )
    yield sessions, batch, value, result_path, book_path
    engine.dispose()


def apply(sessions, batch):
    return importer.apply_recognition(sessions, batch, catalog_id="ishida-judgement", dataset="ishida-final")


def test_normalize_preserves_global_coordinates_unknowns_and_pending_replay():
    original = raw()
    saved = copy.deepcopy(original)
    value = importer.normalize_payload(original)
    assert value["stones"]["B"] == [[14, 2]]
    assert value["unknown_stones"] == [{"point": [17, 7], "color": None}]
    assert value["labels"] == {"14,2": "W41"}
    assert value["source_region"] == {"col": 7, "row": 0, "cols": 12, "rows": 19, "confirmed": False}
    assert value["replay"] == {"status": "needs_calibration", "initial": None, "moves": []}
    assert original == saved


def test_loader_hash_and_index_are_checked_without_caption_matching(tmp_path):
    batch, value, result_path, book_path = write_inputs(tmp_path)
    assert batch.figures[0].source_pointer.endswith("/elements/0")
    index_path = tmp_path / "recognition-index.json"
    index_path.write_text(
        json.dumps(
            {
                "source_hashes": value["sources"],
                "figures": {
                    "p011-f01": {
                        "page": 11,
                        "ref_index": 1,
                        "source_pointer": "/wrong",
                        "figure_sha256": importer.content_sha256(raw()),
                    }
                },
            }
        )
    )
    with pytest.raises(importer.RecognitionImportError, match="index"):
        importer.load_recognition(result_path, book_path, index_path=index_path)
    book_path.write_text(book_path.read_text() + " ")
    with pytest.raises(importer.RecognitionImportError, match="hash"):
        importer.load_recognition(result_path, book_path)


def test_dry_run_is_read_only_and_repeated_apply_changes_nothing(catalog):
    sessions, batch, *_ = catalog
    with sessions() as db:
        plan = importer.plan_recognition(db, batch, catalog_id="ishida-judgement", dataset="ishida-final")
        assert plan.rows[0]["figure_id"] == 1274
        assert plan.rows[0]["source_figure_id"] == 1001
        assert plan.rows[0]["status"] == "would_apply"
        assert not db.new and not db.dirty
    result = apply(sessions, batch)
    assert result.rows[0]["status"] == "applied"
    with sessions() as db:
        figure = db.get(TutorialFigure, 1274)
        candidate = db.scalar(select(TutorialRecognitionCandidate))
        version = figure.updated_at
        assert figure.board_payload == importer.normalize_payload(raw())
        assert candidate.raw_result == raw()
        assert candidate.source_figure_id == 1001
        assert len(db.scalars(select(BoardPayloadHistory)).all()) == 1
        assert len(db.scalars(select(AdminAuditLog)).all()) == 1
    assert apply(sessions, batch).rows[0]["status"] == "existing"
    with sessions() as db:
        assert db.get(TutorialFigure, 1274).updated_at == version
        assert len(db.scalars(select(TutorialRecognitionCandidate)).all()) == 1
        assert len(db.scalars(select(TutorialFigure)).all()) == 1
        assert len(db.scalars(select(BoardPayloadHistory)).all()) == 1
        assert len(db.scalars(select(AdminAuditLog)).all()) == 1


@pytest.mark.parametrize("protection", ["payload", "history", "review", "narration", "audio", "video", "debug"])
def test_existing_human_or_media_content_is_preserved(catalog, protection):
    sessions, batch, *_ = catalog
    with sessions.begin() as db:
        figure = db.get(TutorialFigure, 1274)
        if protection == "payload":
            figure.board_payload = {"stones": {"B": [], "W": []}}
        if protection == "history":
            db.add(BoardPayloadHistory(figure_id=1274, board_payload={}, changed_by="human"))
        if protection == "review":
            figure.recognition_debug = {"human_verified": True}
        if protection == "debug":
            figure.recognition_debug = {"manual_note": "keep"}
        if protection == "narration":
            figure.narration = "human narration"
        if protection == "audio":
            figure.audio_asset = "audio.mp3"
        if protection == "video":
            figure.video_asset = "video.mp4"
        db.flush()
        snapshot = {
            column.name: copy.deepcopy(getattr(figure, column.name)) for column in TutorialFigure.__table__.columns
        }
    result = apply(sessions, batch)
    assert result.rows[0]["status"] == "protected"
    with sessions() as db:
        figure = db.get(TutorialFigure, 1274)
        assert {column.name: getattr(figure, column.name) for column in TutorialFigure.__table__.columns} == snapshot
        assert db.scalar(select(TutorialRecognitionCandidate)).raw_result == raw()


def test_missing_ambiguous_extra_and_split_are_stable_supplemental_figures(catalog):
    sessions, _, value, result_path, book_path = catalog
    with sessions.begin() as db:
        db.get(TutorialSourceFigure, 1003).match_reason = "ambiguous_figure_candidates"
    value["figures"] = [raw(), raw("p011-f02", 2), raw("p011-f03", 3), raw("p011-f04", 0), raw("p011-f05", 1)]
    result_path.write_text(json.dumps(value))
    batch = importer.load_recognition(result_path, book_path)
    result = apply(sessions, batch)
    assert len({row["figure_id"] for row in result.rows}) == 5
    assert sum(row["supplemental"] for row in result.rows) == 4
    with sessions() as db:
        assert db.get(TutorialSourceFigure, 1003).figure_id is None
        assert db.get(TutorialSourceFigure, 1002).figure_id == result.rows[1]["figure_id"]
        assert db.get(TutorialSourceFigure, 1001).figure_id == 1274
        assert len(db.scalars(select(TutorialSection)).all()) == 3  # canonical group + extra page group
        assert len(db.scalars(select(TutorialRecognitionCandidate)).all()) == 5
    second = apply(sessions, batch)
    assert [row["figure_id"] for row in second.rows] == [row["figure_id"] for row in result.rows]
    with sessions() as db:
        assert len(db.scalars(select(TutorialFigure)).all()) == 5
        assert len(db.scalars(select(TutorialRecognitionCandidate)).all()) == 5


def test_manual_save_between_dry_run_and_apply_is_rechecked(catalog):
    sessions, batch, *_ = catalog
    with sessions() as db:
        assert (
            importer.plan_recognition(db, batch, catalog_id="ishida-judgement", dataset="ishida-final").rows[0][
                "status"
            ]
            == "would_apply"
        )
    with sessions.begin() as db:
        db.get(TutorialFigure, 1274).board_payload = {"stones": {"B": [[0, 0]], "W": []}}
    assert apply(sessions, batch).rows[0]["status"] == "protected"
    with sessions() as db:
        assert db.get(TutorialFigure, 1274).board_payload["stones"]["B"] == [[0, 0]]


def test_cas_conflict_rolls_back_candidate_payload_history_and_audit(catalog, monkeypatch):
    sessions, batch, *_ = catalog
    original = importer._cas_update

    def racing_save(db, figure, expected, values):
        db.execute(
            update(TutorialFigure)
            .where(TutorialFigure.id == figure.id)
            .values(updated_at=datetime.now(timezone.utc) + timedelta(seconds=1))
            .execution_options(synchronize_session=False)
        )
        return original(db, figure, expected, values)

    monkeypatch.setattr(importer, "_cas_update", racing_save)
    with pytest.raises(HTTPException) as error:
        apply(sessions, batch)
    assert error.value.status_code == 409
    with sessions() as db:
        assert db.get(TutorialFigure, 1274).board_payload is None
        assert not db.scalars(select(TutorialRecognitionCandidate)).all()
        assert not db.scalars(select(BoardPayloadHistory)).all()
        assert not db.scalars(select(AdminAuditLog)).all()


def test_audit_failure_rolls_back_supplemental_candidate_and_link(catalog):
    sessions, _, value, result_path, book_path = catalog
    value["figures"] = [raw("p011-f02", 2)]
    result_path.write_text(json.dumps(value))
    batch = importer.load_recognition(result_path, book_path)

    def refuse_audit(_mapper, _connection, _target):
        raise RuntimeError("audit failed")

    event.listen(AdminAuditLog, "before_insert", refuse_audit)
    try:
        with pytest.raises(RuntimeError, match="audit failed"):
            apply(sessions, batch)
    finally:
        event.remove(AdminAuditLog, "before_insert", refuse_audit)
    with sessions() as db:
        assert len(db.scalars(select(TutorialFigure)).all()) == 1
        assert len(db.scalars(select(TutorialSection)).all()) == 1
        assert db.get(TutorialSourceFigure, 1002).figure_id is None
        assert not db.scalars(select(TutorialRecognitionCandidate)).all()


def test_conflicting_raw_identity_fails_without_overwriting(catalog):
    sessions, batch, value, result_path, book_path = catalog
    apply(sessions, batch)
    value["figures"][0]["result"]["notes"] = "different evidence"
    result_path.write_text(json.dumps(value))
    changed = importer.load_recognition(result_path, book_path)
    with pytest.raises((ValueError, importer.RecognitionImportError), match="immutable"):
        apply(sessions, changed)
    with sessions() as db:
        assert db.scalar(select(TutorialRecognitionCandidate)).raw_result == raw()


def test_failed_or_malformed_results_are_reported_not_inserted(catalog):
    sessions, _, value, result_path, book_path = catalog
    failed = raw("p011-f02", 2)
    failed["result"] = {"complete": False, "error": "recognition failed"}
    malformed = raw("p011-f03", 3)
    malformed["result"]["payload"]["unknown_stones"] = [[14, 2]]
    value["figures"] = [raw(), failed, malformed]
    result_path.write_text(json.dumps(value))
    batch = importer.load_recognition(result_path, book_path)
    result = apply(sessions, batch)
    assert [row["status"] for row in result.rows] == ["applied", "failed", "failed"]
    with sessions() as db:
        assert len(db.scalars(select(TutorialRecognitionCandidate)).all()) == 1


def test_p92_sentinel_requires_corrected95_triangle_and_capture_notes():
    value = raw("p092-f03")
    value["page"] = 92
    payload = value["result"]["payload"]
    payload["labels"] = {"2,18": "95", "0,0": "80", "1,0": "91"}
    payload["shapes"] = {"1,5": "triangle"}
    value["result"]["notes"] = "黑93＝△；白94＝白80；黑99＝黑91"
    importer.validate_p92_sentinel([value])
    payload["labels"]["2,18"] = "93"
    with pytest.raises(importer.RecognitionImportError, match="p092"):
        importer.validate_p92_sentinel([value])


def test_missing_link_is_flushed_before_cas_with_autoflush_disabled(catalog):
    sessions, _, value, result_path, book_path = catalog
    sessions.configure(autoflush=False)
    value["figures"] = [raw("p011-f02", 2)]
    result_path.write_text(json.dumps(value))
    batch = importer.load_recognition(result_path, book_path)
    result = apply(sessions, batch)
    with sessions() as db:
        assert db.get(TutorialSourceFigure, 1002).figure_id == result.rows[0]["figure_id"]


def test_empty_index_is_not_silently_ignored(tmp_path):
    _, _, result_path, book_path = write_inputs(tmp_path)
    index_path = tmp_path / "index.json"
    index_path.write_text("{}")
    with pytest.raises(importer.RecognitionImportError, match="index"):
        importer.load_recognition(result_path, book_path, index_path=index_path)


def test_registered_book_hash_mismatch_refuses_all_writes(catalog):
    sessions, batch, *_ = catalog
    with sessions.begin() as db:
        db.get(TutorialSourceBook, 9).source_json_sha256 = "d" * 64
    with pytest.raises(importer.RecognitionImportError, match="hash"):
        apply(sessions, batch)
    with sessions() as db:
        assert not db.scalars(select(TutorialRecognitionCandidate)).all()
        assert db.get(TutorialFigure, 1274).board_payload is None


def test_schema_helper_creates_only_candidate_table(tmp_path):
    from sqlalchemy import inspect

    engine = create_engine(f"sqlite:///{tmp_path / 'ddl.sqlite'}")
    importer.create_recognition_table(engine)
    assert inspect(engine).get_table_names() == ["tutorial_recognition_candidates"]
    engine.dispose()


def test_cli_schema_and_apply_guards_run_before_database_access(tmp_path, monkeypatch):
    import importlib.util
    from pathlib import Path

    spec = importlib.util.spec_from_file_location(
        "recognition_cli", Path(__file__).parents[2] / "scripts/import_tutorial_recognition.py"
    )
    cli = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cli)

    def database_must_not_open(*_args, **_kwargs):
        raise AssertionError("guard must run before opening database")

    monkeypatch.setattr(cli, "create_engine", database_must_not_open)
    monkeypatch.delenv("KATRAIN_ADMIN_ENV", raising=False)
    common = [
        "--results",
        "missing",
        "--book-json",
        "missing",
        "--frozen-first100",
        "missing",
        "--dataset",
        "ishida",
        "--report-dir",
        str(tmp_path),
    ]
    assert cli.main(common + ["--create-schema"]) == 2
    assert cli.main(common + ["--apply", "--expected-env", "test"]) == 2


def test_malformed_conflict_with_existing_identity_refuses_other_candidate_writes(catalog):
    sessions, batch, value, result_path, book_path = catalog
    apply(sessions, batch)
    value["figures"] = [raw("p011-f02", 2), raw()]
    value["figures"][1]["result"]["payload"]["stones"]["B"] = [[99, 99]]
    result_path.write_text(json.dumps(value))
    changed = importer.load_recognition(result_path, book_path)
    with pytest.raises(importer.RecognitionImportError, match="immutable"):
        apply(sessions, changed)
    with sessions() as db:
        assert len(db.scalars(select(TutorialRecognitionCandidate)).all()) == 1
        assert len(db.scalars(select(TutorialFigure)).all()) == 1
        assert db.get(TutorialSourceFigure, 1002).figure_id is None


def test_extra_physical_identity_reuses_real_figure_across_datasets(catalog):
    sessions, _, value, result_path, book_path = catalog
    value["figures"] = [raw("p011-f04", 0)]
    result_path.write_text(json.dumps(value))
    batch = importer.load_recognition(result_path, book_path)
    first = importer.apply_recognition(sessions, batch, catalog_id="ishida-judgement", dataset="dataset-one")
    second = importer.apply_recognition(sessions, batch, catalog_id="ishida-judgement", dataset="dataset-two")
    assert second.rows[0]["figure_id"] == first.rows[0]["figure_id"]
    assert second.rows[0]["supplemental"] is True
    assert second.rows[0]["status"] == "protected"
    with sessions() as db:
        assert len(db.scalars(select(TutorialFigure)).all()) == 2
        assert len(db.scalars(select(TutorialRecognitionCandidate)).all()) == 2


@pytest.mark.parametrize("change", ["different_digest", "missing_registered_page"])
def test_live_page_provenance_mismatch_refuses_before_any_writes(catalog, change):
    from sqlalchemy import delete

    sessions, batch, *_ = catalog
    if change == "different_digest":
        batch.pages[0]["page_sha256"] = "d" * 64
    else:
        with sessions.begin() as db:
            db.execute(delete(TutorialSourcePage))
    with pytest.raises(importer.RecognitionImportError, match="page.*hash|page.*provenance"):
        apply(sessions, batch)
    with sessions() as db:
        assert not db.scalars(select(TutorialRecognitionCandidate)).all()
        assert db.get(TutorialFigure, 1274).board_payload is None


def test_local_page_hash_mismatch_is_rejected(tmp_path):
    _, value, result_path, book_path = write_inputs(tmp_path)
    page = tmp_path / "page.png"
    page.write_bytes(b"actual source image")
    value["pages"][0].update(input_image=str(page), page_sha256="d" * 64)
    result_path.write_text(json.dumps(value))
    with pytest.raises(importer.RecognitionImportError, match="page.*hash"):
        importer.load_recognition(result_path, book_path)


def generic_inputs(tmp_path, *, page_number=1, commentary=False):
    _, data, result_path, book_path = write_inputs(tmp_path)
    pdf = tmp_path / "source.pdf"
    pdf.write_bytes(b"isolated PDF identity; page count supplied by independent operator inventory")
    book = json.loads(book_path.read_text())
    record = book["chapters"][0]["sections"][0]["pages"][0]
    record["page"] = page_number
    if commentary:
        record["elements"][0]["commentary_refs"] = [{"type": "figure_ref", "page": page_number, "element_index": 1}]
    book_path.write_text(json.dumps(book))
    figure = data["figures"][0]
    figure.update(id=f"p{page_number:03d}-f03", page=page_number)
    data.update(catalog_id="intro-up", pdf_pages=page_number, baseline_references=3)
    data["sources"] = {str(book_path): importer.file_sha256(book_path), str(pdf): importer.file_sha256(pdf)}
    # Every PDF page has an immutable outcome; pages outside source PNGs have no figures/refs.
    page = data["pages"][0]
    source_image = tmp_path / "pages" / f"page_{page_number:03d}.png"
    source_image.parent.mkdir(parents=True)
    source_image.write_bytes(b"original registered source PNG")
    page.update(
        references=record["elements"],
        page=page_number,
        input_image=str(source_image),
        page_sha256=importer.file_sha256(source_image),
        figure_ids=[figure["id"]],
        detected_count=1,
    )
    pages = []
    for n in range(1, page_number):
        image = tmp_path / f"assets/pages/page_{n:03d}.png"
        image.parent.mkdir(parents=True, exist_ok=True)
        image.write_bytes(b"rendered blank PDF page")
        pages.append(
            dict(
                page=n,
                references=[],
                reference_pointers=[],
                input_image=str(image),
                page_sha256=importer.file_sha256(image),
                detection_status="complete",
                detected_count=0,
                figure_ids=[],
                rendered_missing_source=True,
                render_provenance=dict(
                    pdf=str(pdf.resolve()),
                    pdf_sha256=importer.file_sha256(pdf),
                    pdf_page=n,
                    renderer="pdftoppm",
                    dpi=120,
                ),
            )
        )
    page["unrepresented_references"] = [
        dict(ref_index=2, reason="text-only reference"),
        dict(ref_index=3, reason="text-only reference"),
    ]
    data["pages"] = pages + [page]
    data["page_outcomes"] = [dict(page=p["page"], status="complete") for p in data["pages"]]
    result_path.write_text(json.dumps(data))
    return data, result_path, book_path, pdf


def generic_load(paths, **kw):
    data, result, book, pdf = paths
    return importer.load_catalog_recognition(
        result,
        book,
        catalog_id="intro-up",
        pdf_path=pdf,
        expected_pdf_pages=max(p["page"] for p in data["pages"]),
        **kw,
    )


def test_generic_other_book_p92_is_not_ishida_and_commentary_is_not_a_physical_diagram(tmp_path):
    paths = generic_inputs(tmp_path, page_number=92, commentary=True)
    batch = generic_load(paths)
    assert len(batch.references) == 3
    assert batch.figures[0].raw["id"] == "p092-f03"
    assert batch.figures[0].payload["schema_version"] == 2
    assert batch.figures[0].payload["replay"]["status"] == "needs_calibration"
    assert len(batch.coverage_only_pages) == 91
    assert len(batch.pages) == 1


@pytest.mark.parametrize(
    "change",
    ["wrong_catalog", "missing_pdf_page", "wrong_pdf_count", "missing_pdf_hash", "extra_figure_on_unregistered_page"],
)
def test_generic_requires_full_independently_counted_pdf_identity(tmp_path, change):
    paths = generic_inputs(tmp_path, page_number=2)
    data, result, book, pdf = paths
    if change == "wrong_catalog":
        data["catalog_id"] = "other-book"
    elif change == "missing_pdf_page":
        data["pages"] = data["pages"][1:]
    elif change == "wrong_pdf_count":
        data["pdf_pages"] = 3
    elif change == "missing_pdf_hash":
        del data["sources"][str(pdf)]
    else:
        data["pages"][0]["detected_count"] = 1
    result.write_text(json.dumps(data))
    with pytest.raises(importer.RecognitionImportError):
        generic_load(paths)


def test_generic_cannot_bypass_ishida_frozen_policy(tmp_path):
    _, result, book, pdf = generic_inputs(tmp_path)
    with pytest.raises(importer.RecognitionImportError, match="Ishida"):
        importer.load_catalog_recognition(
            result, book, catalog_id="ishida-judgement", pdf_path=pdf, expected_pdf_pages=1
        )


@pytest.mark.parametrize(
    "change",
    ["partial_outcome", "unvalidated_figure", "unexplained_missing", "copy_registered_png", "wrong_render_pdf"],
)
def test_generic_does_not_bypass_complete_results_or_registered_page_guard(tmp_path, change):
    paths = generic_inputs(tmp_path, page_number=2)
    data, result, book, pdf = paths
    if change == "partial_outcome":
        data["page_outcomes"][0]["status"] = "not_requested"
    elif change == "unvalidated_figure":
        data["figures"][0]["result"]["complete"] = False
    elif change == "unexplained_missing":
        data["pages"][1]["unrepresented_references"] = []
    elif change == "copy_registered_png":
        (book.parent / "pages/page_001.png").write_bytes(b"source actually exists")
    else:
        data["pages"][0]["render_provenance"]["pdf_sha256"] = "d" * 64
    result.write_text(json.dumps(data))
    with pytest.raises(importer.RecognitionImportError):
        generic_load(paths)


def test_generic_cli_dry_run_requires_test_before_opening_database(tmp_path, monkeypatch):
    import importlib.util
    from pathlib import Path

    spec = importlib.util.spec_from_file_location(
        "generic_recognition_cli", Path(__file__).parents[2] / "scripts/import_tutorial_book_recognition.py"
    )
    cli = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cli)
    monkeypatch.delenv("KATRAIN_ADMIN_ENV", raising=False)
    monkeypatch.setattr(cli, "create_engine", lambda *_a, **_kw: pytest.fail("database must not open"))
    assert (
        cli.main(
            [
                "--results",
                "missing",
                "--book-json",
                "missing",
                "--pdf",
                "missing",
                "--expected-pdf-pages",
                "314",
                "--catalog-id",
                "intro-up",
                "--dataset",
                "intro-up-gpt61sol-v1",
                "--report-dir",
                str(tmp_path),
            ]
        )
        == 2
    )
