"""Inject subprocess/OS boundaries: no process or GPU is launched."""

import io
import json
import signal
from uuid import uuid4

import pytest


class Child:
    pid = 4242
    stdout = io.BytesIO(b"epoch output\n")
    exit_code = None

    def poll(self):
        return self.exit_code


@pytest.fixture
def adapter(monkeypatch, tmp_path):
    from katrain.web.admin import vision_training_process as module

    child = Child()
    child.stdout = io.BytesIO(b"epoch output\n")
    calls = []

    def launch(argv, **kwargs):
        calls.append((argv, kwargs))
        return child

    monkeypatch.setattr(module.sys, "platform", "linux")
    monkeypatch.setattr(module.subprocess, "Popen", launch)
    monkeypatch.setattr(module.os, "getpgid", lambda pid: pid)
    monkeypatch.setattr(module.os, "getsid", lambda pid: pid)
    monkeypatch.setattr(module.signal, "getsignal", lambda sig: signal.SIG_DFL)
    run_id = str(uuid4())
    run = tmp_path / run_id
    run.mkdir()
    spec = {"run_id": run_id}
    (run / "spec.json").write_text(json.dumps(spec))
    service = module.TrainingProcessAdapter()
    handle = service.start(run_id, run, spec)
    handle.reader.join(timeout=1)
    return module, service, handle, child, calls


def test_launch_is_fixed_no_shell_and_log_is_bounded(adapter):
    module, service, handle, child, calls = adapter
    argv, options = calls[0]
    assert argv[1:3] == ["-m", "katrain.web.admin.vision_training_worker"]
    assert argv[-1] == str(handle.run_dir / "spec.json")
    assert options["start_new_session"] is True
    assert options.get("shell", False) is False
    assert options["stdin"] == module.subprocess.DEVNULL
    seen = service.observe(handle)
    assert seen.log_chunk == "epoch output\n" and seen.run_id == handle.run_id
    assert seen.group_exited is False


def test_cancel_only_signals_the_live_owned_session(adapter, monkeypatch):
    module, service, handle, child, calls = adapter
    signals = []
    monkeypatch.setattr(module.os, "killpg", lambda *args: signals.append(args))
    service.cancel(handle)
    assert signals == [(child.pid, signal.SIGTERM)]
    signals.clear()
    monkeypatch.setattr(module.os, "getpgid", lambda pid: pid + 1)
    with pytest.raises(RuntimeError):
        service.cancel(handle)
    assert not signals


def test_exited_leader_is_not_killed_and_group_disappearance_requires_esrch(adapter, monkeypatch):
    module, service, handle, child, calls = adapter
    child.exit_code = -15
    signals = []
    monkeypatch.setattr(module.os, "killpg", lambda *args: signals.append(args))
    service.cancel(handle)
    assert not signals
    assert service.observe(handle).group_exited is False
    assert signals == [(child.pid, 0)]

    def disappeared(*args):
        raise ProcessLookupError()

    monkeypatch.setattr(module.os, "killpg", disappeared)
    assert service.observe(handle).group_exited is True

    def forbidden(*args):
        raise PermissionError()

    monkeypatch.setattr(module.os, "killpg", forbidden)
    assert service.observe(handle).group_exited is False


def test_progress_for_different_run_is_rejected(adapter):
    module, service, handle, child, calls = adapter
    (handle.run_dir / "progress.json").write_text(json.dumps({"run_id": str(uuid4()), "epoch": 1, "metrics": {}}))
    with pytest.raises(RuntimeError):
        service.observe(handle)


def test_observation_reads_current_log_tail_without_poll_backlog(adapter):
    module, service, handle, child, calls = adapter
    log = b"old-epoch\n" * 4000 + b"latest-epoch\n"
    child.stdout = io.BytesIO(log)
    module._drain(handle)
    assert service.observe(handle).log_chunk.endswith("latest-epoch\n")
    assert service.observe(handle).log_chunk == ""


def test_latest_error_is_visible_after_saved_log_budget_is_full(adapter, monkeypatch):
    module, service, handle, child, calls = adapter
    monkeypatch.setattr(module, "MAX_LOG_BYTES", 64)
    child.stdout = io.BytesIO(b"old-log\n" * 100 + b"LATEST-TRAINING-ERROR\n")
    module._drain(handle)
    assert (handle.run_dir / "worker.log").stat().st_size == 64
    assert service.observe(handle).log_chunk.endswith("LATEST-TRAINING-ERROR\n")
