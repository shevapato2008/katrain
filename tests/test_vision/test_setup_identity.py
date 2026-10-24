import numpy as np

from katrain.vision.sync import SyncEventType, SyncStateMachine


def test_setup_identity_changes_and_legacy_remains_untagged():
    sync = SyncStateMachine()
    target = np.zeros((19, 19), dtype=int)
    target[0, 0] = 1
    sync.enter_setup_mode(target, setup_id="old")
    assert sync.update(np.zeros_like(target))[0].data["setup_id"] == "old"
    sync.enter_setup_mode(target, setup_id="new")
    events = sync.update(target)
    assert [e.type for e in events] == [SyncEventType.SETUP_PROGRESS, SyncEventType.SETUP_COMPLETE]
    assert all(e.data["setup_id"] == "new" for e in events)
    sync.enter_setup_mode(target)
    assert all("setup_id" not in e.data for e in sync.update(target))


def test_service_forwards_optional_setup_identity():
    from unittest.mock import Mock
    from katrain.vision.config_service import VisionServiceConfig
    from katrain.vision.service import VisionService

    service = VisionService(VisionServiceConfig())
    service._worker = Mock()
    board = np.zeros((19, 19), dtype=int)
    for setup_id in ("clear-1", "place-2", None):
        service.enter_setup_mode(board, setup_id=setup_id)
        data = service._worker.send_command.call_args.args[0].data
        assert data == {"target_board": board.tolist(), **({"setup_id": setup_id} if setup_id is not None else {})}
