"""FetchUpcomingJob: scrape upcoming matches from FoxWQ and Japan Go Association."""

import asyncio
import logging
import re
from datetime import datetime
from typing import Optional

import httpx
from bs4 import BeautifulSoup

from katrain.cron.jobs.base import BaseJob
from katrain.cron.db import SessionLocal
from katrain.cron.models import UpcomingMatchDB

logger = logging.getLogger("katrain_cron.fetch_upcoming")

# User-Agent for web scraping
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"


class FetchUpcomingJob(BaseJob):
    """Scrape upcoming Go tournament events from official sources.

    Sources:
    - 野狐围棋 (foxwq.com) - Covers Chinese, Korean, and international tournaments
    - 日本棋院 (nihonkiin.or.jp) - Japanese tournaments

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

        # Deduplicate by (tournament, date)
        seen = set()
        unique_events = []
        for event in sorted(all_events, key=lambda e: e["scheduled_time"]):
            key = (event["tournament"], event["scheduled_time"].date())
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

            # Pattern: "1月27日 10:30 赛事名 选手VS选手"
            pattern = re.compile(
                r"(\d{1,2})月(\d{1,2})日\s*(\d{1,2}):(\d{2})\s+"
                r"([^\n]+?)\s+"
                r"([\u4e00-\u9fff]{2,5})\s*(?:VS|vs|对)\s*([\u4e00-\u9fff]{2,5})",
                re.UNICODE,
            )

            for match in pattern.finditer(text):
                try:
                    month, day = int(match.group(1)), int(match.group(2))
                    hour, minute = int(match.group(3)), int(match.group(4))
                    tournament = match.group(5).strip()
                    player_black = match.group(6).strip()
                    player_white = match.group(7).strip()

                    year = datetime.now().year
                    if month < datetime.now().month - 6:
                        year += 1

                    scheduled_time = datetime(year, month, day, hour, minute)
                    if scheduled_time < datetime.now():
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

            # Also look for tournament-only entries (no players)
            pattern_no_players = re.compile(
                r"(\d{1,2})月(\d{1,2})日\s*(\d{1,2}):(\d{2})\s+([^\n]+?)(?:\n|$)",
                re.UNICODE,
            )

            for match in pattern_no_players.finditer(text):
                try:
                    month, day = int(match.group(1)), int(match.group(2))
                    hour, minute = int(match.group(3)), int(match.group(4))
                    tournament = match.group(5).strip()

                    if "VS" in tournament or "vs" in tournament or "对" in tournament:
                        continue

                    year = datetime.now().year
                    if month < datetime.now().month - 6:
                        year += 1

                    scheduled_time = datetime(year, month, day, hour, minute)
                    if scheduled_time < datetime.now():
                        continue

                    event_id = f"foxwq_{tournament}_{scheduled_time.strftime('%Y%m%d%H%M')}"
                    if any(e["event_id"] == event_id for e in events):
                        continue

                    events.append({
                        "event_id": event_id,
                        "tournament": tournament,
                        "round_name": None,
                        "scheduled_time": scheduled_time,
                        "player_black": None,
                        "player_white": None,
                        "source": "foxwq",
                        "source_url": url,
                    })
                except (ValueError, TypeError):
                    continue

            self.logger.info("Fetched %d upcoming events from FoxWQ", len(events))

        except Exception as e:
            self.logger.error("Failed to scrape FoxWQ: %s", e)

        return events

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
                        year = datetime.now().year
                        if month < datetime.now().month - 6:
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

                    if tournament and current_date >= datetime.now():
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
