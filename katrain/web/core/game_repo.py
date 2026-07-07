"""Repository for multiplayer game recording and rating updates.

Uses the UserGame model (previously used the now-removed Game model).
"""

from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy.sql import func
from katrain.web.core import models_db
from katrain.web.core.ranking import calculate_rank_update


class GameRepository:
    """Handles multiplayer game end recording + rating calculation."""

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

        Returns the canonical game record (black's if present, else white's) used
        for rating_history.
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
            session.flush()  # Get IDs before rating calc

            # Handle rated game ranking
            if game_type == "rated":
                winner_color = result[0] if result and result[0] in ("B", "W") else None
                if winner_color:
                    winner_id = black_id if winner_color == "B" else white_id
                    for uid in [black_id, white_id]:
                        user = session.query(models_db.User).filter(models_db.User.id == uid).first()
                        if user:
                            old_rank = user.rank
                            won = winner_id == user.id
                            new_rank, new_net_wins, new_elo, elo_change = calculate_rank_update(
                                user.rank, user.net_wins, user.elo_points, won
                            )
                            user.rank = new_rank
                            user.net_wins = new_net_wins
                            user.elo_points = new_elo

                            history = models_db.RatingHistory(
                                user_id=user.id,
                                old_rank=old_rank,
                                new_rank=new_rank,
                                elo_change=elo_change,
                                game_id=canonical.id,  # canonical (black if present, else white)
                            )
                            session.add(history)

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

    def count_completed_rated_games(self, user_id: int) -> int:
        """Count completed rated games for a user (for matchmaking prerequisite)."""
        session = self.session_factory()
        try:
            count = (
                session.query(models_db.UserGame)
                .filter(
                    models_db.UserGame.user_id == user_id,
                    models_db.UserGame.game_type == "rated",
                    models_db.UserGame.result.isnot(None),
                )
                .count()
            )
            return count
        finally:
            session.close()
