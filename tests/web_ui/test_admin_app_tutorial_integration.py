"""The independent admin site serves read-only tutorial data and admin writes."""

from fastapi.testclient import TestClient
from passlib.context import CryptContext
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from katrain.web.core.models_db import Base, TutorialBook, TutorialChapter, TutorialFigure, TutorialSection


def test_admin_app_mounts_real_tutorial_reads_and_versioned_writes(monkeypatch, tmp_path):
    from katrain.web.admin.app import create_admin_app

    monkeypatch.setenv("KATRAIN_ADMIN_USERNAME", "admin:fan")
    monkeypatch.setenv("KATRAIN_ADMIN_PASSWORD_HASH", CryptContext(schemes=["bcrypt"]).hash("local-only-password"))
    monkeypatch.setenv("KATRAIN_ADMIN_SESSION_SECRET", "s" * 48)
    monkeypatch.setenv("KATRAIN_ADMIN_ENV", "test")
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    factory = sessionmaker(bind=engine)
    try:
        with factory() as db:
            book = TutorialBook(
                category="入门",
                subcategory="棋书",
                title="真实测试教材",
                slug="local-book",
                asset_dir="tutorial_assets/local-book/pages",
            )
            db.add(book)
            db.flush()
            chapter = TutorialChapter(book_id=book.id, chapter_number="1", title="第一章", order=1)
            db.add(chapter)
            db.flush()
            section = TutorialSection(chapter_id=chapter.id, section_number="1", title="第一节", order=1)
            db.add(section)
            db.flush()
            figure = TutorialFigure(
                section_id=section.id,
                page=1,
                figure_label="图 1",
                narration="原讲解",
                board_payload={"size": 19, "stones": {"B": [], "W": []}},
                order=1,
            )
            db.add(figure)
            db.commit()
            figure_id = figure.id

        client = TestClient(create_admin_app(session_factory=factory, static_dir=tmp_path))
        login = client.post("/api/admin/auth/login", json={"username": "admin:fan", "password": "local-only-password"})
        assert login.status_code == 200
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

        books = client.get("/api/v1/tutorials/categories/入门/books")
        assert books.status_code == 200
        assert books.json()[0]["title"] == "真实测试教材"
        detail = client.get(f"/api/v1/tutorials/figures/{figure_id}")
        assert detail.status_code == 200
        assert detail.json()["narration"] == "原讲解"
        assert (
            client.put(
                f"/api/admin/tutorials/figures/{figure_id}/narration",
                json={"narration": "新讲解", "expected_updated_at": detail.json()["updated_at"]},
            ).status_code
            == 401
        )
        updated = client.put(
            f"/api/admin/tutorials/figures/{figure_id}/narration",
            headers=headers,
            json={"narration": "新讲解", "expected_updated_at": detail.json()["updated_at"]},
        )
        assert updated.status_code == 200, updated.text
        assert client.get(f"/api/v1/tutorials/figures/{figure_id}").json()["narration"] == "新讲解"
        from katrain.web.core.config import settings

        with monkeypatch.context() as media_settings:
            media_settings.setattr(settings, "STORAGE_BACKEND", "s3")
            media_settings.setattr(settings, "S3_PUBLIC_BASE_URL", "https://media.example.test/tutorial-assets")
            media_client = TestClient(create_admin_app(session_factory=factory, static_dir=tmp_path))
            policy = media_client.get("/api/admin/health").headers["content-security-policy"]
            assert "img-src 'self' data: https://media.example.test" in policy
            assert "media-src 'self' https://media.example.test" in policy
    finally:
        engine.dispose()
