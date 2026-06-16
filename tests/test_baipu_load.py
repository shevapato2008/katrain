"""Tests for the backend-authoritative 摆谱 per-step truth builder (decision ②).

These are pure-logic tests (no hardware, no HTTP, no DB) — they exercise the SGF
replay → canonical (row=0 top, col=0 left) coordinate normalization, capture
detection, handicap/setup (AB/AW) handling, pass handling, and board_hash.

The LED (row,col)->chain-index round-trip lives in tests/test_led_service.py (P2),
where the canonical convention meets the LUT.
"""

import os

import pytest

from katrain.core.baipu import build_steps_from_sgf

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")


def _steps(sgf):
    return build_steps_from_sgf(sgf)


class TestCoordinateNormalization:
    def test_four_corners_canonical(self):
        # row=0 TOP, col=0 LEFT. SGF letter index for the row == canonical row.
        data = _steps("(;GM[1]FF[4]SZ[19];B[pd];W[dp];B[pp];W[dd])")
        assert data["board_size"] == 19
        steps = data["steps"]
        assert len(steps) == 4
        # B[pd] -> Q16, upper-right: row 3 from top, col 15 from left
        assert (steps[0]["kind"], steps[0]["color"], steps[0]["row"], steps[0]["col"]) == ("move", "B", 3, 15)
        # W[dp] -> D4, lower-left
        assert (steps[1]["color"], steps[1]["row"], steps[1]["col"]) == ("W", 15, 3)
        # B[pp] -> Q4, lower-right
        assert (steps[2]["row"], steps[2]["col"]) == (15, 15)
        # W[dd] -> D16, upper-left
        assert (steps[3]["row"], steps[3]["col"]) == (3, 3)
        for k, s in enumerate(steps):
            assert s["move_index"] == k
            assert s["property"] in ("B", "W")
            assert s["removed"] == []
            assert s["board_hash"]

    def test_top_left_origin(self):
        # SGF 'aa' is the top-left corner -> canonical (0, 0)
        data = _steps("(;SZ[19];B[aa])")
        assert (data["steps"][0]["row"], data["steps"][0]["col"]) == (0, 0)

    def test_bottom_right_origin(self):
        # SGF 'ss' on 19x19 is the bottom-right corner -> canonical (18, 18)
        data = _steps("(;SZ[19];B[ss])")
        assert (data["steps"][0]["row"], data["steps"][0]["col"]) == (18, 18)

    def test_nonsquare_and_small_boards(self):
        # 9x9: 'cc' -> internal (2,6) -> canonical (2,2)
        d9 = _steps("(;SZ[9];B[cc])")
        assert d9["board_size"] == 9
        assert (d9["steps"][0]["row"], d9["steps"][0]["col"]) == (2, 2)
        # 13x13 top-left corner stays (0,0)
        d13 = _steps("(;SZ[13];B[aa])")
        assert (d13["steps"][0]["row"], d13["steps"][0]["col"]) == (0, 0)


class TestCaptures:
    def test_corner_capture_removed_list(self):
        # W in the top-left corner (aa), surrounded by B at ba and ab -> captured.
        data = _steps("(;SZ[19];W[aa];B[ba];B[ab])")
        steps = data["steps"]
        assert steps[0]["removed"] == []
        assert steps[1]["removed"] == []
        # The capturing move reports the removed stone in canonical coords.
        assert steps[2]["kind"] == "move"
        assert steps[2]["removed"] == [{"row": 0, "col": 0}]

    def test_board_hash_changes_when_stone_captured(self):
        data = _steps("(;SZ[19];W[aa];B[ba];B[ab])")
        # board after capture must differ from board right before it
        assert data["steps"][1]["board_hash"] != data["steps"][2]["board_hash"]


class TestHandicapAndSetup:
    def test_ab_setup_then_move(self):
        # decision ② regression: handicap/setup (AB/AW) must be emitted as setup steps,
        # never treated as captures or illegal moves.
        data = _steps("(;SZ[19]HA[2]AB[pd][dp];W[dd])")
        steps = data["steps"]
        assert data["meta"]["handicap"] == 2
        setup = [s for s in steps if s["kind"] == "setup"]
        moves = [s for s in steps if s["kind"] == "move"]
        assert len(setup) == 2
        assert all(s["property"] == "AB" and s["color"] == "B" for s in setup)
        assert {(s["row"], s["col"]) for s in setup} == {(3, 15), (15, 3)}
        assert len(moves) == 1 and (moves[0]["row"], moves[0]["col"]) == (3, 3)

    def test_aw_setup(self):
        data = _steps("(;SZ[19]AW[dd];B[pd])")
        setup = [s for s in data["steps"] if s["kind"] == "setup"]
        assert len(setup) == 1
        assert setup[0]["property"] == "AW" and setup[0]["color"] == "W"


class TestPass:
    def test_pass_step(self):
        data = _steps("(;SZ[19];B[pd];W[];B[pp])")
        steps = data["steps"]
        assert steps[1]["kind"] == "pass"
        assert steps[1]["row"] is None and steps[1]["col"] is None and steps[1]["color"] is None
        # passes still occupy a step index; surrounding moves are unaffected
        assert steps[0]["kind"] == "move" and steps[2]["kind"] == "move"


class TestDeterminism:
    def test_same_sgf_same_hashes(self):
        sgf = "(;SZ[19];B[pd];W[dp];B[pp];W[dd])"
        a = _steps(sgf)
        b = _steps(sgf)
        assert [s["board_hash"] for s in a["steps"]] == [s["board_hash"] for s in b["steps"]]

    def test_meta_fields(self):
        data = _steps("(;SZ[19]PB[Lee]PW[AlphaGo]KM[7.5];B[pd])")
        assert data["meta"]["player_black"] == "Lee"
        assert data["meta"]["player_white"] == "AlphaGo"
        assert data["meta"]["komi"] == 7.5


class TestRealGame:
    @pytest.mark.parametrize("name", ["ogs.sgf", "LS vs AG - G4 - English.sgf"])
    def test_full_game_replays_cleanly(self, name):
        path = os.path.join(DATA_DIR, name)
        if not os.path.exists(path):
            pytest.skip(f"missing fixture {name}")
        with open(path, "rb") as fh:
            import chardet

            raw = fh.read()
            text = raw.decode(chardet.detect(raw)["encoding"] or "utf-8", errors="replace")
        data = build_steps_from_sgf(text)
        bs = data["board_size"]
        steps = data["steps"]
        assert len(steps) > 50  # a real game has plenty of moves
        for s in steps:
            if s["kind"] != "pass":
                assert 0 <= s["row"] < bs and 0 <= s["col"] < bs
            for rm in s["removed"]:
                assert 0 <= rm["row"] < bs and 0 <= rm["col"] < bs
        # move_index is a dense 0..N-1 sequence
        assert [s["move_index"] for s in steps] == list(range(len(steps)))
        # at least one capture occurs in a full game
        assert any(s["removed"] for s in steps)
