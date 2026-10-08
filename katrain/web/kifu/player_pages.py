"""Append reviewed person pages to existing players without changing name batches."""

from __future__ import annotations

from copy import deepcopy
import re
import unicodedata
from urllib.parse import parse_qs, unquote, urldefrag, urlparse

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from katrain.web.core.models_db import KifuNameResearchEvidence, KifuNameSourceRegistry, KifuPlayer, KifuPlayerName
from katrain.web.kifu.identity import _approved_names, _qualified_name_rows
from katrain.web.kifu.name_candidates import canonical_sha256

_ROLES = {"official", "language_go", "reference", "wikipedia_article", "encyclopedia"}
_BODY_SHA = re.compile(r"^[0-9a-f]{64}$")


def _page_url(value):
    """Keep the captured URL, excluding search/discovery URLs and page fragments."""
    if not isinstance(value, str):
        return None
    try:
        value = urldefrag(value.strip())[0]
        parsed = urlparse(value)
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.port not in (None, 443)
        ):
            return None
    except ValueError:
        return None
    path = unquote(parsed.path).lower()
    keys = {key.lower() for key in parse_qs(parsed.query)}
    if (
        keys & {"search", "query", "q", "srsearch", "fulltext"}
        or re.search(r"(?:^|/)(?:special:|(?:search|searchresults?)(?:[./:_-]|$))", path)
        or any(value.lower().startswith("special:") for value in parse_qs(parsed.query).get("title", []))
    ):
        return None
    return value


def _source(url, registry, source_id=None):
    """Use registered publisher and language paths, including Go Ratings editions."""
    parsed = urlparse(url)
    matches = []
    for source in registry.get("sources", []):
        if source.get("tier") not in _ROLES or source_id is not None and source.get("id") != source_id:
            continue
        home = urlparse(source.get("home_url", ""))
        prefix = home.path.rstrip("/")
        same_publisher = parsed.hostname == home.hostname or {parsed.hostname, home.hostname} <= {
            "goratings.org", "www.goratings.org"
        }
        if same_publisher and (
            not prefix or parsed.path == prefix or parsed.path.startswith(prefix + "/")
        ):
            matches.append((len(prefix), source))
    if not matches:
        return None
    longest = max(length for length, _ in matches)
    best = [source for length, source in matches if length == longest]
    return best[0] if len(best) == 1 else None


def _has_body(capture, *, require_http=True):
    return (
        isinstance(capture, dict)
        and capture.get("http_status") in ((200,) if require_http else (None, 200))
        and bool(_BODY_SHA.fullmatch(str(capture.get("body_sha256", ""))))
        and isinstance(capture.get("body_excerpt"), str)
        and bool(capture["body_excerpt"].strip())
    )


def _contains_name(capture, name):
    def normalized(value):
        return "".join(unicodedata.normalize("NFKC", value).split())

    return isinstance(name, str) and bool(name.strip()) and normalized(name) in normalized(capture["body_excerpt"])


def pages_from_evidence(name, evidence, registry_row):
    """Read only the reviewed research bound to this current physical player ID.

    The DB approval covers the candidate's research hash even when its captured
    research record still says pending. Unbound legacy payloads, symbolic owners
    and generated-source anchors without direct research are skipped, not guessed.
    """
    owner = {"kind": "player", "id": name.player_id}
    payload = evidence.research_payload
    if not isinstance(payload, dict) or registry_row is None:
        return []
    candidate, research = payload.get("candidate"), payload.get("research")
    registry = registry_row.registry
    if not all(isinstance(value, dict) for value in (candidate, research, registry)):
        return []
    if (
        candidate.get("owner") != owner
        or research.get("owner") != owner
        or candidate.get("review_status") != "approved"
        or candidate.get("lang") != name.lang
        or research.get("lang") != name.lang
        or candidate.get("display_name") != name.display_name
        or candidate.get("decision_kind") != name.decision_kind
        or candidate.get("generation_rule_version") != name.generation_rule_version
        or any(
            candidate.get(key) != getattr(evidence, key)
            for key in ("producer_id", "producer_model", "reviewer_id", "reviewer_model")
        )
        or candidate.get("research_sha256") != canonical_sha256(research)
        or registry_row.sha256 != canonical_sha256(registry)
        or research.get("registry_sha256") != registry_row.sha256
        or research.get("registry_version") != registry_row.version
        or research.get("scope_status") == "found"
        and research.get("candidate_name") != name.display_name
    ):
        return []
    found = []

    def add(capture, url, source_id=None, *, require_http=True):
        if not _has_body(capture, require_http=require_http) or capture.get("owner", owner) != owner:
            return
        url = _page_url(url)
        source = _source(url, registry, source_id) if url else None
        if source:
            found.append(
                {
                    "url": url,
                    "source_id": source["id"],
                    "language": capture.get("observed_lang") or capture.get("html_lang") or source["language"],
                    "role": source["tier"],
                    "evidence_ids": [evidence.id],
                }
            )

    original = research.get("original_name")
    checks = research.get("source_checks", [])
    for check in checks if isinstance(checks, list) else ():
        if (
            not _has_body(check)
            or check.get("status") != "found"
            or check.get("owner") != owner
            or not check.get("identity_basis")
            or not isinstance(check.get("source_id"), str)
            or not _contains_name(check, check.get("candidate_name"))
        ):
            continue
        # Unknown/incorrect publisher and discovery links cannot carry nested pages.
        url = _page_url(check.get("url"))
        if not url or not _source(url, registry, check.get("source_id")):
            continue
        add(check, url, check.get("source_id"))
        corroboration = check.get("identity_corroboration")
        if (
            _has_body(corroboration)
            and corroboration.get("original_name") == original
            and corroboration.get("identity_basis")
            and _contains_name(corroboration, original)
        ):
            add(corroboration, corroboration.get("url"), corroboration.get("source_id"))
        # These are explicit captured same-person profile bridges, not citations
        # found by recursively walking the source page or the research document.
        bridges = check.get("identity_bridges", [])
        for bridge in bridges if isinstance(bridges, list) else ():
            if _has_body(bridge) and _contains_name(bridge, original):
                add(bridge, bridge.get("url"), bridge.get("source_id"))
    original_capture = research.get("original_language_evidence")
    if (
        _has_body(original_capture, require_http=False)
        and original_capture.get("identity_basis")
        and _contains_name(original_capture, original)
    ):
        # Older approved records retain the body/hash without a separate HTTP field.
        add(original_capture, research.get("original_language_basis_url"), require_http=False)
    return found


def merge_pages(existing, additions):
    """Append URLs and evidence IDs while preserving all existing manual metadata."""
    if not isinstance(existing, list):
        raise ValueError("authoritative_pages must be a JSON array; existing data was not changed")
    merged = deepcopy(existing)
    by_url = {}
    for page in merged:
        if not isinstance(page, dict) or not isinstance(page.get("url"), str):
            raise ValueError("existing authoritative page needs a URL")
        ids = page.get("evidence_ids", [])
        if not isinstance(ids, list) or any(type(value) is not int or value < 1 for value in ids):
            raise ValueError("existing authoritative page has invalid evidence IDs")
        by_url.setdefault(page["url"], page)
    for page in sorted(additions, key=lambda page: page["url"]):
        current = by_url.get(page["url"])
        if current is None:
            current = deepcopy(page)
            merged.append(current)
            by_url[page["url"]] = current
        else:
            current["evidence_ids"] = sorted(set(current.get("evidence_ids", [])) | set(page["evidence_ids"]))
    return merged


def sync_player_pages(engine, *, player_ids=None, apply=False):
    """Preview or atomically append pages; callers explicitly choose the database."""
    if player_ids is not None and any(type(value) is not int or value < 1 for value in player_ids):
        raise ValueError("player IDs must be positive integers")
    postgres = engine.dialect.name == "postgresql"
    report = {
        "committed": apply,
        "players_scanned": 0,
        "eligible_names": 0,
        "names_with_pages": 0,
        "players_changed": 0,
        "pages_added": 0,
        "changes": [],
    }
    with engine.connect().execution_options(isolation_level="READ COMMITTED" if postgres else "SERIALIZABLE") as conn:
        with conn.begin(), Session(bind=conn) as db:
            if postgres:
                # Take UPDATE's ordinary table lock before any row locks. Name
                # batches take SHARE ROW EXCLUSIVE on this table first; upgrading
                # later while holding a player/name row could deadlock with them.
                conn.execute(
                    text("LOCK TABLE kifu_players IN ROW EXCLUSIVE MODE" if apply else "SET TRANSACTION READ ONLY")
                )
            ids = _approved_names(db, KifuPlayerName, "player_id", ids=None if player_ids is None else set(player_ids))
            ids = [
                row[0]
                for row in ids.with_entities(KifuPlayerName.player_id).distinct().order_by(KifuPlayerName.player_id)
            ]
            for player_id in ids:
                query = select(KifuPlayer).where(KifuPlayer.id == player_id)
                # Wait before reading the JSON so another sync/manual update cannot be lost.
                player = db.scalar(query.with_for_update() if apply else query)
                if player is None:
                    continue
                report["players_scanned"] += 1
                query = _approved_names(db, KifuPlayerName, "player_id", ids={player_id})
                if apply:
                    query = query.with_for_update(read=True, of=(KifuPlayerName, KifuNameResearchEvidence))
                additions = []
                for name, evidence in _qualified_name_rows(db, query, KifuPlayerName, "player_id"):
                    report["eligible_names"] += 1
                    found = pages_from_evidence(
                        name, evidence, db.get(KifuNameSourceRegistry, evidence.source_registry_id)
                    )
                    report["names_with_pages"] += bool(found)
                    additions.extend(found)
                merged = merge_pages(player.authoritative_pages, additions)
                if merged != player.authoritative_pages:
                    report["players_changed"] += 1
                    report["pages_added"] += len(merged) - len(player.authoritative_pages)
                    report["changes"].append(
                        {
                            "player_id": player_id,
                            "canonical_name": player.canonical_name,
                            "before": player.authoritative_pages,
                            "after": merged,
                        }
                    )
                    if apply:
                        player.authoritative_pages = merged
            if apply:
                db.flush()
    return report
