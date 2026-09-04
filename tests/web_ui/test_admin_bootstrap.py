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


def test_bootstrap_password_setting_exists_and_defaults_empty():
    from katrain.web.core.config import settings
    assert settings.ADMIN_BOOTSTRAP_PASSWORD == ""
