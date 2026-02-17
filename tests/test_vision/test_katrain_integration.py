import pytest
from unittest.mock import MagicMock, patch
from katrain.core.sgf_parser import Move
from katrain.vision.katrain_integration import VisionPlayerBridge


class TestVisionPlayerBridge:
    def test_submits_move_to_session(self):
        mock_session = MagicMock()
        bridge = VisionPlayerBridge(session=mock_session)

        move = Move(coords=(3, 3), player="B")
        bridge.submit_move(move)

        mock_session.katrain.assert_called_once_with("play", (3, 3))

    def test_ignores_none_move(self):
        mock_session = MagicMock()
        bridge = VisionPlayerBridge(session=mock_session)

        bridge.submit_move(None)
        mock_session.katrain.assert_not_called()

    def test_duplicate_move_rejected(self):
        mock_session = MagicMock()
        bridge = VisionPlayerBridge(session=mock_session)

        move = Move(coords=(3, 3), player="B")
        bridge.submit_move(move)
        bridge.submit_move(move)  # duplicate

        assert mock_session.katrain.call_count == 1
