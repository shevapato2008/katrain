import pytest
from pathlib import Path
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from katrain.web.core import models_db
from katrain.web.core.db import get_db
from katrain.web.tutorials.loader import TutorialLoader

FIXTURE_PATH = Path("data/tutorials_published")


@pytest.fixture
def client():
    from katrain.web.server import create_app

    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    models_db.Base.metadata.create_all(bind=engine)
    TestSession = sessionmaker(bind=engine)

    app = create_app()

    def override_db():
        db = TestSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_db

    loader = TutorialLoader(FIXTURE_PATH)
    loader.load()
    app.state.tutorial_loader = loader

    return TestClient(app)


def test_get_categories(client):
    resp = client.get("/api/v1/tutorials/categories")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["slug"] == "opening"


def test_get_topics(client):
    resp = client.get("/api/v1/tutorials/categories/opening/topics")
    assert resp.status_code == 200
    assert len(resp.json()) == 1
    assert resp.json()[0]["id"] == "topic_opening_001"


def test_get_topic(client):
    resp = client.get("/api/v1/tutorials/topics/topic_opening_001")
    assert resp.status_code == 200
    assert resp.json()["title"] == "角、边与中央的价值"


def test_get_topic_not_found(client):
    assert client.get("/api/v1/tutorials/topics/does_not_exist").status_code == 404


def test_get_topic_examples(client):
    resp = client.get("/api/v1/tutorials/topics/topic_opening_001/examples")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["id"] == "ex_opening_001"


def test_get_topic_examples_not_found(client):
    assert client.get("/api/v1/tutorials/topics/does_not_exist/examples").status_code == 404


def test_get_example(client):
    resp = client.get("/api/v1/tutorials/examples/ex_opening_001")
    assert resp.status_code == 200
    data = resp.json()
    assert data["step_count"] == 2
    assert len(data["steps"]) == 2


def test_example_not_found(client):
    assert client.get("/api/v1/tutorials/examples/does_not_exist").status_code == 404


def test_example_board_mode_image(client):
    data = client.get("/api/v1/tutorials/examples/ex_opening_001").json()
    for step in data["steps"]:
        assert step["board_mode"] == "image"
        assert step["board_payload"] is None


def test_example_no_forbidden_fields(client):
    data = client.get("/api/v1/tutorials/examples/ex_opening_001").json()
    forbidden = {"source_path", "raw_text", "source_id", "book_title", "author", "translator"}
    for step in data["steps"]:
        assert not forbidden.intersection(step.keys()), \
            f"Forbidden fields in step: {forbidden.intersection(step.keys())}"


def test_get_asset_image(client):
    resp = client.get("/api/v1/tutorials/assets/images/ex_opening_001_step_01.png")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("image/png")


def test_get_asset_not_found(client):
    assert client.get("/api/v1/tutorials/assets/images/missing.png").status_code == 404


def test_progress_requires_auth(client):
    # get_current_user raises HTTP 401 when no bearer token is present
    assert client.get("/api/v1/tutorials/progress").status_code == 401


def test_category_no_forbidden_fields(client):
    data = client.get("/api/v1/tutorials/categories").json()
    forbidden = {"source_path", "book_title", "author", "translator", "raw_text"}
    for cat in data:
        assert not forbidden.intersection(cat.keys())
