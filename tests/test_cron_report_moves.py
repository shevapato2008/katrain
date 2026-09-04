"""cron 不得覆盖 web 写死的 total_moves —— 那是计价操作数。

变异验证（2026-09-05 实测）：临时把
    if not task.total_moves:
        task.total_moves = len(moves)
两行（连同其上三行中文注释）改回无条件的 `task.total_moves = len(moves)`，
`paid_moves = task.total_moves` / `moves = moves[:paid_moves]` 保持不动，
跑 `uv run pytest tests/test_cron_report_moves.py -v`，实际输出：
    test_cron_guards_total_moves_against_unconditional_overwrite FAILED
        AssertionError: 缺少「只在缺失时兜底」的守卫
        assert 'if not task.total_moves:' in '...'
    test_cron_truncates_to_paid_moves_prefix PASSED
    1 failed, 1 passed in 0.05s
（第二条本来就只查截断那一行文本，删守卫不影响它，所以只有第一条红。）
恢复守卫后 `uv run pytest tests/test_cron_report_moves.py -v` 两条都转绿
（2 passed）。
"""
import inspect

from katrain.cron.jobs import report_analyze


def test_cron_guards_total_moves_against_unconditional_overwrite():
    src = inspect.getsource(report_analyze)
    assert "if not task.total_moves:" in src, "缺少「只在缺失时兜底」的守卫"


def test_cron_truncates_to_paid_moves_prefix():
    src = inspect.getsource(report_analyze)
    assert "moves = moves[:paid_moves]" in src, "缺少「只分析已付费前缀」的截断"
