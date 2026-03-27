"""FetchUpcomingJob: scrape upcoming matches from multiple sources.

Sources:
- 野狐围棋 (foxwq.com) - Chinese, Korean, and international tournaments
- 弈客围棋 (yikeweiqi.com) - Preparing matches (status=1) as upcoming
- 幽玄の間 (u-gen.nihonkiin.or.jp) - Japanese tournament schedule
- 日本棋院 2-week schedule (nihonkiin.or.jp) - Japanese tournaments
"""

import asyncio
import logging
import re
from datetime import datetime, timezone
from typing import Optional

import httpx
from bs4 import BeautifulSoup

from katrain.cron.jobs.base import BaseJob
from katrain.cron.db import SessionLocal
from katrain.cron.models import UpcomingMatchDB

logger = logging.getLogger("katrain_cron.fetch_upcoming")

# User-Agent for web scraping
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"

# Regex to strip rank suffix from Japanese player names (e.g. "高尾紳路九段" → "高尾紳路")
# Uses word-boundary-like check: rank suffix must be a known pattern at end of string.
_RANK_RE = re.compile(
    r"(?:初段|二段|三段|四段|五段|六段|七段|八段|九段|十段"
    r"|[２３４５６７８９]段|１０段"
    r"|名人|棋聖|本因坊|王座|天元|碁聖)$"
)


class FetchUpcomingJob(BaseJob):
    """Scrape upcoming Go tournament events from official sources.

    Sources:
    - 野狐围棋 (foxwq.com) - Covers Chinese, Korean, and international tournaments
    - 弈客围棋 (yikeweiqi.com) - Preparing matches (status=1) via API
    - 幽玄の間 (u-gen.nihonkiin.or.jp) - Japanese tournament schedule (public)
    - 日本棋院 (nihonkiin.or.jp) - Japanese tournaments 2-week view

    Uses REPLACE strategy: deletes all existing upcoming events and inserts fresh data.
    """

    name = "fetch_upcoming"
    interval_seconds = 7200  # 2 hours

    def __init__(self):
        super().__init__()
        self.headers = {
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9,ko;q=0.8,ja;q=0.7,zh-CN;q=0.6",
        }
        self.timeout = 15.0

    async def run(self) -> None:
        # Fetch from all sources concurrently
        tasks = [
            self._fetch_foxwq(),
            self._fetch_yike_preparing(),
            self._fetch_yugen_schedule(),
            self._fetch_japanese(),
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        all_events = []
        for result in results:
            if isinstance(result, Exception):
                self.logger.error("Failed to fetch upcoming: %s", result)
            elif result:
                all_events.extend(result)

        if not all_events:
            self.logger.info("No upcoming events found from any source")
            return

        # Deduplicate by (tournament, date, player_black, player_white)
        seen = set()
        unique_events = []
        for event in sorted(all_events, key=lambda e: e["scheduled_time"]):
            key = (
                event["tournament"],
                event["scheduled_time"].date(),
                event.get("player_black") or "",
                event.get("player_white") or "",
            )
            if key not in seen:
                seen.add(key)
                unique_events.append(event)

        # Replace all existing upcoming events in DB
        db = SessionLocal()
        try:
            # Delete all existing
            deleted = db.query(UpcomingMatchDB).delete()

            # Insert new events
            for event in unique_events:
                db.add(UpcomingMatchDB(**event))

            db.commit()
            self.logger.info(
                "FetchUpcomingJob: replaced %d with %d upcoming events",
                deleted, len(unique_events)
            )
        except Exception:
            db.rollback()
            self.logger.exception("FetchUpcomingJob failed to save events")
        finally:
            db.close()

    async def _fetch_html(self, url: str) -> Optional[str]:
        """Fetch HTML content from a URL."""
        try:
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
                response = await client.get(url, headers=self.headers)
                response.raise_for_status()
                return response.text
        except Exception as e:
            self.logger.error("Failed to fetch %s: %s", url, e)
            return None

    # ── Source: FoxWQ (野狐围棋) ─────────────────────────────────

    async def _fetch_foxwq(self) -> list[dict]:
        """Fetch upcoming events from FoxWQ (野狐围棋).

        URL: https://www.foxwq.com
        Covers Chinese, Korean, and international tournaments.
        """
        url = "https://www.foxwq.com"
        events = []

        try:
            html = await self._fetch_html(url)
            if not html:
                return []

            soup = BeautifulSoup(html, "lxml")
            text = soup.get_text()

            # Pattern: "1月27日 10:30 赛事名 [选手VS选手]"
            # Note: The page text has no newlines, so we use lookahead to stop at the next date entry.
            # Players are optional and may contain numbers (e.g., "王硕94").
            pattern = re.compile(
                r"(\d{1,2})月(\d{1,2})日\s*(\d{1,2}):(\d{2})\s+"
                r"(.+?)"  # Tournament name (non-greedy)
                r"(?:"
                r"\s+([\u4e00-\u9fff\w]{2,10})\s*(?:VS|vs|对)\s*([\u4e00-\u9fff\w]{2,10})"  # Optional players
                r")?"
                r"(?=\d{1,2}月\d{1,2}日|Previous|Next|$)",  # Stop at next date, navigation, or end
                re.UNICODE,
            )

            now = datetime.now()
            for match in pattern.finditer(text):
                try:
                    month, day = int(match.group(1)), int(match.group(2))
                    hour, minute = int(match.group(3)), int(match.group(4))
                    tournament = match.group(5).strip()
                    player_black = match.group(6).strip() if match.group(6) else None
                    player_white = match.group(7).strip() if match.group(7) else None

                    year = now.year
                    if month < now.month - 6:
                        year += 1

                    scheduled_time = datetime(year, month, day, hour, minute)
                    if scheduled_time < now:
                        continue

                    event_id = f"foxwq_{tournament}_{scheduled_time.strftime('%Y%m%d%H%M')}"
                    events.append({
                        "event_id": event_id,
                        "tournament": tournament,
                        "round_name": None,
                        "scheduled_time": scheduled_time,
                        "player_black": player_black,
                        "player_white": player_white,
                        "source": "foxwq",
                        "source_url": url,
                    })
                except (ValueError, TypeError):
                    continue

            self.logger.info("Fetched %d upcoming events from FoxWQ", len(events))

        except Exception as e:
            self.logger.error("Failed to scrape FoxWQ: %s", e)

        return events

    # ── Source: YikeWeiQi preparing matches (弈客围棋 status=1) ──

    async def _fetch_yike_preparing(self) -> list[dict]:
        """Fetch preparing matches from YikeWeiQi (弈客围棋) as upcoming events.

        Uses the existing YikeWeiQiClient to query status=1 (preparing) matches.
        These are matches that have been scheduled but haven't started yet.
        """
        from katrain.cron import config
        if not config.YIKE_ENABLED:
            return []

        from katrain.cron.clients.yike import YikeWeiQiClient

        events = []
        client = YikeWeiQiClient()

        try:
            # status=1 means "preparing" (准备中), type=0 means professional
            data = await client._request("GET", "/v1/golives", params={
                "status": 1, "type": 0, "page": 1, "page_size": 50,
            })
            items = client._extract_data(data)

            for raw in items:
                try:
                    game_id = str(raw.get("id", ""))
                    if not game_id:
                        continue

                    tournament = raw.get("game_name") or ""
                    # Filter non-professional and test content
                    if any(kw in tournament for kw in client._NON_PRO_KEYWORDS):
                        continue
                    if tournament.lower().strip() in ("test", "测试"):
                        continue

                    player_black = raw.get("black_name") or (raw.get("black_player") or {}).get("player_name")
                    player_white = raw.get("white_name") or (raw.get("white_player") or {}).get("player_name")

                    # Parse scheduled time: combine game_date + broadcast_time
                    # game_date="2026-03-28", broadcast_time="13:00"
                    game_date_str = raw.get("game_date") or ""
                    broadcast_time_str = raw.get("broadcast_time") or ""

                    scheduled_time = None
                    if game_date_str:
                        try:
                            base_date = datetime.strptime(game_date_str[:10], "%Y-%m-%d")
                            # Try to add time from broadcast_time (could be "13:00" or "13:00:00")
                            time_match = re.match(r"(\d{1,2}):(\d{2})", broadcast_time_str)
                            if time_match:
                                base_date = base_date.replace(
                                    hour=int(time_match.group(1)),
                                    minute=int(time_match.group(2)),
                                )
                            scheduled_time = base_date
                        except (ValueError, IndexError):
                            pass

                    if not scheduled_time:
                        continue

                    # Only include future events
                    if scheduled_time < datetime.now():
                        continue

                    event_id = f"yike_{game_id}"
                    events.append({
                        "event_id": event_id,
                        "tournament": tournament,
                        "round_name": None,
                        "scheduled_time": scheduled_time,
                        "player_black": player_black,
                        "player_white": player_white,
                        "source": "yike",
                        "source_url": f"https://www.yikeweiqi.com/golive/{game_id}",
                    })
                except (ValueError, TypeError, KeyError):
                    continue

            self.logger.info("Fetched %d upcoming events from YikeWeiQi (preparing)", len(events))

        except Exception as e:
            self.logger.error("Failed to fetch YikeWeiQi preparing matches: %s", e)

        return events

    # ── Source: 幽玄の間 schedule (u-gen.nihonkiin.or.jp) ────────

    async def _fetch_yugen_schedule(self) -> list[dict]:
        """Fetch upcoming events from 幽玄の間 (Yugen no Ma) schedule page.

        URL: https://u-gen.nihonkiin.or.jp/live/schedule_list.asp
        Public page, no login required. Covers all Japanese professional tournaments.

        HTML structure: table with thead [日時, 棋戦名, 対局者(colspan=2)].
        Data rows have 4 cells: [date, tournament, player_black, player_white].
        Detail/expanded rows have more cells and should be skipped.
        """
        url = "https://u-gen.nihonkiin.or.jp/live/schedule_list.asp"
        events = []

        try:
            html = await self._fetch_html(url)
            if not html:
                return []

            soup = BeautifulSoup(html, "html.parser")

            # Find the schedule table (has thead with 棋戦名)
            target_table = None
            for table in soup.find_all("table"):
                thead = table.find("thead")
                if thead and "棋戦名" in thead.get_text():
                    target_table = table
                    break

            if not target_table:
                self.logger.warning("Yugen schedule table not found")
                return []

            now = datetime.now()
            rows = target_table.find_all("tr")

            for row in rows:
                tds = row.find_all("td")
                # Data rows have exactly 4 cells: [date, tournament, player_black, player_white]
                if len(tds) != 4:
                    continue

                texts = [td.get_text(strip=True) for td in tds]
                date_str, tournament, player_black_raw, player_white_raw = texts

                # Parse date: "2026/03/30"
                date_match = re.match(r"(\d{4})/(\d{2})/(\d{2})", date_str)
                if not date_match:
                    continue

                year = int(date_match.group(1))
                month = int(date_match.group(2))
                day = int(date_match.group(3))

                # Extract time from detail row (next sibling), default 10:00
                hour, minute = 10, 0
                next_row = row.find_next_sibling("tr")
                if next_row:
                    detail_text = next_row.get_text()
                    time_match = re.search(r"(\d{1,2}):(\d{2})～", detail_text)
                    if time_match:
                        hour = int(time_match.group(1))
                        minute = int(time_match.group(2))

                try:
                    scheduled_time = datetime(year, month, day, hour, minute)
                except ValueError:
                    continue

                if scheduled_time < now:
                    continue

                # Strip rank from player names (e.g. "高尾紳路九段" → "高尾紳路")
                player_black = _RANK_RE.sub("", player_black_raw).strip() or None
                player_white = _RANK_RE.sub("", player_white_raw).strip() or None

                event_id = f"yugen_{tournament}_{scheduled_time.strftime('%Y%m%d')}_{player_black_raw}"
                events.append({
                    "event_id": event_id,
                    "tournament": tournament,
                    "round_name": None,
                    "scheduled_time": scheduled_time,
                    "player_black": player_black,
                    "player_white": player_white,
                    "source": "yugen",
                    "source_url": url,
                })

            self.logger.info("Fetched %d upcoming events from Yugen (幽玄の間)", len(events))

        except Exception as e:
            self.logger.error("Failed to scrape Yugen schedule: %s", e)

        return events

    # ── Source: nihonkiin.or.jp 2-week schedule ──────────────────

    async def _fetch_japanese(self) -> list[dict]:
        """Fetch upcoming events from Japan Go Association (nihonkiin.or.jp).

        URL: https://www.nihonkiin.or.jp/match/2week.html
        """
        url = "https://www.nihonkiin.or.jp/match/2week.html"
        events = []

        try:
            html = await self._fetch_html(url)
            if not html:
                return []

            soup = BeautifulSoup(html, "lxml")
            tables = soup.select("table")

            current_date = None
            now = datetime.now()

            for table in tables:
                rows = table.find_all("tr")
                for row in rows:
                    cells = row.find_all(["td", "th"])
                    if not cells:
                        continue

                    text = " ".join(c.get_text(strip=True) for c in cells)

                    # Check for date header
                    date_match = re.search(r"(\d{1,2})月(\d{1,2})日", text)
                    if date_match:
                        month, day = int(date_match.group(1)), int(date_match.group(2))
                        year = now.year
                        if month < now.month - 6:
                            year += 1
                        current_date = datetime(year, month, day, 10, 0)
                        continue

                    if not current_date:
                        continue

                    # Look for tournament name
                    tournament = None
                    players_text = ""

                    for cell in cells:
                        cell_text = cell.get_text(strip=True)
                        if any(k in cell_text for k in ["戦", "杯", "棋聖", "名人", "本因坊", "リーグ", "予選"]):
                            tournament = cell_text
                        elif "vs" in cell_text.lower() or "対" in cell_text:
                            players_text = cell_text

                    if tournament and current_date >= now:
                        player_black, player_white = self._parse_players(players_text)

                        event_id = f"nihonkiin_{tournament}_{current_date.strftime('%Y%m%d')}"
                        events.append({
                            "event_id": event_id,
                            "tournament": tournament,
                            "round_name": None,
                            "scheduled_time": current_date,
                            "player_black": player_black,
                            "player_white": player_white,
                            "source": "nihonkiin",
                            "source_url": url,
                        })

            self.logger.info("Fetched %d upcoming events from Japan Go Association", len(events))

        except Exception as e:
            self.logger.error("Failed to scrape Japan Go Association: %s", e)

        return events

    # ── Helpers ───────────────────────────────────────────────────

    def _parse_players(self, text: str) -> tuple[Optional[str], Optional[str]]:
        """Parse player names from text like 'Player A vs Player B'."""
        if not text:
            return None, None

        for sep in [" vs ", " VS ", " v ", " 対 ", " - ", "vs", "對"]:
            if sep in text:
                parts = text.split(sep, 1)
                if len(parts) == 2:
                    black = re.sub(r"\s*\d+[段级]?\s*$", "", parts[0].strip())
                    white = re.sub(r"\s*\d+[段级]?\s*$", "", parts[1].strip())
                    return black or None, white or None

        return None, None
