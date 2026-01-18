import time
import pytest
from katrain.web.interface import WebKaTrain, NullEngine
from katrain.core.constants import MODE_PLAY

class MockEngine(NullEngine):
    def request_analysis(self, *args, **kwargs):
        pass

def test_timer_logic_parity():
    # Setup WebKaTrain with manual control
    katrain = WebKaTrain(force_package_config=True, enable_engine=False)
    katrain.engine = MockEngine()
    
    # Configure timer: 1 min main, 30s byoyomi, 5 periods
    katrain._config["timer"] = {
        "main_time": 1,
        "byo_length": 30,
        "byo_periods": 5,
        "minimal_use": 0,
        "sound": True
    }
    
    katrain._do_new_game(size=19)
    katrain.timer_paused = False
    katrain.play_analyze_mode = MODE_PLAY
    # Ensure next player is human
    katrain.next_player_info.player_type = "player:human"
    
    # Reset baseline for test
    katrain.last_timer_update = time.time()

    # Initial state
    current_player = katrain.next_player_info.player
    assert katrain.main_time_used_by_player[current_player] == 0
    assert katrain.game.current_node.time_used == 0
    assert katrain.next_player_info.periods_used == 0
    
    # 1. Main time consumption
    katrain.last_timer_update = time.time() - 10 # 10 seconds ago
    katrain.update_timer()
    assert katrain.main_time_used_by_player[current_player] == pytest.approx(10, abs=0.1)
    assert katrain.game.current_node.time_used == 0
    
    # 2. Transition to Byoyomi (exhaust 60s main time)
    katrain.main_time_used_by_player[current_player] = 55
    katrain.last_timer_update = time.time() - 10 # 10 seconds ago (5s main, 5s byo)
    katrain.update_timer()
    
    assert katrain.main_time_used_by_player[current_player] == 60
    assert katrain.game.current_node.time_used == pytest.approx(5, abs=0.1)
    assert katrain.next_player_info.periods_used == 0
    
    # 3. Period decrement
    katrain.game.current_node.time_used = 25
    katrain.last_timer_update = time.time() - 10 # 10 seconds ago (5s left in period, 5s into next)
    katrain.update_timer()
    
    # After 35s total in byoyomi (25+10):
    # Period 1 (30s) consumed -> 1 period used
    # Remaining 5s in next period
    assert katrain.next_player_info.periods_used == 1
    assert katrain.game.current_node.time_used == pytest.approx(5, abs=0.1)

    # 4. Multiple periods at once
    katrain.game.current_node.time_used = 0
    katrain.last_timer_update = time.time() - 70 # 70 seconds ago (2 periods of 30s + 10s)
    katrain.update_timer()
    
    # 1 (prev) + 2 consumed = 3 periods used
    # 10s into the next period
    assert katrain.next_player_info.periods_used == 3
    assert katrain.game.current_node.time_used == pytest.approx(10, abs=0.1)

def test_timer_reset_on_move():
    katrain = WebKaTrain(force_package_config=True, enable_engine=False)
    katrain.engine = MockEngine()
    katrain._config["timer"] = {"main_time": 0, "byo_length": 30, "byo_periods": 5}
    katrain._do_new_game()
    katrain.timer_paused = False
    katrain.play_analyze_mode = MODE_PLAY
    katrain.next_player_info.player_type = "player:human"
    
    # Reset baseline
    katrain.last_timer_update = time.time()

    # Consume some time
    katrain.last_timer_update = time.time() - 10
    katrain.update_timer()
    assert katrain.game.current_node.time_used == pytest.approx(10, abs=0.1)
    
    # Play a move (disable analysis to avoid background threads)
    katrain.game.play = lambda move, ignore_ko=False, analyze=False: super(type(katrain.game), katrain.game).play(move, ignore_ko=ignore_ko, analyze=False)
    katrain._do_play((3, 3))
    
    # New node should have 0 time used
    assert katrain.game.current_node.time_used == 0
    # last_timer_update should be reset to 'now'
    assert time.time() - katrain.last_timer_update < 0.5

if __name__ == "__main__":
    test_timer_logic_parity()
    test_timer_reset_on_move()
    print("Tests passed!")
