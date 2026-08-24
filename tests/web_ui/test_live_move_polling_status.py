"""poll_moves 不许把已经结束的对局改回「正在直播」。

2026-08-24 现场量到的那一环：`fetch_list` 每分钟如实把 49 局降级成 finished
（日志里 "demoted 49" 一轮不落），但接口读出来仍然是 49 局 live —— 有人在两轮
之间把它们改了回去。就是 `poll_moves`，每 3 秒一次：

1. 对局结束后，上游 `/situation/<id>` 只回**信封** `{"code":"0","msg":""}`
   （实测 21 字节，没有 `data`）。`get_situation` 里写的是 `data.get("data", data)`,
   于是把信封本身当成局面返回 —— 一个**真值 dict**，调用方的 `if not situation`
   拦不住。
2. 再往下 `md.get("liveStatus", 0) == 0` —— 默认值 0 恰好就是「进行中」那一档。
   字段缺失 ⇒ 判成 live。

两层是同一个错的两次出现：**「上游没说」被当成了「上游说还在下」。**
判别位必须是上游真写进来的值，不能是一个字段的缺席，更不能给它配一个
恰好等于「进行中」的默认值。

本文件把两层各守一条，另加一条端到端的「结束了就别再复活」。
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from katrain.cron.clients.xingzhen import XingZhenClient
from katrain.cron.db import Base
from katrain.cron.jobs.poll_moves import PollMovesJob
from katrain.cron.models import LiveMatchDB

# 上游在对局结束后真正回的东西（实测 21 字节）
ENVELOPE_ONLY = {"code": "0", "msg": ""}


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine, tables=[LiveMatchDB.__table__])
    session = sessionmaker(bind=engine)()
    yield session
    session.close()
    engine.dispose()


def _match(session, status="finished", move_count=303) -> LiveMatchDB:
    row = LiveMatchDB(
        match_id="x1",
        source="xingzhen",
        source_id="191344",
        tournament="测试杯",
        player_black="黑",
        player_white="白",
        status=status,
        move_count=move_count,
        moves=[],
        current_winrate=0.5,
        current_score=0.0,
    )
    session.add(row)
    session.commit()
    return row


# ── 层一：只回信封时，get_situation 要说「没有」 ──────────────────────────


def test_get_situation_returns_none_when_upstream_sent_only_an_envelope(monkeypatch):
    client = XingZhenClient()
    monkeypatch.setattr(client, "_request", AsyncMock(return_value=ENVELOPE_ONLY))

    assert asyncio.run(client.get_situation("191344")) is None, "信封被当成局面返回了"


def test_get_situation_still_returns_a_real_situation():
    """把上面那条写死成 None 是不行的 —— 有局面时必须照常返回。"""
    client = XingZhenClient()
    payload = {"liveStatus": 0, "moves": "pd,dp", "winrate": 0.55}
    client._request = AsyncMock(return_value={"code": "0", "msg": "", "data": payload})

    assert asyncio.run(client.get_situation("191344")) == payload


# ── 层二：liveStatus 缺失不许读成 live ───────────────────────────────────


def _poll(job, match, db, situation):
    registry = MagicMock()
    client = MagicMock()
    client.get_situation = AsyncMock(return_value=situation)
    registry.get_client.return_value = client
    repo = MagicMock()
    asyncio.run(job._poll_xingzhen(registry, repo, match, db))


def test_a_missing_live_status_does_not_resurrect_a_finished_match(db_session):
    """字段缺失 ⇒ 保持原状。这条要是红了，直播列表永远清不干净。"""
    match = _match(db_session, status="finished")

    _poll(PollMovesJob(), match, db_session, {"moves": "pd,dp"})

    assert match.status == "finished"


def test_a_missing_live_status_does_not_end_a_live_match_either(db_session):
    """反方向也要守：缺失既不是 live 也不是 finished，是「不知道」，别动它。"""
    match = _match(db_session, status="live")

    _poll(PollMovesJob(), match, db_session, {"moves": "pd,dp"})

    assert match.status == "live"


@pytest.mark.parametrize(
    "live_status,expected",
    [(0, "live"), (40, "finished"), (2, "finished")],
    ids=["0=进行中", "40=已结束", "其它非零=已结束"],
)
def test_an_explicit_live_status_is_still_honoured(db_session, live_status, expected):
    """上游**明确给了**状态时，照它说的办 —— 上面两条不能退化成「永不改状态」。"""
    match = _match(db_session, status="finished" if expected == "live" else "live")

    _poll(PollMovesJob(), match, db_session, {"liveStatus": live_status, "moves": "pd"})

    assert match.status == expected


def test_an_envelope_only_situation_never_reaches_the_status_write(db_session):
    """端到端：结束的对局 + 上游只回信封 ⇒ 状态一动不动。

    这条同时覆盖两层：层一让 `get_situation` 回 None，`if not situation: return`
    就拦住了；即使层一被改坏，层二也会把 status 保持原样。
    """
    match = _match(db_session, status="finished")

    _poll(PollMovesJob(), match, db_session, None)  # get_situation 回 None
    assert match.status == "finished"

    _poll(PollMovesJob(), match, db_session, ENVELOPE_ONLY)  # 万一层一失守
    assert match.status == "finished"
