"""P3：send-code / phone-login / bind 三个手机端点。夹具全部来自 tests/web_ui/conftest.py。"""

SEND = "/api/v1/auth/phone/send-code"
REGISTER = "/api/v1/auth/register"


async def test_send_code_needs_no_authentication(phone_client):
    """注册/找回密码时用户手上还没有 token —— 这个端点必须不鉴权。"""
    r = await phone_client.post(SEND, json={"phone": "13800138000", "purpose": "login"})
    assert r.status_code == 200, r.text


async def test_send_code_rejects_a_malformed_phone(phone_client):
    r = await phone_client.post(SEND, json={"phone": "abc", "purpose": "login"})
    assert r.status_code == 400
    assert r.json()["detail"]["code"] == "bad_phone"


async def test_send_code_rejects_an_unknown_purpose(phone_client):
    r = await phone_client.post(SEND, json={"phone": "13800138000", "purpose": "steal"})
    assert r.status_code == 400
    assert r.json()["detail"]["code"] == "bad_purpose"


async def test_send_code_second_call_for_the_same_phone_is_429_not_200(phone_client):
    """spec §3.1：任何一种超限都不许返 200。"""
    first = await phone_client.post(SEND, json={"phone": "13800138000", "purpose": "login"})
    assert first.status_code == 200, first.text
    r = await phone_client.post(SEND, json={"phone": "13800138000", "purpose": "login"})
    assert r.status_code == 429
    assert r.json()["detail"]["code"] == "sms_cooldown"
    assert r.json()["detail"]["retry_after_sec"] > 0
    assert r.headers["Retry-After"] == str(r.json()["detail"]["retry_after_sec"])


async def test_send_code_response_is_identical_whether_or_not_the_phone_has_an_account(
    phone_client, phone_app, phone_db, monkeypatch
):
    """**同一个手机号**，一次在"没绑过任何账号"的状态、一次在"已绑账号"的状态，
    响应必须一模一样 —— 否则这个不鉴权端点就是账号枚举器。

    旧版这条用例有两个洞：`set(a.json()) == set(b.json())` 只比键（多一个
    `registered` 布尔照样绿），而且两次调用换了手机号 ⇒ 唯一该被控住的变量没控住。
    """
    from katrain.web.core import models_db
    from katrain.web.core.auth import get_password_hash
    from katrain.web.core.config import settings

    # 冷却不是这条要测的东西，而同一个号连打两次必然撞上它 ⇒ 关掉，好让变量只剩"绑没绑"。
    monkeypatch.setattr(settings, "SMS_COOLDOWN_SEC", 0)
    phone = "13800138000"

    a = await phone_client.post(SEND, json={"phone": phone, "purpose": "login"})

    phone_app.state.user_repo.create_user(
        username="owner", hashed_password=get_password_hash("pw123456")
    )
    u = phone_db.query(models_db.User).filter_by(username="owner").one()
    u.phone_e164 = "+86" + phone
    phone_db.commit()

    b = await phone_client.post(SEND, json={"phone": phone, "purpose": "login"})

    assert a.status_code == b.status_code == 200, (a.text, b.text)
    # 键集**恒定且穷尽**：多出任何一个字段（registered / exists / user_id …）这里当场红
    assert set(a.json()) == set(b.json()) == {"challenge_id", "cooldown_sec"}
    # 值也必须一样。challenge_id 是随机串，当然不同 —— 单独断言它不同，
    # 免得有人把它改成"手机号的哈希"这种同样会泄露的东西。
    assert {k: v for k, v in a.json().items() if k != "challenge_id"} == {
        k: v for k, v in b.json().items() if k != "challenge_id"
    }
    assert a.json()["challenge_id"] != b.json()["challenge_id"]


async def test_send_code_response_never_carries_the_code(phone_client, sms_outbox):
    r = await phone_client.post(SEND, json={"phone": "13800138000", "purpose": "login"})
    assert r.status_code == 200, r.text
    code = sms_outbox.last_code
    assert len(code) == 6 and code.isdigit()
    assert code not in r.text


async def test_provider_failure_is_502_not_200(phone_client, sms_outbox):
    from katrain.web.core import sms

    sms_outbox.fail_with = sms.SmsUnreachable("供应商超时")
    r = await phone_client.post(SEND, json={"phone": "13800138000", "purpose": "login"})
    assert r.status_code == 502
    assert r.json()["detail"]["code"] == "sms_provider_failed"


async def test_daily_capacity_exhausted_is_503_not_429(phone_client, monkeypatch):
    """日总量打满是**服务端自己容量到顶**，跟这个用户快不快无关。
    给一个今天一条码都没取过的人返 429，是在撒谎说这是他的错。"""
    from katrain.web.core.config import settings

    monkeypatch.setattr(settings, "SMS_DAILY_CAP_CN", 0)
    r = await phone_client.post(SEND, json={"phone": "13800138000", "purpose": "login"})
    assert r.status_code == 503
    detail = r.json()["detail"]
    assert detail["code"] == "sms_capacity"
    # 字段恒在（没有理由时为 None），不要"有理由才有字段"
    assert "retry_after_sec" in detail and detail["retry_after_sec"] is None


async def test_send_code_records_the_forwarded_client_ip_not_the_peer(phone_client, phone_db):
    """**端点交给限流器的必须是 client_ip_for_ratelimit(request)，不是 request.client.host。**

    Task 2 只证明那个函数本身对，Task 6 只证明 issue() 按传进来的值分桶 ——
    端点写成 `ip = request.client.host` 的话那两套仍然全绿，而那正是 F10 那个缺陷本身。
    这条断言看的是**落到 challenge 行上的那个值**：ASGITransport 的对端恒为
    127.0.0.1，所以拿错值时这里会是两个 "127.0.0.1"。
    """
    from katrain.web.core import models_db

    await phone_client.post(
        SEND, json={"phone": "13800138001", "purpose": "login"},
        headers={"X-Forwarded-For": "203.0.113.9"},
    )
    await phone_client.post(
        SEND, json={"phone": "13800138002", "purpose": "login"},
        headers={"X-Forwarded-For": "198.51.100.7"},
    )

    ips = [
        row.client_ip
        for row in phone_db.query(models_db.SmsChallenge)
        .order_by(models_db.SmsChallenge.id)
        .all()
    ]
    assert ips == ["203.0.113.9", "198.51.100.7"]


async def test_the_ip_daily_cap_is_per_client_ip(phone_client, monkeypatch):
    """行为侧的同一条：换一个客户端 IP 必须重新有配额。
    只断言"限流会拦"的用例在"全站一个桶"的世界里也是绿的。"""
    from katrain.web.core.config import settings

    monkeypatch.setattr(settings, "SMS_IP_DAILY", 1)
    a = {"X-Forwarded-For": "203.0.113.9"}
    b = {"X-Forwarded-For": "198.51.100.7"}

    r1 = await phone_client.post(SEND, json={"phone": "13800138001", "purpose": "login"}, headers=a)
    assert r1.status_code == 200, r1.text
    r2 = await phone_client.post(SEND, json={"phone": "13800138002", "purpose": "login"}, headers=a)
    assert r2.status_code == 429 and r2.json()["detail"]["code"] == "sms_quota_ip"
    r3 = await phone_client.post(SEND, json={"phone": "13800138003", "purpose": "login"}, headers=b)
    assert r3.status_code == 200, "换了客户端 IP 还被拦 ⇒ 全站一个桶"


# ---- 盒子四答（spec §2.6 / F6：四个端点每一个都要显式回答，一个都不能漏） ----
async def test_send_code_403_on_strict_box(phone_strict_client):
    r = await phone_strict_client.post(SEND, json={"phone": "13800138000", "purpose": "login"})
    assert r.status_code == 403


async def test_send_code_503_on_board_and_does_not_forward(phone_board_client, remote_spy):
    r = await phone_board_client.post(SEND, json={"phone": "13800138000", "purpose": "login"})
    assert r.status_code == 503
    assert r.json()["detail"]["code"] == "need_online_phone"
    # remote_spy 是 MagicMock：`assert_not_called()` 只管它**自己**没被调用，
    # 管不住 `remote_client.send_phone_code(...)` 这种子调用。mock_calls 管得住。
    assert remote_spy.mock_calls == []


# ---- 顺带补的已知缺口：/auth/register 至今零限流 ----
def test_signup_ip_column_migrates_onto_an_existing_users_table(tmp_path):
    """`users` 加列走的是 add_missing_columns 那条零手写 DDL 的路（F1/F2）。
    只测 create_all 证明不了生产上会不会加列。"""
    from sqlalchemy import Column, Integer, MetaData, String, Table, create_engine, inspect

    from katrain.web.core import migrations

    eng = create_engine(f"sqlite:///{tmp_path}/old.db")
    md = MetaData()
    Table(
        "users",
        md,
        Column("id", Integer, primary_key=True),
        Column("username", String, unique=True),
        Column("hashed_password", String),
    )
    md.create_all(eng)

    migrations.add_missing_columns(eng)

    assert "signup_ip" in {c["name"] for c in inspect(eng).get_columns("users")}
    eng.dispose()


async def test_register_records_the_forwarded_ip_and_keeps_it_out_of_the_user_dict(
    phone_client, phone_app, phone_db
):
    """记的是可信 IP，而且**不进 `_to_dict`** —— `_to_dict` 是显式白名单
    （core/auth.py:323），进去了就会随 `User` 漏进 /auth/me、/users/online、
    /api/v1/social 每一个回 User 的响应。"""
    from katrain.web.core import models_db

    r = await phone_client.post(
        REGISTER, json={"username": "a0", "password": "pw123456"},
        headers={"X-Forwarded-For": "203.0.113.9"},
    )
    assert r.status_code == 200, r.text
    assert phone_db.query(models_db.User).filter_by(username="a0").one().signup_ip == "203.0.113.9"
    assert "signup_ip" not in phone_app.state.user_repo.get_user_by_username("a0")
    assert "signup_ip" not in r.json()


async def test_register_is_rate_limited_per_client_ip(phone_client, monkeypatch):
    """per-IP，不是全站每日上限：后者是一个任何匿名脚本几秒就能扳下的
    "今天全站关闭注册"开关，且没有绕过口。最后一句才是这条用例存在的理由。"""
    from katrain.web.core.config import settings

    monkeypatch.setattr(settings, "REGISTER_IP_DAILY", 2)
    a = {"X-Forwarded-For": "203.0.113.9"}
    b = {"X-Forwarded-For": "198.51.100.7"}

    for i in range(2):
        r = await phone_client.post(
            REGISTER, json={"username": f"a{i}", "password": "pw123456"}, headers=a
        )
        assert r.status_code == 200, r.text

    blocked = await phone_client.post(
        REGISTER, json={"username": "a9", "password": "pw123456"}, headers=a
    )
    assert blocked.status_code == 429
    assert blocked.json()["detail"]["code"] == "register_ip_daily"

    other_ip = await phone_client.post(
        REGISTER, json={"username": "b0", "password": "pw123456"}, headers=b
    )
    assert other_ip.status_code == 200, "换了 IP 还被拦 ⇒ 这是全站闸不是 per-IP 闸"


async def test_register_on_a_board_is_forwarded_without_touching_the_local_cap(
    phone_board_client, remote_spy, monkeypatch
):
    """盒子上的注册原样转发给云端。限流挂在**转发分支之后**，
    否则盒子会先在本地库上数一遍，凭空多一个故障面（D-U3「盒子什么都不改」）。
    REGISTER_IP_DAILY=0 ⇒ 本地闸只要跑到就必然 429，所以这条 200 是硬证据。"""
    from katrain.web.core.config import settings

    monkeypatch.setattr(settings, "REGISTER_IP_DAILY", 0)
    r = await phone_board_client.post(
        REGISTER, json={"username": "u0", "password": "pw123456"},
        headers={"X-Forwarded-For": "203.0.113.9"},
    )
    assert r.status_code == 200, r.text
    assert remote_spy.register.await_count == 1


LOGIN = "/api/v1/auth/phone/login"
ME = "/api/v1/auth/me"


async def test_phone_login_issues_a_token_for_a_bound_user(
    phone_client, sms_outbox, send_code, bound_user
):
    cid = await send_code(phone_client, bound_user["phone"], "login")
    r = await phone_client.post(LOGIN, json={"challenge_id": cid, "code": sms_outbox.last_code})
    assert r.status_code == 200, r.text
    assert r.json()["token_type"] == "bearer"

    me = await phone_client.get(
        ME, headers={"Authorization": f"Bearer {r.json()['access_token']}"}
    )
    assert me.status_code == 200, me.text
    assert me.json()["username"] == bound_user["username"]   # JWT 的 sub 是 username（F4）
    # `phone_bound` 必须真的从库里长出来。pydantic 默认值是 False ⇒ `_to_dict` 漏了
    # 那一行、或 models.User 少了那个字段时，失败方向是**所有人都"没绑手机"**，
    # 而不是报错 —— Task 11/12 的闸会静默地对每个人关上。这一句就是盯它的。
    assert me.json()["phone_bound"] is True
    # 原始号不许随 User 外溢（接口契约口径 2）
    assert "phone_e164" not in me.json()
    assert bound_user["phone"] not in me.text


async def test_phone_login_on_an_unbound_phone_is_404_not_a_silent_signup(
    phone_client, phone_db, sms_outbox, send_code
):
    """本轮**不做**手机注册（见计划开头那节收窄说明）：注册仍需用户名，
    没有用户名就建不了号。未绑号必须给一条能走的路，不许静默建号。"""
    from katrain.web.core import models_db

    cid = await send_code(phone_client, "13900139000", "login")
    r = await phone_client.post(LOGIN, json={"challenge_id": cid, "code": sms_outbox.last_code})
    assert r.status_code == 404
    assert r.json()["detail"]["code"] == "phone_not_bound"
    # 没有静默建号：库里一个 user 行都不该多出来
    assert phone_db.query(models_db.User).count() == 0


async def test_phone_login_rejects_a_bind_purpose_challenge(
    phone_client, sms_outbox, send_code, bound_user
):
    """拿绑定用的码去登录 —— 必须拒。端点写死 purpose="login"。"""
    cid = await send_code(phone_client, bound_user["phone"], "bind")
    r = await phone_client.post(LOGIN, json={"challenge_id": cid, "code": sms_outbox.last_code})
    assert r.status_code == 400
    assert r.json()["detail"]["code"] == "challenge_purpose_mismatch"


async def test_phone_login_challenge_is_single_use(
    phone_client, sms_outbox, send_code, bound_user
):
    cid = await send_code(phone_client, bound_user["phone"], "login")
    code = sms_outbox.last_code
    first = await phone_client.post(LOGIN, json={"challenge_id": cid, "code": code})
    assert first.status_code == 200, first.text
    second = await phone_client.post(LOGIN, json={"challenge_id": cid, "code": code})
    assert second.status_code == 400
    assert second.json()["detail"]["code"] == "challenge_consumed"


def test_repo_get_by_phone_reports_phone_bound_and_keeps_the_raw_number_out(
    phone_app, bound_user
):
    """`_to_dict`（core/auth.py:323）是显式白名单，全仓只有这一个生产实现，
    加字段只此一处。两个方向都要钉住：绑了的必须 True（漏了那一行的表现是
    静默 False，不是报错），原始号必须**不在**里面（口径 2）。"""
    repo = phone_app.state.user_repo

    d = repo.get_by_phone(bound_user["phone_e164"])
    assert d is not None
    assert d["username"] == bound_user["username"]
    assert d["phone_bound"] is True
    assert "phone_e164" not in d

    # 端点真正读的是 get_user_by_username 那条路（get_user_from_token → User(**user_dict)），
    # 所以同一条断言在那条路上再钉一次。
    assert repo.get_user_by_username(bound_user["username"])["phone_bound"] is True
    assert repo.get_by_phone("+8613900139000") is None


async def test_me_reports_phone_bound_false_for_an_unbound_account(phone_auth_client):
    """诚实的默认方向：没绑就是 False，字段必须存在（不是缺席）。"""
    r = await phone_auth_client.get(ME)
    assert r.status_code == 200, r.text
    assert r.json()["phone_bound"] is False


async def test_phone_login_403_on_strict_box(phone_strict_client):
    r = await phone_strict_client.post(LOGIN, json={"challenge_id": "x", "code": "123456"})
    assert r.status_code == 403


async def test_phone_login_503_on_board_and_does_not_forward(phone_board_client, remote_spy):
    r = await phone_board_client.post(LOGIN, json={"challenge_id": "x", "code": "123456"})
    assert r.status_code == 503
    assert r.json()["detail"]["code"] == "need_online_phone"
    assert remote_spy.mock_calls == []
