"""Validate auditable, pending kifu-name research records.

This module checks evidence format, not whether a name is historically correct.
Independent language review and the database import gate handle approval.
"""

from __future__ import annotations

import json
import re
import hashlib
import time
from copy import deepcopy
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen


DEFAULT_REGISTRY = Path(__file__).resolve().parents[3] / "docs/resource/kifu-name-source-registry.json"
OWNER_KINDS = {"player", "event", "raw_player", "raw_event"}
CHECK_STATUSES = {"found", "not_found", "incomplete", "unavailable"}
SCOPE_STATUSES = {"found", "not_found_in_scope", "incomplete"}
LANGUAGE_BASIS = {"html_lang", "http_header", "reviewed_text"}
SOURCE_PRIORITY = {"official": 0, "language_go": 1, "reference": 2,
                   "wikipedia_article": 3, "encyclopedia": 3, "discovery": 4}
_HEX_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_OWNER_REF = re.compile(r"^[a-z][a-z0-9_-]{1,63}$")


class EvidenceError(ValueError):
    """A research claim lacks the evidence needed for review."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise EvidenceError(message)


def _text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def owner_key(owner: object, lang: str) -> str:
    """Pin one existing DB ID or one new identity's bundle-local reference."""
    _require(isinstance(owner, dict) and owner.get("kind") in OWNER_KINDS, "one exact owner is required")
    if set(owner) == {"kind", "id"}:
        _require(type(owner["id"]) is int and owner["id"] > 0, "owner ID invalid")
        token = str(owner["id"])
    elif set(owner) == {"kind", "ref"}:
        _require(isinstance(owner["ref"], str) and bool(_OWNER_REF.fullmatch(owner["ref"])),
                 "owner symbolic reference invalid")
        token = "@" + owner["ref"]
    else:
        raise EvidenceError("one exact owner ID or symbolic reference is required")
    return f"{owner['kind']}:{token}:{lang}"


def _https_url(value: object) -> bool:
    if not _text(value):
        return False
    parsed = urlparse(value)
    return parsed.scheme == "https" and bool(parsed.netloc) and not parsed.username and not parsed.password


def _source_url_matches(url: str, source: dict) -> bool:
    if not _https_url(url):
        return False
    url_host = urlparse(url).hostname or ""
    source_host = urlparse(source["home_url"]).hostname or ""
    return url_host == source_host or url_host.endswith("." + source_host)


def _aware_timestamp(value: object) -> bool:
    if not _text(value):
        return False
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).tzinfo is not None
    except ValueError:
        return False


def load_registry(path: str | Path = DEFAULT_REGISTRY) -> dict:
    """Load the pinned discovery scope; it does not assert that any name is verified."""
    registry = json.loads(Path(path).read_text(encoding="utf-8"))
    _require(_text(registry.get("version")), "registry version is required")
    tags = registry.get("language_tags")
    _require(isinstance(tags, dict) and bool(tags), "registry language_tags are required")
    scopes = registry.get("language_scopes")
    _require(isinstance(scopes, dict) and set(scopes) == set(tags), "registry language scopes must cover all tags")
    sources = registry.get("sources")
    _require(isinstance(sources, list) and bool(sources), "registry sources are required")
    ids = [source.get("id") for source in sources]
    _require(all(_text(source_id) for source_id in ids) and len(ids) == len(set(ids)), "source IDs must be unique")
    for source in sources:
        _require(_https_url(source.get("home_url")), "source home_url must be HTTPS")
        _require(_text(source.get("tier")) and _text(source.get("language")), "source tier/language required")
    for lang, scope in scopes.items():
        required = scope.get("required_source_ids")
        _require(isinstance(required, list) and bool(required), f"{lang} scope must name sources")
        _require(all(source_id in ids for source_id in required), f"{lang} scope references unknown source")
        _require(isinstance(scope.get("complete_for_negative_claims"), bool), f"{lang} scope completion required")
    return registry


def registry_sha256(registry: dict) -> str:
    """Canonical content hash, independent of JSON whitespace and key order."""
    canonical = json.dumps(registry, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def product_language_tag(lang: str, registry: dict) -> str:
    try:
        return registry["language_tags"][lang]
    except (KeyError, TypeError) as exc:
        raise EvidenceError(f"unknown product language: {lang}") from exc


def source_plan(lang: str, registry: dict) -> list[dict]:
    """Return the registered target-language search scope in research order."""
    product_language_tag(lang, registry)
    sources = {source["id"]: source for source in registry["sources"]}
    required = registry["language_scopes"][lang]["required_source_ids"]
    return sorted((sources[source_id] for source_id in required),
                  key=lambda source: (SOURCE_PRIORITY.get(source["tier"], 99), source["id"]))


def _matches_target(observed: str, target: str) -> bool:
    observed = observed.lower().replace("_", "-")
    target = target.lower()
    if observed in {"mul", "und", "auto", "fallback", ""}:
        return False
    if target == "zh-hans":
        return observed == "zh-hans" or observed.startswith("zh-hans-") or observed in {"zh-cn", "zh-sg"}
    if target == "zh-hant":
        return observed == "zh-hant" or observed.startswith("zh-hant-") or observed in {"zh-tw", "zh-hk", "zh-mo"}
    return observed == target or observed.startswith(target + "-")


def _validate_discovery_label(check: dict, source: dict, target: str) -> None:
    """Require a separately captured language-specific API field for discovery leads."""
    evidence = check.get("label_evidence")
    _require(isinstance(evidence, dict), "discovery hit needs explicit API label evidence")
    api_url = evidence.get("api_url")
    _require(_source_url_matches(api_url, source), "API label URL must be on registered host")
    _require(urlparse(api_url).path.endswith(".json") or urlparse(api_url).path.endswith("/api.php"),
             "API label URL must identify a JSON or API response")
    _require(_aware_timestamp(evidence.get("fetched_at")), "API label timestamp required")
    _require(evidence.get("http_status") == 200, "API label response must have HTTP 200")
    _require(bool(_HEX_SHA256.fullmatch(str(evidence.get("response_sha256", "")))),
             "API label response hash required")
    pointer = evidence.get("json_pointer")
    _require(_text(pointer) and pointer.startswith("/") and "/labels/" in pointer
             and _matches_target(pointer.rsplit("/", 1)[-1], target),
             "API label field must explicitly name target language")
    if (urlparse(api_url).hostname or "").endswith("wikidata.org"):
        page_entity = re.fullmatch(r"/wiki/(Q[1-9][0-9]*)", urlparse(check["url"]).path)
        api_entity = re.fullmatch(r"/wiki/Special:EntityData/(Q[1-9][0-9]*)\.json", urlparse(api_url).path)
        _require(bool(page_entity and api_entity and page_entity.group(1) == api_entity.group(1)
                      and f"/entities/{page_entity.group(1)}/labels/" in pointer),
                 "Wikidata page, API and label pointer must identify the same entity")
    label = evidence.get("label")
    _require(isinstance(label, dict) and _text(label.get("language")) and _text(label.get("value")),
             "API label object must contain language and value")
    _require(_matches_target(label["language"], target) and label["value"] == check.get("candidate_name"),
             "API label language/value differs from candidate")
    _require(not check.get("label_lang") or check["label_lang"] == label["language"],
             "page label language conflicts with API label language")
    _require(evidence.get("fallback") is False, "API label cannot be a fallback")
    try:
        excerpt_label = json.loads(evidence.get("body_excerpt", ""))
    except (TypeError, json.JSONDecodeError) as exc:
        raise EvidenceError("API label body excerpt must contain the returned label object") from exc
    _require(excerpt_label == label, "API label excerpt differs from the claimed label")


def _validate_article_evidence(check: dict, sources: dict[str, dict], original_name: str) -> None:
    """Article usage is separate from an API label and needs outside identity evidence."""
    source = sources[check["source_id"]]
    article = check.get("article_evidence")
    _require(isinstance(article, dict), "article needs captured article evidence")
    if source["tier"] == "wikipedia_article":
        _require(_text(article.get("revision_id")) and str(article["revision_id"]).isdigit(),
                 "Wikipedia article revision ID required")
    else:
        _require(_text(article.get("edition")) or _text(article.get("revision_id")),
                 "encyclopedia edition or revision required")
    passage = article.get("passage")
    _require(_text(article.get("title")) and _text(passage)
             and check["candidate_name"] in passage
             and passage in check["body_excerpt"]
             and hashlib.sha256(passage.encode("utf-8")).hexdigest() == article.get("passage_sha256")
             and _text(article.get("subject_identity")),
             "article title, exact passage/hash and subject identity required")
    corroboration = check.get("identity_corroboration")
    _require(isinstance(corroboration, dict), "article needs separately published identity corroboration")
    other_id = corroboration.get("source_id")
    _require(other_id in sources and sources[other_id]["tier"] in {"official", "language_go", "reference"}
             and _source_url_matches(corroboration.get("url"), sources[other_id]),
             "identity corroboration needs a registered independent reference")
    article_host = urlparse(check["url"]).hostname
    other_host = urlparse(corroboration["url"]).hostname
    _require(article_host != other_host, "identity corroboration must be separately published")
    _require(_aware_timestamp(corroboration.get("fetched_at")) and corroboration.get("http_status") == 200
             and bool(_HEX_SHA256.fullmatch(str(corroboration.get("body_sha256", ""))))
             and _text(corroboration.get("body_excerpt")) and _text(corroboration.get("identity_basis"))
             and corroboration.get("original_name") == original_name
             and original_name in corroboration["body_excerpt"],
             "corroboration needs real body evidence for the exact original name")


def _validate_negative_outcome(check: dict, source: dict, producer_id: str) -> None:
    outcome = check.get("negative_outcome")
    _require(outcome in {"no_target_string", "rejected_leads"},
             "completed negative source needs an explicit outcome")
    leads = check.get("rejected_leads", [])
    if outcome == "no_target_string":
        _require(not leads, "no-string outcome cannot hide rejected leads")
        return
    _require(isinstance(leads, list) and bool(leads), "rejected lead outcome needs lead records")
    for lead in leads:
        _require(isinstance(lead, dict) and _text(lead.get("candidate_name"))
                 and _source_url_matches(lead.get("url"), source)
                 and bool(_HEX_SHA256.fullmatch(str(lead.get("body_sha256", ""))))
                 and _text(lead.get("body_excerpt"))
                 and lead["candidate_name"] in lead["body_excerpt"]
                 and _text(lead.get("rejection_basis"))
                 and _text(lead.get("reviewer_id")) and lead["reviewer_id"] != producer_id
                 and lead.get("reviewer_model") == "gpt-6-sol"
                 and _aware_timestamp(lead.get("reviewed_at")),
                 "rejected lead needs sourced body and independent Sol rejection")


def _validate_check(check: dict, owner: dict, target: str, sources: dict[str, dict]) -> None:
    _require(isinstance(check, dict), "source check must be an object")
    _require(check.get("owner") == owner, "source check owner differs from research record")
    source_id = check.get("source_id")
    _require(source_id in sources, f"unknown source: {source_id}")
    _require(_text(check.get("query")), "each source check needs its own query")
    status = check.get("status")
    _require(status in CHECK_STATUSES, "invalid source check status")
    _require(_source_url_matches(check.get("url"), sources[source_id]),
             "source check URL must be HTTPS on registered host")
    _require(_aware_timestamp(check.get("fetched_at")), "source check needs timezone-aware timestamp")
    if status in {"incomplete", "unavailable"}:
        _require(not _text(check.get("candidate_name")), "incomplete source cannot claim a candidate")
        return
    _require(check.get("http_status") == 200, "completed search requires HTTP 200")
    _require(bool(_HEX_SHA256.fullmatch(str(check.get("body_sha256", "")))), "completed search needs body SHA-256")
    _require(_text(check.get("body_excerpt")), "completed search needs real body excerpt")
    _require(check.get("language_basis") in LANGUAGE_BASIS, "completed search needs actual-language basis")
    observed = check.get("observed_lang")
    _require(_text(observed), "actual page language must be recorded")
    if sources[source_id]["tier"] != "discovery" or status == "not_found":
        _require(_matches_target(observed, target), "actual page language differs from target")
    returned = check.get("returned_lang")
    _require(not returned or _matches_target(returned, target), "returned label language differs from target")
    _require(not check.get("fallback"), "fallback label is not target-language evidence")
    if status == "found":
        _require(_text(check.get("candidate_name")), "found check needs candidate name")
        _require(check["candidate_name"] in check["body_excerpt"], "candidate must occur in captured body excerpt")
        _require(_text(check.get("identity_basis")), "found check needs identity matching basis")
        if sources[source_id]["tier"] == "discovery":
            _validate_discovery_label(check, sources[source_id], target)
    else:
        _require(not _text(check.get("candidate_name")), "not-found check cannot contain candidate")
        _require(check.get("scope_complete") is True and _text(check.get("search_scope")),
                 "not-found requires documented complete search scope")


def validate_research_record(record: dict, registry: dict) -> dict:
    """Validate one candidate or negative search claim, always returning pending status."""
    _require(isinstance(record, dict), "research record must be an object")
    owner = record.get("owner")
    lang = record.get("lang")
    exact_owner_key = owner_key(owner, lang)
    target = product_language_tag(lang, registry)
    _require(record.get("registry_version") == registry["version"], "registry version mismatch")
    _require(record.get("registry_sha256") == registry_sha256(registry), "registry hash mismatch")
    _require(record.get("review_status") == "pending", "research records must remain pending")
    _require(not any(record.get(key) for key in ("reviewer_id", "reviewer_model", "reviewed_at")),
             "research record cannot contain a review signature")
    _require(_text(record.get("producer_id")) and _text(record.get("producer_model")),
             "actual producer identity/model required")
    scope_status = record.get("scope_status")
    _require(scope_status in SCOPE_STATUSES, "invalid scope status")
    if scope_status != "incomplete":
        _require(_text(record.get("original_name")) and _text(record.get("original_language")),
                 "completed research needs original name and language")
        _require(_https_url(record.get("original_language_basis_url")),
                 "completed research needs original-language source URL")
        if _text(record.get("reading")):
            _require(_https_url(record.get("reading_basis_url")), "reading needs source URL")
    checks = record.get("source_checks")
    _require(isinstance(checks, list) and bool(checks), "source checks required")
    sources = {source["id"]: source for source in registry["sources"]}
    for check in checks:
        _validate_check(check, owner, target, sources)
        if check["status"] == "found" and sources[check["source_id"]]["tier"] in {
            "wikipedia_article", "encyclopedia"
        }:
            _require(_text(record.get("original_name")), "article identity needs original name")
            _validate_article_evidence(check, sources, record["original_name"])
    if scope_status == "found":
        candidate = record.get("candidate_name")
        _require(_text(candidate), "found record needs candidate name")
        _require(any(check["status"] == "found" and check["candidate_name"] == candidate for check in checks),
                 "candidate is not supported by a found source check")
    elif scope_status == "not_found_in_scope":
        _require(not _text(record.get("candidate_name")), "negative scope cannot claim a candidate")
        scope = registry["language_scopes"][lang]
        _require(scope["complete_for_negative_claims"], "source scope is incomplete for negative claims")
        for source_id in scope["required_source_ids"]:
            _require(any(check["source_id"] == source_id and check["status"] == "not_found" for check in checks),
                     f"source scope lacks completed negative search for {source_id}")
        _require(all(check["status"] == "not_found" for check in checks), "negative source scope has unresolved checks")
        for check in checks:
            _validate_negative_outcome(check, sources[check["source_id"]], record["producer_id"])
    else:
        _require(not _text(record.get("candidate_name")), "incomplete scope cannot claim a candidate")
    result = deepcopy(record)
    result["owner_key"] = exact_owner_key
    return result


class _VisibleHTML(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.language = ""
        self.hidden_depth = 0
        self.parts: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag == "html":
            self.language = dict(attrs).get("lang", "")
        if tag in {"script", "style"}:
            self.hidden_depth += 1

    def handle_endtag(self, tag):
        if tag in {"script", "style"} and self.hidden_depth:
            self.hidden_depth -= 1

    def handle_data(self, data):
        if not self.hidden_depth and data.strip():
            self.parts.append(data.strip())


def _excerpt(body_text: str, needle: str, limit: int = 500) -> str:
    at = body_text.find(needle) if needle else -1
    start = max(0, at - 120) if at >= 0 else 0
    return body_text[start:start + limit]


def capture_source_check(
    task: dict,
    registry: dict,
    *,
    open_url=urlopen,
    sleep=time.sleep,
    max_attempts: int = 3,
    timeout: float = 10.0,
    max_bytes: int = 2_000_000,
) -> dict:
    """Capture a page for one owner/language query; a page miss is never proof of absence.

    The caller supplies the intended candidate and identity basis. This routine only
    checks that the text appears on a same-language page and leaves review pending.
    """
    _require(isinstance(task, dict), "capture task must be an object")
    owner = task.get("owner")
    owner_key(owner, task.get("lang"))
    lang = task.get("lang")
    target = product_language_tag(lang, registry)
    source = next((item for item in registry["sources"] if item["id"] == task.get("source_id")), None)
    _require(source is not None, "capture task has unknown source")
    url = task.get("url")
    _require(_source_url_matches(url, source), "capture URL must be HTTPS on registered host")
    _require(_text(task.get("query")), "capture query required")
    _require(max_attempts >= 1 and max_bytes >= 1, "invalid capture limits")
    candidate = task.get("candidate_name", "")
    check = {
        "owner": deepcopy(owner),
        "source_id": source["id"],
        "query": task["query"],
        "status": "unavailable",
        "url": url,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "http_status": None,
        "body_sha256": "",
        "body_excerpt": "",
        "observed_lang": "",
        "language_basis": "",
        "candidate_name": "",
    }
    request = Request(url, headers={"User-Agent": "KifuNameResearch/1.0 (+evidence capture; no auto approval)"})
    for attempt in range(max_attempts):
        try:
            with open_url(request, timeout=timeout) as response:
                check["http_status"] = getattr(response, "status", 200)
                resolved_url = getattr(response, "url", url)
                _require(_source_url_matches(resolved_url, source), "redirect left registered source host")
                check["url"] = resolved_url
                raw = response.read(max_bytes + 1)
                if check["http_status"] != 200 or len(raw) > max_bytes or not raw.strip():
                    check["status"] = "incomplete"
                    return check
                charset = response.headers.get_content_charset() or "utf-8"
                try:
                    markup = raw.decode(charset)
                except (UnicodeDecodeError, LookupError):
                    check["status"] = "incomplete"
                    return check
                parser = _VisibleHTML()
                parser.feed(markup)
                body_text = " ".join(parser.parts)
                observed = parser.language or response.headers.get("Content-Language", "")
                check.update({
                    "body_sha256": hashlib.sha256(raw).hexdigest(),
                    "body_excerpt": _excerpt(body_text, candidate),
                    "observed_lang": observed,
                    "language_basis": "html_lang" if parser.language else "http_header" if observed else "",
                })
                if not body_text or not _matches_target(observed, target):
                    check["status"] = "incomplete"
                    return check
                if not (_text(candidate) and candidate in body_text and _text(task.get("identity_basis"))):
                    check["status"] = "incomplete"
                    return check
                if source["tier"] == "discovery":
                    # An HTML page language says nothing about API label fallback.
                    check["status"] = "incomplete"
                    return check
                check["status"] = "found"
                check["candidate_name"] = candidate
                check["identity_basis"] = task["identity_basis"]
                return check
        except HTTPError as exc:
            check["http_status"] = exc.code
            if exc.code not in {429, 500, 502, 503, 504} or attempt == max_attempts - 1:
                return check
        except (URLError, OSError):
            if attempt == max_attempts - 1:
                return check
        sleep(min(2 ** attempt, 8))
    return check
