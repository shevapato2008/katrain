"""近 30 天档位走势(G3,Fan 2026-09-21 裁定画档位)。

**数据源的前提**:`expected_opponent_rung` 的 docstring 写着「定级之后玩家面对的就是自己那一档」——
所以定级**之后**那些局的 `opponent_rung` 就是本人当时的档位。这份前提由本文件的前提闸钉住:
前提变了,它先红,而不是走势图开始画错。

**定级期那 5 局必须排除**:那时的 `opponent_rung` 是二分搜索的中点,不是实力。
账本里没有一列写着「这局是不是定级局」,唯一摘得出来的办法是按时间取前 PLACEMENT_GAMES 局。

**没有对局的那天不补点**:把昨天的值延续到今天,会画出一条「你在进步」的假曲线。

⚠️ 时间窗与「哪天」的边界在 SQLite 上只断言分得开,不断言秒级(同 `test_growth_summary.py`):
SQLite 不存时区,口径以 PG 为准。
"""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from katrain.web.core import models_db
from katrain.web.core.ai_ladder_ranked import PLACEMENT_GAMES, AiLadderRankedRepository, expected_opponent_rung

NOW = datetime.now(timezone.utc).replace(hour=12, minute=0, second=0, microsecond=0)
SINCE = NOW - timedelta(days=30)


@pytest.fixture()
def repo(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path/'t.db'}")
    models_db.Base.metadata.create_all(engine)
    return AiLadderRankedRepository(sessionmaker(bind=engine, expire_on_commit=False))


_seq = iter(range(1, 100_000))


def _settle(repo, *, at, rung, user_id=1, counted=True, result="win"):
    """counted 的行要过 `ck_ai_ladder_ledger_decision`:档位、配置快照、认证、可用、线路一样不能少。"""
    s = repo.session_factory()
    s.add(
        models_db.AiLadderGameLedger(
            game_id=f"g{next(_seq)}",
            user_id=user_id,
            user_color="B",
            result=result,
            game_type="ai_ladder_ranked",
            opponent_rung=rung if counted else None,
            opponent_rank_name=f"{21 - rung}级" if counted else None,
            opponent_config_snapshot={"recipe": "fixture"} if counted else None,
            opponent_certification_status="certified" if counted else None,
            opponent_availability="available" if counted else None,
            opponent_route="local" if counted else None,
            counted=counted,
            reason=None if counted else "inconclusive",
            settled_at=at,
        )
    )
    s.commit()
    s.close()


def _placement(repo, *, start, user_id=1):
    for i in range(PLACEMENT_GAMES):  # 二分搜索的中点:故意给离谱的档,画出来一眼就看得见
        _settle(repo, at=start + timedelta(minutes=i), rung=30, user_id=user_id)


def test_one_point_per_day_taking_the_last_game_of_that_day(repo):
    base = NOW - timedelta(days=10)
    _placement(repo, start=base - timedelta(days=1))
    _settle(repo, at=base + timedelta(hours=1), rung=10)
    _settle(repo, at=base + timedelta(hours=5), rung=11)  # 同一天的后一局
    _settle(repo, at=base + timedelta(days=3), rung=12)  # 中间两天没下:不补点

    got = repo.rung_trend(1, since=SINCE)

    assert [p["rung"] for p in got] == [11, 12]
    assert [p["date"] for p in got] == [base.date().isoformat(), (base + timedelta(days=3)).date().isoformat()]
    assert got[0]["rank_name"] == "10级"


def test_still_in_placement_means_no_trend_at_all(repo):
    """**不许**把定级局的中点画出来充当实力曲线。"""
    for i in range(PLACEMENT_GAMES - 1):
        _settle(repo, at=NOW - timedelta(days=3, minutes=-i), rung=7)
    assert repo.rung_trend(1, since=SINCE) == []


def test_placement_games_are_excluded_even_inside_the_window(repo):
    _placement(repo, start=NOW - timedelta(days=5))
    _settle(repo, at=NOW - timedelta(days=2), rung=12)
    assert [p["rung"] for p in repo.rung_trend(1, since=SINCE)] == [12]


def test_uncounted_other_users_and_old_games_stay_out(repo):
    _placement(repo, start=NOW - timedelta(days=60))
    _settle(repo, at=NOW - timedelta(days=40), rung=9)  # 窗口外
    _settle(repo, at=NOW - timedelta(days=4), rung=12, counted=False)  # 不作数的局
    _settle(repo, at=NOW - timedelta(days=3), rung=13, user_id=2)  # 别人的
    _settle(repo, at=NOW - timedelta(days=2), rung=11)
    assert [p["rung"] for p in repo.rung_trend(1, since=SINCE)] == [11]


def test_the_premise_behind_the_data_source():
    """**前提闸。** 定级之后「对手档 = 自己那一档」—— 走势图整条建立在这句话上。
    这条一旦红,说明前提变了,`rung_trend` 的数据源随之作废(该改的是数据源,不是这条测试)。"""
    for rung in (1, 12, 18, 38):
        assert expected_opponent_rung(rung, 1, 32) == rung
