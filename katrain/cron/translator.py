"""Translation logic: search-first for players, direct LLM for tournaments."""

import asyncio
import json
import logging
from typing import Optional

import httpx

from katrain.cron import config

logger = logging.getLogger("katrain_cron.translator")

LANGUAGES = ["en", "cn", "tw", "jp", "ko"]

# User-Agent for web searches (Wikipedia blocks default httpx User-Agent)
USER_AGENT = "KaTrain/1.0 (https://github.com/sanderland/katrain; katrain-cron)"

# Wikipedia language codes for search
WIKI_LANGS = ["en", "ja", "ko", "zh"]


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
            # Step A: Search multiple Wikipedia languages and get interwiki links
            search_context, langlinks = await self._search_player_multilang(name)

            if search_context or langlinks:
                # Step B: LLM-assisted extraction from search results + langlinks
                result = await self._llm_extract_player(name, search_context, langlinks)
                if result:
                    result["source"] = "search+llm"
                    result["llm_model"] = config.LLM_MODEL
                    return result

            # Step C: Fallback — direct LLM translation
            result = await self._llm_translate_player(name, country)
            result["source"] = "llm"
            result["llm_model"] = config.LLM_MODEL
            return result

    async def _search_player_multilang(self, name: str) -> tuple[Optional[str], dict[str, str]]:
        """Search multiple Wikipedia languages for a player.

        Returns:
            (search_context, langlinks) where:
            - search_context: Combined snippets from search results
            - langlinks: Dict of {lang_code: page_title} from interwiki links
        """
        headers = {"User-Agent": USER_AGENT}
        search_results = []
        langlinks: dict[str, str] = {}
        found_page_title = None
        found_wiki_lang = None

        async with httpx.AsyncClient(timeout=10.0, headers=headers) as client:
            # Search in multiple Wikipedia languages
            for wiki_lang in WIKI_LANGS:
                if found_page_title:
                    break  # Already found a good page

                queries = self._get_search_queries(name, wiki_lang)
                wiki_url = f"https://{wiki_lang}.wikipedia.org/w/api.php"

                for q in queries:
                    try:
                        resp = await client.get(
                            wiki_url,
                            params={"action": "query", "list": "search", "srsearch": q, "format": "json", "srlimit": 3},
                        )
                        if resp.status_code != 200:
                            continue

                        data = resp.json()
                        results = data.get("query", {}).get("search", [])

                        for item in results:
                            title = item.get("title", "")
                            snippet = item.get("snippet", "")
                            search_results.append(f"[{wiki_lang}] Title: {title}\nSnippet: {snippet}")

                            # Check if this looks like a player page (contains the name)
                            if name in title or self._normalize_name(name) in self._normalize_name(title):
                                found_page_title = title
                                found_wiki_lang = wiki_lang
                                break

                        if found_page_title:
                            break
                    except Exception as e:
                        logger.debug("Search failed for %s on %s: %s", q, wiki_lang, e)
                        continue

            # If we found a page, fetch its langlinks (interwiki links)
            if found_page_title and found_wiki_lang:
                langlinks = await self._fetch_langlinks(client, found_wiki_lang, found_page_title)
                # Add the found page's own language
                langlinks[found_wiki_lang] = found_page_title

        search_context = "\n---\n".join(search_results) if search_results else None
        return search_context, langlinks

    def _get_search_queries(self, name: str, wiki_lang: str) -> list[str]:
        """Get search queries based on Wikipedia language."""
        if wiki_lang == "en":
            return [f"{name} Go player", f"{name} baduk", f"{name} weiqi"]
        elif wiki_lang == "ja":
            return [f"{name} 囲碁", f"{name} 棋士"]
        elif wiki_lang == "ko":
            return [f"{name} 바둑", f"{name} 기사"]
        elif wiki_lang == "zh":
            return [f"{name} 围棋", f"{name} 棋手"]
        return [name]

    def _normalize_name(self, name: str) -> str:
        """Normalize name for comparison (lowercase, remove spaces)."""
        return name.lower().replace(" ", "").replace("·", "").replace("・", "")

    async def _fetch_langlinks(self, client: httpx.AsyncClient, wiki_lang: str, title: str) -> dict[str, str]:
        """Fetch interwiki language links for a Wikipedia page.

        Returns: {lang_code: page_title} e.g. {"ja": "唐韋星", "ko": "탕웨이싱"}
        """
        wiki_url = f"https://{wiki_lang}.wikipedia.org/w/api.php"
        langlinks = {}

        try:
            resp = await client.get(
                wiki_url,
                params={
                    "action": "query",
                    "titles": title,
                    "prop": "langlinks",
                    "lllimit": "50",
                    "format": "json",
                },
            )
            if resp.status_code != 200:
                return langlinks

            data = resp.json()
            pages = data.get("query", {}).get("pages", {})

            for page in pages.values():
                for ll in page.get("langlinks", []):
                    lang = ll.get("lang", "")
                    link_title = ll.get("*", "")
                    if lang and link_title:
                        langlinks[lang] = link_title
                        logger.debug("Found langlink: %s -> %s", lang, link_title)

        except Exception as e:
            logger.debug("Failed to fetch langlinks for %s: %s", title, e)

        return langlinks

    async def _llm_extract_player(self, name: str, context: Optional[str], langlinks: dict[str, str]) -> Optional[dict]:
        """Feed search results and langlinks to LLM to extract multilingual names."""
        # Build context with langlinks info
        parts = []
        if context:
            parts.append(f"Search results:\n{context}")

        if langlinks:
            ll_text = "\n".join(f"  {lang}: {title}" for lang, title in langlinks.items())
            parts.append(f"Wikipedia page titles in different languages:\n{ll_text}")

        if not parts:
            return None

        full_context = "\n\n".join(parts)

        prompt = (
            f"Based on the following information about the Go/Baduk/Weiqi player '{name}', "
            f"provide their name in these languages. Return ONLY valid JSON.\n\n"
            f"{full_context}\n\n"
            f"IMPORTANT: For Japanese (jp), if the Wikipedia langlinks show the actual characters "
            f"(like 唐韋星), use those characters, NOT a phonetic transliteration (like トウ・ウェイシン).\n\n"
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
