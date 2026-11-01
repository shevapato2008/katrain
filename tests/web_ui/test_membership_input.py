"""Paid analysis accepts one bounded, legal SGF main line without dropping moves."""

import hashlib

import pytest


def canonical(sgf, kind="report", profile="normal"):
    from katrain.web.core.billing_input import canonical_analysis_input

    return canonical_analysis_input(sgf, kind, profile)


def test_canonical_input_contains_complete_main_line_and_engine_fields():
    result = canonical("(;SZ[9]RU[Japanese]KM[6.5]PL[B];B[aa]C[;W[cc\\] text](;W[bb];B[])(;W[cc]))")
    assert set(result) == {
        "fingerprint",
        "canonical_sgf",
        "move_count",
        "board_size",
        "rules",
        "komi",
        "initial_player",
        "initial_stones",
        "moves",
    }
    assert result["move_count"] == 3
    assert result["board_size"] == 9
    assert result["rules"] == "japanese"
    assert result["komi"] == 6.5
    assert result["initial_player"] == "B"
    assert result["initial_stones"] == []
    assert result["moves"] == [["B", "A9"], ["W", "B8"], ["B", "pass"]]
    assert len(result["fingerprint"]) == 64
    assert canonical(result["canonical_sgf"]) == result


def test_comments_names_and_non_main_line_variations_do_not_change_compute_identity():
    plain = canonical("(;SZ[9];B[aa];W[bb])")
    annotated = canonical("(;PB[名字]PW[Name]SZ[9]C[comment];B[aa](;W[bb]C[text])(;W[cc];B[dd]))")
    assert plain == annotated


@pytest.mark.parametrize(
    "other,kind,profile",
    [
        ("(;SZ[9]KM[6.5];B[aa])", "report", "normal"),
        ("(;SZ[9]RU[japanese];B[aa])", "report", "normal"),
        ("(;SZ[9];W[aa])", "report", "normal"),
        ("(;SZ[9];B[aa];W[];B[])", "report", "normal"),
        ("(;SZ[9];B[aa])", "position", "normal"),
        ("(;SZ[9];B[aa])", "report", "advanced"),
    ],
)
def test_owned_results_are_bound_to_complete_compute_scope(other, kind, profile):
    assert canonical(other, kind, profile)["fingerprint"] != canonical("(;SZ[9];B[aa])")["fingerprint"]


def test_initial_compressed_setup_and_clear_are_frozen_for_the_cron_reader():
    from katrain.cron.sgf import parse_game

    result = canonical("(;SZ[9]AB[aa:bb]AW[cc];AE[bb]PL[W];W[dd])")
    assert result["initial_stones"] == [["B", "A9"], ["B", "B9"], ["B", "A8"], ["W", "C7"]]
    assert result["initial_player"] == "W"
    parsed = parse_game(result["canonical_sgf"])
    assert parsed.initial_stones == result["initial_stones"]
    assert parsed.initial_player == result["initial_player"]
    assert [list(move) for move in parsed.moves] == result["moves"]
    assert parsed.rules == result["rules"]
    assert parsed.komi == result["komi"]
    assert parsed.board_size == result["board_size"]
    assert hashlib.sha256(result["canonical_sgf"].encode()).hexdigest() != result["fingerprint"]


def test_zero_move_position_and_root_move_are_supported():
    assert canonical("(;SZ[9]AB[aa][cc])", "position")["initial_player"] == "W"
    assert canonical("(;SZ[2])", "position")["move_count"] == 0
    assert canonical("(;SZ[9]B[aa])")["move_count"] == 1
    with pytest.raises(ValueError):
        canonical("(;SZ[9]AB[aa])")


def test_move_limit_is_checked_without_truncating_legal_moves():
    moves = "".join(";" + "BW"[i % 2] + "[]" for i in range(500))
    assert canonical("(;SZ[9]" + moves + ")")["move_count"] == 500
    with pytest.raises(ValueError):
        canonical("(;SZ[9]" + moves + ";B[])")


def test_utf8_limit_is_bytes_and_includes_ignored_metadata():
    base = "(;C[];B[aa])"
    exact = "(;C[" + "x" * (256 * 1024 - len(base)) + "];B[aa])"
    assert len(exact.encode()) == 256 * 1024
    assert canonical(exact)["move_count"] == 1
    with pytest.raises(ValueError):
        canonical(exact.replace("C[x", "C[中", 1))


@pytest.mark.parametrize(
    "sgf",
    [
        "",
        "garbage(;B[aa])",
        "(;B[aa])tail",
        "(;B[aa])(;B[bb])",
        "(;B[aa]",
        "(;B[aa]))",
        "()",
        "(B[aa])",
        "(;B[aa]C[unclosed)",
        "(;B[aa] garbage)",
        "(;B[aa](;W[bb]);W[cc])",
        "(;GM[2];B[aa])",
        "(;SZ[1];B[aa])",
        "(;SZ[20];B[aa])",
        "(;SZ[9:13];B[aa])",
        "(;SZ[9oops];B[aa])",
        "(;SZ[9][13];B[aa])",
        "(;KM[NaN];B[aa])",
        "(;KM[inf];B[aa])",
        "(;KM[bad];B[aa])",
        "(;KM[6.25];B[aa])",
        "(;KM[401];B[aa])",
        "(;RU[unknown];B[aa])",
        '(;RU[{"ko":"SIMPLE"}];B[aa])',
        "(;PL[X];B[aa])",
        "(;PL[W];B[aa])",
        "(;SZ[9];B[zz])",
        "(;SZ[9];B[a])",
        "(;SZ[9];B[aaa])",
        "(;SZ[9];B[AA])",
        "(;SZ[9];B[aa][bb])",
        "(;SZ[9];B[aa]W[bb])",
        "(;SZ[9];B[aa]B[bb])",
        "(;SZ[9];B[aa];B[bb])",
        "(;SZ[9];B[aa];W[aa])",
        "(;SZ[9];B[aa];AW[bb])",
        "(;SZ[9];B[aa];PL[B];W[bb])",
        "(;SZ[9];B[aa];KM[1];W[bb])",
        "(;SZ[9]AB[aa][aa];B[bb])",
        "(;SZ[9]AB[aa]AW[aa];B[bb])",
        "(;SZ[9]AB[aa]AE[aa];B[bb])",
        "(;SZ[9]AB[aa:zz];B[bb])",
        "(;SZ[9]AB[];B[bb])",
        "(;SZ[9]AB[aa]B[bb])",
        "(;SZ[9]HA[2];B[aa])",
        "(;SZ[2]AB[aa][bb]AW[ab][ba];B[])",
    ],
)
def test_malformed_unrepresentable_or_illegal_history_is_rejected(sgf):
    with pytest.raises(ValueError):
        canonical(sgf)


def test_capture_is_legal_and_suicide_is_rejected():
    assert canonical("(;SZ[3];B[ab];W[aa];B[ba];W[cc])")["move_count"] == 4
    with pytest.raises(ValueError, match="[Ss]uicide"):
        canonical("(;SZ[3]AB[ab][ba]PL[W];W[aa])")


@pytest.mark.parametrize("rules", ["japanese", "chinese", "aga", "new zealand", "tromp-taylor"])
def test_immediate_ko_recapture_is_rejected_for_supported_rules(rules):
    # Black C2 takes white C3; C3 immediately taking C2 recreates the initial board.
    sgf = "(;SZ[5]RU[" + rules + "]AB[bc][dc][cd]AW[cc][bb][db][ca]PL[B];B[cb];W[cc])"
    with pytest.raises(ValueError, match="[Kk]o|repetition"):
        canonical(sgf)


@pytest.mark.parametrize(
    "rules,legal", [("japanese", True), ("chinese", True), ("aga", False), ("tromp-taylor", False)]
)
def test_ko_recapture_after_passes_obeys_rule_specific_repetition(rules, legal):
    sgf = "(;SZ[5]RU[" + rules + "]AB[bc][dc][cd]AW[cc][bb][db][ca]PL[B];B[cb];W[];B[];W[cc])"
    if legal:
        assert canonical(sgf)["move_count"] == 4
    else:
        with pytest.raises(ValueError, match="repetition"):
            canonical(sgf)


def test_multi_stone_suicide_is_only_allowed_by_suicide_rules():
    # B A3 joins B A2; both have no liberties and remove themselves under NZ.
    setup = "SZ[3]AB[ab]AW[ba][bb][ac]PL[B]"
    assert canonical("(;" + setup + "RU[new zealand];B[aa])")["move_count"] == 1
    with pytest.raises(ValueError, match="[Ss]uicide"):
        canonical("(;" + setup + "RU[japanese];B[aa])")
    with pytest.raises(ValueError, match="[Ss]uicide"):
        canonical("(;SZ[3]RU[new zealand]AB[ab][ba]PL[W];W[aa])")


@pytest.mark.parametrize("kind,profile", [("bad", "normal"), ("report", "deep"), (None, "normal")])
def test_unknown_scope_is_rejected(kind, profile):
    with pytest.raises(ValueError):
        canonical("(;B[aa])", kind, profile)
