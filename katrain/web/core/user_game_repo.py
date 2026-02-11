"""Repository for user_games and user_game_analysis CRUD operations."""
import hashlib
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy.sql import func
from katrain.web.core import models_db


class UserGameRepository:
    def __init__(self, session_factory):
        self.session_factory = session_factory

    def create(self, user_id: int, sgf_content: str, source: str, game_id: Optional[str] = None, **kwargs) -> Dict[str, Any]:
        session = self.session_factory()
        try:
            # Idempotent creation: if client provides an id that already exists, return existing record
            if game_id:
                existing = session.query(models_db.UserGame).filter(models_db.UserGame.id == game_id).first()
                if existing:
                    return self._to_dict(existing, include_sgf=True)

            sgf_hash = hashlib.sha256(sgf_content.encode()).hexdigest() if sgf_content else None
            game_kwargs = dict(
                user_id=user_id,
                sgf_content=sgf_content,
                source=source,
                sgf_hash=sgf_hash,
                title=kwargs.get("title"),
                player_black=kwargs.get("player_black"),
                player_white=kwargs.get("player_white"),
                result=kwargs.get("result"),
                board_size=kwargs.get("board_size", 19),
                rules=kwargs.get("rules", "chinese"),
                komi=kwargs.get("komi", 7.5),
                move_count=kwargs.get("move_count", 0),
                category=kwargs.get("category", "game"),
                game_type=kwargs.get("game_type"),
                event=kwargs.get("event"),
                game_date=kwargs.get("game_date"),
            )
            if game_id:
                game_kwargs["id"] = game_id

            db_game = models_db.UserGame(**game_kwargs)
            session.add(db_game)
            session.commit()
            session.refresh(db_game)
            return self._to_dict(db_game, include_sgf=True)
        finally:
            session.close()

    def get(self, game_id: str, user_id: int) -> Optional[Dict[str, Any]]:
        session = self.session_factory()
        try:
            game = session.query(models_db.UserGame).filter(
                models_db.UserGame.id == game_id,
                models_db.UserGame.user_id == user_id,
            ).first()
            if game:
                return self._to_dict(game, include_sgf=True)
            return None
        finally:
            session.close()

    def list(
        self,
        user_id: int,
        page: int = 1,
        page_size: int = 20,
        category: Optional[str] = None,
        source: Optional[str] = None,
        sort: str = "created_at_desc",
        q: Optional[str] = None,
    ) -> Dict[str, Any]:
        session = self.session_factory()
        try:
            query = session.query(models_db.UserGame).filter(
                models_db.UserGame.user_id == user_id
            )
            if category:
                query = query.filter(models_db.UserGame.category == category)
            if source:
                query = query.filter(models_db.UserGame.source == source)
            if q:
                like = f"%{q}%"
                query = query.filter(
                    (models_db.UserGame.title.ilike(like))
                    | (models_db.UserGame.player_black.ilike(like))
                    | (models_db.UserGame.player_white.ilike(like))
                    | (models_db.UserGame.event.ilike(like))
                )

            # Sort
            if sort == "created_at_asc":
                query = query.order_by(models_db.UserGame.created_at.asc())
            elif sort == "move_count_desc":
                query = query.order_by(models_db.UserGame.move_count.desc())
            else:
                query = query.order_by(models_db.UserGame.created_at.desc())

            total = query.count()
            page_size = min(page_size, 100)
            offset = (page - 1) * page_size
            games = query.offset(offset).limit(page_size).all()
            return {
                "items": [self._to_dict(g, include_sgf=False) for g in games],
                "total": total,
                "page": page,
                "page_size": page_size,
            }
        finally:
            session.close()

    def update(self, game_id: str, user_id: int, updated_at: Optional[str] = None, **kwargs) -> Optional[Dict[str, Any]]:
        session = self.session_factory()
        try:
            game = session.query(models_db.UserGame).filter(
                models_db.UserGame.id == game_id,
                models_db.UserGame.user_id == user_id,
            ).first()
            if not game:
                return None

            # Optimistic lock: if updated_at provided, check it matches
            if updated_at and game.updated_at and str(game.updated_at) != updated_at:
                raise ValueError("Conflict: game has been modified since last read")

            for key, value in kwargs.items():
                if hasattr(game, key) and value is not None:
                    setattr(game, key, value)

            if "sgf_content" in kwargs and kwargs["sgf_content"]:
                game.sgf_hash = hashlib.sha256(kwargs["sgf_content"].encode()).hexdigest()

            session.commit()
            session.refresh(game)
            return self._to_dict(game, include_sgf=True)
        finally:
            session.close()

    def delete(self, game_id: str, user_id: int) -> bool:
        session = self.session_factory()
        try:
            game = session.query(models_db.UserGame).filter(
                models_db.UserGame.id == game_id,
                models_db.UserGame.user_id == user_id,
            ).first()
            if not game:
                return False
            session.delete(game)
            session.commit()
            return True
        finally:
            session.close()

    def _to_dict(self, game: models_db.UserGame, include_sgf: bool = False) -> Dict[str, Any]:
        d = {
            "id": game.id,
            "user_id": game.user_id,
            "title": game.title,
            "player_black": game.player_black,
            "player_white": game.player_white,
            "result": game.result,
            "board_size": game.board_size,
            "rules": game.rules,
            "komi": game.komi,
            "move_count": game.move_count,
            "source": game.source,
            "category": game.category,
            "game_type": game.game_type,
            "event": game.event,
            "game_date": game.game_date,
            "created_at": str(game.created_at) if game.created_at else None,
            "updated_at": str(game.updated_at) if game.updated_at else None,
        }
        if include_sgf:
            d["sgf_content"] = game.sgf_content
        return d


class UserGameAnalysisRepository:
    def __init__(self, session_factory):
        self.session_factory = session_factory

    def get_analysis(self, game_id: str, start_move: int = 0, limit: int = 400) -> List[Dict[str, Any]]:
        session = self.session_factory()
        try:
            records = session.query(models_db.UserGameAnalysis).filter(
                models_db.UserGameAnalysis.game_id == game_id,
                models_db.UserGameAnalysis.move_number >= start_move,
            ).order_by(models_db.UserGameAnalysis.move_number).limit(limit).all()
            return [self._to_dict(r) for r in records]
        finally:
            session.close()

    def get_move_analysis(self, game_id: str, move_number: int) -> Optional[Dict[str, Any]]:
        session = self.session_factory()
        try:
            record = session.query(models_db.UserGameAnalysis).filter(
                models_db.UserGameAnalysis.game_id == game_id,
                models_db.UserGameAnalysis.move_number == move_number,
            ).first()
            if record:
                return self._to_dict(record)
            return None
        finally:
            session.close()

    def upsert(self, game_id: str, move_number: int, **kwargs) -> Dict[str, Any]:
        session = self.session_factory()
        try:
            record = session.query(models_db.UserGameAnalysis).filter(
                models_db.UserGameAnalysis.game_id == game_id,
                models_db.UserGameAnalysis.move_number == move_number,
            ).first()

            if record:
                for key, value in kwargs.items():
                    if hasattr(record, key):
                        setattr(record, key, value)
            else:
                record = models_db.UserGameAnalysis(
                    game_id=game_id,
                    move_number=move_number,
                    **{k: v for k, v in kwargs.items() if hasattr(models_db.UserGameAnalysis, k)}
                )
                session.add(record)

            session.commit()
            session.refresh(record)
            return self._to_dict(record)
        finally:
            session.close()

    def _to_dict(self, record: models_db.UserGameAnalysis) -> Dict[str, Any]:
        return {
            "id": record.id,
            "game_id": record.game_id,
            "move_number": record.move_number,
            "status": record.status,
            "winrate": record.winrate,
            "score_lead": record.score_lead,
            "visits": record.visits,
            "top_moves": record.top_moves,
            "ownership": record.ownership,
            "move": record.move,
            "actual_player": record.actual_player,
            "delta_score": record.delta_score,
            "delta_winrate": record.delta_winrate,
            "is_brilliant": record.is_brilliant,
            "is_mistake": record.is_mistake,
            "is_questionable": record.is_questionable,
        }
