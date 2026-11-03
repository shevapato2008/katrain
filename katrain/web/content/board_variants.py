"""Conservative, source-pinned translations of certified local exercises to 19x19.

The replay proves equivalence of the *recorded* branches, not completeness of a
puzzle tree or safety of arbitrary future play. A separate, executable local
postcondition and reviewed source text are required before any variant is used.
"""

import copy
import hashlib
import json
import re
from functools import lru_cache
from pathlib import Path

from katrain.core.sgf_parser import SGF, ParseError

POLICY_VERSION = "kiosk19-local-v1"
TARGET_SIZE = 19
STRUCTURE_FIELDS = (
    "source_id",
    "lesson_id",
    "step",
    "page",
    "source_url",
    "size",
    "initial_player",
    "stones",
    "letters",
    "shapes",
    "viewport",
    "exercise",
)
DETAIL_FIELDS = ("id", "boardSize", "initialBlack", "initialWhite", "hint", "category", "sgfContent")
ROOT_PROPERTIES = {"GM", "FF", "CA", "AP", "SZ", "GN", "AN", "SO", "GC", "C", "AB", "AW", "PL"}


class Unavailable(ValueError):
    pass


def digest(value):
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def tsumego_source_hash(detail):
    return digest({key: detail.get(key) for key in DETAIL_FIELDS})


def ogs_source_hash(step):
    return digest({key: step.get(key) for key in STRUCTURE_FIELDS})


def locale_hash(step):
    text = step["locale"]["text"]
    return digest({key: text.get(key) for key in ("title", "instruction", "choices")})


@lru_cache(maxsize=1)
def _policy():
    try:
        data = json.loads(Path(__file__).with_name("kiosk19_policy.json").read_text(encoding="utf-8"))
        return data if data.get("policy_version") == POLICY_VERSION else {}
    except (OSError, ValueError):
        return {}


def _size(value):
    if type(value) is not int or not 2 <= value <= 19:
        raise Unavailable("棋盘尺寸不在本次支持范围")
    return value


def _point(value, n):
    if (
        not isinstance(value, (list, tuple))
        or len(value) != 2
        or any(type(v) is not int or not 0 <= v < n for v in value)
    ):
        raise Unavailable("坐标越界或格式不受支持")
    return tuple(value)


def _sgf_point(value, n):
    if not isinstance(value, str) or not re.fullmatch("[a-s]{2}", value):
        raise Unavailable("SGF含pass、压缩点或本次不支持的坐标")
    return _point([ord(c) - 97 for c in value], n)


def _coord(p):
    return "".join(chr(97 + v) for v in p)


def _neighbors(point, n):
    x, y = point
    return {(a, b) for a, b in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)) if 0 <= a < n and 0 <= b < n}


def _group(board, start, n):
    color = board[start]
    group, liberties, pending = set(), set(), [start]
    while pending:
        point = pending.pop()
        if point in group:
            continue
        group.add(point)
        for neighbor in _neighbors(point, n):
            if neighbor not in board:
                liberties.add(neighbor)
            elif board[neighbor] == color and neighbor not in group:
                pending.append(neighbor)
    return group, liberties


def _groups(board, n, color=None):
    remaining = {p for p, c in board.items() if color is None or color == c}
    result = []
    while remaining:
        group, liberties = _group(board, min(remaining), n)
        result.append((group, liberties))
        remaining -= group
    return result


def _signature(board):
    return tuple(sorted((p[0], p[1], c) for p, c in board.items()))


def _play(board, point, player, n, history):
    if point in board:
        raise Unavailable("源答案在已有棋子处落子")
    result = board.copy()
    result[point] = player
    captured = set()
    for neighbor in _neighbors(point, n):
        if result.get(neighbor) and result[neighbor] != player:
            group, liberties = _group(result, neighbor, n)
            if not liberties:
                captured |= group
                for stone in group:
                    del result[stone]
    if not _group(result, point, n)[1]:
        raise Unavailable("源答案含自杀手")
    signature = _signature(result)
    if len(history) >= 2 and signature == history[-2]:
        raise Unavailable("源答案含未解决的劫重复")
    if signature in history:
        raise Unavailable("源答案出现重复局面，本次未认证规则")
    return result, captured


def _initial(stones, n):
    if not isinstance(stones, dict) or set(stones) != {"B", "W"}:
        raise Unavailable("初始棋子格式不受支持")
    board = {}
    for color in ("B", "W"):
        for point in stones[color]:
            point = _point(point, n)
            if point in board:
                raise Unavailable("初始棋子重叠")
            board[point] = color
    if any(not liberties for _, liberties in _groups(board, n)):
        raise Unavailable("源初始棋块无气")
    return board


def _offset(points, n):
    if not points:
        raise Unavailable("没有可认证的局部目标")
    offsets = []
    for axis in (0, 1):
        low = any(p[axis] == 0 for p in points)
        high = any(p[axis] == n - 1 for p in points)
        if low and high:
            raise Unavailable("相反两边均参与，19路平移不能保持边界")
        offsets.append(0 if low else 19 - n if high else (19 - n) // 2)
    return tuple(offsets)


def _shift(p, offset):
    return p[0] + offset[0], p[1] + offset[1]


def _state_facts(board, n, offset=(0, 0)):
    groups = []
    for group, liberties in _groups(board, n):
        groups.append(
            {
                "color": board[min(group)],
                "stones": sorted(_shift(p, offset) for p in group),
                "liberties": sorted(_shift(p, offset) for p in liberties),
            }
        )
    groups.sort(key=lambda g: g["stones"])
    return groups


def _replay(board, tree, player, n, offset):
    """Compare each node, captures, all groups/liberties, turn and repetition history."""
    if player not in ("B", "W"):
        raise Unavailable("未能确认源题轮到方")
    moved = {_shift(p, offset): c for p, c in board.items()}
    leaves, trajectory = [], []
    stack = [(tree, board, moved, player, [_signature(board)], [_signature(moved)], [])]
    while stack:
        node, original, derived, turn, history, other_history, path = stack.pop()
        a, b = _state_facts(original, n, offset), _state_facts(derived, 19)
        if a != b:
            raise Unavailable("扩盘改变了棋块连接或气集合")
        trajectory.append(
            {
                "path": path,
                "groups": len(a),
                "liberties": sum(len(g["liberties"]) for g in a),
                "state_sha256": digest(a),
            }
        )
        children = node.get("children", [])
        if children and (node.get("correct") or node.get("wrong")):
            raise Unavailable("源树在非叶节点判终局，本次未认证")
        if not children:
            if node.get("correct") == node.get("wrong"):
                raise Unavailable("源答案叶未明确区分正确与失败")
            leaves.append({"path": path, "point": node.get("point"), "correct": node["correct"], "board": original})
        for index, child in reversed(list(enumerate(children))):
            if child.get("player", turn) != turn:
                raise Unavailable("源答案行棋方不交替")
            point = _point(child["point"], n)
            next_a, captures_a = _play(original, point, turn, n, history)
            next_b, captures_b = _play(derived, _shift(point, offset), turn, 19, other_history)
            if {_shift(p, offset): c for p, c in next_a.items()} != next_b or {
                _shift(p, offset) for p in captures_a
            } != captures_b:
                raise Unavailable("扩盘改变了落子或提子结果")
            repeat_a = [_signature(next_a) == h for h in history]
            repeat_b = [_signature(next_b) == h for h in other_history]
            if repeat_a != repeat_b:
                raise Unavailable("扩盘改变了重复局面关系")
            trajectory.append({"path": path + [index], "player": turn, "point": point, "captures": sorted(captures_a)})
            stack.append(
                (
                    child,
                    next_a,
                    next_b,
                    "W" if turn == "B" else "B",
                    history + [_signature(next_a)],
                    other_history + [_signature(next_b)],
                    path + [index],
                )
            )
    if not any(leaf["correct"] for leaf in leaves):
        raise Unavailable("源答案没有明确正确叶")
    return leaves, trajectory


def _prepare_tsumego(detail):
    n = _size(detail["boardSize"])
    root = SGF.parse_sgf(detail["sgfContent"])
    if root.get_property("SZ") != str(n):
        raise Unavailable("源SGF尺寸与题目不一致")
    if root.get_property("PL") not in ("B", "W"):
        raise Unavailable("未能确认源题轮到方")
    points = []
    nodes = root.nodes_in_tree
    converted = {}
    for node in reversed(nodes):
        allowed = ROOT_PROPERTIES if node is root else {"B", "W", "C"}
        if set(node.properties) - allowed:
            raise Unavailable("SGF含本次不支持的属性或节点setup")
        moves = [(c, v) for c in ("B", "W") for v in node.get_list_property(c, [])]
        if (node is root and moves) or (node is not root and len(moves) != 1):
            raise Unavailable("SGF节点落子格式不受支持")
        for prop in ("AB", "AW", "B", "W"):
            for value in node.get_list_property(prop, []):
                points.append(_sgf_point(value, n))
        comment = node.get_property("C", "")
        converted[id(node)] = {
            "children": [converted[id(c)] for c in node.children],
            "correct": "✓ 正确" in comment,
            "wrong": "✗ 失败" in comment,
        }
        if moves:
            converted[id(node)].update(player=moves[0][0], point=_sgf_point(moves[0][1], n))
    for field, prop in (("initialBlack", "AB"), ("initialWhite", "AW")):
        if sorted(detail[field]) != sorted(root.get_list_property(prop, [])):
            raise Unavailable("源初始棋子与SGF不一致")
    board = _initial(
        {c: [_sgf_point(p, n) for p in detail["initial" + name]] for c, name in [("B", "Black"), ("W", "White")]}, n
    )
    return n, board, converted[id(root)], root.get_property("PL"), _offset(points, n), root


def _prepare_ogs(step):
    n = _size(step["size"])
    allowed = set(STRUCTURE_FIELDS) | {"book_id", "figure_id", "locale", "screenshot", "screenshot_status"}
    if set(step) - allowed:
        raise Unavailable("教程含本次不支持的结构字段")
    board = _initial(step["stones"], n)
    points = list(board)
    for key in ("letters", "shapes"):
        for value in step[key]:
            if not re.fullmatch(r"\d+,\d+", value):
                raise Unavailable("标记坐标格式不受支持")
            points.append(_point([int(a) for a in value.split(",")], n))
    viewport = step["viewport"]
    if viewport is not None:
        if set(viewport) != {"col", "row", "cols", "rows"}:
            raise Unavailable("视窗格式不受支持")
        points.extend(
            [
                _point([viewport["col"], viewport["row"]], n),
                _point([viewport["col"] + viewport["cols"] - 1, viewport["row"] + viewport["rows"] - 1], n),
            ]
        )
    exercise = step["exercise"]
    kind = exercise["kind"]
    if kind == "choice":
        if set(exercise) != {"kind", "choices", "correct_choice"}:
            raise Unavailable("选择题结构不受支持")
        tree = None
    elif kind == "puzzle":
        if set(exercise) != {"kind", "tree"}:
            raise Unavailable("答案结构不受支持")
        tree = exercise["tree"]
        stack = [(tree, True)]
        while stack:
            node, is_root = stack.pop()
            if (
                set(node) != {"point", "correct", "wrong", "children"}
                or type(node["correct"]) is not bool
                or type(node["wrong"]) is not bool
            ):
                raise Unavailable("答案节点格式不受支持")
            if is_root:
                if node["point"] is not None:
                    raise Unavailable("答案根节点格式不受支持")
            else:
                points.append(_point(node["point"], n))
            stack.extend((child, False) for child in node["children"])
    else:
        raise Unavailable("整盘终局教学保留原盘")
    return n, board, tree, step["initial_player"], _offset(points, n), None


def _goal_certificate(goal, board, leaves, n, exercise=None):
    """Recompute a concrete predicate independent of author's correct flags."""
    family = goal["family"]
    color = goal["player"]
    targets = [set(map(tuple, group)) for group in goal.get("targets", [])]
    initial_groups = {frozenset(g) for g, _ in _groups(board, n, color)}
    if any(frozenset(t) not in initial_groups for t in targets):
        raise Unavailable("证书目标不是指定方的固定初始棋块")
    if family == "choice":
        predicate = goal["predicate"]
        if predicate == "liberties":
            if len(targets) != 1:
                raise Unavailable("数气证书缺少唯一目标")
            answer = str(len(_group(board, min(targets[0]), n)[1]))
        elif predicate == "chains":
            answer = str(len(_groups(board, n, color)))
        elif predicate == "atari_count":
            answer = str(sum(len(libs) == 1 for _, libs in _groups(board, n, color)))
        elif predicate == "marked_atari":
            if len(targets) != 1:
                raise Unavailable("打吃证书缺少唯一目标")
            answer = "yes" if len(_group(board, min(targets[0]), n)[1]) == 1 else "no"
        elif predicate == "compare_liberties":
            counts = {}
            for c in ("B", "W"):
                target = set(map(tuple, goal["comparison_targets"][c]))
                if frozenset(target) not in {frozenset(g) for g, _ in _groups(board, n, c)}:
                    raise Unavailable("比较气数未指定固定初始棋块")
                counts[c] = len(_group(board, min(target), n)[1])
            answer = "same" if counts["B"] == counts["W"] else "Black" if counts["B"] > counts["W"] else "White"
        else:
            raise Unavailable("本次没有该选择题的局部证书")
        values = [choice["value"] for choice in exercise["choices"]]
        if len(values) != len(set(values)) or answer not in values or exercise["correct_choice"] != answer:
            raise Unavailable("重算结果与源选择题答案不符")
        expected_label = {"yes": "Yes", "no": "No"}.get(answer, answer)
        if next(c["label_key"] for c in exercise["choices"] if c["value"] == answer) != expected_label:
            raise Unavailable("重算答案与源选择键不符")
        return {"family": family, "predicate": predicate, "answer": answer, "targets": goal.get("targets", [])}
    if not targets:
        raise Unavailable("证书缺少固定初始目标")
    if family == "escape" and (len(targets) != 1 or len(_group(board, min(targets[0]), n)[1]) != 1):
        raise Unavailable("解除打吃目标并非初始一气棋块")
    if (family == "connect" and len(targets) < 2) or (family == "cut" and len(targets) != 2):
        raise Unavailable("连接证书缺少固定初始棋块")
    if family == "cut":
        point = _point(goal["connection_point"], n)
        connected, _ = _play(board, point, color, n, [_signature(board)])
        if not targets[0] | targets[1] <= _group(connected, min(targets[0]), n)[0]:
            raise Unavailable("源切断点不能连接所问两块棋")
    rescue_targets = [set(map(tuple, group)) for group in goal.get("rescue_targets", [])]
    rescuer = "W" if color == "B" else "B"
    for target in rescue_targets:
        if frozenset(target) not in {frozenset(g) for g, l in _groups(board, n, rescuer) if len(l) == 1}:
            raise Unavailable("证书救出目标不是初始一气棋块")
    leaf_stats = []
    for leaf in leaves:
        end = leaf["board"]
        survivors = [{p for p in target if end.get(p) == color} for target in targets]
        liberties = [len(_group(end, min(s), n)[1]) if s else 0 for s in survivors]
        if family == "capture":
            achieved = all(not s for s in survivors)
        elif family == "escape":
            achieved = survivors[0] == targets[0] and liberties[0] >= 2
        elif family == "connect":
            achieved = (
                all(s == t for s, t in zip(survivors, targets))
                and set().union(*targets) <= _group(end, min(targets[0]), n)[0]
            )
        elif family == "cut":
            point = tuple(goal["connection_point"])
            achieved = all(s == t for s, t in zip(survivors, targets)) and end.get(point) == (
                "W" if color == "B" else "B"
            )
            achieved = achieved and not targets[0] | targets[1] <= _group(end, min(targets[0]), n)[0]
        elif family == "fill_liberty":
            achieved = len(leaf["path"]) == 1 and tuple(leaf["point"]) in _group(board, min(targets[0]), n)[1]
        else:
            raise Unavailable("本次没有该目标的局部证书")
        rescue_stats = []
        for target in rescue_targets:
            survivors_own = {p for p in target if end.get(p) == rescuer}
            own_liberties = len(_group(end, min(survivors_own), n)[1]) if survivors_own else 0
            achieved = achieved and survivors_own == target and own_liberties >= 2
            rescue_stats.append({"survivors": len(survivors_own), "liberties": own_liberties})
        if achieved != leaf["correct"]:
            raise Unavailable("正确或失败分支未满足固定局部目标证书")
        leaf_stats.append(
            {
                "path": leaf["path"],
                "correct": leaf["correct"],
                "target_survivors": [len(s) for s in survivors],
                "target_liberties": liberties,
                "rescued": rescue_stats,
                "achieved": achieved,
            }
        )
    return {"family": family, "targets": goal["targets"], "leaves": leaf_stats}


def verify_goal(prepared, goal, exercise=None):
    n, board, tree, player, offset, _ = prepared
    if tree is None:
        # Exact setup liberties and adjacency must also hold for choice exercises.
        moved = {_shift(p, offset): c for p, c in board.items()}
        if _state_facts(board, n, offset) != _state_facts(moved, 19):
            raise Unavailable("扩盘改变了初始棋块或气集合")
        leaves, trajectory = [], [{"state_sha256": digest(_state_facts(board, n)), "groups": len(_groups(board, n))}]
    else:
        leaves, trajectory = _replay(board, tree, player, n, offset)
    certificate = _goal_certificate(goal, board, leaves, n, exercise)
    certificate["goal_sha256"] = digest(goal)
    named_stats = []
    for named in goal.get("named_points", []):
        point = _point(named["point"], n)
        if point in board:
            raise Unavailable("命名的落子点已有棋子")
        outcomes = []
        for position, size, p in [
            (board, n, point),
            ({_shift(p, offset): c for p, c in board.items()}, 19, _shift(point, offset)),
        ]:
            try:
                _, captured = _play(position, p, named["player"], size, [_signature(position)])
                outcomes.append({"legal": True, "captures": len(captured)})
            except Unavailable as exc:
                if str(exc) != "源答案含自杀手":
                    raise
                outcomes.append({"legal": False, "captures": 0})
        if outcomes[0] != outcomes[1] or outcomes[0]["legal"] != named["legal"]:
            raise Unavailable("命名点的合法性不符合源题面")
        named_stats.append({"name": named["name"], **outcomes[0]})
    if named_stats:
        certificate["named_points"] = named_stats
    certificate["trajectory"] = trajectory
    certificate["branch_count"] = len(leaves)
    certificate["node_count"] = sum("state_sha256" in item for item in trajectory)
    certificate["max_depth"] = max((len(leaf["path"]) for leaf in leaves), default=0)
    return certificate


def _adapt(source, kind):
    output = copy.deepcopy(source)
    size_key = "boardSize" if kind == "tsumego" else "size"
    n = source.get(size_key)
    source_hash = tsumego_source_hash(source) if kind == "tsumego" else ogs_source_hash(source)
    metadata = {
        "status": "unavailable",
        "source_size": n,
        "target_size": 19,
        "policy_version": POLICY_VERSION,
        "source_sha256": source_hash,
        "offset": [0, 0],
        "reason": "本次未能确认局部目标",
    }
    output["board_variant"] = metadata
    if n == 19:
        metadata.update(status="original", reason="原生19路")
        return output
    try:
        source_id = str(source["id"] if kind == "tsumego" else source["source_id"])
        entry = _policy().get(kind, {}).get(source_id)
        if entry is None:
            raise Unavailable("本次未审核该来源的局部目标")
        if entry["source_sha256"] != source_hash:
            raise Unavailable("来源内容已改变，需重新审核")
        if kind == "ogs":
            effective = source["locale"]["effective"]
            if effective not in entry.get("locale_sha256", {}):
                raise Unavailable("本语言尚无已审核19路版本")
            if entry.get("locale_sha256", {}).get(effective) != locale_hash(source):
                raise Unavailable("当前语言题面内容已改变，需重新审核")
        if not entry.get("available"):
            raise Unavailable(entry["reason"])
        prepared = _prepare_tsumego(source) if kind == "tsumego" else _prepare_ogs(source)
        if kind == "tsumego":
            root = prepared[5]
            # Hashes attest which complete text was reviewed against this goal;
            # they never infer a goal from category, keywords, or a correct flag.
            evidence = {
                "gc_sha256": digest(root.get_list_property("GC", [])),
                "all_comments_sha256": digest([node.get_list_property("C", []) for node in root.nodes_in_tree]),
                "goal_sha256": digest(entry["goal"]),
            }
            reviewed = entry.get("semantic_review", {})
            if reviewed.get("decision") != "accepted" or any(
                reviewed.get(key) != value for key, value in evidence.items()
            ):
                raise Unavailable("完整题面尚无与当前目标一致的审核证据")
        certificate = verify_goal(prepared, entry["goal"], source.get("exercise"))
        if digest(certificate) != entry["certificate_sha256"]:
            raise Unavailable("局部目标证书校验不一致")
        offset = prepared[4]
        if kind == "tsumego":
            root = prepared[5]
            root.set_property("SZ", "19")
            for node in root.nodes_in_tree:
                for prop in ("AB", "AW", "B", "W"):
                    if prop in node.properties:
                        node.set_property(
                            prop, [_coord(_shift(_sgf_point(v, n), offset)) for v in node.get_list_property(prop)]
                        )
            output.update(
                boardSize=19,
                initialBlack=root.get_list_property("AB", []),
                initialWhite=root.get_list_property("AW", []),
                sgfContent=root.sgf(),
            )
        else:
            output["size"] = 19
            output["viewport"] = None
            output["stones"] = {c: [list(_shift(tuple(p), offset)) for p in ps] for c, ps in source["stones"].items()}
            for key in ("letters", "shapes"):
                output[key] = {
                    ",".join(map(str, _shift(tuple(map(int, p.split(","))), offset))): v for p, v in source[key].items()
                }
            if prepared[2] is not None:
                stack = [output["exercise"]["tree"]]
                while stack:
                    node = stack.pop()
                    if node["point"] is not None:
                        node["point"] = list(_shift(tuple(node["point"]), offset))
                    stack.extend(node["children"])
        metadata.update(status="adapted", offset=list(offset), reason=entry["reason"])
    except Unavailable as exc:
        metadata["reason"] = str(exc)
    except (KeyError, TypeError, ValueError, IndexError, AttributeError, RecursionError, ParseError):
        metadata["reason"] = "源数据或资格清单格式不完整，保留原题"
    if metadata["status"] == "unavailable":
        output = copy.deepcopy(source)
        output["board_variant"] = metadata
    return output


def adapt_tsumego_detail(detail: dict) -> dict:
    return _adapt(detail, "tsumego")


def adapt_ogs_step(step: dict) -> dict:
    return _adapt(step, "ogs")
