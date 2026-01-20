from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from katrain.web.core import models_db

class GameRepository:
    def __init__(self, session_factory):
        self.session_factory = session_factory

    def create_game(self, user_id: int, sgf_content: str, result: str, game_type: str) -> Dict[str, Any]:
        session = self.session_factory()
        try:
            # For simplicity, assume single player saves (Human vs AI) 
            # or we set black/white based on SGF later. 
            # For now, let's just save it associated with the user as Black player default?
            # Or just "black_player_id" for now.
            db_game = models_db.Game(
                black_player_id=user_id, # Default ownership
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
