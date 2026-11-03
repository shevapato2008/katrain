"""Bounded reuse of pure first-pass compilation, guarded by fresh artifact bytes."""

from collections import OrderedDict
import hashlib
import marshal
from threading import Lock

from sqlalchemy import Text, cast, func
from sqlalchemy.orm import defer, undefer

from katrain.web.core.models_db import KifuNameBatch


class _CompiledFirstPassCache:
    def __init__(self, max_bytes=64 * 1024 * 1024, max_entries=1024, max_entry_bytes=1024 * 1024):
        self.max_bytes = max_bytes
        self.max_entries = max_entries
        self.max_entry_bytes = max_entry_bytes
        self._entries = OrderedDict()
        self._bytes = 0
        self._lock = Lock()

    def clear(self):
        with self._lock:
            self._entries.clear()
            self._bytes = 0

    def get(self, key):
        with self._lock:
            encoded = self._entries.get(key)
            if encoded is not None:
                self._entries.move_to_end(key)
        # Only bytes made here are decoded; callers never share mutable objects.
        return marshal.loads(encoded) if encoded is not None else None

    def put(self, key, compiled):
        encoded = marshal.dumps(compiled)
        if len(encoded) > min(self.max_entry_bytes, self.max_bytes) or self.max_entries < 1:
            return
        with self._lock:
            previous = self._entries.pop(key, None)
            if previous is not None:
                self._bytes -= len(previous)
            self._entries[key] = encoded
            self._bytes += len(encoded)
            while len(self._entries) > self.max_entries or self._bytes > self.max_bytes:
                _, removed = self._entries.popitem(last=False)
                self._bytes -= len(removed)


_CACHE = _CompiledFirstPassCache()


def compile_first_pass(status, bundle_sha256, artifact):
    """Compile frozen membership only; live payloads and sources stay uncached."""
    from katrain.web.kifu.name_candidates import canonical_sha256

    bundle = artifact.get("bundle") if isinstance(artifact, dict) else None
    if status != "applied" or not isinstance(bundle, dict) or canonical_sha256(bundle) != bundle_sha256:
        return None
    return (
        frozenset(canonical_sha256(item) for item in bundle.get("candidates", ())),
        frozenset(artifact.get("research_hashes", ())),
        bundle.get("shared_displays", ()),
    )


def _guard_expression(dialect):
    artifact_text = cast(KifuNameBatch.reviewed_artifact, Text)
    if dialect == "postgresql":
        return func.encode(func.sha256(func.convert_to(artifact_text, "UTF8")), "hex")
    if dialect == "sqlite":
        # SQLite has no built-in SHA256; keep the original text distinctions.
        return artifact_text
    return None


def _key(batch, guard, dialect):
    digest = hashlib.sha256(guard.encode("utf-8")).hexdigest() if dialect == "sqlite" else guard
    return (batch.id, batch.status, batch.bundle_sha256, batch.inventory_sha256, batch.source_registry_id, digest)


def read_compiled_first_pass(db, batch_ids):
    """Read a fresh guard on every use; misses pair full JSON and its new guard."""
    if not batch_ids or db.new or db.dirty or db.deleted:
        return None
    dialect = db.get_bind().dialect.name
    guard = _guard_expression(dialect)
    if guard is None:
        return None
    headers = (
        db.query(KifuNameBatch, guard.label("artifact_guard"))
        .options(defer(KifuNameBatch.reviewed_artifact))
        .filter(KifuNameBatch.id.in_(batch_ids))
        .populate_existing()
    )
    # PostgreSQL returns only a digest here. SQLite's guard is the raw JSON
    # text, so fetch one header at a time rather than retaining every string.
    headers = headers.yield_per(1) if dialect == "sqlite" else headers
    batches, contexts, misses = {}, {}, set()
    for batch, current_guard in headers:
        # defer does not discard JSON already held by this Session. A later
        # scope reader must load current artifact instead of pairing old JSON
        # with the refreshed scalar metadata above. This expiry performs no SQL.
        db.expire(batch, ["reviewed_artifact"])
        batches[batch.id] = batch
        if batch.status != "applied" or not isinstance(current_guard, str):
            contexts[batch.id] = None
            continue
        compiled = _CACHE.get(_key(batch, current_guard, dialect))
        if compiled is None:
            misses.add(batch.id)
        else:
            contexts[batch.id] = compiled
    # A SQLite header's text must not remain live while a cold JSON is decoded.
    if batches:
        del current_guard
    if misses:
        # A header can change before this read. Never pair its old guard with
        # this new artifact; every scalar and guard below comes from one row.
        found = set()
        for batch_id in sorted(misses):
            full_row = (
                db.query(KifuNameBatch, guard.label("artifact_guard"))
                .options(undefer(KifuNameBatch.reviewed_artifact))
                .filter(KifuNameBatch.id == batch_id)
                .populate_existing()
                .one_or_none()
            )
            if full_row is None:
                continue
            batch, current_guard = full_row
            found.add(batch.id)
            batches[batch.id] = batch
            try:
                compiled = compile_first_pass(batch.status, batch.bundle_sha256, batch.reviewed_artifact)
                contexts[batch.id] = compiled
                if compiled is not None and isinstance(current_guard, str):
                    _CACHE.put(_key(batch, current_guard, dialect), compiled)
            finally:
                # Only scalar headers and pure compiled membership escape this
                # iteration. A later scope reader reloads current full JSON.
                db.expire(batch, ["reviewed_artifact"])
                del full_row, current_guard
        # Deleted rows cannot retain the earlier header as usable proof.
        for missing in misses - found:
            batches.pop(missing, None)
    return batches, contexts
