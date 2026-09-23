"""盒子上 `GET /tsumego/progress` 只能回**当前这个人**的进度。

成长屏「累计已解题」那一格的数就是从这个端点的响应里数出来的
(`TsumegoProgressContext` → `GrowthPage`),所以这条闸和成长那三个端点是同一件事:

**盒子是共用设备。** `RemoteAPIClient` 是进程级单例,只揣着**最后登录**那个人的云端 token,
而云端是按 token 里的身份算数的 ⇒ 不先问一句「云端认的是谁」,甲的屏上就会显示乙解过的题。

判据同 `RepositoryDispatcher.cloud_session_is`:**绑不上就当不是**。
退回本机是正确的降级 —— 响应头 `X-Data-Authority: local_cache` 就是它的出口。
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from katrain.web.core import models_db
from katrain.web.core.repository import RepositoryDispatcher
from katrain.web.core.tsumego_progress_repo import LocalTsumegoProgressRepository


class _FakeConnectivity:
    is_online = True


class _FakeRemoteTsumego:
    """云端那份进度 —— 属于 `bound_user_id` 那个人,不是当前这个人。"""

    def __init__(self):
        self.calls = 0

    async def get_progress(self):
        self.calls += 1
        return {"cloud-problem": {"problemId": "cloud-problem", "completed": True, "attempts": 1}}


class _FakeRemoteClient:
    def __init__(self, bound_user_id):
        self.bound_user_id = bound_user_id


@pytest.fixture()
def harness(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path/'p.db'}")
    models_db.Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    # 本机这份是**当前用户自己**解的题。
    LocalTsumegoProgressRepository(factory).upsert(1, "mine", {"completed": True, "attempts": 1})
    return factory


def _client(factory, *, bound_user_id):
    from katrain.web.api.v1.endpoints.auth import get_current_user
    from katrain.web.api.v1.endpoints.tsumego import router
    from katrain.web.models import User

    remote_tsumego = _FakeRemoteTsumego()
    app = FastAPI()
    app.include_router(router, prefix="/api/v1/tsumego")
    app.dependency_overrides[get_current_user] = lambda: User(id=1, username="me")
    app.state.repository_dispatcher = RepositoryDispatcher(
        connectivity_manager=_FakeConnectivity(),
        remote_tsumego=remote_tsumego,
        remote_kifu=None,
        remote_user_games=None,
        local_user_game_repo=None,
        local_tsumego_progress_repo=LocalTsumegoProgressRepository(factory),
        remote_client=_FakeRemoteClient(bound_user_id),
    )
    return TestClient(app), remote_tsumego


def test_the_cloud_answers_when_the_session_is_this_user(harness):
    client, remote = _client(harness, bound_user_id="1")
    resp = client.get("/api/v1/tsumego/progress")
    assert resp.status_code == 200
    assert remote.calls == 1
    assert resp.headers["X-Data-Authority"] == "cloud"
    assert "cloud-problem" in resp.json()


@pytest.mark.parametrize("bound", ["2", None], ids=["别人的会话", "没绑过"])
def test_another_users_cloud_session_never_answers(harness, bound):
    client, remote = _client(harness, bound_user_id=bound)
    resp = client.get("/api/v1/tsumego/progress")

    assert resp.status_code == 200
    assert remote.calls == 0, "云端会话不是这个人的,根本不该去问"
    assert resp.headers["X-Data-Authority"] == "local_cache"
    body = resp.json()
    assert "cloud-problem" not in body, "别人解的题不能算进这个人的「累计已解题」"
    assert "mine" in body
