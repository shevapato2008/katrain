"""Explicit generation consent never becomes a manual board review."""

import copy
from types import SimpleNamespace

import pytest

from tests.web_ui.test_tutorial_media import media, current_version, enqueue
from katrain.web.core.models_db import TutorialFigure, TutorialMediaTask
from katrain.web.tutorials.manual_review import board_approval


@pytest.fixture
def consent(media, monkeypatch):
    from katrain.web.tutorials import generation_authorization as auth
    from katrain.web.tutorials.source_models import TutorialSourceBook, TutorialSourceFigure, TutorialSourcePage

    client, factory, worker, storage, app = media
    app.state.admin_config = SimpleNamespace(env="test")
    monkeypatch.setattr(auth, "is_test_database", lambda db: True)
    monkeypatch.setattr(auth, "require_service", lambda request: None)
    with factory() as db:
        figure = db.get(TutorialFigure, 1)
        figure.board_review = None
        figure.page_image_path = "test/page1.png"
        figure.recognition_debug = {"needs_manual_review": True, "concerns": ["uncertain stone"]}
        db.add(
            TutorialSourceBook(
                id=1,
                source_namespace="test",
                catalog_id="test",
                book_id=1,
                source_json_sha256="b" * 64,
                assets_manifest_sha256="c" * 64,
                source_metadata={},
                matching_evidence={},
            )
        )
        db.flush()
        db.add(
            TutorialSourceFigure(
                source_book_id=1,
                source_figure_id="test-1",
                source_pointer="/p/1",
                page=1,
                figure_id=1,
                source_metadata={},
            )
        )
        db.add(
            TutorialSourcePage(
                source_book_id=1,
                page=1,
                page_image_path=figure.page_image_path,
                image_sha256="a" * 64,
                text_fragments=[],
                page_context_text="",
            )
        )
        db.commit()
        identity = auth.generation_identity(figure, db)
        monkeypatch.setattr(auth, "COHORT", {"1": auth.digest(identity)})
    return media, auth


def grant(consent):
    (client, factory, *_), auth = consent
    return client.put(
        "/api/admin/tutorials/figures/1/authorize-generation",
        json={
            "expected_updated_at": current_version(factory),
            "cohort_id": auth.COHORT_ID,
        },
    )


def test_current_consent_allows_generation_without_manual_review(consent):
    (client, factory, worker, *_), auth = consent
    assert enqueue(client, version=current_version(factory)).status_code == 422
    response = grant(consent)
    assert response.status_code == 200, response.text
    with factory() as db:
        f = db.get(TutorialFigure, 1)
        assert not board_approval(f)["approved"]
        assert f.board_review is None
        assert f.recognition_debug["needs_manual_review"] is True
        assert f.recognition_debug["concerns"] == ["uncertain stone"]
        assert auth.generation_eligibility(f, db=db)["authorized"]
    response = enqueue(client, version=current_version(factory))
    assert response.status_code == 202, response.text
    assert worker.run_next()
    assert (
        client.get("/api/admin/tutorials/media-tasks/" + response.json()["task"]["id"]).json()["task"]["status"]
        == "succeeded"
    )
    with factory() as db:
        assert db.get(TutorialFigure, 1).board_review is None
        from katrain.web.tutorials.manual_review import video_problem

        assert "manual approval" in video_problem(db.get(TutorialFigure, 1), "2d", db=db)


@pytest.mark.parametrize("drift", ["board", "source", "source_version", "scope"])
def test_grant_rejects_current_drift_and_does_not_admit_task(consent, drift):
    (client, factory, worker, *_), auth = consent
    assert grant(consent).status_code == 200
    with factory() as db:
        f = db.get(TutorialFigure, 1)
        if drift == "board":
            value = copy.deepcopy(f.board_payload)
            value["stones"]["W"] = [[8, 8]]
            f.board_payload = value
        elif drift == "source":
            from katrain.web.tutorials.source_models import TutorialSourcePage

            db.get(TutorialSourcePage, 1).image_sha256 = "d" * 64
        elif drift == "source_version":
            from katrain.web.tutorials.source_models import TutorialSourceBook

            db.get(TutorialSourceBook, 1).source_json_sha256 = "d" * 64
        else:
            auth.COHORT.clear()
        db.commit()
        assert not auth.generation_eligibility(f, db=db)["authorized"]
    assert enqueue(client, version=current_version(factory)).status_code == 422
    assert grant(consent).status_code == 422


@pytest.mark.parametrize("boundary", ["claim", "publish"])
def test_grant_is_rechecked_after_enqueue(consent, boundary):
    (client, factory, worker, *_), auth = consent
    assert grant(consent).status_code == 200
    response = enqueue(client, version=current_version(factory))
    assert response.status_code == 202
    ident = response.json()["task"]["id"]
    if boundary == "publish":
        assert worker._claim_next()[0] == ident
    with factory() as db:
        f = db.get(TutorialFigure, 1)
        debug = copy.deepcopy(f.recognition_debug)
        debug.pop(auth.RECORD_KEY)
        f.recognition_debug = debug
        db.commit()
    if boundary == "claim":
        worker._claim_next()
    else:
        worker._publish(ident, {})
    with factory() as db:
        assert db.get(TutorialMediaTask, ident).status == "stale"


def test_consent_endpoint_retains_cas_and_test_boundary(consent, monkeypatch):
    (client, factory, worker, storage, app), auth = consent
    response = client.put(
        "/api/admin/tutorials/figures/1/authorize-generation",
        json={
            "expected_updated_at": "2000-01-01T00:00:00Z",
            "cohort_id": auth.COHORT_ID,
        },
    )
    assert response.status_code == 409
    app.state.admin_config.env = "production"
    assert grant(consent).status_code == 403
    app.state.admin_config.env = "test"
    monkeypatch.setattr(auth, "is_test_database", lambda db: False)
    assert grant(consent).status_code == 403


def test_consent_endpoint_requires_service_assertion(media):
    client, factory, worker, storage, app = media
    app.state.admin_config = SimpleNamespace(env="test")
    response = client.put(
        "/api/admin/tutorials/figures/1/authorize-generation",
        json={
            "expected_updated_at": current_version(factory),
            "cohort_id": "ogs-book-sources-20261113-user-generation-20261114",
        },
    )
    assert response.status_code == 403


def test_source_reference_accepts_consent_only_for_generation(consent):
    (_, factory, *_), auth = consent
    assert grant(consent).status_code == 200
    from katrain.web.tutorials.manual_review import presentation_source_identity
    from katrain.web.tutorials.source_models import TutorialSourceFigure, TutorialSourcePage

    with factory() as db:
        initial = db.get(TutorialFigure, 1)
        target = TutorialFigure(
            id=2,
            section_id=1,
            page=2,
            figure_label="图2",
            order=2,
            page_image_path="test/page2.png",
            board_payload=copy.deepcopy(initial.board_payload),
        )
        db.add(target)
        db.flush()
        db.add(
            TutorialSourceFigure(
                source_book_id=1,
                source_figure_id="test-2",
                source_pointer="/p/2",
                page=2,
                figure_id=2,
                source_metadata={},
            )
        )
        db.add(
            TutorialSourcePage(
                source_book_id=1,
                page=2,
                page_image_path=target.page_image_path,
                image_sha256="b" * 64,
                text_fragments=[],
                page_context_text="",
            )
        )
        db.commit()
        plan = {
            "forbidden_ko": {
                "initial_figure_id": 1,
                "initial_board_sha256": auth.digest(initial.board_payload),
                "initial_board_review_sha256": auth.digest(None),
            }
        }
        with pytest.raises(ValueError, match="manual approval"):
            presentation_source_identity(target, plan, db=db)
        identity = presentation_source_identity(target, plan, db=db, for_generation=True)
        assert identity["reference"]["generation_authorization_sha256"]
        assert initial.board_review is None


def test_exact_registered_correction_needs_a_new_versioned_grant(consent):
    (_, factory, *_), auth = consent
    assert grant(consent).status_code == 200
    with factory() as db:
        f = db.get(TutorialFigure, 1)
        original = auth.COHORT["1"]
        payload = copy.deepcopy(f.board_payload)
        payload["stones"]["W"] = [[8, 8]]
        f.board_payload = payload
        db.commit()
        corrected = auth.digest(auth.generation_identity(f, db))
        auth.COHORT["1"] = [original, corrected]
        assert not auth.generation_eligibility(f, db=db)["authorized"]
    assert grant(consent).status_code == 200
    with factory() as db:
        f = db.get(TutorialFigure, 1)
        assert auth.generation_eligibility(f, db=db)["authorized"]
        assert f.board_review is None
