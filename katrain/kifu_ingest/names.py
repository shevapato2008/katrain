"""Bounded Qwen generation and independent model review for incremental names.

Instantiate once per ingestion round: ``max_items`` is the round's name budget.
This module never loads credentials or writes translation tables.
"""

from __future__ import annotations

import asyncio
import inspect
from datetime import datetime, timezone
from hashlib import sha256
from html import unescape
import json
import re
from urllib.parse import quote
from uuid import uuid4

import httpx

from katrain.web.kifu.name_parse import parse_player


LANGUAGES = ("cn", "tw", "jp", "ko", "en")
METHODS = frozenset({"retain_original", "orthographic_conversion", "transliteration", "translation"})
KINDS = frozenset({"player", "event", "raw_player", "raw_event"})
_RANK = re.compile(r"\s*(?:[一二三四五六七八九十0-9０-９]+\s*[段级級]|[0-9０-９]+\s*[dpk])\s*$", re.I)
_WIKI_LANGUAGES = frozenset({"en", "zh", "ja", "ko"})


def _wiki_evidence(lang: str, title: str, excerpt: str) -> dict:
    excerpt = excerpt[:500]
    return {
        "url": f"https://{lang}.wikipedia.org/wiki/{quote(title.replace(' ', '_'))}",
        "lang": lang,
        "title": title,
        "retrieved_at": _now(),
        "excerpt": excerpt,
        "content_sha256": sha256(excerpt.encode("utf-8")).hexdigest(),
    }


async def wiki_sources(raw: str, client: httpx.AsyncClient, languages=("en", "zh", "ja", "ko")) -> dict:
    """Fetch finite Wikipedia search titles and their actual language links.

    Search hits are candidate evidence only; the reviewer must verify identity.
    Returns ``{'status': 'available'|'unavailable', 'sources': [...]}``.
    """
    if not isinstance(raw, str) or not raw.strip() or len(raw) > 120:
        raise ValueError("invalid Wikipedia query")
    if not languages or len(languages) > 4 or any(lang not in _WIKI_LANGUAGES for lang in languages):
        raise ValueError("invalid Wikipedia languages")
    sources = []
    try:
        for lang in languages:
            response = await client.get(
                f"https://{lang}.wikipedia.org/w/api.php",
                params={
                    "action": "query",
                    "list": "search",
                    "srsearch": f"{raw} Go player",
                    "srlimit": 2,
                    "format": "json",
                    "formatversion": 2,
                },
                headers={"User-Agent": "KaTrain/1.0 (https://github.com/sanderland/katrain)"},
                timeout=10,
            )
            response.raise_for_status()
            if len(response.content) > 64_000:
                raise ValueError("Wikipedia response too large")
            hits = response.json().get("query", {}).get("search", [])
            if not isinstance(hits, list):
                raise ValueError("Wikipedia search malformed")
            for hit in hits[:2]:
                title, snippet = hit.get("title"), hit.get("snippet", "")
                if isinstance(title, str) and title and isinstance(snippet, str):
                    clean = unescape(re.sub(r"<[^>]*>", "", snippet))
                    sources.append(_wiki_evidence(lang, title, clean or f"Search result title: {title}"))
            if hits and isinstance(hits[0].get("title"), str):
                title = hits[0]["title"]
                links_response = await client.get(
                    f"https://{lang}.wikipedia.org/w/api.php",
                    params={
                        "action": "query",
                        "prop": "langlinks",
                        "titles": title,
                        "lllimit": 50,
                        "format": "json",
                    },
                    headers={"User-Agent": "KaTrain/1.0 (https://github.com/sanderland/katrain)"},
                    timeout=10,
                )
                links_response.raise_for_status()
                if len(links_response.content) > 64_000:
                    raise ValueError("Wikipedia response too large")
                pages = links_response.json().get("query", {}).get("pages", [])
                if not isinstance(pages, dict):
                    raise ValueError("Wikipedia langlinks malformed")
                for page in list(pages.values())[:1]:
                    for link in page.get("langlinks", [])[:50]:
                        linked_lang, linked_title = link.get("lang"), link.get("title") or link.get("*")
                        if linked_lang in _WIKI_LANGUAGES and isinstance(linked_title, str) and linked_title:
                            sources.append(
                                _wiki_evidence(
                                    linked_lang,
                                    linked_title,
                                    f"Wikipedia language link from {lang}:{title} to {linked_lang}:{linked_title}",
                                )
                            )
    except (httpx.HTTPError, ValueError, TypeError, KeyError):
        return {"status": "unavailable", "sources": []}
    unique = {source["url"]: source for source in sources}
    return {"status": "available", "sources": list(unique.values())}


class NameServiceError(RuntimeError):
    """No reviewed decision was produced."""


class NeedsCredentials(NameServiceError):
    """A caller must supply a Qwen API key explicitly."""


class NameRejected(NameServiceError):
    """Generation or independent review failed closed."""


def _now():
    return datetime.now(timezone.utc).isoformat()


class QwenNameService:
    def __init__(
        self,
        client: httpx.AsyncClient,
        key: str | None,
        model: str = "qwen-plus",
        base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1",
        concurrency: int = 3,
        max_items: int = 20,
        timeout: float = 30,
        max_output_tokens: int = 1024,
        max_total_tokens: int = 0,
        audit_call=None,
        reserve_call=None,
        settle_call=None,
        initial_tokens_used: int = 0,
    ):
        if concurrency < 1 or max_items < 1 or timeout <= 0 or max_output_tokens < 1 or max_total_tokens < 0:
            raise ValueError("concurrency, max_items and timeout must be positive")
        self.client, self.key, self.model = client, key, model
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_items = max_items
        self.max_output_tokens = max_output_tokens
        self.max_total_tokens = max_total_tokens
        self.tokens_used = initial_tokens_used
        self.audit_call = audit_call
        self.reserve_call = reserve_call
        self.settle_call = settle_call
        self._items = 0
        self._semaphore = asyncio.Semaphore(concurrency)

    async def _audit(self, *, role, attempt, status_code, request_id=None, usage=None):
        if self.audit_call is None:
            return
        entry = {
            "at": _now(),
            "model": self.model,
            "role": role,
            "attempt": attempt,
            "status_code": status_code,
            "request_id": request_id,
            "usage": usage,
            "max_output_tokens": self.max_output_tokens,
            "max_total_tokens": self.max_total_tokens,
            "tokens_used": self.tokens_used,
        }
        result = self.audit_call(entry)
        if inspect.isawaitable(result):
            await result

    async def _call(self, role: str, content: dict) -> tuple[dict, dict]:
        body = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are an independent Go name reviewer. Return one JSON object only; approve only if "
                        "all names, methods, identity, digits and cited sources are supported."
                        if role == "reviewer"
                        else "You translate Go names. Return one JSON object only with displays and methods keyed "
                        "by cn, tw, jp, ko, en; original_language and source_urls. Each method must be "
                        "retain_original, orthographic_conversion, transliteration, or translation. "
                        "Keep the same entity. For event and raw_event names, preserve every token in "
                        "required_digit_tokens literally in all five displays. "
                        "use supplied source URLs only, and mark generated names honestly."
                    ),
                },
                {"role": "user", "content": json.dumps(content, ensure_ascii=False)},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0,
            "max_tokens": self.max_output_tokens,
        }
        for attempt in range(2):
            reservation = None
            if self.reserve_call is not None:
                # UTF-8 bytes exceed prompt tokens for ordinary text; leave room for
                # chat protocol framing while reserving the full output cap.
                upper_bound = len(json.dumps(body, ensure_ascii=True).encode("utf-8")) + 2048 + self.max_output_tokens
                reservation = self.reserve_call(upper_bound)
                if inspect.isawaitable(reservation):
                    reservation = await reservation
            elif self.tokens_used + self.max_output_tokens > self.max_total_tokens:
                raise NameServiceError("Qwen token budget exhausted")
            try:
                response = await self.client.post(
                    f"{self.base_url}/chat/completions",
                    json=body,
                    headers={"Authorization": f"Bearer {self.key}"},
                    timeout=self.timeout,
                )
            except httpx.RequestError as exc:
                await self._audit(role=role, attempt=attempt + 1, status_code="transport_error")
                if attempt == 0:
                    continue
                raise NameServiceError("Qwen transport failure") from None
            if response.status_code == 429 and attempt == 0:
                await self._audit(role=role, attempt=attempt + 1, status_code=429)
                continue
            if response.status_code != 200:
                await self._audit(role=role, attempt=attempt + 1, status_code=response.status_code)
                raise NameServiceError(f"Qwen HTTP {response.status_code}")
            if len(response.content) > 64_000:
                await self._audit(role=role, attempt=attempt + 1, status_code=200)
                raise NameRejected("Qwen response exceeds size limit")
            try:
                envelope = response.json()
                if not isinstance(envelope, dict):
                    raise ValueError("object required")
            except (ValueError, TypeError):
                await self._audit(role=role, attempt=attempt + 1, status_code=200)
                raise NameRejected("Qwen response is invalid or incomplete") from None
            request_id = envelope.get("id") or response.headers.get("x-request-id")
            request_id = str(request_id) if request_id else f"local-call:{uuid4()}"
            usage = envelope.get("usage")
            usage_valid = isinstance(usage, dict) and all(
                isinstance(usage.get(field), int) and usage[field] >= 0
                for field in ("prompt_tokens", "completion_tokens", "total_tokens")
            )
            if usage_valid:
                if self.settle_call is not None:
                    settled = self.settle_call(reservation, usage["total_tokens"])
                    if inspect.isawaitable(settled):
                        settled = await settled
                    self.tokens_used = settled
                else:
                    self.tokens_used += usage["total_tokens"]
            await self._audit(
                role=role,
                attempt=attempt + 1,
                status_code=200,
                request_id=request_id,
                usage=usage if usage_valid else None,
            )
            if self.reserve_call is None and self.tokens_used > self.max_total_tokens:
                raise NameServiceError("Qwen token budget exhausted")
            try:
                choice = envelope["choices"][0]
                if choice.get("finish_reason") not in (None, "stop"):
                    raise ValueError("incomplete response")
                output = json.loads(choice["message"]["content"])
                if not isinstance(output, dict):
                    raise ValueError("object required")
            except (ValueError, KeyError, IndexError, TypeError):
                raise NameRejected("Qwen response is invalid or incomplete") from None
            if not usage_valid:
                raise NameServiceError("Qwen actual usage unavailable")
            return output, {
                "id": f"qwen-{role}",
                "model": self.model,
                "request_id": request_id,
                "at": _now(),
                "usage": usage,
                "request_attempts": attempt + 1,
                "max_output_tokens": self.max_output_tokens,
            }
        raise NameServiceError("Qwen rate limited")

    @staticmethod
    def _candidate(candidate: dict, kind: str, key: str, sources: list[dict], context=None) -> dict:
        if not {"displays", "methods", "original_language", "source_urls"} <= set(candidate) or not set(candidate) <= {
            "displays",
            "methods",
            "original_language",
            "source_urls",
            "cn_conversion_note",
        }:
            raise NameRejected("candidate fields invalid")
        displays, methods = candidate["displays"], candidate["methods"]
        if (
            not isinstance(displays, dict)
            or set(displays) != set(LANGUAGES)
            or any(not isinstance(value, str) or not value.strip() or len(value) > 120 for value in displays.values())
        ):
            raise NameRejected("candidate requires five nonempty displays")
        if not isinstance(methods, dict) or set(methods) != set(LANGUAGES) or not set(methods.values()) <= METHODS:
            raise NameRejected("candidate methods invalid")
        if kind == "raw_player" and not (isinstance(context, dict) and context.get("verified_reuse_displays")):
            retained = parse_player(key, None).name
            if any(methods[lang] == "retain_original" and displays[lang] != retained for lang in LANGUAGES):
                raise NameRejected("raw player retain_original differs from parsed name")
        if not isinstance(candidate["original_language"], str) or not candidate["original_language"].strip():
            raise NameRejected("original language missing")
        if kind == "raw_player" and isinstance(context, dict) and context.get("verified_reuse_displays"):
            for field in ("displays", "original_language", "methods"):
                if candidate[field] != context.get(f"verified_reuse_{field}"):
                    raise NameRejected(f"{field} differs from qualified raw player template")
        urls = candidate["source_urls"]
        if not isinstance(urls, list) or len(urls) != len(set(urls)) or not set(urls) <= {s["url"] for s in sources}:
            raise NameRejected("candidate invented a source URL")
        literal = _RANK.sub("", key).strip() if kind == "raw_player" else key.strip()
        if re.search(r"[\u3400-\u9fff]", literal) and displays["cn"] != literal:
            note = candidate.get("cn_conversion_note")
            if methods["cn"] != "orthographic_conversion" or not isinstance(note, str) or not note.strip():
                raise NameRejected("Chinese original was changed without orthographic explanation")
        if kind in {"player", "raw_player"} and _RANK.search(displays["cn"]):
            raise NameRejected("rank attached to player name")
        if kind in {"event", "raw_event"}:
            digits = re.findall(r"\d+", key)
            if any(not all(d in value for d in digits) for value in displays.values()):
                raise NameRejected("event year or round number lost")
            english = displays["en"]
            # Finite known mistranslations only; do not infer a catalog identity
            # from these terms or turn the event parser into a full glossary.
            if re.search(r"日本棋[圣聖][战戰戦]", key) and (
                not re.search(r"\bKisei\b", english, re.I)
                or "本因坊" not in key
                and re.search(r"\bHoninbo\b", english, re.I)
                or "名人" not in key
                and re.search(r"\bMeijin\b", english, re.I)
            ):
                raise NameRejected("English Japanese Kisei title was substituted")
            if re.findall(r"(?<!\d)(\d+)\s*[强強]", key) == ["8"] and re.search(
                r"\bRound\s+(?:of\s+)?16\b", english, re.I
            ):
                raise NameRejected("English 8-player stage contradicts Round of 16")
            if "青白江" in key and re.search(r"\bQingshuijiang\b", english, re.I):
                raise NameRejected("English Qingbaijiang place name was misspelled")
            if re.search(r"[烂爛]柯[杯盃]", key) and re.search(r"\bLangke\b", english, re.I):
                raise NameRejected("English Lanke cup name was misspelled")
        return candidate

    async def translate_and_review(
        self, kind: str, key: str, source_items: list[dict], sources=(), context=None
    ) -> dict:
        if not self.key or not self.key.strip():
            raise NeedsCredentials("Qwen API key must be supplied by caller")
        if kind not in KINDS or not isinstance(key, str) or not key.strip():
            raise ValueError("invalid name kind or key")
        if not isinstance(source_items, list) or not source_items:
            raise ValueError("source_items required")
        slots = {"event"} if kind in {"event", "raw_event"} else {"black", "white"}
        if any(
            not isinstance(item, dict)
            or set(item) != {"source_key", "source_item_id", "slot", "sgf_sha256"}
            or not isinstance(item["source_key"], str)
            or not item["source_key"]
            or not isinstance(item["source_item_id"], str)
            or not item["source_item_id"].isdigit()
            or item["slot"] not in slots
            or not isinstance(item["sgf_sha256"], str)
            or re.fullmatch(r"[0-9a-f]{64}", item["sgf_sha256"]) is None
            for item in source_items
        ):
            raise ValueError("source_items invalid")
        sources = list(sources)
        if any(not isinstance(s, dict) or not isinstance(s.get("url"), str) for s in sources):
            raise ValueError("source evidence invalid")
        async with self._semaphore:
            if self._items >= self.max_items:
                raise NameServiceError("name item budget exceeded")
            self._items += 1
            evidence = [
                {k: s[k] for k in ("url", "lang", "title", "retrieved_at", "excerpt", "content_sha256")}
                for s in sources
            ]
            prompt = {
                "kind": kind,
                "key": key,
                "context": context,
                "sources": evidence,
                "required_languages": LANGUAGES,
                "allowed_methods": sorted(METHODS),
                "output_fields": [
                    "displays",
                    "methods",
                    "original_language",
                    "source_urls",
                    "optional cn_conversion_note for an explained Chinese orthographic conversion",
                ],
                "output_shape": {
                    "displays": {lang: "string" for lang in LANGUAGES},
                    "methods": {lang: "one allowed method" for lang in LANGUAGES},
                    "original_language": "language code of the original",
                    "source_urls": "list of supplied URLs actually used",
                },
                "output_shape_rule": "displays and methods must be objects keyed by language, never arrays",
            }
            if kind == "raw_player" and isinstance(context, dict) and context.get("verified_reuse_displays"):
                prompt["verified_reuse_rule"] = (
                    "Preserve displays, original_language and methods exactly as supplied in context's "
                    "verified_reuse fields; they describe existing qualified provenance, not a new identity claim."
                )
            literal = _RANK.sub("", key).strip() if kind == "raw_player" else key.strip()
            if re.search(r"[\u3400-\u9fff]", literal):
                prompt["required_cn_literal"] = literal
                prompt["cn_literal_rule"] = (
                    "Set displays.cn to required_cn_literal exactly, character for character; do not add or remove "
                    "第, 赛, spaces, ranks, or other text. Only a necessary simplified/traditional character "
                    "conversion may differ, with methods.cn=orthographic_conversion and a cn_conversion_note."
                )
            if kind in {"event", "raw_event"}:
                digits = re.findall(r"\d+", key)
                prompt["required_digit_tokens"] = digits
                prompt["digit_rule"] = (
                    f"Each of cn, tw, jp, ko and en must contain every original digit token exactly: {digits}. "
                    "Use natural translated round names if useful, then add a localized numeric explanation. "
                    "Before returning JSON, check all five displays for every token. "
                    "Keep the cn original unchanged unless an orthographic conversion is explained."
                )
                prompt["english_event_rules"] = [
                    "For Japanese Kisei (日本棋圣战/日本棋聖戦), use Kisei. Honinbo means 本因坊 and Meijin means "
                    "名人; do not insert either unless the original explicitly names it.",
                    "If the only numbered knockout stage is 8强/8強, it is an 8-player stage: "
                    "Quarterfinal or Round of 8, never Round of 16, even with a Top 8 suffix.",
                    "青白江 is Qingbaijiang, never Qingshuijiang.",
                    "烂柯杯/爛柯盃 uses Lanke, never Langke. Preserve the original domestic/world/team scope.",
                ]
            repair_reason = None
            for repair in range(2):
                try:
                    candidate, producer = await self._call(
                        "producer", {**prompt, "repair_attempt": repair, "repair_reason": repair_reason}
                    )
                    self._candidate(candidate, kind, key, sources, context=context)
                    review, reviewer = await self._call(
                        "reviewer",
                        {
                            **prompt,
                            "candidate": candidate,
                            "review_instructions": "Approve or reject this exact candidate. "
                            'Return {"decision":"approve"} or {"decision":"reject"}; do not rewrite it.',
                        },
                    )
                    if set(review) != {"decision"} or review["decision"] != "approve":
                        raise NameRejected("independent review rejected candidate")
                    if producer["request_id"] == reviewer["request_id"]:
                        raise NameRejected("producer and review request IDs coincide")
                    from katrain.kifu_ingest.catalog import review_content_sha256, validate_decision

                    decision = {
                        "kind": kind,
                        "key": key,
                        "displays": candidate["displays"],
                        "original_language": candidate["original_language"],
                        "methods": candidate["methods"],
                        "sources": [s for s in evidence if s["url"] in candidate["source_urls"]],
                        "source_items": source_items,
                        "producer": producer,
                    }
                    if "cn_conversion_note" in candidate:
                        decision["cn_conversion_note"] = candidate["cn_conversion_note"]
                    decision["review"] = {
                        **reviewer,
                        "decision": "approve",
                        "content_sha256": review_content_sha256(decision),
                    }
                    validate_decision(decision)
                    return decision
                except NameRejected as exc:
                    if repair:
                        raise
                    repair_reason = str(exc)
            raise NameRejected("candidate could not be reviewed")

    async def review_existing_decision(self, decision: dict, source_items: list[dict]) -> dict:
        """Independently approve a successful producer result for a narrowed finite scope."""
        from katrain.kifu_ingest.catalog import review_content_sha256, validate_decision

        if not source_items or len(source_items) >= len(decision["source_items"]):
            raise ValueError("reviewed source scope must shrink")
        old_members = {tuple(sorted(member.items())) for member in decision["source_items"]}
        if any(tuple(sorted(member.items())) not in old_members for member in source_items):
            raise ValueError("reviewed source scope cannot expand")
        candidate = {
            "displays": decision["displays"],
            "methods": decision["methods"],
            "original_language": decision["original_language"],
            "source_urls": [source["url"] for source in decision["sources"]],
        }
        if "cn_conversion_note" in decision:
            candidate["cn_conversion_note"] = decision["cn_conversion_note"]
        review, reviewer = await self._call(
            "reviewer",
            {
                "kind": decision["kind"],
                "key": decision["key"],
                "candidate": candidate,
                "sources": decision["sources"],
                "source_items": source_items,
                "review_instructions": "Approve or reject this exact candidate for only these source items. "
                'Return {"decision":"approve"} or {"decision":"reject"}; do not rewrite it.',
            },
        )
        if set(review) != {"decision"} or review["decision"] != "approve":
            raise NameRejected("independent review rejected narrowed source scope")
        if decision["producer"]["request_id"] == reviewer["request_id"]:
            raise NameRejected("producer and review request IDs coincide")
        narrowed = {**decision, "source_items": source_items}
        narrowed["review"] = {
            **reviewer,
            "decision": "approve",
            "content_sha256": review_content_sha256(narrowed),
        }
        validate_decision(narrowed)
        return narrowed
