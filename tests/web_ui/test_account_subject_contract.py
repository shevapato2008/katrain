"""Guard the frozen `account_subject` format on the minting side.

katrain is the ONLY minter of `account_subject` (`users.uuid`). Per the Phase 1 contract
`superpowers/shared/identity-vocabulary-freeze-2026-08-10.md` §4, that value is frozen as
**32 lowercase hex characters, no dashes** (`uuid4().hex`), and downstream services enforce it:

    lobby-platform/api/lobby_api/auth.py  ACCOUNT_SUBJECT_PATTERN = ^[A-Za-z0-9_-]{1,32}$

so a 36-char dashed `str(uuid4())` makes **every** box-SSO bootstrap 400 — chess and gomoku
break together, far from wherever the bad value was written.

Until today that 32-char invariant was held up by exactly one thing: the `default=` lambda on
`katrain/web/core/models_db.py:51-53`. The column itself is an unbounded `String`, so the
schema does not constrain it, and no test asserted it. lobby has a guard
(`lobby-platform/api/tests/test_auth.py:198-216`); the minting side had none. These are it.

This matters most for the Phase 3 account-authority move: any path that writes `users.uuid`
without going through the model default — a migration script, an admin tool, the identity
service copying account rows — can silently land a dashed uuid.
"""

import re
import uuid as uuid_module

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker

from katrain.web.core import models_db

# The frozen format. Do not loosen this without also changing lobby's ACCOUNT_SUBJECT_PATTERN
# and lobby-platform/api/tests/test_auth.py:198-216 -- see freeze doc §4.
ACCOUNT_SUBJECT_RE = re.compile(r"^[0-9a-f]{32}$")


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    models_db.Base.metadata.create_all(bind=engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    yield engine, sessions


def test_minted_subject_matches_frozen_format(db):
    """The one real minting path produces a conforming subject."""
    engine, sessions = db
    session = sessions()
    try:
        # Mirrors katrain/web/core/auth.py:161 -- uuid is left to the model default.
        users = [models_db.User(username=f"u{i}", hashed_password="x") for i in range(25)]
        session.add_all(users)
        session.commit()
        for user in users:
            session.refresh(user)
            assert ACCOUNT_SUBJECT_RE.match(user.uuid), f"non-conforming subject: {user.uuid!r}"
    finally:
        session.close()


def test_minted_subject_is_never_a_dashed_uuid4(db):
    """The explicit negative: dashed 36-char uuids are the documented failure mode."""
    engine, sessions = db
    session = sessions()
    try:
        user = models_db.User(username="dashcheck", hashed_password="x")
        session.add(user)
        session.commit()
        session.refresh(user)

        assert "-" not in user.uuid, "dashed subject would 400 every downstream bootstrap"
        assert len(user.uuid) == 32, f"expected 32 chars, got {len(user.uuid)}"
        # And confirm the shape we must NOT emit is genuinely different, so this test
        # keeps meaning if uuid4().hex ever changes upstream.
        assert len(str(uuid_module.uuid4())) == 36
    finally:
        session.close()


def test_subject_is_unique_and_indexed(db):
    """`account_subject` is the sole basis of rating ownership, so it must be a real key."""
    engine, _ = db
    indexes = inspect(engine).get_indexes("users")
    uuid_index = [ix for ix in indexes if ix["column_names"] == ["uuid"]]
    assert uuid_index, "users.uuid must be indexed"
    assert uuid_index[0]["unique"], "users.uuid must be unique -- it identifies the account"


@pytest.mark.xfail(
    reason=(
        "KNOWN GAP (freeze doc §4, raised by the chess track 2026-08-10): users.uuid is an "
        "unbounded String, so the 32-char contract lives only in the Python default. Nothing "
        "stops a migration or the Phase 3 identity service from writing a 36-char dashed uuid. "
        "Fixing it is a schema change + migration, which Phase 1 forbids -- so this is recorded "
        "as an expected failure and is a Phase 3 precondition. When the constraint lands, this "
        "test will XPASS: remove the xfail marker at that point."
    ),
    strict=True,
)
def test_schema_rejects_a_dashed_subject(db):
    """Characterisation: today the database happily accepts a forbidden subject."""
    engine, sessions = db
    session = sessions()
    try:
        bad = str(uuid_module.uuid4())  # 36 chars, dashed -- forbidden by the contract
        session.add(models_db.User(username="smuggled", hashed_password="x", uuid=bad))
        session.commit()
        stored = session.execute(text("SELECT uuid FROM users WHERE username='smuggled'")).scalar()
        # The assertion we WANT to hold. It does not today; hence xfail(strict=True).
        assert ACCOUNT_SUBJECT_RE.match(stored), f"schema accepted a forbidden subject: {stored!r}"
    finally:
        session.close()


def test_all_stored_subjects_conform(db):
    """Reusable shape of the Phase 3 post-migration check: zero non-conforming rows."""
    engine, sessions = db
    session = sessions()
    try:
        session.add_all([models_db.User(username=f"m{i}", hashed_password="x") for i in range(10)])
        session.commit()
        rows = session.execute(text("SELECT id, uuid FROM users")).all()
        offenders = [(rid, val) for rid, val in rows if not ACCOUNT_SUBJECT_RE.match(val or "")]
        assert offenders == [], f"non-conforming account_subject rows: {offenders}"
    finally:
        session.close()
