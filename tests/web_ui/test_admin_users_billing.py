"""Admin users & billing: read-only lookups, audited credit adjustments, one-time redeem codes, audit view."""

import json
import uuid

import pytest
from fastapi.testclient import TestClient
from passlib.context import CryptContext
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from katrain.web.core import billing
from katrain.web.core.models_db import AdminAuditLog, Base, CreditTransaction, RedeemCode, User


@pytest.fixture
def env(monkeypatch, tmp_path):
    from katrain.web.admin.app import create_admin_app

    monkeypatch.setenv("KATRAIN_ADMIN_USERNAME", "admin:fan")
    monkeypatch.setenv("KATRAIN_ADMIN_PASSWORD_HASH", CryptContext(schemes=["bcrypt"]).hash("local-only-password"))
    monkeypatch.setenv("KATRAIN_ADMIN_SESSION_SECRET", "s" * 48)
    monkeypatch.setenv("KATRAIN_ADMIN_ENV", "test")
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    factory = sessionmaker(bind=engine)
    with factory() as db:
        for index, name in enumerate(["fan", "liuyang", "chenjing", "chenmo"], start=1):
            db.add(User(id=index, username=name, hashed_password="x", rank="1d", credits=0, is_admin=index == 1))
        db.commit()
        billing.grant(db, 3, 330, reason="signup_grant", ref_id="signup:3")
    client = TestClient(create_admin_app(session_factory=factory, static_dir=tmp_path))
    token = client.post("/api/admin/auth/login", json={"username": "admin:fan", "password": "local-only-password"})
    return client, {"Authorization": f"Bearer {token.json()['access_token']}"}, factory


def adjust(client, headers, user_id, amount, reason="误发补偿退回", key=None, username=None, confirm=None):
    return client.post(
        f"/api/admin/users/{user_id}/credits",
        headers=headers,
        json={
            "amount": amount,
            "reason": reason,
            "idempotency_key": key or uuid.uuid4().hex,
            "confirm_username": username if username is not None else {3: "chenjing", 2: "liuyang"}.get(user_id, ""),
            "confirm_amount": amount if confirm is None else confirm,
        },
    )


def audits(factory, action):
    with factory() as db:
        return db.scalars(select(AdminAuditLog).where(AdminAuditLog.action == action)).all()


def test_every_route_requires_the_admin_session(env):
    client, _, _ = env
    for method, path in [
        ("get", "/api/admin/users"),
        ("get", "/api/admin/users/3"),
        ("get", "/api/admin/users/3/ledger"),
        ("post", "/api/admin/users/3/credits"),
        ("get", "/api/admin/redeem-codes"),
        ("post", "/api/admin/redeem-codes"),
        ("get", "/api/admin/audit"),
    ]:
        assert getattr(client, method)(path).status_code == 401, path


def test_user_search_by_prefix_id_and_uuid_never_exposes_secrets(env):
    client, headers, factory = env
    body = client.get("/api/admin/users?q=chen", headers=headers).json()
    assert [u["username"] for u in body["items"]] == ["chenjing", "chenmo"] and body["total"] == 2
    assert set(body["items"][0]) == {"id", "username", "rank", "credits", "is_admin", "created_at"}
    assert [u["id"] for u in client.get("/api/admin/users?q=2", headers=headers).json()["items"]] == [2]
    with factory() as db:
        uid = db.get(User, 4).uuid
    assert [u["id"] for u in client.get(f"/api/admin/users?q={uid}", headers=headers).json()["items"]] == [4]
    assert client.get("/api/admin/users?q=%25", headers=headers).json()["items"] == []  # LIKE wildcard is literal
    detail = client.get("/api/admin/users/3", headers=headers).json()
    assert detail["credits"] == 330 and detail["uuid"] and "hashed_password" not in detail
    assert client.get("/api/admin/users/99", headers=headers).status_code == 404


def test_adjustment_appends_a_row_and_its_audit_in_one_commit(env):
    client, headers, factory = env
    key = uuid.uuid4().hex
    added = adjust(client, headers, 3, 200, reason="活动奖励发放", key=key)
    assert added.status_code == 200, added.text
    assert added.json()["balance"] == 530 and added.json()["replayed"] is False
    deducted = adjust(client, headers, 3, -50)
    assert deducted.json()["balance"] == 480
    ledger = client.get("/api/admin/users/3/ledger", headers=headers).json()["items"]
    assert [(r["delta"], r["reason"], r["status"]) for r in ledger[:2]] == [
        (-50, "admin_adjust", "committed"),
        (200, "admin_adjust", "committed"),
    ]
    assert ledger[1]["ref_id"] == f"admin_adjust:{key}"
    rows = audits(factory, "credit_adjust")
    assert len(rows) == 2 and rows[0].target_type == "user" and rows[0].target_id == 3
    detail = json.loads(rows[0].detail)
    assert detail == {"amount": 200, "reason": "活动奖励发放", "balance_before": 330, "balance_after": 530, "key": key}
    assert client.get("/api/admin/users/3", headers=headers).json()["admin_adjust_total"] == 150


def test_replaying_the_same_key_changes_nothing_and_a_different_request_under_it_is_refused(env):
    client, headers, factory = env
    key = uuid.uuid4().hex
    assert adjust(client, headers, 3, 100, key=key).json()["balance"] == 430
    replay = adjust(client, headers, 3, 100, key=key)
    assert replay.status_code == 200 and replay.json() == {**replay.json(), "balance": 430, "replayed": True}
    assert adjust(client, headers, 3, 90, key=key).status_code == 409
    assert adjust(client, headers, 2, 100, key=key).status_code == 409
    assert len(audits(factory, "credit_adjust")) == 1


@pytest.mark.parametrize(
    "amount, reason, username, confirm, status",
    [
        (0, "误发补偿退回", "chenjing", None, 422),
        (12001, "误发补偿退回", "chenjing", None, 422),
        (-12001, "误发补偿退回", "chenjing", None, 422),
        (10, "太短", "chenjing", None, 422),
        (10, "误发补偿退回", "chenmo", None, 409),
        (10, "误发补偿退回", "chenjing", 11, 409),
        (-331, "误发补偿退回", "chenjing", None, 409),
    ],
)
def test_invalid_mismatched_or_overdrawing_adjustments_write_nothing(env, amount, reason, username, confirm, status):
    client, headers, factory = env
    response = adjust(client, headers, 3, amount, reason=reason, username=username, confirm=confirm)
    assert response.status_code == status, response.text
    with factory() as db:
        assert db.get(User, 3).credits == 330
        assert db.scalars(select(CreditTransaction).where(CreditTransaction.reason == "admin_adjust")).all() == []
    assert audits(factory, "credit_adjust") == []


def test_a_failed_audit_write_rolls_the_adjustment_back(env, monkeypatch):
    client, headers, factory = env
    from katrain.web.admin.routers import users as users_router

    def broken(*args, **kwargs):
        raise RuntimeError("audit table unavailable")

    monkeypatch.setattr(users_router, "_audit", broken)
    with pytest.raises(RuntimeError):
        adjust(client, headers, 3, 100)
    with factory() as db:
        assert db.get(User, 3).credits == 330


def test_redeem_codes_are_shown_once_then_only_masked(env):
    client, headers, factory = env
    body = {"count": 3, "credits": 100, "days": 90, "note": "九月线下活动奖品", "idempotency_key": uuid.uuid4().hex}
    made = client.post("/api/admin/redeem-codes", headers=headers, json=body)
    assert made.status_code == 200, made.text
    codes = made.json()["codes"]
    assert len(codes) == 3 and all(len(code) == 32 for code in codes)
    assert client.post("/api/admin/redeem-codes", headers=headers, json=body).status_code == 409
    with factory() as db:
        billing.redeem(db, 3, codes[0])
    listing = client.get("/api/admin/redeem-codes", headers=headers).json()
    assert [b["count"] for b in listing["batches"]] == [3] and listing["batches"][0]["used"] == 1
    assert listing["batches"][0]["note"] == "九月线下活动奖品"
    shown = {c["code"] for c in listing["codes"]}
    assert all("…" in c and c not in codes for c in shown) and f"{codes[0][:4]}…{codes[0][-4:]}" in shown
    used = [c for c in listing["codes"] if c["used_by"]]
    assert used == [{**used[0], "used_by": "chenjing"}]
    rows = audits(factory, "redeem_codes_generate")
    assert len(rows) == 1 and codes[0] not in rows[0].detail
    redeemed = client.get("/api/admin/users/3/redeemed", headers=headers).json()["items"]
    assert [(r["code"], r["credits"]) for r in redeemed] == [(f"{codes[0][:4]}…{codes[0][-4:]}", 100)]


@pytest.mark.parametrize(
    "patch", [{"count": 0}, {"count": 201}, {"credits": 12001}, {"days": 0}, {"days": 366}, {"note": "短"}]
)
def test_redeem_batch_limits(env, patch):
    client, headers, factory = env
    body = {"count": 3, "credits": 100, "days": 90, "note": "九月线下活动奖品", "idempotency_key": uuid.uuid4().hex, **patch}
    assert client.post("/api/admin/redeem-codes", headers=headers, json=body).status_code == 422
    with factory() as db:
        assert db.scalars(select(RedeemCode)).all() == []


def test_audit_view_filters_by_action_and_target_user(env):
    client, headers, factory = env
    adjust(client, headers, 3, 100)
    adjust(client, headers, 2, 5, reason="测试补偿一次")
    everything = client.get("/api/admin/audit", headers=headers).json()
    assert {"credit_adjust", "login_success"} <= {row["action"] for row in everything["items"]}
    only = client.get("/api/admin/audit?action=credit_adjust&target_user_id=3", headers=headers).json()
    assert [(r["target_id"], r["target_label"]) for r in only["items"]] == [(3, "chenjing")]
    newest_first = [r["created_at"] for r in everything["items"]]
    assert newest_first == sorted(newest_first, reverse=True)


def test_audit_export_is_csv_of_the_filter_and_is_itself_audited(env):
    import csv
    import io

    client, headers, factory = env
    adjust(client, headers, 3, 100)
    adjust(client, headers, 2, 5, reason="测试补偿一次")
    client.post("/api/admin/auth/login", json={"username": "=HYPERLINK(\"http://x\")", "password": "nope"})
    everything = list(csv.reader(io.StringIO(client.get("/api/admin/audit/export", headers=headers).content.decode("utf-8-sig"))))
    actors = {r[2] for r in everything[1:]}
    assert "'=HYPERLINK(\"http://x\")" in actors and not any(a.startswith("=") for a in actors)
    assert all(r[7] != "'" for r in everything[1:])  # an empty detail stays empty
    response = client.get("/api/admin/audit/export?action=credit_adjust", headers=headers)
    assert response.status_code == 200 and response.headers["content-type"].startswith("text/csv")
    assert response.headers["x-export-rows"] == "2"
    rows = list(csv.reader(io.StringIO(response.content.decode("utf-8-sig"))))
    assert rows[0][:4] == ["id", "created_at_shanghai", "actor", "action"] and rows[1][1].endswith("+08:00") and {r[3] for r in rows[1:]} == {"credit_adjust"}
    assert all(not r[7].startswith(("=", "+", "-", "@")) for r in rows[1:])
    exports = audits(factory, "audit_export")
    assert len(exports) == 2 and json.loads(exports[-1].detail)["rows"] == 2
    assert client.get("/api/admin/audit/export").status_code == 401
