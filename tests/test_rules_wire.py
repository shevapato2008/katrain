"""前端能送出来的每一个规则值,后端都要认得。

**这条闸挡的是一次静默换记分法。** `BaseEngine.get_rules()` 查不到就回退到
`japanese`(`katrain/core/engine.py` 最后一行)—— 而在围棋里,把面积计分的局
按数目法算,胜负会不一样,屏上却看不出任何异常:没有报错、没有降级提示,
一局棋照常下完、照常判出一个结果来。

写它的直接原因:「AI 赛规则」第一版打算把 `aga-button` 原样送给后端,而那个名字
**不在** `RULESETS_ABBR` 里 —— 实测 `get_rules('aga-button') == 'japanese'`。

两半操作数都在这个仓里(前端那张表是 TS 字面量,后端这张是 Python 字面量),
所以闸建在这儿能真的通。TS 那边必须写成**字面量**才读得到;哪天它变成
从别处算出来的值,这条闸会读不到而不是假绿 —— 见下面的 `assert wires`。
"""

import re
from pathlib import Path

import pytest

from katrain.core.engine import BaseEngine

SETUP_OPTIONS = (
    Path(__file__).resolve().parents[1]
    / "katrain" / "web" / "ui" / "src" / "kiosk" / "utils" / "setupOptions.ts"
)


def _kiosk_rule_wires() -> list[str]:
    """从 kiosk 的规则表里摘出 `wire:` 那一列。"""
    src = SETUP_OPTIONS.read_text(encoding="utf-8")
    table = re.search(r"export const RULES: RuleDef\[\] = \[(.*?)\n\];", src, re.S)
    assert table, "kiosk 的 RULES 表找不到了 —— 表挪了地方,这条闸要跟着改,不是删掉"
    wires = re.findall(r"wire:\s*'([^']+)'", table.group(1))
    # `RULE_WIRE_BUTTON` 那一项是常量引用,不是字符串字面量,单独取
    const = re.search(r"export const RULE_WIRE_BUTTON = '([^']+)';", src)
    if "RULE_WIRE_BUTTON" in table.group(1):
        assert const, "RULE_WIRE_BUTTON 不再是字面量了 —— 这条闸读不到它,请改成读得到的形式"
        wires.append(const.group(1))
    return wires


def test_kiosk_rules_table_is_readable():
    """闸自己要先能取到操作数。取不到就是闸瞎了,不是被测的东西对了。"""
    wires = _kiosk_rule_wires()
    assert len(wires) >= 4, f"只读出 {wires} —— 少于 kiosk 屏上那四项,说明正则和表对不上了"
    assert "chinese" in wires and "japanese" in wires


@pytest.mark.parametrize("wire", _kiosk_rule_wires())
def test_every_kiosk_rule_is_known_to_the_engine(wire):
    """每一个值都要**映射到它自己**,不许落进 japanese 那个兜底。"""
    resolved = BaseEngine.get_rules(wire)
    assert resolved == wire, (
        f"kiosk 会送 rules={wire!r},但 get_rules 把它解析成了 {resolved!r}。"
        f"没在 RULESETS_ABBR 里登记的值会静默回退到 japanese —— "
        f"那是换了一种记分法,不是降级。"
    )


def test_the_fallback_still_exists_and_is_still_silent():
    """兜底本身没被改掉 —— 上面那条闸的前提就是它还在、而且还是不吭声的。

    **变异记录(2026-09-21 实测)**:把 `("button", "aga-button")` 从 `RULESETS_ABBR`
    里注释掉,上面那条参数化用例红在
    `test_every_kiosk_rule_is_known_to_the_engine[aga-button]`:
    `assert 'japanese' == 'aga-button'`。还原后全绿。

    第一次变异**没红** —— 当时表里写了 `("button", ...)` 和 `("aga-button", ...)` 两条,
    而 `RULESETS` 的推导式把 `abbr` 和 `name` 两个键都注册,所以删掉任意一条
    另一条都还兜着。两条因此是冗余的,已去掉一条。
    **闸能不能红,和它看起来合不合理是两件事。**
    """
    assert BaseEngine.get_rules("no-such-ruleset") == "japanese"
