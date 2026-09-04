"""katrain/cron 是 Dockerfile.cron 独立复制的子树，不得反向依赖 katrain.web。

变异验证记录（2026-09-05 实测）：在 katrain/cron/jobs/report_analyze.py 顶部临时加
`from katrain.web.core import billing`，本测试 FAIL：

    AssertionError: Dockerfile.cron 只 COPY katrain/cron/，这些跨目录 import 只会
    在容器里炸：['.../katrain/cron/jobs/report_analyze.py']

撤销该行后 PASS。
"""
import pathlib
import re

CRON = pathlib.Path(__file__).resolve().parents[2] / "katrain" / "cron"


def test_cron_never_imports_katrain_web():
    offenders = []
    for py in CRON.rglob("*.py"):
        code = "\n".join(
            l for l in py.read_text(encoding="utf-8").splitlines()
            if not l.lstrip().startswith("#")
        )
        if re.search(r"^\s*(from|import)\s+katrain\.web", code, re.M):
            offenders.append(str(py))
    assert offenders == [], (
        f"Dockerfile.cron 只 COPY katrain/cron/，这些跨目录 import 只会在容器里炸：{offenders}"
    )
