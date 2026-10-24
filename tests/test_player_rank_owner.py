"""Real headless interface coverage, outside web_ui's mocked interface setup."""

import pytest

from katrain.core.constants import AI_DEFAULT, PLAYER_AI, PLAYER_HUMAN
from katrain.web.interface import WebKaTrain
from katrain.web.session import SessionManager


@pytest.fixture
def manager(monkeypatch):
    original_init = WebKaTrain.__init__

    def init(self, **kwargs):
        kwargs["force_package_config"] = True
        original_init(self, **kwargs)
        self.update_player("B", player_type=PLAYER_HUMAN)
        self.update_player("W", player_type=PLAYER_AI, player_subtype=AI_DEFAULT)

    monkeypatch.setattr(WebKaTrain, "__init__", init)
    manager = SessionManager(enable_engine=False)
    yield manager
    for session_id in list(manager._sessions):
        manager.remove_session(session_id)


@pytest.mark.parametrize("human_color", ["B", "W"])
def test_private_ai_owner_uses_account_id_and_exact_human_color(manager, human_color):
    session = manager.create_session(user_id=7, katago_uuid="engine-uuid")
    kt = session.katrain
    kt.update_player(human_color, player_type=PLAYER_HUMAN)
    kt.update_player("W" if human_color == "B" else "B", player_type=PLAYER_AI, player_subtype=AI_DEFAULT)
    assert kt.user_id == "engine-uuid"
    assert kt.get_state()["rank_owner"] == {"user_id": 7, "color": human_color}


@pytest.mark.parametrize("account_id", [None, 0, -1, True, "engine-uuid"])
def test_engine_identity_and_anonymous_later_management_claim_never_supply_owner(manager, account_id):
    session = manager.create_session(user_id=account_id, katago_uuid="engine-uuid")
    session.owner_user_id = 7
    session.user_id = 7
    assert session.katrain.get_state()["rank_owner"] is None


def test_loading_sgf_clears_current_owner_and_platform_ranks_until_new_private_game(manager):
    session = manager.create_session(user_id=7)
    kt = session.katrain
    assert kt.get_state()["rank_owner"] == {"user_id": 7, "color": "B"}
    kt.platform_player_ranks = {"B": "1d", "W": "3k"}
    kt("load_sgf", "(;SZ[19]PB[Someone else];B[pd])", skip_initial_analysis=True)
    assert kt.get_state()["rank_owner"] is None
    assert kt.get_state()["platform_player_ranks"] == {}
    assert session.last_state["rank_owner"] is None
    kt("new_game", skip_initial_analysis=True)
    assert kt.get_state()["rank_owner"] == {"user_id": 7, "color": "B"}


@pytest.mark.parametrize("kind", ["research", "multiplayer", "platform"])
def test_non_private_sessions_exclude_owner_before_the_first_state(manager, monkeypatch, kind):
    observed = []
    original_on_state = manager._on_state

    def on_state(session_id, state):
        observed.append(state["rank_owner"])
        original_on_state(session_id, state)

    monkeypatch.setattr(manager, "_on_state", on_state)
    if kind == "research":
        session = manager.create_research_session(7)
    else:
        session = manager.create_multiplayer_session(
            7, -1, initial_game_type="pvp_online" if kind == "platform" else "free"
        )
    assert observed and all(owner is None for owner in observed)
    assert session.last_state["rank_owner"] is None
    session.katrain("new_game", skip_initial_analysis=True)
    assert session.katrain.get_state()["rank_owner"] is None


@pytest.mark.parametrize("marker", ["platform_engine_color", "platform_my_color"])
def test_platform_markers_exclude_private_owner(manager, marker):
    kt = manager.create_session(user_id=7).katrain
    setattr(kt, marker, "W")
    assert kt.get_state()["rank_owner"] is None


@pytest.mark.parametrize(
    "game_type,expected",
    [
        ("free", True),
        ("ranked", True),
        ("ai_ladder_ranked", True),
        ("rated", False),
        ("pvp_local", False),
        ("pvp_online", False),
    ],
)
def test_owner_requires_private_ai_game_type_and_one_human(manager, game_type, expected):
    kt = manager.create_session(user_id=7, initial_game_type=game_type).katrain
    assert (kt.get_state()["rank_owner"] is not None) is expected
    kt.update_player("W", player_type=PLAYER_HUMAN)
    assert kt.get_state()["rank_owner"] is None
