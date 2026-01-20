import pytest
from katrain.web.session import Matchmaker

class MockWebSocket:
    def __init__(self, user_id):
        self.user_id = user_id
        self.sent_messages = []
    async def send_json(self, msg):
        self.sent_messages.append(msg)

@pytest.mark.asyncio
async def test_matchmaker_finds_match():
    mm = Matchmaker()
    ws1 = MockWebSocket(1)
    ws2 = MockWebSocket(2)
    
    # User 1 starts matchmaking
    mm.add_to_queue(1, "rated", ws1)
    assert len(mm._queues["rated"]) == 1
    
    # User 2 starts matchmaking
    match = mm.add_to_queue(2, "rated", ws2)
    
    # Should find match
    assert match is not None
    assert {match.player1_id, match.player2_id} == {1, 2}
    assert len(mm._queues["rated"]) == 0

@pytest.mark.asyncio
async def test_matchmaker_different_types():
    mm = Matchmaker()
    ws1 = MockWebSocket(1)
    ws2 = MockWebSocket(2)
    
    mm.add_to_queue(1, "rated", ws1)
    match = mm.add_to_queue(2, "free", ws2)
    
    # Should NOT find match (different types)
    assert match is None
    assert len(mm._queues["rated"]) == 1
    assert len(mm._queues["free"]) == 1
