"""katrain.web 必须懒加载:导入 LED/相机/标定/灯规划这些无 GUI 的子模块不得拉起 kivy。
SmartBox 五子棋后端在自己的 venv(无 kivy、无 fastapi)里 import 它们。"""
import subprocess
import sys

_LEAF_MODULES = [
    "katrain.web.core.led_service",
    "katrain.web.core.camera_hub",
    "katrain.web.core.physical_play",
    "katrain.web.core.hardware_vision_state",
]


def _in_subprocess(code: str) -> subprocess.CompletedProcess:
    # 必须开子进程:本测试进程多半已经 import 过 kivy,在本进程里判等于恒真
    return subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)


def test_leaf_modules_import_without_kivy():
    for mod in _LEAF_MODULES:
        r = _in_subprocess(
            f"import {mod}, sys;"
            "mods=[m for m in sys.modules if m.split('.')[0] in ('kivy','kivymd')];"
            "print('LEAKED:'+','.join(mods) if mods else 'CLEAN')"
        )
        assert r.returncode == 0, f"{mod}: {r.stderr}"
        assert "CLEAN" in r.stdout, f"{mod}: {r.stdout}"


def test_public_names_still_work():
    r = _in_subprocess("from katrain.web import create_app, run_web, NullEngine, WebKaTrain; print('OK')")
    assert r.returncode == 0, r.stderr
    assert "OK" in r.stdout


def test_submodule_import_form_still_works():
    """tests/web_ui 里 9 处用的是这个写法。"""
    r = _in_subprocess("from katrain.web import server; print(server.__name__)")
    assert r.returncode == 0, r.stderr
    assert "katrain.web.server" in r.stdout


def test_a_submodule_absent_from_the_lazy_table_still_imports():
    """test_box_sso.py:38 导入的是 `session`,它不在 _LAZY 表里。
    这条证明回退机制是通用的 —— 不靠把每个子模块都列进表。
    把 __getattr__ 的 raise 改成 return None,这条会红。"""
    r = _in_subprocess("from katrain.web import session; print(session.__name__)")
    assert r.returncode == 0, r.stderr
    assert "katrain.web.session" in r.stdout


def test_unknown_attribute_raises_attribute_error():
    r = _in_subprocess(
        "import katrain.web\n"
        "try:\n"
        "    katrain.web.definitely_not_a_real_name\n"
        "except AttributeError:\n"
        "    print('RAISED')\n"
    )
    assert r.returncode == 0, r.stderr
    assert "RAISED" in r.stdout
