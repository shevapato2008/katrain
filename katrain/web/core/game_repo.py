"""Repository for multiplayer game recording.

Uses the UserGame model (previously used the now-removed Game model).

Human-vs-human results DO NOT move a rank. A player has exactly one rank and it is
defined by their 升降级对弈 games against the 41-tier ladder; see
katrain/web/core/ladder_repo.py and WebKaTrain.RANK_MOVING_GAME_TYPES. The old
Elo/net-win update that used to run here (katrain/web/core/ranking.py) is gone --
keeping it would have meant two rank systems writing the same `users.rank` column,
which is what made the rated-PvP prerequisite unreachable in the first place.
"""

from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy.sql import func
from katrain.web.core import models_db


class GameRepository:
    """Handles multiplayer game end recording."""

    def __init__(self, session_factory):
        self.session_factory = session_factory

    def record_multiplayer_game(
        self,
        sgf_content: str,
        result: str,
        game_type: str,
        black_id: int,
        white_id: int,
        black_name: str = "",
        white_name: str = "",
    ) -> Dict[str, Any]:
        """Record a completed multiplayer game. Creates a UserGame record for each REAL player.

        Synthetic opponents (e.g. the engine AI, recorded with a non-positive id
        like -1) have no `users` row -- creating a UserGame for them would raise a
        ForeignKeyViolation and roll back the whole transaction (losing the human's
        record too). Such players are skipped; only real (id > 0) players get a row.

        Returns the canonical game record (black's if present, else white's).
        """
        session = self.session_factory()
        try:
            import hashlib

            sgf_hash = hashlib.sha256(sgf_content.encode()).hexdigest() if sgf_content else None
            source = "play_human"

            def _make_game(user_id):
                game = models_db.UserGame(
                    user_id=user_id,
                    sgf_content=sgf_content,
                    source=source,
                    sgf_hash=sgf_hash,
                    player_black=black_name,
                    player_white=white_name,
                    result=result,
                    game_type=game_type,
                    category="game",
                )
                session.add(game)
                return game

            # Only real users get a UserGame row; skip synthetic opponents (id <= 0).
            black_game = _make_game(black_id) if black_id > 0 else None
            white_game = _make_game(white_id) if white_id > 0 else None
            canonical = black_game or white_game
            session.flush()

            # No rank update here, deliberately. A rated human-vs-human game is a
            # scoring game for anti-cheat purposes (no analysis, no undo) but it does
            # not move anybody's rank -- only 升降级对弈 against the ladder does.
            session.commit()
            if canonical is None:
                # No real players (shouldn't happen) -- nothing was recorded.
                return {"id": None, "result": result, "game_type": game_type}
            session.refresh(canonical)
            return {
                "id": canonical.id,
                "result": canonical.result,
                "game_type": canonical.game_type,
            }
        finally:
            session.close()

    def count_completed_ladder_games(self, user_id: int) -> int:
        """Completed 升降级对弈 games. Informational only -- the rated-PvP prerequisite
        is `has_completed_placement`, which reads the rank rather than counting rows."""
        session = self.session_factory()
        try:
            from katrain.web.core.ladder_repo import LADDER_GAME_TYPE

            return (
                session.query(models_db.UserGame)
                .filter(
                    models_db.UserGame.user_id == user_id,
                    models_db.UserGame.game_type == LADDER_GAME_TYPE,
                    models_db.UserGame.result.isnot(None),
                )
                .count()
            )
        finally:
            session.close()
