"""Upcoming Events Scraper for official Go association websites.

Sources:
- 韩国棋院 (baduk.or.kr) - 대국일정
- 日本棋院 (nihonkiin.or.jp) - 対局予定
- 中国围棋协会 (weiqi.org.cn) - 赛事日历

These are scraped via HTML parsing since no official APIs exist.
"""

import asyncio
import logging
import re
from datetime import datetime, timedelta
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
            self._fetch_korean(),
            self._fetch_japanese(),
            self._fetch_chinese(),
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

    async def _fetch_korean(self) -> list[UpcomingMatch]:
        """Fetch upcoming events from Korean Baduk Association (baduk.or.kr).

        URL: https://www.baduk.or.kr/record/schedule.asp
        """
        url = "https://www.baduk.or.kr/record/schedule.asp"
        matches = []

        try:
            html = await self._fetch_html(url)
            if not html:
                return []

            soup = BeautifulSoup(html, "lxml")

            # Find schedule table rows
            # The page typically has a table with columns: 일자(Date), 대회명(Tournament), 대국자(Players)
            rows = soup.select("table tr")

            for row in rows:
                cells = row.find_all("td")
                if len(cells) < 3:
                    continue

                try:
                    # Parse date (format varies: YYYY.MM.DD or MM/DD)
                    date_text = cells[0].get_text(strip=True)
                    tournament = cells[1].get_text(strip=True)
                    players_text = cells[2].get_text(strip=True) if len(cells) > 2 else ""

                    if not date_text or not tournament:
                        continue

                    # Skip header rows
                    if "일자" in date_text or "대회" in tournament:
                        continue

                    # Parse date
                    scheduled_time = self._parse_korean_date(date_text)
                    if not scheduled_time:
                        continue

                    # Only include future events
                    if scheduled_time < datetime.now():
                        continue

                    # Parse players if available
                    player_black, player_white = self._parse_players(players_text)

                    match = UpcomingMatch(
                        id=f"korea_{tournament}_{scheduled_time.strftime('%Y%m%d')}",
                        tournament=tournament,
                        round_name=None,
                        scheduled_time=scheduled_time,
                        player_black=player_black,
                        player_white=player_white,
                        source_url=url,
                    )
                    matches.append(match)

                except Exception as e:
                    logger.debug(f"Failed to parse Korean row: {e}")
                    continue

            logger.info(f"Fetched {len(matches)} upcoming events from Korean Baduk Association")

        except Exception as e:
            logger.error(f"Failed to scrape Korean Baduk Association: {e}")

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

    async def _fetch_chinese(self) -> list[UpcomingMatch]:
        """Fetch upcoming events from Chinese Go Association (weiqi.org.cn).

        Note: The Chinese Go Association website structure may vary.
        We try to find the event calendar or schedule page.
        """
        # Try multiple potential URLs
        urls = [
            "https://www.weiqi.org.cn/",
            "https://www.cwql.org.cn/",  # Chinese Go A-League
        ]

        matches = []

        for url in urls:
            try:
                html = await self._fetch_html(url)
                if not html:
                    continue

                soup = BeautifulSoup(html, "lxml")

                # Look for schedule/calendar links or sections
                # Chinese sites often have 赛程, 日程, 比赛安排 etc.
                schedule_keywords = ["赛程", "日程", "比赛", "对阵", "安排"]

                # Find links that might lead to schedules
                for link in soup.find_all("a", href=True):
                    link_text = link.get_text(strip=True)
                    if any(k in link_text for k in schedule_keywords):
                        logger.debug(f"Found potential schedule link: {link_text} -> {link['href']}")

                # Look for tournament announcements in the main content
                # These often contain dates and tournament names
                for article in soup.select("article, .news-item, .list-item, li"):
                    text = article.get_text(strip=True)

                    # Look for date patterns
                    date_match = re.search(r"(\d{4})年(\d{1,2})月(\d{1,2})日", text)
                    if not date_match:
                        date_match = re.search(r"(\d{1,2})月(\d{1,2})日", text)

                    if date_match:
                        try:
                            if len(date_match.groups()) == 3:
                                year, month, day = map(int, date_match.groups())
                            else:
                                month, day = map(int, date_match.groups())
                                year = datetime.now().year
                                if month < datetime.now().month - 6:
                                    year += 1

                            scheduled_time = datetime(year, month, day, 10, 0)

                            # Only future events
                            if scheduled_time < datetime.now():
                                continue

                            # Extract tournament name (look for common patterns)
                            tournament_match = re.search(
                                r"([\u4e00-\u9fff]+(?:杯|赛|战|联赛|锦标赛|公开赛|名人战|棋圣战))",
                                text,
                            )
                            if tournament_match:
                                tournament = tournament_match.group(1)

                                match = UpcomingMatch(
                                    id=f"china_{tournament}_{scheduled_time.strftime('%Y%m%d')}",
                                    tournament=tournament,
                                    round_name=None,
                                    scheduled_time=scheduled_time,
                                    player_black=None,
                                    player_white=None,
                                    source_url=url,
                                )
                                matches.append(match)

                        except (ValueError, TypeError):
                            continue

            except Exception as e:
                logger.error(f"Failed to scrape {url}: {e}")

        logger.info(f"Fetched {len(matches)} upcoming events from Chinese sources")
        return matches

    def _parse_korean_date(self, date_text: str) -> Optional[datetime]:
        """Parse Korean date format."""
        try:
            # Try YYYY.MM.DD format
            match = re.search(r"(\d{4})\.(\d{1,2})\.(\d{1,2})", date_text)
            if match:
                year, month, day = map(int, match.groups())
                return datetime(year, month, day, 10, 0)

            # Try MM/DD format
            match = re.search(r"(\d{1,2})/(\d{1,2})", date_text)
            if match:
                month, day = map(int, match.groups())
                year = datetime.now().year
                if month < datetime.now().month - 6:
                    year += 1
                return datetime(year, month, day, 10, 0)

            # Try MM.DD format
            match = re.search(r"(\d{1,2})\.(\d{1,2})", date_text)
            if match:
                month, day = map(int, match.groups())
                year = datetime.now().year
                if month < datetime.now().month - 6:
                    year += 1
                return datetime(year, month, day, 10, 0)

        except (ValueError, TypeError):
            pass

        return None

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
