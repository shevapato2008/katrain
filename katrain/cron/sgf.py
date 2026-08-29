"""SGF reader for cron-side report analysis.

**为什么这里自己写一份，而不 import `katrain.core.sgf_parser`：**
`Dockerfile.cron` 只 `COPY katrain/cron/` 然后 `touch katrain/__init__.py` ——
部署镜像里根本没有 `katrain.core`；而且 `katrain/core/sgf_parser.py` 顶层就
`import chardet`，它也不在 `requirements-cron.txt` 里。这两条**都只在容器里炸**，
在本仓跑测试永远绿（整棵树都在）。`tests/web_ui/test_cron_import_boundary.py` 守这条。

所以这份只用标准库，且只解报告分析需要的那几个属性。

## 它比原来那条平铺正则多做的三件事

1. **只走主线。** 原来是 `re.findall(r";([BW])\\[…\\]")` 扫全文 ⇒ 分支谱里的变化图
   被一股脑拼进主线，越往后错得越离谱，而屏上没有任何东西会说它算错了。
2. **读 `AB[]/AW[]/AE[]`。** 原来一个都不读、调用处还写死 `initial_stones=[]`
   ⇒ **任何让子局都是从空盘算出来的报告**。
3. **属性值按 SGF 规则读**（`\\]` 是转义、`[` 在值里不用转义）⇒ 注释里出现
   `;B[…]` 这样的文本不再变成幽灵着手。
"""

import logging
import re
from dataclasses import dataclass, field

logger = logging.getLogger("katrain_cron.sgf")

# SGF 坐标只有 a–z 和 A–Z 两段（>26 路才用到大写），报告只处理 9/13/19 路。
_SGF_LETTERS = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
# GTP 跳过 I。
_GTP_COLUMNS = "ABCDEFGHJKLMNOPQRSTUVWXYZ"

_SIZE_RE = re.compile(r"^\s*(\d+)")


@dataclass
class ParsedGame:
    board_size: int = 19
    komi: float = 7.5
    rules: str = "chinese"
    # [[color, gtp], …]，直接喂给 KataGo 的 initialStones
    initial_stones: list[list[str]] = field(default_factory=list)
    initial_player: str = "B"
    # [(color, gtp), …]，只含主线的落子（含虚手 "pass"）
    moves: list[tuple[str, str]] = field(default_factory=list)
    handicap: int = 0
    result: str | None = None
    # 主线上出现在**第一手之后**的摆子属性 —— KataGo 的 initialStones 表达不了，
    # 只能丢掉。丢掉了就把它记出来，别让它变成又一个安静的错。
    dropped_midgame_setup: int = 0


# ── 词法 ──


def _read_value(text: str, start: int) -> tuple[str, int]:
    """读一个 `[…]` 属性值，返回 (值, 右括号之后的下标)。

    SGF 规则：值里 `]` 和 `\\` 必须转义，`[` 不用。所以 `C[见 ;B[aa\\] 那手]`
    是**一个**值，里面的 `;B[aa]` 是正文不是着手。
    """
    i = start + 1
    out: list[str] = []
    n = len(text)
    while i < n:
        c = text[i]
        if c == "\\":
            if i + 1 < n:
                out.append(text[i + 1])
                i += 2
            else:
                i += 1
        elif c == "]":
            return "".join(out), i + 1
        else:
            out.append(c)
            i += 1
    return "".join(out), i


def _tokenize(sgf: str) -> list[tuple]:
    """→ [('(',), (')',), (';',), ('P', ident, [values]), …]"""
    tokens: list[tuple] = []
    i, n = 0, len(sgf)
    while i < n:
        c = sgf[i]
        if c in "();":
            tokens.append((c,))
            i += 1
        elif c.isalpha():
            j = i
            while j < n and sgf[j].isalpha():
                j += 1
            # 老棋谱里有 `Ff[4]` 这种写法；SGF 规范说标识符只看大写字母。
            ident = "".join(ch for ch in sgf[i:j] if ch.isupper())
            i = j
            values: list[str] = []
            while True:
                k = i
                while k < n and sgf[k].isspace():
                    k += 1
                if k < n and sgf[k] == "[":
                    value, i = _read_value(sgf, k)
                    values.append(value)
                else:
                    break
            if values and ident:
                tokens.append(("P", ident, values))
        else:
            i += 1
    return tokens


def _skip_subtree(tokens: list[tuple], i: int) -> int:
    """tokens[i] 是 '('，返回配对 ')' 之后的下标。"""
    depth = 0
    n = len(tokens)
    while i < n:
        kind = tokens[i][0]
        if kind == "(":
            depth += 1
        elif kind == ")":
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1
    return n


def _main_line_nodes(sgf: str) -> list[dict[str, list[str]]]:
    """主线上的节点，按顺序。

    棋谱树是 `( node+ subtree* )`：主线 = 本层的节点，接上**第一个**子树的主线。
    其余子树整棵跳过 —— 这正是原来那条 `findall` 做不到的事。
    迭代不递归：每手都带一个变化图的谱能嵌到几百层深。
    """
    tokens = _tokenize(sgf or "")
    nodes: list[dict[str, list[str]]] = []
    stack: list[bool] = []  # 每层：本层是否已经进过一个子树
    i, n = 0, len(tokens)
    while i < n:
        kind = tokens[i][0]
        if kind == "(":
            if stack and stack[-1]:
                i = _skip_subtree(tokens, i)
                continue
            if stack:
                stack[-1] = True
            stack.append(False)
            i += 1
        elif kind == ")":
            if stack:
                stack.pop()
            i += 1
            if not stack:
                break  # 收掉最外层；一个文件里的第二盘棋不属于这次分析
        elif kind == ";":
            i += 1
            props: dict[str, list[str]] = {}
            while i < n and tokens[i][0] == "P":
                _, ident, values = tokens[i]
                props.setdefault(ident, []).extend(values)
                i += 1
            nodes.append(props)
        else:
            i += 1
    return nodes


# ── 坐标 ──


def sgf_to_gtp(sgf_coord: str, board_size: int) -> str | None:
    """SGF 坐标 → GTP。虚手返回 "pass"；读不懂返回 None（调用方跳过，别塞个假坐标进去）。"""
    if not sgf_coord:
        return "pass"
    # [tt] 在 ≤19 路上是老写法的虚手。
    if sgf_coord.lower() == "tt" and board_size <= 19:
        return "pass"
    if len(sgf_coord) < 2:
        return None
    col_idx = _SGF_LETTERS.find(sgf_coord[0])
    row_idx = _SGF_LETTERS.find(sgf_coord[1])
    if col_idx < 0 or row_idx < 0:
        return None
    if not (0 <= col_idx < board_size and 0 <= row_idx < board_size):
        return None
    if col_idx >= len(_GTP_COLUMNS):
        return None
    return f"{_GTP_COLUMNS[col_idx]}{board_size - row_idx}"


# ── 解析 ──


def _first(props: dict[str, list[str]], key: str) -> str | None:
    values = props.get(key)
    return values[0] if values else None


def parse_game(sgf: str) -> ParsedGame:
    nodes = _main_line_nodes(sgf)
    game = ParsedGame()
    if not nodes:
        return game

    root = nodes[0]

    size_raw = _first(root, "SZ")  # SZ[19] 或 SZ[19:19]
    if size_raw:
        match = _SIZE_RE.match(size_raw)
        if match:
            try:
                size = int(match[1])
                if 2 <= size <= 52:
                    game.board_size = size
            except ValueError:
                pass

    komi_raw = _first(root, "KM")
    if komi_raw:
        try:
            game.komi = float(komi_raw.strip())
        except ValueError:
            pass

    rules_raw = _first(root, "RU")
    if rules_raw and rules_raw.strip():
        game.rules = rules_raw.strip().lower()

    handicap_raw = _first(root, "HA")
    if handicap_raw:
        try:
            game.handicap = int(handicap_raw.strip())
        except ValueError:
            pass

    result_raw = _first(root, "RE")
    if result_raw and result_raw.strip():
        game.result = result_raw.strip()

    # 摆子按出现顺序累积；AE 是拿掉。用 dict 保序，同一点后写覆盖先写。
    setup: dict[str, str] = {}

    for node in nodes:
        has_setup = any(key in node for key in ("AB", "AW", "AE"))
        if has_setup:
            if game.moves:
                # 第一手之后的摆子 —— initialStones 表达不了，只能丢，但要留声。
                game.dropped_midgame_setup += sum(len(node.get(k, ())) for k in ("AB", "AW", "AE"))
            else:
                for prop, color in (("AB", "B"), ("AW", "W")):
                    for raw in node.get(prop, ()):
                        gtp = sgf_to_gtp(raw, game.board_size)
                        if gtp and gtp != "pass":
                            setup[gtp] = color
                for raw in node.get("AE", ()):
                    gtp = sgf_to_gtp(raw, game.board_size)
                    if gtp:
                        setup.pop(gtp, None)

        for color in ("B", "W"):
            if color not in node:
                continue
            raw = node[color][0]
            gtp = sgf_to_gtp(raw, game.board_size)
            if gtp is None:
                logger.warning("Skipping unparseable SGF coordinate %r on a %d board", raw, game.board_size)
                continue
            game.moves.append((color, gtp))

    game.initial_stones = [[color, gtp] for gtp, color in setup.items()]

    # `initialPlayer` 只在 moves 为空那一帧（第 0 手）说了算，但那一帧是报告的第一格。
    played_first = _first(root, "PL")
    if played_first and played_first.strip().upper() in ("B", "W"):
        game.initial_player = played_first.strip().upper()
    elif game.moves:
        game.initial_player = game.moves[0][0]
    elif any(color == "B" for color in setup.values()):
        game.initial_player = "W"  # 让子局：摆完黑子轮白走

    if game.dropped_midgame_setup:
        logger.warning(
            "SGF has %d setup stones after the first move; KataGo initialStones cannot express them",
            game.dropped_midgame_setup,
        )

    return game
