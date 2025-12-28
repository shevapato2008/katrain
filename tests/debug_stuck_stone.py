import multiprocessing
import threading
import json
import time
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler
from katrain.core.engine import KataGoHttpEngine
from katrain.core.base_katrain import KaTrainBase

class MockKaTrain(KaTrainBase):
    def __init__(self):
        self.config_data = {
            "engine": {
                "backend": "http",
                "http_url": "http://127.0.0.1:8082",
                "max_visits": 10,
                "wide_root_noise": 0.0,
                "max_time": 5.0,
                "http_timeout": 5.0,
                "_enable_ownership": False
            }
        }
    
    def log(self, msg, level=None):
        print(f"[LOG] {msg}")
        sys.stdout.flush()

    def config(self, key):
        return self.config_data.get(key, {})

    def update_state(self):
        pass

class SimpleHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            content_length = int(self.headers["Content-Length"])
            body = self.rfile.read(content_length)
            data = json.loads(body)
            print(f"SERVER: Received request {data.get('id')}")
            sys.stdout.flush()
            
            time.sleep(0.1)
            
            response = {
                "id": data.get('id'),
                "moveInfos": [{"move": "D4", "visits": 10}] * 10, 
                "rootInfo": {"visits": 10, "winrate": 0.5},
                "isDuringSearch": False
            }
            
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(response).encode("utf-8"))
        except Exception as e:
            print(f"SERVER ERROR: {e}")
            sys.stdout.flush()

    def log_message(self, format, *args):
        pass

def run_server(stop_event):
    server = HTTPServer(("127.0.0.1", 8082), SimpleHandler)
    server.timeout = 0.1
    while not stop_event.is_set():
        server.handle_request()
    server.server_close()

def test_sequence():
    try:
        multiprocessing.set_start_method("spawn")
    except RuntimeError:
        pass

    print("Starting server...")
    stop_event = threading.Event()
    server_thread = threading.Thread(target=run_server, args=(stop_event,))
    server_thread.start()
    time.sleep(1)

    katrain = MockKaTrain()
    # Engine starts its thread in __init__
    engine = KataGoHttpEngine(katrain, katrain.config("engine"))
    
    try:
        def callback(result, partial):
            print(f"TEST: Callback received for {result.get('id')}")
            sys.stdout.flush()

        # Query 1
        print("Sending Query 1 via queue")
        payload1 = {"id": "HTTP:1", "moves": [], "maxVisits": 1}
        engine.send_query(payload1, callback, None)
        
        time.sleep(2)
        
        # Query 2
        print("Sending Query 2 via queue")
        payload2 = {"id": "HTTP:2", "moves": [["B", "D4"]], "maxVisits": 1}
        engine.send_query(payload2, callback, None)
        
        time.sleep(2)
        
    finally:
        engine.shutdown(finish=False)
        stop_event.set()
        server_thread.join()

if __name__ == "__main__":
    test_sequence()
