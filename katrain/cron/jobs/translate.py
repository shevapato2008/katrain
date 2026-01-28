"""TranslateJob: scan for missing translations, call search+LLM."""

import logging

from katrain.cron.jobs.base import BaseJob
from katrain.cron.db import SessionLocal
from katrain.cron.models import PlayerTranslationDB, TournamentTranslationDB, LiveMatchDB
from katrain.cron.translator import Translator, LANGUAGES

logger = logging.getLogger("katrain_cron.translate")


class TranslateJob(BaseJob):
    name = "translate"
    interval_seconds = 120

    def __init__(self):
        super().__init__()
        self._translator = Translator()
        self._consecutive_failures = 0
        self._cooldown_cycles = 0  # Circuit breaker

    async def run(self) -> None:
        # Circuit breaker: skip if in cooldown
        if self._cooldown_cycles > 0:
            self._cooldown_cycles -= 1
            self.logger.info("TranslateJob in cooldown, %d cycles remaining", self._cooldown_cycles)
            return

        db = SessionLocal()
        try:
            await self._translate_players(db)
            await self._translate_tournaments(db)
        except Exception:
            self.logger.exception("TranslateJob failed")
            self._consecutive_failures += 1
            if self._consecutive_failures >= 3:
                self._cooldown_cycles = 2  # Skip ~4 min (2 * 120s)
                self.logger.warning("Circuit breaker triggered: 3 consecutive failures, cooling down")
        else:
            self._consecutive_failures = 0
        finally:
            db.close()

    async def _translate_players(self, db) -> None:
        """Find untranslated player names from live matches and translate them."""
        # Collect unique player names from all matches
        matches = db.query(LiveMatchDB.player_black, LiveMatchDB.player_white).all()
        all_names = set()
        for black, white in matches:
            all_names.add(black)
            all_names.add(white)

        if not all_names:
            return

        # Find names missing translations (skip source=manual)
        for name in all_names:
            existing = db.query(PlayerTranslationDB).filter(PlayerTranslationDB.canonical_name == name).first()

            if existing and existing.source == "manual":
                continue  # Never overwrite manual corrections

            # Check if any language is missing
            needs_translation = existing is None or any(getattr(existing, lang) is None for lang in LANGUAGES)
            if not needs_translation:
                continue

            self.logger.info("Translating player: %s", name)
            try:
                result = await self._translator.translate_player(name)
            except Exception:
                self.logger.exception("Failed to translate player %s", name)
                self._consecutive_failures += 1
                if self._consecutive_failures >= 3:
                    raise  # Trigger circuit breaker
                continue

            if existing:
                # Only fill in missing languages
                for lang in LANGUAGES:
                    if getattr(existing, lang) is None and result.get(lang):
                        setattr(existing, lang, result[lang])
                existing.source = result.get("source", existing.source)
                existing.llm_model = result.get("llm_model")
            else:
                db.add(PlayerTranslationDB(
                    canonical_name=name,
                    en=result.get("en"),
                    cn=result.get("cn"),
                    tw=result.get("tw"),
                    jp=result.get("jp"),
                    ko=result.get("ko"),
                    source=result.get("source", "llm"),
                    llm_model=result.get("llm_model"),
                ))
            db.commit()

    async def _translate_tournaments(self, db) -> None:
        """Find untranslated tournament names and translate them."""
        tournaments = db.query(LiveMatchDB.tournament).distinct().all()
        names = {t[0] for t in tournaments if t[0]}

        for name in names:
            existing = db.query(TournamentTranslationDB).filter(TournamentTranslationDB.original == name).first()

            if existing and existing.source == "manual":
                continue

            needs_translation = existing is None or any(getattr(existing, lang) is None for lang in LANGUAGES)
            if not needs_translation:
                continue

            self.logger.info("Translating tournament: %s", name)
            try:
                result = await self._translator.translate_tournament(name)
            except Exception:
                self.logger.exception("Failed to translate tournament %s", name)
                self._consecutive_failures += 1
                if self._consecutive_failures >= 3:
                    raise
                continue

            if existing:
                for lang in LANGUAGES:
                    if getattr(existing, lang) is None and result.get(lang):
                        setattr(existing, lang, result[lang])
                existing.source = result.get("source", existing.source)
                existing.llm_model = result.get("llm_model")
            else:
                db.add(TournamentTranslationDB(
                    original=name,
                    en=result.get("en"),
                    cn=result.get("cn"),
                    tw=result.get("tw"),
                    jp=result.get("jp"),
                    ko=result.get("ko"),
                    source=result.get("source", "llm"),
                    llm_model=result.get("llm_model"),
                ))
            db.commit()
