"""Concurrent anonymous downloads reuse one complete OGS-only source build."""
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from threading import Event

import pytest

from katrain.web.tutorials.ogs_source_cache import cached_source_zip


def test_concurrent_downloads_build_once_and_reuse_file(tmp_path, monkeypatch):
    from katrain.web.tutorials import ogs_course
    monkeypatch.setattr('katrain.web.tutorials.ogs_source_cache.tempfile.gettempdir', lambda: str(tmp_path))
    calls = []
    entered, release = Event(), Event()
    def build(db, book, course):
        calls.append(course.content_sha256)
        entered.set()
        assert release.wait(5)
        return b'complete zip bytes'
    monkeypatch.setattr(ogs_course, 'export_zip', build)
    course = SimpleNamespace(content_sha256='a' * 64)
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = [pool.submit(cached_source_zip, None, None, course) for _ in range(4)]
        assert entered.wait(5)
        release.set()
        paths = [future.result(5) for future in futures]
    assert len(calls) == 1
    assert len(set(paths)) == 1
    assert paths[0].read_bytes() == b'complete zip bytes'
    assert cached_source_zip(None, None, course) == paths[0]
    assert len(calls) == 1
    # A new content revision generates a distinct artifact.
    assert cached_source_zip(None, None, SimpleNamespace(content_sha256='b' * 64)) != paths[0]
    assert len(calls) == 2


def test_invalid_digest_never_builds_or_escapes_cache(tmp_path, monkeypatch):
    monkeypatch.setattr('katrain.web.tutorials.ogs_source_cache.tempfile.gettempdir', lambda: str(tmp_path))
    for digest in ('../outside', 'a' * 63, 'A' * 64):
        with pytest.raises(ValueError, match='digest'):
            cached_source_zip(None, None, SimpleNamespace(content_sha256=digest))
    assert list(tmp_path.iterdir()) == []


def test_failed_build_is_not_published_and_can_retry(tmp_path, monkeypatch):
    from katrain.web.tutorials import ogs_course
    monkeypatch.setattr('katrain.web.tutorials.ogs_source_cache.tempfile.gettempdir', lambda: str(tmp_path))
    def fail(*args):
        raise RuntimeError('export failed')
    monkeypatch.setattr(ogs_course, 'export_zip', fail)
    course = SimpleNamespace(content_sha256='c' * 64)
    with pytest.raises(RuntimeError):
        cached_source_zip(None, None, course)
    assert not list(tmp_path.rglob('*.zip'))
    assert not list(tmp_path.rglob('building-*'))
    monkeypatch.setattr(ogs_course, 'export_zip', lambda *args: b'retried')
    assert cached_source_zip(None, None, course).read_bytes() == b'retried'
