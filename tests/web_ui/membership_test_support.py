"""Dedicated local PostgreSQL fixtures; destructive work stays in a random schema.

The runner supplies TEST_DATABASE_URL from its private credential file. This
module never reads application/default configuration and never logs the URL.
"""

import os
import uuid
from contextlib import contextmanager

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url


def safe_test_database_url():
    raw = os.getenv("TEST_DATABASE_URL")
    if not raw:
        raise RuntimeError("TEST_DATABASE_URL is required for real PostgreSQL membership tests")
    try:
        url = make_url(raw)
        safe = (
            url.get_backend_name() == "postgresql"
            and url.host in {"127.0.0.1", "localhost", "::1"}
            and url.database
            and url.database.startswith("membership_validation")
        )
    except Exception:
        raise RuntimeError("Invalid dedicated membership test database URL") from None
    if not safe:
        raise RuntimeError("Membership tests require loopback PostgreSQL database membership_validation*")
    return url


@contextmanager
def _private_schema_engine():
    """An empty private schema, with independent DB identity checked first."""
    url = safe_test_database_url()
    control = create_engine(url)
    schema = "membership_test_" + uuid.uuid4().hex
    try:
        with control.begin() as connection:
            actual = connection.execute(text("SELECT current_database()")).scalar_one()
            if actual != url.database:
                raise RuntimeError("Dedicated test database identity mismatch")
            marker = connection.execute(
                text("SELECT environment FROM billing_test_identity.environment WHERE database_name=:database"),
                {"database": actual},
            ).scalar_one_or_none()
            if marker != "TEST":
                raise RuntimeError("Dedicated membership database lacks independent TEST marker")
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        engine = create_engine(url, connect_args={"options": f"-csearch_path={schema}"})
        try:
            yield engine
        finally:
            engine.dispose()
            with control.begin() as connection:
                # Generated name only; no application/default schema is ever dropped.
                connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
    finally:
        control.dispose()


@pytest.fixture
def membership_pg_schema_engine():
    """An empty private schema for migration tests."""
    with _private_schema_engine() as engine:
        yield engine


@pytest.fixture
def membership_pg_engine():
    """A private schema populated with current ORM tables."""
    from katrain.web.core.models_db import Base

    with _private_schema_engine() as engine:
        Base.metadata.create_all(engine)
        yield engine
