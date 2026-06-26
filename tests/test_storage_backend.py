"""Contract tests for the storage backend abstraction (tutorial media storage).

Task 1 of superpowers/tracks/tutorial-database/plan.md.

Covers the shared contract (normalize_key) and the LocalStorageBackend, which
must reproduce the current filesystem-under-``data/`` behaviour exactly so that
``STORAGE_BACKEND=local`` is a no-op relative to today.
"""
import io

import pytest

from katrain.web.core.storage import get_storage_backend
from katrain.web.core.storage.base import StorageBackend, normalize_key
from katrain.web.core.storage.local import LocalStorageBackend


# ── normalize_key (shared contract) ───────────────────────────────────────────

class TestNormalizeKey:
    def test_plain_relative_key_unchanged(self):
        assert normalize_key("tutorial_assets/slug/video/fig_1.mp4") == "tutorial_assets/slug/video/fig_1.mp4"

    def test_strips_leading_slash(self):
        assert normalize_key("/tutorial_assets/slug/x.mp3") == "tutorial_assets/slug/x.mp3"

    def test_strips_data_prefix(self):
        # DB / callers may pass a path that already includes the ASSET_BASE root.
        assert normalize_key("data/tutorial_assets/slug/x.mp4") == "tutorial_assets/slug/x.mp4"

    def test_collapses_backslashes(self):
        assert normalize_key("tutorial_assets\\slug\\x.mp4") == "tutorial_assets/slug/x.mp4"

    def test_rejects_parent_traversal(self):
        with pytest.raises(ValueError):
            normalize_key("../../etc/passwd")

    def test_rejects_embedded_traversal(self):
        with pytest.raises(ValueError):
            normalize_key("tutorial_assets/../../secret")

    def test_rejects_empty(self):
        with pytest.raises(ValueError):
            normalize_key("")


# ── LocalStorageBackend ───────────────────────────────────────────────────────

@pytest.fixture
def local_backend(tmp_path):
    return LocalStorageBackend(base_dir=tmp_path)


class TestLocalStorageBackend:
    KEY = "tutorial_assets/book/video/fig_1.mp4"
    DATA = b"\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09"

    def test_is_a_storage_backend(self, local_backend):
        assert isinstance(local_backend, StorageBackend)

    def test_is_not_remote(self, local_backend):
        # Local backend serves bytes through the app (Range), never a 302 redirect.
        assert local_backend.is_remote is False

    def test_put_then_exists(self, local_backend):
        assert local_backend.exists(self.KEY) is False
        local_backend.put(self.KEY, self.DATA)
        assert local_backend.exists(self.KEY) is True

    def test_put_accepts_fileobj(self, local_backend):
        local_backend.put(self.KEY, io.BytesIO(self.DATA))
        assert local_backend.read(self.KEY) == self.DATA

    def test_put_creates_nested_dirs(self, local_backend, tmp_path):
        local_backend.put(self.KEY, self.DATA)
        assert (tmp_path / self.KEY).is_file()

    def test_size(self, local_backend):
        local_backend.put(self.KEY, self.DATA)
        assert local_backend.size(self.KEY) == len(self.DATA)

    def test_read_full(self, local_backend):
        local_backend.put(self.KEY, self.DATA)
        assert local_backend.read(self.KEY) == self.DATA

    def test_read_range(self, local_backend):
        local_backend.put(self.KEY, self.DATA)
        assert local_backend.read_range(self.KEY, 2, 4) == self.DATA[2:6]

    def test_public_url_is_app_relative(self, local_backend):
        # Frontend tutorialApi.assetUrl() must keep working unchanged.
        assert local_backend.public_url(self.KEY) == f"/api/v1/tutorials/assets/{self.KEY}"

    def test_exists_missing_returns_false(self, local_backend):
        assert local_backend.exists("tutorial_assets/nope.mp4") is False

    def test_size_missing_raises(self, local_backend):
        with pytest.raises(FileNotFoundError):
            local_backend.size("tutorial_assets/nope.mp4")

    def test_key_is_normalized_on_access(self, local_backend):
        local_backend.put(self.KEY, self.DATA)
        # Leading slash / data prefix must resolve to the same object.
        assert local_backend.exists("/" + self.KEY) is True
        assert local_backend.exists("data/" + self.KEY) is True

    def test_traversal_rejected(self, local_backend):
        with pytest.raises(ValueError):
            local_backend.put("../escape.mp4", self.DATA)


# ── factory ───────────────────────────────────────────────────────────────────

class TestFactory:
    def test_default_backend_is_local(self, monkeypatch):
        from katrain.web.core import storage as storage_mod
        storage_mod._backend = None  # reset memoized singleton
        from katrain.web.core.config import settings
        monkeypatch.setattr(settings, "STORAGE_BACKEND", "local", raising=False)
        backend = get_storage_backend()
        assert isinstance(backend, LocalStorageBackend)

    def test_factory_returns_singleton(self):
        assert get_storage_backend() is get_storage_backend()


# ── upload_file (write-through helper, Task 6) ────────────────────────────────

class _RemoteLocal(LocalStorageBackend):
    """Local on disk but advertises is_remote=True (stands in for S3)."""

    is_remote = True


class TestUploadFile:
    def test_noop_for_local_backend(self, tmp_path, monkeypatch):
        from katrain.web.core import storage as storage_mod

        monkeypatch.setattr(storage_mod, "_backend", LocalStorageBackend(base_dir=tmp_path / "store"))
        src = tmp_path / "fig_1.mp4"
        src.write_bytes(b"abc")
        # Local backend = the disk store already; nothing to upload.
        assert storage_mod.upload_file("tutorial_assets/b/video/fig_1.mp4", src) is False

    def test_uploads_for_remote_backend(self, tmp_path, monkeypatch):
        from katrain.web.core import storage as storage_mod

        backend = _RemoteLocal(base_dir=tmp_path / "store")
        monkeypatch.setattr(storage_mod, "_backend", backend)
        src = tmp_path / "fig_1.mp4"
        src.write_bytes(b"abc")
        key = "tutorial_assets/b/video/fig_1.mp4"
        assert storage_mod.upload_file(key, src) is True
        assert backend.read(key) == b"abc"

    def test_swallows_missing_source(self, tmp_path, monkeypatch):
        from katrain.web.core import storage as storage_mod

        monkeypatch.setattr(storage_mod, "_backend", _RemoteLocal(base_dir=tmp_path / "store"))
        # Missing local file must not raise — returns False, logs a warning.
        assert storage_mod.upload_file("k.mp4", tmp_path / "nope.mp4") is False
