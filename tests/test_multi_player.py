import threading
import uuid
import datetime
from katrain.core.base_katrain import KaTrainBase
from katrain.core.engine import KataGoHttpEngine
from katrain.core.game import Game
from katrain.core.utils import generate_id

def test_id_generation_formats():
    """Verify that ID generation follows the new prefixed standard."""
    game_id = generate_id("game")
    user_id = generate_id("user")
    
    assert game_id.startswith("game_")
    assert user_id.startswith("user_")
    
    # Check game_id format: game_YYYY-MM-DD...
    parts = game_id.split("_")
    assert len(parts) >= 3 # game, date string, uuid suffix
    
    # Check user_id format: user_<uuid>
    assert len(user_id.split("_")[1]) > 0

def test_game_id_propagation():
    katrain = KaTrainBase(force_package_config=True, debug_level=0)
    config = dict(katrain.config("engine"))
    config["backend"] = "http"
    config["http_url"] = "http://127.0.0.1:8000"
    
    # Create engine
    engine = KataGoHttpEngine(katrain, config)
    
    try:
        # Create game with this engine
        game = Game(katrain, engine)
        
        # Check game_id generation
        assert game.game_id.startswith("game_")
        # Verify it's set on the engine
        assert engine.game_id == game.game_id
        
        # Verify request payload contains gameId
        node = game.root
        
        seen = {}
        done = threading.Event()

        def fake_post_json(payload):
            seen["payload"] = payload
            board_squares = payload["boardXSize"] * payload["boardYSize"]
            return {
                "id": payload["id"],
                "moveInfos": [],
                "rootInfo": {"visits": 10, "winrate": 0.5, "scoreLead": 0.0},
                "ownership": [0.0] * board_squares,
                "policy": [1.0 / (board_squares + 1)] * (board_squares + 1),
            }

        engine._post_json = fake_post_json

        def callback(result, partial_result):
            done.set()

        engine.request_analysis(node, callback)
        assert done.wait(2)

        payload = seen["payload"]
        assert "gameId" in payload
        assert payload["gameId"] == game.game_id
        
    finally:
        engine.shutdown(finish=False)

def test_user_id_propagation():
    katrain = KaTrainBase(force_package_config=True, debug_level=0)
    config = dict(katrain.config("engine"))
    config["backend"] = "http"
    config["http_url"] = "http://127.0.0.1:8000"
    
    engine = KataGoHttpEngine(katrain, config)
    test_user_id = generate_id("user")
    
    try:
        # Create game with explicit user_id
        game = Game(katrain, engine, user_id=test_user_id)
        
        # Verify it's set on the engine
        assert engine.user_id == test_user_id
        
        # Verify request payload contains userId
        node = game.root
        
        seen = {}
        done = threading.Event()

        def fake_post_json(payload):
            seen["payload"] = payload
            board_squares = payload["boardXSize"] * payload["boardYSize"]
            return {
                "id": payload["id"],
                "moveInfos": [],
                "rootInfo": {"visits": 10, "winrate": 0.5, "scoreLead": 0.0},
                "ownership": [0.0] * board_squares,
                "policy": [1.0 / (board_squares + 1)] * (board_squares + 1),
            }

        engine._post_json = fake_post_json

        def callback(result, partial_result):
            done.set()

        engine.request_analysis(node, callback)
        assert done.wait(2)

        payload = seen["payload"]
        assert "userId" in payload
        assert payload["userId"] == test_user_id
        assert "gameId" in payload # Should have both
        
    finally:
        engine.shutdown(finish=False)

def test_unique_game_ids():
    katrain = KaTrainBase(force_package_config=True, debug_level=0)
    config = dict(katrain.config("engine"))
    config["backend"] = "http"
    engine1 = KataGoHttpEngine(katrain, config)
    engine2 = KataGoHttpEngine(katrain, config)
    
    try:
        game1 = Game(katrain, engine1)
        game2 = Game(katrain, engine2)
        
        assert game1.game_id != game2.game_id
        assert game1.game_id.startswith("game_")
        assert game2.game_id.startswith("game_")
        assert engine1.game_id == game1.game_id
        assert engine2.game_id == game2.game_id
    finally:
        engine1.shutdown(finish=False)
        engine2.shutdown(finish=False)