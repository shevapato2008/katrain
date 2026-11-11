"""E18 restoration and the next physical move against a real local game/session.

Run separately from suites that replace katrain.web.interface in sys.modules.
Only the camera/worker and browser socket are simulated; publication, recovery,
HTTP refresh, turn guards, and the committed game tree use their real runtime.
"""

import asyncio
from collections import deque
from copy import deepcopy
import logging
from types import SimpleNamespace

import httpx
import numpy as np

from katrain.core.constants import PLAYER_HUMAN
from katrain.core.sgf_parser import Move
from katrain.vision.config_service import VisionServiceConfig
from katrain.vision.ipc import CommandType, ConfirmedMove, WorkerStatus
from katrain.vision.service import VisionService
from katrain.vision.sync import game_state_stones_to_board
from katrain.web.api.v1.endpoints.auth import get_current_user_optional
from katrain.web.core.config import settings
from katrain.web.core.physical_play import PhysicalPlayConfig
from katrain.web.core.physical_play_orchestrator import PhysicalPlayOrchestrator
from katrain.web.interface import WebKaTrain
from katrain.web.server import _handle_confirmed_move, create_app
from katrain.web.session import WebSession


class ObservedWorker:
    def __init__(self, board):
        self.commands = []
        self.events = deque()
        self.recovery_commands = asyncio.Queue()
        self.status = WorkerStatus(detected_board=board, observation_seq=10)

    def send_command(self, command):
        self.commands.append(command)
        if command.action == CommandType.SET_EXPECTED_BOARD and command.data.get("recovery_id"):
            self.recovery_commands.put_nowait(command)

    def observe(self, board, sequence, expected=None):
        self.status = WorkerStatus(detected_board=board, observation_seq=sequence)
        if expected is not None:
            assert np.array_equal(board, expected.data["board"])
            self.events.append(
                {
                    "type": "synced",
                    "binding_epoch": expected.data["binding_epoch"],
                    "expected_revision": expected.data["expected_revision"],
                    "data": {
                        "expected_node_id": expected.data["expected_node_id"],
                        "recovery_id": expected.data["recovery_id"],
                    },
                }
            )

    def get_status(self):
        return self.status

    def get_event(self):
        return self.events.popleft() if self.events else None


class ProjectedSocket:
    def __init__(self):
        self.state = None
        self.received = []
        self.nodes = {}

    async def send_json(self, payload):
        if payload["type"] == "game_update":
            self.state = deepcopy(payload["state"])
            self.received.append(self.state)
            self.nodes.setdefault(self.state["current_node_id"], asyncio.Event()).set()

    async def wait_for_node(self, node):
        await asyncio.wait_for(self.nodes.setdefault(id(node), asyncio.Event()).wait(), 1)


def test_restoring_existing_white_e18_publishes_16_then_accepts_black_17_once(monkeypatch):
    async def run():
        # These overrides belong only to this fixture; no lifespan, DB, camera,
        # model, or remote engine starts when exercising the in-process routes.
        monkeypatch.setattr(settings, "KATRAIN_BOX_SSO", False)
        app = create_app(enable_engine=False)
        app.dependency_overrides[get_current_user_optional] = lambda: SimpleNamespace(id=10, username="owner")
        manager = app.state.session_manager
        manager.attach_loop(asyncio.get_running_loop())
        runtime = WebKaTrain(force_package_config=True, enable_engine=False)
        runtime.save_config = lambda *_args, **_kwargs: None
        runtime.start()
        for color in ("B", "W"):
            runtime.players_info[color].update(player_type=PLAYER_HUMAN)
        for index in range(15):
            runtime.game.play(Move((index, 0), player="B" if index % 2 == 0 else "W"), analyze=False)
        node15 = runtime.game.current_node
        stale15 = runtime.get_state()
        node16 = runtime.game.play(Move((4, 17), player="W"), analyze=False)
        assert node16.depth == 16 and node16.move.gtp() == "E18"
        assert runtime.next_player_to_move() == "B"
        live16 = runtime.get_state()
        session = WebSession(session_id="e18", katrain=runtime, user_id=10, last_state=stale15)
        manager._sessions[session.session_id] = session
        runtime.update_state_callback = lambda state: manager._on_state(session.session_id, state)
        runtime.message_callback = lambda kind, data: manager._on_message(session.session_id, kind, data)
        ui = ProjectedSocket()
        session.sockets.add(ui)
        manager._on_state(session.session_id, stale15)
        await ui.wait_for_node(node15)
        assert ui.state["current_node_index"] == 15 and ui.state["player_to_move"] == "W"

        vision = VisionService(VisionServiceConfig())
        worker = vision._worker = ObservedWorker(game_state_stones_to_board(stale15["stones"], 19).tolist())
        vision.bind_session(session.session_id, session=session)
        orch = PhysicalPlayOrchestrator(config=PhysicalPlayConfig(), led=None, vision=vision, session_manager=manager)
        app.state.vision, app.state.physical_play = vision, orch
        orch.on_bind(session.session_id, session)
        # Keep this scenario event-driven; it does not need the periodic LED tick.
        orch._task.cancel()
        orch._latest_state = stale15
        plays = []
        real_play = runtime.game.play

        def record_play(move, *args, **kwargs):
            plays.append((move.player, move.coords))
            return real_play(move, *args, **kwargs)

        monkeypatch.setattr(runtime.game, "play", record_play)
        restored_board = game_state_stones_to_board(live16["stones"], 19).tolist()
        worker.observe(restored_board, 11)  # the existing White E18 is physically restored
        recovery = None
        try:
            recovery = asyncio.create_task(orch.restore_scoped(session.session_id, live16["game_id"], timeout=1))
            expected = await asyncio.wait_for(worker.recovery_commands.get(), 1)
            await ui.wait_for_node(node16)
            assert expected.data["expected_node_id"] == id(node16)
            assert expected.data["board"][1][4] == 2
            assert session.last_state["current_node_index"] == ui.state["current_node_index"] == 16
            assert session.last_state["player_to_move"] == ui.state["player_to_move"] == "B"
            assert runtime.game.current_node is node16 and plays == []
            assert not recovery.done()  # publication and a restored board alone are insufficient

            worker.observe(restored_board, 12, expected=expected)
            assert vision.poll_events()[0]["type"] == "synced"
            result = await asyncio.wait_for(recovery, 1)
            assert result == {
                "ok": True,
                "recovery_id": expected.data["recovery_id"],
                "session_id": session.session_id,
                "game_id": live16["game_id"],
                "current_node_id": id(node16),
            }
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
                response = await client.get("/api/state", params={"session_id": session.session_id})
            assert response.status_code == 200
            refreshed = response.json()["state"]
            assert refreshed["current_node_id"] == id(node16)
            assert refreshed["current_node_index"] == 16 and refreshed["player_to_move"] == "B"

            black17 = deepcopy(restored_board)
            black17[1][5] = 1
            worker.observe(black17, 13)
            confirmation = ConfirmedMove(5, 1, 1, 13, vision.binding_epoch, vision.expected_revision)
            worker.events.append(confirmation)
            assert vision.get_confirmed_move() is confirmation
            runtime._last_broadcast_time = 0  # next real publication need not use the throttle timer
            delay = await _handle_confirmed_move(
                app, vision, session.session_id, confirmation, logging.getLogger(__name__)
            )
            node17 = runtime.game.current_node
            await ui.wait_for_node(node17)
            assert delay == 0.0 and node17.parent is node16 and node17.depth == 17
            assert plays == [("B", (5, 17))]
            assert node16.move.player == "W" and node16.move.gtp() == "E18"
            assert session.last_state["current_node_index"] == ui.state["current_node_index"] == 17
            assert [state["current_node_index"] for state in ui.received] == [15, 16, 17]
            assert worker.commands[-1].action == CommandType.RELEASE_CONFIRMED_MOVE
            assert worker.commands[-1].data == {"token": confirmation.token}
            assert all(command.action != CommandType.RESET_SYNC for command in worker.commands)
        finally:
            if recovery is not None and not recovery.done():
                recovery.cancel()
                await asyncio.gather(recovery, return_exceptions=True)
            await orch.shutdown()
            runtime.shutdown()

    asyncio.run(run())
