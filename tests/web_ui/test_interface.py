import pytest
import os
import sys

# Ensure katrain package is in path
sys.path.append(os.getcwd())

from katrain.web.interface import NullEngine, WebKaTrain
def test_web_katrain_initialization():
    """Test that WebKaTrain can be initialized without Kivy GUI errors."""
    wkt = WebKaTrain(force_package_config=True, enable_engine=False)
    assert wkt.engine is None
    assert wkt.game is None
    assert "B" in wkt.players_info
    assert "W" in wkt.players_info

def test_web_katrain_start_game():
    """Test starting a game and getting the initial state."""
    wkt = WebKaTrain(force_package_config=True, enable_engine=False)
    wkt.start()
    assert wkt.game is not None
    assert isinstance(wkt.engine, NullEngine)
    state = wkt.get_state()
    assert state["board_size"] == [19, 19]
    assert state["is_root"] is True
    assert state["player_to_move"] == "B"

def test_web_katrain_play_move():
    """Test playing a move and verifying the state update."""
    wkt = WebKaTrain(force_package_config=True, enable_engine=False)
    wkt.start()
    
    # Play a move at (3, 3) - D4
    wkt("play", (3, 3))
    
    state = wkt.get_state()
    assert state["is_root"] is False
    assert state["last_move"] == [3, 3]
    assert state["player_to_move"] == "W"
    
    # Verify stone is on board
    stones = state["stones"]
    assert any(s[0] == "B" and s[1] == [3, 3] for s in stones)

def test_web_katrain_undo_redo():
    """Test undo and redo functionality."""
    wkt = WebKaTrain(force_package_config=True, enable_engine=False)
    wkt.start()
    
    wkt("play", (3, 3))
    assert wkt.get_state()["is_root"] is False
    
    wkt("undo")
    assert wkt.get_state()["is_root"] is True
    
    wkt("redo")
    assert wkt.get_state()["is_root"] is False
    assert wkt.get_state()["last_move"] == [3, 3]

if __name__ == "__main__":
    pytest.main([__file__])
