"""Display-only Go account projections preserve canonical identities and external SGFs."""

import asyncio
from types import SimpleNamespace

from katrain.web.api.v1.endpoints import games
from katrain.web.core.public_identity import display_account_name


def test_active_lobby_cards_include_trusted_public_names_beside_canonical_names(monkeypatch):
    monkeypatch.setattr(games, "human_ladder_rungs", lambda factory, ids: {})
    session = SimpleNamespace(
        session_id="room", player_b_id=7, player_w_id=8, game_ended=False, game_type="free", last_state={"history": []}
    )
    manager = SimpleNamespace(list_active_multiplayer_sessions=lambda: [session], spectator_count=lambda s: 0)
    users = [
        dict(id=7, username="u_0123456789abcdefabcd", public_username="公开棋手"),
        dict(id=8, username="old-player", public_username=None),
    ]
    state = SimpleNamespace(
        session_manager=manager, user_repo=SimpleNamespace(list_users=lambda: users), session_factory=None
    )
    rows = asyncio.run(games.list_active_multiplayer_games(SimpleNamespace(app=SimpleNamespace(state=state))))
    assert rows[0]["player_b"] == users[0]["username"]
    assert rows[0]["player_b_public_username"] == "公开棋手"
    assert rows[0]["player_b_id"] == 7
    assert rows[0]["player_w"] == "old-player"


def test_account_labels_keep_legacy_human_names_and_reject_private_fallbacks():
    assert display_account_name("old-player") == "old-player"
    assert display_account_name("2024") == "2024"
    assert display_account_name("u_0123456789abcdefabcd", "公开棋手") == "公开棋手"
    for name in (
        "u_0123456789abcdefabcd",
        "cce0f02b-36f3-4ae5-813e-101c73fe7830",
        "+8613800138000",
        "008613800138000",
        "138-0013-8000",
        "+86 (138) 0013 8000",
    ):
        assert display_account_name(name) is None
