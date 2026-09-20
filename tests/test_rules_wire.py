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

import json
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


# ──────────────────────────────────────────────────────────────────────────────
# 被提交的那份默认值,自己不能自相矛盾。
# ──────────────────────────────────────────────────────────────────────────────


def _kiosk_even_komi() -> dict[str, float]:
    """规则 wire → 分先贴目。和上面那张表是同一份操作数,多取一列。"""
    src = SETUP_OPTIONS.read_text(encoding="utf-8")
    table = re.search(r"export const RULES: RuleDef\[\] = \[(.*?)\n\];", src, re.S)
    assert table, "kiosk 的 RULES 表找不到了 —— 表挪了地方,这条闸要跟着改,不是删掉"
    const = re.search(r"export const RULE_WIRE_BUTTON = '([^']+)';", src)
    out: dict[str, float] = {}
    for wire_expr, komi in re.findall(r"wire:\s*([^,]+),.*?evenKomi:\s*([\d.]+)", table.group(1)):
        wire_expr = wire_expr.strip()
        if wire_expr.startswith("'"):
            wire = wire_expr.strip("'")
        else:
            assert const, f"{wire_expr} 不是字面量也查不到常量 —— 这条闸读不到它,请改成读得到的形式"
            wire = const.group(1)
        out[wire] = float(komi)
    return out


def test_kiosk_even_komi_table_is_readable():
    """闸自己要先能取到操作数。"""
    komis = _kiosk_even_komi()
    assert komis.get("japanese") == 6.5 and komis.get("chinese") == 7.5, komis


def test_packaged_config_default_rules_and_komi_agree():
    """`katrain/config.json` 里的 `game/rules` 和 `game/komi` 必须是同一种规则下的一对。

    **这一对不是摆设**:任何**没有显式送 komi/rules** 的建局都拿它当默认值 ——
    `Game.__init__` 在没有 `game_properties` 时直接读 `katrain.config("game/komi")`
    / `("game/rules")`(`katrain/core/game.py:88-93`),`WebKaTrain.start()` 走的就是
    这条路。更要紧的是:首次运行时这份包内 config 会被**整份复制**成
    `~/.katrain/config.json`(`base_katrain.py:_load_config`)—— 盒子上那份就是它,
    一旦写错,错的是设备上的长期默认值,不是某一次会话。

    **实际发生过**:`komi` 在 2026-07-08 的一次 merge(`f06440c4`)里从 6.5 变成 7.5,
    而 `rules` 还是 `japanese`。此前 8 年一直是 6.5。实测那次漂移的后果是
    `get_state()` 报 `komi=7.5 / ruleset='japanese'` —— 日本规则配中国贴目,
    屏上看不出异常,判出来的胜负差一目。没人改过代码,所以没有任何一条既有用例会红。

    闸只认「这一对自洽」,不钉死具体数值 —— 想把默认改成中国规则 7.5 是正当的,
    连着改两个值就行;这条挡的是**只改了其中一个**。
    """
    config = json.loads((Path(__file__).resolve().parents[1] / "katrain" / "config.json").read_text("utf-8"))
    game = config["game"]
    rules, komi = game["rules"], float(game["komi"])
    expected = _kiosk_even_komi()
    assert rules in expected, (
        f"katrain/config.json 的 game/rules={rules!r} 不在 kiosk 规则表里 —— "
        f"要么它写错了,要么表里该补一项。表里有:{sorted(expected)}"
    )
    assert komi == expected[rules], (
        f"katrain/config.json 自相矛盾:game/rules={rules!r} 的分先贴目是 "
        f"{expected[rules]},但 game/komi 写的是 {komi}。"
        f"这一对会被复制成设备上的 ~/.katrain/config.json,并成为所有"
        f"「没显式送 komi」的建局的默认值。"
    )
