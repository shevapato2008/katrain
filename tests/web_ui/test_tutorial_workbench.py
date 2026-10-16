"""Durable calibration uses isolated SQLite, never a configured tutorial database."""

import copy
import hashlib
import io
import json
import zipfile

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import create_engine, event, update
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from katrain.web.core import models_db
from katrain.web.tutorials.models import StrictBoardPayload


def diagram():
    return {
        "schema_version": 2,
        "size": 9,
        "stones": {"B": [[0, 0]], "W": []},
        "unknown_stones": [],
        "labels": {"0,0": "W41"},
        "letters": {"8,8": "A"},
        "shapes": {"0,0": "triangle"},
        "highlights": [[8, 8]],
        "viewport": {"col": 0, "row": 0, "cols": 9, "rows": 9},
        "source_region": {"col": 0, "row": 0, "cols": 9, "rows": 9, "confirmed": True},
        "replay": {
            "status": "complete",
            "initial": {
                "stones": {"B": [], "W": []},
                "unknown_stones": [],
                "labels": {},
                "known_region": {"col": 0, "row": 0, "cols": 9, "rows": 9},
                "to_play": "B",
            },
            "moves": [{"kind": "move", "color": "B", "point": [0, 0], "printed_number": "W41"}],
            "evidence": {
                "kind": "source",
                "source_pointer": "/pages/92/figures/3",
                "description": "Explicit source move 41",
            },
        },
    }


def test_v2_roundtrip_preserves_unknowns_extent_static_marks_and_null_draft():
    value = diagram()
    value["unknown_stones"] = [{"point": [7, 7], "color": None, "evidence": "p014-f06"}]
    value["replay"]["status"] = "needs_calibration"
    value["replay"]["moves"].append({"kind": "move", "color": None, "point": None, "printed_number": "1"})
    assert StrictBoardPayload.model_validate(value).model_dump(exclude_unset=True) == value


@pytest.mark.parametrize(
    "change",
    [
        "overlap",
        "unknown_overlap",
        "outside",
        "illegal_order",
        "final_mismatch",
        "zero_steps",
        "no_evidence",
        "unconfirmed",
        "suicide",
    ],
)
def test_complete_replay_is_validated_not_trusted(change):
    value = diagram()
    if change == "overlap":
        value["stones"]["W"] = [[0, 0]]
    if change == "unknown_overlap":
        value["unknown_stones"] = [{"point": [0, 0], "color": None}]
    if change == "outside":
        value["viewport"]["cols"] = 10
    if change == "illegal_order":
        value["replay"]["moves"][0]["color"] = "W"
    if change == "final_mismatch":
        value["stones"]["B"] = [[1, 0]]
    if change == "zero_steps":
        value["replay"]["initial"]["stones"] = copy.deepcopy(value["stones"])
        value["replay"]["moves"] = []
    if change == "no_evidence":
        value["replay"].pop("evidence")
    if change == "unconfirmed":
        value["source_region"]["confirmed"] = False
    if change == "suicide":
        value["replay"]["initial"]["stones"]["W"] = [[1, 0], [0, 1]]
    with pytest.raises(ValidationError):
        StrictBoardPayload.model_validate(value)


def test_replay_reuses_capture_primitives_and_never_assumes_outside_empty():
    from katrain.web.tutorials.replay import validate_replay

    value = diagram()
    initial = value["replay"]["initial"]
    initial["stones"] = {"B": [[0, 1], [1, 0], [2, 1]], "W": [[1, 1]]}
    value["replay"]["moves"] = [
        {"kind": "move", "color": "B", "point": [1, 2], "printed_number": "1"},
        {"kind": "pass", "color": "W", "point": None, "printed_number": None},
        {"kind": "move", "color": "B", "point": [1, 1], "printed_number": "3"},
    ]
    value["stones"] = {"B": [[0, 1], [1, 0], [2, 1], [1, 2], [1, 1]], "W": []}
    assert validate_replay(value)["status"] == "complete"
    initial["known_region"] = {"col": 1, "row": 1, "cols": 1, "rows": 2}
    assert validate_replay(value)["status"] == "needs_calibration"


@pytest.fixture
def workbench():
    from katrain.web.admin.routers import tutorial_workbench, tutorials
    from katrain.web.admin.session import get_current_admin
    from katrain.web.tutorials.source_models import TutorialSourceBook, TutorialSourceFigure, TutorialSourcePage
    from katrain.web.tutorials.recognition_models import TutorialRecognitionCandidate

    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    models_db.Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    with Session() as db:
        db.add(
            models_db.TutorialBook(id=1, category="布局", subcategory="棋书", title="Test", slug="test", asset_dir="x")
        )
        db.flush()
        db.add(models_db.TutorialChapter(id=1, book_id=1, chapter_number="1", title="Test", order=1))
        db.flush()
        db.add(models_db.TutorialSection(id=1, chapter_id=1, section_number="1", title="Test", order=1))
        db.flush()
        db.add(models_db.TutorialFigure(id=1, section_id=1, page=92, figure_label="图3", order=1))
        db.flush()
        db.add(
            TutorialSourceBook(
                id=1,
                source_namespace="curriculum",
                catalog_id="ishida",
                book_id=1,
                source_json_sha256="a" * 64,
                assets_manifest_sha256="b" * 64,
                source_metadata={},
                matching_evidence={},
            )
        )
        db.flush()
        db.add(
            TutorialSourceFigure(
                id=1,
                source_book_id=1,
                source_figure_id="p092-f03",
                source_pointer="/pages/92/figures/3",
                page=92,
                figure_id=1,
                source_metadata={"bbox": {"x_min": 0, "y_min": 0, "x_max": 1, "y_max": 1}},
                match_reason="exact",
            )
        )
        for page in [1, 14, 92, 195]:
            db.add(
                TutorialSourcePage(
                    source_book_id=1,
                    page=page,
                    page_image_path=f"tutorial_assets/test/pages/{page}.png",
                    image_sha256="c" * 64,
                    text_fragments=[],
                    page_context_text="source",
                )
            )
        db.commit()
        db.execute(update(models_db.TutorialFigure).values(updated_at=None))
        db.commit()
    app = FastAPI()
    app.state.session_factory = Session
    app.state.admin_config = object()
    app.include_router(tutorials.router, prefix="/api/admin/tutorials")
    app.include_router(tutorial_workbench.router, prefix="/api/admin/tutorials")
    app.dependency_overrides[get_current_admin] = lambda: {"realm": "admin", "username": "admin:fan"}
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client, Session, app
    engine.dispose()


def save(client, value=None, version=None):
    return client.put(
        "/api/admin/tutorials/figures/1/calibration",
        json={"board_payload": value or diagram(), "expected_updated_at": version},
    )


def test_calibration_cas_history_reviews_and_narration_media(workbench):
    client, Session, _ = workbench
    first = save(client)
    assert first.status_code == 200, first.text
    version = first.json()["updated_at"]
    verified = client.put("/api/admin/tutorials/figures/1/verify-board", json={"expected_updated_at": version})
    assert verified.status_code == 200, verified.text
    version = verified.json()["updated_at"]
    seq = client.put("/api/admin/tutorials/figures/1/verify-sequence", json={"expected_updated_at": version})
    assert seq.status_code == 200, seq.text
    version = seq.json()["updated_at"]
    assert seq.json()["recognition_debug"]["calibration_review"]["sequence"]["verified_by"] == "admin:fan"
    assert save(client, version=None).status_code == 409
    with Session() as db:
        figure = db.get(models_db.TutorialFigure, 1)
        figure.audio_asset = "a.mp3"
        figure.video_asset = "v.mp4"
        figure.narration = "old"
        db.commit()
        version = figure.updated_at.replace(tzinfo=__import__("datetime").timezone.utc).isoformat()
    changed = diagram()
    changed["labels"]["0,0"] = "W1"
    response = client.put(
        "/api/admin/tutorials/figures/1/calibration",
        json={"board_payload": changed, "narration": "new", "expected_updated_at": version},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["audio_asset"] is None and body["video_asset"] is None
    assert body["recognition_debug"]["calibration_review"] == {"board": None, "sequence": None}
    history = client.get("/api/admin/tutorials/figures/1/history").json()["history"]
    assert len(history) == 4
    assert history[0]["change_type"] == "edit"
    with Session() as db:
        assert db.query(models_db.AdminAuditLog).count() == 4


def test_incomplete_saved_but_not_sequence_verified_and_legacy_write_preserves_v2(workbench):
    client, Session, _ = workbench
    value = diagram()
    value["replay"]["status"] = "needs_calibration"
    value["replay"]["moves"] = []
    saved = save(client, value)
    assert saved.status_code == 200, saved.text
    version = saved.json()["updated_at"]
    assert (
        client.put("/api/admin/tutorials/figures/1/verify-sequence", json={"expected_updated_at": version}).status_code
        == 422
    )
    response = client.put(
        "/api/admin/tutorials/figures/1/board",
        json={"board_payload": {"size": 9, "stones": value["stones"]}, "expected_updated_at": version},
    )
    assert response.status_code == 409
    with Session() as db:
        assert db.get(models_db.TutorialFigure, 1).board_payload["schema_version"] == 2


def test_candidate_identity_immutable_and_explicit_apply(workbench):
    from katrain.web.tutorials.recognition_import import import_candidate
    from katrain.web.tutorials.recognition_models import TutorialRecognitionCandidate

    client, Session, _ = workbench
    raw = {"id": "p092-f03", "notes": "95 corrected; 93 triangle; capture/ko 99=91"}
    with Session() as db:
        candidate = import_candidate(
            db,
            source_book_id=1,
            dataset="first100-final",
            recognition_id="p092-f03",
            figure_id=1,
            page=92,
            raw_result=raw,
            board_payload=diagram(),
            source_figure_id=1,
            source_pointer="/pages/92/figures/3",
        )
        db.commit()
        candidate_id = candidate.id
    with Session() as db:
        assert (
            import_candidate(
                db,
                source_book_id=1,
                dataset="first100-final",
                recognition_id="p092-f03",
                figure_id=1,
                page=92,
                raw_result=raw,
                board_payload=diagram(),
                source_figure_id=1,
            ).id
            == candidate_id
        )
        with pytest.raises(ValueError):
            import_candidate(
                db,
                source_book_id=1,
                dataset="first100-final",
                recognition_id="p092-f03",
                figure_id=1,
                page=92,
                raw_result={"notes": "changed"},
                board_payload=diagram(),
            )
        assert db.get(models_db.TutorialFigure, 1).board_payload is None
        candidate = db.get(TutorialRecognitionCandidate, candidate_id)
        candidate.raw_result = {"forged": True}
        with pytest.raises(ValueError):
            db.flush()
        db.rollback()
    applied = client.post(
        "/api/admin/tutorials/figures/1/apply-candidate",
        json={"candidate_id": candidate_id, "expected_updated_at": None},
    )
    assert applied.status_code == 200, applied.text
    assert applied.json()["recognition_debug"]["calibration_review"] == {"board": None, "sequence": None}
    assert applied.json()["recognition_debug"]["human_verified"] is False


def test_workbench_keeps_all_pages_empty_states_and_current_candidate_compare(workbench):
    client, _, _ = workbench
    assert save(client).status_code == 200
    response = client.get("/api/admin/tutorials/books/1/workbench?page=92")
    assert response.status_code == 200, response.text
    body = response.json()
    assert [p["page"] for p in body["pages"]] == [1, 14, 92, 195]
    assert len(body["figures"]) == 1 and body["figures"][0]["current"]["schema_version"] == 2
    assert client.get("/api/admin/tutorials/books/1/workbench?page=195").json()["figures"] == []
    filtered = client.get("/api/admin/tutorials/books/1/workbench?page=92&filter=uncertainty").json()
    assert filtered["figures"] == [] and filtered["page"]["page_image_path"].endswith("92.png")


def test_audit_failure_rolls_back_board_history_version(workbench):
    client, Session, _ = workbench

    @event.listens_for(Session, "before_flush")
    def fail_audit(session, *_):
        if any(isinstance(item, models_db.AdminAuditLog) for item in session.new):
            raise RuntimeError("audit unavailable")

    try:
        assert save(client).status_code >= 500
    finally:
        event.remove(Session, "before_flush", fail_audit)
    with Session() as db:
        figure = db.get(models_db.TutorialFigure, 1)
        assert figure.board_payload is None and figure.updated_at is None
        assert db.query(models_db.BoardPayloadHistory).count() == 0


def test_exports_sgf_and_zip_exact_version_unknowns_and_capture_notes(workbench):
    from katrain.core.sgf_parser import SGF
    from katrain.web.tutorials.recognition_import import import_candidate

    client, Session, _ = workbench
    value = diagram()
    value["unknown_stones"] = [{"point": [8, 8], "color": None, "evidence": "p014-f06"}]
    value["replay"]["status"] = "needs_calibration"
    with Session() as db:
        import_candidate(
            db,
            source_book_id=1,
            dataset="first100-final",
            recognition_id="p092-f03",
            figure_id=1,
            page=92,
            raw_result={"notes": "p014-f06; p092-f03: 95 corrected; 99=91 capture/ko"},
            board_payload=value,
        )
        db.commit()
    sgf = client.get("/api/admin/tutorials/figures/1/export.sgf")
    assert sgf.status_code == 200, sgf.text
    root = SGF.parse_sgf(sgf.text)
    assert root.get_list_property("AB") == ["aa"]
    assert not root.get_list_property("AW")
    assert "8,8" in root.get_property("C") and "candidate" in root.get_property("C")
    archive = client.get("/api/admin/tutorials/books/1/export.zip")
    assert archive.status_code == 200, archive.text
    with zipfile.ZipFile(io.BytesIO(archive.content)) as zipped:
        index = json.loads(zipped.read("index.json"))
        entry = index["figures"][0]
        sidecar = json.loads(zipped.read(entry["json_file"]))
        assert entry["version_kind"] == "candidate"
        assert "capture/ko" in json.dumps(sidecar, ensure_ascii=False)
        assert (
            entry["payload_sha256"]
            == hashlib.sha256(
                json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest()
        )


def test_workbench_requires_admin_auth(workbench):
    from katrain.web.admin.session import get_current_admin

    client, _, app = workbench
    app.dependency_overrides.pop(get_current_admin)
    assert client.get("/api/admin/tutorials/books/1/workbench?page=92").status_code in (401, 503)


def test_simple_ko_and_unknown_liberty_are_not_playable():
    from katrain.web.tutorials.replay import validate_replay

    value = diagram()
    value["replay"]["initial"]["stones"] = {"B": [[0, 1], [1, 0], [2, 1]], "W": [[1, 1], [0, 2], [2, 2], [1, 3]]}
    value["replay"]["moves"] = [
        {"kind": "move", "color": "B", "point": [1, 2], "printed_number": "99"},
        {"kind": "move", "color": "W", "point": [1, 1], "printed_number": "100"},
    ]
    assert any("ko" in issue.lower() for issue in validate_replay(value)["issues"])
    value = diagram()
    value["replay"]["initial"]["known_region"] = {"col": 0, "row": 0, "cols": 1, "rows": 1}
    assert any("unknown" in issue.lower() for issue in validate_replay(value)["issues"])


def test_sequence_only_change_preserves_board_review_and_invalidates_sequence(workbench):
    client, _, _ = workbench
    first = save(client).json()
    board = client.put(
        "/api/admin/tutorials/figures/1/verify-board", json={"expected_updated_at": first["updated_at"]}
    ).json()
    sequence = client.put(
        "/api/admin/tutorials/figures/1/verify-sequence", json={"expected_updated_at": board["updated_at"]}
    ).json()
    assert first["updated_at"] < board["updated_at"] < sequence["updated_at"]
    changed = diagram()
    changed["replay"]["evidence"]["description"] = "Explicit source move 41, checked caption"
    response = save(client, changed, sequence["updated_at"])
    assert response.status_code == 200, response.text
    review = response.json()["recognition_debug"]["calibration_review"]
    assert review["board"] == board["recognition_debug"]["calibration_review"]["board"]
    assert review["sequence"] is None


def test_legacy_verification_cannot_verify_unknown_v2_and_evidence_not_client_writable(workbench):
    client, _, _ = workbench
    value = diagram()
    value["unknown_stones"] = [{"point": [8, 8], "color": None}]
    value["replay"]["status"] = "needs_calibration"
    saved = save(client, value).json()
    assert (
        client.put(
            "/api/admin/tutorials/figures/1/verify", json={"expected_updated_at": saved["updated_at"]}
        ).status_code
        == 422
    )
    assert (
        client.put(
            "/api/admin/tutorials/figures/1/calibration",
            json={
                "board_payload": value,
                "expected_updated_at": saved["updated_at"],
                "recognition_debug": {"human_verified": True},
            },
        ).status_code
        == 422
    )


def test_legacy_unknown_points_roundtrip_without_silent_erasure():
    value = {"size": 19, "stones": {"B": [], "W": []}, "unknown_stones": [[3, 3]]}
    assert StrictBoardPayload.model_validate(value).model_dump(exclude_unset=True) == value


def test_candidate_on_supplemental_figure_keeps_shared_catalog_reference(workbench):
    from katrain.web.tutorials.recognition_import import import_candidate

    client, Session, _ = workbench
    with Session() as db:
        db.add(models_db.TutorialFigure(id=2, section_id=1, page=92, figure_label="extra", order=2))
        db.flush()
        import_candidate(
            db,
            source_book_id=1,
            dataset="first100-final",
            recognition_id="p092-f03-extra",
            figure_id=2,
            page=92,
            raw_result={"notes": "split diagram"},
            board_payload=diagram(),
            source_figure_id=1,
        )
        db.commit()
    figures = client.get("/api/admin/tutorials/books/1/workbench?page=92").json()["figures"]
    supplemental = next(item for item in figures if item["figure"]["id"] == 2)
    assert supplemental["source_references"][0]["source_figure_id"] == "p092-f03"


def test_first_manual_edit_preserves_preexisting_original_current(workbench):
    client, Session, _ = workbench
    original = {"size": 9, "stones": {"B": [[3, 3]], "W": []}}
    with Session() as db:
        db.execute(
            update(models_db.TutorialFigure)
            .where(models_db.TutorialFigure.id == 1)
            .values(board_payload=original, updated_at=None)
        )
        db.commit()
    response = save(client)
    assert response.status_code == 200, response.text
    history = client.get("/api/admin/tutorials/figures/1/history").json()["history"]
    assert history[0]["change_type"] == "original" and history[0]["board_payload"] == original
    assert history[1]["board_payload"] == diagram()


def test_legacy_default_size_is_saved_and_v2_missing_size_is_rejected(workbench):
    client, _, _ = workbench
    result = save(client, {"stones": {"B": [], "W": []}})
    assert result.status_code == 200, result.text
    assert result.json()["board_payload"]["size"] == 19
    value = diagram()
    value.pop("size")
    with pytest.raises(ValidationError):
        StrictBoardPayload.model_validate(value)


def test_pending_replay_initial_requires_explicit_both_stone_colors():
    for missing_color in ("B", "W"):
        value = diagram()
        value["replay"]["status"] = "needs_calibration"
        value["replay"]["initial"]["stones"].pop(missing_color)
        with pytest.raises(ValidationError, match="Initial state.*B and W"):
            StrictBoardPayload.model_validate(value)


def test_export_extent_distinguishes_confirmed_crop_from_full_board(workbench):
    from katrain.core.sgf_parser import SGF

    client, _, _ = workbench
    version = None
    for using_replay, full_board in ((False, False), (False, True), (True, False), (True, True)):
        value = diagram()
        region = {"col": 0, "row": 0, "cols": 9 if full_board else 3, "rows": 9 if full_board else 3}
        value["source_region"] = {**region, "confirmed": True}
        value["replay"]["initial"]["known_region"] = region
        value["replay"]["status"] = "complete" if using_replay else "needs_calibration"
        saved = save(client, value, version)
        assert saved.status_code == 200, saved.text
        version = saved.json()["updated_at"]
        exported = client.get("/api/admin/tutorials/figures/1/export.sgf")
        assert exported.status_code == 200, exported.text
        comment = SGF.parse_sgf(exported.text).get_property("C")
        assert f"unknown_extent={not full_board}" in comment
        assert f"known_region={region}" in comment
        assert f"outside_known_region={'known' if full_board else 'unknown'}" in comment
        if using_replay:
            assert f"initial_known_region={region}" in comment
        archive = client.get("/api/admin/tutorials/books/1/export.zip")
        assert archive.status_code == 200, archive.text
        with zipfile.ZipFile(io.BytesIO(archive.content)) as zipped:
            entry = json.loads(zipped.read("index.json"))["figures"][0]
            sidecar = json.loads(zipped.read(entry["json_file"]))
            assert (
                sidecar["extent"]
                == entry["extent"]
                == {
                    "source_known_region": region,
                    "outside_source_region_unknown": not full_board,
                    "initial_known_region": region if using_replay else None,
                    "outside_initial_known_region_unknown": not full_board if using_replay else None,
                    "unknown_extent": not full_board,
                }
            )


def test_accepted_collection_scopes_workbench_and_zip_preserving_legacy_and_current(workbench):
    from katrain.web.tutorials.recognition_import import content_sha256, import_candidate

    client, Session, _ = workbench
    protected = diagram()
    protected["labels"]["0,0"] = "human saved"
    saved = save(client, protected).json()
    verified = client.put(
        "/api/admin/tutorials/figures/1/verify-board", json={"expected_updated_at": saved["updated_at"]}
    )
    assert verified.status_code == 200, verified.text
    with Session() as db:
        db.add(models_db.TutorialFigure(id=2, section_id=1, page=92, figure_label="recognized extra", order=2))
        db.add(
            models_db.TutorialFigure(
                id=3,
                section_id=1,
                page=92,
                figure_label="legacy unlinked",
                order=3,
                board_payload={"size": 9, "stones": {"B": [[3, 3]], "W": []}},
            )
        )
        db.commit()
        db.execute(
            update(models_db.TutorialFigure)
            .where(models_db.TutorialFigure.id == 1)
            .values(narration="human narration", audio_asset="protected.mp3")
        )
        db.commit()
        figure = db.get(models_db.TutorialFigure, 1)
        original = {
            name: copy.deepcopy(getattr(figure, name))
            for name in ("board_payload", "recognition_debug", "narration", "audio_asset", "updated_at")
        }
    fallback = client.get("/api/admin/tutorials/books/1/workbench?page=92").json()
    assert {row["figure"]["id"] for row in fallback["figures"]} == {1, 2, 3}
    assert fallback["scope"]["dataset"] is None
    assert fallback["scope"]["physical_figure_count"] == 3
    assert fallback["scope"]["legacy_unlinked_count"] == 0
    with Session() as db:
        for recognition_id, figure_id, dataset in (
            ("p092-f03", 1, "ishida-full195-gpt61sol-v1"),
            ("p092-f04", 2, "ishida-full195-gpt61sol-v1"),
            ("p092-f04-related", 2, "ishida-full195-gpt61sol-v1"),
            ("old-experiment", 3, "unaccepted-experiment"),
        ):
            import_candidate(
                db,
                source_book_id=1,
                dataset=dataset,
                recognition_id=recognition_id,
                figure_id=figure_id,
                page=92,
                raw_result={"id": recognition_id},
                board_payload=diagram(),
            )
        db.commit()
    response = client.get("/api/admin/tutorials/books/1/workbench?page=92")
    assert response.status_code == 200, response.text
    default = response.json()
    assert {row["figure"]["id"] for row in default["figures"]} == {1, 2}
    assert default["scope"] == {
        "dataset": "ishida-full195-gpt61sol-v1",
        "physical_figure_count": 2,
        "legacy_unlinked_count": 1,
        "legacy_unlinked_label": "旧数据未关联",
    }
    page = next(item for item in default["pages"] if item["page"] == 92)
    assert (page["figure_count"], page["filtered_figure_count"], page["legacy_unlinked_count"]) == (2, 2, 1)
    pending = client.get("/api/admin/tutorials/books/1/workbench?page=92&filter=uncalibrated").json()
    assert [row["figure"]["id"] for row in pending["figures"]] == [2]
    legacy_response = client.get("/api/admin/tutorials/books/1/workbench?page=92&filter=legacy_unlinked")
    assert legacy_response.status_code == 200, legacy_response.text
    legacy = legacy_response.json()
    assert [row["figure"]["id"] for row in legacy["figures"]] == [3]
    assert legacy["figures"][0]["scope_label"] == "旧数据未关联"
    assert next(item for item in legacy["pages"] if item["page"] == 92)["filtered_figure_count"] == 1
    archive = client.get("/api/admin/tutorials/books/1/export.zip")
    assert archive.status_code == 200, archive.text
    with zipfile.ZipFile(io.BytesIO(archive.content)) as zipped:
        index = json.loads(zipped.read("index.json"))
        assert len([name for name in zipped.namelist() if name.endswith(".sgf")]) == 2
        assert {entry["figure_id"] for entry in index["figures"]} == {1, 2}
        assert index["scope"] == default["scope"]
        assert len(index["legacy_unlinked"]) == 1
        unlinked = index["legacy_unlinked"][0]
        assert unlinked["figure_id"] == 3 and unlinked["page"] == 92
        assert unlinked["figure_label"] == "legacy unlinked" and unlinked["status"] == "legacy_unlinked"
        assert "version" in unlinked and unlinked["reason"]
        current = next(entry for entry in index["figures"] if entry["figure_id"] == 1)
        assert current["version_kind"] == "current" and current["payload_sha256"] == content_sha256(protected)
        assert json.loads(zipped.read(current["json_file"]))["board_payload"] == protected
        assert next(entry for entry in index["figures"] if entry["figure_id"] == 2)["version_kind"] == "candidate"
    assert client.get("/api/admin/tutorials/figures/3/export.sgf").status_code == 200
    assert client.get("/api/admin/tutorials/figures/3/history").status_code == 200
    with Session() as db:
        figure = db.get(models_db.TutorialFigure, 1)
        assert {name: getattr(figure, name) for name in original} == original


def test_workbench_separates_playability_and_saved_board_review_without_inheriting_legacy_flags(workbench):
    from katrain.web.tutorials.recognition_import import import_candidate

    client, Session, _ = workbench
    assert save(client).status_code == 200  # Complete sourced replay, no human reviews.
    draft = diagram()
    draft["replay"]["status"] = "needs_calibration"
    with Session() as db:
        for figure_id, payload in ((2, {"size": 9, "stones": {"B": [[0, 0]], "W": []}}), (3, None), (4, draft)):
            db.add(
                models_db.TutorialFigure(
                    id=figure_id,
                    section_id=1,
                    page=92,
                    figure_label=str(figure_id),
                    order=figure_id,
                    board_payload=payload,
                    recognition_debug={"human_verified": True},
                )
            )
        db.flush()
        import_candidate(
            db,
            source_book_id=1,
            dataset="first100-final",
            recognition_id="p092-candidate-only",
            figure_id=3,
            page=92,
            raw_result={"id": "p092-candidate-only"},
            board_payload=draft,
        )
        db.commit()
    rows = client.get("/api/admin/tutorials/books/1/workbench?page=92").json()["figures"]
    by_id = {row["figure"]["id"]: row for row in rows}
    assert by_id[1]["replay"]["status"] == "complete" and by_id[1]["review"]["sequence"] is None
    assert {figure_id: row["board_review_status"] for figure_id, row in by_id.items()} == {
        1: "unreviewed",
        2: "legacy_verified",
        3: "unreviewed",
        4: "unreviewed",
    }
    pending = client.get("/api/admin/tutorials/books/1/workbench?page=92&filter=sequence_pending").json()["figures"]
    assert {row["figure"]["id"] for row in pending} == {2, 3, 4}
    uncalibrated = client.get("/api/admin/tutorials/books/1/workbench?page=92&filter=uncalibrated").json()["figures"]
    assert {row["figure"]["id"] for row in uncalibrated} == {1, 3, 4}
    with Session() as db:
        for figure_id in (2, 3, 4):
            assert db.get(models_db.TutorialFigure, figure_id).recognition_debug == {"human_verified": True}
