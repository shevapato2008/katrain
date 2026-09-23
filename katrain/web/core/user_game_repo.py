"""Repository for user_games and user_game_analysis CRUD operations."""

import hashlib
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy.sql import func
from katrain.web.core import models_db


class ReservedAiLadderGameIdError(ValueError):
    pass


class ProtectedRankedGameError(ValueError):
    pass


class InvalidAuthoritativeRankedGameError(ValueError):
    pass


class UserGameRepository:
    def __init__(self, session_factory):
        self.session_factory = session_factory

    def create(
        self, user_id: int, sgf_content: str, source: str, game_id: Optional[str] = None, **kwargs
    ) -> Dict[str, Any]:
        session = self.session_factory()
        try:
            if game_id and self._is_ai_ladder_game_id_reserved(session, game_id):
                raise ReservedAiLadderGameIdError("game_id is reserved for a ranked AI game")
            # Idempotent creation: if client provides an id that already exists, return existing record
            if game_id:
                existing = session.query(models_db.UserGame).filter(models_db.UserGame.id == game_id).first()
                if existing:
                    return self._to_dict(existing, include_sgf=True)

            sgf_hash = hashlib.sha256(sgf_content.encode()).hexdigest() if sgf_content else None

            # Dedup: if same user already has a game with identical SGF content, return existing
            if sgf_hash:
                existing = (
                    session.query(models_db.UserGame)
                    .filter(
                        models_db.UserGame.user_id == user_id,
                        models_db.UserGame.sgf_hash == sgf_hash,
                    )
                    .first()
                )
                if existing:
                    return self._to_dict(existing, include_sgf=True)

            game_kwargs = dict(
                user_id=user_id,
                sgf_content=sgf_content,
                source=source,
                sgf_hash=sgf_hash,
                title=kwargs.get("title"),
                player_black=kwargs.get("player_black"),
                player_white=kwargs.get("player_white"),
                black_rank=kwargs.get("black_rank"),
                white_rank=kwargs.get("white_rank"),
                result=kwargs.get("result"),
                board_size=kwargs.get("board_size", 19),
                rules=kwargs.get("rules", "chinese"),
                komi=kwargs.get("komi", 7.5),
                move_count=kwargs.get("move_count", 0),
                category=kwargs.get("category", "game"),
                game_type=kwargs.get("game_type"),
                user_color=kwargs.get("user_color"),
                origin_device_id=kwargs.get("origin_device_id"),
                event=kwargs.get("event"),
                round_name=kwargs.get("round_name"),
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

    def create_ai_ladder_ranked(self, *, user_id: int, game_id: str, sgf_content: str, **kwargs) -> Dict[str, Any]:
        """Persist one server-issued ranked game id without SGF hash deduplication.

        A retry may return the same owner's existing ranked row. Reusing a game id
        across users or for a different game type fails closed.
        """

        if kwargs.get("source", "play_ai") != "play_ai":
            raise InvalidAuthoritativeRankedGameError("authoritative ranked AI games require source=play_ai")
        session = self.session_factory()
        try:
            existing = session.get(models_db.UserGame, game_id)
            if existing is not None:
                if existing.user_id != user_id:
                    raise ValueError("game_id belongs to another user")
                if existing.game_type != "ai_ladder_ranked":
                    raise ValueError("game_id is not an authoritative ranked AI game")
                incoming_hash = hashlib.sha256(sgf_content.encode()).hexdigest() if sgf_content else None
                immutable_fields = {
                    "sgf_content": sgf_content,
                    "sgf_hash": incoming_hash,
                    "result": kwargs.get("result"),
                    "board_size": kwargs.get("board_size", 19),
                    "rules": kwargs.get("rules", "chinese"),
                    "komi": kwargs.get("komi", 7.5),
                    "move_count": kwargs.get("move_count", 0),
                    "player_black": kwargs.get("player_black"),
                    "player_white": kwargs.get("player_white"),
                    "black_rank": kwargs.get("black_rank"),
                    "white_rank": kwargs.get("white_rank"),
                    "source": "play_ai",
                    "category": kwargs.get("category", "game"),
                    "origin_device_id": kwargs.get("origin_device_id"),
                    # ⚠️ `user_color` 故意不在这里:这一列诞生之前写下的权威局是 NULL,
                    # 重试时传进来的却是 'B'/'W' ⇒ 一次正常重试会被判成「权威局被篡改」。
                }
                if any(getattr(existing, field) != value for field, value in immutable_fields.items()):
                    raise ValueError("authoritative ranked AI game is immutable")
                return self._to_dict(existing, include_sgf=True)

            db_game = models_db.UserGame(
                id=game_id,
                user_id=user_id,
                sgf_content=sgf_content,
                source="play_ai",
                sgf_hash=hashlib.sha256(sgf_content.encode()).hexdigest() if sgf_content else None,
                title=kwargs.get("title"),
                player_black=kwargs.get("player_black"),
                player_white=kwargs.get("player_white"),
                black_rank=kwargs.get("black_rank"),
                white_rank=kwargs.get("white_rank"),
                result=kwargs.get("result"),
                board_size=kwargs.get("board_size", 19),
                rules=kwargs.get("rules", "chinese"),
                komi=kwargs.get("komi", 7.5),
                move_count=kwargs.get("move_count", 0),
                category=kwargs.get("category", "game"),
                game_type="ai_ladder_ranked",
                user_color=kwargs.get("user_color"),
                origin_device_id=kwargs.get("origin_device_id"),
                event=kwargs.get("event"),
                round_name=kwargs.get("round_name"),
                game_date=kwargs.get("game_date"),
            )
            session.add(db_game)
            session.commit()
            session.refresh(db_game)
            return self._to_dict(db_game, include_sgf=True)
        finally:
            session.close()

    def get(self, game_id: str, user_id: int) -> Optional[Dict[str, Any]]:
        session = self.session_factory()
        try:
            game = (
                session.query(models_db.UserGame)
                .filter(
                    models_db.UserGame.id == game_id,
                    models_db.UserGame.user_id == user_id,
                )
                .first()
            )
            if game:
                return self._to_dict(game, include_sgf=True)
            return None
        finally:
            session.close()

    def is_ai_ladder_game_id_reserved(self, game_id: str) -> bool:
        session = self.session_factory()
        try:
            return self._is_ai_ladder_game_id_reserved(session, game_id)
        finally:
            session.close()

    @staticmethod
    def _is_ai_ladder_game_id_reserved(session: Session, game_id: str) -> bool:
        return (
            session.get(models_db.AiLadderPendingGame, game_id) is not None
            or session.get(models_db.AiLadderActiveGame, game_id) is not None
        )

    def get_authoritative_ai_ladder_ranked(self, game_id: str, user_id: int) -> Optional[Dict[str, Any]]:
        """Load a trusted ranked row for recovery, rejecting lookalikes without mutating them."""

        session = self.session_factory()
        try:
            game = session.get(models_db.UserGame, game_id)
            if game is None:
                return None
            if game.user_id != user_id or game.game_type != "ai_ladder_ranked" or game.source != "play_ai":
                raise InvalidAuthoritativeRankedGameError("UserGame is not an authoritative ranked AI game")
            expected_hash = hashlib.sha256(game.sgf_content.encode()).hexdigest() if game.sgf_content else None
            if (
                not game.sgf_content
                or game.sgf_hash != expected_hash
                or not isinstance(game.result, str)
                or not game.result.strip()
                or game.category != "game"
                or game.board_size is None
                or not game.rules
                or game.komi is None
                or game.move_count is None
                or game.move_count < 0
            ):
                raise InvalidAuthoritativeRankedGameError("UserGame failed authoritative ranked AI validation")
            return self._to_dict(game, include_sgf=True)
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
            query = session.query(models_db.UserGame).filter(models_db.UserGame.user_id == user_id)
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

    def count_since(self, user_id: int, *, since) -> int:
        """近 N 天下了多少局。**只数局数,不数胜负** —— 胜负在 `decided_since`,
        两者口径不同(导入的谱、面对面、执色没记下来的局在这里算、在那里不算)。

        ⚠️ `since` 要**带时区**:`created_at` 是 `DateTime(timezone=True)`,
        而 SQLite 不存时区。生产是 PG,口径以 PG 为准。
        """
        session = self.session_factory()
        try:
            return int(
                session.query(func.count(models_db.UserGame.id))
                .filter(
                    models_db.UserGame.user_id == user_id,
                    models_db.UserGame.created_at >= since,
                )
                .scalar()
                or 0
            )
        finally:
            session.close()

    def decided_since(self, user_id: int, *, since) -> Dict[str, int]:
        """近 N 天里**算得出胜负**的局:知道这个用户执哪一方、且 `result` 判得出赢家。

        执色取 `user_games.user_color`;这一列诞生之前的升降级局在这里是 NULL,
        就回落到账本 `ai_ladder_game_ledger.user_color`(按 `game_id` 对上、且是同一个用户)
        —— 那个事实账本早就记着,读它不是追认。其余 NULL 的局不算,不猜。

        胜负在 Python 里判,不在 SQL 里:`result` 是 `"B+R"` / `"W+3.5"` / `"0"` / `"Void"`
        这种自由文本,SQLite 与 PG 的字符串函数不一样,这点数据量不值得写两套 SQL。

        ⚠️ 和 `count_since` **口径不同**:那个数的是下了多少局,这个数的是算得出胜负的局。
        屏上那句「有 N 局没算进胜率」就是两者的差 —— 不许拿一个冒充另一个。
        ⚠️ `since` 要**带时区**(同 `count_since`)。
        """
        G, L = models_db.UserGame, models_db.AiLadderGameLedger
        session = self.session_factory()
        try:
            rows = (
                session.query(func.coalesce(G.user_color, L.user_color), G.result)
                .outerjoin(L, (L.game_id == G.id) & (L.user_id == G.user_id))
                .filter(G.user_id == user_id, G.created_at >= since, G.result.isnot(None))
                .all()
            )
            wins = losses = 0
            for color, result in rows:
                text = (result or "").strip().upper()
                # 只认「B+…」「W+…」:和棋("0"/"DRAW")、无胜负("VOID")、没下完的都不算。
                if color not in ("B", "W") or len(text) < 2 or text[0] not in "BW" or text[1] != "+":
                    continue
                if text[0] == color:
                    wins += 1
                else:
                    losses += 1
            return {"decided": wins + losses, "wins": wins, "losses": losses}
        finally:
            session.close()

    def update(
        self, game_id: str, user_id: int, updated_at: Optional[str] = None, **kwargs
    ) -> Optional[Dict[str, Any]]:
        session = self.session_factory()
        try:
            game = (
                session.query(models_db.UserGame)
                .filter(
                    models_db.UserGame.id == game_id,
                    models_db.UserGame.user_id == user_id,
                )
                .first()
            )
            if not game:
                return None
            if game.game_type == "ai_ladder_ranked":
                raise ProtectedRankedGameError("authoritative ranked AI games are protected from generic updates")

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
            game = (
                session.query(models_db.UserGame)
                .filter(
                    models_db.UserGame.id == game_id,
                    models_db.UserGame.user_id == user_id,
                )
                .first()
            )
            if not game:
                return False
            if game.game_type == "ai_ladder_ranked":
                raise ProtectedRankedGameError("authoritative ranked AI games are protected from generic deletion")
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
            "black_rank": game.black_rank,
            "white_rank": game.white_rank,
            "result": game.result,
            "board_size": game.board_size,
            "rules": game.rules,
            "komi": game.komi,
            "move_count": game.move_count,
            "source": game.source,
            "category": game.category,
            "game_type": game.game_type,
            "user_color": game.user_color,
            "origin_device_id": game.origin_device_id,
            "event": game.event,
            "round_name": game.round_name,
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
            records = (
                session.query(models_db.UserGameAnalysis)
                .filter(
                    models_db.UserGameAnalysis.game_id == game_id,
                    models_db.UserGameAnalysis.move_number >= start_move,
                )
                .order_by(models_db.UserGameAnalysis.move_number)
                .limit(limit)
                .all()
            )
            return [self._to_dict(r) for r in records]
        finally:
            session.close()

    def get_move_analysis(self, game_id: str, move_number: int) -> Optional[Dict[str, Any]]:
        session = self.session_factory()
        try:
            record = (
                session.query(models_db.UserGameAnalysis)
                .filter(
                    models_db.UserGameAnalysis.game_id == game_id,
                    models_db.UserGameAnalysis.move_number == move_number,
                )
                .first()
            )
            if record:
                return self._to_dict(record)
            return None
        finally:
            session.close()

    def upsert(self, game_id: str, move_number: int, **kwargs) -> Dict[str, Any]:
        session = self.session_factory()
        try:
            record = (
                session.query(models_db.UserGameAnalysis)
                .filter(
                    models_db.UserGameAnalysis.game_id == game_id,
                    models_db.UserGameAnalysis.move_number == move_number,
                )
                .first()
            )

            if record:
                for key, value in kwargs.items():
                    if hasattr(record, key):
                        setattr(record, key, value)
            else:
                record = models_db.UserGameAnalysis(
                    game_id=game_id,
                    move_number=move_number,
                    **{k: v for k, v in kwargs.items() if hasattr(models_db.UserGameAnalysis, k)},
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
