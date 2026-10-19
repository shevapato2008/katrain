"""Real flock/process checks in temporary directories; no model or database calls."""

from contextlib import ExitStack
import fcntl
import importlib.util
import multiprocessing
import os
from pathlib import Path
import queue
import time

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts/recognize_tutorial_book.py"
LIMIT = "KATRAIN_TUTORIAL_REQUEST_LIMIT"
PREFER = "KATRAIN_TUTORIAL_REQUEST_PREFER_FROM"


def load_runner():
    spec = importlib.util.spec_from_file_location("request_slot_runner", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(autouse=True)
def clean_configuration(monkeypatch):
    monkeypatch.delenv(LIMIT, raising=False)
    monkeypatch.delenv(PREFER, raising=False)


def held_slots(directory):
    held = []
    for path in sorted(directory.glob("slot-*.lock")):
        with path.open("a+") as handle:
            try:
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                held.append(int(path.stem.split("-")[1]))
            else:
                fcntl.flock(handle, fcntl.LOCK_UN)
    return held


def test_default_preserves_three_slot_files(tmp_path):
    module = load_runner()
    with module.request_slot(tmp_path):
        assert held_slots(tmp_path) == [0]
        assert sorted(p.name for p in tmp_path.iterdir()) == [f"slot-{n}.lock" for n in range(3)]
    assert held_slots(tmp_path) == []


@pytest.mark.parametrize("limit,prefer", [(6, 3), (10, 6)])
def test_high_slots_are_preferred_then_wrap_to_zero(tmp_path, monkeypatch, limit, prefer):
    monkeypatch.setenv(LIMIT, str(limit))
    monkeypatch.setenv(PREFER, str(prefer))
    module = load_runner()
    with module.request_slot(tmp_path):
        assert held_slots(tmp_path) == [prefer]
    with (tmp_path / f"slot-{prefer}.lock").open("a+") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with module.request_slot(tmp_path):
            assert held_slots(tmp_path) == [prefer, prefer + 1]
    with ExitStack() as stack:
        for number in range(prefer, limit):
            handle = stack.enter_context((tmp_path / f"slot-{number}.lock").open("a+"))
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with module.request_slot(tmp_path):
            assert held_slots(tmp_path) == sorted([0, *range(prefer, limit)])
    assert held_slots(tmp_path) == []


def test_exception_releases_existing_slot_without_replacing_file(tmp_path):
    module = load_runner()
    with pytest.raises(RuntimeError, match="caller failed"):
        with module.request_slot(tmp_path):
            inode = (tmp_path / "slot-0.lock").stat().st_ino
            assert held_slots(tmp_path) == [0]
            raise RuntimeError("caller failed")
    assert held_slots(tmp_path) == []
    with module.request_slot(tmp_path):
        assert (tmp_path / "slot-0.lock").stat().st_ino == inode


@pytest.mark.parametrize(
    "limit,prefer",
    [
        ("0", None),
        ("-1", None),
        ("33", None),
        ("bad", None),
        ("", None),
        (None, "-1"),
        ("6", "6"),
        ("10", "x"),
        ("6", "1.5"),
    ],
)
def test_invalid_configuration_fails_before_creating_locks(tmp_path, monkeypatch, limit, prefer):
    if limit is not None:
        monkeypatch.setenv(LIMIT, limit)
    if prefer is not None:
        monkeypatch.setenv(PREFER, prefer)
    directory = tmp_path / "locks"
    with pytest.raises(ValueError, match="KATRAIN_TUTORIAL_REQUEST"):
        with load_runner().request_slot(directory):
            pytest.fail("Invalid configuration silently accepted")
    assert not directory.exists()


def slot_worker(directory, limit, prefer, active, maximum, ready, entered, release):
    # Unconfigured workers use the unchanged legacy 0..2 slot range. Configured
    # workers share those exact files plus higher numbered slots.
    for name, value in ((LIMIT, limit), (PREFER, prefer)):
        if value is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = str(value)
    module = load_runner()
    ready.put(True)
    with module.request_slot(Path(directory)):
        with active.get_lock():
            active.value += 1
            maximum.value = max(maximum.value, active.value)
        entered.put(True)
        assert release.wait(15), "Parent did not release isolated fixture workers"
        with active.get_lock():
            active.value -= 1


@pytest.mark.parametrize("limit,prefer", [(6, 3), (10, 6)])
def test_mixed_legacy_three_and_new_processes_share_total_cap(tmp_path, limit, prefer):
    context = multiprocessing.get_context("fork")
    active, maximum = context.Value("i", 0), context.Value("i", 0)
    ready, entered, release = context.Queue(), context.Queue(), context.Event()
    workers = []
    try:
        for _ in range(3):
            worker = context.Process(
                target=slot_worker, args=(str(tmp_path), None, None, active, maximum, ready, entered, release)
            )
            workers.append(worker)
            worker.start()
        for _ in range(3):
            ready.get(timeout=10)
            entered.get(timeout=10)
        assert held_slots(tmp_path) == [0, 1, 2]
        for _ in range(limit + 1):
            worker = context.Process(
                target=slot_worker, args=(str(tmp_path), limit, prefer, active, maximum, ready, entered, release)
            )
            workers.append(worker)
            worker.start()
        for _ in range(limit + 1):
            ready.get(timeout=10)
        for _ in range(limit - 3):
            entered.get(timeout=10)
        time.sleep(0.2)
        with pytest.raises(queue.Empty):
            entered.get_nowait()
        assert active.value == maximum.value == limit
        assert held_slots(tmp_path) == list(range(limit))
        release.set()
        for worker in workers:
            worker.join(10)
            assert worker.exitcode == 0
        assert maximum.value == limit and active.value == 0
    finally:
        release.set()
        for worker in workers:
            worker.join(2)
            if worker.is_alive():
                worker.terminate()  # Only this test's temporary fixture processes.
                worker.join(2)
        ready.close()
        entered.close()
