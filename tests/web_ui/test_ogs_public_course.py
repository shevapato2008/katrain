"""The imported OGS course is publicly readable without exposing source evidence."""

import copy
import subprocess
import sys
from textwrap import dedent

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from katrain.web.core.db import get_db
from katrain.web.core.models_db import TutorialBook, TutorialChapter, TutorialFigure, TutorialSection
from test_ogs_course_import import sample_bundle


def _client(factory):
    from katrain.web.server import create_app

    app = create_app(enable_engine=False)
    app.dependency_overrides[get_db] = lambda: factory()
    return TestClient(app, raise_server_exceptions=False)


def test_startup_keeps_ogs_tables_absent_and_public_reads_report_unavailable():
    # Fresh interpreter: other tests may have registered OGS models in Base.metadata.
    script = dedent(
        """
        from fastapi.testclient import TestClient
        from sqlalchemy import create_engine, inspect
        from sqlalchemy.orm import sessionmaker
        from sqlalchemy.pool import StaticPool
        from katrain.web.core.config import settings
        from katrain.web.core.db import Base, get_db
        from katrain.web.server import create_app

        engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        factory = sessionmaker(bind=engine)
        app = create_app(enable_engine=False)
        app.state.session_factory = factory
        app.dependency_overrides[get_db] = lambda: factory()
        settings.KATRAIN_MODE = "server"
        settings.SECRET_KEY = "ogs-public-test-secret-" + "x" * 40
        ogs_tables = {"tutorial_ogs_courses", "tutorial_ogs_steps"}
        assert not ogs_tables & set(Base.metadata.tables)
        assert not ogs_tables & set(inspect(engine).get_table_names())
        with TestClient(app, raise_server_exceptions=False) as client:
            assert not ogs_tables & set(inspect(engine).get_table_names())
            for path in ("ogs-course", "ogs-course/steps/1"):
                response = client.get(f"/api/v1/tutorials/{path}")
                assert response.status_code == 503, response.text
                assert "SELECT" not in response.text
            assert not ogs_tables & set(inspect(engine).get_table_names())
        engine.dispose()
        """
    )
    result = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.fixture
def imported_course():
    from katrain.web.tutorials.ogs_import import create_ogs_tables, import_ogs_course

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    for model in (TutorialBook, TutorialChapter, TutorialSection, TutorialFigure):
        model.__table__.create(engine)
    create_ogs_tables(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    bundle = sample_bundle()
    bundle["chapters"][0]["translations"]["zh-cn"] = {"title": "基础"}
    bundle["lessons"][0]["translations"]["zh-cn"] = {"title": "行棋", "subtext": "落子入门"}
    bundle["steps"][0]["viewport"] = {"col": 0, "row": 0, "cols": 5, "rows": 5}
    bundle["steps"][0]["shapes"] = {"2,2": "circle"}
    second_lesson = copy.deepcopy(bundle["lessons"][0])
    second_lesson.update(id="bl;3-skills-6", route="bl;3-skills-6", order=2, course_code="1.2", first_page=2)
    second_lesson["translations"]["en"]["title"] = "Captures"
    second_lesson["translations"]["zh-cn"]["title"] = "提子"
    bundle["lessons"].append(second_lesson)
    second_step = copy.deepcopy(bundle["steps"][0])
    second_step.update(source_id="ogs-learning:bl;3-skills-6:1", lesson_id="bl;3-skills-6", page=2)
    bundle["steps"].append(second_step)
    imported = import_ogs_course(factory, bundle)
    with factory.begin() as db:
        db.add(TutorialBook(category="入门", title="Other", slug="other", asset_dir="other"))
    client = _client(factory)
    yield client, imported, bundle
    client.close()
    engine.dispose()


def test_public_index_is_localized_ordered_and_anonymous(imported_course):
    client, imported, bundle = imported_course
    response = client.get("/api/v1/tutorials/ogs-course?lang=zh-cn")
    assert response.status_code == 200, response.text
    index = response.json()
    assert index["book_id"] == imported["book_id"]
    assert index["chapters"][0]["id"] == "basics"
    assert index["chapters"][0]["title"] == "基础"
    assert index["lessons"][0]["title"] == "行棋"
    assert index["lessons"][0]["subtext"] == "落子入门"
    assert index["lessons"][0]["first_page"] == 1
    assert index["lessons"][0]["step_count"] == 1
    assert [(lesson["id"], lesson["first_page"]) for lesson in index["lessons"]] == [
        ("bl;3-skills-5", 1),
        ("bl;3-skills-6", 2),
    ]
    assert index["chapters"][0]["lesson_count"] == 2
    assert index["chapters"][0]["step_count"] == 2
    assert index["counts"]["steps"] == 2
    assert index["source"]["commit"] == bundle["source"]["commit"]
    assert all("translations" not in item for item in index["chapters"] + index["lessons"])
    assert "license_text" not in index["source"]
    english = client.get("/api/v1/tutorials/ogs-course?lang=en").json()
    assert english["chapters"][0]["title"] == "Basics"
    assert english["lessons"][0]["title"] == "Moves"
    assert english["lessons"][1]["title"] == "Captures"


def test_public_step_has_board_exercise_and_only_selected_text(imported_course):
    client, imported, bundle = imported_course
    response = client.get("/api/v1/tutorials/ogs-course/steps/1?lang=zh-cn")
    assert response.status_code == 200, response.text
    step = response.json()
    source = bundle["steps"][0]
    assert step["book_id"] == imported["book_id"]
    assert step["source_id"] == source["source_id"]
    assert step["source_url"] == source["source_url"]
    assert step["lesson_id"] == source["lesson_id"] and step["page"] == 1
    assert step["size"] == 9 and step["initial_player"] == "W"
    assert step["stones"] == {"B": [[0, 0]], "W": [[1, 1]]}
    assert step["letters"] == source["letters"] and step["shapes"] == source["shapes"]
    assert step["viewport"] == source["viewport"]
    assert step["exercise"] == source["exercise"]
    assert step["locale"]["text"]["instruction"] == "白先"
    assert step["screenshot_status"] == "pending"
    assert "raw_source" not in step and "translations" not in step and "issues" not in step
    assert "White to play" not in response.text
    fallback = client.get("/api/v1/tutorials/ogs-course/steps/1?lang=fr").json()
    assert fallback["locale"]["effective"] == "en"
    assert fallback["locale"]["text"]["instruction"] == "White to play"
    second = client.get("/api/v1/tutorials/ogs-course/steps/2").json()
    assert (second["lesson_id"], second["page"]) == ("bl;3-skills-6", 2)


def test_public_course_rejects_unknown_language_and_page(imported_course):
    client, _, _ = imported_course
    for path in ("ogs-course", "ogs-course/steps/1"):
        assert client.get(f"/api/v1/tutorials/{path}?lang=invalid").status_code == 404
    for page in (0, 3):
        assert client.get(f"/api/v1/tutorials/ogs-course/steps/{page}").status_code == 404


def test_public_course_requires_imported_slug_and_course(imported_course):
    from katrain.web.tutorials.ogs_models import TutorialOgsCourse

    client, imported, _ = imported_course
    with client.app.dependency_overrides[get_db]() as db:
        book = db.get(TutorialBook, imported["book_id"])
        book.slug = "renamed-course"
        db.commit()
    for path in ("ogs-course", "ogs-course/steps/1"):
        assert client.get(f"/api/v1/tutorials/{path}").status_code == 404
    with client.app.dependency_overrides[get_db]() as db:
        book = db.get(TutorialBook, imported["book_id"])
        book.slug = "ogs-learn-to-play-go"
        db.query(TutorialOgsCourse).delete()
        db.commit()
    for path in ("ogs-course", "ogs-course/steps/1"):
        assert client.get(f"/api/v1/tutorials/{path}").status_code == 404


def test_missing_ogs_tables_are_503_without_creating_them(imported_course):
    from katrain.web.tutorials.ogs_models import TutorialOgsCourse, TutorialOgsStep

    client, _, _ = imported_course
    engine = client.app.dependency_overrides[get_db]().get_bind()
    TutorialOgsStep.__table__.drop(engine)
    TutorialOgsCourse.__table__.drop(engine)
    before = inspect(engine).get_table_names()
    for path in ("ogs-course", "ogs-course/steps/1"):
        response = client.get(f"/api/v1/tutorials/{path}")
        assert response.status_code == 503, response.text
        assert "SELECT" not in response.text
    assert inspect(engine).get_table_names() == before


def test_public_corresponding_source_is_anonymous_and_ogs_only(imported_course):
    import io
    import json
    import zipfile

    client, imported, bundle = imported_course
    response = client.get('/api/v1/tutorials/ogs-course/source.zip')
    assert response.status_code == 200
    assert response.headers['content-type'] == 'application/zip'
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        assert set(archive.namelist()) == {'source.json', 'index.json', 'LICENSE', 'README.txt', 'sgf/0001.sgf', 'sgf/0002.sgf'}
        source = json.loads(archive.read('source.json'))
        assert source['source'] == bundle['source']
        assert len(source['steps']) == 2
        assert source['steps'][0]['raw_source'] == bundle['steps'][0]['raw_source']
        assert archive.read('LICENSE').decode() == bundle['source']['license_text']
        notice = archive.read('README.txt').decode()
        assert 'AGPL-3.0-or-later' in notice and '2026-10-24' in notice
        assert 'TEST' not in notice and 'commercial authorization' not in notice


def test_public_step_kiosk_variant_is_explicit_and_source_download_stays_original(imported_course, monkeypatch):
    import sys
    from types import SimpleNamespace

    client, _, _ = imported_course
    original = client.get("/api/v1/tutorials/ogs-course/steps/1").json()
    source_archive = client.get("/api/v1/tutorials/ogs-course/source.zip").content
    calls = []
    derived = {**original, "size": 19, "viewport": None, "board_variant": {"status": "adapted"}}
    monkeypatch.setitem(
        sys.modules,
        "katrain.web.content.board_variants",
        SimpleNamespace(
            adapt_ogs_step=lambda step: calls.append(step) or derived,
        ),
    )
    assert client.get("/api/v1/tutorials/ogs-course/steps/1").json() == original
    assert calls == []
    response = client.get("/api/v1/tutorials/ogs-course/steps/1?board_variant=kiosk19")
    assert response.status_code == 200 and response.json() == derived
    assert calls == [original]
    assert client.get("/api/v1/tutorials/ogs-course/source.zip?board_variant=kiosk19").content == source_archive
