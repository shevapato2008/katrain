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


def test_bootstrap_password_field_defaults_to_empty():
    """断的是**字段默认值**，不是当前进程的装配结果。

    `settings.ADMIN_BOOTSTRAP_PASSWORD` 来自 `os.getenv(...)`，开发机上设了
    `KATRAIN_ADMIN_BOOTSTRAP_PASSWORD` 就会让断言变红 —— 那是环境差异，
    不是被测行为出了问题。要守的是「不配就不建账号」这条默认语义。
    """
    from katrain.web.core.config import Settings

    assert Settings.model_fields["ADMIN_BOOTSTRAP_PASSWORD"].default == ""
