"""Tests for the GolaxyAdapter human-vs-AI engine-play state machine.

Engine and profile network boundaries are mocked; the identity-race case uses
an httpx mock transport. These tests never contact Golaxy.
The correctness core under test is the *proposed-moves discipline*:
the human move is encoded into an immutable ``proposed_moves`` snapshot BEFORE the
network call, ``ctx.moves`` is committed exactly once only after a valid AI coord
comes back, and every retry reuses the SAME snapshot -- so a timeout/retry can
never append the human move twice or land moves out of order.

Tests are async (``asyncio_mode=auto`` in pyproject.toml).
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

import httpx
import pytest

from katrain.web.platforms.golaxy.adapter import (
    EngineGameConfig,
    EngineGameContext,
    EngineGameStart,
    GolaxyAdapter,
    GolaxyEngineTerminal,
    GolaxyLobbyAuthError,
    GolaxyLobbyError,
)
from katrain.web.platforms.golaxy.coords import Move, golaxy_to_katrain, katrain_to_golaxy
from katrain.web.platforms.golaxy.engine_client import (
    AuthExpired,
    Fatal,
    GenmoveResult,
    Retryable,
    get_level,
    list_levels,
)
from katrain.web.platforms.models import (
    OnlineUser,
    PlatformCredentials,
    PlatformGameSession,
    PlatformMove,
    PlatformPass,
    PlatformResign,
)

AI_COORD = 286  # arbitrary valid on-board coord used by the mocked engine


def make_adapter() -> GolaxyAdapter:
    """Connected adapter with caller/profile reads isolated from the network."""
    adapter = GolaxyAdapter()
    adapter._rest.set_tokens("tok", "refresh")
    adapter._connected = True
    adapter._rest._get_user_code = AsyncMock(return_value="self-code")
    adapter._rest.get_player_profile = AsyncMock(
        return_value={"userCode": "self-code", "nickname": "本人", "level": None}
    )
    return adapter


def recorder():
    """Return (events_list, async_callback) for capturing emitted events."""
    events: list = []

    async def cb(*args):
        events.append(args)

    return events, cb


async def start_black(adapter: GolaxyAdapter, **cfg_kwargs) -> str:
    """Start a human-Black game (AI does not open) and return the game_id."""
    if not hasattr(adapter._rest, "engine_genmove") or not isinstance(adapter._rest.engine_genmove, AsyncMock):
        adapter._rest.engine_genmove = AsyncMock()
    cfg = EngineGameConfig(level=1100, human_color="B", **cfg_kwargs)
    start = await adapter.start_engine_game(cfg)
    return start.session.game_id


# --------------------------------------------------------------------------- #
# 1-3: happy-path start / submit                                              #
# --------------------------------------------------------------------------- #


async def test_human_black_submit_one_move():
    adapter = make_adapter()
    adapter._rest.engine_genmove = AsyncMock(return_value=GenmoveResult(coord=AI_COORD, prob=0.19))
    start = await adapter.start_engine_game(EngineGameConfig(level=1100, human_color="B"))
    assert start.first_ai_move is None
    game_id = start.session.game_id
    ctx = adapter._engine_games[game_id]

    col, row = 3, 3
    human_coord = katrain_to_golaxy(col, row)
    move = await adapter.submit_engine_move(game_id, col, row)

    ai_pt = golaxy_to_katrain(AI_COORD)
    assert isinstance(ai_pt, Move)
    assert isinstance(move, PlatformMove)
    assert (move.col, move.row) == (ai_pt.col, ai_pt.row)
    assert move.color == "W"
    assert move.move_number == 2
    assert move.game_id == game_id
    assert ctx.moves == [human_coord, AI_COORD]


async def test_human_white_start_opens_with_ai():
    adapter = make_adapter()
    adapter._rest.engine_genmove = AsyncMock(return_value=GenmoveResult(coord=AI_COORD, prob=0.19))
    start = await adapter.start_engine_game(EngineGameConfig(level=1100, human_color="W"))

    assert isinstance(start, EngineGameStart)
    fm = start.first_ai_move
    assert fm is not None
    ai_pt = golaxy_to_katrain(AI_COORD)
    assert (fm.col, fm.row) == (ai_pt.col, ai_pt.row)
    assert fm.color == "B"
    assert fm.move_number == 1
    ctx = adapter._engine_games[start.session.game_id]
    assert ctx.moves == [AI_COORD]


async def test_human_black_start_no_ai_move():
    adapter = make_adapter()
    adapter._rest.engine_genmove = AsyncMock(return_value=GenmoveResult(coord=AI_COORD, prob=0.19))
    start = await adapter.start_engine_game(EngineGameConfig(level=1100, human_color="B"))
    assert start.first_ai_move is None
    ctx = adapter._engine_games[start.session.game_id]
    assert ctx.moves == []
    adapter._rest.engine_genmove.assert_not_awaited()


@pytest.mark.parametrize("human_color", ["B", "W"])
@pytest.mark.parametrize("level_row", [{"name": "Verified bot", "level_name": "3d"}, None, {"name": "Bot"}])
async def test_player_ranks_only_include_verified_ai_level_name(monkeypatch, human_color, level_row):
    adapter = make_adapter()
    adapter._rest.engine_genmove = AsyncMock(return_value=GenmoveResult(coord=AI_COORD, prob=0.19))
    monkeypatch.setattr("katrain.web.platforms.golaxy.adapter.engine_client.get_level", lambda level: level_row)
    start = await adapter.start_engine_game(EngineGameConfig(level=1100, human_color=human_color))
    ai_color = "W" if human_color == "B" else "B"
    assert start.session.player_ranks == {
        human_color: None,
        ai_color: "3d" if level_row and "level_name" in level_row else None,
    }


@pytest.mark.parametrize("human_color", ["B", "W"])
async def test_engine_game_uses_current_platform_self_rank_once(human_color):
    adapter = make_adapter()
    adapter._rest.get_player_profile.return_value["level"] = 1500
    adapter._rest.engine_genmove = AsyncMock(return_value=GenmoveResult(coord=AI_COORD, prob=0.19))

    start = await adapter.start_engine_game(EngineGameConfig(level=1100, human_color=human_color))
    ai_color = "W" if human_color == "B" else "B"
    assert start.session.player_ranks == {human_color: "2段", ai_color: get_level(1100)["level_name"]}
    adapter._rest.get_player_profile.assert_awaited_once_with("self-code")

    await adapter.submit_engine_move(start.session.game_id, 3, 3)
    adapter._rest.get_player_profile.assert_awaited_once_with("self-code")


@pytest.mark.parametrize("level", [None, 2700, True, 1500.0, "1500.0", {"level": 1500}, []])
async def test_engine_game_unknown_or_malformed_self_level_stays_unknown(level):
    adapter = make_adapter()
    adapter._rest.get_player_profile.return_value["level"] = level
    start = await adapter.start_engine_game(EngineGameConfig(level=1100, human_color="B"))
    assert start.session.player_ranks == {"B": None, "W": get_level(1100)["level_name"]}
    adapter._rest.get_player_profile.assert_awaited_once_with("self-code")


@pytest.mark.parametrize(
    "profile",
    [
        {"user_id": "self-code", "is_self": False, "rank": "2段"},
        {"user_id": "self-code", "is_self": 1, "rank": "2段"},
        {"user_id": "other-code", "is_self": True, "rank": "2段"},
        {"user_id": "self-code", "is_self": True, "rank": "2d"},
        {"user_id": "self-code", "is_self": True, "rank": 1500},
        {"user_id": "self-code", "is_self": True},
    ],
)
async def test_engine_game_rejects_unverified_or_noncanonical_self_rank(profile):
    adapter = make_adapter()
    adapter.get_player_profile = AsyncMock(return_value=profile)
    start = await adapter.start_engine_game(EngineGameConfig(level=1100, human_color="B"))
    assert start.session.player_ranks["B"] is None
    adapter.get_player_profile.assert_awaited_once_with("self-code")


@pytest.mark.parametrize("stage", ["caller", "profile"])
@pytest.mark.parametrize("error", [GolaxyLobbyError("unavailable"), GolaxyLobbyAuthError("expired"), TimeoutError()])
async def test_engine_game_self_rank_failure_does_not_block_ai_opening(stage, error):
    adapter = make_adapter()
    lookup = adapter._rest._get_user_code if stage == "caller" else adapter._rest.get_player_profile
    lookup.side_effect = error
    adapter._rest.refresh_access_token = AsyncMock()
    adapter._rest.engine_genmove = AsyncMock(return_value=GenmoveResult(coord=AI_COORD, prob=0.19))

    start = await adapter.start_engine_game(EngineGameConfig(level=1100, human_color="W"))
    assert start.session.player_ranks == {"W": None, "B": get_level(1100)["level_name"]}
    assert start.first_ai_move.color == "B"
    adapter._rest.refresh_access_token.assert_not_awaited()
    lookup.assert_awaited_once()


@pytest.mark.parametrize("stage", ["caller", "profile"])
async def test_engine_game_self_rank_lookup_has_one_three_second_budget(monkeypatch, stage):
    adapter = make_adapter()
    real_timeout = asyncio.timeout
    budgets = []

    def short_timeout(seconds):
        budgets.append(seconds)
        return real_timeout(0.01)

    async def pending(*args):
        await asyncio.Event().wait()

    lookup = adapter._rest._get_user_code if stage == "caller" else adapter._rest.get_player_profile
    lookup.side_effect = pending
    monkeypatch.setattr(asyncio, "timeout", short_timeout)
    start = await adapter.start_engine_game(EngineGameConfig(level=1100, human_color="B"))
    assert start.session.player_ranks["B"] is None
    assert budgets == [3.0]
    lookup.assert_awaited_once()


async def test_engine_game_discards_self_rank_when_credential_changes():
    adapter = make_adapter()

    async def changed_profile(peer_code):
        adapter._rest.set_tokens("next-token", "next-refresh")
        return {"user_id": "self-code", "is_self": True, "rank": "2段"}

    adapter.get_player_profile = AsyncMock(side_effect=changed_profile)
    start = await adapter.start_engine_game(EngineGameConfig(level=1100, human_color="B"))
    assert start.session.player_ranks["B"] is None
    adapter.get_player_profile.assert_awaited_once_with("self-code")


@pytest.mark.parametrize("change", ["disconnect", "credentials"])
async def test_engine_game_stops_profile_lookup_if_identity_read_changes_connection(change):
    adapter = make_adapter()

    async def changed_caller():
        if change == "disconnect":
            adapter._connected = False
        else:
            adapter._rest.set_tokens("next-token", "next-refresh")
        return "self-code"

    adapter._rest._get_user_code.side_effect = changed_caller
    start = await adapter.start_engine_game(EngineGameConfig(level=1100, human_color="B"))
    assert start.session.player_ranks["B"] is None
    adapter._rest.get_player_profile.assert_not_awaited()


async def test_engine_game_does_not_look_up_rank_while_disconnected():
    adapter = make_adapter()
    adapter._connected = False
    start = await adapter.start_engine_game(EngineGameConfig(level=1100, human_color="B"))
    assert start.session.player_ranks["B"] is None
    adapter._rest._get_user_code.assert_not_awaited()
    adapter._rest.get_player_profile.assert_not_awaited()


async def test_engine_game_discards_rank_when_disconnected_during_lookup():
    adapter = make_adapter()

    async def disconnected_profile(peer_code):
        adapter._connected = False
        return {"user_id": "self-code", "is_self": True, "rank": "2段"}

    adapter.get_player_profile = AsyncMock(side_effect=disconnected_profile)
    start = await adapter.start_engine_game(EngineGameConfig(level=1100, human_color="B"))
    assert start.session.player_ranks["B"] is None
    adapter.get_player_profile.assert_awaited_once_with("self-code")


async def test_engine_game_pending_identity_cannot_pollute_switched_account_cache():
    adapter = GolaxyAdapter()
    adapter._connected = True
    adapter._rest.set_tokens("old-token", "old-refresh")

    async def switched_identity(request):
        adapter._rest.set_tokens("new-token", "new-refresh")
        adapter._rest.set_username("0086-13000000002")
        adapter._rest._user_code = "new-self"
        return httpx.Response(
            200,
            json={
                "active": True,
                "username": "0086-13000000001",
                "nickname": "旧本人",
                "usercode": "old-self",
            },
        )

    adapter._rest._client = httpx.AsyncClient(
        base_url="https://www.19x19.com", transport=httpx.MockTransport(switched_identity)
    )
    adapter._rest.get_player_profile = AsyncMock(
        return_value={"userCode": "old-self", "nickname": "旧本人", "level": 1500}
    )
    try:
        start = await adapter.start_engine_game(EngineGameConfig(level=1100, human_color="B"))
        assert start.session.player_ranks["B"] is None
        assert adapter._rest._user_code == "new-self"
        assert adapter._rest._username == "0086-13000000002"
    finally:
        await adapter._rest.close()


@pytest.mark.parametrize("auth_data", [{"password": "new-password"}, {"sms_code": "123456"}, {"scan_uuid": "new-uuid"}])
async def test_new_login_rejects_old_identity_before_new_token_arrives(auth_data):
    adapter = GolaxyAdapter()
    adapter._connected = True
    adapter._rest.set_tokens("old-token", "old-refresh")
    adapter._rest.set_username("0086-13000000001")
    identity_started = asyncio.Event()
    login_started = asyncio.Event()
    release_old_identity = asyncio.Event()
    release_login = asyncio.Event()
    profile_callers = []

    async def handler(request):
        if request.url.path == "/api/auth/oauth/token":
            login_started.set()
            await release_login.wait()
            return httpx.Response(200, json={"access_token": "new-token", "refresh_token": "new-refresh"})
        if request.url.path == "/api/auth/oauth/check_token":
            old = httpx.QueryParams(request.content.decode())["token"] == "old-token"
            if old:
                identity_started.set()
                await release_old_identity.wait()
            return httpx.Response(
                200,
                json={
                    "active": True,
                    "username": "0086-13000000001" if old else "0086-13000000002",
                    "nickname": "旧本人" if old else "新本人",
                    "usercode": "old-self" if old else "new-self",
                },
            )
        caller = request.url.path.rsplit("/", 1)[-1]
        profile_callers.append(caller)
        assert request.url.params["peer_user_code"] == caller
        assert caller in ("old-self", "new-self")
        return httpx.Response(
            200,
            json={
                "code": 0,
                "data": {
                    "userCode": caller,
                    "nickname": "本人",
                    "level": 1500 if caller == "old-self" else 1900,
                },
            },
        )

    adapter._rest._client = httpx.AsyncClient(base_url="https://example.test", transport=httpx.MockTransport(handler))
    old_rank_task = asyncio.create_task(adapter._get_engine_self_rank())
    login_task = None
    try:
        await asyncio.wait_for(identity_started.wait(), 1)
        login_task = asyncio.create_task(adapter.connect(PlatformCredentials("golaxy", "13000000002", auth_data)))
        await asyncio.wait_for(login_started.wait(), 1)
        assert adapter.is_connected is False
        release_old_identity.set()
        old_rank = await asyncio.wait_for(old_rank_task, 1)
        identity_while_login_pending = (adapter._rest._user_code, adapter._rest._username)
        release_login.set()
        assert await asyncio.wait_for(login_task, 1) is True

        start = await adapter.start_engine_game(EngineGameConfig(level=1100, human_color="B"))
        assert (old_rank, start.session.player_ranks["B"]) == (None, "4段")
        assert identity_while_login_pending == (None, "0086-13000000002")
        assert adapter._rest._user_code == "new-self"
        assert profile_callers == ["new-self"]
    finally:
        for task in (old_rank_task, login_task):
            if task is not None and not task.done():
                task.cancel()
        await asyncio.gather(
            *(task for task in (old_rank_task, login_task) if task is not None), return_exceptions=True
        )
        await adapter._rest.close()


async def test_engine_self_rank_discards_profile_if_new_login_starts_before_token_changes():
    adapter = make_adapter()

    async def new_login_started(peer_code):
        adapter._rest.clear_username()
        adapter._rest.set_username("13000000002")
        return {"user_id": "self-code", "is_self": True, "rank": "2段"}

    adapter.get_player_profile = AsyncMock(side_effect=new_login_started)
    start = await adapter.start_engine_game(EngineGameConfig(level=1100, human_color="B"))
    assert start.session.player_ranks["B"] is None


@pytest.mark.parametrize(
    "method,args",
    [
        ("login_password", ("13000000002", "new-password")),
        ("login_sms", ("13000000002", "123456")),
        ("login_scan_code", ("new-uuid",)),
    ],
)
async def test_login_token_publication_invalidates_previous_user_code(method, args):
    adapter = GolaxyAdapter()
    adapter._rest.set_tokens("old-token", "old-refresh")
    adapter._rest._user_code = "old-self"
    adapter._rest._client = httpx.AsyncClient(
        base_url="https://example.test",
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                json={"access_token": "new-token", "refresh_token": "new-refresh"},
            )
        ),
    )
    try:
        await getattr(adapter._rest, method)(*args)
        assert adapter._rest._user_code is None
    finally:
        await adapter._rest.close()


# --------------------------------------------------------------------------- #
# 4-7: retry / commit discipline (the correctness core)                       #
# --------------------------------------------------------------------------- #


async def test_retryable_reuses_same_proposed_moves_and_commits_once():
    adapter = make_adapter()
    game_id = await start_black(adapter)
    ctx = adapter._engine_games[game_id]

    calls: list[list[int]] = []

    def side_effect(*, moves, **kwargs):
        calls.append(list(moves))
        if len(calls) == 1:
            raise Retryable("transient")
        return GenmoveResult(coord=AI_COORD, prob=0.19)

    adapter._rest.engine_genmove = AsyncMock(side_effect=side_effect)

    col, row = 3, 3
    human_coord = katrain_to_golaxy(col, row)
    move = await adapter.submit_engine_move(game_id, col, row)

    # retried exactly once, both attempts saw the SAME proposed_moves
    assert len(calls) == 2
    assert calls[0] == [human_coord]
    assert calls[1] == [human_coord]
    # human move appended exactly once (length 2, not 3), AI move committed
    assert ctx.moves == [human_coord, AI_COORD]
    assert len(ctx.moves) == 2
    assert move.move_number == 2


async def test_auth_expired_refresh_then_retry_commits_once():
    adapter = make_adapter()
    game_id = await start_black(adapter)
    ctx = adapter._engine_games[game_id]

    adapter._rest.refresh_access_token = AsyncMock(return_value={"access_token": "new"})

    calls: list[list[int]] = []

    def side_effect(*, moves, **kwargs):
        calls.append(list(moves))
        if len(calls) == 1:
            raise AuthExpired("token expired")
        return GenmoveResult(coord=AI_COORD, prob=0.19)

    adapter._rest.engine_genmove = AsyncMock(side_effect=side_effect)

    refreshed, refreshed_cb = recorder()
    adapter.on_token_refreshed(refreshed_cb)

    col, row = 3, 3
    human_coord = katrain_to_golaxy(col, row)
    move = await adapter.submit_engine_move(game_id, col, row)

    adapter._rest.refresh_access_token.assert_awaited_once()
    assert len(refreshed) == 1
    assert len(calls) == 2
    assert calls[0] == calls[1] == [human_coord]
    assert ctx.moves == [human_coord, AI_COORD]
    assert move.move_number == 2


async def test_auth_expired_twice_emits_and_raises_no_commit():
    adapter = make_adapter()
    game_id = await start_black(adapter)
    ctx = adapter._engine_games[game_id]
    before = list(ctx.moves)

    adapter._rest.refresh_access_token = AsyncMock(return_value={})
    adapter._rest.engine_genmove = AsyncMock(side_effect=AuthExpired("token expired"))

    expired, expired_cb = recorder()
    adapter.on_auth_expired(expired_cb)

    with pytest.raises(AuthExpired):
        await adapter.submit_engine_move(game_id, 3, 3)

    assert len(expired) == 1
    assert ctx.moves == before == []  # no half-commit
    assert adapter._rest.engine_genmove.await_count == 2


async def test_fatal_not_retried_no_commit():
    adapter = make_adapter()
    game_id = await start_black(adapter)
    ctx = adapter._engine_games[game_id]

    mock = AsyncMock(side_effect=Fatal("bad request"))
    adapter._rest.engine_genmove = mock

    with pytest.raises(Fatal):
        await adapter.submit_engine_move(game_id, 3, 3)

    mock.assert_awaited_once()  # no retry
    assert ctx.moves == []


# --------------------------------------------------------------------------- #
# 8: AI pass / resign / unknown special                                       #
# --------------------------------------------------------------------------- #


async def test_ai_pass_is_committed_and_keeps_game_playing():
    adapter = make_adapter()
    game_id = await start_black(adapter)
    ctx = adapter._engine_games[game_id]
    ended, ended_cb = recorder()
    adapter.on_game_ended(ended_cb)
    adapter._rest.engine_genmove = AsyncMock(return_value=GenmoveResult(coord=-1, prob=0.0))

    reply = await adapter.submit_engine_move(game_id, 3, 3)

    assert isinstance(reply, PlatformPass)
    assert reply.color == "W"
    assert reply.move_number == 2
    assert ctx.moves == [katrain_to_golaxy(3, 3), -1]
    assert ctx.status == "playing"
    assert ended == []


async def test_ai_resign_is_conclusive_human_win():
    adapter = make_adapter()
    game_id = await start_black(adapter)
    ctx = adapter._engine_games[game_id]
    ended, ended_cb = recorder()
    adapter.on_game_ended(ended_cb)
    adapter._rest.engine_genmove = AsyncMock(return_value=GenmoveResult(coord=-3, prob=0.0))

    reply = await adapter.submit_engine_move(game_id, 3, 3)

    assert isinstance(reply, PlatformResign)
    assert reply.color == "W"
    assert reply.winner == "B"
    assert reply.move_number == 1
    assert ctx.moves == [katrain_to_golaxy(3, 3)]
    assert ctx.status == "finished"
    assert ended == [(game_id, "ai_resign", "B")]


async def test_unknown_special_coord_terminates_game_without_winner():
    adapter = make_adapter()
    game_id = await start_black(adapter)
    ctx = adapter._engine_games[game_id]

    ended, ended_cb = recorder()
    adapter.on_game_ended(ended_cb)

    adapter._rest.engine_genmove = AsyncMock(return_value=GenmoveResult(coord=999, prob=0.0))

    with pytest.raises(GolaxyEngineTerminal):
        await adapter.submit_engine_move(game_id, 3, 3)

    assert ctx.status == "finished"
    assert len(ended) == 1
    assert ended[0][0] == game_id
    assert ended[0][1] == "ai_unknown_special"
    assert ended[0][2] == ""
    # The human move is real; only the unknown AI value is omitted.
    assert ctx.moves == [katrain_to_golaxy(3, 3)]


async def test_human_pass_is_sent_to_engine_and_ai_move_is_committed():
    adapter = make_adapter()
    game_id = await start_black(adapter)
    ctx = adapter._engine_games[game_id]
    adapter._rest.engine_genmove = AsyncMock(return_value=GenmoveResult(coord=AI_COORD, prob=0.19))

    reply = await adapter.submit_engine_pass(game_id)

    assert isinstance(reply, PlatformMove)
    assert ctx.moves == [-1, AI_COORD]
    assert adapter._rest.engine_genmove.await_args.kwargs["moves"] == [-1]


# --------------------------------------------------------------------------- #
# 9: resign                                                                    #
# --------------------------------------------------------------------------- #


async def test_resign_engine_game_human_black():
    adapter = make_adapter()
    game_id = await start_black(adapter)

    ended, ended_cb = recorder()
    adapter.on_game_ended(ended_cb)

    await adapter.resign_engine_game(game_id)

    assert game_id not in adapter._engine_games  # popped
    assert len(ended) == 1
    assert ended[0] == (game_id, "resign", "W")  # human Black resigns -> AI White wins


async def test_resign_engine_game_human_white_winner_black():
    adapter = make_adapter()
    adapter._rest.engine_genmove = AsyncMock(return_value=GenmoveResult(coord=AI_COORD, prob=0.1))
    start = await adapter.start_engine_game(EngineGameConfig(level=1100, human_color="W"))
    game_id = start.session.game_id

    ended, ended_cb = recorder()
    adapter.on_game_ended(ended_cb)

    await adapter.resign_engine_game(game_id)
    assert ended[0] == (game_id, "resign", "B")


async def test_resign_unknown_game_is_noop():
    adapter = make_adapter()
    ended, ended_cb = recorder()
    adapter.on_game_ended(ended_cb)
    await adapter.resign_engine_game("nope")  # must not raise
    assert ended == []


# --------------------------------------------------------------------------- #
# 10: rebuild_engine_moves                                                     #
# --------------------------------------------------------------------------- #


async def test_rebuild_engine_moves_resets_context():
    adapter = make_adapter()
    game_id = await start_black(adapter)
    ctx = adapter._engine_games[game_id]

    adapter.rebuild_engine_moves(game_id, [(3, 3), (15, 3)])
    assert ctx.moves == [katrain_to_golaxy(3, 3), katrain_to_golaxy(15, 3)]


async def test_rebuild_engine_moves_preserves_passes():
    adapter = make_adapter()
    game_id = await start_black(adapter)

    adapter.rebuild_engine_moves(game_id, [(3, 3), None, (15, 3)])

    assert adapter._engine_games[game_id].moves == [katrain_to_golaxy(3, 3), -1, katrain_to_golaxy(15, 3)]


async def test_rebuild_engine_moves_unknown_game_raises():
    adapter = make_adapter()
    with pytest.raises(KeyError):
        adapter.rebuild_engine_moves("nope", [(3, 3)])


# --------------------------------------------------------------------------- #
# 11: get_engine_levels                                                        #
# --------------------------------------------------------------------------- #


def test_get_engine_levels_returns_full_table():
    adapter = GolaxyAdapter()
    levels = adapter.get_engine_levels()
    assert levels == list_levels()
    assert len(levels) == 39


# --------------------------------------------------------------------------- #
# 12: submit on unknown / finished game                                       #
# --------------------------------------------------------------------------- #


async def test_submit_unknown_game_raises_keyerror():
    adapter = make_adapter()
    with pytest.raises(KeyError):
        await adapter.submit_engine_move("nope", 3, 3)


async def test_submit_finished_game_raises_runtimeerror():
    adapter = make_adapter()
    game_id = await start_black(adapter)
    adapter._engine_games[game_id].status = "finished"
    with pytest.raises(RuntimeError):
        await adapter.submit_engine_move(game_id, 3, 3)


# --------------------------------------------------------------------------- #
# capability flag / session shape / auth guard                                #
# --------------------------------------------------------------------------- #


def test_supports_engine_play_flag():
    assert GolaxyAdapter.supports_engine_play is True
    assert GolaxyAdapter().supports_engine_play is True


async def test_start_engine_game_requires_authentication():
    adapter = GolaxyAdapter()  # no tokens set -> not authenticated
    with pytest.raises(RuntimeError):
        await adapter.start_engine_game(EngineGameConfig(level=1100, human_color="B"))


async def test_start_engine_game_session_fields_from_level_table():
    adapter = make_adapter()
    # human Black + handicap 2 => White (the AI) is to move and opens, so the genmove
    # mock must return a valid GenmoveResult (Task B seeds handicap stones + turn logic).
    adapter._rest.engine_genmove = AsyncMock(return_value=GenmoveResult(coord=AI_COORD, prob=0.19))
    cfg = EngineGameConfig(level=1100, human_color="B", komi=6.5, rule="japanese", handicap=2)
    start = await adapter.start_engine_game(cfg)
    s = start.session

    assert isinstance(s, PlatformGameSession)
    assert s.platform == "golaxy"
    assert s.my_color == "B"
    assert s.board_size == 19
    assert s.ranked is False
    assert s.komi == 6.5
    assert s.rules == "japanese"
    assert s.handicap == 2
    assert s.time_control.main_time == 0

    level = get_level(1100)
    assert isinstance(s.opponent, OnlineUser)
    assert s.opponent.platform == "golaxy"
    assert s.opponent.user_id == "1100"
    assert s.opponent.rank_numeric == 1100.0
    assert s.opponent.username == level["name"]  # 星铠虾
    assert s.opponent.rank == level["level_name"]  # 1级


async def test_start_engine_game_unknown_level_fallback_name():
    adapter = make_adapter()
    adapter._rest.engine_genmove = AsyncMock()
    start = await adapter.start_engine_game(EngineGameConfig(level=12345, human_color="B"))
    assert start.session.opponent.username == "AI-12345"
    assert start.session.opponent.rank == "AI-12345"


async def test_engine_game_ids_are_unique_and_monotonic():
    adapter = make_adapter()
    adapter._rest.engine_genmove = AsyncMock()
    g1 = (await adapter.start_engine_game(EngineGameConfig(level=1100, human_color="B"))).session.game_id
    g2 = (await adapter.start_engine_game(EngineGameConfig(level=1100, human_color="B"))).session.game_id
    assert g1 != g2
    assert g1 == "golaxy-engine-1"
    assert g2 == "golaxy-engine-2"
