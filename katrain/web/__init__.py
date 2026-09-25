"""KaTrain web package.

为什么懒加载:`interface` 在模块级调 `ensure_kivy()`,`server` 拉起整个 FastAPI + DB 栈。
SmartBox 的五子棋后端在它自己的、没有 kivy 也没有 fastapi 的 venv 里复用本包下的
`core.led_service` / `core.camera_hub` / `core.physical_play` / `core.hardware_vision_state`
驱动同一块 19 路 LED 盘(Fan 2026-09-23 拍板:五子棋进程自己跑视觉,直接复用 katrain)。
`katrain/web/core/` 没有 __init__.py,但 Python 导入子模块仍会先执行本文件 ⇒ 即时导入会让那条 import 直接失败。

对围棋侧行为不变:`from katrain.web import create_app` 照常,只是推迟到取用那一刻。
`__getattr__` 对不认识的名字**必须抛 AttributeError** —— `from katrain.web import server`
与 `from katrain.web import session` 这类子模块导入靠的就是这次抛出后的回退(tests/web_ui 有 10 处)。
"""

_LAZY = {
    "NullEngine": "katrain.web.interface",
    "WebKaTrain": "katrain.web.interface",
    "create_app": "katrain.web.server",
    "run_web": "katrain.web.server",
}

__all__ = ["NullEngine", "WebKaTrain", "create_app", "run_web"]


def __getattr__(name):
    module_path = _LAZY.get(name)
    if module_path is None:
        # 必须抛,不能返回 None:import 机制靠这次 AttributeError 回退去找子模块
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    import importlib

    return getattr(importlib.import_module(module_path), name)


def __dir__():
    return sorted(__all__)
