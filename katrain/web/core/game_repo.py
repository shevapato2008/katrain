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
        """Record a completed multiplayer game. Creates a UserGame record for each player.

        Returns the black player's game record (used as the canonical record for rating_history).
        """
        session = self.session_factory()
        try:
            import hashlib
            sgf_hash = hashlib.sha256(sgf_content.encode()).hexdigest() if sgf_content else None
            source = "play_human"

            # Create record for black player
            black_game = models_db.UserGame(
                user_id=black_id,
                sgf_content=sgf_content,
                source=source,
                sgf_hash=sgf_hash,
                player_black=black_name,
                player_white=white_name,
                result=result,
                game_type=game_type,
                category="game",
            )
            session.add(black_game)

            # Create record for white player
            white_game = models_db.UserGame(
                user_id=white_id,
                sgf_content=sgf_content,
                source=source,
                sgf_hash=sgf_hash,
                player_black=black_name,
                player_white=white_name,
                result=result,
                game_type=game_type,
                category="game",
            )
            session.add(white_game)
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
                                game_id=black_game.id,  # Both point to black's record
                            )
                            session.add(history)

            session.commit()
            session.refresh(black_game)
            return {
                "id": black_game.id,
                "result": black_game.result,
                "game_type": black_game.game_type,
            }
        finally:
            session.close()

    def count_completed_rated_games(self, user_id: int) -> int:
        """Count completed rated games for a user (for matchmaking prerequisite)."""
        session = self.session_factory()
        try:
            count = session.query(models_db.UserGame).filter(
                models_db.UserGame.user_id == user_id,
                models_db.UserGame.game_type == "rated",
                models_db.UserGame.result.isnot(None),
            ).count()
            return count
        finally:
            session.close()
