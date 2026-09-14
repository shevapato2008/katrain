"""手机功能总开关 `PHONE_LOGIN_ENABLED` 关着时的那条路。

仓里所有别的手机用例走的都是「功能开着」（`phone_app` 夹具替它们打开）。
这个文件是**唯一**测「关着」的地方，它解的是两个堵点：

  1. 四个手机端点在这种服务器上不存在 ⇒ 404，而不是一路走到 sms 去炸；
  2. **功能关着的服务端不需要短信提供方** —— 两台线上机器今天
     `KATRAIN_SMS_PROVIDER` 都是空的，启动闸不早退就是拒绝启动。

⚠️ **本文件一律不 monkeypatch `PHONE_LOGIN_ENABLED`**，用的是这个进程里真实的
默认值（没有 `KATRAIN_PHONE_LOGIN_ENABLED` 环境变量 ⇒ False），并在下面那条
`test_the_flag_is_off_by_default` 里把它当作前提显式断言出来。
理由：如果这里自己把它设成 False，那"默认值被改成 True"这种改动就不会让任何一条
用例变红 —— 一组"关着"的测试测不出默认是不是关着，等于没写。
"""
import asyncio
import logging

import pytest
from fastapi import FastAPI

from katrain.web.core import config
from katrain.web.core.config import Settings, assert_sms_provider_is_configured

# `_guard_phone_endpoint` 守着的全部端点。**逐个断言，不是测一个推其余** ——
# 漏守一个的表现是那一个端点在功能关着的服务器上照常受理请求。
# 名单由 `grep -n "_guard_phone_endpoint(request)" katrain/web/api/v1/endpoints/auth.py` 数出来，
# 与下面 `test_every_guarded_endpoint_is_covered_here` 对账。
# 第三格是「要不要先登录」：`/phone/bind` 与 `/set-password` 上挂着
# `Depends(get_current_user)`，而依赖在端点函数体**之前**跑 ⇒ 匿名请求拿到的是 401，
# 根本走不到闸。不带票去断言 404 会把这两条写成永远测不到闸的空断言。
PHONE_ENDPOINTS = [
    ("/api/v1/auth/phone/send-code", {"phone": "13800138000", "purpose": "login"}, False),
    ("/api/v1/auth/phone/login", {"challenge_id": "c1", "code": "123456"}, False),
    ("/api/v1/auth/phone/bind", {"challenge_id": "c1", "code": "123456"}, True),
    ("/api/v1/auth/set-password", {"challenge_id": "c1", "code": "123456", "new_password": "newpw123456"}, True),
]


@pytest.fixture
async def phone_off_client(phone_app_unflagged):
    """开关处于**默认**状态（关）的 server 模式客户端。"""
    from httpx import ASGITransport, AsyncClient

    assert config.settings.PHONE_LOGIN_ENABLED is False, (
        "这一组测的就是「功能关着」，而进程里它是开着的 —— 要么默认值被改了，"
        "要么有别的夹具把它打开了没还原"
    )
    async with AsyncClient(transport=ASGITransport(app=phone_app_unflagged), base_url="http://test") as ac:
        yield ac


# --- 默认值本身 -------------------------------------------------------------

def test_the_flag_is_off_by_default(monkeypatch):
    """没有 `KATRAIN_PHONE_LOGIN_ENABLED` 这个环境变量时必须是关的。

    这条钉的是**生产真正读到的那个默认**：`Settings.__init__` 里
    `os.getenv("KATRAIN_PHONE_LOGIN_ENABLED", "")` 的那个 `""`。
    类体上的 `PHONE_LOGIN_ENABLED: bool = False` 在 `Settings()`（data 为空字典）这条
    路上**永远读不到** —— `data.setdefault` 一定先把键写上了。本文件每一条"关着"的
    用例都依赖这个默认，所以它必须被单独钉一次。
    """
    monkeypatch.delenv("KATRAIN_PHONE_LOGIN_ENABLED", raising=False)
    assert Settings().PHONE_LOGIN_ENABLED is False


@pytest.mark.parametrize("value", ["1", "true", "TRUE", "yes"])
def test_the_env_var_turns_it_on(monkeypatch, value):
    """env 装配真的接上了 —— 少了那一行就是"设了不生效"。"""
    monkeypatch.setenv("KATRAIN_PHONE_LOGIN_ENABLED", value)
    assert Settings().PHONE_LOGIN_ENABLED is True


# --- 1. 关着时四个端点各自 404 ----------------------------------------------

@pytest.mark.parametrize("path,body,needs_auth", PHONE_ENDPOINTS, ids=[p for p, _, _ in PHONE_ENDPOINTS])
async def test_every_phone_endpoint_is_404_when_disabled(
    phone_app_unflagged, phone_off_client, path, body, needs_auth
):
    """功能关着 ⇒ 这几个路由在语义上不存在。

    **404 不是 403**：403 会被读成"有这个功能但你没权限"，那是 strict 盒子那条
    （`phone_disabled_on_device`）说的事。三种拒绝是三个不同的事实。

    带票的那两个（`/phone/bind` / `/set-password`）必须真的带票 —— 匿名请求会被
    `Depends(get_current_user)` 在闸之前挡成 401，那样这条断言测的就不是闸了。
    """
    headers = {}
    if needs_auth:
        from katrain.web.core.auth import get_password_hash

        phone_app_unflagged.state.user_repo.create_user(
            username="flagoff", hashed_password=get_password_hash("oldpw123456")
        )
        login = await phone_off_client.post(
            "/api/v1/auth/login", json={"username": "flagoff", "password": "oldpw123456"}
        )
        assert login.status_code == 200, login.text
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    r = await phone_off_client.post(path, json=body, headers=headers)
    assert r.status_code == 404, r.text
    assert r.json()["detail"]["code"] == "phone_login_disabled", r.text


def test_every_guarded_endpoint_is_covered_here():
    """上面那张表必须盖住 `_guard_phone_endpoint` 今天守着的每一个端点。

    漏一个的表现是：某个手机端点在功能关着的服务器上照常受理请求，而这个文件全绿。
    判据落在**源码里真实的调用次数**上，不落在我数了几个上。
    """
    import inspect

    from katrain.web.api.v1.endpoints import auth as auth_mod

    src = inspect.getsource(auth_mod)
    guarded = src.count("_guard_phone_endpoint(request)")
    assert guarded == len(PHONE_ENDPOINTS), (
        f"源码里有 {guarded} 处 `_guard_phone_endpoint(request)`，而本文件只盖了 "
        f"{len(PHONE_ENDPOINTS)} 个端点 —— 新加的那个没人测它关着时的行为"
    )


# --- 2. /auth/features 说的和闸做的是同一件事 --------------------------------

async def test_features_reports_false_when_disabled(phone_off_client):
    """关着 ⇒ 前端问出来的是 false ⇒ 四个入口一个都不画。"""
    r = await phone_off_client.get("/api/v1/auth/features")
    assert r.status_code == 200, r.text
    assert r.json() == {"phone_login": False}


async def test_features_needs_no_credentials(phone_off_client):
    """**公开端点。** 登录框里的"验证码登录"要在登录之前就决定画不画 ⇒ 不能要 token。
    上面那条已经没带凭据了，这条把"不鉴权"写成独立的断言，免得日后有人给它加上
    `Depends(get_current_user)` 而只有一条含糊的用例变红。"""
    r = await phone_off_client.get("/api/v1/auth/features", headers={"Authorization": "Bearer not-a-real-token"})
    assert r.status_code == 200, r.text


async def test_features_reports_true_when_enabled(phone_client):
    """开着的 server ⇒ true。（`phone_client` 走 `phone_app`，开关是开的。）"""
    r = await phone_client.get("/api/v1/auth/features")
    assert r.status_code == 200, r.text
    assert r.json() == {"phone_login": True}


async def test_features_reports_false_on_a_strict_box(phone_strict_client):
    """开关开着，但 strict 盒子上那四个端点一律 403 ⇒ 这里必须是 false。

    这条钉的是「`/auth/features` 报的是**真实能力**，不是配置项的转述」。
    两处各判一套时，盒子上会画出一个点下去必然 403 的入口。
    """
    r = await phone_strict_client.get("/api/v1/auth/features")
    assert r.status_code == 200, r.text
    assert r.json() == {"phone_login": False}


async def test_features_reports_false_on_a_non_strict_board(phone_board_client):
    """同上：board 非 strict 的四个端点是 503（不转发）⇒ 也得是 false。"""
    r = await phone_board_client.get("/api/v1/auth/features")
    assert r.status_code == 200, r.text
    assert r.json() == {"phone_login": False}


# --- 3. 关着的服务端不需要短信提供方就能起来（本次的核心价值）-----------------

def test_the_gate_does_not_demand_a_provider_when_the_feature_is_off():
    """闸函数本身：功能关着 + 提供方为空 ⇒ 放行。"""
    assert assert_sms_provider_is_configured("server", "", phone_login_enabled=False) is None


def test_the_gate_still_demands_a_provider_when_the_feature_is_on():
    """**功能开着时那三条判断一条都没松。** 这是上面那条的对照组 ——
    少了它，"早退"很容易被写成"闸整个没了"而没有任何用例变红。"""
    with pytest.raises(RuntimeError, match="KATRAIN_SMS_PROVIDER"):
        assert_sms_provider_is_configured("server", "", phone_login_enabled=True)
    with pytest.raises(RuntimeError, match="console"):
        assert_sms_provider_is_configured("server", "console", phone_login_enabled=True)
    with pytest.raises(RuntimeError, match="未知的 SMS_PROVIDER"):
        assert_sms_provider_is_configured("server", "aliyu", phone_login_enabled=True)


def test_the_gate_defaults_to_the_stricter_side():
    """漏传第四个参数的调用者拿到的是**今天的行为**（照旧要求配提供方），
    不是一个静默放行的闸。闸的默认必须偏严那一侧。"""
    with pytest.raises(RuntimeError, match="KATRAIN_SMS_PROVIDER"):
        assert_sms_provider_is_configured("server", "")


class _ReachedTheRepos(Exception):
    """执行走过了闸，到了它后面第一件真事。"""


def test_a_disabled_server_starts_with_an_empty_sms_provider(monkeypatch):
    """端到端：真的跑 `_lifespan_server`，证明这台服务器**起得来**。

    这一条是本次改动的核心价值。两台线上机器今天 `KATRAIN_SMS_PROVIDER` 都是空的；
    闸不早退，它们合并之后当场拒绝启动 —— 一个和短信零关系的安全修复（P1 改密码即刻
    作废所有票）就要陪着阿里云签名报备一起等两周。

    形状照 `test_sms_provider.py::test_sms_gate_actually_raises_when_the_lifespan_runs`，
    方向相反：那边证明闸会抛，这边证明它放行。放行的证据是执行**走到了闸后面**那句
    `SQLAlchemyUserRepository(session_factory)` —— 把它换成一个当场抛哨兵的假体，
    既不真连库（`tests/conftest.py` 那道写库闸盯着），又比"没抛 RuntimeError"这种
    否定式证据强：否定式证据在函数一开头就 return 的实现下也成立。

    **不碰 `PHONE_LOGIN_ENABLED`**：它默认关，而这里要测的就是那个默认。
    """
    from katrain.web import server
    from katrain.web.core import auth as auth_mod

    assert config.settings.PHONE_LOGIN_ENABLED is False, "这条测的就是「默认关」这个状态"
    monkeypatch.setattr(config.settings, "SMS_PROVIDER", "")
    monkeypatch.setattr(config.settings, "KATRAIN_MODE", "server")

    def _sentinel(*args, **kwargs):
        raise _ReachedTheRepos

    monkeypatch.setattr(auth_mod, "SQLAlchemyUserRepository", _sentinel)
    with pytest.raises(_ReachedTheRepos):
        asyncio.run(server._lifespan_server(FastAPI(), logging.getLogger("test-phone-flag")))


def test_password_login_is_untouched_by_the_flag():
    """关掉手机功能**不许**顺手关掉口令登录。

    这条不是凑数：`/auth/login` 与那四个端点在同一个路由文件里，而这次改动往那个文件里
    加了一个"整类端点在这台服务器上不存在"的分支。上面那条 404 用例正是靠
    `/auth/login` 先换到一张票才测得成闸 —— 它已经在实际走这条路了，
    这里把它写成一条独立的、看得见的断言。
    """
    import inspect

    from katrain.web.api.v1.endpoints import auth as auth_mod

    src = inspect.getsource(auth_mod.login)
    assert "_guard_phone_endpoint" not in src, "口令登录被手机功能开关连坐了"
