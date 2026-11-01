"""Bounded, legal and reproducible SGF inputs for paid analysis.

Only the first main line is analyzed. Comments, names, markup and other
non-computational metadata do not affect its identity. A canonical SGF freezes
the exact engine input (including expanded initial setup) for the cron reader.
The fingerprint additionally binds kind, catalog, profile, model and visits.

Unknown rule presets, mid-game setup / player changes and custom JSON rules
are explicitly unsupported. This module starts no engine and needs no DB.
"""

import hashlib
import json
import math
import re

from katrain.web.core.billing_catalog import CATALOG_VERSION, MAX_REPORT_MOVES, get_profile

_MAX_SGF_BYTES = 256 * 1024
_GTP_COLUMNS = "ABCDEFGHJKLMNOPQRST"
# Verified against KataGo cpp/game/rules.cpp. Chinese uses SIMPLE, not PSK.
_RULES = {
    "japanese": ("simple", False),
    "korean": ("simple", False),
    "chinese": ("simple", False),
    "chinese-ogs": ("positional", False),
    "stone_scoring": ("simple", False),
    "aga": ("situational", False),
    "aga-button": ("situational", False),
    "new zealand": ("situational", True),
    "tromp-taylor": ("positional", True),
}
_RULE_ALIASES = {
    "jp": "japanese",
    "cn": "chinese",
    "ko": "korean",
    "button": "aga-button",
    "nz": "new zealand",
    "newzealand": "new zealand",
    "new-zealand": "new zealand",
    "tt": "tromp-taylor",
    "tromptaylor": "tromp-taylor",
    "tromp_taylor": "tromp-taylor",
    "chineseogs": "chinese-ogs",
    "chinese_ogs": "chinese-ogs",
}


def _tokens(text):
    """Read every character; unlike the existing readers, never clip/skip junk."""
    i = 0
    while i < len(text):
        char = text[i]
        if char.isspace():
            i += 1
        elif char in "();":
            yield (char,)
            i += 1
        elif char in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz":
            start = i
            while i < len(text) and text[i] in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz":
                i += 1
            # SGF's legacy mixed-case identifiers ignore their lower-case letters.
            key = "".join(c for c in text[start:i] if c.isupper())
            values = []
            while True:
                while i < len(text) and text[i].isspace():
                    i += 1
                if i >= len(text) or text[i] != "[":
                    break
                i += 1
                value = []
                while i < len(text) and text[i] != "]":
                    if text[i] == "\\":
                        i += 1
                        if i >= len(text):
                            raise ValueError("Unterminated SGF escape")
                        if text[i] in "\r\n":
                            first = text[i]
                            i += 1
                            if i < len(text) and text[i] in "\r\n" and text[i] != first:
                                i += 1
                            continue
                    value.append(text[i])
                    i += 1
                if i >= len(text):
                    raise ValueError("Unterminated SGF property")
                values.append("".join(value))
                i += 1
            if not key or not values:
                raise ValueError("Invalid SGF property")
            yield ("property", key, values)
        else:
            raise ValueError("Invalid character outside an SGF property")


def _main_line(text):
    """Validate one complete tree, selecting only its first variation, iteratively."""
    stack, nodes = [], []
    current = None
    closed = False
    for token in _tokens(text):
        kind = token[0]
        if closed:
            raise ValueError("Expected exactly one SGF game")
        if kind == "(":
            selected = True
            if stack:
                parent = stack[-1]
                if not parent[0]:
                    raise ValueError("SGF variation precedes a node")
                selected = parent[2] and not parent[1]
                parent[1] = True
            stack.append([False, False, selected])  # has node, has variations, selected
            current = None
        elif kind == ";":
            if not stack or stack[-1][1]:
                raise ValueError("Invalid SGF node after variation")
            stack[-1][0] = True
            current = {}
            if stack[-1][2]:
                nodes.append(current)
        elif kind == ")":
            if not stack or not stack[-1][0]:
                raise ValueError("Empty or unbalanced SGF tree")
            stack.pop()
            current = None
            closed = not stack
        else:
            if current is None:
                raise ValueError("SGF property outside a node")
            _, key, values = token
            if key in current:
                raise ValueError("Duplicate SGF property")
            current[key] = values
    if stack or not closed or not nodes:
        raise ValueError("Incomplete SGF game")
    return nodes


def _single(node, key, default=None):
    values = node.get(key, [default])
    if len(values) != 1:
        raise ValueError(f"SGF {key} requires one value")
    return values[0]


def _point(raw, size, *, allow_pass=False):
    if allow_pass and raw in ("", "tt"):
        return None
    if len(raw) != 2 or any(not "a" <= c < chr(ord("a") + size) for c in raw):
        raise ValueError("Invalid SGF board coordinate")
    return (ord(raw[0]) - ord("a"), ord(raw[1]) - ord("a"))


def _setup_points(raw, size):
    parts = raw.split(":")
    if len(parts) == 1:
        return [_point(raw, size)]
    if len(parts) != 2:
        raise ValueError("Invalid SGF setup range")
    (x1, y1), (x2, y2) = (_point(part, size) for part in parts)
    if x2 < x1 or y2 < y1:
        raise ValueError("Reversed SGF setup range")
    return [(x, y) for y in range(y1, y2 + 1) for x in range(x1, x2 + 1)]


def _neighbors(point, size):
    x, y = point
    return [(a, b) for a, b in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)) if 0 <= a < size and 0 <= b < size]


def _group(board, point, size):
    stones, liberties, todo = set(), set(), [point]
    while todo:
        current = todo.pop()
        if current in stones:
            continue
        stones.add(current)
        for neighbor in _neighbors(current, size):
            if neighbor not in board:
                liberties.add(neighbor)
            elif board[neighbor] == board[point] and neighbor not in stones:
                todo.append(neighbor)
    return stones, liberties


def _validate_history(initial, moves, size, rules, initial_player):
    """Capture, suicide, turn order, simple ko and rule-specific superko.

    Multi-stone suicide follows KataGo; single-stone suicide is always illegal.
    Passes are exempt from repetition bans. The analysis engine prevents cleanup
    phases, so this validates the ordinary phase throughout the supplied history.
    """
    board = dict(initial)
    for point in board:
        if not _group(board, point, size)[1]:
            raise ValueError("Initial setup contains a group without liberties")
    ko_rule, allow_suicide = _RULES[rules]
    state = lambda: tuple(sorted(board.items()))
    previous_states = [state()]
    seen = {(state(), initial_player)} if ko_rule == "situational" else {state()}
    next_player = initial_player
    button_available = rules == "aga-button"
    for color, point in moves:
        if color != next_player:
            raise ValueError("SGF move is out of turn")
        next_player = "W" if color == "B" else "B"
        if point is not None:
            if point in board:
                raise ValueError("SGF move occupies an occupied point")
            board[point] = color
            for neighbor in _neighbors(point, size):
                if neighbor in board and board[neighbor] != color:
                    group, liberties = _group(board, neighbor, size)
                    if not liberties:
                        for captured in group:
                            del board[captured]
            group, liberties = _group(board, point, size)
            if not liberties:
                if not allow_suicide or len(group) == 1:
                    raise ValueError("Suicide in SGF history")
                for removed in group:
                    del board[removed]
            current = state()
            if len(previous_states) >= 2 and current == previous_states[-2]:
                raise ValueError("Illegal ko recapture")
            key = (current, next_player) if ko_rule == "situational" else current
            if ko_rule != "simple" and key in seen:
                raise ValueError("Illegal superko repetition")
        elif button_available:
            # Taking the AGA button clears repetition history in KataGo.
            seen.clear()
            button_available = False
        current = state()
        previous_states.append(current)
        seen.add((current, next_player) if ko_rule == "situational" else current)


def canonical_analysis_input(sgf: str, kind: str, profile: str) -> dict:
    """Return exactly the documented calculation fields, or raise ValueError.

    board_size is an int, komi a float, initial_player B/W, and initial_stones /
    moves are KataGo ``[[color, GTP], ...]`` lists. ``fingerprint`` is a SHA-256
    calculation identity, not the SHA-256 of the original/canonical SGF bytes.
    Defaults match the report worker: 19x19, Chinese rules, 7.5 komi.
    """
    if kind not in ("report", "position"):
        raise ValueError("Unknown analysis kind")
    settings = get_profile(profile)
    if not isinstance(sgf, str):
        raise ValueError("SGF must be text")
    try:
        byte_count = len(sgf.encode("utf-8"))
    except UnicodeEncodeError as exc:
        raise ValueError("Invalid UTF-8 SGF") from exc
    if byte_count > _MAX_SGF_BYTES:
        raise ValueError("SGF exceeds 256 KiB")
    nodes = _main_line(sgf.lstrip("\ufeff"))
    root = nodes[0]
    if _single(root, "GM", "1").strip() != "1":
        raise ValueError("Only Go SGF is supported")
    raw_size = _single(root, "SZ", "19").strip()
    if not re.fullmatch(r"\d+(?::\d+)?", raw_size):
        raise ValueError("Invalid SGF board size")
    dimensions = [int(part) for part in raw_size.split(":")]
    size = dimensions[0]
    if not 2 <= size <= 19 or any(part != size for part in dimensions):
        raise ValueError("Analysis requires a square board of size 2..19")
    raw_rules = _single(root, "RU", "chinese").strip().lower()
    rules = _RULE_ALIASES.get(raw_rules, raw_rules)
    if rules not in _RULES:
        raise ValueError("Unsupported SGF rules")
    try:
        komi = float(_single(root, "KM", "7.5").strip())
    except ValueError as exc:
        raise ValueError("Invalid SGF komi") from exc
    # KataGo analysis accepts finite half-integers within this user-input range.
    if not math.isfinite(komi) or not -400 <= komi <= 400 or not (komi * 2).is_integer():
        raise ValueError("Invalid SGF komi")
    komi = komi or 0.0  # canonicalize negative zero
    raw_handicap = _single(root, "HA", "0").strip()
    if not re.fullmatch(r"\d+", raw_handicap):
        raise ValueError("Invalid SGF handicap")
    handicap = int(raw_handicap)
    initial, moves, explicit_player = {}, [], None
    for index, node in enumerate(nodes):
        if index and any(key in node for key in ("GM", "FF", "SZ", "RU", "KM", "HA")):
            raise ValueError("Root game properties cannot change in the main line")
        has_move = "B" in node or "W" in node
        setup_keys = [key for key in ("AB", "AW", "AE", "PL") if key in node]
        if setup_keys and (moves or has_move):
            raise ValueError("Setup / PL with a move or after the first move is unsupported")
        touched = set()
        for prop, color in (("AB", "B"), ("AW", "W"), ("AE", None)):
            for raw in node.get(prop, []):
                for point in _setup_points(raw, size):
                    if point in touched or (color is not None and point in initial):
                        raise ValueError("Duplicate or conflicting initial setup")
                    touched.add(point)
                    if color is None:
                        initial.pop(point, None)
                    else:
                        initial[point] = color
        if "PL" in node:
            player = _single(node, "PL").strip().upper()
            if player not in ("B", "W") or (explicit_player is not None and player != explicit_player):
                raise ValueError("Invalid or conflicting initial player")
            explicit_player = player
        if has_move:
            if "B" in node and "W" in node:
                raise ValueError("An SGF node must have only one move")
            color = "B" if "B" in node else "W"
            moves.append((color, _point(_single(node, color), size, allow_pass=True)))
            if len(moves) > MAX_REPORT_MOVES:
                raise ValueError("Analysis supports at most 500 moves")
    if handicap and (handicap < 2 or handicap != len(initial) or any(c != "B" for c in initial.values())):
        raise ValueError("Handicap requires matching explicit black setup stones")
    if kind == "report" and not moves:
        raise ValueError("Report requires at least one move")
    initial_player = explicit_player or (
        moves[0][0] if moves else ("W" if initial and set(initial.values()) == {"B"} else "B")
    )
    _validate_history(initial, moves, size, rules, initial_player)

    def sgf_point(point):
        return "" if point is None else chr(ord("a") + point[0]) + chr(ord("a") + point[1])

    def gtp(point):
        return "pass" if point is None else _GTP_COLUMNS[point[0]] + str(size - point[1])

    ordered_setup = sorted(initial, key=lambda point: (point[1], point[0]))
    canonical = f"(;GM[1]FF[4]CA[UTF-8]SZ[{size}]RU[{rules}]KM[{komi:g}]PL[{initial_player}]"
    for color in "BW":
        points = [point for point in ordered_setup if initial[point] == color]
        if points:
            canonical += "A" + color + "".join(f"[{sgf_point(point)}]" for point in points)
    canonical += "".join(f";{color}[{sgf_point(point)}]" for color, point in moves) + ")"
    scope = {
        "schema": 1,
        "catalog": CATALOG_VERSION,
        "kind": kind,
        "profile": profile,
        "model_sha256": settings["model_sha256"],
        "visits": settings["visits"],
        "sgf": canonical,
    }
    fingerprint = hashlib.sha256(json.dumps(scope, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    return {
        "fingerprint": fingerprint,
        "canonical_sgf": canonical,
        "move_count": len(moves),
        "board_size": size,
        "rules": rules,
        "komi": komi,
        "initial_player": initial_player,
        "initial_stones": [[color, gtp(point)] for color in "BW" for point in ordered_setup if initial[point] == color],
        "moves": [[color, gtp(point)] for color, point in moves],
    }
