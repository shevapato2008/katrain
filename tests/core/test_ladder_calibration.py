import math, pytest

from katrain.core.ladder_calibration import elo_from_winrate, play_one_game


def test_elo_math():
    assert abs(elo_from_winrate(25, 50)[0]) < 1e-6
    assert elo_from_winrate(40, 50)[0] > 0 > elo_from_winrate(10, 50)[0]
    assert math.isfinite(elo_from_winrate(50, 50)[0])
    assert elo_from_winrate(0, 0) == (0.0, float("-inf"), float("inf"))  # no conclusive games


@pytest.mark.asyncio
async def test_unverified_golaxy_terminal_never_scored_even_if_settled():
    """H1 (round 4): an UNVERIFIED out-of-board golaxy reply (e.g. coord=99999) is a possibly
    corrupted response — it must NEVER be adjudicated/counted, even in a coincidentally-settled
    position. It is inconclusive_terminal, not a win/loss."""

    async def our(m):
        return 0

    async def gx(m):
        return "terminal"  # adapter maps any unverified out-of-board coord here

    async def adj(m):
        return (5.0, True)  # settled + we'd be winning — still must NOT count

    r = await play_one_game(our_move=our, golaxy_move=gx, adjudicate=adj, our_color="B", move_cap=10)
    assert r.conclusive is False and r.result == "inconclusive_terminal" and r.our_win is False


@pytest.mark.asyncio
async def test_verified_golaxy_resign_is_our_win():
    async def our(m):
        return 0

    async def gx(m):
        return "resign"  # adapter recognized the smoke-verified resign code

    async def adj(m):
        return (-99.0, True)  # even if the raw position looks bad, resign = concede

    r = await play_one_game(our_move=our, golaxy_move=gx, adjudicate=adj, our_color="B", move_cap=10)
    assert r.conclusive and r.result == "our_win" and r.end_reason == "golaxy_resign"


@pytest.mark.asyncio
async def test_verified_golaxy_pass_adjudicates_like_our_pass():
    """Symmetry for VERIFIED stops: a smoke-verified golaxy pass adjudicates the same settled
    position identically to an our-pass."""

    async def adj(m):
        return (-5.0, True)  # white ahead, settled

    async def our_move(m):
        return 0

    async def gx_pass(m):
        return "pass"  # verified golaxy pass

    r = await play_one_game(our_move=our_move, golaxy_move=gx_pass, adjudicate=adj, our_color="W", move_cap=10)
    assert r.conclusive and r.result == "our_win" and r.end_reason == "golaxy_pass"  # W ahead -> our(W) win


@pytest.mark.asyncio
async def test_our_pass_unsettled_is_inconclusive():
    async def our(m):
        return "pass"

    async def gx(m):
        return 0

    async def adj(m):
        return (1.0, False)  # NOT settled -> inconclusive

    r = await play_one_game(our_move=our, golaxy_move=gx, adjudicate=adj, our_color="B", move_cap=10)
    assert r.conclusive is False and r.result == "inconclusive_unsettled" and r.our_win is False


@pytest.mark.asyncio
async def test_our_unavailable_is_inconclusive_engine():
    async def our(m):
        return "unavailable"  # rung couldn't produce a certified move

    async def gx(m):
        return 0

    async def adj(m):
        return (5.0, True)

    r = await play_one_game(our_move=our, golaxy_move=gx, adjudicate=adj, our_color="B", move_cap=10)
    assert r.conclusive is False and r.result == "inconclusive_engine"


@pytest.mark.asyncio
async def test_no_sentinel_ever_reaches_golaxy():
    """G1 regression: history passed to golaxy_move must contain only valid wire coords."""
    seen_histories = []
    calls = {"n": 0}

    async def our(m):
        calls["n"] += 1
        return 5 if calls["n"] <= 2 else "pass"  # two real moves, then pass

    async def gx(m):
        seen_histories.append(list(m))
        return 7

    async def adj(m):
        return (1.0, True)

    await play_one_game(our_move=our, golaxy_move=gx, adjudicate=adj, our_color="B", board_size=19, move_cap=10)
    for h in seen_histories:
        assert all(isinstance(c, int) and 0 <= c < 19 * 19 for c in h)  # no -1 / sentinel / invalid


@pytest.mark.asyncio
async def test_unsettled_cap_is_inconclusive():
    async def mv(m):
        return 0

    async def adj(m):
        return (2.0, False)  # not settled

    r = await play_one_game(our_move=mv, golaxy_move=mv, adjudicate=adj, our_color="B", move_cap=4)
    assert r.conclusive is False and r.result == "inconclusive_unsettled"


@pytest.mark.asyncio
async def test_missing_score_is_inconclusive():
    async def our(m):
        return "pass"

    async def gx(m):
        return 0

    async def adj(m):
        return (None, True)

    r = await play_one_game(our_move=our, golaxy_move=gx, adjudicate=adj, our_color="B", move_cap=10)
    assert r.conclusive is False and r.result == "inconclusive_score"


@pytest.mark.asyncio
async def test_initial_history_is_copied_and_sets_white_to_play():
    initial_history = [0, 20, 2]
    seen = []

    async def our(history):
        seen.append(("our", list(history), history is initial_history))
        return "pass"

    async def opponent(history):
        seen.append(("opponent", list(history), history is initial_history))
        return "pass"

    async def adjudicate(history):
        assert history == initial_history
        assert history is not initial_history
        return (-1.0, True)

    outcome = await play_one_game(
        our_move=our,
        golaxy_move=opponent,
        adjudicate=adjudicate,
        our_color="B",
        initial_history=initial_history,
        move_cap=10,
    )

    assert seen == [("opponent", initial_history, False)]
    assert initial_history == [0, 20, 2]
    assert outcome.num_moves == 3


@pytest.mark.asyncio
async def test_initial_history_counts_only_new_moves_against_move_cap_and_is_adjudicated():
    initial_history = [0, 20, 2, 22]
    seen = []

    async def move(history):
        seen.append(list(history))
        return 40 + len(seen)

    async def adjudicate(history):
        assert history == [0, 20, 2, 22, 41, 42, 43]
        return (1.0, True)

    outcome = await play_one_game(
        our_move=move,
        golaxy_move=move,
        adjudicate=adjudicate,
        our_color="B",
        initial_history=initial_history,
        move_cap=7,
    )

    assert len(seen) == 3
    assert outcome.num_moves == 7
    assert outcome.end_reason == "move_cap"
    assert initial_history == [0, 20, 2, 22]


@pytest.mark.asyncio
async def test_initial_history_at_move_cap_plays_no_new_moves():
    calls = 0

    async def move(_history):
        nonlocal calls
        calls += 1
        return 42

    async def adjudicate(history):
        assert history == [0, 20, 2, 22]
        return (1.0, True)

    outcome = await play_one_game(
        our_move=move,
        golaxy_move=move,
        adjudicate=adjudicate,
        our_color="B",
        initial_history=[0, 20, 2, 22],
        move_cap=4,
    )

    assert calls == 0
    assert outcome.num_moves == 4


@pytest.mark.asyncio
@pytest.mark.parametrize("bad_history", [[-1], [361], [True], [1.0], "not-a-list"])
async def test_initial_history_rejects_non_wire_or_out_of_bounds_moves(bad_history):
    async def move(_history):
        return "pass"

    async def adjudicate(_history):
        return (1.0, True)

    with pytest.raises(ValueError, match="initial_history"):
        await play_one_game(
            our_move=move,
            golaxy_move=move,
            adjudicate=adjudicate,
            our_color="B",
            initial_history=bad_history,
        )
