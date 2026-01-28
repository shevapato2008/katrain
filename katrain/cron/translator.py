"""Translation logic: search-first for players, direct LLM for tournaments."""

import asyncio
import json
import logging
from typing import Optional

import httpx

from katrain.cron import config

logger = logging.getLogger("katrain_cron.translator")

LANGUAGES = ["en", "cn", "tw", "jp", "ko"]


class Translator:
    """Translates player names (search+LLM) and tournament names (direct LLM)."""

    def __init__(self):
        self._semaphore = asyncio.Semaphore(config.LLM_CONCURRENCY)

    # ── Player names (search-first) ──────────────────────────

    async def translate_player(self, name: str, country: Optional[str] = None) -> dict:
        """Translate a player name using search-first strategy.

        Returns: {lang: translation, ..., "source": "search+llm"|"llm"}
        """
        async with self._semaphore:
            # Step A + B: Search for the player
            search_context = await self._search_player(name, country)

            if search_context:
                # Step C: LLM-assisted extraction from search results
                result = await self._llm_extract_player(name, search_context)
                if result:
                    result["source"] = "search+llm"
                    result["llm_model"] = config.LLM_MODEL
                    return result

            # Step D: Fallback — direct LLM translation
            result = await self._llm_translate_player(name, country)
            result["source"] = "llm"
            result["llm_model"] = config.LLM_MODEL
            return result

    async def _search_player(self, name: str, country: Optional[str] = None) -> Optional[str]:
        """Search Wikipedia and Go associations for a player name.

        Returns combined search context string, or None if nothing found.
        """
        queries = [
            f"{name} Go player",
            f"{name} 围棋 棋手",
            f"{name} 棋士",
        ]

        results = []
        async with httpx.AsyncClient(timeout=10.0) as client:
            for q in queries:
                try:
                    # Use Wikipedia API for search
                    resp = await client.get(
                        "https://en.wikipedia.org/w/api.php",
                        params={"action": "query", "list": "search", "srsearch": q, "format": "json", "srlimit": 3},
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        for item in data.get("query", {}).get("search", []):
                            results.append(f"Title: {item['title']}\nSnippet: {item.get('snippet', '')}")
                except Exception:
                    continue

                if results:
                    break  # Got results from first successful query

        return "\n---\n".join(results) if results else None

    async def _llm_extract_player(self, name: str, context: str) -> Optional[dict]:
        """Feed search results to LLM to extract multilingual names."""
        prompt = (
            f"Based on the following search results about the Go/Baduk/Weiqi player '{name}', "
            f"provide their name in these languages. Return ONLY valid JSON.\n\n"
            f"Search results:\n{context}\n\n"
            f"Return format: {{\"en\": \"...\", \"cn\": \"...\", \"tw\": \"...\", \"jp\": \"...\", \"ko\": \"...\"}}\n"
            f"If you cannot determine a language, set it to null."
        )
        return await self._call_llm(prompt)

    async def _llm_translate_player(self, name: str, country: Optional[str] = None) -> dict:
        """Direct LLM translation (fallback for unknown players)."""
        country_hint = f" (from {country})" if country else ""
        prompt = (
            f"Translate the Go/Baduk/Weiqi player name '{name}'{country_hint} "
            f"into the following languages. Return ONLY valid JSON.\n\n"
            f"Return format: {{\"en\": \"...\", \"cn\": \"...\", \"tw\": \"...\", \"jp\": \"...\", \"ko\": \"...\"}}\n"
            f"If you cannot determine a language, set it to null."
        )
        result = await self._call_llm(prompt)
        return result or {lang: None for lang in LANGUAGES}

    # ── Tournament names (direct LLM) ───────────────────────

    async def translate_tournament(self, name: str) -> dict:
        """Translate a tournament name using direct LLM.

        Returns: {lang: translation, ..., "source": "llm"}
        """
        async with self._semaphore:
            prompt = (
                f"Translate the Go/Baduk/Weiqi tournament name '{name}' "
                f"into the following languages. Return ONLY valid JSON.\n\n"
                f"Return format: {{\"en\": \"...\", \"cn\": \"...\", \"tw\": \"...\", \"jp\": \"...\", \"ko\": \"...\"}}\n"
                f"If you cannot determine a language, set it to null."
            )
            result = await self._call_llm(prompt)
            out = result or {lang: None for lang in LANGUAGES}
            out["source"] = "llm"
            out["llm_model"] = config.LLM_MODEL
            return out

    # ── LLM backend ──────────────────────────────────────────

    async def _call_llm(self, prompt: str) -> Optional[dict]:
        """Call Qwen LLM via DashScope-compatible API. Returns parsed JSON or None."""
        if not config.DASHSCOPE_API_KEY:
            logger.warning("DASHSCOPE_API_KEY not set, skipping LLM call")
            return None

        url = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {config.DASHSCOPE_API_KEY}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": config.LLM_MODEL,
            "messages": [
                {"role": "system", "content": "You are a Go/Baduk/Weiqi translation assistant. Always return valid JSON only."},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.1,
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(url, json=payload, headers=headers)
                resp.raise_for_status()
                data = resp.json()

            content = data["choices"][0]["message"]["content"]
            # Strip markdown code fences if present
            content = content.strip()
            if content.startswith("```"):
                content = content.split("\n", 1)[-1]
                if content.endswith("```"):
                    content = content[:-3]
                content = content.strip()

            return json.loads(content)
        except json.JSONDecodeError:
            logger.warning("LLM returned invalid JSON for prompt: %s...", prompt[:80])
            return None
        except Exception:
            logger.exception("LLM call failed")
            return None
