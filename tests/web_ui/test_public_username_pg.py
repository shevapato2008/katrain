"""Public names belong to server authority; board copies are display caches."""

import pytest
from fastapi import FastAPI, HTTPException
from httpx import ASGITransport, AsyncClient
from jose import jwt
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from katrain.web.core import migrations, models_db
from katrain.web.core.auth import SQLAlchemyUserRepository, create_access_token, create_refresh_token, get_password_hash
from katrain.web.core.config import settings
from tests.web_ui.membership_test_support import membership_pg_schema_engine


@pytest.fixture
def sqlite_engine():
    engine = create_engine("sqlite:///:memory:")
    try:
        yield engine
    finally:
        engine.dispose()


def migrate(engine, mode="server"):
    migration = getattr(migrations, "migrate_public_username_schema", None)
    assert callable(migration), "Public names need a role-aware additive migration"
    migration(engine, mode=mode)


def legacy_users(engine):
    with engine.begin() as conn:
        conn.execute(
            text(
                "CREATE TABLE users (id INTEGER PRIMARY KEY, uuid TEXT, username TEXT NOT NULL, "
                "hashed_password TEXT NOT NULL, is_admin BOOLEAN NOT NULL DEFAULT FALSE, "
                "credits INTEGER NOT NULL, membership_revision INTEGER NOT NULL)"
            )
        )
        names = [
            "旧 人类 名称 超出二十四字符也必须完整保留_Exact",
            "u_" + "a" * 20,
            "u_" + "b" * 20,
            "u_" + "c" * 20,
            "u_" + "D" * 20,
            "u_" + "e" * 20,
        ]
        for user_id, name in enumerate(names, 1):
            conn.execute(
                text("INSERT INTO users VALUES (:id, :uuid, :name, 'old-hash', :admin, 4321, 7)"),
                {"id": user_id, "uuid": f"old-uuid-{user_id}", "name": name, "admin": user_id == 4},
            )
    migrations.migrate_phone_auth_schema(engine)
    with engine.begin() as conn:
        for user_id in [2, 3, 4, 5]:
            conn.execute(
                text("INSERT INTO phone_identities(phone_e164,user_id) VALUES (:phone,:id)"),
                {"phone": f"+861380000000{user_id}", "id": user_id},
            )
        conn.execute(
            text(
                "INSERT INTO phone_signup_claims(phone_e164,claim_type,user_id) "
                "VALUES ('+8613800000003','bound_existing',3), "
                "('+8613800000099','signup_grant',999)"
            )
        )
    return names


def assert_migration_preserves_users(engine):
    names = legacy_users(engine)
    migrate(engine)
    migrate(engine)
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT id,uuid,username,public_username,hashed_password,credits,membership_revision "
                "FROM users ORDER BY id"
            )
        ).all()
        assert rows == [
            (i, f"old-uuid-{i}", name, None if i == 2 else name, "old-hash", 4321, 7) for i, name in enumerate(names, 1)
        ]
        assert (
            conn.execute(text("SELECT user_id FROM phone_signup_claims WHERE claim_type='signup_grant'")).scalar_one()
            == 999
        )
    assert inspect(engine).get_foreign_keys("phone_signup_claims") == []
    with pytest.raises(IntegrityError), engine.begin() as conn:
        conn.execute(text("UPDATE users SET public_username=:name WHERE id=2"), {"name": names[0]})
    with engine.begin() as conn:
        conn.execute(text("UPDATE users SET public_username='CaseName' WHERE id=2"))
        conn.execute(text("UPDATE users SET public_username='casename' WHERE id=3"))


def test_pg_backfill_is_exact_idempotent_and_preserves_assets(membership_pg_schema_engine):
    assert_migration_preserves_users(membership_pg_schema_engine)


def test_server_sqlite_backfill_and_unique_authority(sqlite_engine):
    assert_migration_preserves_users(sqlite_engine)


def test_public_name_migration_can_precede_generic_legacy_columns(sqlite_engine):
    with sqlite_engine.begin() as conn:
        conn.execute(text("CREATE TABLE users (id INTEGER PRIMARY KEY,username TEXT NOT NULL)"))
        conn.execute(text("INSERT INTO users VALUES (1,'old owner')"))
    migrate(sqlite_engine)
    with sqlite_engine.connect() as conn:
        assert conn.execute(text("SELECT username,public_username FROM users")).one() == ("old owner", "old owner")


@pytest.mark.parametrize(
    "ddl",
    [
        "CREATE INDEX uq_user_public_username ON users(public_username)",
        "CREATE UNIQUE INDEX uq_user_public_username ON users(public_username) WHERE public_username IS NOT NULL",
        "CREATE UNIQUE INDEX uq_user_public_username ON users(lower(public_username))",
        "CREATE UNIQUE INDEX uq_user_public_username ON users(username)",
    ],
)
def test_pg_refuses_same_named_wrong_index(membership_pg_schema_engine, ddl):
    engine = membership_pg_schema_engine
    legacy_users(engine)
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE users ADD COLUMN public_username TEXT"))
        conn.execute(text(ddl))
    with pytest.raises(RuntimeError, match="public username.*index"):
        migrate(engine)


@pytest.mark.parametrize(
    "ddl",
    [
        "CREATE INDEX uq_user_public_username ON users(public_username)",
        "CREATE UNIQUE INDEX uq_user_public_username ON users(public_username) WHERE public_username IS NOT NULL",
        "CREATE UNIQUE INDEX uq_user_public_username ON users(lower(public_username))",
        "CREATE UNIQUE INDEX uq_user_public_username ON users(username)",
    ],
)
def test_sqlite_refuses_same_named_wrong_index(sqlite_engine, ddl):
    legacy_users(sqlite_engine)
    with sqlite_engine.begin() as conn:
        conn.execute(text("ALTER TABLE users ADD COLUMN public_username TEXT"))
        conn.execute(text(ddl))
    with pytest.raises(RuntimeError, match="public username.*index"):
        migrate(sqlite_engine)


def test_server_migration_never_pollutes_board_create_all(sqlite_engine):
    models_db.User.__table__.create(sqlite_engine)
    migrate(sqlite_engine)
    assert all("public_username" not in [c.name for c in index.columns] for index in models_db.User.__table__.indexes)
    board = create_engine("sqlite:///:memory:")
    try:
        models_db.Base.metadata.create_all(board)
        migrate(board, "board")
        migrations.create_missing_indexes(board)
        assert "uq_user_public_username" not in {i["name"] for i in inspect(board).get_indexes("users")}
        with sessionmaker(bind=board)() as db:
            db.add_all(
                [
                    models_db.User(username=f"cloud-{i}", hashed_password="shadow", public_username="同名")
                    for i in [1, 2]
                ]
            )
            db.commit()
    finally:
        board.dispose()


def test_board_migration_never_guesses_generated_or_human_names(sqlite_engine):
    legacy_users(sqlite_engine)
    migrate(sqlite_engine, "board")
    with sqlite_engine.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM users WHERE public_username IS NOT NULL")).scalar_one() == 0


def assert_login_lookup_is_canonical(engine, monkeypatch):
    monkeypatch.setattr(settings, "KATRAIN_MODE", "server")
    models_db.User.__table__.create(engine)
    migrate(engine)
    repo = SQLAlchemyUserRepository(sessionmaker(bind=engine))
    owner = repo.create_user("canonical-a", "hash", public_username="公开名字")
    assert repo.get_user_by_login_name("公开名字")["id"] == owner["id"]
    assert repo.get_user_by_username("公开名字") is None
    other = repo.create_user("公开名字", "hash", public_username="another")
    assert other["id"] != owner["id"]
    assert repo.get_user_by_login_name("公开名字") is None
    assert repo.get_user_by_username("公开名字")["id"] == other["id"]
    monkeypatch.setattr(settings, "KATRAIN_MODE", "board")
    assert repo.get_user_by_login_name("公开名字") is None


def test_login_name_is_separate_from_canonical_identity(sqlite_engine, monkeypatch):
    assert_login_lookup_is_canonical(sqlite_engine, monkeypatch)


def test_pg_login_name_does_not_change_canonical_identity(membership_pg_schema_engine, monkeypatch):
    assert_login_lookup_is_canonical(membership_pg_schema_engine, monkeypatch)


def test_legacy_server_writer_reserves_exact_name_without_new_input_validation(sqlite_engine, monkeypatch):
    monkeypatch.setattr(settings, "KATRAIN_MODE", "server")
    models_db.User.__table__.create(sqlite_engine)
    repo = SQLAlchemyUserRepository(sessionmaker(bind=sqlite_engine))
    username = "旧的 含空格且超长的用户名也不能被新注册校验器禁止"
    assert repo.create_user(username, "hash")["public_username"] == username


def test_shadow_name_reuse_keeps_canonical_uuid_history_and_clears_trusted_null(sqlite_engine, monkeypatch):
    from katrain.web.api.v1.endpoints.auth import _get_or_create_shadow_user

    monkeypatch.setattr(settings, "KATRAIN_MODE", "board")
    models_db.Base.metadata.create_all(sqlite_engine)
    repo = SQLAlchemyUserRepository(sessionmaker(bind=sqlite_engine))
    first = _get_or_create_shadow_user(repo, "u_" + "a" * 20, "复用名字")
    with repo.session_factory() as db:
        db.get(models_db.User, first["id"]).credits = 1234
        db.commit()
    second = _get_or_create_shadow_user(repo, "u_" + "b" * 20, "复用名字")
    again = _get_or_create_shadow_user(repo, first["username"], None)
    assert second["id"] != first["id"] and second["public_username"] == "复用名字"
    assert (again["id"], again["uuid"], again["username"], again["credits"], again["public_username"]) == (
        first["id"],
        first["uuid"],
        first["username"],
        1234,
        None,
    )


@pytest.mark.asyncio
async def test_password_alias_issues_canonical_token_and_alias_tokens_cannot_authenticate(sqlite_engine, monkeypatch):
    from katrain.web.api.v1.endpoints.auth import get_user_from_token, router

    monkeypatch.setattr(settings, "KATRAIN_MODE", "server")
    monkeypatch.setattr(settings, "KATRAIN_BOX_SSO", False)
    models_db.User.__table__.create(sqlite_engine)
    repo = SQLAlchemyUserRepository(sessionmaker(bind=sqlite_engine))
    owner = repo.create_user("canonical-owner", get_password_hash("old-short"), public_username="名字")
    app = FastAPI()
    app.include_router(router, prefix="/auth")
    app.state.user_repo = repo
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/auth/login", json={"username": "名字", "password": "old-short"})
        assert response.status_code == 200
        token = response.json()["access_token"]
        assert jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])["sub"] == owner["username"]
        me = await client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert (me.json()["username"], me.json()["public_username"]) == ("canonical-owner", "名字")
        forged_alias = create_access_token({"sub": "名字"})
        with pytest.raises(HTTPException):
            await get_user_from_token(forged_alias, repo)
        refreshed = await client.post("/auth/refresh", json={"refresh_token": create_refresh_token({"sub": "名字"})})
        assert refreshed.status_code == 401


@pytest.mark.asyncio
@pytest.mark.parametrize("canonical", ["guest", "admin:owner"])
async def test_public_name_cannot_bypass_reserved_canonical_login(sqlite_engine, monkeypatch, canonical):
    from katrain.web.api.v1.endpoints.auth import router

    monkeypatch.setattr(settings, "KATRAIN_MODE", "server")
    monkeypatch.setattr(settings, "KATRAIN_BOX_SSO", False)
    models_db.User.__table__.create(sqlite_engine)
    repo = SQLAlchemyUserRepository(sessionmaker(bind=sqlite_engine))
    repo.create_user(canonical, get_password_hash("old-short"), public_username="普通名字")
    app = FastAPI()
    app.include_router(router, prefix="/auth")
    app.state.user_repo = repo
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/auth/login", json={"username": "普通名字", "password": "old-short"})
    assert response.status_code == 400


@pytest.mark.parametrize("name", ["棋手_01", "Go-Player", "é棋", "１２", "Ａｂ"])
def test_new_public_name_validation_accepts_exact_unicode(name):
    from katrain.web.core.public_identity import validate_public_username

    assert validate_public_username(name) is None


@pytest.mark.parametrize(
    "name", ["a", "a" * 25, "a b", "a\n", "e\u0301", "🙂棋", "guest", "GuEsT", "ADMIN", "admin:x", "U_name"]
)
def test_new_public_name_validation_rejects_reserved_or_invalid_input(name):
    from katrain.web.core.public_identity import validate_public_username

    with pytest.raises(ValueError, match="username_invalid"):
        validate_public_username(name)


@pytest.mark.parametrize("password", ["a" * 15, "密" * 15, " 密码_" * 5, "a" * 72])
def test_signup_password_accepts_unicode_and_preserves_input(password):
    from katrain.web.core.public_identity import validate_signup_password

    assert validate_signup_password(password) is None


@pytest.mark.parametrize("password", ["a" * 14, "a" * 73, "密" * 25, "a" * 15 + "\0"])
def test_signup_password_rejects_short_overbytes_and_nul(password):
    from katrain.web.core.public_identity import validate_signup_password

    with pytest.raises(ValueError, match="password_invalid"):
        validate_signup_password(password)


def test_generated_handle_classifier_is_strict():
    from katrain.web.core.public_identity import is_generated_phone_username

    assert is_generated_phone_username("u_" + "a0" * 10)
    for name in ["u_" + "A" * 20, "U_" + "a" * 20, "u_" + "a" * 19, "u_" + "a" * 20 + "\n"]:
        assert not is_generated_phone_username(name)
