import threading

from katrain.core.base_katrain import KaTrainBase
from katrain.core.engine import KataGoHttpEngine
from katrain.core.game import BaseGame
from katrain.core.sgf_parser import Move


def test_http_engine_request_payload():
    katrain = KaTrainBase(force_package_config=True, debug_level=0)
    config = dict(katrain.config("engine"))
    config["backend"] = "http"
    config["http_url"] = "http://127.0.0.1:8000"
    engine = KataGoHttpEngine(katrain, config)
    try:
        game = BaseGame(katrain, bypass_config=True)
        game.play(Move.from_gtp("D4", player="B"))
        node = game.play(Move.from_gtp("Q4", player="W"))

        seen = {}
        done = threading.Event()

        def fake_post_json(payload):
            seen["payload"] = payload
            board_squares = payload["boardXSize"] * payload["boardYSize"]
            return {
                "id": payload["id"],
                "moveInfos": [
                    {"move": "D4", "order": 0, "visits": 10, "winrate": 0.5, "scoreLead": 0.0, "pv": ["D4"]}
                ],
                "rootInfo": {"visits": 10, "winrate": 0.5, "scoreLead": 0.0},
                "ownership": [0.0] * board_squares,
                "policy": [1.0 / (board_squares + 1)] * (board_squares + 1),
            }

        engine._post_json = fake_post_json

        def callback(result, partial_result):
            seen["result"] = result
            seen["partial"] = partial_result
            done.set()

        engine.request_analysis(node, callback)
        assert done.wait(2)

        payload = seen["payload"]
        assert payload["moves"] == [["B", "D4"], ["W", "Q4"]]
        assert payload["initialStones"] == []
        assert payload["rules"] == "japanese"
        assert payload["boardXSize"] == 19
        assert payload["overrideSettings"]["reportAnalysisWinratesAs"] == "BLACK"
        assert seen["result"]["id"] == payload["id"]
        assert node.analysis_visits_requested == config["max_visits"]
        assert seen["partial"] is False
    finally:
        engine.shutdown(finish=False)
