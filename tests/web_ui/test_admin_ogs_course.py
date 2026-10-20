"""The OGS course is read only and protected by the existing admin session."""

import io
import json
import zipfile

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from katrain.core.sgf_parser import SGF
from katrain.web.core.models_db import TutorialBook, TutorialChapter, TutorialFigure, TutorialSection
from test_ogs_course_import import sample_bundle


@pytest.fixture
def ogs_reader(monkeypatch, tmp_path):
    from katrain.web.admin.app import create_admin_app
    from katrain.web.admin.session import create_session_token
    from katrain.web.tutorials.ogs_import import create_ogs_tables, import_ogs_course

    for key, value in {
        "KATRAIN_MODE": "server",
        "KATRAIN_ADMIN_USERNAME": "admin:fan",
        "KATRAIN_ADMIN_PASSWORD_HASH": "$2b$12$" + "a" * 53,
        "KATRAIN_ADMIN_SESSION_SECRET": "ogs-test-secret-" + "x" * 40,
        "KATRAIN_ADMIN_ENV": "test",
    }.items():
        monkeypatch.setenv(key, value)
    monkeypatch.delenv("KATRAIN_ADMIN_SERVICE_SECRET", raising=False)
    monkeypatch.delenv("KATRAIN_ADMIN_PROVIDER_ONLY", raising=False)
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    for model in (TutorialBook, TutorialChapter, TutorialSection, TutorialFigure):
        model.__table__.create(engine)
    create_ogs_tables(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    imported = import_ogs_course(factory, sample_bundle())
    with factory.begin() as db:
        other = TutorialBook(category="入门", title="Other", slug="other", asset_dir="other")
        db.add(other)
        db.flush()
        other_id = other.id
    client = TestClient(create_admin_app(session_factory=factory, static_dir=tmp_path), raise_server_exceptions=False)
    headers = {"Authorization": f"Bearer {create_session_token('admin:fan', 'test')}"}
    yield client, headers, engine, imported["book_id"], other_id
    client.close()
    engine.dispose()


def test_index_and_step_only_return_the_requested_language(ogs_reader):
    client, headers, _, book_id, _ = ogs_reader
    response = client.get(f"/api/admin/tutorials/books/{book_id}/ogs-course", headers=headers)
    assert response.status_code == 200, response.text
    index = response.json()
    assert set(index) == {"book_id", "title", "source", "languages", "chapters", "lessons", "counts", "license_notice"}
    assert index["lessons"][0]["first_page"] == 1
    assert "steps" not in index and "AGPL" in index["license_notice"]
    response = client.get(f"/api/admin/tutorials/books/{book_id}/ogs-steps/1?lang=zh-cn", headers=headers)
    assert response.status_code == 200, response.text
    step = response.json()
    assert step["locale"] == {
        "requested": "zh-cn",
        "effective": "zh-cn",
        "text": {"title": "行棋", "instruction": "白先", "fallback": False},
    }
    assert "translations" not in step
    assert step["screenshot"] is None and step["screenshot_status"] == "pending"
    assert step["raw_source"]["config"]["white"] == "bbbb"
    fallback = client.get(f"/api/admin/tutorials/books/{book_id}/ogs-steps/1?lang=fr", headers=headers).json()
    assert fallback["locale"]["effective"] == "en"
    assert fallback["locale"]["text"]["instruction"] == "White to play"


def test_auth_book_page_and_language_boundaries(ogs_reader):
    client, headers, _, book_id, other_id = ogs_reader
    suffixes = ("ogs-course", "ogs-steps/1", "ogs-export")
    for suffix in suffixes:
        assert client.get(f"/api/admin/tutorials/books/{book_id}/{suffix}").status_code == 401
        assert client.get(f"/api/admin/tutorials/books/{other_id}/{suffix}", headers=headers).status_code == 404
    for page in (0, 2):
        assert client.get(f"/api/admin/tutorials/books/{book_id}/ogs-steps/{page}", headers=headers).status_code == 404
    assert (
        client.get(f"/api/admin/tutorials/books/{book_id}/ogs-steps/1?lang=invalid", headers=headers).status_code == 404
    )


def test_zip_keeps_branches_pass_colors_and_identity(ogs_reader):
    client, headers, _, book_id, _ = ogs_reader
    response = client.get(f"/api/admin/tutorials/books/{book_id}/ogs-export", headers=headers)
    assert response.status_code == 200, response.text
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        assert {"source.json", "index.json", "LICENSE"} <= set(archive.namelist())
        mapping = json.loads(archive.read("index.json"))["steps"][0]
        assert mapping["book_id"] == book_id and mapping["source_id"] == "ogs-learning:bl;3-skills-5:1"
        sgf = archive.read(mapping["sgf_path"]).decode()
        root = SGF.parse_sgf(sgf)
        assert root.get_property("SZ") == "9" and root.get_property("PL") == "W"
        assert len(root.children) == 2
        assert root.children[0].get_property("W") == "cc"
        assert root.children[0].children[0].get_property("B") == ""
        assert "correct" in root.children[0].children[0].get_property("C").lower()
        assert "wrong" in root.children[1].get_property("C").lower()


def test_missing_ogs_tables_return_sanitized_503_without_ddl(ogs_reader):
    from katrain.web.tutorials.ogs_models import TutorialOgsCourse, TutorialOgsStep

    client, headers, engine, book_id, _ = ogs_reader
    TutorialOgsStep.__table__.drop(engine)
    TutorialOgsCourse.__table__.drop(engine)
    before = inspect(engine).get_table_names()
    for suffix in ("ogs-course", "ogs-steps/1", "ogs-export"):
        response = client.get(f"/api/admin/tutorials/books/{book_id}/{suffix}", headers=headers)
        assert response.status_code == 503
        assert "SELECT" not in response.text
    assert inspect(engine).get_table_names() == before


def test_partial_translation_fallback_preserves_translated_fields():
    from types import SimpleNamespace
    from katrain.web.tutorials.ogs_course import step_output

    bundle = sample_bundle()
    payload = bundle["steps"][0]
    payload["translations"]["zh-cn"]["fallback"] = True
    output = step_output(1, SimpleNamespace(payload=payload, figure_id=1, screenshot=None), "zh-cn")
    assert output["locale"]["effective"] == "zh-cn"
    assert output["locale"]["text"]["instruction"] == "白先"
    assert output["locale"]["text"]["fallback"] is True
