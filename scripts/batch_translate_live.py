#!/usr/bin/env python
"""Batch translate missing player and tournament names using LLM.

This script fetches all missing translations from the API and uses
the Anthropic Claude API to translate them, then stores in the database.

Usage:
    python scripts/batch_translate_live.py [--dry-run]
"""

import argparse
import json
import os
import sys
import time

import requests

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

API_BASE = "http://localhost:8001/api/v1"

# Target languages for translation
TARGET_LANGS = ["en", "jp", "ko"]

# LLM prompts
PLAYER_PROMPT = """Translate this Go player name. Provide translations for English, Japanese (katakana), and Korean (hangul).

Player name: {name}

Conventions:
- Chinese names to English: Pinyin without tones (e.g., 柯洁 → Ke Jie)
- Chinese names to Japanese: Katakana with middle dot (e.g., 柯洁 → カ・ケツ)
- Chinese names to Korean: Hangul reading (e.g., 柯洁 → 커제)
- Japanese names to English: Romaji, surname first (e.g., 井山裕太 → Iyama Yuta)
- Korean names to English: Revised romanization (e.g., 신진서 → Shin Jinseo)

Return ONLY a JSON object with keys "en", "jp", "ko" for the translations.
Example: {{"en": "Ke Jie", "jp": "カ・ケツ", "ko": "커제"}}"""

TOURNAMENT_PROMPT = """Translate this Go tournament name. Provide translations for English, Japanese, and Korean.

Tournament name: {name}

Guidelines:
- Use official English names when known (棋聖戦 → Kisei)
- Translate 战/杯/赛 as Tournament/Cup/Match
- For editions, use ordinal numbers (第52期 → 52nd)
- For team matches, translate team names appropriately
- Keep proper nouns in appropriate script

Return ONLY a JSON object with keys "en", "jp", "ko" for the translations.
Example: {{"en": "52nd Tengen Preliminary A", "jp": "第52期天元戦予選A組", "ko": "제52기 천원전 예선 A조"}}"""


def call_llm(prompt: str) -> dict | None:
    """Call Anthropic API to translate."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY not set")
        return None

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=200,
            messages=[{"role": "user", "content": prompt}],
        )
        if response.content:
            text = response.content[0].text.strip()
            # Parse JSON response
            # Handle potential markdown code blocks
            if text.startswith("```"):
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
            return json.loads(text)
        return None
    except json.JSONDecodeError as e:
        print(f"  JSON parse error: {e}")
        return None
    except Exception as e:
        print(f"  LLM error: {e}")
        return None


def get_missing_translations() -> dict:
    """Fetch missing translations from API."""
    try:
        resp = requests.get(f"{API_BASE}/live/translations/missing?lang=en", timeout=30)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"ERROR: Failed to fetch missing translations: {e}")
        return {"missing_players": [], "missing_tournaments": []}


def store_translation(name: str, name_type: str, translations: dict, token: str) -> bool:
    """Store translation via API."""
    try:
        payload = {
            "name": name,
            "name_type": name_type,
            "translations": translations,
            "source": "llm"
        }
        headers = {"Authorization": f"Bearer {token}"}
        resp = requests.post(
            f"{API_BASE}/live/translations/learn",
            json=payload,
            headers=headers,
            timeout=30
        )
        return resp.status_code == 200
    except Exception as e:
        print(f"  Store error: {e}")
        return False


def login(username: str = "admin", password: str = "admin") -> str | None:
    """Login to get auth token."""
    try:
        resp = requests.post(
            f"{API_BASE}/auth/login",
            data={"username": username, "password": password},
            timeout=30
        )
        if resp.status_code == 200:
            return resp.json().get("access_token")
        print(f"Login failed: {resp.status_code}")
        return None
    except Exception as e:
        print(f"Login error: {e}")
        return None


def store_directly_to_db(name: str, name_type: str, translations: dict, country: str = None):
    """Store translation directly to database (bypass API auth)."""
    from katrain.web.core.db import SessionLocal
    from katrain.web.core.models_db import PlayerTranslationDB, TournamentTranslationDB

    session = SessionLocal()
    try:
        if name_type == "player":
            # Check if exists
            existing = session.query(PlayerTranslationDB).filter_by(canonical_name=name).first()
            if existing:
                # Update
                for lang, value in translations.items():
                    if value and hasattr(existing, lang):
                        setattr(existing, lang, value)
                existing.source = "llm"
            else:
                # Create new
                player = PlayerTranslationDB(
                    canonical_name=name,
                    country=country,
                    en=translations.get("en"),
                    jp=translations.get("jp"),
                    ko=translations.get("ko"),
                    source="llm"
                )
                session.add(player)
        else:
            # Tournament
            existing = session.query(TournamentTranslationDB).filter_by(original=name).first()
            if existing:
                for lang, value in translations.items():
                    if value and hasattr(existing, lang):
                        setattr(existing, lang, value)
                existing.source = "llm"
            else:
                tournament = TournamentTranslationDB(
                    original=name,
                    en=translations.get("en"),
                    jp=translations.get("jp"),
                    ko=translations.get("ko"),
                    source="llm"
                )
                session.add(tournament)
        session.commit()
        return True
    except Exception as e:
        session.rollback()
        print(f"  DB error: {e}")
        return False
    finally:
        session.close()


def detect_country(name: str) -> str:
    """Detect player's country based on name characters."""
    # Check for Japanese-specific characters (hiragana, katakana)
    if any('\u3040' <= c <= '\u309F' or '\u30A0' <= c <= '\u30FF' for c in name):
        return "JP"
    # Check for Korean characters
    if any('\uAC00' <= c <= '\uD7AF' for c in name):
        return "KR"
    # Default to Chinese for CJK characters
    if any('\u4E00' <= c <= '\u9FFF' for c in name):
        return "CN"
    return None


def main():
    parser = argparse.ArgumentParser(description="Batch translate missing names")
    parser.add_argument("--dry-run", action="store_true", help="Don't store, just print")
    parser.add_argument("--players-only", action="store_true", help="Only translate players")
    parser.add_argument("--tournaments-only", action="store_true", help="Only translate tournaments")
    parser.add_argument("--limit", type=int, default=50, help="Max items to translate")
    args = parser.parse_args()

    print("Fetching missing translations...")
    missing = get_missing_translations()

    players = missing.get("missing_players", [])
    tournaments = missing.get("missing_tournaments", [])

    print(f"Found {len(players)} missing players, {len(tournaments)} missing tournaments")

    if not args.tournaments_only and players:
        print(f"\n=== Translating Players (limit: {args.limit}) ===")
        for i, name in enumerate(players[:args.limit]):
            print(f"[{i+1}/{min(len(players), args.limit)}] {name}")
            prompt = PLAYER_PROMPT.format(name=name)
            translations = call_llm(prompt)
            if translations:
                print(f"  -> en: {translations.get('en')}, jp: {translations.get('jp')}, ko: {translations.get('ko')}")
                if not args.dry_run:
                    country = detect_country(name)
                    if store_directly_to_db(name, "player", translations, country):
                        print("  [Stored]")
                    else:
                        print("  [Store failed]")
            else:
                print("  [Translation failed]")
            time.sleep(0.5)  # Rate limiting

    if not args.players_only and tournaments:
        print(f"\n=== Translating Tournaments (limit: {args.limit}) ===")
        for i, name in enumerate(tournaments[:args.limit]):
            print(f"[{i+1}/{min(len(tournaments), args.limit)}] {name}")
            prompt = TOURNAMENT_PROMPT.format(name=name)
            translations = call_llm(prompt)
            if translations:
                print(f"  -> en: {translations.get('en')}")
                if not args.dry_run:
                    if store_directly_to_db(name, "tournament", translations):
                        print("  [Stored]")
                    else:
                        print("  [Store failed]")
            else:
                print("  [Translation failed]")
            time.sleep(0.5)  # Rate limiting

    print("\nDone!")


if __name__ == "__main__":
    main()
