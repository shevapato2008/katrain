"""取「最近 N 份已完成报告」里,本用户执的那一方的逐手评级(能力诊断 G1 的数据源)。

为什么不复用 `endpoints/reports.py` 的逐手接口:那边会**按需补算**老报告缺的 `grade`
(读 `top_moves` 重新判级),跨 20 份报告逐份补算太贵。这里只读已经落库的 `grade`,
补算不了的手按「不知道」处理(不进分母,见 `growth_diagnosis.bucket`)。
"""

from typing import Any, Dict

from sqlalchemy.sql import func

from katrain.web.core import models_db


class ReportDiagnosisRepository:
    def __init__(self, session_factory):
        self.session_factory = session_factory

    def recent_graded_moves(self, user_id: int, *, since, max_reports: int = 20) -> Dict[str, Any]:
        """→ `{"reports": 算进来的份数, "skipped_without_color": 整份没算的份数, "moves": [...]}`。

        · **只算已完成**的报告;**同一局只算最新那一份**(重跑、不同档位的报告会把同一局的手
          重复计入,样本量也跟着虚高)。
        · **只取你执的那一方**的手。执色取 `user_games.user_color`,老的升降级局回落到账本
          (同 `UserGameRepository.decided_since`)。执色算不出的局**整份跳过并报出来**,
          不把两边的手混在一起算。
        · 窗口按**对局**的时间算(诊断看的是最近的棋,不是最近才跑的报告)。
        ⚠️ `since` 要带时区(同 `count_since`)。
        """
        T, G, M, L = models_db.ReportTask, models_db.UserGame, models_db.ReportTaskMove, models_db.AiLadderGameLedger
        session = self.session_factory()
        try:
            tasks = (
                session.query(T.id, T.user_game_id, func.coalesce(G.user_color, L.user_color))
                .join(G, G.id == T.user_game_id)
                .outerjoin(L, (L.game_id == G.id) & (L.user_id == G.user_id))
                .filter(T.user_id == user_id, G.user_id == user_id, T.status == "completed", G.created_at >= since)
                .order_by(T.created_at.desc(), T.id.desc())
                .all()
            )
            picked, seen = [], set()
            for task_id, game_id, color in tasks:
                if game_id in seen:
                    continue
                seen.add(game_id)
                picked.append((task_id, color))
                if len(picked) >= max_reports:
                    break
            usable = [(task_id, color) for task_id, color in picked if color in ("B", "W")]
            moves: list = []
            for task_id, color in usable:
                rows = (
                    session.query(M.move_number, M.grade)
                    .filter(M.task_id == task_id, M.actual_player == color)
                    .order_by(M.move_number)
                    .all()
                )
                moves.extend({"move_number": n, "grade": g} for n, g in rows)
            return {"reports": len(usable), "skipped_without_color": len(picked) - len(usable), "moves": moves}
        finally:
            session.close()
