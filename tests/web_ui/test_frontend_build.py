import logging
import shutil

from katrain.web import server


def _fake_frontend_tree(tmp_path, monkeypatch, *, with_bundle: bool):
    web_dir = tmp_path / "katrain" / "web"
    ui_dir = web_dir / "ui"
    ui_dir.mkdir(parents=True)
    (ui_dir / "package.json").write_text("{}", encoding="utf-8")
    if with_bundle:
        static_dir = web_dir / "static-kiosk-2d"
        static_dir.mkdir()
        (static_dir / "index.html").write_text("<!doctype html>", encoding="utf-8")

    monkeypatch.setattr(server, "__file__", str(web_dir / "server.py"))
    monkeypatch.setattr(server.settings, "KATRAIN_MODE", "board")
    monkeypatch.setattr(shutil, "which", lambda executable: None)


def test_existing_kiosk_bundle_does_not_require_npm(tmp_path, monkeypatch, caplog):
    _fake_frontend_tree(tmp_path, monkeypatch, with_bundle=True)

    with caplog.at_level(logging.INFO, logger="katrain_web"):
        server.build_frontend(force=False)

    assert "Frontend already built" in caplog.text
    assert "npm not found" not in caplog.text


def test_missing_kiosk_bundle_without_npm_keeps_warning(tmp_path, monkeypatch, caplog):
    _fake_frontend_tree(tmp_path, monkeypatch, with_bundle=False)

    with caplog.at_level(logging.WARNING, logger="katrain_web"):
        server.build_frontend(force=False)

    assert "npm not found, skipping frontend build" in caplog.text
