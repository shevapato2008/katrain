import requests
import json
import time
import sys
import multiprocessing
import threading
from katrain.core.engine import KataGoHttpEngine
from katrain.core.base_katrain import KaTrainBase

URL = "http://127.0.0.1:8000/analyze"

PAYLOAD1 = {
    "rules": "japanese", "priority": -99, "analyzeTurns": [0], "maxVisits": 25, "komi": 6.5, 
    "boardXSize": 19, "boardYSize": 19, "includeOwnership": True, "includeMovesOwnership": True, 
    "includePolicy": True, "initialStones": [], "initialPlayer": "B", "moves": [], 
    "overrideSettings": {"reportAnalysisWinratesAs": "BLACK", "wideRootNoise": 0.04, "maxTime": 8.0}, 
    "reportDuringSearchEvery": 1, "id": "HTTP:1"
}

PAYLOAD2 = {
    "rules": "japanese", "priority": 1001, "analyzeTurns": [1], "maxVisits": 100, "komi": 6.5, 
    "boardXSize": 19, "boardYSize": 19, "includeOwnership": True, "includeMovesOwnership": True, 
    "includePolicy": True, "initialStones": [], "initialPlayer": "B", "moves": [["B", "D16"]], 
    "overrideSettings": {"reportAnalysisWinratesAs": "BLACK", "wideRootNoise": 0.04, "maxTime": 8.0}, 
    "reportDuringSearchEvery": 1, "id": "HTTP:2"
}

def test_direct_requests():
    print("--- Testing Direct Requests ---")
    try:
        print(f"Sending Query 1 to {URL}")
        t0 = time.time()
        resp = requests.post(URL, json=PAYLOAD1, timeout=10)
        dt = time.time() - t0
        print(f"Query 1 finished in {dt:.2f}s. Status: {resp.status_code}")
        print(f"Content Length: {len(resp.content)} bytes")
        if resp.status_code == 200:
            data = resp.json()
            print(f"Moves found: {len(data.get('moveInfos', []))}")
        else:
            print(f"Error: {resp.text}")

        print(f"Sending Query 2 to {URL}")
        t0 = time.time()
        resp = requests.post(URL, json=PAYLOAD2, timeout=10)
        dt = time.time() - t0
        print(f"Query 2 finished in {dt:.2f}s. Status: {resp.status_code}")
        print(f"Content Length: {len(resp.content)} bytes")
        if resp.status_code == 200:
            data = resp.json()
            print(f"Moves found: {len(data.get('moveInfos', []))}")
        else:
            print(f"Error: {resp.text}")
            
    except Exception as e:
        print(f"DIRECT REQUEST FAILED: {e}")
        sys.exit(1)

class MockKaTrain(KaTrainBase):
    def __init__(self):
        self.config_data = {
            "engine": {
                "backend": "http",
                "http_url": "http://127.0.0.1:8000",
                "max_visits": 100,
                "wide_root_noise": 0.0,
                "max_time": 10.0,
                "http_timeout": 15.0,
                "_enable_ownership": True
            }
        }
    
    def log(self, msg, level=None):
        print(f"[LOG] {msg}")
        sys.stdout.flush()

    def config(self, key):
        return self.config_data.get(key, {})

    def update_state(self):
        pass

def test_engine_integration():
    print("--- Testing Engine Integration ---")
    try:
        multiprocessing.set_start_method("spawn")
    except RuntimeError:
        pass

    katrain = MockKaTrain()
    engine = KataGoHttpEngine(katrain, katrain.config("engine"))
    
    try:
        def callback(result, partial):
            print(f"CALLBACK: Received for {result.get('id')}")
            sys.stdout.flush()

        print("Sending Query 1 via Engine")
        engine.send_query(PAYLOAD1, callback, None)
        time.sleep(2)

        print("Sending Query 2 via Engine")
        engine.send_query(PAYLOAD2, callback, None)
        time.sleep(5)
    except Exception as e:
         print(f"ENGINE TEST FAILED: {e}")
    finally:
        engine.shutdown(finish=False)

if __name__ == "__main__":
    test_direct_requests()
    test_engine_integration()
