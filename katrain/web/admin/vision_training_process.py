"""Fixed Linux worker process adapter; imported without starting a process.

Only this adapter may reap its private child. The same handle lock serializes
polling and signalling so a live/unreaped session leader cannot have a reused PID.
"""

import json
import os
import signal
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from threading import Event, RLock, Thread
from uuid import UUID

from katrain.web.admin.vision_training import MAX_LOG_BYTES, TrainingObservation, TrainingStartError

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


@dataclass
class _Handle:
    run_id: str
    run_dir: Path
    child: object
    lock: RLock = field(default_factory=RLock)
    drained: Event = field(default_factory=Event)
    log_total: int = 0
    log_observed: int = 0
    log_tail: bytes = b""
    reader: Thread | None = None


def _drain(handle):
    """Drain indefinitely but save at most 8MiB; never poll/wait/communicate."""
    saved = 0
    try:
        with (handle.run_dir / "worker.log").open("wb") as log:
            while block := handle.child.stdout.read(4096):
                with handle.lock:
                    handle.log_tail = (handle.log_tail + block)[-16 * 1024 :]
                    handle.log_total += len(block)
                writable = block[: max(0, MAX_LOG_BYTES - saved)]
                if writable:
                    log.write(writable)
                    log.flush()
                    saved += len(writable)
    finally:
        handle.child.stdout.close()
        handle.drained.set()


class TrainingProcessAdapter:
    persists_log = True

    def start(self, run_id, run_dir, spec):
        directory = Path(run_dir)
        try:
            if (
                sys.platform != "linux"
                or signal.getsignal(signal.SIGCHLD) != signal.SIG_DFL
                or str(UUID(run_id)) != run_id
                or directory.name != run_id
                or not directory.is_absolute()
                or directory.resolve() != directory
                or spec.get("run_id") != run_id
            ):
                raise ValueError("Unverified process launch boundary")
            path = directory / "spec.json"
            if path.is_symlink() or not 0 < path.stat().st_size <= 64 * 1024 or json.loads(path.read_bytes()) != spec:
                raise ValueError("Worker input differs from persisted run")
            child = subprocess.Popen(
                [sys.executable, "-m", "katrain.web.admin.vision_training_worker", str(path)],
                cwd=str(REPOSITORY_ROOT),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                start_new_session=True,
                bufsize=0,
            )
        except (OSError, ValueError, TypeError) as exc:
            raise TrainingStartError("Worker was not launched", group_exited=True) from exc
        handle = _Handle(run_id, directory, child)
        handle.reader = Thread(target=_drain, args=(handle,), daemon=True, name=f"vision-training-log-{run_id}")
        # A failure after Popen is intentionally not labelled 'no live process'.
        handle.reader.start()
        return handle

    def cancel(self, handle):
        with handle.lock:
            if handle.child.poll() is not None:
                return  # never signal an already reaped numeric process group
            pid = handle.child.pid
            if os.getpgid(pid) != pid or os.getsid(pid) != pid:
                raise RuntimeError("Run process-group ownership is unverified")
            try:
                os.killpg(pid, signal.SIGTERM)
            except ProcessLookupError:
                pass  # observe() still has to prove the whole group has gone

    def observe(self, handle):
        with handle.lock:
            exit_code = handle.child.poll()
            gone = False
            if exit_code is not None:
                try:
                    os.killpg(handle.child.pid, 0)
                except ProcessLookupError:
                    gone = True
                except OSError:
                    pass  # EPERM/unknown is not proof of exit
            chunk = ""
            pending = handle.log_total - handle.log_observed
            if pending > 0:
                chunk = handle.log_tail[-pending:].decode("utf-8", errors="replace")
                handle.log_observed = handle.log_total
            progress_path = handle.run_dir / "progress.json"
            epoch, metrics = None, None
            if progress_path.exists():
                if progress_path.is_symlink() or not 0 < progress_path.stat().st_size <= 64 * 1024:
                    raise RuntimeError("Invalid worker progress budget")
                progress = json.loads(progress_path.read_bytes())
                if progress.get("run_id") != handle.run_id:
                    raise RuntimeError("Worker progress belongs to a different run")
                epoch, metrics = progress.get("epoch"), progress.get("metrics")
            return TrainingObservation(
                handle.run_id,
                epoch=epoch,
                metrics=metrics,
                log_chunk=chunk,
                exit_code=exit_code,
                group_exited=gone and handle.drained.is_set(),
            )
