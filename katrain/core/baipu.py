"""Backend-authoritative 摆谱 per-step truth (decision ②) — pure core logic.

Given an SGF, replay the whole game with the existing KaTrain engine
(`game.py` + `sgf_parser.py`, which already compute captures and expand
AB/AW/AE) and emit, for every placement / move / pass, a step in **canonical
coordinates** (`row=0 top, col=0 left` — the LED LUT convention in
`superpowers/tracks/sbc-baipu-led-guide/plan.md` Appendix A).

The frontend is a dumb player of `steps[]`; it never recomputes captures.
This closes the 让子 (AB/AW) hole and removes any TS capture-logic edge cases.

No FastAPI / DB / hardware imports here so this stays unit-testable in CI.
"""

import hashlib
from typing import Any, Dict, List

from katrain.core.game import BaseGame, KaTrainSGF


class _StubKaTrain:
    """Minimal stand-in for the KaTrain app object.

    ``BaseGame.__init__`` only reaches for ``katrain.config(...)`` to fill a
    missing ``RU`` (ruleset); everything else (board size, rules, capture
    logic) is derived from the parsed SGF root. We also set RU defensively
    before construction, so this stub is belt-and-suspenders.
    """

    def config(self, key: str, default: Any = None) -> Any:
        if key == "game/rules":
            return "japanese"
        return default

    def log(self, *args: Any, **kwargs: Any) -> None:  # pragma: no cover
        pass


def _canon_point(move, board_y: int) -> Dict[str, int]:
    """Internal (x=col, y=row, y=0 bottom) -> canonical {row (0 top), col}."""
    x, y = move.coords
    return {"row": board_y - 1 - y, "col": x}


def _board_hash(chains) -> str:
    """Order-independent hash of the stones currently on the board."""
    stones = sorted((m.coords[0], m.coords[1], m.player) for chain in chains for m in chain)
    return hashlib.sha1(repr(stones).encode("utf-8")).hexdigest()[:16]


def build_steps_from_sgf(sgf: str) -> Dict[str, Any]:
    """Replay an SGF and return per-step canonical truth.

    Returns ``{"board_size": int, "steps": [...], "meta": {...}}`` where each
    step is ``{kind, move_index, property, row, col, color, removed, board_hash}``:

    * ``kind`` — ``setup`` (AB/AW), ``move`` (B/W) or ``pass``
    * ``move_index`` — 0-based index into ``steps``
    * ``property`` — SGF property class: ``AB``/``AW``/``B``/``W``
    * ``row``/``col`` — canonical (``row=0`` top, ``col=0`` left); ``None`` for pass
    * ``color`` — ``B``/``W``; ``None`` for pass
    * ``removed`` — stones captured by this step, canonical ``[{row, col}, ...]``
    * ``board_hash`` — deterministic hash of the board after this step
    """
    root = KaTrainSGF.parse_sgf(sgf)
    if not root.get_property("RU"):
        root.set_property("RU", "japanese")

    game = BaseGame(_StubKaTrain(), move_tree=root, bypass_config=True)
    board_x, board_y = game.board_size  # (width, height)

    # Walk to the main-line leaf; nodes_from_root then yields root..leaf in order.
    leaf = root
    while leaf.children:
        leaf = leaf.children[0]

    # Fresh single-pass replay with a snapshot after every individual stone,
    # mirroring BaseGame._calculate_groups but capturing per-node state.
    game.current_node = leaf
    game._init_state()
    steps: List[Dict[str, Any]] = []

    for node in leaf.nodes_from_root:
        placements = node.placements  # AB/AW (already expanded for ranges)
        moves = node.moves  # B/W (pass moves have coords=None)
        n_setup = len(placements)
        for i, m in enumerate(placements + moves):
            game._validate_move_and_update_chains(m, True)  # ignore ko — SGF is trusted
            removed = [_canon_point(rm, board_y) for rm in game.last_capture]
            if m.is_pass:
                step = {
                    "kind": "pass",
                    "move_index": len(steps),
                    "property": m.player,
                    "row": None,
                    "col": None,
                    "color": None,
                    "removed": removed,
                    "board_hash": _board_hash(game.chains),
                }
            else:
                is_setup = i < n_setup
                point = _canon_point(m, board_y)
                step = {
                    "kind": "setup" if is_setup else "move",
                    "move_index": len(steps),
                    "property": ("AB" if m.player == "B" else "AW") if is_setup else m.player,
                    "row": point["row"],
                    "col": point["col"],
                    "color": m.player,
                    "removed": removed,
                    "board_hash": _board_hash(game.chains),
                }
            steps.append(step)

        if node.clear_placements:
            # AE (rare in game records): replay survivors from empty so later
            # board_hashes stay correct. No guided step is emitted for AE.
            clear_coords = {c.coords for c in node.clear_placements}
            survivors = [m for chain in game.chains for m in chain if m.coords not in clear_coords]
            game._init_state()
            for m in survivors:
                game._validate_move_and_update_chains(m, True)

    try:
        komi = float(root.komi)
    except (TypeError, ValueError):
        komi = 0.0
    meta = {
        "player_black": root.get_property("PB", "") or "",
        "player_white": root.get_property("PW", "") or "",
        "handicap": int(root.handicap or 0),
        "komi": komi,
        "ruleset": root.ruleset,
    }
    return {"board_size": board_x, "steps": steps, "meta": meta}


def expected_board_from_steps(steps: List[Dict[str, Any]], k: int, board_size: int = 19):
    """Canonical 19x19 board (``'B'``/``'W'``/``None``) after applying ``steps[0..k]``.

    ``k == -1`` yields the empty board. Used by L2 QA (decision ③) to know what the
    physical board *should* look like after the operator has placed move ``k``.
    """
    board = [[None] * board_size for _ in range(board_size)]
    for i in range(0, k + 1):
        s = steps[i]
        if s["kind"] in ("setup", "move") and s["row"] is not None:
            board[s["row"]][s["col"]] = s["color"]
        for rm in s.get("removed", []):
            board[rm["row"]][rm["col"]] = None
    return board


def next_placement_index(steps: List[Dict[str, Any]], after: int):
    """First index ``j > after`` that is a physical placement (``kind != 'pass'``).

    Returns ``None`` if there is no further stone to guide (the capture becomes a
    final, no-LED frame). Passes are skipped because they need no physical action.
    """
    for j in range(after + 1, len(steps)):
        if steps[j]["kind"] != "pass":
            return j
    return None
