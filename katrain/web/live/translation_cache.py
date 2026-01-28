"""In-memory translation cache, refreshed from the database periodically.

Replaces on-demand LLM translation with pre-computed lookups.
katrain-cron populates the DB; this cache reads it.
"""

import asyncio
import logging
from typing import Optional

logger = logging.getLogger("katrain_web.live.translation_cache")

LANGUAGES = ("en", "cn", "tw", "jp", "ko")

# Refresh interval
_REFRESH_INTERVAL = 60  # seconds


class TranslationCache:
    """Fast in-memory cache for player and tournament translations.

    Data flow:
        katrain-cron (LLM + search) → PostgreSQL → TranslationCache → API responses
    """

    def __init__(self):
        # {canonical_name -> {lang -> translated_name}}
        self._players: dict[str, dict[str, Optional[str]]] = {}
        # {original_name -> {lang -> translated_name}}
        self._tournaments: dict[str, dict[str, Optional[str]]] = {}

        self._loaded = False
        self._refresh_task: Optional[asyncio.Task] = None

    # ── Lifecycle ──────────────────────────────────────────────

    async def start(self) -> None:
        """Initial load + start background refresh."""
        await self._load_from_db()
        self._refresh_task = asyncio.create_task(self._refresh_loop())
        logger.info(
            "TranslationCache started: %d players, %d tournaments",
            len(self._players),
            len(self._tournaments),
        )

    async def stop(self) -> None:
        """Stop background refresh."""
        if self._refresh_task and not self._refresh_task.done():
            self._refresh_task.cancel()
            try:
                await self._refresh_task
            except asyncio.CancelledError:
                pass

    async def _refresh_loop(self) -> None:
        while True:
            try:
                await asyncio.sleep(_REFRESH_INTERVAL)
                await self._load_from_db()
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("TranslationCache refresh error")
                await asyncio.sleep(_REFRESH_INTERVAL)

    async def _load_from_db(self) -> None:
        """Load all translations from DB into memory."""
        from katrain.web.core.db import SessionLocal
        from katrain.web.core.models_db import PlayerTranslationDB, TournamentTranslationDB

        try:
            with SessionLocal() as db:
                # Players
                players: dict[str, dict[str, Optional[str]]] = {}
                for row in db.query(PlayerTranslationDB).all():
                    players[row.canonical_name] = {
                        lang: getattr(row, lang, None) for lang in LANGUAGES
                    }

                # Tournaments
                tournaments: dict[str, dict[str, Optional[str]]] = {}
                for row in db.query(TournamentTranslationDB).all():
                    tournaments[row.original] = {
                        lang: getattr(row, lang, None) for lang in LANGUAGES
                    }

            # Swap atomically
            self._players = players
            self._tournaments = tournaments
            self._loaded = True
        except Exception:
            logger.exception("Failed to load translations from DB")

    # ── Lookups ────────────────────────────────────────────────

    def translate_player(self, name: str, lang: str) -> str:
        """Translate a player name. Returns original if no translation."""
        entry = self._players.get(name)
        if entry:
            translated = entry.get(lang)
            if translated:
                return translated
        return name

    def translate_tournament(self, name: str, lang: str) -> str:
        """Translate a tournament name. Returns original if no translation."""
        entry = self._tournaments.get(name)
        if entry:
            translated = entry.get(lang)
            if translated:
                return translated
        return name

    def get_player_translations(self, name: str) -> Optional[dict[str, Optional[str]]]:
        """Get all translations for a player (all languages)."""
        return self._players.get(name)

    def get_all_translations(self, lang: str) -> dict:
        """Get all translations for a language, suitable for frontend caching."""
        players = {}
        for name, translations in self._players.items():
            translated = translations.get(lang)
            if translated:
                players[name] = translated

        tournaments = {}
        for name, translations in self._tournaments.items():
            translated = translations.get(lang)
            if translated:
                tournaments[name] = translated

        return {
            "players": players,
            "tournaments": tournaments,
        }

    @property
    def stats(self) -> dict:
        return {
            "players": len(self._players),
            "tournaments": len(self._tournaments),
            "loaded": self._loaded,
        }
