from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy.sql import func
from katrain.web.core import models_db
from katrain.web.core.ranking import calculate_rank_update

class GameRepository:
    def __init__(self, session_factory):
        self.session_factory = session_factory

    def create_game(self, user_id: int, sgf_content: str, result: str, game_type: str, black_id: int = None, white_id: int = None) -> Dict[str, Any]:
        session = self.session_factory()
        try:
            db_game = models_db.Game(
                black_player_id=black_id or user_id,
                white_player_id=white_id,
                sgf_content=sgf_content,
                result=result,
                game_type=game_type
            )
            session.add(db_game)
            session.commit()
            session.refresh(db_game)
            return self._to_dict(db_game)
        finally:
            session.close()

    def update_game_result(self, game_id: int, result: str, winner_id: int = None) -> Dict[str, Any]:
        session = self.session_factory()
        try:
            db_game = session.query(models_db.Game).filter(models_db.Game.id == game_id).first()
            if not db_game:
                raise ValueError("Game not found")
            
            db_game.result = result
            db_game.winner_id = winner_id
            db_game.ended_at = func.now()
            
            if db_game.game_type == "rated":
                # Find the human user
                # For now, we assume black_player_id or white_player_id is the user
                # We update for the one that is NOT null and is a valid user
                for uid in [db_game.black_player_id, db_game.white_player_id]:
                    if not uid: continue
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
                        
                        # Log history
                        history = models_db.RatingHistory(
                            user_id=user.id,
                            old_rank=old_rank,
                            new_rank=new_rank,
                            elo_change=elo_change,
                            game_id=db_game.id
                        )
                        session.add(history)
            
            session.commit()
            session.refresh(db_game)
            return self._to_dict(db_game)
        finally:
            session.close()

    def list_games(self, user_id: int, limit: int = 20, offset: int = 0) -> List[Dict[str, Any]]:
        session = self.session_factory()
        try:
            # Get games where user is black or white
            games = session.query(models_db.Game).filter(
                (models_db.Game.black_player_id == user_id) | 
                (models_db.Game.white_player_id == user_id)
            ).order_by(models_db.Game.started_at.desc()).offset(offset).limit(limit).all()
            return [self._to_dict(game) for game in games]
        finally:
            session.close()

    def get_game(self, game_id: int) -> Optional[Dict[str, Any]]:
        session = self.session_factory()
        try:
            game = session.query(models_db.Game).filter(models_db.Game.id == game_id).first()
            if game:
                return self._to_dict(game)
            return None
        finally:
            session.close()

    def _to_dict(self, game: models_db.Game) -> Dict[str, Any]:
        return {
            "id": game.id,
            "black_player_id": game.black_player_id,
            "white_player_id": game.white_player_id,
            "result": game.result,
            "game_type": game.game_type,
            "started_at": game.started_at,
            "sgf_content": game.sgf_content
        }
