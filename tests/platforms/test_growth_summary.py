"""成长屏(围棋 kiosk 屏 22)那几个数的聚合 —— `GET /api/v1/growth/summary` 背后的两个仓方法。

这里守的是**口径**,不是数字本身:

1. **升降级胜率从账本算。** `ai_ladder_game_ledger` 有 `user_color`,`result` 本身就是
   **从这个用户视角**写的 win/loss。(2026-09 起 `user_games` 也有了 `user_color`,
   「全部算得出执色的局」那个胜率在 `UserGameRepository.decided_since`,
   见 `tests/web_ui/test_user_game_color.py`;这里守的是升降级那一半。)
2. **没打过的档不出现。** 稿子原话「没打过的档一律不列,不摆一排 0 胜 0 负」——
   GROUP BY 天然满足,但要有人守着,别哪天改成「补齐 41 档」。
3. **`counted=False` 的行一局都不算。** 那是已经判过「这一局不作数」的局,
   算进胜率就是把被排除的成绩又放回去了。

⚠️ 时间窗那条断言**在 SQLite 上不作数**:`settled_at`/`created_at` 是
`DateTime(timezone=True)`,而 SQLite 不存时区(同一坑在本仓已登记过三条)。
所以这里只断言「窗内 / 窗外分得开」,不断言具体秒数;真正的边界口径以 PG 为准。

**变异记录**(2026-08-25,逐个改坏逐个跑):
  MG1 不再排除 `counted=False`        → 红「uncounted」那条
  MG2 时间窗失效(近 30 天当成全部)   → 红「window separates」那条
  MG3 不按 `user_id` 过滤             → 红「another user」那条
  MG4 把 41 档补齐(没打过的也列)     → 红 3 条,含「only rungs actually played」

⚠️ MG4 第一次跑**全绿**,而原因是我的 perl 模式没匹配上源码那一行(它在 dict 字面量里,
不是 `return`)—— **空变异,不是闸有洞**。换对模式后照常红。
记在这儿是因为下一个人看到「变异全绿」时,第一件该查的是**变异到底改没改到代码**。
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from katrain.web.core import models_db
from katrain.web.core.ai_ladder_ranked import AiLadderRankedRepository
from katrain.web.core.user_game_repo import UserGameRepository


@pytest.fixture()
def db(tmp_path):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    engine = create_engine(f"sqlite:///{tmp_path/'growth.db'}")
    models_db.Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


def _user(session_factory, username="tester"):
    s = session_factory()
    try:
        u = models_db.User(username=username, hashed_password="x")
        s.add(u)
        s.commit()
        return u.id
    finally:
        s.close()


def _ledger(session_factory, *, user_id, game_id, result, settled_at, counted=True, rung=18, rank_name="3级"):
    """⚠️ **`counted=True` 的行不是随便造得出来的。**

    `ck_ai_ladder_ledger_decision` 要求:counted 为真 ⇒ `reason IS NULL` **且**
    `opponent_rung` / `opponent_rank_name` / `opponent_config_snapshot` 都有值、
    认证是 `certified`、可用是 `available`、`result IN ('win','loss')`;
    counted 为假 ⇒ **必须**给出 `reason`。

    这条约束顺带保证了一件事,而 `growth_summary` 正好靠它:
    **每一条 counted 的行都一定有 `opponent_rung`** —— 「按对手强度」不会漏掉已计入的局。
    (查询里那句 `opponent_rung.isnot(None)` 因此是冗余的;留着是因为
    `counted=False` 的行不受这条约束管,而将来若放开过滤条件,它还挡得住。)
    """
    s = session_factory()
    try:
        s.add(
            models_db.AiLadderGameLedger(
                game_id=game_id,
                user_id=user_id,
                user_color="B",
                result=result,
                game_type="ai_ladder_ranked",
                opponent_rung=rung if counted else None,
                opponent_rank_name=rank_name if counted else None,
                opponent_config_snapshot={"recipe": "fixture"} if counted else None,
                opponent_certification_status="certified" if counted else None,
                opponent_availability="available" if counted else None,
                opponent_route="local" if counted else None,
                counted=counted,
                reason=None if counted else "inconclusive",
                settled_at=settled_at,
            )
        )
        s.commit()
    finally:
        s.close()


NOW = datetime(2026, 8, 25, 12, 0, tzinfo=timezone.utc)
IN_WINDOW = NOW - timedelta(days=3)
OUT_OF_WINDOW = NOW - timedelta(days=90)
SINCE = NOW - timedelta(days=30)


def test_winrate_comes_from_the_ledger_because_user_games_cannot_say_who_won(db):
    """同一个用户的两局:账本说「他赢了一局、输了一局」,胜负从账本的用户视角读。

    这条原先还断言 `UserGame` 里**没有** `user_color` —— 2026-09 那一列加上了(可空,
    算不出就 NULL,见 `models_db.UserGame.user_color`),那句反面断言随之作废。
    """
    uid = _user(db)
    _ledger(db, user_id=uid, game_id="g1", result="win", settled_at=IN_WINDOW)
    _ledger(db, user_id=uid, game_id="g2", result="loss", settled_at=IN_WINDOW)

    summary = AiLadderRankedRepository(db).growth_summary(uid, since=SINCE)
    assert (summary["ranked_wins_in_window"], summary["ranked_losses_in_window"]) == (1, 1)


def test_window_separates_recent_from_old_but_the_all_time_total_does_not(db):
    uid = _user(db)
    _ledger(db, user_id=uid, game_id="new", result="win", settled_at=IN_WINDOW)
    _ledger(db, user_id=uid, game_id="old", result="win", settled_at=OUT_OF_WINDOW)

    summary = AiLadderRankedRepository(db).growth_summary(uid, since=SINCE)
    assert summary["ranked_wins_in_window"] == 1, "窗外那局被算进了近 30 天"
    assert summary["ranked_total"] == 2, "累计应该是所有 counted 的局,不受窗影响"


def test_uncounted_games_never_enter_any_number(db):
    """`counted=False` = 已经判过「这一局不作数」。算进去就是把排除掉的成绩放回来。"""
    uid = _user(db)
    _ledger(db, user_id=uid, game_id="ok", result="win", settled_at=IN_WINDOW)
    _ledger(db, user_id=uid, game_id="void", result="win", settled_at=IN_WINDOW, counted=False)

    summary = AiLadderRankedRepository(db).growth_summary(uid, since=SINCE)
    assert summary["ranked_total"] == 1
    assert summary["ranked_wins_in_window"] == 1
    # 两局同一档、都是 win;算进去就会是 2 胜。**判据落在这个 1 上,不落在「列表空不空」上**。
    assert summary["by_opponent_rung"] == [{"rung": 18, "rank_name": "3级", "wins": 1, "losses": 0}]


def test_by_opponent_rung_lists_only_rungs_actually_played(db):
    """稿子原话:「**没打过的档一律不列**,不摆一排 0 胜 0 负。」"""
    uid = _user(db)
    _ledger(db, user_id=uid, game_id="a", result="win", settled_at=IN_WINDOW, rung=18, rank_name="3级")
    _ledger(db, user_id=uid, game_id="b", result="loss", settled_at=IN_WINDOW, rung=18, rank_name="3级")
    _ledger(db, user_id=uid, game_id="c", result="win", settled_at=OUT_OF_WINDOW, rung=21, rank_name="准1段")

    summary = AiLadderRankedRepository(db).growth_summary(uid, since=SINCE)

    # 高档在前 —— 屏上那一列就是这个顺序。窗外那局也算:这一块说的是「累计战绩」。
    assert summary["by_opponent_rung"] == [
        {"rung": 21, "rank_name": "准1段", "wins": 1, "losses": 0},
        {"rung": 18, "rank_name": "3级", "wins": 1, "losses": 1},
    ]
    assert len(summary["by_opponent_rung"]) == 2, "补出了没打过的档"


def test_another_users_games_do_not_leak_in(db):
    mine = _user(db, "mine")
    theirs = _user(db, "theirs")
    _ledger(db, user_id=theirs, game_id="x", result="win", settled_at=IN_WINDOW, rung=18, rank_name="3级")

    summary = AiLadderRankedRepository(db).growth_summary(mine, since=SINCE)
    assert summary["ranked_total"] == 0
    assert summary["by_opponent_rung"] == []


def test_count_since_counts_only_this_users_games_in_the_window(db):
    mine = _user(db, "mine")
    theirs = _user(db, "theirs")
    s = db()
    try:
        s.add_all(
            [
                models_db.UserGame(id="a", user_id=mine, source="play_ai", created_at=IN_WINDOW),
                models_db.UserGame(id="b", user_id=mine, source="play_ai", created_at=OUT_OF_WINDOW),
                models_db.UserGame(id="c", user_id=theirs, source="play_ai", created_at=IN_WINDOW),
            ]
        )
        s.commit()
    finally:
        s.close()

    assert UserGameRepository(db).count_since(mine, since=SINCE) == 1


def test_count_since_counts_only_games_this_user_actually_played(db):
    """「近 30 天对局」那一格只数自己下的局(Fan 2026-09-23 裁定:成长屏只讲这个账户自己练的)。

    导入的谱、棋谱库里的谱、研究存档都存在你名下,但**不是你下的** —— 从前它们也被数进去,
    于是同一屏上「近 30 天对局」比日历的全年总数还大(线上实测 40 vs 39)。
    """
    mine = _user(db, "player")
    s = db()
    try:
        s.add_all(
            [
                models_db.UserGame(id=f"g-{src}", user_id=mine, source=src, created_at=IN_WINDOW)
                for src in ("play_ai", "play_local", "play_human", "import", "kifu_library", "research")
            ]
        )
        s.commit()
    finally:
        s.close()

    assert UserGameRepository(db).count_since(mine, since=SINCE) == 3
