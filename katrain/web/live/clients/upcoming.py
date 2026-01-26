"""Upcoming Events Scraper for Go tournament schedules.

Sources:
- 日本棋院 (nihonkiin.or.jp) - 対局予定
- 野狐围棋 (foxwq.com) - 直播预告 (includes Chinese, Korean, and international tournaments)

These are scraped via HTML parsing since no official APIs exist.
Note: Some official association sites (baduk.or.kr, weiqi.org.cn) use JavaScript rendering
which requires a headless browser. FoxWQ provides static HTML with comprehensive coverage.
"""

import asyncio
import logging
import re
from datetime import datetime
from typing import Optional

import httpx
from bs4 import BeautifulSoup

from katrain.web.live.models import UpcomingMatch

logger = logging.getLogger("katrain_web.live.upcoming")


class UpcomingScraper:
    """Scraper for upcoming Go tournament events from official sources."""

    def __init__(self, timeout: float = 15.0):
        self.timeout = timeout
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9,ko;q=0.8,ja;q=0.7,zh-CN;q=0.6",
        }

    async def fetch_all(self) -> list[UpcomingMatch]:
        """Fetch upcoming events from all sources."""
        results = []

        # Fetch from all sources concurrently
        tasks = [
            self._fetch_japanese(),
            self._fetch_foxwq(),  # Covers Chinese, Korean, and international tournaments
        ]

        fetched = await asyncio.gather(*tasks, return_exceptions=True)

        for source_result in fetched:
            if isinstance(source_result, Exception):
                logger.error(f"Failed to fetch upcoming events: {source_result}")
            elif source_result:
                results.extend(source_result)

        # Sort by scheduled time
        results.sort(key=lambda m: m.scheduled_time)

        # Remove duplicates (same tournament + same date)
        seen = set()
        unique = []
        for m in results:
            key = (m.tournament, m.scheduled_time.date())
            if key not in seen:
                seen.add(key)
                unique.append(m)

        logger.info(f"Fetched {len(unique)} unique upcoming events from all sources")
        return unique

    async def _fetch_html(self, url: str) -> Optional[str]:
        """Fetch HTML content from a URL."""
        try:
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
                response = await client.get(url, headers=self.headers)
                response.raise_for_status()
                return response.text
        except Exception as e:
            logger.error(f"Failed to fetch {url}: {e}")
            return None

    async def _fetch_foxwq(self) -> list[UpcomingMatch]:
        """Fetch upcoming events from FoxWQ (野狐围棋).

        URL: https://www.foxwq.com
        This source covers Chinese, Korean, and international tournaments.
        The 直播预告 section lists upcoming matches with dates and times.
        """
        url = "https://www.foxwq.com"
        matches = []

        try:
            html = await self._fetch_html(url)
            if not html:
                return []

            soup = BeautifulSoup(html, "lxml")

            # Find the 直播预告 section
            # Look for text that contains schedule entries with the pattern:
            # "月日 时:分 赛事名 选手VS选手"

            # Get all text content
            text = soup.get_text()

            # Pattern: "1月27日 10:30 赛事名 选手VS选手"
            # or "1月27日10:30 赛事名 选手VS选手"
            # Player names are typically 2-4 Chinese characters, no digits
            pattern = re.compile(
                r"(\d{1,2})月(\d{1,2})日\s*(\d{1,2}):(\d{2})\s+"  # Date and time
                r"([^\n]+?)\s+"  # Tournament name
                r"([\u4e00-\u9fff]{2,5})\s*(?:VS|vs|对)\s*([\u4e00-\u9fff]{2,5})",  # Players (2-5 Chinese chars)
                re.UNICODE,
            )

            for match in pattern.finditer(text):
                try:
                    month = int(match.group(1))
                    day = int(match.group(2))
                    hour = int(match.group(3))
                    minute = int(match.group(4))
                    tournament = match.group(5).strip()
                    player_black = match.group(6).strip()
                    player_white = match.group(7).strip()

                    # Determine year
                    year = datetime.now().year
                    if month < datetime.now().month - 6:
                        year += 1

                    scheduled_time = datetime(year, month, day, hour, minute)

                    # Only include future events
                    if scheduled_time < datetime.now():
                        continue

                    upcoming = UpcomingMatch(
                        id=f"foxwq_{tournament}_{scheduled_time.strftime('%Y%m%d%H%M')}",
                        tournament=tournament,
                        round_name=None,
                        scheduled_time=scheduled_time,
                        player_black=player_black,
                        player_white=player_white,
                        source_url=url,
                    )
                    matches.append(upcoming)

                except (ValueError, TypeError) as e:
                    logger.debug(f"Failed to parse FoxWQ entry: {e}")
                    continue

            # Also look for entries without player names (tournament-only)
            pattern_no_players = re.compile(
                r"(\d{1,2})月(\d{1,2})日\s*(\d{1,2}):(\d{2})\s+"  # Date and time
                r"([^\n]+?)(?:\n|$)",  # Tournament name
                re.UNICODE,
            )

            for match in pattern_no_players.finditer(text):
                try:
                    month = int(match.group(1))
                    day = int(match.group(2))
                    hour = int(match.group(3))
                    minute = int(match.group(4))
                    tournament = match.group(5).strip()

                    # Skip if tournament name looks like it has VS (already captured above)
                    if "VS" in tournament or "vs" in tournament or "对" in tournament:
                        continue

                    year = datetime.now().year
                    if month < datetime.now().month - 6:
                        year += 1

                    scheduled_time = datetime(year, month, day, hour, minute)

                    # Only include future events
                    if scheduled_time < datetime.now():
                        continue

                    # Check for duplicates
                    match_id = f"foxwq_{tournament}_{scheduled_time.strftime('%Y%m%d%H%M')}"
                    if any(m.id == match_id for m in matches):
                        continue

                    upcoming = UpcomingMatch(
                        id=match_id,
                        tournament=tournament,
                        round_name=None,
                        scheduled_time=scheduled_time,
                        player_black=None,
                        player_white=None,
                        source_url=url,
                    )
                    matches.append(upcoming)

                except (ValueError, TypeError) as e:
                    logger.debug(f"Failed to parse FoxWQ entry: {e}")
                    continue

            logger.info(f"Fetched {len(matches)} upcoming events from FoxWQ")

        except Exception as e:
            logger.error(f"Failed to scrape FoxWQ: {e}")

        return matches

    async def _fetch_japanese(self) -> list[UpcomingMatch]:
        """Fetch upcoming events from Japan Go Association (nihonkiin.or.jp).

        URL: https://www.nihonkiin.or.jp/match/2week.html
        """
        url = "https://www.nihonkiin.or.jp/match/2week.html"
        matches = []

        try:
            html = await self._fetch_html(url)
            if not html:
                return []

            soup = BeautifulSoup(html, "lxml")

            # Find schedule entries - typically in a table or list format
            # The page shows matches for the next 2 weeks
            tables = soup.select("table")

            current_date = None

            for table in tables:
                rows = table.find_all("tr")
                for row in rows:
                    cells = row.find_all(["td", "th"])
                    if not cells:
                        continue

                    text = " ".join(c.get_text(strip=True) for c in cells)

                    # Check if this row contains a date header
                    date_match = re.search(r"(\d{1,2})月(\d{1,2})日", text)
                    if date_match:
                        month = int(date_match.group(1))
                        day = int(date_match.group(2))
                        year = datetime.now().year
                        # Handle year rollover
                        if month < datetime.now().month - 6:
                            year += 1
                        current_date = datetime(year, month, day, 10, 0)  # Default 10:00
                        continue

                    if not current_date:
                        continue

                    # Look for tournament name in cells
                    tournament = None
                    players_text = ""

                    for cell in cells:
                        cell_text = cell.get_text(strip=True)
                        # Tournament names often contain 戦, 杯, 棋聖, 名人, 本因坊, etc.
                        if any(k in cell_text for k in ["戦", "杯", "棋聖", "名人", "本因坊", "リーグ", "予選"]):
                            tournament = cell_text
                        elif "vs" in cell_text.lower() or "対" in cell_text:
                            players_text = cell_text

                    if tournament and current_date >= datetime.now():
                        player_black, player_white = self._parse_players(players_text)

                        match = UpcomingMatch(
                            id=f"japan_{tournament}_{current_date.strftime('%Y%m%d')}",
                            tournament=tournament,
                            round_name=None,
                            scheduled_time=current_date,
                            player_black=player_black,
                            player_white=player_white,
                            source_url=url,
                        )
                        matches.append(match)

            logger.info(f"Fetched {len(matches)} upcoming events from Japan Go Association")

        except Exception as e:
            logger.error(f"Failed to scrape Japan Go Association: {e}")

        return matches

    def _parse_players(self, text: str) -> tuple[Optional[str], Optional[str]]:
        """Parse player names from text like 'Player A vs Player B'."""
        if not text:
            return None, None

        # Common separators
        for sep in [" vs ", " VS ", " v ", " 対 ", " - ", "vs", "對"]:
            if sep in text:
                parts = text.split(sep, 1)
                if len(parts) == 2:
                    black = parts[0].strip()
                    white = parts[1].strip()
                    # Clean up rank suffixes
                    black = re.sub(r"\s*\d+[段级]?\s*$", "", black)
                    white = re.sub(r"\s*\d+[段级]?\s*$", "", white)
                    return black or None, white or None

        return None, None
