"""
Integrates vision detection pipeline with KaTrain's game session.

Submits confirmed moves to the active game session via the same interface
used by web/desktop UI (session.katrain("play", coords)).
"""

from katrain.core.sgf_parser import Move


class VisionPlayerBridge:
    """Submits vision-detected moves to a KaTrain game session."""

    def __init__(self, session):
        self.session = session
        self.last_submitted_move: Move | None = None

    def submit_move(self, move: Move | None) -> bool:
        """
        Submit a confirmed move to the game session.

        Returns True if the move was submitted, False if skipped (None or duplicate).
        """
        if move is None:
            return False
        if self.last_submitted_move is not None and move == self.last_submitted_move:
            return False

        self.session.katrain("play", move.coords)
        self.last_submitted_move = move
        return True
