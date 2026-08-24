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
        """Merged rows only. Kept for callers that do not need per-source liveness."""
        rows, _ = await self.fetch_all_matches_with_liveness()
        return rows

    async def fetch_all_matches_with_liveness(self) -> tuple[list[dict], dict[str, set[str]]]:
        """Fetch every source, and report **which sources actually answered** the live query.

        Returns ``(rows, live_ids_by_source)``.

        ``live_ids_by_source`` carries the distinction that matters downstream:

        * key **present** (even mapped to an empty set) ⇒ that source answered, and this is
          its complete list of currently-live match ids. An empty set is a real answer
          ("nothing is live right now"), not an absence of one.
        * key **absent** ⇒ the live query failed for that source. Callers must not conclude
          anything about its matches — in particular they must not mark them finished.

        The old flat-list return could not tell those two apart: a failed fetch and a
        genuinely empty upstream both showed up as "no rows for this source", which is why
        matches that ended stayed marked live forever (nothing dared demote them) while a
        transient outage looked identical to an empty schedule.
        """
        all_rows: list[dict] = []
        live_ids_by_source: dict[str, set[str]] = {}
        for source_name, client in self._clients.items():
            try:
                raw_list = await client.get_live_matches()
                live_ids: set[str] = set()
                for raw in raw_list:
                    row = client.parse_match_to_row(raw)
                    if row:
                        all_rows.append(row)
                        if row.get("status") == "live":
                            live_ids.add(row["match_id"])
                # Only recorded on success — see the docstring.
                live_ids_by_source[source_name] = live_ids
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

        return all_rows, live_ids_by_source
