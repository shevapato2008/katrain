"""Source-page reads use the existing protected admin app and isolated SQLite."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from katrain.web.core.models_db import Base, TutorialBook
from katrain.web.tutorials.source_models import TutorialSourceBook, TutorialSourceFigure, TutorialSourcePage


@pytest.fixture
def source_reader(monkeypatch, tmp_path):
    from katrain.web.admin.app import create_admin_app
    from katrain.web.admin.session import create_session_token

    monkeypatch.setenv("KATRAIN_MODE", "server")
    monkeypatch.setenv("KATRAIN_ADMIN_USERNAME", "admin:fan")
    monkeypatch.setenv("KATRAIN_ADMIN_PASSWORD_HASH", "$2b$12$" + "a" * 53)
    monkeypatch.setenv("KATRAIN_ADMIN_SESSION_SECRET", "source-page-test-session-secret-" + "x" * 32)
    monkeypatch.setenv("KATRAIN_ADMIN_ENV", "test")
    monkeypatch.delenv("KATRAIN_ADMIN_SERVICE_SECRET", raising=False)
    monkeypatch.delenv("KATRAIN_ADMIN_PROVIDER_ONLY", raising=False)
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    with factory() as db:
        db.add_all(
            [
                TutorialBook(
                    id=1, category="入门", subcategory="棋书", title="原页教材", slug="source-test", asset_dir="x"
                ),
                TutorialBook(
                    id=2, category="布局", subcategory="棋书", title="已有教材", slug="legacy-test", asset_dir="y"
                ),
            ]
        )
        db.flush()
        db.add(
            TutorialSourceBook(
                id=1,
                source_namespace="curriculum",
                catalog_id="test-book",
                book_id=1,
                source_json_sha256="a" * 64,
                assets_manifest_sha256="b" * 64,
                source_metadata={"private_path": "/Users/fan/private", "raw_metadata": {"secret": "hidden"}},
                matching_evidence={},
            )
        )
        db.flush()
        db.add_all(
            [
                TutorialSourcePage(
                    source_book_id=1,
                    page=7,
                    page_image_path="tutorial_assets/catalog/test-book/hash/page_007.png",
                    image_sha256="c" * 64,
                    page_context_text="原页文字，与讲解分开。",
                    text_fragments=[
                        {
                            "kind": "description",
                            "text": "原页文字，与讲解分开。",
                            "chapter_title": "章首",
                            "section_title": "导读",
                            "pointer": "/chapters/0/intro/0/elements/0",
                            "raw_metadata": {"path": "/Users/fan/private"},
                        },
                        {
                            "kind": "figure_ref",
                            "text": "尚未匹配的原图说明。",
                            "source_figure_id": "curriculum:test-book:p7:o1",
                            "chapter_title": "章首",
                            "section_title": "导读",
                            "pointer": "/chapters/0/intro/0/elements/1",
                        },
                    ],
                ),
                TutorialSourcePage(
                    source_book_id=1,
                    page=8,
                    page_image_path="tutorial_assets/catalog/test-book/hash/page_008.png",
                    image_sha256="d" * 64,
                    page_context_text="纯文字页。",
                    text_fragments=[
                        {
                            "kind": "description",
                            "text": "纯文字页。",
                            "chapter_title": "第二章",
                            "section_title": "",
                            "pointer": "/chapters/1/intro/0/elements/0",
                        }
                    ],
                ),
                TutorialSourceFigure(
                    source_book_id=1,
                    source_figure_id="curriculum:test-book:p7:o1",
                    source_pointer="/chapters/0/intro/0/elements/1",
                    page=7,
                    figure_id=None,
                    source_metadata={
                        "original_caption": {"label": "图 1", "text": "尚未匹配的原图说明。"},
                        "bbox": {"x_min": 0.1, "y_min": 0.2, "x_max": 0.5, "y_max": 0.6},
                        "raw_metadata": {"private_path": "/Users/fan/private"},
                    },
                    match_reason="No unambiguous legacy figure match",
                ),
            ]
        )
        db.commit()
    client = TestClient(create_admin_app(session_factory=factory, static_dir=tmp_path), raise_server_exceptions=False)
    headers = {"Authorization": f"Bearer {create_session_token('admin:fan', 'test')}"}
    try:
        yield client, headers, engine
    finally:
        client.close()
        engine.dispose()


def test_source_page_list_is_ordered_and_includes_text_only_pages(source_reader):
    client, headers, _ = source_reader
    response = client.get("/api/admin/tutorials/books/1/source-pages", headers=headers)
    assert response.status_code == 200, response.text
    assert response.json() == {
        "book_id": 1,
        "source_catalog_id": "test-book",
        "pages": [
            {
                "page": 7,
                "page_image_path": "tutorial_assets/catalog/test-book/hash/page_007.png",
                "has_text": True,
                "figure_count": 1,
            },
            {
                "page": 8,
                "page_image_path": "tutorial_assets/catalog/test-book/hash/page_008.png",
                "has_text": True,
                "figure_count": 0,
            },
        ],
    }


def test_page_detail_keeps_unmapped_caption_and_whitelists_metadata(source_reader):
    client, headers, _ = source_reader
    response = client.get("/api/admin/tutorials/books/1/source-pages/7", headers=headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert set(body) == {"book_id", "page", "page_image_path", "page_context_text", "text_fragments", "figures"}
    assert body["text_fragments"] == [
        {
            "kind": "description",
            "text": "原页文字，与讲解分开。",
            "source_figure_id": None,
            "chapter_title": "章首",
            "section_title": "导读",
            "source_pointer": "/chapters/0/intro/0/elements/0",
        },
        {
            "kind": "figure_ref",
            "text": "尚未匹配的原图说明。",
            "source_figure_id": "curriculum:test-book:p7:o1",
            "chapter_title": "章首",
            "section_title": "导读",
            "source_pointer": "/chapters/0/intro/0/elements/1",
        },
    ]
    assert body["figures"] == [
        {
            "source_figure_id": "curriculum:test-book:p7:o1",
            "figure_id": None,
            "figure_label": "图 1",
            "bbox": {"x_min": 0.1, "y_min": 0.2, "x_max": 0.5, "y_max": 0.6},
            "match_reason": "No unambiguous legacy figure match",
        }
    ]
    assert "/Users/" not in response.text
    assert "raw_metadata" not in response.text
    text_page = client.get("/api/admin/tutorials/books/1/source-pages/8", headers=headers)
    assert text_page.status_code == 200
    assert text_page.json()["figures"] == []


def test_source_pages_require_admin_and_return_explicit_missing_states(source_reader):
    client, headers, _ = source_reader
    assert client.get("/api/admin/tutorials/books/1/source-pages").status_code == 401
    assert client.get("/api/admin/tutorials/books/1/source-pages/7").status_code == 401
    assert client.get("/api/admin/tutorials/books/404/source-pages", headers=headers).status_code == 404
    assert client.get("/api/admin/tutorials/books/1/source-pages/404", headers=headers).status_code == 404
    legacy = client.get("/api/admin/tutorials/books/2/source-pages", headers=headers)
    assert legacy.status_code == 200
    assert legacy.json() == {"book_id": 2, "source_catalog_id": "", "pages": []}
    assert client.get("/api/admin/tutorials/books/2/source-pages/7", headers=headers).status_code == 404


def test_missing_provenance_tables_return_sanitized_503_without_ddl(source_reader):
    client, headers, engine = source_reader
    for table in (TutorialSourceFigure.__table__, TutorialSourcePage.__table__, TutorialSourceBook.__table__):
        table.drop(engine)
    before = set(inspect(engine).get_table_names())
    for path in ("/api/admin/tutorials/books/1/source-pages", "/api/admin/tutorials/books/1/source-pages/7"):
        response = client.get(path, headers=headers)
        assert response.status_code == 503, response.text
        assert response.json() == {"detail": "Tutorial source pages are unavailable"}
        assert "SELECT" not in response.text
    assert set(inspect(engine).get_table_names()) == before
