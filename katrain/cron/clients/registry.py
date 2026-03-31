"""SourceRegistry: lightweight dispatcher for multi-source live match fetching."""

import logging
from typing import Optional

logger = logging.getLogger("katrain_cron.registry")


class SourceRegistry:
    """Routes fetch/poll operations to the appropriate source client.

    Each registered client must implement:
    - get_live_matches() -> list[dict]
    - parse_match_to_row(raw: dict) -> dict | None
    """

    def __init__(self):
        self._clients: dict[str, object] = {}

    def register(self, source_name: str, client: object):
        self._clients[source_name] = client

    def get_client(self, source_name: str) -> Optional[object]:
        return self._clients.get(source_name)

    @property
    def sources(self) -> list[str]:
        return list(self._clients.keys())

    async def fetch_all_matches(self) -> list[dict]:
        """Call get_live_matches() + get_finished_matches() on all registered clients, merge results."""
        all_rows: list[dict] = []
        for source_name, client in self._clients.items():
            try:
                raw_list = await client.get_live_matches()
                for raw in raw_list:
                    row = client.parse_match_to_row(raw)
                    if row:
                        all_rows.append(row)
                logger.debug("Fetched %d live matches from %s", len(raw_list), source_name)
            except Exception:
                logger.exception("Failed to fetch live matches from %s", source_name)

            # Also fetch recent finished matches (for history)
            if hasattr(client, "get_history"):
                try:
                    history = await client.get_history()
                    for raw in history:
                        row = client.parse_match_to_row(raw)
                        if row:
                            all_rows.append(row)
                except Exception:
                    logger.exception("Failed to fetch history from %s", source_name)
            elif hasattr(client, "get_finished_matches"):
                try:
                    finished = await client.get_finished_matches()
                    for raw in finished:
                        row = client.parse_match_to_row(raw)
                        if row:
                            all_rows.append(row)
                except Exception:
                    logger.exception("Failed to fetch finished matches from %s", source_name)

        return all_rows
