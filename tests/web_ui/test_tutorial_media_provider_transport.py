"""The batch client's local SSH bound does not weaken remote write guards."""
import importlib.util
import json
import multiprocessing
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]
PATH = ROOT / 'data/tutorial_media_batches/ogs-book-sources-20261113/provider.py'
spec = importlib.util.spec_from_file_location('media_batch_provider', PATH)
provider = importlib.util.module_from_spec(spec)
spec.loader.exec_module(provider)


@pytest.fixture(autouse=True)
def private_campaign(tmp_path, monkeypatch):
    """Transport checks must not depend on a developer's unversioned book data."""
    monkeypatch.setattr(provider, 'HERE', tmp_path)
    monkeypatch.setattr(provider, 'SSH_LOCK_DIRECTORY', tmp_path / 'transport-slots')
    snapshot = {'books': [{'book_id': 11, 'catalog_id': 'intro-up', 'figures': [{
        'figure': {'id': 4275, 'page': 10},
        'source_identity': {'source_pointer': '/one', 'image_sha256': 'source'},
        'source_error': None, 'board_sha256': 'board',
        'current_board_approval': {'approved': True},
    }]}]}
    (tmp_path / 'snapshot.json').write_text(json.dumps(snapshot))


def test_get_retry_keeps_book_master_and_uses_bounded_backoff(monkeypatch):
    calls = []
    sleeps = []
    def run(cmd, **kwargs):
        calls.append((cmd, kwargs['input']))
        if len(calls) == 1:
            return SimpleNamespace(returncode=255, stdout='', stderr='kex_exchange_identification: Connection reset by peer')
        return SimpleNamespace(returncode=0, stdout=json.dumps({'http_status': 200, 'json': {'ok': True}}), stderr='')
    monkeypatch.setattr(provider.subprocess, 'run', run)
    monkeypatch.setattr(provider.time, 'sleep', sleeps.append)
    assert provider.request('GET', '/figures/4275')['ok']
    assert len(calls) == 2 and 5 <= sleeps[0] <= 6
    for cmd, script in calls:
        assert 'ControlMaster=auto' in cmd
        assert 'ControlPath=none' not in cmd
        assert 'wrong_test_identity' in script and 'source_changed' in script
        assert 'current_generation_authorization_missing' in script


def test_unknown_write_is_never_retried(monkeypatch):
    # Execution admission is tested separately; this test isolates the SSH write policy.
    monkeypatch.setattr(provider, '_require_execution', lambda *args: None)
    calls = []
    def run(cmd, **kwargs):
        calls.append(cmd)
        return SimpleNamespace(returncode=255, stdout='', stderr='Connection reset by peer')
    monkeypatch.setattr(provider.subprocess, 'run', run)
    with pytest.raises(RuntimeError, match='response unknown'):
        provider.request('PUT', '/figures/4275/narration', {'expected_updated_at': '2026-11-14T00:00:00Z', 'narration': '观察棋盘。'})
    assert len(calls) == 1


def _hold_slot(start, active, peak):
    start.wait()
    with provider.ssh_exec_slot():
        with active.get_lock():
            active.value += 1
            peak.value = max(peak.value, active.value)
        time.sleep(0.15)
        with active.get_lock():
            active.value -= 1


def test_real_processes_share_four_exec_slots(tmp_path, monkeypatch):
    monkeypatch.setattr(provider, 'SSH_LOCK_DIRECTORY', tmp_path / 'slots')
    ctx = multiprocessing.get_context('fork')
    start = ctx.Event()
    active, peak = ctx.Value('i', 0), ctx.Value('i', 0)
    workers = [ctx.Process(target=_hold_slot, args=(start, active, peak)) for _ in range(8)]
    for worker in workers:worker.start()
    start.set()
    for worker in workers:
        worker.join(5)
        assert worker.exitcode == 0
    assert peak.value == 4
    assert active.value == 0
