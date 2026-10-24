"""The frozen examples use actual API-shaped source data, never a source database."""

import copy
import json
from pathlib import Path

import pytest

SOURCES = json.loads((Path(__file__).parent / "data/kiosk19_sources.json").read_text())


def tsumego(source_id):
    return copy.deepcopy(next(p for p in SOURCES["tsumego"] if p["id"] == source_id))


def ogs(page):
    return copy.deepcopy(next(p for p in SOURCES["ogs"] if p["page"] == page))


@pytest.mark.parametrize(
    "source_id,offset,expected",
    [
        ("92643", [5, 5], "B[li]"),
        ("218387", [0, 12], "B[cq]"),
        ("124386", [10, 5], "B[sj]"),
        ("129993", [5, 5], "B[ji]"),
    ],
)
def test_actual_local_targets_keep_all_branches_and_source(source_id, offset, expected):
    from katrain.web.content.board_variants import adapt_tsumego_detail
    from katrain.core.sgf_parser import SGF

    source = tsumego(source_id)
    before = copy.deepcopy(source)
    result = adapt_tsumego_detail(source)
    assert source == before
    assert result["id"] == source_id
    assert result["board_variant"]["status"] == "adapted", result["board_variant"]
    assert result["boardSize"] == 19
    assert result["board_variant"]["offset"] == offset
    assert expected in result["sgfContent"]
    a, b = SGF.parse_sgf(source["sgfContent"]), SGF.parse_sgf(result["sgfContent"])
    assert len(a.nodes_in_tree) == len(b.nodes_in_tree)
    assert [(n.get_property("C"), len(n.children)) for n in a.nodes_in_tree] == [
        (n.get_property("C"), len(n.children)) for n in b.nodes_in_tree
    ]
    assert b.get_list_property("AB") == result["initialBlack"]
    assert b.get_list_property("AW", []) == result["initialWhite"]


@pytest.mark.parametrize("source_id", ["108018", "122131", "123086", "213404"])
def test_opposite_edges_and_global_scores_stay_original(source_id):
    from katrain.web.content.board_variants import adapt_tsumego_detail

    source = tsumego(source_id)
    result = adapt_tsumego_detail(source)
    assert result.pop("board_variant")["status"] == "unavailable"
    assert result == source


def test_native19_is_business_identical_and_unknown_source_is_honest():
    from katrain.web.content.board_variants import adapt_tsumego_detail, adapt_ogs_step

    for adapt, source, field in [
        (adapt_tsumego_detail, tsumego("92643"), "boardSize"),
        (adapt_ogs_step, ogs(73), "size"),
    ]:
        source[field] = 19
        result = adapt(source)
        assert result.pop("board_variant")["status"] == "original"
        assert result == source
    source = tsumego("92643")
    source["id"] = "unknown"
    assert adapt_tsumego_detail(source)["board_variant"]["status"] == "unavailable"


@pytest.mark.parametrize("field,value", [("hint", "白先"), ("category", "endgame"), ("sgfContent", "(;SZ[8])")])
def test_changed_source_never_uses_stale_certificate(field, value):
    from katrain.web.content.board_variants import adapt_tsumego_detail

    source = tsumego("92643")
    source[field] = value
    assert adapt_tsumego_detail(source)["board_variant"]["status"] == "unavailable"


@pytest.mark.parametrize("replacement", ["B[]", "B[aa:bb]", "B[zz]", "AE[aa]", "LB[aa:A]"])
def test_unsupported_sgf_coordinates_cannot_silently_disappear(replacement):
    from katrain.web.content.board_variants import adapt_tsumego_detail

    source = tsumego("92643")
    source["sgfContent"] = source["sgfContent"].replace("B[gd]", replacement)
    result = adapt_tsumego_detail(source)
    assert result["board_variant"]["status"] == "unavailable"
    assert result["sgfContent"] == source["sgfContent"]
    assert result["board_variant"]["reason"]


def test_ogs_corner_capture_and_marks_have_one_authority():
    from katrain.web.content.board_variants import adapt_ogs_step

    source = ogs(73)
    before = copy.deepcopy(source)
    result = adapt_ogs_step(source)
    assert source == before
    assert result["board_variant"]["status"] == "adapted", result["board_variant"]
    assert result["board_variant"]["offset"] == [0, 10]
    assert result["stones"] == {"B": [[0, 17]], "W": [[0, 18]]}
    assert result["shapes"] == {"0,18": "triangle"}
    assert result["exercise"]["tree"]["children"][0]["point"] == [1, 18]
    assert result["viewport"] is None
    assert result["figure_id"] == source["figure_id"]


@pytest.mark.parametrize("page", [37, 49, 55, 63, 95, 107, 113, 137, 143])
def test_direct_ogs_certificates_are_executable(page):
    from katrain.web.content.board_variants import adapt_ogs_step

    source = ogs(page)
    result = adapt_ogs_step(source)
    assert result["board_variant"]["status"] == "adapted", result["board_variant"]
    assert result["size"] == 19


@pytest.mark.parametrize("page", [1, 2, 21, 31, 32, 33, 35])
def test_whole_board_or_ambiguous_locale_ogs_stays_original(page):
    from katrain.web.content.board_variants import adapt_ogs_step

    source = ogs(page)
    result = adapt_ogs_step(source)
    assert result.pop("board_variant")["status"] == "unavailable"
    assert result == source


def test_public_hash_is_independent_of_environment_ids_but_includes_text_and_source_url():
    from katrain.web.content.board_variants import adapt_ogs_step

    source = ogs(73)
    source["book_id"] = 987
    source["figure_id"] = 654
    assert adapt_ogs_step(source)["board_variant"]["status"] == "adapted"
    for field in ("instruction", "title"):
        changed = copy.deepcopy(source)
        changed["locale"]["text"][field] += "changed"
        assert adapt_ogs_step(changed)["board_variant"]["status"] == "unavailable"
    source["source_url"] += "/changed"
    assert adapt_ogs_step(source)["board_variant"]["status"] == "unavailable"


def test_missing_policy_or_metadata_never_turns_source_into_500(monkeypatch):
    from katrain.web.content import board_variants as bv

    monkeypatch.setattr(bv, "_policy", lambda: {})
    assert bv.adapt_tsumego_detail(tsumego("92643"))["board_variant"]["status"] == "unavailable"
    assert bv.adapt_ogs_step({"size": 9})["board_variant"]["status"] == "unavailable"


def test_named_illegal_points_and_rescue_are_certified_too():
    from katrain.web.content import board_variants as bv

    page7 = ogs(7)
    assert bv.adapt_ogs_step(page7)["board_variant"]["status"] == "adapted"
    goal = bv._policy()["ogs"][page7["source_id"]]["goal"]
    assert sorted((p["name"], p["legal"]) for p in goal["named_points"]) == [("A", False), ("B", False), ("C", True)]
    both = bv._policy()["ogs"][ogs(95)["source_id"]]["goal"]
    assert len(both["targets"]) == 2
    assert both["rescue_targets"]


def test_certificate_rejects_wrong_author_leaf_instead_of_using_flag_as_proof():
    from katrain.web.content import board_variants as bv

    detail = tsumego("124386")
    changed = detail["sgfContent"].replace("B[ie]C[✓ 正确]", "B[ic]C[✓ 正确]")
    detail["sgfContent"] = changed
    with pytest.raises(bv.Unavailable, match="目标证书"):
        bv.verify_goal(bv._prepare_tsumego(detail), bv._policy()["tsumego"]["124386"]["goal"])


@pytest.mark.parametrize(
    "points,expected",
    [([(0, 0)], [0, 0]), ([(8, 0)], [10, 0]), ([(0, 8)], [0, 10]), ([(8, 8)], [10, 10]), ([(4, 4)], [5, 5])],
)
def test_translation_preserves_each_named_edge_and_corner(points, expected):
    from katrain.web.content.board_variants import _offset

    assert list(_offset(points, 9)) == expected


def test_source_illegal_turn_and_branch_are_rejected():
    from katrain.web.content import board_variants as bv

    goal = bv._policy()["tsumego"]["124386"]["goal"]
    source = tsumego("124386")
    source["sgfContent"] = source["sgfContent"].replace("W[ie]", "B[ie]")
    with pytest.raises(bv.Unavailable, match="交替"):
        bv.verify_goal(bv._prepare_tsumego(source), goal)
    source = tsumego("124386")
    source["sgfContent"] = source["sgfContent"].replace("B[hh]", "B[gd]")
    with pytest.raises(bv.Unavailable, match="已有棋子"):
        bv.verify_goal(bv._prepare_tsumego(source), goal)


def test_all_named_components_connect_and_compared_marked_groups_are_recomputed():
    from katrain.web.content import board_variants as bv

    assert bv.adapt_ogs_step(ogs(138))["board_variant"]["status"] == "adapted"
    assert bv.adapt_ogs_step(ogs(492))["board_variant"]["status"] == "adapted"
    assert bv.adapt_ogs_step(ogs(278))["board_variant"]["status"] == "unavailable"
    assert bv.adapt_tsumego_detail(tsumego("76898"))["board_variant"]["status"] == "unavailable"


@pytest.mark.parametrize("source_id", ["92643", "218387", "124386", "129993"])
def test_every_representative_branch_matches_existing_independent_go_rules(source_id):
    from types import SimpleNamespace
    from katrain.core.game import BaseGame, KaTrainSGF
    from katrain.web.content import board_variants as bv

    source = tsumego(source_id)
    for detail in (source, bv.adapt_tsumego_detail(source)):
        root = KaTrainSGF.parse_sgf(detail["sgfContent"])
        game = BaseGame(SimpleNamespace(config=lambda key: "japanese"), move_tree=root)
        for node in root.nodes_in_tree:
            game.set_current_node(node)
            n = detail["boardSize"]
            actual = {(move.coords[0], n - 1 - move.coords[1]): move.player for move in game.stones}
            # Independent rule implementation, including exact captured stones.
            prepared = bv._prepare_tsumego(detail)
            expected = prepared[1].copy()
            history = [bv._signature(expected)]
            for move_node in node.nodes_from_root[1:]:
                move = move_node.moves[0]
                expected, _ = bv._play(expected, (move.coords[0], n - 1 - move.coords[1]), move.player, n, history)
                history.append(bv._signature(expected))
            assert actual == expected


def test_unreviewed_language_has_an_explicit_retained_reason():
    from katrain.web.content.board_variants import adapt_ogs_step

    source = ogs(73)
    source["locale"]["effective"] = "fr"
    assert adapt_ogs_step(source)["board_variant"]["reason"] == "本语言尚无已审核19路版本"


def test_marks_and_wrong_branches_also_preserve_source_edges():
    from katrain.web.content import board_variants as bv

    source = ogs(73)
    source["letters"]["8,0"] = "A"
    with pytest.raises(bv.Unavailable, match="相反两边"):
        bv._prepare_ogs(source)
    source = ogs(73)
    source["exercise"]["tree"]["children"].append({"point": [8, 0], "correct": False, "wrong": True, "children": []})
    with pytest.raises(bv.Unavailable, match="相反两边"):
        bv._prepare_ogs(source)


@pytest.mark.parametrize(
    "source_id,goal_text",
    [
        ("66104", "对杀"),
        ("81717", "连接"),
        ("81740", "分断"),
        ("82153", "反击"),
    ],
)
def test_specific_gc_goal_cannot_be_certified_as_generic_capture(source_id, goal_text):
    from katrain.web.content import board_variants as bv

    source = tsumego(source_id)
    result = bv.adapt_tsumego_detail(source)
    metadata = result.pop("board_variant")
    assert metadata["status"] == "unavailable"
    assert goal_text in metadata["reason"]
    assert result == source
    entry = bv._policy()["tsumego"][source_id]
    assert entry["reason_code"] == "objective_unconfirmed"
    assert not entry["available"]
    assert "goal" not in entry


def test_accepted_tsumego_requires_full_gc_and_all_comments_review(monkeypatch):
    from katrain.web.content import board_variants as bv

    policy = copy.deepcopy(bv._policy())
    policy["tsumego"]["92643"].pop("semantic_review", None)
    monkeypatch.setattr(bv, "_policy", lambda: policy)
    result = bv.adapt_tsumego_detail(tsumego("92643"))
    assert result["board_variant"]["status"] == "unavailable"
    assert "完整题面" in result["board_variant"]["reason"]


def test_offline_audit_does_not_call_unreviewed_language_policy_approved():
    from katrain.web.content import board_variants as bv
    from scripts.audit_kiosk_board_variants import audit

    source = ogs(73)
    payload = {key: source[key] for key in bv.STRUCTURE_FIELDS}
    payload["translations"] = {"fr": source["locale"]["text"]}
    report = audit({"tsumego": [], "ogs": [{"payload": payload}]}, "fr")
    assert report["ogs"][0]["status"] == "unavailable"
    assert report["summary"]["ogs"]["approved_but_failed"] == 0
