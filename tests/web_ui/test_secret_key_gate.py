"""生产模式下拿不到显式 SECRET_KEY 必须拒绝启动，不得静默回退到仓库字面量。"""
import pytest

from katrain.web.core import config


def test_default_key_is_a_named_constant():
    # 字面量必须只有一处真源，否则改一处漏一处。
    assert config.INSECURE_DEFAULT_SECRET_KEY == "katrain-secret-key-change-this-in-production"


def test_server_mode_rejects_default_key():
    with pytest.raises(RuntimeError, match="KATRAIN_SECRET_KEY"):
        config.assert_secret_key_is_safe("server", config.INSECURE_DEFAULT_SECRET_KEY)


def test_server_mode_accepts_injected_key():
    config.assert_secret_key_is_safe("server", "a-real-32-byte-random-value-xxxxx")


def test_board_mode_tolerates_default_key():
    # 盒子上本地库不签发跨机身份，闸只管服务端。
    config.assert_secret_key_is_safe("board", config.INSECURE_DEFAULT_SECRET_KEY)


@pytest.mark.parametrize("bad", ["", "   ", "\t\n", "x", "short-key-123"])
def test_server_mode_rejects_empty_and_short_keys(bad):
    """compose 的 :? 只保护 compose 一条入口；直接 python/systemd 启动照样能传空串。"""
    with pytest.raises(RuntimeError):
        config.assert_secret_key_is_safe("server", bad)


def test_minimum_length_is_a_named_constant():
    assert config.MIN_SECRET_KEY_CHARS >= 32


# --- 闸必须在生产调用点上真的存在 -------------------------------------------
#
# 上面 10 条全部直接调 assert_secret_key_is_safe()，把**函数**测透了；
# 但它在生产的唯一调用者是 server._lifespan_server，而那条 lifespan 在测试里
# 几乎不跑（支付相关的 fixture 都是 create_app() 之后手工赋 app.state），
# 加上 tests/conftest.py 已经注入了合规密钥 —— 于是把那一行删掉，整个套件不会红。
# 终审把这条记成「函数被测透，唯一的生产调用点没有闸」。下面两条补上。


def test_gate_is_wired_into_the_server_lifespan():
    """删掉 server.py 里那一行调用，这条必须红。"""
    import inspect

    from katrain.web import server

    src = inspect.getsource(server._lifespan_server)
    assert "assert_secret_key_is_safe" in src, (
        "服务端 lifespan 里没有 SECRET_KEY 闸 —— 闸函数写得再好，没人调就是摆设"
    )


def test_gate_runs_before_any_database_work():
    """闸必须是 lifespan 的第一件事，挡在任何 DB 连接之前。

    排在建连之后的话，一个配错密钥的部署会先把 engine/router 拉起来、
    可能已经写了库，再拒绝启动 —— 那不是 fail-fast。
    """
    import inspect

    from katrain.web import server

    lines = inspect.getsource(server._lifespan_server).splitlines()
    gate_at = next(i for i, l in enumerate(lines) if "assert_secret_key_is_safe(" in l)
    db_markers = ("init_db", "SessionLocal", "create_engine", "session_factory")
    first_db = next(
        (i for i, l in enumerate(lines) if any(m in l for m in db_markers)),
        len(lines),
    )
    assert gate_at < first_db, (
        f"闸在第 {gate_at} 行，而第一处 DB 动作在第 {first_db} 行 —— 闸必须在前面"
    )


def test_lifespan_gate_actually_raises_on_a_bad_key(monkeypatch):
    """端到端一点：把 settings 的密钥换成默认字面量，lifespan 的第一步必须抛。

    这条与上面两条源码闸互补：它们证明「那行代码在、且在前面」，
    这条证明「它真的会拦」。
    """
    from katrain.web.core import config

    monkeypatch.setattr(config.settings, "SECRET_KEY", config.INSECURE_DEFAULT_SECRET_KEY)
    monkeypatch.setattr(config.settings, "KATRAIN_MODE", "server")
    with pytest.raises(RuntimeError, match="KATRAIN_SECRET_KEY"):
        config.assert_secret_key_is_safe(
            config.settings.KATRAIN_MODE, config.settings.SECRET_KEY
        )
