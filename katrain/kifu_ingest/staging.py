"""Crash-safe, database-free staging for incremental kifu collection."""

from contextlib import contextmanager
import errno
import fcntl
import hashlib
import json
import os
import re
import stat
import tempfile
import time
from pathlib import Path

from katrain.core.sgf_parser import SGF
from katrain.kifu_ingest.source_19x19 import SourceBudgetExceeded, SourceError, SourceRateLimited


def _id(value):
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        raise ValueError("external_id must be numeric")
    result = str(value)
    if not re.fullmatch(r"[0-9]+", result):
        raise ValueError("external_id must contain only digits")
    return result


@contextmanager
def staging_writer_lock(root):
    """Exclusive nonblocking writer lock shared by hourly and manual writers.

    Acquire before constructing Stage, so its in-memory manifest cannot be stale.
    The production scheduler must use this lock too (or be stopped for maintenance).
    """
    root = Path(root)
    if not root.is_absolute() or root.is_symlink():
        raise ValueError("staging root must be an absolute non-symlink directory")
    root = root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    path = root / ".writer.lock"
    fd = os.open(path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise ValueError("writer lock must be a regular file")
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


class Stage:
    """One independent manifest plus raw SGF and metadata sidecars under an absolute root."""

    def __init__(self, root):
        root = Path(root)
        if not root.is_absolute() or root.is_symlink():
            raise ValueError("staging root must be an absolute non-symlink directory")
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self.sgf_dir = self._directory("sgf")
        self.metadata_dir = self._directory("metadata")
        self.manifest_path = self.root / "manifest.json"
        if self.manifest_path.is_symlink():
            raise ValueError("manifest symlink is unsafe")
        if self.manifest_path.exists():
            self.manifest = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        else:
            self.manifest = {
                "version": 1,
                "source_key": "19x19",
                "items": {},
                "rolling_cursor": 0,
                "head": {},
                "rolling": {},
            }
            self._persist()

    def _directory(self, name):
        path = self.root / name
        if path.is_symlink():
            raise ValueError("staging directory symlink is unsafe")
        path.mkdir(exist_ok=True)
        return path

    @staticmethod
    def _atomic(path, data):
        if path.is_symlink():
            raise ValueError("staging target symlink is unsafe")
        fd, temporary = tempfile.mkstemp(prefix=".writing-", suffix=".tmp", dir=path.parent)
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            if path.is_symlink():
                raise ValueError("staging target symlink is unsafe")
            os.replace(temporary, path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    def _persist(self):
        payload = json.dumps(self.manifest, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")
        self._atomic(self.manifest_path, payload)

    def items(self):
        return list(self.manifest["items"].values())

    def _rank_decision_path(self, game):
        from katrain.kifu_ingest.ranks import rank_decision_request
        from katrain.web.kifu.name_candidates import canonical_sha256

        request = rank_decision_request(game)
        digest = canonical_sha256(request)
        directory = self.root / "rank-snapshots"
        if directory.is_symlink() or directory.exists() and not directory.is_dir():
            raise ValueError("rank checkpoint directory unsafe")
        path = directory / f"{digest}.json"
        if path.is_symlink():
            raise ValueError("rank checkpoint symlink unsafe")
        return path, request, digest

    @staticmethod
    def _validate_rank_decision(game, decision):
        from katrain.kifu_ingest.ranks import FORMAT_V2, validate_manifest_ranks

        if not isinstance(decision, dict) or set(decision) != {"rank_snapshots", "rank_observations", "rank_facts"}:
            raise ValueError("rank checkpoint decision invalid")
        validate_manifest_ranks(
            {
                "format": FORMAT_V2,
                "games": [{**game, **{key: decision[key] for key in ("rank_snapshots", "rank_observations")}}],
                "rank_facts": decision["rank_facts"],
            }
        )

    def load_rank_decision(self, game):
        """Load the entire immutable decision, including an explicit unknown."""
        from katrain.web.kifu.name_candidates import canonical_sha256

        path, request, digest = self._rank_decision_path(game)
        try:
            fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        except FileNotFoundError:
            return None
        except OSError as exc:
            raise ValueError("rank checkpoint unsafe") from exc
        with os.fdopen(fd, "rb") as handle:
            info = os.fstat(handle.fileno())
            if not stat.S_ISREG(info.st_mode) or not 0 < info.st_size <= 16 * 1024 * 1024:
                raise ValueError("rank checkpoint exceeds limit or is not a regular file")
            raw = handle.read(info.st_size + 1)
            if len(raw) != info.st_size or os.fstat(handle.fileno()).st_size != info.st_size:
                raise ValueError("rank checkpoint changed during read")
        try:
            record = json.loads(raw)
            if (
                set(record) != {"version", "request", "request_sha256", "decision", "decision_sha256"}
                or type(record["version"]) is not int
                or record["version"] != 1
                or record["request"] != request
                or record["request_sha256"] != digest
                or canonical_sha256(record["request"]) != digest
                or canonical_sha256(record["decision"]) != record["decision_sha256"]
            ):
                raise ValueError("rank checkpoint binding mismatch")
            self._validate_rank_decision(game, record["decision"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("rank checkpoint invalid") from exc
        return record["decision"]

    def save_rank_decision(self, game, decision):
        """Persist once; a retry must reuse rather than replace a frozen grade."""
        from katrain.web.kifu.name_candidates import canonical_sha256

        path, request, digest = self._rank_decision_path(game)
        existing = self.load_rank_decision(game)
        if existing is not None:
            if existing != decision:
                raise ValueError("rank decision is already frozen")
            return
        self._validate_rank_decision(game, decision)
        payload = json.dumps(
            {
                "version": 1,
                "request": request,
                "request_sha256": digest,
                "decision": decision,
                "decision_sha256": canonical_sha256(decision),
            },
            ensure_ascii=False,
            sort_keys=True,
            allow_nan=False,
        ).encode("utf-8")
        if len(payload) > 16 * 1024 * 1024:
            raise ValueError("rank checkpoint exceeds limit")
        path.parent.mkdir(mode=0o700, exist_ok=True)
        os.chmod(path.parent, 0o700)
        # Link the fully fsynced temporary file without overwriting an existing decision.
        fd, temporary = tempfile.mkstemp(dir=path.parent, prefix=".rank-")
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            try:
                os.link(temporary, path)
            except FileExistsError:
                if self.load_rank_decision(game) != decision:
                    raise ValueError("rank decision is already frozen")
            for directory in (path.parent, self.root):
                directory_fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
                try:
                    os.fsync(directory_fd)
                finally:
                    os.close(directory_fd)
        finally:
            os.unlink(temporary)

    def _name_decision_path(self, request):
        from katrain.web.kifu.name_candidates import canonical_sha256

        if (
            not isinstance(request, dict)
            or set(request) != {"kind", "key", "source_items", "context", "template_sources"}
            or not isinstance(request["source_items"], list)
            or not request["source_items"]
        ):
            raise ValueError("name decision checkpoint request invalid")
        try:
            digest = canonical_sha256(request)
        except (TypeError, ValueError) as exc:
            raise ValueError("name decision checkpoint request must be JSON") from exc
        directory = self.root / "name-decisions"
        if directory.is_symlink() or directory.exists() and not directory.is_dir():
            raise ValueError("name decision checkpoint directory unsafe")
        path = directory / f"{digest}.json"
        if path.is_symlink():
            raise ValueError("name decision checkpoint symlink unsafe")
        return path, digest

    @staticmethod
    def _validate_name_decision(request, decision):
        from katrain.kifu_ingest.catalog import validate_decision
        from katrain.web.kifu.name_candidates import canonical_sha256

        try:
            validate_decision(decision)
            if (
                decision["kind"] != request["kind"]
                or decision["key"] != request["key"]
                or sorted(decision["source_items"], key=canonical_sha256)
                != sorted(request["source_items"], key=canonical_sha256)
            ):
                raise ValueError("name decision differs from exact checkpoint request")
            return canonical_sha256(decision)
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("name decision checkpoint review or binding invalid") from exc

    def load_name_decision(self, request):
        """Load a complete reviewed decision only for this exact finite request."""
        from katrain.web.kifu.name_candidates import canonical_sha256

        path, digest = self._name_decision_path(request)
        if not path.exists():
            return None
        if not path.is_file():
            raise ValueError("name decision checkpoint must be a regular file")
        try:
            fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        except FileNotFoundError:
            return None
        except OSError as exc:
            if exc.errno == errno.ELOOP:
                raise ValueError("name decision checkpoint symlink unsafe") from exc
            raise
        with os.fdopen(fd, "rb") as handle:
            info = os.fstat(handle.fileno())
            if not stat.S_ISREG(info.st_mode) or not 0 < info.st_size <= 1024 * 1024:
                raise ValueError("name decision checkpoint exceeds size limit or is not a file")
            raw = handle.read(info.st_size)
            if len(raw) != info.st_size or os.fstat(handle.fileno()).st_size != info.st_size:
                raise ValueError("name decision checkpoint changed during read")
        try:
            record = json.loads(raw)
            if (
                not isinstance(record, dict)
                or set(record) != {"version", "request_sha256", "request", "decision", "decision_content_sha256"}
                or type(record["version"]) is not int
                or record["version"] != 1
                or record["request_sha256"] != digest
                or record["request"] != request
                or canonical_sha256(record["request"]) != digest
                or record["decision_content_sha256"] != self._validate_name_decision(request, record["decision"])
            ):
                raise ValueError("name decision checkpoint content mismatch")
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("name decision checkpoint invalid") from exc
        return record["decision"]

    def save_name_decision(self, request, decision):
        """Atomically retain the actual review and all its signed finite members."""
        path, digest = self._name_decision_path(request)
        decision_digest = self._validate_name_decision(request, decision)
        payload = json.dumps(
            {
                "version": 1,
                "request_sha256": digest,
                "request": request,
                "decision": decision,
                "decision_content_sha256": decision_digest,
            },
            ensure_ascii=False,
            sort_keys=True,
            allow_nan=False,
        ).encode("utf-8")
        if len(payload) > 1024 * 1024:
            raise ValueError("name decision checkpoint exceeds size limit")
        new_directory = not path.parent.exists()
        path.parent.mkdir(mode=0o700, exist_ok=True)
        os.chmod(path.parent, 0o700)
        self._atomic(path, payload)
        # _atomic fsyncs the file. Also persist its rename and the lazy directory.
        for directory in (path.parent, self.root) if new_directory else (path.parent,):
            fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(fd)
            finally:
                os.close(fd)

    def remember(self, metadata):
        if not isinstance(metadata, dict):
            raise ValueError("metadata must be an object")
        external_id = _id(metadata.get("id"))
        # Original source metadata is immutable, just like its raw SGF.
        if external_id in self.manifest["items"]:
            return self.manifest["items"][external_id]
        path = self.metadata_dir / f"{external_id}.json"
        self._atomic(path, json.dumps(metadata, ensure_ascii=False, sort_keys=True).encode("utf-8"))
        items = self.manifest["items"]
        if external_id not in items:
            items[external_id] = {
                "source_key": "19x19",
                "external_id": external_id,
                "metadata": metadata,
                "raw_sgf_path": None,
                "raw_sha256": None,
                "status": "pending",
                "last_error": None,
                "attempts": 0,
                "next_retry_at": None,
            }
        self._persist()
        return items[external_id]

    def save_sgf(self, external_id, raw_sgf):
        external_id = _id(external_id)
        if external_id not in self.manifest["items"]:
            raise ValueError("external_id must be remembered before SGF download")
        if not isinstance(raw_sgf, str) or not raw_sgf.strip():
            raise ValueError("SGF must be nonempty text")
        if not raw_sgf.lstrip().startswith("(;") or not raw_sgf.rstrip().endswith(")"):
            raise ValueError("invalid SGF structure")
        try:
            SGF.parse_sgf(raw_sgf)
        except (ValueError, IndexError, AttributeError, TypeError) as exc:
            raise ValueError("invalid SGF") from exc
        raw = raw_sgf.encode("utf-8")
        digest = hashlib.sha256(raw).hexdigest()
        path = self.sgf_dir / f"{external_id}.sgf"
        if path.is_symlink():
            raise ValueError("staging target symlink is unsafe")
        if path.exists() and hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError("same ID has different SGF content")
        if not path.exists():
            self._atomic(path, raw)
        item = self.manifest["items"][external_id]
        item.update(raw_sgf_path=str(path), raw_sha256=digest, status="downloaded", last_error=None, next_retry_at=None)
        self._persist()
        return path

    def fail(self, external_id, error, *, wall_clock=time.time):
        item = self.manifest["items"][_id(external_id)]
        item["status"] = "failed"
        item["attempts"] += 1
        item["last_error"] = str(error)
        item["next_retry_at"] = (
            wall_clock() + getattr(error, "retry_after", 0) if getattr(error, "retryable", True) else None
        )
        self._persist()


async def discover_and_download(
    source,
    stage: Stage,
    known_ids=(),
    *,
    max_head_pages=20,
    max_rolling_pages=100,
    max_downloads=100,
    deadline=None,
    clock=None,
    wall_clock=None,
):
    """Discover bounded head/rolling pages and download saved pending IDs.

    `deadline` is an absolute value from `clock` (monotonic by default).
    A successful empty rolling page is the only signal for a completed pass.
    """
    clock = clock or time.monotonic
    wall_clock = wall_clock or time.time
    known = {_id(value) for value in known_ids}
    if max_head_pages < 0 or max_rolling_pages < 0 or max_downloads < 0:
        raise ValueError("budgets cannot be negative")
    downloaded = 0
    failures = 0
    consecutive_failures = 0
    rolling_complete = False
    partial = False
    attempted = set()
    errors = []

    def result():
        backlog = any(item["status"] != "downloaded" for item in stage.items())
        return {
            "status": "caught_up" if rolling_complete and not partial and not backlog else "partial",
            "items": stage.items(),
            "downloaded": downloaded,
            "failures": failures,
            "errors": errors,
            "last_error": errors[-1]["error"] if errors else None,
            "head": stage.manifest["head"],
            "rolling": stage.manifest["rolling"],
            "deferred_until": stage.manifest.get("source_next_retry_at"),
        }

    def record_error(error, **context):
        nonlocal failures, consecutive_failures
        errors.append({**context, "error": str(error)})
        failures += 1
        consecutive_failures += 1

    if (stage.manifest.get("source_next_retry_at") or 0) > wall_clock():
        partial = True
        return result()
    if stage.manifest.get("source_next_retry_at"):
        stage.manifest["source_next_retry_at"] = None
        stage._persist()

    async def download_pending():
        nonlocal downloaded, failures, consecutive_failures, partial
        for item in stage.items():
            if (
                item["status"] == "downloaded"
                or item["external_id"] in attempted
                or (item["status"] == "failed" and item["next_retry_at"] is None)
                or (item["status"] == "failed" and item["next_retry_at"] > wall_clock())
            ):
                continue
            if max_downloads <= downloaded + failures or (deadline is not None and clock() >= deadline):
                partial = True
                return
            external_id = item["external_id"]
            attempted.add(external_id)
            try:
                stage.save_sgf(external_id, await source.fetch_sgf(external_id))
            except SourceBudgetExceeded:
                partial = True
                return
            except SourceRateLimited as exc:
                stage.fail(external_id, exc, wall_clock=wall_clock)
                stage.manifest["source_next_retry_at"] = wall_clock() + exc.retry_after
                stage._persist()
                record_error(exc, phase="sgf", external_id=external_id)
                partial = True
                return
            except (SourceError, ValueError) as exc:
                stage.fail(external_id, exc, wall_clock=wall_clock)
                record_error(exc, phase="sgf", external_id=external_id)
                if consecutive_failures >= 5:
                    partial = True
                    return
            else:
                downloaded += 1
                consecutive_failures = 0

    await download_pending()
    if consecutive_failures >= 5 or partial:
        return result()

    async def scan_page(page, phase):
        nonlocal consecutive_failures, partial
        if deadline is not None and clock() >= deadline:
            partial = True
            return None
        try:
            games = await source.fetch_page(page)
        except SourceBudgetExceeded:
            partial = True
            return None
        except SourceRateLimited as exc:
            stage.manifest["source_next_retry_at"] = wall_clock() + exc.retry_after
            stage._persist()
            record_error(exc, phase=phase, page=page)
            partial = True
            return None
        except SourceError as exc:
            record_error(exc, phase=phase, page=page)
            partial = True
            return None
        consecutive_failures = 0
        for metadata in games:
            external_id = _id(metadata.get("id"))
            if external_id not in known or external_id in stage.manifest["items"]:
                stage.remember(metadata)
        return games

    for page in range(max_head_pages):
        games = await scan_page(page, "head")
        if games is None:
            break
        stage.manifest["head"] = {"last_page": page, "games": len(games)}
        stage._persist()
        await download_pending()
        if not games or partial:
            break

    if not partial:
        start = max(0, int(stage.manifest["rolling_cursor"]) - 1)
        for page in range(start, start + max_rolling_pages):
            games = await scan_page(page, "rolling")
            if games is None:
                break
            if not games:
                rolling_complete = True
                stage.manifest["rolling_cursor"] = 0
                stage.manifest["rolling"] = {"last_page": page, "complete": True}
                stage._persist()
                break
            stage.manifest["rolling_cursor"] = page + 1
            stage.manifest["rolling"] = {"last_page": page, "complete": False}
            stage._persist()
            await download_pending()
            if partial:
                break

    return result()
