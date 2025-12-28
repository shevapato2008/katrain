import multiprocessing
import threading
import json
import time
import pytest
from http.server import HTTPServer, BaseHTTPRequestHandler
from katrain.core.engine import KataGoHttpEngine
from katrain.core.base_katrain import KaTrainBase

# Mock KaTrain class
class MockKaTrain(KaTrainBase):
    def __init__(self):
        self.config_data = {
            "engine": {
                "backend": "http",
                "http_url": "http://127.0.0.1:8081",
                "max_visits": 10,
                "wide_root_noise": 0.0,
                "max_time": 10.0,
                "_enable_ownership": False
            }
        }
    
    def log(self, msg, level=None):
        pass

    def config(self, key):
        return self.config_data.get(key, {})

# Simple HTTP Server
class SimpleHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            content_length = int(self.headers["Content-Length"])
            self.rfile.read(content_length)
            
            # Simulate some processing time
            time.sleep(0.05)
            
            # Return a large-ish response to ensure pipe interaction
            # 1000 items should be enough to fill a standard pipe buffer if not handled correctly
            response = {
                "id": "test_id",
                "moveInfos": [{"move": "D4", "visits": 10}] * 1000, 
                "rootInfo": {"visits": 10, "winrate": 0.5},
                "isDuringSearch": False
            }
            
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(response).encode("utf-8"))
        except Exception as e:
            pass

    def log_message(self, format, *args):
        pass # Silence server logs

@pytest.fixture
def mock_server():
    stop_event = threading.Event()
    server = HTTPServer(("127.0.0.1", 8081), SimpleHandler)
    server.timeout = 0.1
    
    def run_server():
        while not stop_event.is_set():
            server.handle_request()
        server.server_close()

    server_thread = threading.Thread(target=run_server)
    server_thread.start()
    
    yield
    
    stop_event.set()
    server_thread.join()

def test_http_engine_subprocess_deadlock(mock_server):
    # Ensure spawning is used as in the app
    try:
        multiprocessing.set_start_method("spawn")
    except RuntimeError:
        pass

    katrain = MockKaTrain()
    engine = KataGoHttpEngine(katrain, katrain.config("engine"))
    
    try:
        payload = {"id": "test_id", "moves": []}
        
        # This calls the method that spawns the subprocess
        # If the deadlock exists, this will hang or timeout
        start_time = time.time()
        result = engine._post_json(payload)
        duration = time.time() - start_time
        
        assert "moveInfos" in result
        assert len(result["moveInfos"]) == 1000
        # Check that it did not take an unreasonably long time (indicating timeout fallback)
        assert duration < 5.0 
        
    finally:
        engine.shutdown(finish=False)
