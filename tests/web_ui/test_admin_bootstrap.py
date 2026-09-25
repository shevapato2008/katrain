"""server 模式不得创建公开已知口令的管理员账号。"""

import inspect

from katrain.web import server


def test_no_hardcoded_admin_password_in_bootstrap():
    src = inspect.getsource(server)
    assert 'get_password_hash("admin")' not in src, (
        "空库启动时创建 admin/admin —— 那是一个公开已知的管理员口令，"
        "不需要伪造 token 就能拿到赠额和兑换码接口"
    )


def test_admin_flag_is_not_granted_by_username():
    src = inspect.getsource(server)
    assert 'User.username == "admin"' not in src, (
        "按用户名无条件提权 ⇒ 任何人注册叫 admin 的账号都可能被提权"
    )


def test_public_web_has_no_admin_bootstrap_configuration():
    """后台专用账号不得通过公开 web 的配置创建。"""
    from katrain.web.core.config import Settings

    assert "ADMIN_BOOTSTRAP_PASSWORD" not in Settings.model_fields


def test_public_web_never_bootstraps_admin_account():
    """空库启动也不能在公开 users 表中自动创建管理员。"""
    assert "ADMIN_BOOTSTRAP_PASSWORD" not in inspect.getsource(server._lifespan_server)
