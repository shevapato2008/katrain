"""Tests for the backend-authoritative 摆谱 per-step truth builder (decision ②).

These are pure-logic tests (no hardware, no HTTP, no DB) — they exercise the SGF
replay → canonical (row=0 top, col=0 left) coordinate normalization, capture
detection, handicap/setup (AB/AW) handling, pass handling, and board_hash.

The LED (row,col)->chain-index round-trip lives in tests/test_led_service.py (P2),
where the canonical convention meets the LUT.
"""

import os

import pytest

from katrain.core.baipu import build_steps_from_sgf, expected_board_from_steps, next_placement_index

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
        data = _steps("(;SZ[19]PB[Lee]PW[AlphaGo]KM[7.5]RE[W+R];B[pd])")
        assert data["meta"]["player_black"] == "Lee"
        assert data["meta"]["player_white"] == "AlphaGo"
        assert data["meta"]["komi"] == 7.5
        assert data["meta"]["result"] == "W+R"

    def test_rank_metadata_preserves_sgf_labels_without_name_lookup(self):
        meta = _steps("(;SZ[19]PB[Lee]PW[AlphaGo]BR[9p]WR[职业九段];B[pd])")["meta"]
        assert meta["player_black_rank"] == "9p"
        assert meta["player_white_rank"] == "职业九段"
        missing = _steps("(;SZ[19]PB[Lee]PW[AlphaGo];B[pd])")["meta"]
        assert missing["player_black_rank"] is None
        assert missing["player_white_rank"] is None


class TestExpectedBoardAndNext:
    def test_expected_board_applies_and_captures(self):
        # W[aa] then B[ba],B[ab] captures the corner W stone.
        steps = _steps("(;SZ[19];W[aa];B[ba];B[ab])")["steps"]
        # empty board at k=-1
        assert all(cell is None for row in expected_board_from_steps(steps, -1) for cell in row)
        # after the W stone is placed (k=0)
        b0 = expected_board_from_steps(steps, 0)
        assert b0[0][0] == "W"
        # after the capture (k=2) the corner is empty again, B stones present
        b2 = expected_board_from_steps(steps, 2)
        assert b2[0][0] is None
        assert b2[0][1] == "B" and b2[1][0] == "B"

    def test_next_placement_skips_pass(self):
        steps = _steps("(;SZ[19];B[pd];W[];B[pp])")["steps"]
        # steps: [0]=move, [1]=pass, [2]=move
        assert next_placement_index(steps, -1) == 0
        assert next_placement_index(steps, 0) == 2  # skips the pass at index 1
        assert next_placement_index(steps, 2) is None

    def test_out_of_range_k_is_clamped(self):
        steps = _steps("(;SZ[19];B[pd])")["steps"]
        # k beyond the last step must not raise (defensive clamp)
        b = expected_board_from_steps(steps, 99)
        assert b[3][15] == "B"

    def test_ae_clear_emitted_and_applied(self):
        # AB places a stone, AE removes it, then a move. The clear must be recorded
        # so expected_board reflects the removal (decision ②, review fix).
        data = _steps("(;SZ[19]AB[aa];AE[aa];B[pd])")
        steps = data["steps"]
        kinds = [s["kind"] for s in steps]
        assert "clear" in kinds
        clear_step = next(s for s in steps if s["kind"] == "clear")
        assert {"row": 0, "col": 0} in clear_step["removed"]
        # final board: aa cleared, pd present
        board = expected_board_from_steps(steps, len(steps) - 1)
        assert board[0][0] is None
        assert board[3][15] == "B"
        # next_placement_index skips the clear step
        clear_idx = kinds.index("clear")
        assert next_placement_index(steps, clear_idx - 1) != clear_idx


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


class TestFF4RecordReplay:
    def test_replacement_and_repeat_preserve_dense_operations(self):
        data = _steps("(;SZ[19];B[aa];W[aa];W[aa])")
        assert data["replay_version"] == 2
        first, replacement, repeat = data["steps"]
        assert first["pre_removed"] == [] and first["requires_placement"] is True
        assert replacement["pre_removed"] == [{"row": 0, "col": 0}]
        assert replacement["removed"] == [] and replacement["requires_placement"] is True
        assert repeat["pre_removed"] == [] and repeat["requires_placement"] is False
        assert [s["move_index"] for s in data["steps"]] == [0, 1, 2]
        assert expected_board_from_steps(data["steps"], 2)[0][0] == "W"
        assert repeat["board_hash"] == replacement["board_hash"]

    @pytest.mark.parametrize(
        "sgf,removed",
        [
            ("(;SZ[9]AW[ba][ab];B[aa])", {(0, 0)}),
            ("(;SZ[9]AB[aa]AW[ba][bb][ac];B[ab])", {(0, 0), (1, 0)}),
        ],
    )
    def test_own_zero_liberty_group_removed_after_placement(self, sgf, removed):
        data = _steps(sgf)
        last = data["steps"][-1]
        assert last["requires_placement"] is True
        assert {(p["row"], p["col"]) for p in last["removed"]} == removed
        board = expected_board_from_steps(data["steps"], len(data["steps"]) - 1, 9)
        assert all(board[r][c] is None for r, c in removed)

    def test_opponents_removed_before_own_liberty_check(self):
        data = _steps("(;SZ[9]AB[ca][bb]AW[ba][ab];B[aa])")
        last = data["steps"][-1]
        assert last["removed"] == [{"row": 0, "col": 1}]
        assert expected_board_from_steps(data["steps"], len(data["steps"]) - 1, 9)[0][0] == "B"

    def test_setup_assignment_does_not_capture_or_remove_own_group(self):
        data = _steps("(;SZ[9]AB[aa]AW[ba][ab];AB[ba][ba];AE[ba][ii])")
        steps = data["steps"]
        assert all(s["removed"] == [] for s in steps if s["kind"] == "setup")
        assert expected_board_from_steps(steps, 2, 9)[0][0] == "B"
        assert steps[3]["pre_removed"] == [{"row": 0, "col": 1}]
        assert steps[4]["requires_placement"] is False
        assert steps[5]["kind"] == "clear" and steps[5]["requires_placement"] is False
        assert steps[5]["removed"] == [{"row": 0, "col": 1}]
        assert expected_board_from_steps(steps, 5, 9)[0][0] == "B"

    def test_compressed_setup_preserves_raw_order_and_repeats(self):
        data = _steps("(;SZ[9]AB[cc][aa:bb][cc])")
        assert [(s["row"], s["col"]) for s in data["steps"]] == [
            (2, 2),
            (0, 0),
            (1, 0),
            (0, 1),
            (1, 1),
            (2, 2),
        ]
        assert data["steps"][-1]["requires_placement"] is False

    @pytest.mark.parametrize(
        "props",
        [
            "B[sa]",
            "B[as]",
            "B[a]",
            "B[aaa]",
            "AB[tt]",
            "AE[]",
            "AB[aa:zz]",
            "AB[bb:aa]",
            "AB[aa]AW[aa]",
            "AB[aa:bb]AW[bb]",
        ],
    )
    def test_bad_coordinates_and_conflicting_setup_are_parse_errors(self, props):
        with pytest.raises(ValueError, match="coordinate|setup"):
            _steps(f"(;SZ[9];{props})")

    def test_ko_record_retake_is_viewable_without_weakening_game_rules(self):
        data = _steps("(;SZ[9]AB[ba][ab][bc]AW[ca][bb][cc][db];B[cb];W[bb])")
        assert data["steps"][-1]["removed"] == [{"row": 1, "col": 2}]
        assert data["steps"][-2]["removed"] == [{"row": 1, "col": 1}]

    def test_pass_has_recorded_player_and_no_physical_action(self):
        step = _steps("(;SZ[9];W[])")["steps"][0]
        assert step["property"] == "W" and step["color"] is None
        assert step["requires_placement"] is False and step["pre_removed"] == []

    def test_expected_board_applies_pre_removal_before_assignment(self):
        steps = [
            {"kind": "move", "row": 0, "col": 0, "color": "W", "pre_removed": [{"row": 0, "col": 0}], "removed": []}
        ]
        assert expected_board_from_steps(steps, 0)[0][0] == "W"

    def test_ordinary_hash_stays_compatible(self):
        import hashlib

        assert (
            _steps("(;SZ[19];B[pd])")["steps"][0]["board_hash"]
            == hashlib.sha1(repr([(15, 15, "B")]).encode()).hexdigest()[:16]
        )


@pytest.mark.parametrize("game_id", [140859, 124442, 118394])
def test_real_ff4_every_dense_state_matches_independent_oracle(game_id):
    import hashlib
    import json
    from pathlib import Path

    golden = json.loads((Path(DATA_DIR) / "baipu_ff4_golden.json").read_text())
    game = next(g for g in golden["games"] if g["id"] == game_id)
    text = (Path(__file__).parents[1] / f"katrain/web/ui/src/utils/__fixtures__/kifu-{game_id}.sgf").read_text()
    assert hashlib.sha256(text.encode()).hexdigest() == game["sgf_sha256"]
    data = _steps(text)
    assert len(data["steps"]) == game["steps"]
    columns = "ABCDEFGHJKLMNOPQRST"
    for k, reference in enumerate(game["hashes"]):
        board = expected_board_from_steps(data["steps"], k - 1)
        stones = sorted(
            f"{color}:{columns[c]}{19-r}" for r, row in enumerate(board) for c, color in enumerate(row) if color
        )
        assert hashlib.sha256("\n".join(stones).encode()).hexdigest() == reference, f"{game_id} step {k - 1}"
    assert len(stones) == {140859: 232, 124442: 259, 118394: 202}[game_id]
