"""A new execution must not wake retired media producers or widen the cohort."""
import hashlib
import importlib.util
import json
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace

import pytest

PATH = Path(__file__).resolve().parents[2] / 'data/tutorial_media_batches/ogs-book-sources-20261113/provider.py'
EXECUTION = 'ogs-source-media-20261117-v1'


@pytest.fixture
def execution_client(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location('execution_provider', PATH)
    client = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(client)
    monkeypatch.setattr(client, 'HERE', tmp_path)
    monkeypatch.setenv('OGS_MEDIA_EXECUTION_ID', EXECUTION)
    snapshot = {'books': [{'book_id': 11, 'catalog_id': 'intro-up', 'figures': [{
        'figure': {'id': 4275, 'page': 10}, 'source_identity': {'source_pointer': '/one', 'image_sha256': 'source'},
        'source_error': None, 'board_sha256': 'board', 'current_board_approval': {'approved': True},
    }, {
        'figure': {'id': 4276, 'page': 10}, 'source_identity': {'source_pointer': '/two', 'image_sha256': 'source'},
        'source_error': None, 'board_sha256': 'board', 'current_board_approval': {'approved': True},
    }]}]}
    (tmp_path / 'snapshot.json').write_text(json.dumps(snapshot))
    directory = tmp_path / 'resume-full-20261117'
    directory.mkdir()
    authorization = {'generation_id': EXECUTION, 'status': 'running',
                     'snapshot_sha256': hashlib.sha256((tmp_path / 'snapshot.json').read_bytes()).hexdigest(),
                     'allowed_ids': [4275]}
    calls = []
    def run(cmd, **kwargs):
        calls.append((cmd, kwargs['input']))
        return SimpleNamespace(returncode=0, stdout=json.dumps({'http_status': 200, 'json': {'ok': True}}), stderr='')
    monkeypatch.setattr(client.subprocess, 'run', run)
    monkeypatch.setattr(client, 'ssh_exec_slot', nullcontext)
    def save(*, update_pointer=True):
        path = directory / 'execution-authorization.json'
        path.write_text(json.dumps(authorization))
        if update_pointer:
            (tmp_path / 'active-execution.json').write_text(json.dumps({
                'generation_id': EXECUTION, 'authorization_path': 'resume-full-20261117/execution-authorization.json',
                'authorization_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
            }))
    save()
    return client, authorization, save, calls


def write(client, fid=4275):
    return client.request('PUT', f'/figures/{fid}/narration', {'expected_updated_at': 'current', 'narration': '观察棋盘。'})


def test_matching_execution_ignores_retired_stop_but_retains_remote_guards(execution_client):
    client, _, _, calls = execution_client
    (client.HERE / 'books/intro-up').mkdir(parents=True)
    (client.HERE / 'books/intro-up/STOP').touch()
    old = client.HERE / 'resume-full-20261114'
    old.mkdir()
    (old / 'user-drain-request.json').write_text(json.dumps({'intent': 'explicit_user_drain_then_pause'}))
    assert write(client)['ok']
    assert len(calls) == 1
    script = calls[0][1]
    assert all(marker in script for marker in ['wrong_test_identity', 'source_changed', 'book_or_board_changed', 'current_generation_authorization_missing'])


@pytest.mark.parametrize('process_id', [None, 'retired-generation'])
def test_missing_or_old_process_execution_cannot_write(execution_client, monkeypatch, process_id):
    client, _, _, calls = execution_client
    if process_id is None: monkeypatch.delenv('OGS_MEDIA_EXECUTION_ID')
    else: monkeypatch.setenv('OGS_MEDIA_EXECUTION_ID', process_id)
    with pytest.raises(AssertionError, match='execution'):
        write(client)
    assert not calls


def test_prepared_is_not_permission_to_generate(execution_client):
    client, authorization, save, calls = execution_client
    authorization['status'] = 'prepared'; save()
    with pytest.raises(AssertionError, match='execution_not_running'):
        write(client)
    assert not calls


@pytest.mark.parametrize('change', ['authorization', 'snapshot'])
def test_authorization_or_snapshot_drift_revokes_local_admission(execution_client, change):
    client, authorization, save, calls = execution_client
    if change == 'authorization': authorization['allowed_ids'].append(4276); save(update_pointer=False)
    else:
        path = client.HERE / 'snapshot.json'; path.write_text(path.read_text() + '\n')
    with pytest.raises(AssertionError, match='execution_.*changed'):
        write(client)
    assert not calls


def test_out_of_authorized_scope_is_rejected(execution_client):
    client, _, _, calls = execution_client
    with pytest.raises(AssertionError, match='execution_figure_not_authorized'):
        write(client, 4276)
    assert not calls


@pytest.mark.parametrize('marker', ['PAUSE', 'CANCELLED.json', 'books/intro-up/resume-20261117/STOP'])
def test_global_and_current_book_stop_are_enforced(execution_client, marker):
    client, _, _, calls = execution_client
    path = client.HERE / marker; path.parent.mkdir(parents=True, exist_ok=True); path.touch()
    with pytest.raises(AssertionError, match='campaign_paused'):
        write(client)
    assert not calls


def test_unknown_write_has_one_attempt_under_new_execution(execution_client, monkeypatch):
    client, _, _, calls = execution_client
    def fail(cmd, **kwargs):
        calls.append(cmd)
        return SimpleNamespace(returncode=255, stdout='', stderr='Connection reset by peer')
    monkeypatch.setattr(client.subprocess, 'run', fail)
    with pytest.raises(RuntimeError, match='response unknown'):
        write(client)
    assert len(calls) == 1


def test_reads_need_no_write_execution(execution_client, monkeypatch):
    client, _, _, _ = execution_client
    monkeypatch.delenv('OGS_MEDIA_EXECUTION_ID')
    (client.HERE / 'PAUSE').touch()
    assert client.request('GET', '/figures/4275')['ok']
