import pytest
import requests
import time

BASE_URL = "http://localhost:8001"

@pytest.fixture(scope="module")
def session():
    # Ensure server is running (assumes it's started externally or handled by pytest-xprocess etc.)
    # For now, just try to create a session
    resp = requests.post(f"{BASE_URL}/api/session")
    assert resp.status_code == 200
    data = resp.json()
    return data["session_id"]

def test_move_and_undo(session):
    # Play a move
    resp = requests.post(f"{BASE_URL}/api/move", json={"session_id": session, "coords": [3, 3]})
    assert resp.status_code == 200
    state = resp.json()["state"]
    assert len(state["stones"]) > 0
    
    # Undo
    resp = requests.post(f"{BASE_URL}/api/undo", json={"session_id": session})
    assert resp.status_code == 200
    state = resp.json()["state"]
    assert len(state["stones"]) == 0

def test_navigation(session):
    # Play 2 moves
    requests.post(f"{BASE_URL}/api/move", json={"session_id": session, "coords": [3, 3]})
    resp = requests.post(f"{BASE_URL}/api/move", json={"session_id": session, "coords": [15, 15]})
    state = resp.json()["state"]
    history = state["history"]
    assert len(history) == 3 # root + 2 moves
    
    node_id = history[1]["node_id"]
    resp = requests.post(f"{BASE_URL}/api/nav", json={"session_id": session, "node_id": node_id})
    assert resp.status_code == 200
    assert resp.json()["state"]["current_node_id"] == node_id

def test_ui_toggles(session):
    resp = requests.post(f"{BASE_URL}/api/ui/toggle", json={"session_id": session, "setting": "coordinates"})
    assert resp.status_code == 200
    state = resp.json()["state"]
    assert "ui_state" in state
    
    # Toggle Zen Mode
    resp = requests.post(f"{BASE_URL}/api/ui/toggle", json={"session_id": session, "setting": "zen_mode"})
    assert resp.status_code == 200
    assert resp.json()["state"]["ui_state"]["zen_mode"] == True

def test_node_actions(session):
    # Setup: 2 moves
    requests.post(f"{BASE_URL}/api/new-game", json={"session_id": session})
    requests.post(f"{BASE_URL}/api/move", json={"session_id": session, "coords": [3, 3]})
    requests.post(f"{BASE_URL}/api/move", json={"session_id": session, "coords": [15, 15]})
    
    # Delete current node
    resp = requests.post(f"{BASE_URL}/api/node/delete", json={"session_id": session})
    assert resp.status_code == 200
    state = resp.json()["state"]
    assert len(state["history"]) == 2 # root + 1 move
    
def test_language_and_theme(session):
    resp = requests.post(f"{BASE_URL}/api/language", json={"session_id": session, "lang": "fr"})
    assert resp.status_code == 200
    assert resp.json()["language"] == "fr"
    
    resp = requests.post(f"{BASE_URL}/api/theme", json={"session_id": session, "theme": "theme:red-green-colourblind"})
    assert resp.status_code == 200
    assert resp.json()["theme"] == "theme:red-green-colourblind"

def test_timer(session):
    resp = requests.post(f"{BASE_URL}/api/timer/pause", json={"session_id": session})
    assert resp.status_code == 200
    assert resp.json()["paused"] == False # toggled from True (default in WebKaTrain init for now)
    
def test_analysis_actions(session):
    # Extra analysis
    resp = requests.post(f"{BASE_URL}/api/analysis/extra", json={"session_id": session, "mode": "extra"})
    assert resp.status_code == 200
    
    # Game analysis
    resp = requests.post(f"{BASE_URL}/api/analysis/game", json={"session_id": session, "visits": 10})
    assert resp.status_code == 200
    
    # Report
    resp = requests.post(f"{BASE_URL}/api/analysis/report", json={"session_id": session})
    assert resp.status_code == 200
    assert "report" in resp.json()

if __name__ == "__main__":
    # Simple manual run
    s_id = requests.post(f"{BASE_URL}/api/session").json()["session_id"]
    test_move_and_undo(s_id)
    print("Tests passed!")
