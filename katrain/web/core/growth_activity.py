"""近一年练棋日历(G4)的数据源:每天下完几局、首次解出几道题。

**一格 = 当天下完的对局 + 当天新解出的题**(Fan 2026-09-22 定)。两项分开回,由前端相加上色 ——
以后要分开画也不用改契约。

**按客户端的时区切天。** 按 UTC 切,北京早上 8 点前下的棋会落到前一天,「今天」那格明明下过却是空的。
`tz_offset` 是东几区的分钟数(北京 = 480)。

**哪些算「下完的对局」**:只认自己下的那三种来源,口径同前端
`kiosk/components/report/reviewPresentation.ts` 的 `isPlaySource`。用**白名单**不用黑名单 ——
导入的谱、棋谱库、研究局都不是你下的,之后再加一种新来源也不会悄悄混进来。

⚠️ 解题时间是 `first_completed_at`,由 `merge_tsumego_progress` 盖戳。盒子离线时解的题,
同步到云端那一刻才在云端盖戳 ⇒ 云端那份可能把它算到同步那天。盒子通常在线,不为此改同步协议。
"""

from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone
from typing import Dict, List

from katrain.web.core import models_db
from katrain.web.core.user_game_repo import PLAYED_SOURCES


def _local_date(ts: datetime, tz: timezone) -> date:
    # SQLite 读回来是 naive(不存时区);写进去的一律是 UTC(`func.now()` / `utcnow()`)。
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return ts.astimezone(tz).date()


class GrowthActivityRepository:
    def __init__(self, session_factory):
        self.session_factory = session_factory

    def daily(self, user_id: int, *, days: int, tz_offset: int, now: datetime = None) -> List[Dict]:
        """→ `[{"date": "YYYY-MM-DD", "games": n, "solved": m}, ...]`,按日期升序,**只列有活动的日子**。

        窗口是客户端时区里的「今天」往前数 `days` 天(含今天)。
        """
        tz = timezone(timedelta(minutes=tz_offset))
        today = (now or datetime.now(timezone.utc)).astimezone(tz).date()
        first = today - timedelta(days=days - 1)
        # 换成 UTC 再进 SQL:SQLite 比的是字面时间,带 +08:00 的参数会被当成 UTC 读,错开 8 小时。
        since = datetime.combine(first, time.min, tzinfo=tz).astimezone(timezone.utc)

        G, P = models_db.UserGame, models_db.UserTsumegoProgress
        session = self.session_factory()
        try:
            games = (
                session.query(G.created_at)
                .filter(G.user_id == user_id, G.source.in_(PLAYED_SOURCES), G.created_at >= since)
                .all()
            )
            solved = (
                session.query(P.first_completed_at)
                .filter(P.user_id == user_id, P.completed.is_(True), P.first_completed_at >= since)
                .all()
            )
        finally:
            session.close()

        buckets: Dict[date, List[int]] = defaultdict(lambda: [0, 0])
        for column, rows in ((0, games), (1, solved)):
            for (ts,) in rows:
                if ts is None:
                    continue
                day = _local_date(ts, tz)
                if first <= day <= today:
                    buckets[day][column] += 1
        return [{"date": d.isoformat(), "games": g, "solved": s} for d, (g, s) in sorted(buckets.items())]
