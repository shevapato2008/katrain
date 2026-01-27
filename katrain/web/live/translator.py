"""Translation service for live broadcasting module.

Provides translation of player names, tournament names, and round names
for the live broadcasting feature.

Translation priority:
1. Static JSON files (players.json, tournaments.json)
2. Database cache (PlayerTranslationDB, TournamentTranslationDB)
3. LLM fallback (generate translation and store in DB)
"""

import json
import logging
import re
from datetime import datetime
from difflib import SequenceMatcher
from functools import lru_cache
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

logger = logging.getLogger("katrain_web.live.translator")


# LLM translation prompts by name type
PLAYER_TRANSLATION_PROMPT = """Translate this Go player name to {lang}:
Name: {name}

Follow these conventions:
- Chinese names to English: Use pinyin without tones (e.g., 柯洁 → Ke Jie)
- Chinese names to Japanese: Use katakana with middle dot (e.g., 柯洁 → カ・ケツ)
- Chinese names to Korean: Use hangul reading (e.g., 柯洁 → 커제)
- Japanese names to English: Use romaji, surname first (e.g., 井山裕太 → Iyama Yuta)
- Japanese names to Chinese: Keep kanji if same
- Korean names to English: Use revised romanization (e.g., 신진서 → Shin Jinseo)

Return ONLY the translated name, nothing else."""

TOURNAMENT_TRANSLATION_PROMPT = """Translate this Go tournament name to {lang}:
Name: {name}

{lang_guidelines}

Return ONLY the translated name, nothing else."""

TOURNAMENT_LANG_GUIDELINES = {
    "English": """Guidelines for English:
- Use official English names when known (棋聖戦 → Kisei, 天元战 → Tengen)
- For editions: 第52期 → 52nd, 27届 → 27th
- Translate 战/杯/赛 as Tournament/Cup/Match""",
    "Simplified Chinese": """Guidelines for Simplified Chinese:
- Keep in simplified Chinese characters
- Preserve original Chinese tournament names
- For Korean/Japanese tournaments, translate to Chinese: 기성전 → 棋圣战, 棋聖戦 → 棋圣战
- Keep edition format: 第N期, 第N届""",
    "Traditional Chinese": """Guidelines for Traditional Chinese:
- Convert to traditional Chinese characters: 战→戰, 预选→預選, 围棋→圍棋
- For Korean/Japanese tournaments, translate to traditional Chinese
- Keep edition format: 第N期, 第N屆""",
    "Japanese": """Guidelines for Japanese:
- Use Japanese kanji where different from simplified Chinese: 战→戦, 围→囲, 预→予
- Use katakana for foreign proper nouns
- Keep edition format: 第N期, 第N回
- For known tournaments use Japanese names: 天元戦, 名人戦, 棋聖戦""",
    "Korean": """Guidelines for Korean:
- Use Korean reading in hangul: 天元战 → 천원전, 名人战 → 명인전
- For editions: 第N期 → 제N기, N届 → 제N회
- Translate fully to Korean""",
}


# Simplified Chinese to Japanese kanji conversion table
# Used for automatic fallback when no Japanese translation exists
SIMPLIFIED_TO_JAPANESE_KANJI = {
    # Common Go tournament terms
    "战": "戦",  # war/battle
    "围": "囲",  # surround (围棋 → 囲碁)
    "棋": "碁",  # Go game (when used alone or in 围棋)
    "预": "予",  # preliminary
    "选": "選",  # select
    "赛": "戦",  # match/competition
    "组": "組",  # group
    "轮": "ラウンド",  # round (use katakana)
    "届": "回",  # edition/session
    "圈": "圏",  # circle/league
    "环": "環",  # ring/circle
    "决": "決",  # final/decisive
    "胜": "勝",  # win
    "负": "敗",  # lose
    "对": "対",  # versus
    "场": "場",  # place/field
    "阶": "階",  # stage
    "强": "強",  # strong (e.g., 32強 = top 32)
    "级": "級",  # rank/class
    "队": "チーム",  # team
    "势": "勢",  # power/momentum
    "怀": "懐",  # embrace
    "酱": "醤",  # sauce
    "聂": "聶",  # surname Nie
    "纯": "純",  # pure
    "维": "維",  # maintain
    "华": "華",  # splendid/China
    "国": "国",  # country (same in Japanese)
    # Common place names
    "韩国": "韓国",
    "贵州": "貴州",
    "广东": "広東",
    "浙江": "浙江",
    "厦门": "厦門",
    "深圳": "深圳",  # Shenzhen (same)
    # Other common characters
    "历": "歴",  # history
    "与": "与",  # and (same)
    "会": "会",  # association (same)
}


def convert_simplified_to_japanese(text: str) -> str:
    """Convert simplified Chinese characters to Japanese kanji equivalents.

    This provides a reasonable fallback when no Japanese translation exists.
    The conversion handles common Go tournament terminology.

    Args:
        text: Text with simplified Chinese characters

    Returns:
        Text with Japanese kanji equivalents
    """
    result = text
    for cn, jp in SIMPLIFIED_TO_JAPANESE_KANJI.items():
        result = result.replace(cn, jp)
    return result


class LiveTranslator:
    """Translates player names, tournament names, and round names.

    Uses database as the primary translation source with LLM fallback
    for unknown names.

    Translation priority:
    1. Database lookup
    2. LLM fallback (if enabled, stores result in DB)
    """

    DEFAULT_LANG = "en"
    SUPPORTED_LANGS = {"en", "cn", "tw", "jp", "ko"}

    def __init__(self, enable_llm: bool = True):
        """Initialize the translator.

        Args:
            enable_llm: Whether to use LLM for unknown translations
        """
        self._enable_llm = enable_llm
        self._db_session: Optional[Session] = None
        self._player_index: dict[str, str] = {}  # alias -> canonical name (built from DB)
        self._index_built = False

    def _build_player_index(self) -> None:
        """Build player alias index from database for fast lookup."""
        if self._index_built:
            return
        try:
            session = self._get_db_session()
            if not session:
                return

            from katrain.web.core.models_db import PlayerTranslationDB
            players = session.query(PlayerTranslationDB).all()

            for player in players:
                # Index canonical name
                self._player_index[player.canonical_name.lower()] = player.canonical_name
                # Index aliases
                if player.aliases:
                    for alias in player.aliases:
                        self._player_index[alias.lower()] = player.canonical_name

            self._index_built = True
            logger.info(f"Built player index with {len(players)} players")
        except Exception as e:
            logger.error(f"Failed to build player index: {e}")

    def _normalize_lang(self, lang: str) -> str:
        """Normalize language code."""
        lang = lang.lower()
        if lang in self.SUPPORTED_LANGS:
            return lang
        # Map common variations
        if lang in ("zh", "zh-cn", "zh_cn", "chinese"):
            return "cn"
        if lang in ("zh-tw", "zh_tw", "traditional"):
            return "tw"
        if lang in ("ja", "japanese"):
            return "jp"
        if lang in ("korean",):
            return "ko"
        return self.DEFAULT_LANG

    def translate_player(self, name: str, lang: str) -> str:
        """Translate a player name to the target language.

        Translation priority:
        1. Database lookup (exact match or alias)
        2. Fuzzy match in database
        3. LLM generation (if enabled, stores result in DB)

        Args:
            name: Player name to translate
            lang: Target language code (en, cn, tw, jp, ko)

        Returns:
            Translated player name, or original if no translation found
        """
        if not name:
            return name

        lang = self._normalize_lang(lang)

        # Build player index if not done
        self._build_player_index()

        # 1. Try exact match via index
        canonical = self._player_index.get(name.lower())
        if canonical:
            db_result = self._lookup_db_player(canonical, lang)
            if db_result:
                return db_result

        # 2. Try direct DB lookup (in case index is stale)
        db_result = self._lookup_db_player(name, lang)
        if db_result:
            return db_result

        # 3. Try fuzzy match
        canonical = self._fuzzy_match_player(name)
        if canonical:
            db_result = self._lookup_db_player(canonical, lang)
            if db_result:
                return db_result

        # 4. Try LLM translation (if enabled)
        if self._enable_llm:
            llm_result = self._translate_player_with_llm(name, lang)
            if llm_result and llm_result != name:
                # Store in database for future use
                self._store_player_translation(name, lang, llm_result, source="llm")
                return llm_result

        # No match - return original
        return name

    def _fuzzy_match_player(self, name: str, threshold: float = 0.8) -> Optional[str]:
        """Find a fuzzy match for a player name.

        Args:
            name: Player name to match
            threshold: Minimum similarity ratio (0.0 to 1.0)

        Returns:
            Canonical player name if match found, None otherwise
        """
        # Ensure index is built
        self._build_player_index()

        name_lower = name.lower()
        best_match = None
        best_ratio = 0.0

        for alias, canonical in self._player_index.items():
            ratio = SequenceMatcher(None, name_lower, alias).ratio()
            if ratio > best_ratio and ratio >= threshold:
                best_ratio = ratio
                best_match = canonical

        return best_match

    def translate_tournament(self, name: str, lang: str) -> str:
        """Translate a tournament name to the target language.

        Translation priority:
        1. Database lookup (exact match)
        2. Compound name parsing (e.g., "第52期日本天元战预选A组")
        3. Space-separated compound name (e.g., "棋聖 ＦＴ")
        4. LLM fallback (if enabled, stores result in DB)

        Args:
            name: Tournament name to translate
            lang: Target language code

        Returns:
            Translated tournament name, or original if no translation found
        """
        if not name:
            return name

        lang = self._normalize_lang(lang)
        result = None

        # 1. Try database lookup
        result = self._lookup_db_tournament(name, lang)

        # 2. Try compound parsing for complex tournament names
        if not result:
            parsed = self._parse_compound_tournament(name, lang)
            if parsed and parsed != name:
                self._store_tournament_translation(name, lang, parsed, source="compound")
                result = parsed

        # 3. Try space-separated compound name (e.g., "棋聖 ＦＴ")
        if not result:
            parts = name.split()
            if len(parts) > 1:
                translated_parts = []
                any_translated = False
                for part in parts:
                    part_trans = self._lookup_db_tournament(part, lang)
                    if part_trans:
                        translated_parts.append(part_trans)
                        if part_trans != part:
                            any_translated = True
                    else:
                        translated_parts.append(part)
                if any_translated:
                    result = " ".join(translated_parts)
                    self._store_tournament_translation(name, lang, result, source="compound")

        # 4. Try LLM translation (if enabled)
        if not result and self._enable_llm:
            llm_result = self._translate_tournament_with_llm(name, lang)
            if llm_result and llm_result != name:
                self._store_tournament_translation(name, lang, llm_result, source="llm")
                result = llm_result

        # 5. For Japanese, apply automatic character conversion
        if lang == "jp":
            text = result if result else name
            converted = convert_simplified_to_japanese(text)
            return converted

        return result if result else name

    def _parse_compound_tournament(self, name: str, lang: str) -> Optional[str]:
        """Parse and translate compound tournament names.

        Handles complex tournament names like:
        - "第52期日本天元战预选A组" -> "52nd Tengen Preliminary A"
        - "第37期日本女流名人战循环圈" -> "37th Women's Meijin League"
        - "27届三国赤壁古战场杯围甲15轮..." -> "27th Chibi Cup Chinese A League Rd.15..."

        Args:
            name: Tournament name to parse
            lang: Target language

        Returns:
            Translated name or None if not parseable
        """

        # Pattern for 期-style: 第N期[国家][比赛名][轮次]
        # e.g., 第52期日本天元战预选A组
        jp_pattern = r"第(\d+)期(日本|韩国|中国)?(.*?[战杯赛])(.*)"
        match = re.match(jp_pattern, name)
        if match:
            edition, country, tournament_name, round_part = match.groups()
            parts = []

            # Edition number — 期 format
            if lang == "en":
                parts.append(self._ordinal(edition))
            elif lang == "ko":
                parts.append(f"제{edition}기")
            else:
                # CN/TW/JP all use 第N期
                parts.append(f"第{edition}期")

            # Country (optional, only for EN)
            if country and lang == "en":
                country_trans = {"日本": "Japan", "韩国": "Korea", "中国": "China"}.get(country, country)
                parts.append(country_trans)

            # Tournament name - try DB lookup
            trans = self._lookup_db_tournament(tournament_name, lang)
            parts.append(trans if trans else tournament_name)

            # Round part (e.g., "预选A组", "循环圈")
            if round_part:
                trans = self._lookup_db_tournament(round_part, lang)
                parts.append(trans if trans else round_part)

            return " ".join(parts)

        # Pattern for 届-style: N届[比赛杯][轮次]
        # e.g., 27届三国赤壁古战场杯围甲15轮
        cup_pattern = r"(\d+)届(.*?杯)(.*)"
        match = re.match(cup_pattern, name)
        if match:
            edition, cup_name, round_part = match.groups()
            parts = []

            # Edition — 届 format
            if lang == "en":
                parts.append(self._ordinal(edition))
            elif lang == "ko":
                parts.append(f"제{edition}회")
            elif lang == "tw":
                parts.append(f"第{edition}屆")
            else:
                # CN/JP use 第N届
                parts.append(f"第{edition}届")

            # Cup name - try DB lookup
            trans = self._lookup_db_tournament(cup_name, lang)
            parts.append(trans if trans else cup_name)

            # Round part - try DB lookup for sub-parts
            if round_part:
                round_trans = self._translate_round_part(round_part, lang)
                parts.append(round_trans)

            return " ".join(parts)

        return None

    @staticmethod
    def _ordinal(n: str) -> str:
        """Convert number string to English ordinal (e.g., '52' -> '52nd')."""
        suffix = "th"
        if n.endswith("1") and not n.endswith("11"):
            suffix = "st"
        elif n.endswith("2") and not n.endswith("12"):
            suffix = "nd"
        elif n.endswith("3") and not n.endswith("13"):
            suffix = "rd"
        return f"{n}{suffix}"

    def _translate_round_part(self, round_part: str, lang: str) -> str:
        """Translate the round part of a compound tournament name.

        Tries exact DB lookup first, then looks for known sub-parts
        like '围甲', '15轮', team names, etc.

        Args:
            round_part: Round/stage string (e.g., "围甲15轮深圳聂道厚势-贵州仁怀酱香1")
            lang: Target language code

        Returns:
            Translated round string (best effort)
        """
        # 1. Try exact DB lookup
        trans = self._lookup_db_tournament(round_part, lang)
        if trans:
            return trans

        # 2. Try to find and translate known sub-parts
        result = round_part
        # Check known tournament terms at the start of the round_part
        known_prefixes = ["围甲", "围乙", "围丙"]
        for prefix in known_prefixes:
            if result.startswith(prefix):
                prefix_trans = self._lookup_db_tournament(prefix, lang)
                if prefix_trans:
                    result = prefix_trans + " " + result[len(prefix):]
                break

        return result

    def translate_round(self, round_name: str, lang: str) -> str:
        """Translate a round name (Final, Semi-final, etc.).

        Args:
            round_name: Round name to translate
            lang: Target language code

        Returns:
            Translated round name, or original if no translation found
        """
        if not round_name:
            return round_name

        lang = self._normalize_lang(lang)

        # Try database lookup (rounds are stored as tournaments)
        db_result = self._lookup_db_tournament(round_name, lang)
        if db_result:
            return db_result

        return round_name

    def translate_rules(self, rules: str, lang: str) -> str:
        """Translate rule names (Chinese Rules, etc.).

        Args:
            rules: Rule name to translate
            lang: Target language code

        Returns:
            Translated rule name, or original if no translation found
        """
        if not rules:
            return rules

        lang = self._normalize_lang(lang)

        # Try database lookup (rules are stored as tournaments)
        db_result = self._lookup_db_tournament(rules, lang)
        if db_result:
            return db_result

        return rules

    @lru_cache(maxsize=16)
    def get_all_translations(self, lang: str) -> dict:
        """Get all live-specific translations for frontend bundling.

        Args:
            lang: Target language code

        Returns:
            Dictionary with players, tournaments, rounds, and rules translations
        """
        lang = self._normalize_lang(lang)

        players = {}
        tournaments = {}
        rounds = {}
        rules = {}

        try:
            session = self._get_db_session()
            if session:
                from katrain.web.core.models_db import PlayerTranslationDB, TournamentTranslationDB

                # Get all players
                for p in session.query(PlayerTranslationDB).all():
                    trans = self._get_player_translation(p, lang)
                    players[p.canonical_name] = trans

                # Get all tournaments (includes rounds and rules)
                for t in session.query(TournamentTranslationDB).all():
                    trans = self._get_tournament_translation(t, lang)
                    # Categorize by pattern
                    if any(kw in t.original for kw in ["规则", "Rules", "ルール"]):
                        rules[t.original] = trans
                    elif any(kw in t.original for kw in ["决赛", "半决赛", "轮", "局", "强", "予選", "本戦", "リーグ", "ＦＴ", "回戦"]):
                        rounds[t.original] = trans
                    else:
                        tournaments[t.original] = trans

        except Exception as e:
            logger.error(f"Failed to get all translations: {e}")

        return {
            "players": players,
            "tournaments": tournaments,
            "rounds": rounds,
            "rules": rules,
        }

    def _get_player_translation(self, record, lang: str) -> str:
        """Get player translation with proper native language fallback.

        For players, if the requested language matches their native language
        (determined by country), return the canonical name instead of falling
        back to English.

        Fallback order for Chinese variants:
        - tw -> cn -> canonical_name -> en
        - cn -> tw -> canonical_name -> en

        Args:
            record: PlayerTranslationDB record
            lang: Target language code

        Returns:
            Translated name or canonical name
        """
        # Map country to native language
        native_lang_map = {"CN": "cn", "TW": "tw", "JP": "jp", "KR": "ko"}
        native_lang = native_lang_map.get(record.country, "cn")  # Default to Chinese

        # First try the requested language
        trans = getattr(record, lang, None)
        if trans:
            return trans

        # If requesting native language, return canonical name (it's already in native language)
        if lang == native_lang:
            return record.canonical_name

        # For Chinese variants (tw/cn), try the other variant before falling back to English
        if lang == "tw":
            # Try simplified Chinese, then canonical name for Chinese players
            cn_trans = getattr(record, "cn", None)
            if cn_trans:
                return cn_trans
            # If player is Chinese (CN/TW), return canonical name
            if record.country in ("CN", "TW"):
                return record.canonical_name
        elif lang == "cn":
            # Try traditional Chinese, then canonical name for Chinese players
            tw_trans = getattr(record, "tw", None)
            if tw_trans:
                return tw_trans
            # If player is Chinese (CN/TW), return canonical name
            if record.country in ("CN", "TW"):
                return record.canonical_name

        # Otherwise fall back to English, then canonical name
        return getattr(record, self.DEFAULT_LANG, None) or record.canonical_name

    def _get_tournament_translation(self, record, lang: str) -> Optional[str]:
        """Get tournament translation for exact language match only.

        Tournament names are language-specific in both format ("52nd" vs "第52期")
        and character set (simplified vs traditional Chinese, Japanese kanji).
        No cross-language fallback — each language must have its own translation.

        Args:
            record: TournamentTranslationDB record
            lang: Target language code

        Returns:
            Translated name or None if no translation for this language
        """
        trans = getattr(record, lang, None)
        return trans if trans else None

    def get_player_info(self, name: str) -> Optional[dict]:
        """Get full player information including all translations.

        Args:
            name: Player name (any language or alias)

        Returns:
            Player info dict with all translations, or None if not found
        """
        self._build_player_index()
        canonical = self._player_index.get(name.lower())
        if not canonical:
            canonical = self._fuzzy_match_player(name)

        if canonical:
            try:
                session = self._get_db_session()
                if session:
                    from katrain.web.core.models_db import PlayerTranslationDB
                    record = session.query(PlayerTranslationDB).filter(
                        PlayerTranslationDB.canonical_name == canonical
                    ).first()
                    if record:
                        return {
                            "canonical": canonical,
                            "country": record.country,
                            "en": record.en,
                            "cn": record.cn,
                            "tw": record.tw,
                            "jp": record.jp,
                            "ko": record.ko,
                            "aliases": record.aliases,
                        }
            except Exception as e:
                logger.debug(f"Failed to get player info: {e}")

        return None

    # ========== Database Methods ==========

    def _get_db_session(self) -> Optional[Session]:
        """Get a database session for translation lookups."""
        if self._db_session is not None:
            return self._db_session
        try:
            from katrain.web.core.db import SessionLocal
            self._db_session = SessionLocal()
            return self._db_session
        except Exception as e:
            logger.debug(f"Could not get DB session: {e}")
            return None

    def _lookup_db_player(self, name: str, lang: str) -> Optional[str]:
        """Look up player translation in database.

        Args:
            name: Player name to look up
            lang: Target language code

        Returns:
            Translated name or None if not found
        """
        try:
            session = self._get_db_session()
            if not session:
                return None

            from katrain.web.core.models_db import PlayerTranslationDB
            record = session.query(PlayerTranslationDB).filter(
                PlayerTranslationDB.canonical_name == name
            ).first()

            if record:
                return self._get_player_translation(record, lang)
            return None
        except Exception as e:
            logger.debug(f"DB lookup failed for player {name}: {e}")
            return None

    def _lookup_db_tournament(self, name: str, lang: str) -> Optional[str]:
        """Look up tournament translation in database.

        Args:
            name: Tournament name to look up
            lang: Target language code

        Returns:
            Translated name or None if not found
        """
        try:
            session = self._get_db_session()
            if not session:
                return None

            from katrain.web.core.models_db import TournamentTranslationDB
            record = session.query(TournamentTranslationDB).filter(
                TournamentTranslationDB.original == name
            ).first()

            if record:
                return self._get_tournament_translation(record, lang)
            return None
        except Exception as e:
            logger.debug(f"DB lookup failed for tournament {name}: {e}")
            return None

    def clear_cache(self) -> None:
        """Clear the translation cache.

        Should be called after storing new translations to ensure
        fresh data is returned by get_all_translations().
        """
        self.get_all_translations.cache_clear()
        self._index_built = False  # Force rebuild of player index
        logger.debug("Translation cache cleared")

    def _store_player_translation(
        self, name: str, lang: str, translation: str, source: str = "manual", country: str = None
    ) -> bool:
        """Store a player translation in the database.

        Args:
            name: Canonical player name
            lang: Language code of the translation
            translation: Translated name
            source: Source of translation (manual, llm, wikipedia)
            country: Player's country (CN, JP, KR, TW)

        Returns:
            True if stored successfully, False otherwise
        """
        try:
            session = self._get_db_session()
            if not session:
                return False

            from katrain.web.core.models_db import PlayerTranslationDB

            # Check if record exists
            record = session.query(PlayerTranslationDB).filter(
                PlayerTranslationDB.canonical_name == name
            ).first()

            if record:
                # Update existing record
                setattr(record, lang, translation)
                record.source = source
                if country:
                    record.country = country
            else:
                # Create new record
                record = PlayerTranslationDB(
                    canonical_name=name,
                    country=country,
                    source=source,
                )
                setattr(record, lang, translation)
                session.add(record)

            session.commit()
            self.clear_cache()  # Invalidate cache after storing
            logger.info(f"Stored player translation: {name} -> {translation} ({lang})")
            return True
        except Exception as e:
            logger.error(f"Failed to store player translation: {e}")
            if session:
                session.rollback()
            return False

    def _store_tournament_translation(
        self, name: str, lang: str, translation: str, source: str = "manual"
    ) -> bool:
        """Store a tournament translation in the database.

        Args:
            name: Original tournament name
            lang: Language code of the translation
            translation: Translated name
            source: Source of translation (manual, llm, wikipedia)

        Returns:
            True if stored successfully, False otherwise
        """
        try:
            session = self._get_db_session()
            if not session:
                return False

            from katrain.web.core.models_db import TournamentTranslationDB

            # Check if record exists
            record = session.query(TournamentTranslationDB).filter(
                TournamentTranslationDB.original == name
            ).first()

            if record:
                # Update existing record
                setattr(record, lang, translation)
                record.source = source
            else:
                # Create new record
                record = TournamentTranslationDB(
                    original=name,
                    source=source,
                )
                setattr(record, lang, translation)
                session.add(record)

            session.commit()
            self.clear_cache()  # Invalidate cache after storing
            logger.info(f"Stored tournament translation: {name} -> {translation} ({lang})")
            return True
        except Exception as e:
            logger.error(f"Failed to store tournament translation: {e}")
            if session:
                session.rollback()
            return False

    # ========== LLM Translation Methods ==========

    def _translate_player_with_llm(self, name: str, lang: str) -> Optional[str]:
        """Translate a player name using LLM.

        Args:
            name: Player name to translate
            lang: Target language code

        Returns:
            Translated name or None if failed
        """
        if not self._enable_llm:
            return None

        try:
            prompt = PLAYER_TRANSLATION_PROMPT.format(name=name, lang=self._lang_name(lang))
            result = self._call_llm(prompt)
            if result:
                return result.strip()
            return None
        except Exception as e:
            logger.debug(f"LLM translation failed for player {name}: {e}")
            return None

    def _translate_tournament_with_llm(self, name: str, lang: str) -> Optional[str]:
        """Translate a tournament name using LLM.

        Args:
            name: Tournament name to translate
            lang: Target language code

        Returns:
            Translated name or None if failed
        """
        if not self._enable_llm:
            return None

        try:
            lang_name = self._lang_name(lang)
            lang_guidelines = TOURNAMENT_LANG_GUIDELINES.get(lang_name, "")
            prompt = TOURNAMENT_TRANSLATION_PROMPT.format(name=name, lang=lang_name, lang_guidelines=lang_guidelines)
            result = self._call_llm(prompt)
            if result:
                return result.strip()
            return None
        except Exception as e:
            logger.debug(f"LLM translation failed for tournament {name}: {e}")
            return None

    def _lang_name(self, lang: str) -> str:
        """Convert language code to full name for LLM prompts."""
        return {
            "en": "English",
            "cn": "Simplified Chinese",
            "tw": "Traditional Chinese",
            "jp": "Japanese",
            "ko": "Korean",
        }.get(lang, "English")

    def _call_llm(self, prompt: str) -> Optional[str]:
        """Call LLM API to generate translation.

        Currently uses Anthropic Claude API if configured.
        Falls back to None if no API key available.

        Args:
            prompt: The prompt to send to LLM

        Returns:
            LLM response text or None if failed
        """
        try:
            import anthropic
            import os

            # API key from environment variable (security best practice)
            api_key = os.environ.get("ANTHROPIC_API_KEY")
            if not api_key:
                logger.debug("ANTHROPIC_API_KEY not set, skipping LLM translation")
                return None

            # Model name from database config or environment variable
            model_name = self._get_llm_config("model_name") or os.environ.get(
                "ANTHROPIC_MODEL", "claude-haiku-4-5-20251001"
            )

            client = anthropic.Anthropic(api_key=api_key)
            response = client.messages.create(
                model=model_name,
                max_tokens=100,
                messages=[{"role": "user", "content": prompt}],
            )

            if response.content:
                return response.content[0].text
            return None
        except ImportError:
            logger.debug("anthropic package not installed, skipping LLM translation")
            return None
        except Exception as e:
            logger.debug(f"LLM API call failed: {e}")
            return None

    def _get_llm_config(self, key: str) -> Optional[str]:
        """Get LLM configuration from database.

        Args:
            key: Config key (e.g., 'model_name')

        Returns:
            Config value or None if not found
        """
        try:
            session = self._get_db_session()
            if not session:
                return None

            from katrain.web.core.models_db import SystemConfigDB
            config = session.query(SystemConfigDB).filter_by(key=f"llm_{key}").first()
            return config.value if config else None
        except Exception as e:
            logger.debug(f"Failed to get LLM config: {e}")
            return None

    # ========== Public Methods for Manual Translation ==========

    def store_player(
        self,
        name: str,
        translations: dict,
        country: str = None,
        source: str = "manual"
    ) -> bool:
        """Store a player translation with all languages.

        Args:
            name: Canonical player name
            translations: Dict of {lang: translation} pairs
            country: Player's country code (CN, JP, KR, TW)
            source: Source of translation

        Returns:
            True if stored successfully
        """
        try:
            session = self._get_db_session()
            if not session:
                return False

            from katrain.web.core.models_db import PlayerTranslationDB

            record = session.query(PlayerTranslationDB).filter(
                PlayerTranslationDB.canonical_name == name
            ).first()

            if record:
                for lang, trans in translations.items():
                    if lang in self.SUPPORTED_LANGS:
                        setattr(record, lang, trans)
                record.source = source
                if country:
                    record.country = country
            else:
                record = PlayerTranslationDB(
                    canonical_name=name,
                    country=country,
                    source=source,
                    **{k: v for k, v in translations.items() if k in self.SUPPORTED_LANGS}
                )
                session.add(record)

            session.commit()
            self.clear_cache()  # Invalidate cache after storing
            logger.info(f"Stored player: {name} with {len(translations)} translations")
            return True
        except Exception as e:
            logger.error(f"Failed to store player: {e}")
            if session:
                session.rollback()
            return False

    def store_tournament(
        self,
        name: str,
        translations: dict,
        source: str = "manual"
    ) -> bool:
        """Store a tournament translation with all languages.

        Args:
            name: Original tournament name
            translations: Dict of {lang: translation} pairs
            source: Source of translation

        Returns:
            True if stored successfully
        """
        try:
            session = self._get_db_session()
            if not session:
                return False

            from katrain.web.core.models_db import TournamentTranslationDB

            record = session.query(TournamentTranslationDB).filter(
                TournamentTranslationDB.original == name
            ).first()

            if record:
                for lang, trans in translations.items():
                    if lang in self.SUPPORTED_LANGS:
                        setattr(record, lang, trans)
                record.source = source
            else:
                record = TournamentTranslationDB(
                    original=name,
                    source=source,
                    **{k: v for k, v in translations.items() if k in self.SUPPORTED_LANGS}
                )
                session.add(record)

            session.commit()
            self.clear_cache()  # Invalidate cache after storing
            logger.info(f"Stored tournament: {name} with {len(translations)} translations")
            return True
        except Exception as e:
            logger.error(f"Failed to store tournament: {e}")
            if session:
                session.rollback()
            return False

    def has_translation(self, name: str, name_type: str, lang: str) -> bool:
        """Check if a translation exists for the given name.

        Args:
            name: Name to check
            name_type: 'player' or 'tournament'
            lang: Target language

        Returns:
            True if translation exists in static data or database
        """
        lang = self._normalize_lang(lang)

        if name_type == "player":
            # Check database
            if self._lookup_db_player(name, lang):
                return True
        elif name_type == "tournament":
            # Check database
            if self._lookup_db_tournament(name, lang):
                return True

        return False

    def get_missing_translations(self, names: list, name_type: str, lang: str) -> list:
        """Get list of names that don't have translations.

        Args:
            names: List of names to check
            name_type: 'player' or 'tournament'
            lang: Target language

        Returns:
            List of names without translations
        """
        return [name for name in names if not self.has_translation(name, name_type, lang)]


# Global singleton
_translator: Optional[LiveTranslator] = None


def get_translator() -> LiveTranslator:
    """Get the global translator instance."""
    global _translator
    if _translator is None:
        _translator = LiveTranslator()
    return _translator


def reset_translator() -> None:
    """Reset the global translator (for testing)."""
    global _translator
    _translator = None
