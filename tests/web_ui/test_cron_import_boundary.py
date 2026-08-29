"""`katrain/cron` 的部署边界。

`Dockerfile.cron` 只 `COPY katrain/cron/`，然后 `RUN touch katrain/__init__.py`
——**镜像里除了 `katrain.cron` 没有别的 katrain**，第三方也只有
`requirements-cron.txt` 里那几个。

这条闸守的是一类**只在容器里炸、在本仓永远绿**的错：本仓跑测试时整棵树都在、
开发机的 venv 里什么都装着，`from katrain.core.sgf_parser import SGF` 一路顺畅；
上了盒子/服务器才 `ModuleNotFoundError`，而 cron 是后台进程，它的崩溃在屏上
就是「报告一直排队」。写 `katrain/cron/sgf.py` 那次差点就这么写了 ——
`katrain/core/sgf_parser.py` 现成、正确，可它顶层还 `import chardet`，
两条都不在镜像里。

变异记录（2026-08-25）：
 · 在 `katrain/cron/sgf.py` 顶部加 `from katrain.core.sgf_parser import SGF`
   ⇒ `test_cron_只用镜像里有的东西` 红，报出 `katrain.core.sgf_parser`。
 · 同处加 `import chardet` ⇒ 同一条红，报出 `chardet`。
 · 两条都不加（当前树）⇒ 绿。
"""

import ast
import pathlib
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
CRON_ROOT = REPO_ROOT / "katrain" / "cron"

# 模块名 → `requirements-cron.txt` 里的包名。下面那条断言逼着这两份一起改。
IMAGE_THIRD_PARTY = {
    "apscheduler": "apscheduler",
    "bs4": "beautifulsoup4",
    "httpx": "httpx",
    "sqlalchemy": "sqlalchemy",
    "lxml": "lxml",
    "psycopg2": "psycopg2-binary",
}


def _import_roots() -> dict[str, set[str]]:
    """{顶层模块名: {用到它的文件…}}，含函数体里的延迟 import。"""
    roots: dict[str, set[str]] = {}
    for path in sorted(CRON_ROOT.rglob("*.py")):
        rel = str(path.relative_to(REPO_ROOT))
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                if node.level:  # 相对 import 一定在包内
                    continue
                names = [node.module] if node.module else []
            else:
                continue
            for name in names:
                roots.setdefault(name, set()).add(rel)
    return roots


def test_cron_不引用_katrain_cron_以外的_katrain():
    offenders = {
        name: sorted(files)
        for name, files in _import_roots().items()
        if name.split(".")[0] == "katrain" and not name.startswith("katrain.cron")
    }
    assert not offenders, (
        "Dockerfile.cron 只 COPY katrain/cron/ —— 这些 import 在镜像里是 ModuleNotFoundError："
        f"{offenders}。需要的东西复制一份进 katrain/cron/，别跨过去拿。"
    )


def test_cron_只用镜像里有的东西():
    offenders = {
        name: sorted(files)
        for name, files in _import_roots().items()
        if (root := name.split(".")[0]) != "katrain"
        and root not in sys.stdlib_module_names
        and root not in IMAGE_THIRD_PARTY
    }
    assert not offenders, (
        f"这些第三方包不在 requirements-cron.txt 里，镜像里没有：{offenders}。"
        "要么别用，要么同时加进 requirements-cron.txt 和本文件的 IMAGE_THIRD_PARTY。"
    )


def test_允许清单跟_requirements_cron_对得上():
    """允许清单是手写的映射；这条防它跟需求文件走散。"""
    declared = set()
    for line in (REPO_ROOT / "requirements-cron.txt").read_text().splitlines():
        line = line.split("#")[0].strip()
        if line:
            declared.add(line.split("==")[0].split(">=")[0].split("[")[0].strip().lower())
    assert set(IMAGE_THIRD_PARTY.values()) == declared, (
        "IMAGE_THIRD_PARTY 的包名要和 requirements-cron.txt 一字不差 —— "
        f"清单里有而需求里没有：{set(IMAGE_THIRD_PARTY.values()) - declared}；"
        f"需求里有而清单里没有：{declared - set(IMAGE_THIRD_PARTY.values())}"
    )
