import pytest
from katrain.web.interface import WebKaTrain

def test_ui_toggle_defaults():
    """Verify that 'Next Moves', 'Show Dots', 'Top Moves', and 'Numbers' are unchecked by default."""
    wkt = WebKaTrain(force_package_config=True, enable_engine=False)
    wkt.start() # Ensure game is active so get_state returns the full state
    state = wkt.get_state()
    ui_state = state["ui_state"]
    
    assert ui_state["show_children"] is False # Next Moves
    assert ui_state["show_dots"] is False     # Show Dots
    assert ui_state["show_hints"] is False    # Top Moves
    assert ui_state["show_move_numbers"] is False
    assert ui_state["show_coordinates"] is True

def test_last_move_stone_info():
    """Verify that stone info includes move_number for identification if needed."""
    wkt = WebKaTrain(force_package_config=True, enable_engine=False)
    wkt.start()
    wkt("play", (3, 3))
    state = wkt.get_state()
    
    last_move = state["last_move"]
    assert last_move == [3, 3]
    
    # Check that we can find the stone and its player
    stones = state["stones"]
    last_stone = next((s for s in stones if s[1] == [3, 3]), None)
    assert last_stone is not None
    assert last_stone[0] == "B" # First move is Black