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
