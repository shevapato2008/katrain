"""Small prepared-read contracts. This module never performs name proof or DDL."""

import hashlib
import json
from functools import lru_cache
from pathlib import Path

from sqlalchemy import select, text

from katrain.web.kifu import prepared_models as m


class PreparedSearchNotReady(RuntimeError):
    code = "kifu_search_not_ready"

    def __init__(self, reason="unprepared"):
        self.reason = reason
        super().__init__(self.code + ": " + reason)


@lru_cache(maxsize=1)
def _static_policy_digest():
    root = Path(__file__).parent
    digest = hashlib.sha256()
    # One process-wide digest of local policy code/static hints, never DB proof.
    # Include new policy modules automatically; do not recurse into artifact trees.
    for path in sorted([*root.glob("*.py"), *root.joinpath("data").glob("*")]):
        if path.is_file():
            digest.update(path.name.encode())
            digest.update(path.read_bytes())
    return digest.hexdigest()


def current_policy_signature():
    from katrain.web.kifu.identity import strict_names_enabled

    payload = [m.POLICY_VERSION, strict_names_enabled(), m.NAME_LANGUAGES, "other-locales=en", _static_policy_digest()]
    return hashlib.sha256(json.dumps(payload, separators=(",", ":")).encode()).hexdigest()


def read_state(db):
    # An installation that has never explicitly migrated remains on the legacy path.
    dialect = db.bind.dialect.name if hasattr(db, "bind") else db.dialect.name
    if dialect == "postgresql":
        exists = db.execute(text("SELECT to_regclass('kifu_search_prepared_state') IS NOT NULL")).scalar_one()
    else:
        exists = db.execute(
            text("SELECT 1 FROM sqlite_master WHERE type='table' AND name='kifu_search_prepared_state'")
        ).first()
    if not exists:
        return None
    value = db.execute(select(m.state).where(m.state.c.id == 1)).mappings().first()
    if value is None:
        raise PreparedSearchNotReady("missing_state")
    return value


def require_ready(db, *, expected_policy_version=m.POLICY_VERSION):
    value = read_state(db)
    if value is None or not value["enabled"]:
        return None
    if not value["ready"] or not value["initial_coverage_complete"]:
        raise PreparedSearchNotReady("incomplete_coverage")
    if value["policy_version"] != expected_policy_version or value["policy_signature"] != current_policy_signature():
        raise PreparedSearchNotReady("policy_mismatch")
    if db.execute(select(m.dirty.c.input_key).limit(1)).first() is not None:
        raise PreparedSearchNotReady("dirty")
    return value
