"""P3 手机绑定与验证码登录的鉴权侧用例。Task 3 起头，后续 Task 继续往这个文件加。"""

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from katrain.web.core.auth import get_password_hash, verify_password  # noqa: E402


@pytest.mark.parametrize(
    "bad_hash",
    ["", "!", "*", "not-a-bcrypt-hash", "SHADOW_USER_NO_LOCAL_AUTH"],
)
def test_verify_password_returns_false_for_unparsable_hash(bad_hash):
    """无法识别的 hash 必须返回 False，不许抛。

    抛的后果：这类账号被打 /auth/login 会 **500 而不是 401**，
    而 500 与 401 可区分"此人存在且没有可用口令" —— 一个免费的账号枚举器。

    `None` 故意不在这张表里：passlib 今天对 `None` 已经返回 False，
    写进来就是一条**拆掉实现也不会红**的假绿断言。表里 5 条都实跑确认过今天抛。"""
    assert verify_password("anything", bad_hash) is False


def test_verify_password_still_works_for_real_hashes():
    h = get_password_hash("correct-horse")
    assert verify_password("correct-horse", h) is True
    assert verify_password("wrong", h) is False


@pytest.fixture
def client_with_sentinel_user(isolated_session_factory):
    """一个真的能打 `/auth/login` 的 app，库里放两个账号：
    `shadowy`（哨兵口令，没有可用密码）与 `normal`（正常 bcrypt 口令，做对照组）。

    `isolated_session_factory` 是 `tests/conftest.py` 里**现成的**夹具
    （`tmp_path` 下的一次性 sqlite + `Base.metadata.create_all` 过）。

    **必须在进 `TestClient` 之前**设 `app.state.session_factory`：
    `TestClient(app)` 当上下文管理器用时会跑 lifespan，而 `_lifespan_server`
    会用它无条件重建 6 个 repo 覆盖 `app.state`。只设 `app.state.user_repo`
    会被覆盖掉，写就落到开发机的真库上 —— `tests/conftest.py` 的写闸会当场拦下。

    用户在 `with` **里面**建：这样拿到的 `app.state.user_repo` 就是端点将要用的
    那一个（lifespan 重建之后的），不是被覆盖掉的那一个。
    `create_app(enable_engine=False)` + 服务端模式下 lifespan 不设
    `app.state.remote_client`，所以 `/auth/login` 走的是本地认证那一支（实跑确认）。
    """
    from katrain.web.api.v1.endpoints.auth import SHADOW_USER_NO_LOCAL_AUTH
    from katrain.web.server import create_app

    app = create_app(enable_engine=False)
    app.state.session_factory = isolated_session_factory
    with TestClient(app) as c:
        app.state.user_repo.create_user("shadowy", SHADOW_USER_NO_LOCAL_AUTH)
        app.state.user_repo.create_user("normal", get_password_hash("pw"))
        yield c


def test_login_with_sentinel_hash_user_returns_401_not_500(client_with_sentinel_user):
    """结构断言：哨兵口令账号走完整条 `/auth/login` 拿到的是 401。
    这条挡的是"以后有人在别处又塞一个哨兵值"。

    `/auth/login` 收的是 **JSON**（`login_data: LoginRequest`，
    `katrain/web/api/v1/endpoints/auth.py:232`），不是表单。用 `data=` 会拿到 422，
    那时红的原因与 `verify_password` 无关，而最省事的"修法"是把断言改成 422 ——
    那条用例从此什么都证明不了。全仓既有的 20 处 `auth/login` 调用都用 `json=`。"""
    c = client_with_sentinel_user
    # 对照组先跑：证明这条路本来就通、库里真的建上了人。
    # 没有它的话，`create_user` 静默失败也会给出 401（"用户不存在"），一样绿。
    ok = c.post("/api/v1/auth/login", json={"username": "normal", "password": "pw"})
    assert ok.status_code == 200, ok.text

    r = c.post("/api/v1/auth/login", json={"username": "shadowy", "password": "x"})
    assert r.status_code == 401
