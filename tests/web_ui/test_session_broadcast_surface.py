"""WebSocket 广播面的**可枚举性**闸。

## 这条闸在守什么

四棋类对战大厅的共享 wire 契约(smartbox 仓 `superpowers/shared/lobby-wire/contract.json`)
里,`variant_local.go.room_server` 记着围棋在 session socket 上产出的全部 type。那份清单
**不是手写的** —— 对面仓有一条闸(`test_wire_contract.py::test_go_local_types_match_vendored_katrain`)
从 submodule 里的本仓源码扫出来,要求两集相等。

**本文件守的是那条扫描的前提。** 它扫得到东西,靠的是今天代码的两个性质:

1. `message_callback(<type>, ...)` 的首参全是字符串字面量。这条路径上 type 名离广播点
   十万八千里 —— `SessionManager._on_message` 是个泛型透传管道
   (`{"type": msg_type, "data": data}`),对广播点做字面量扫描在那里只能抓到一个叫
   `msg_type` 的变量名。`sound` / `log` / `game_report` 三个 type **只走这条路**。
2. 广播的 payload 是字面量字典、且 `"type"` 的值是字面量。只有两处例外,写在
   `_NON_LITERAL_PAYLOAD_ALLOWLIST` 里,每条附理由。

这两条性质**今天成立,而在此之前没有任何东西在执行它们**。谁哪天写成
`self.message_callback(kind, ...)`,对面那条闸不会红 —— 那个 type 只是从清单里**消失**,
而「清单少了一条」和「本来就只有这些」在报告上长得一模一样。

## 为什么每条闸都配正对照

这是 2026-08-18 那一天三个 track 反复撞上的同一个形状:**闸本身是对的,而闸的输入面
可以是空的或残缺的** —— 逐条列举的 parametrize 只列了想到的那几个;手写清单没有产出方
可比对;生成器跑的时候目标目录还不存在。三次都不是「断言写错了」,是「断言的对象在那
一刻恰好是空的或残缺的」。

所以下面每条闸都配一条**证明扫描面非空、而且真的咬到了肉**的正对照。没有它,把扫描面
掐断就能让全部断言变成恒真,而且会一直绿到有人真的加了一个动态 type 为止。

## 变异记录(2026-08-18,四处,逐条核过红在哪一句)

写在这里而不是留在提交信息里:**下一个人要判断这些断言值不值得信,靠的是它们红过什么,
而提交信息不会跟着文件走。**

| 变异 | 结果 |
|---|---|
| `message_callback("sound", …)` 首参改成变量 | 主闸 1 红,**只有它**(1 failed / 5 passed) |
| 非白名单函数里加一处 `{"type": some_kind, …}` | 主闸 2 红,只有它 |
| `_python_sources()` 返回 `[]`(掐断扫描面) | 正对照红 + 僵尸闸红,**而两条主闸原地变成恒真绿** |
| 把聊天那处改成字面量(模拟修完忘了删豁免) | 那条僵尸闸红,只有它 |

第三条是这组里唯一**证明了正对照有用**的那一条:掐断扫描面之后两条主闸不但没红,反而
变绿了 —— 「闸的输入面可以是空的」在这个文件里不是一句告诫,是跑得出来的。

第四条那次是真的发生过:聊天那处修好之后,`test_the_allowlist_has_no_zombies[key0]` 当场
红,逼着把那条豁免删掉。**过期的豁免比没有豁免更危险,因为它看起来是被想过的。**

⚠️ **这组变异守的全是「坏的时候会不会红」。反方向 —— 「好的时候会不会绿」 —— 只被覆盖到
一半**:上面每行的「只有它」记录的正是「其余的仍然绿」。缺的是**把目标状态造出来跑一次**
的那种形式化断言。本文件的闸不是休眠闸(操作数今天就在,正对照证明了扫描面非空),所以
「在真实树上绿」本身带信息;但对**操作数还不存在**的闸(等外部落地的、等豁免过期的、
等状态翻转的),真实树上的绿什么都不说明,那种闸必须单独造目标状态验一次放行。
"""

import ast
from pathlib import Path

import pytest

import katrain.web

_WEB_ROOT = Path(katrain.web.__file__).resolve().parent
_REPO_ROOT = _WEB_ROOT.parent.parent

# 三个把 payload 送上 socket 的方法。`broadcast` 是大厅 socket、另两个是对局 socket ——
# 两条 socket 的 type 都要可枚举,契约按段分开记,闸不必分。
_BROADCAST_METHODS = ("broadcast_to_session", "_schedule_broadcast", "broadcast")

# 广播点的 type 不是字面量。key = (相对路径, 最内层函数名) —— **不用行号**,
# 行号会漂,而漂掉之后白名单会静默失配、把一个真的违规当成新增。
_NON_LITERAL_PAYLOAD_ALLOWLIST = {
    ("katrain/web/session.py", "broadcast_to_session"): (
        "转发体,不是独立发射点:它把调用方给的 payload 原样交给 _schedule_broadcast。"
        "type 名在调用方那一侧,已被本文件的其它断言覆盖。"
    ),
    ("katrain/web/session.py", "_on_message"): (
        '泛型透传管道 `{"type": msg_type, ...}` —— **本文件两条主闸的接缝就在这里**。'
        "它的 type 名全部来自 `message_callback` 的调用点,而那些调用点由主闸 1 钉成字面量。"
        "所以这一处豁免是**有条件的**:主闸 1 一旦被删或放宽,这条管道立刻变成一个"
        "任意 type 都能上 wire 的洞。两条闸互为对方的前提。"
    ),
}


def _python_sources() -> list[Path]:
    return sorted(p for p in _WEB_ROOT.rglob("*.py") if "__pycache__" not in p.parts)


def _rel(path: Path) -> str:
    return path.relative_to(_REPO_ROOT).as_posix()


def _enclosing_function(tree: ast.AST, lineno: int) -> str | None:
    """包住 lineno 的最内层函数名。嵌套函数取最内的那个(本仓的路由全是闭包)。"""
    best = None
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.lineno <= lineno <= (node.end_lineno or node.lineno):
                if best is None or node.lineno > best.lineno:
                    best = node
    return best.name if best else None


def _calls_named(name: str) -> list[tuple[str, int, ast.Call, ast.AST]]:
    """全部 `<something>.name(...)` 与 `name(...)` 调用点,连同它所在的文件与树。"""
    found = []
    for path in _python_sources():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            hit = (isinstance(func, ast.Attribute) and func.attr == name) or (
                isinstance(func, ast.Name) and func.id == name
            )
            if hit:
                found.append((_rel(path), node.lineno, node, tree))
    return found


def _message_callback_calls():
    """`message_callback(...)` 的**调用**点 —— 赋值(`x.message_callback = ...`)不是调用,
    AST 天然区分,不会像 grep 那样需要事后过滤。"""
    return _calls_named("message_callback")


def _broadcast_calls():
    out = []
    for name in _BROADCAST_METHODS:
        out.extend(_calls_named(name))
    # 方法定义体内的递归/转发调用会被上面抓到,这没问题:它们要么 type 是字面量,
    # 要么在白名单里。真正要排除的只有 `def` 本身,而 def 不是 Call。
    return out


def _broadcast_type_literal(call: ast.Call) -> str | None:
    """这个广播点的 `"type"` 值,当且仅当它是字符串字面量;否则 None。

    **判据只有这一份** —— 主闸和白名单僵尸闸共用它。两处各写一份的话,「什么算已修好」
    会在两处慢慢分叉,而分叉的那天僵尸闸会开始给一条真的违规发通行证。
    """
    payloads = [a for a in call.args if not isinstance(a, ast.Starred)]
    payload = payloads[-1] if payloads else None
    if not isinstance(payload, ast.Dict):
        return None
    for key, value in zip(payload.keys, payload.values):
        if isinstance(key, ast.Constant) and key.value == "type":
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                return value.value
            return None
    return None


# ---------------------------------------------------------------- 正对照


def test_the_scanner_reaches_both_emission_paths():
    """**先证明扫描面非空,而且两条发射路径各自咬到了肉。**

    没有这一条,下面两条断言可以靠「什么都没扫到」满足 —— 那是恒真守卫。这里不写死数量
    (数量会随功能增删漂),写死的是**两条路径都必须有产出**,以及各自一个今天确实存在、
    而且**只走该路径**的代表:

    - `sound` 只走 message_callback(`interface.py`),字面量广播点扫描对它零命中;
    - `spectator_count` 只走 broadcast_to_session(`server.py`),message_callback 扫描对它零命中。

    这两个代表互为对方的反证:少扫一条路径,就有一个代表落空。
    """
    mc_names = {
        call.args[0].value
        for _, _, call, _ in _message_callback_calls()
        if call.args and isinstance(call.args[0], ast.Constant)
    }
    assert "sound" in mc_names, "message_callback 那条路径没扫到 —— sound 只走它"

    bc_types = {t for _, _, call, _ in _broadcast_calls() if (t := _broadcast_type_literal(call))}
    assert "spectator_count" in bc_types, "广播点那条路径没扫到 —— spectator_count 只走它"


# ---------------------------------------------------------------- 主闸 1


def test_every_message_callback_type_is_a_string_literal():
    """`message_callback` 的首参必须是字符串字面量。

    它是 `SessionManager._on_message` 那条泛型透传管道的**唯一** type 名来源
    (`session.py`:`{"type": msg_type, "data": data}`)。写成变量,静态扫描就再也说不出
    这条 socket 上会飞过什么 —— 而这不是本仓自己的问题:对面仓那条契约闸读的就是这里。

    如果确实需要动态 type,那要先改契约的分层办法,不是在这里放行。
    """
    offenders = []
    for rel, lineno, call, _ in _message_callback_calls():
        if not call.args:
            offenders.append(f"{rel}:{lineno} 没有位置参数")
        elif not (isinstance(call.args[0], ast.Constant) and isinstance(call.args[0].value, str)):
            offenders.append(f"{rel}:{lineno} 首参不是字符串字面量")
    assert not offenders, (
        "message_callback 的 type 名必须是字面量,否则 wire 契约的 variant_local.go "
        "清单扫不到它,而缺一条与本来就只有这些**在报告上长得一模一样**:\n  " + "\n  ".join(offenders)
    )


# ---------------------------------------------------------------- 主闸 2


def test_every_broadcast_payload_is_a_literal_dict_with_a_literal_type():
    """广播 payload 必须是字面量字典、`"type"` 的值必须是字面量。

    白名单里那两处是**明确的例外**,不是漏网:一处是转发体,一处是聊天回广播(它同时是
    一个待修的安全缺口,理由写在白名单条目里)。新增任何一处,都要在白名单里写下理由 ——
    **写理由这个动作本身就是闸**:写不出来的,多半就是不该那么写。
    """
    offenders = []
    for rel, lineno, call, tree in _broadcast_calls():
        if _broadcast_type_literal(call) is not None:
            continue
        if (rel, _enclosing_function(tree, lineno)) in _NON_LITERAL_PAYLOAD_ALLOWLIST:
            continue
        offenders.append(f"{rel}:{lineno}")
    assert not offenders, (
        "这些广播点的 payload 不是带字面量 type 的字典。要么改成字面量,要么在 "
        "_NON_LITERAL_PAYLOAD_ALLOWLIST 里加一条**带理由**的豁免:\n  " + "\n  ".join(offenders)
    )


# ---------------------------------------------------------------- 白名单不许养僵尸


@pytest.mark.parametrize("key", sorted(_NON_LITERAL_PAYLOAD_ALLOWLIST))
def test_the_allowlist_has_no_zombies(key):
    """白名单每条都必须**仍然**对应一个真的非字面量广播点。

    聊天那条修完之后,如果没人删掉它的豁免,下一个在同一个函数里写非字面量广播的人会
    白白继承这条许可 —— 而豁免的理由早已不成立。**过期的豁免比没有豁免更危险**,
    因为它看起来是被想过的。
    """
    rel_target, fn_target = key
    for rel, lineno, call, tree in _broadcast_calls():
        if rel != rel_target or _enclosing_function(tree, lineno) != fn_target:
            continue
        if _broadcast_type_literal(call) is None:
            return
    pytest.fail(f"白名单条目 {key} 已经没有对应的非字面量广播点了 —— 删掉它。")
