"""Atomic publication of logical, independently reviewed incremental game manifests.

Model/network work happens before this API. IDs are always resolved in the target
database. The existing strict first-pass proof/journal format is retained; the
versioned ``incremental_binding`` explains which content was reviewed outside the
transaction and which finite IDs/scopes were bound by deterministic code.
"""

from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
import json
import re
from urllib.parse import urlparse

from sqlalchemy import Text, and_, cast, func, or_, select, text, true, update
from sqlalchemy.exc import DBAPIError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, defer

from katrain.core.sgf_parser import ParseError, SGF
from katrain.kifu_ingest.exclusions import assert_source_allowed
from katrain.kifu_ingest.preparation import derive_metadata
from katrain.kifu_ingest.ranks import (
    FORMAT_V2,
    historical_game_targets,
    is_historical_snapshot,
    validate_manifest_ranks,
    validate_rank_snapshot,
    validate_rank_outcomes,
    portable_rank_outcomes,
    expected_rank_for_outcome,
)
from katrain.web.kifu import historical_ranks
from katrain.web.core.models_db import (
    KifuAlbum,
    KifuAlbumSource,
    KifuAlbumEventSelection,
    KifuEvent,
    KifuEventAlias,
    KifuNameBatch,
    KifuNameChange,
    KifuNameResearchEvidence,
    KifuNameSourceRegistry,
    KifuPlayer,
    KifuPlayerRankHistory,
    KifuAlbumRankSnapshot,
    KifuPlayerAlias,
    KifuRawEventName,
    KifuRawEventValue,
    KifuRawPlayerName,
    KifuRawPlayerValue,
    KifuSource,
    KifuDedupBatch,
    KifuDedupChange,
)
from katrain.web.kifu import name_batch, name_first_pass
from katrain.web.kifu import player_ranks
from katrain.web.kifu import catalog_standardization
from katrain.web.kifu.identity import (
    _approved_names,
    _qualified_name_rows,
    _approved_raw_event_names,
    _approved_raw_player_names,
    live_event_selections,
    normalize_alias,
    player_identity_name,
    strict_slot_approvals,
)
from katrain.web.kifu.name_candidates import canonical_sha256, _validate_candidate
from katrain.web.kifu.name_parse import parse_event, parse_player
from katrain.web.kifu.name_raw_player_scope import CONTEXT_FIELDS


FORMAT = "kifu-incremental-manifest-v1"
FORMATS = (FORMAT, FORMAT_V2)
BINDING_VERSION = "kifu-incremental-binding-v1"
LANGUAGES = ("cn", "tw", "jp", "ko", "en")
_STATEMENT_TIMEOUT_MS = 15 * 60 * 1000
_PUBLICATION_LOCK_KEY = 0x4B49465550554231
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_ALBUM_METADATA = frozenset(
    {
        "player_black",
        "player_white",
        "black_rank",
        "white_rank",
        "event",
        "result",
        "date_played",
        "date_sort",
        "place",
        "komi",
        "handicap",
        "board_size",
        "rules",
        "round_name",
        "source",
        "move_count",
        "search_text",
    }
)
_REGISTRY = {
    "version": BINDING_VERSION,
    "sources": [],
    "purpose": "deterministic local publication bindings",
    "language_tags": {"cn": "zh-Hans", "tw": "zh-Hant", "jp": "ja", "ko": "ko", "en": "en"},
}


class PublicationError(ValueError):
    """Nothing was published because a pinned source, identity or proof differed."""


def _require(condition, message):
    if not condition:
        raise PublicationError(message)


def review_content_sha256(decision):
    """Hash all logical text, evidence, methods and finite source membership."""
    return canonical_sha256({key: value for key, value in decision.items() if key != "review"})


def validate_decision(decision):
    """Validate immutable logical review content without a database or model call."""
    _require(
        isinstance(decision, dict)
        and decision.get("kind") in name_batch._OWNER
        and isinstance(decision.get("key"), str)
        and decision["key"].strip(),
        "decision owner invalid",
    )
    displays, methods = decision.get("displays"), decision.get("methods")
    _require(
        isinstance(displays, dict)
        and set(displays) == set(LANGUAGES)
        and all(isinstance(value, str) and value.strip() for value in displays.values()),
        "decision requires exactly five language displays",
    )
    _require(
        isinstance(methods, dict)
        and set(methods) == set(LANGUAGES)
        and set(methods.values()) <= name_first_pass.METHODS
        and isinstance(decision.get("original_language"), str)
        and decision["original_language"],
        "decision generation methods missing or invalid",
    )
    producer, review = decision.get("producer"), decision.get("review")
    _require(
        isinstance(producer, dict)
        and isinstance(review, dict)
        and all(
            isinstance(actor.get(key), str) and actor[key].strip()
            for actor in (producer, review)
            for key in ("id", "model", "request_id", "at")
        )
        and producer["id"] != review["id"]
        and producer["request_id"] != review["request_id"]
        and review.get("decision") == "approve"
        and review.get("content_sha256") == review_content_sha256(decision),
        "independent actual producer/reviewer request identity or content hash invalid",
    )
    try:
        produced = datetime.fromisoformat(producer["at"].replace("Z", "+00:00"))
        reviewed = datetime.fromisoformat(review["at"].replace("Z", "+00:00"))
        _require(
            produced.tzinfo is not None and reviewed.tzinfo is not None and reviewed >= produced,
            "decision review chronology invalid",
        )
    except (ValueError, TypeError) as exc:
        raise PublicationError("decision timestamp invalid") from exc
    sources = decision.get("sources")
    _require(isinstance(sources, list), "decision sources must explicitly list evidence or be empty")
    for source in sources:
        _require(
            isinstance(source, dict)
            and isinstance(source.get("excerpt"), str)
            and source.get("content_sha256") == sha256(source["excerpt"].encode("utf-8")).hexdigest()
            and all(
                isinstance(source.get(key), str) and source[key].strip()
                for key in ("url", "lang", "title", "retrieved_at")
            ),
            "source evidence/hash invalid",
        )
        parsed_url = urlparse(source["url"])
        _require(
            parsed_url.scheme in {"https", "http"}
            and parsed_url.hostname
            and not parsed_url.username
            and not parsed_url.password,
            "source evidence URL invalid",
        )
        try:
            retrieved = datetime.fromisoformat(source["retrieved_at"].replace("Z", "+00:00"))
            _require(retrieved.tzinfo is not None and retrieved <= reviewed, "source retrieved after review")
        except (ValueError, TypeError) as exc:
            raise PublicationError("source retrieval time invalid") from exc
    members = decision.get("source_items")
    _require(isinstance(members, list) and members, "decision requires finite source_items")
    seen = set()
    for member in members:
        _require(
            isinstance(member, dict)
            and set(member) == {"source_key", "source_item_id", "slot", "sgf_sha256"}
            and isinstance(member["source_key"], str)
            and isinstance(member["source_item_id"], str)
            and member["slot"] in ({"event"} if decision["kind"] in {"event", "raw_event"} else {"black", "white"})
            and isinstance(member["sgf_sha256"], str)
            and _SHA.fullmatch(member["sgf_sha256"]),
            "decision source member invalid",
        )
        key = member["source_key"], member["source_item_id"], member["slot"]
        _require(key not in seen, "duplicate decision source member")
        seen.add(key)
    return decision


def _canonical_sgf(content):
    return SGF.parse_sgf(content).sgf()


def _cached_canonical_sha(content, cache):
    content_hash = sha256(content.encode("utf-8")).hexdigest()
    if content_hash not in cache:
        try:
            cache[content_hash] = sha256(_canonical_sgf(content).encode("utf-8")).hexdigest()
        except Exception:
            cache[content_hash] = None
    return cache[content_hash]


def warm_sgf_cache(engine, cache=None):
    """Parse immutable content outside the write lock; retain hashes, never SGFs.

    A caller publishing several manifests can keep this process-local dictionary.
    Locked reads still hash current bytes, and any possible match is compared in
    full. New or changed content gets a new cache key and is parsed again.
    """
    cache = {} if cache is None else cache
    with engine.connect() as conn:
        rows = conn.execution_options(stream_results=True).execute(select(KifuAlbum.sgf_content)).yield_per(500)
        for content in rows.scalars():
            _cached_canonical_sha(content, cache)
    return cache


def _validate_manifest(manifest, expected):
    _require(
        isinstance(expected, str) and _SHA.fullmatch(expected) and canonical_sha256(manifest) == expected,
        "manifest hash mismatch",
    )
    _require(
        manifest.get("format") in FORMATS
        and isinstance(manifest.get("publication_key"), str)
        and manifest["publication_key"].strip(),
        "manifest format or publication key missing",
    )
    games = manifest.get("games")
    _require(isinstance(games, list) and 1 <= len(games) <= 100, "manifest needs a finite game list")
    _require(isinstance(manifest.get("decisions", []), list), "decisions must be a list")
    seen = set()
    prepared = []
    for game in games:
        _require(isinstance(game, dict), "game must be an object")
        source_key, item_id = game.get("source_key"), game.get("source_item_id")
        _require(
            isinstance(source_key, str)
            and 0 < len(source_key) <= 64
            and isinstance(item_id, str)
            and re.fullmatch(r"[0-9]+", item_id),
            "source identity invalid",
        )
        _require((source_key, item_id) not in seen, "duplicate source identity in manifest")
        try:
            assert_source_allowed(source_key, item_id)
        except ValueError as exc:
            raise PublicationError(str(exc)) from exc
        seen.add((source_key, item_id))
        _require(
            isinstance(game.get("origin_path"), str) and 0 < len(game["origin_path"]) <= 512, "origin path invalid"
        )
        content = game.get("sgf_content")
        _require(
            isinstance(content, str)
            and content
            and sha256(content.encode("utf-8")).hexdigest() == game.get("sgf_sha256")
            and isinstance(game.get("raw_sha256"), str)
            and _SHA.fullmatch(game["raw_sha256"]),
            "complete SGF content/hash invalid",
        )
        metadata = game.get("metadata")
        _require(
            isinstance(metadata, dict)
            and set(metadata) <= _ALBUM_METADATA
            and all(
                isinstance(metadata.get(key), str) and metadata[key].strip() for key in ("player_black", "player_white")
            ),
            "album metadata invalid",
        )
        try:
            root = SGF.parse_sgf(content)
            canonical = root.sgf()
            derived = derive_metadata(content, game.get("source_metadata"), source_key)
        except Exception as exc:
            raise PublicationError(f"SGF/metadata cannot be prepared: {exc}") from exc
        if manifest["format"] == FORMAT_V2:
            _require(
                all(metadata.get(f"{side}_rank") == derived.get(f"{side}_rank") for side in ("black", "white")),
                "album original rank assertion differs from deterministic SGF/source derivation",
            )
        _require(
            all(value == derived.get(field) for field, value in metadata.items()),
            "album metadata differs from deterministic SGF/source derivation",
        )
        _require(metadata.get("event") == derived["event"], "event metadata differs from SGF/source derivation")
        prepared.append((game, canonical))
    indexed_games = {(game["source_key"], game["source_item_id"]): game for game, _ in prepared}
    seen_decisions = set()
    for decision in manifest.get("decisions", []):
        validate_decision(decision)
        key = decision["kind"], decision["key"]
        _require(key not in seen_decisions, "duplicate name decision")
        seen_decisions.add(key)
        for member in decision["source_items"]:
            game = indexed_games.get((member["source_key"], member["source_item_id"]))
            _require(
                game is not None and game["sgf_sha256"] == member["sgf_sha256"],
                "decision source scope differs from manifest",
            )
            slot = member["slot"]
            raw = game["metadata"].get("event" if slot == "event" else f"player_{slot}")
            if decision["kind"].startswith("raw_"):
                _require(raw == decision["key"], "decision raw scope differs from literal source")
            elif isinstance(game.get("identities", {}).get(slot), dict):
                _require(
                    game["identities"][slot] == {"canonical_name": decision["key"]},
                    "decision canonical scope differs from identity binding",
                )
    try:
        validate_manifest_ranks(manifest)
    except (KeyError, TypeError, ValueError) as exc:
        raise PublicationError(str(exc)) from exc
    return prepared


def _identity_indexes(conn):
    result = {}
    for kind, model, alias, column in (
        ("player", KifuPlayer, KifuPlayerAlias, "player_id"),
        ("event", KifuEvent, KifuEventAlias, "event_id"),
    ):
        index = {}
        for owner_id, value in conn.execute(select(model.id, model.canonical_name)):
            index.setdefault(normalize_alias(value), set()).add(owner_id)
        for owner_id, value in conn.execute(select(getattr(alias, column), alias.normalized_alias)):
            index.setdefault(value, set()).add(owner_id)
        result[kind] = index
    return result


def _resolve_identity(kind, raw, instruction, indexes):
    if instruction is None:
        return None
    _require(
        instruction == "auto" or isinstance(instruction, dict) and set(instruction) == {"canonical_name"},
        "identity instruction must use a logical canonical name, never a database ID",
    )
    raw_needle = player_identity_name(raw) if kind == "player" else raw
    raw_owners = indexes[kind].get(normalize_alias(raw_needle), set())
    _require(len(raw_owners) <= 1, f"ambiguous {kind} raw identity: {raw}")
    needle = instruction.get("canonical_name") if isinstance(instruction, dict) else raw_needle
    _require(isinstance(needle, str) and needle.strip(), "identity lookup key missing")
    normalized = normalize_alias(needle)
    owners = indexes[kind].get(normalized, set())
    _require(len(owners) <= 1, f"ambiguous {kind} alias: {needle}")
    if isinstance(instruction, dict):
        _require(owners, f"unknown {kind} identity: {needle}")
        _require(not raw_owners or raw_owners == owners, f"conflicting {kind} raw identity: {raw}")
    return next(iter(owners), None)


def _require_public(conn, ids):
    public = set(
        conn.scalars(
            select(KifuAlbum.id).where(
                KifuAlbum.id.in_(ids), KifuAlbum.duplicate_of_id.is_(None), KifuAlbum.list_hidden_reason.is_(None)
            )
        )
    )
    _require(public == set(ids), "requested album is missing, hidden or duplicate; publication requires public albums")


def _require_source_publication(conn, ids, *, resource=None):
    """Original receipts remain exact; only proved display dedup may hide them."""
    from katrain.web.kifu.catalog_standardization import verified_display_duplicate

    for album_id in ids:
        album = (
            conn.execute(
                select(KifuAlbum.list_hidden_reason, KifuAlbum.duplicate_of_id).where(KifuAlbum.id == album_id)
            )
            .mappings()
            .one_or_none()
        )
        _require(
            album is not None and album["list_hidden_reason"] is None,
            "requested album is missing, hidden or duplicate; publication requires public albums",
        )
        if album["duplicate_of_id"] is not None:
            try:
                proof = verified_display_duplicate(conn, album_id, resource=resource)
            except ValueError as exc:
                raise PublicationError("duplicate album has no verified same-game dedup journal") from exc
            _require_public(conn, {proof["canonical_album_id"]})


def _select_source_owner(conn, game, matches, origin_owners, *, resource=None):
    """An aggregated provenance link cannot replace the original SGF owner."""
    from katrain.web.kifu.catalog_standardization import verified_display_duplicate

    direct = set(
        conn.scalars(
            select(KifuAlbum.id).where(KifuAlbum.id.in_(matches), KifuAlbum.source_path == game["origin_path"])
        )
    )
    original = set(
        conn.scalars(
            select(KifuAlbumSource.album_id).where(
                KifuAlbumSource.album_id.in_(matches),
                KifuAlbumSource.origin_path == game["origin_path"],
                KifuAlbumSource.match_method != "reviewed_same_game",
            )
        )
    )
    owners = direct or original or matches
    _require(len(owners) <= 1, "multiple exact SGFs require explicit duplicate resolution")
    chosen = next(iter(owners), None)
    for owner in origin_owners:
        if owner in matches:
            continue
        _require(chosen is not None, "existing source path content changed")
        try:
            proof = verified_display_duplicate(conn, chosen, resource=resource)
        except ValueError as exc:
            raise PublicationError("existing source path content changed") from exc
        _require(proof and proof["canonical_album_id"] == owner, "existing source path content changed")
    return chosen


def _check_reused_identity_instructions(conn, game, album_id, indexes):
    instructions = game.get("identities", {})
    if not instructions:
        return
    album = (
        conn.execute(
            select(KifuAlbum.black_player_id, KifuAlbum.white_player_id, KifuAlbum.event_id).where(
                KifuAlbum.id == album_id
            )
        )
        .mappings()
        .one_or_none()
    )
    _require(album is not None, "reused identity album is missing")
    for slot in ("black", "white", "event"):
        if slot not in instructions:
            continue
        kind = "event" if slot == "event" else "player"
        raw_field = "event" if slot == "event" else f"player_{slot}"
        id_field = "event_id" if slot == "event" else f"{slot}_player_id"
        expected = _resolve_identity(kind, game["metadata"].get(raw_field), instructions[slot], indexes)
        _require(album[id_field] == expected, "explicit identity instruction differs from reused album identity")


def _coverage(conn, ids, *, resource=None):
    if not ids:
        return
    with Session(bind=conn) as db:
        albums = (
            db.query(KifuAlbum)
            .options(defer(KifuAlbum.sgf_content, raiseload=True))
            .filter(KifuAlbum.id.in_(ids))
            .all()
        )
        from katrain.web.kifu.catalog_standardization import verified_display_duplicate

        retained = []
        for album in albums:
            if album.list_hidden_reason is not None:
                continue
            if album.duplicate_of_id is not None:
                try:
                    verified_display_duplicate(conn, album.id, resource=resource)
                except ValueError:
                    continue
            retained.append(album)
        albums = retained
        selected = live_event_selections(db, albums)
        for lang in LANGUAGES:
            approvals = strict_slot_approvals(db, albums, lang, selected_events=selected)
            missing = [album.id for album in albums if not all(approvals.get(album.id, (None, None, None)))]
            _require(not missing, f"five-language coverage missing for {lang}: {missing[:10]}")


def _existing_event_proofs(conn, raws):
    result = {}
    with Session(bind=conn) as db:
        for name, raw, proof in _approved_raw_event_names(db, values=raws):
            if name.lang not in LANGUAGES:
                continue
            result[(raw, name.lang)] = {
                "name": name_batch._image(conn, KifuRawEventName.__table__, name.id),
                "evidence": name_batch._image(conn, KifuNameResearchEvidence.__table__, name.evidence_id),
                "scope": proof,
            }
    return result


def _existing_player_proofs(conn, raws):
    result = {}
    scopes_by_batch = {}
    with Session(bind=conn) as db:
        for name, raw, scope in _approved_raw_player_names(db, values=raws):
            if name.lang not in LANGUAGES:
                continue
            evidence = name_batch._image(conn, KifuNameResearchEvidence.__table__, name.evidence_id)
            proof = evidence["research_payload"].get("raw_display_scope")
            if proof and proof["batch_id"] not in scopes_by_batch:
                batch = name_batch._image(conn, KifuNameBatch.__table__, proof["batch_id"])
                scopes_by_batch[proof["batch_id"]] = (
                    {
                        row["owner"]["id"]: row["raw_display_scope"]
                        for row in batch["reviewed_artifact"]["bundle"].get("owners", ())
                        if row.get("owner", {}).get("kind") == "raw_player"
                        and "id" in row["owner"]
                        and "raw_display_scope" in row
                    }
                    if batch
                    else {}
                )
            scope = scopes_by_batch.get(proof["batch_id"], {}).get(name.raw_player_id) if proof else None
            result[(raw, name.lang)] = {
                "name": name_batch._image(conn, KifuRawPlayerName.__table__, name.id),
                "evidence": evidence,
                "scope": deepcopy(scope),
            }
    return result


def qualified_raw_player_templates(engine, *, raw_values=None):
    """Read target-qualified literal templates; never fabricate a fresh review.

    ``templates`` are incomplete logical decisions: callers must supply current
    producer, review and finite source_items. ``target_bindings`` preserve each
    language's full native source meaning for comparing TEST/PROD differences;
    those local IDs and preimages do not belong in a portable logical decision.
    """
    return _qualified_raw_templates(engine, "raw_player", raw_values)


def qualified_raw_event_templates(engine, *, raw_values=None):
    """Report qualified native event text that publication can renew unchanged.

    Entries in ``templates`` need no new text decision or model review: omit
    those raw events from the manifest decisions. Publication rechecks the live
    proof and binds its complete new occurrence scope in the locked transaction.
    Frozen profiles are reported unavailable rather than expanded. Per-language
    original meaning and source evidence remain in ``target_bindings``.
    """
    return _qualified_raw_templates(engine, "raw_event", raw_values)


def _qualified_raw_templates(engine, kind, raw_values):
    with engine.connect() as conn:
        capture = _existing_player_proofs if kind == "raw_player" else _existing_event_proofs
        captured = capture(conn, None if raw_values is None else set(raw_values))
        raws = sorted(set(raw_values) if raw_values is not None else {raw for raw, _lang in captured})
        templates, bindings, unavailable = {}, {}, {}
        for raw in raws:
            members = {lang: captured.get((raw, lang)) for lang in LANGUAGES}
            if not all(members.values()):
                unavailable[raw] = "missing_qualified_five_languages"
                continue
            if not all(
                member["name"]["generation_rule_version"] == name_first_pass.VERSION
                and member["scope"]
                and (kind == "raw_player" or "first_pass" in member["scope"])
                for member in members.values()
            ):
                unavailable[raw] = "no_native_generated_scope_refresh"
                continue
            records = {lang: member["evidence"]["research_payload"]["research"] for lang, member in members.items()}
            languages = {record["original_language"] for record in records.values()}
            if len(languages) != 1 and kind == "raw_player":
                unavailable[raw] = "different_original_languages_require_separate_review"
                continue
            source_pages = {}
            for record in records.values():
                for source in record.get("sources", ()):
                    source_pages[canonical_sha256(source)] = deepcopy(source)
            templates[raw] = {
                "kind": kind,
                "key": raw,
                "displays": {lang: member["name"]["display_name"] for lang, member in members.items()},
                "original_language": next(iter(languages)) if len(languages) == 1 else None,
                "methods": {lang: record["generation"]["method"] for lang, record in records.items()},
                "sources": [source_pages[key] for key in sorted(source_pages)],
            }
            bindings[raw] = {}
            for lang, record in records.items():
                member = members[lang]
                meaning = {
                    field: deepcopy(record[field])
                    for field in ("original_name", "original_language", "source_input", "generation")
                }
                bindings[raw][lang] = {
                    "owner_id": member["name"][f"{kind}_id"],
                    "name_id": member["name"]["id"],
                    "evidence_id": member["evidence"]["id"],
                    "revision": member["name"]["revision"],
                    "source_meaning": meaning,
                    "source_meaning_sha256": canonical_sha256(meaning),
                    "name_preimage_sha256": canonical_sha256(member["name"]),
                    "evidence_preimage_sha256": canonical_sha256(member["evidence"]),
                }
        return {"templates": templates, "target_bindings": bindings, "unavailable": unavailable}


def lookup_qualified_identities(engine, *, player_values=(), event_values=()):
    """Read only canonical/alias matches with five qualified native names.

    Display translations never participate in identity matching. Returned IDs
    describe this target only; portable manifests use the canonical_name field.
    """
    result = {"player": {}, "event": {}}
    with engine.connect() as conn:
        indexes = _identity_indexes(conn)
        for kind, values in (("player", player_values), ("event", event_values)):
            owner_model, name_model, owner_column = name_batch._OWNER[kind]
            resolved = {}
            for raw in values:
                needle = player_identity_name(raw) if kind == "player" else raw
                owners = indexes[kind].get(normalize_alias(needle), set())
                if len(owners) != 1:
                    result[kind][raw] = {"status": "ambiguous" if owners else "unresolved"}
                else:
                    resolved[raw] = next(iter(owners))
            if not resolved:
                continue
            ids = set(resolved.values())
            canonical = dict(
                conn.execute(select(owner_model.id, owner_model.canonical_name).where(owner_model.id.in_(ids))).all()
            )
            by_owner = {}
            with Session(bind=conn) as db:
                rows = _qualified_name_rows(
                    db, _approved_names(db, name_model, owner_column, ids), name_model, owner_column
                )
                for name, _evidence in rows:
                    if name.lang in LANGUAGES:
                        by_owner.setdefault(getattr(name, owner_column), {})[name.lang] = name.display_name
            for raw, owner_id in resolved.items():
                displays = by_owner.get(owner_id, {})
                result[kind][raw] = {
                    "status": "qualified" if set(displays) == set(LANGUAGES) else "missing_qualified_five_languages",
                    "id": owner_id,
                    "canonical_name": canonical[owner_id],
                    "displays": displays,
                }
    return result


IDENTITY_CHECK_STATUSES = frozenset(
    {
        "qualified",
        "missing_qualified_five_languages",
        "unresolved",
        "ambiguous",
        "conflict",
        "canonical_decision_key_mismatch",
    }
)


def validate_identity_check_request(request):
    _require(
        isinstance(request, dict)
        and set(request) == {"operation", "game_count", "instructions"}
        and request["operation"] == "check-identities"
        and type(request["game_count"]) is int
        and 1 <= request["game_count"] <= 100
        and isinstance(request["instructions"], list)
        and len(request["instructions"]) <= min(300, 3 * request["game_count"]),
        "identity check request invalid",
    )
    seen = set()
    for row in request["instructions"]:
        _require(
            isinstance(row, dict)
            and set(row) == {"kind", "raw", "canonical_name", "name_decision"}
            and isinstance(row["kind"], str)
            and row["kind"] in {"player", "event"}
            and type(row["name_decision"]) is bool
            and all(
                isinstance(row[field], str) and row[field].strip() and len(row[field]) <= 512
                for field in ("raw", "canonical_name")
            ),
            "identity check instruction invalid",
        )
        key = row["kind"], row["raw"], row["canonical_name"]
        _require(key not in seen, "identity check instructions must be unique")
        seen.add(key)
    return request


def validate_identity_check_response(request, response):
    validate_identity_check_request(request)
    _require(
        isinstance(response, dict)
        and set(response) == {"status", "request_sha256", "results"}
        and response["status"] == "checked"
        and response["request_sha256"] == canonical_sha256(request)
        and isinstance(response["results"], list)
        and len(response["results"]) == len(request["instructions"])
        and all(isinstance(value, str) and value in IDENTITY_CHECK_STATUSES for value in response["results"]),
        "identity check response invalid",
    )
    return response


def check_identity_instructions(engine, request):
    """Resolve bounded logical instructions on this target; expose no local IDs."""
    validate_identity_check_request(request)
    results, resolved = [], {"player": {}, "event": {}}
    with engine.connect() as conn, conn.begin():
        if conn.dialect.name == "postgresql":
            conn.execute(text("SET TRANSACTION READ ONLY"))
        indexes = _identity_indexes(conn)
        for index, row in enumerate(request["instructions"]):
            try:
                owner_id = _resolve_identity(
                    row["kind"], row["raw"], {"canonical_name": row["canonical_name"]}, indexes
                )
            except PublicationError as exc:
                message = str(exc)
                results.append(
                    "unresolved"
                    if message.startswith("unknown ")
                    else "ambiguous" if message.startswith("ambiguous ") else "conflict"
                )
            else:
                resolved[row["kind"]][index] = owner_id
                results.append("missing_qualified_five_languages")
        for kind, owners in resolved.items():
            if not owners:
                continue
            owner_model, name_model, owner_column = name_batch._OWNER[kind]
            canonical = dict(
                conn.execute(
                    select(owner_model.id, owner_model.canonical_name).where(owner_model.id.in_(set(owners.values())))
                ).all()
            )
            languages = {}
            with Session(bind=conn) as db:
                for name, _evidence in _qualified_name_rows(
                    db, _approved_names(db, name_model, owner_column, set(owners.values())), name_model, owner_column
                ):
                    if name.lang in LANGUAGES:
                        languages.setdefault(getattr(name, owner_column), set()).add(name.lang)
            for index, owner_id in owners.items():
                row = request["instructions"][index]
                # Game instructions accept aliases; native canonical name
                # decisions additionally bind by the exact canonical key.
                if row["name_decision"] and canonical[owner_id] != row["canonical_name"]:
                    results[index] = "canonical_decision_key_mismatch"
                elif languages.get(owner_id) == set(LANGUAGES):
                    results[index] = "qualified"
    return {"status": "checked", "request_sha256": canonical_sha256(request), "results": results}


def _scope_refresh_marker(conn, kind, prior):
    name, evidence = prior["name"], prior["evidence"]
    payload = evidence["research_payload"]
    candidate, research = payload["candidate"], payload["research"]
    prior_batch = (
        conn.execute(
            select(KifuNameBatch.id, KifuNameBatch.bundle_sha256).where(
                KifuNameBatch.id == payload["first_pass"]["batch_id"]
            )
        )
        .mappings()
        .one()
    )
    return {
        "version": f"generated-{kind.replace('_', '-')}-scope-refresh-v1",
        "owner": candidate["owner"],
        "lang": candidate["lang"],
        "raw_value": candidate["raw_value"],
        "name_preimage_sha256": canonical_sha256(name),
        "prior_name_revision": name["revision"],
        "prior_candidate_sha256": canonical_sha256(candidate),
        "prior_evidence_sha256": canonical_sha256(evidence),
        "prior_batch_id": prior_batch["id"],
        "prior_bundle_sha256": prior_batch["bundle_sha256"],
        "source_meaning_sha256": name_batch._raw_player_source_meaning_sha256(research),
    }


def _literal_display_fields(candidate, research):
    """Raw scopes approve displayed text and carry no player/series identity claim."""
    kind = candidate["owner"]["kind"]
    if kind == "raw_player":
        candidate.update(
            collision_decision="shared_display",
            collision_basis={
                "kind": "literal_translation",
                "source_text": candidate["raw_value"],
                "parsed_name": research["source_input"]["parsed_name"],
                "provenance": "signed_raw_player_literal",
            },
        )
    elif kind == "raw_event" and research["generation"].get("submode") != name_first_pass.RECORD_LABEL_MODE:
        shared = {
            **candidate,
            "collision_decision": "shared_display",
            "collision_basis": {
                "kind": "literal_title_translation",
                "source_text": candidate["raw_value"],
                "provenance": "signed_raw_event_literal",
            },
        }
        if name_first_pass.shared_event_display_candidate(shared, research):
            candidate.update(collision_decision=shared["collision_decision"], collision_basis=shared["collision_basis"])


def _check_incoming_collisions(candidates, research_by_hash):
    groups = {}
    for candidate in candidates:
        key = candidate["lang"], normalize_alias(candidate["display_name"])
        for prior in groups.get(key, ()):
            kinds = {prior["owner"]["kind"], candidate["owner"]["kind"]}
            if kinds <= {"player", "raw_player"} and "raw_player" in kinds:
                shared = all(
                    row["owner"]["kind"] != "raw_player" or name_first_pass.shared_display_candidate(row)
                    for row in (prior, candidate)
                )
            elif kinds <= {"event", "raw_event"} and "raw_event" in kinds:
                shared = all(
                    row["owner"]["kind"] != "raw_event"
                    or name_first_pass.shared_event_display_candidate(row, research_by_hash[row["research_sha256"]])
                    for row in (prior, candidate)
                )
            else:
                shared = False
            _require(
                shared and prior["owner"] != candidate["owner"], "incoming name decisions have conflicting displays"
            )
        groups.setdefault(key, []).append(candidate)


def _write_name_batch(conn, candidates, records, declarations, inventory_sha, manifest_hash):
    if not candidates:
        return None
    research_by_hash = {canonical_sha256(row): row for row in records}
    _check_incoming_collisions(candidates, research_by_hash)
    name_batch._check_name_preimages(conn, candidates, _REGISTRY)
    name_batch._check_first_pass_sources(conn, candidates, research_by_hash, declarations)
    for candidate, research in zip(candidates, records):
        name_first_pass.validate_research(research)
        name_first_pass.validate_candidate(candidate, research)
    bundle = {
        "bundle_format": 2,
        "inventory_sha256": inventory_sha,
        "rule_version": BINDING_VERSION,
        "manifest_sha256": manifest_hash,
        "owners": declarations,
        "candidates": candidates,
        "album_links": [],
    }
    registry_id, _ = name_batch._source_registry_for_batch(
        conn, _REGISTRY, {"registry_sha256": canonical_sha256(_REGISTRY)}
    )
    batch_id, _ = name_batch._insert(
        conn,
        KifuNameBatch,
        {
            "bundle_sha256": canonical_sha256(bundle),
            "inventory_sha256": inventory_sha,
            "source_registry_id": registry_id,
            "status": "pending",
            "reviewed_artifact": {"bundle": bundle, "research_hashes": sorted(research_by_hash)},
        },
    )
    sequence, prior_proofs = 1, {}
    for candidate in candidates:
        declaration = next(item for item in declarations if item["owner"] == candidate["owner"])
        sequence = name_batch._apply_candidate(
            conn,
            candidate,
            research_by_hash,
            registry_id,
            batch_id,
            sequence,
            raw_display_scope=declaration.get("raw_display_scope"),
            registry=_REGISTRY,
            prior_proofs=prior_proofs,
        )
    conn.execute(
        KifuNameBatch.__table__.update()
        .where(KifuNameBatch.id == batch_id)
        .values(status="applied", applied_at=datetime.now(timezone.utc))
    )
    # Simultaneous scope renewals temporarily invalidate each other's old proof.
    # Check the complete pending postimage with the native qualification reader;
    # any unproved collision still aborts this locked transaction before commit.
    name_batch._check_cross_bundle_collisions(conn, candidates, owners=declarations, research_by_hash=research_by_hash)
    return batch_id


def _apply_decisions(
    conn, decisions, resolved_games, raw_players, inventory_sha, manifest_hash, publication_batch_id, sequence
):
    candidates, records, declarations = [], [], []
    indexed_games = {(game["source_key"], game["source_item_id"]): game for game in resolved_games}
    for decision in decisions:
        kind, key = decision["kind"], decision["key"]
        owner_model, name_model, owner_column = name_batch._OWNER[kind]
        lookup_column = owner_model.raw_value if kind.startswith("raw_") else owner_model.canonical_name
        owners = list(conn.scalars(select(owner_model.id).where(lookup_column == key)))
        _require(len(owners) <= 1, "ambiguous decision owner")
        if not owners:
            _require(kind.startswith("raw_"), "canonical decision must bind an existing or explicitly created identity")
            parsed = parse_player(key, None) if kind == "raw_player" else parse_event(key, None)
            owner_id, after = name_batch._insert(
                conn, owner_model, {"raw_value": key, "category": parsed.category, "review_status": "pending"}
            )
            name_batch._record_change(conn, publication_batch_id, sequence, owner_model, owner_id, None, after)
            sequence += 1
        else:
            owner_id = owners[0]
        owner = {"kind": kind, "id": owner_id}
        owner_image = name_batch._image(conn, owner_model.__table__, owner_id)
        bound_members = []
        for member in decision["source_items"]:
            game = indexed_games[(member["source_key"], member["source_item_id"])]
            fields = set(CONTEXT_FIELDS) | {"id", "list_hidden_reason"}
            album = (
                conn.execute(
                    select(*(getattr(KifuAlbum, field) for field in sorted(fields))).where(
                        KifuAlbum.id == game["album_id"]
                    )
                )
                .mappings()
                .one()
            )
            slot = member["slot"]
            expected_owner = album["event_id" if slot == "event" else f"{slot}_player_id"]
            _require(
                expected_owner == (None if kind.startswith("raw_") else owner_id) or kind == "raw_event",
                "decision source member has a different bound identity",
            )
            _require(
                album["duplicate_of_id"] is None and album["list_hidden_reason"] is None,
                "decision source member is not a public game",
            )
            bound_members.append(
                {"album_id": album["id"], "slot": slot, "context": {field: album[field] for field in CONTEXT_FIELDS}}
            )
        declaration = {"owner": owner, "preimage": owner_image}
        scope = None
        if kind == "raw_player":
            old_scopes = [
                prior["scope"] for (raw, _lang), prior in raw_players.items() if raw == key and prior["scope"]
            ]
            old_members = {
                (row["album_id"], row["slot"]): row
                for prior_scope in old_scopes
                for row in prior_scope["content"]["slots"]
            }
            old_members.update({(row["album_id"], row["slot"]): row for row in bound_members})
            content = {
                "inventory_sha256": inventory_sha,
                "raw_value": key,
                "applicability_basis": "Reviewed source_items bound to exact local unlinked slots; retained prior signed members",
                "slots": [old_members[token] for token in sorted(old_members)],
            }
            scope = {
                "content": content,
                "approval": {
                    "status": "approved",
                    "content_sha256": canonical_sha256(content),
                    "producer_id": decision["producer"]["id"],
                    "producer_model": decision["producer"]["model"],
                    "produced_at": decision["producer"]["at"],
                    "reviewer_id": decision["review"]["id"],
                    "reviewer_model": decision["review"]["model"],
                    "reviewed_at": decision["review"]["at"],
                    "conclusion": "approved_raw_display_scope",
                },
            }
            occurrence_ids = list(
                conn.scalars(
                    select(KifuAlbum.id)
                    .where(or_(KifuAlbum.player_black == key, KifuAlbum.player_white == key))
                    .order_by(KifuAlbum.id)
                )
            )
            declaration.update(
                raw_display_scope=scope,
                occurrence_album_ids=occurrence_ids,
                occurrence_sha256=canonical_sha256(occurrence_ids),
            )
        declarations.append(declaration)
        with Session(bind=conn) as db:
            qualified = {
                name.lang: name.id
                for name, _evidence in _qualified_name_rows(
                    db, _approved_names(db, name_model, owner_column, {owner_id}), name_model, owner_column
                )
            }
        for lang in LANGUAGES:
            current = (
                conn.execute(
                    select(name_model.__table__).where(
                        getattr(name_model, owner_column) == owner_id, name_model.lang == lang
                    )
                )
                .mappings()
                .one_or_none()
            )
            prior = raw_players.get((key, lang)) if kind == "raw_player" else None
            if current is not None and lang in qualified:
                _require(
                    current["display_name"] == decision["displays"][lang],
                    "reviewed text conflicts with an existing qualified name",
                )
                if kind != "raw_player":
                    continue
                _require(
                    prior and prior["name"]["generation_rule_version"] == name_first_pass.VERSION and prior["scope"],
                    "raw-player scope renewal needs qualified native prior proof",
                )
            else:
                _require(
                    current is None or current["status"] != "verified" and current["evidence_id"] is None,
                    "decision cannot replace an unqualified evidence-backed name",
                )
            research = {
                "owner": owner,
                "lang": lang,
                "registry_version": _REGISTRY["version"],
                "registry_sha256": canonical_sha256(_REGISTRY),
                "source_basis": name_first_pass.VERSION,
                "scope_status": name_first_pass.LEVEL,
                "verification_level": name_first_pass.LEVEL,
                "original_name": key,
                "original_language": decision["original_language"],
                "candidate_name": decision["displays"][lang],
                "source_input": {
                    "kind": f"{kind}_literal" if kind.startswith("raw_") else "catalog_canonical",
                    "owner": owner,
                    "text": key,
                    "owner_preimage_sha256": canonical_sha256(owner_image),
                },
                "generation": {"method": decision["methods"][lang]},
                "sources": deepcopy(decision["sources"]),
                "producer_id": decision["producer"]["id"],
                "producer_model": decision["producer"]["model"],
                "review_status": "pending",
                "incremental_binding": {
                    "version": BINDING_VERSION,
                    "mode": "reviewed_text",
                    "decision": deepcopy(decision),
                    "manifest_sha256": manifest_hash,
                    "binding_actor": "kifu-deterministic-id-binding-v1",
                    "bound_members": bound_members,
                },
            }
            if kind == "raw_event":
                research["raw_scope"] = {"raw_value": key, "slots": name_first_pass.raw_scope_rows(conn, key)}
            if kind == "raw_player":
                parsed = parse_player(key, None)
                research["source_input"].update(parsed_name=parsed.name, embedded_rank=parsed.embedded_rank)
                research["raw_display_scope_sha256"] = canonical_sha256(scope)
                if prior:
                    previous_research = prior["evidence"]["research_payload"]["research"]
                    # A portable decision states the method, while this target
                    # retains additional native reading/source provenance.
                    for field in ("original_name", "original_language", "source_input", "generation"):
                        research[field] = deepcopy(previous_research[field])
            candidate = {
                "owner": owner,
                "lang": lang,
                "display_name": decision["displays"][lang],
                "decision_kind": "generated",
                "generation_rule_version": name_first_pass.VERSION,
                "research_sha256": canonical_sha256(research),
                "name_preimage_sha256": name_batch._name_preimage_sha256(conn, owner, lang),
                "producer_id": decision["producer"]["id"],
                "producer_model": decision["producer"]["model"],
                "produced_at": decision["producer"]["at"],
                "review_status": "approved",
                "reviewer_id": decision["review"]["id"],
                "reviewer_model": decision["review"]["model"],
                "reviewed_at": decision["review"]["at"],
                "review_conclusion": "approved_first_pass_display_and_source",
            }
            if kind.startswith("raw_"):
                candidate["raw_value"] = key
            if kind == "raw_player":
                candidate["raw_display_scope_sha256"] = canonical_sha256(scope)
                if prior:
                    candidate["first_pass_correction"] = _scope_refresh_marker(conn, kind, prior)
            _literal_display_fields(candidate, research)
            candidate["generated_review"] = {
                "decision": "approve_generated_first_pass",
                **{
                    field: candidate[field]
                    for field in (
                        "owner",
                        "lang",
                        "display_name",
                        "research_sha256",
                        "reviewer_id",
                        "reviewer_model",
                        "reviewed_at",
                    )
                },
            }
            values = {owner_kind: set() for owner_kind in name_batch._OWNER}
            values[kind].add(key if kind.startswith("raw_") else owner_id)
            _validate_candidate(
                candidate, research, _REGISTRY, values, declarations={f"{kind}:{owner_id}": declaration}
            )
            candidates.append(candidate)
            records.append(research)
    return _write_name_batch(conn, candidates, records, declarations, inventory_sha, manifest_hash), sequence


def _source_records(conn, source_keys):
    """Read only incoming source identities from original committed receipts."""
    result = {}
    if conn.dialect.name == "postgresql":
        entries = func.json_array_elements(KifuNameBatch.reviewed_artifact["sources"]).table_valued("value")
        key, item = entries.c.value.op("->>")("source_key"), entries.c.value.op("->>")("source_item_id")
    else:
        entries = func.json_each(KifuNameBatch.reviewed_artifact, "$.sources").table_valued("value")
        key, item = func.json_extract(entries.c.value, "$.source_key"), func.json_extract(
            entries.c.value, "$.source_item_id"
        )
    query = (
        select(entries.c.value)
        .select_from(KifuNameBatch.__table__.join(entries, true()))
        .where(
            KifuNameBatch.status == "applied",
            KifuNameBatch.reviewed_artifact["publication_format"].as_string().in_(FORMATS),
            or_(*(and_(key == source_key, item == source_item) for source_key, source_item in source_keys)),
        )
    )
    with historical_ranks._bounded_queries(conn):
        sub = query.subquery()
        count, size = conn.execute(
            select(func.count(), func.coalesce(func.sum(func.length(cast(sub.c.value, Text))), 0)).select_from(sub)
        ).one()
        _require(
            count <= historical_ranks.MAX_SCALAR_ROWS and size * 4 + count * 128 <= historical_ranks.MAX_SCALAR_BYTES,
            "original source receipt integrity resource limit",
        )
        used = 0
        for raw in conn.scalars(query):
            source = json.loads(raw) if isinstance(raw, str) else raw
            used += len(json.dumps(source, ensure_ascii=False).encode())
            _require(used <= historical_ranks.MAX_SCALAR_BYTES, "original source receipt integrity resource limit")
            source_key = (source["source_key"], source["source_item_id"])
            _require(source_key in source_keys, "source receipt SQL membership changed")
            _require(source_key not in result or result[source_key] == source, "conflicting committed source receipts")
            result[source_key] = source
    return result


def _bounded_exact_matches(conn, game, canonical, origin_owners, resource, deferred):
    """Keep SQL exact equality and conservative metadata fallback, never warm SGFs.

    Content equality is deliberately not described as indexed: its statement
    timeout and body ceilings bound refusal, while raw names use existing indexes.
    Original path owners must always be checked, even when a candidate cohort is
    deferred. They cannot be skipped or reassigned because of a resource limit.
    """
    matches, seen = set(), set()

    def read(predicate, *, integrity=False, expected_sha=None):
        with historical_ranks._bounded_queries(conn):
            length = historical_ranks._body_length(conn, KifuAlbum.sgf_content)
            count, maximum, size = conn.execute(
                select(func.count(), func.coalesce(func.max(length), 0), func.coalesce(func.sum(length), 0)).where(
                    predicate
                )
            ).one()
            over = (
                count > historical_ranks.MAX_BODY_ROWS
                or maximum > historical_ranks.MAX_SGF_BYTES
                or size > historical_ranks.MAX_BODY_BYTES
            )
            if over:
                _require(not integrity, "original source ownership SGF resource limit")
                return False
            cohort_matches, cohort_seen = set(), set()
            scalar_rows = [
                dict(row)
                for row in conn.execute(
                    select(
                        KifuAlbum.id,
                        length.label("sgf_bytes"),
                        (KifuAlbum.sgf_content == game["sgf_content"]).label("incoming_body_exact"),
                    ).where(predicate, KifuAlbum.id.not_in(seen))
                ).mappings()
            ]
            expected = {
                row["id"]: game["sgf_sha256"] if row["incoming_body_exact"] else expected_sha for row in scalar_rows
            }
            missing = [
                row
                for row in scalar_rows
                if resource.cached_body(row["id"]) is None and expected[row["id"]] not in resource.body_cache
            ]
            needed = sum(row["sgf_bytes"] for row in missing)
            missing_count = len(missing)
            if (
                needed > resource.remaining_bytes
                or len(resource.body_cache) + missing_count > historical_ranks.MAX_BODY_ROWS
            ):
                _require(not integrity, "original source ownership SGF resource limit")
                return False
            for row in scalar_rows:
                body = historical_ranks.load_rank_body(conn, row, resource=resource, expected_sha=expected[row["id"]])
                cohort_seen.add(row["id"])
                try:
                    if _canonical_sgf(body) == canonical:
                        cohort_matches.add(row["id"])
                except (ParseError, ValueError, TypeError, IndexError):
                    _require(not integrity, "original source ownership SGF invalid")
            seen.update(cohort_seen)
            matches.update(cohort_matches)
            return True

    read(KifuAlbum.id.in_(origin_owners), integrity=True)
    owner_matches = set(matches)
    resource_deferred = False
    metadata = game["metadata"]
    predicates = [
        (KifuAlbum.sgf_content == canonical, sha256(canonical.encode()).hexdigest()),
        (
            and_(
                KifuAlbum.player_black == metadata["player_black"],
                KifuAlbum.player_white == metadata["player_white"],
                KifuAlbum.date_played == metadata.get("date_played"),
            ),
            None,
        ),
    ]
    for predicate, expected_sha in predicates:
        try:
            complete = read(predicate, expected_sha=expected_sha)
        except DBAPIError as exc:
            if getattr(exc.orig, "sqlstate", None) != "57014" and getattr(exc.orig, "pgcode", None) != "57014":
                raise
            complete = False
        if not complete:
            resource_deferred = True
            deferred.append(
                {
                    "source_key": game["source_key"],
                    "source_item_id": game["source_item_id"],
                    "reason": "resource_deferred",
                }
            )
    return owner_matches if resource_deferred else matches


def _source_owner_ids(conn, game):
    with historical_ranks._bounded_queries(conn):
        query = (
            select(KifuAlbumSource.album_id)
            .join(KifuSource, KifuSource.id == KifuAlbumSource.source_id)
            .where(KifuSource.source_key == game["source_key"], KifuAlbumSource.origin_path == game["origin_path"])
        )
        _require(
            conn.scalar(select(func.count()).select_from(query.subquery())) <= historical_ranks.MAX_BODY_ROWS,
            "original source ownership resource limit",
        )
        result = set(conn.scalars(query))
        result.update(conn.scalars(select(KifuAlbum.id).where(KifuAlbum.source_path == game["origin_path"])))
        return result


def _planned_rank_outcomes(conn, manifest, prepared, source_records, resource):
    """Freeze TEST's portable choices before PROD's first business mutation.

    Negative IDs name only earlier proposed originals within this finite batch;
    they are never persisted, exposed in receipts or used as player authority.
    """
    exact, virtual, outcomes, planned = {}, {}, [], {}
    for game, canonical in prepared:
        key = game["source_key"], game["source_item_id"]
        old = source_records.get(key)
        if old:
            _check_source_receipts(conn, [old], resource=resource)
            _require(
                all(old[field] == game[field] for field in ("raw_sha256", "sgf_sha256", "origin_path")),
                "source ID content changed; explicit revision required",
            )
            album_id = old["album_id"]
        else:
            owners = _source_owner_ids(conn, game)
            matches = set(exact.get(canonical, ())) | _bounded_exact_matches(
                conn, game, canonical, owners, resource, []
            )
            album_id = _select_source_owner(conn, game, matches, owners, resource=resource)
            if album_id is None:
                album_id = -(len(virtual) + 1)
                virtual[album_id] = game
                exact.setdefault(canonical, []).append(album_id)
        if not any(is_historical_snapshot(snapshot) for snapshot in game.get("rank_snapshots", {}).values()):
            continue
        context = _rank_source_context(conn, game, album_id, resource) if album_id > 0 else None
        for side, snapshot in game["rank_snapshots"].items():
            if not is_historical_snapshot(snapshot):
                continue
            if context:
                binding = context["binding"][side]
                row = (
                    conn.execute(
                        select(KifuAlbumRankSnapshot.__table__).where(
                            KifuAlbumRankSnapshot.album_id == album_id, KifuAlbumRankSnapshot.side == side
                        )
                    )
                    .mappings()
                    .one_or_none()
                )
                if row:
                    _assert_retained_rank_row(conn, dict(row), context, resource=resource)
                actual = row["snapshot"] if row else planned.get((album_id, side))
            else:
                original = virtual[album_id]
                binding = {
                    "source_key": original["source_key"],
                    "source_path": original["origin_path"],
                    "sgf_sha256": original["sgf_sha256"],
                }
                actual = planned.get((album_id, side))
            outcome = _rank_outcome(game, side, album_id, binding, "applied")
            if outcome["original_source_ref"] != snapshot["source_ref"]:
                outcome.update(status="retained" if actual else "deferred", retained_snapshot=deepcopy(actual))
            else:
                if actual is not None:
                    _require(actual == snapshot, "existing frozen rank differs; explicit rank correction required")
                planned[album_id, side] = snapshot
            outcomes.append(outcome)
    return outcomes


def _check_source_receipts(conn, receipts, *, resource=None):
    resource = resource or historical_ranks.EvidenceBudget()
    for source in receipts:
        with historical_ranks._bounded_queries(conn):
            album = (
                conn.execute(
                    select(
                        KifuAlbum.id, historical_ranks._body_length(conn, KifuAlbum.sgf_content).label("sgf_bytes")
                    ).where(KifuAlbum.id == source["album_id"])
                )
                .mappings()
                .one_or_none()
            )
            content = (
                historical_ranks.load_rank_body(conn, album, resource=resource, expected_sha=source["album_sgf_sha256"])
                if album
                else None
            )
        _require(
            content is not None and sha256(content.encode("utf-8")).hexdigest() == source["album_sgf_sha256"],
            "published SGF differs from its source receipt",
        )
        link = conn.scalar(
            select(KifuAlbumSource.id)
            .join(KifuSource, KifuSource.id == KifuAlbumSource.source_id)
            .where(
                KifuAlbumSource.album_id == source["album_id"],
                KifuSource.source_key == source["source_key"],
                KifuAlbumSource.origin_path == source["origin_path"],
            )
        )
        _require(link is not None, "published source link differs from its receipt")


def _renew_events(conn, captured, new_raws, inventory_sha, manifest_hash):
    candidates, records, declarations = [], [], []
    for raw in sorted(new_raws):
        scopes = name_first_pass.raw_scope_rows(conn, raw)
        for lang in LANGUAGES:
            prior = captured.get((raw, lang))
            if not prior or not isinstance(prior["scope"], dict) or "first_pass" not in prior["scope"]:
                continue
            old_name, old_evidence = prior["name"], prior["evidence"]
            payload = old_evidence["research_payload"]
            research, candidate = deepcopy(payload["research"]), deepcopy(payload["candidate"])
            if research["raw_scope"]["slots"] == scopes:
                continue
            owner = candidate["owner"]
            marker = _scope_refresh_marker(conn, "raw_event", prior)
            research["raw_scope"]["slots"] = scopes
            research["incremental_binding"] = {
                "version": BINDING_VERSION,
                "mode": "qualified_scope_renewal",
                "manifest_sha256": manifest_hash,
                "prior_evidence_sha256": canonical_sha256(old_evidence),
                "prior_candidate": deepcopy(payload["candidate"]),
                "prior_research_sha256": canonical_sha256(payload["research"]),
                "binding_actor": "kifu-deterministic-scope-binding-v1",
            }
            # These actors performed deterministic proof checking; the historical
            # language reviewers remain explicitly recorded in prior_candidate.
            now = datetime.now(timezone.utc).isoformat()
            research.update(producer_id="kifu-scope-renewal-builder-v1", producer_model="deterministic-code")
            candidate.update(
                first_pass_correction=marker,
                name_preimage_sha256=canonical_sha256(old_name),
                research_sha256=canonical_sha256(research),
                producer_id="kifu-scope-renewal-builder-v1",
                producer_model="deterministic-code",
                reviewer_id="kifu-scope-renewal-verifier-v1",
                reviewer_model="deterministic-code",
                produced_at=now,
                reviewed_at=now,
            )
            candidate["generated_review"].update(
                {key: candidate[key] for key in ("research_sha256", "reviewer_id", "reviewer_model", "reviewed_at")}
            )
            _literal_display_fields(candidate, research)
            candidates.append(candidate)
            records.append(research)
            if not any(item["owner"] == owner for item in declarations):
                declarations.append(
                    {"owner": owner, "preimage": name_batch._image(conn, KifuRawEventValue.__table__, owner["id"])}
                )
    return _write_name_batch(conn, candidates, records, declarations, inventory_sha, manifest_hash)


def _journal_changes(conn, batch_id):
    columns = (
        KifuNameChange.sequence,
        KifuNameChange.target_table,
        KifuNameChange.target_row_id,
        KifuNameChange.before_image,
        KifuNameChange.after_image,
    )
    return [
        dict(row)
        for row in conn.execute(
            select(*columns).where(KifuNameChange.batch_id == batch_id).order_by(KifuNameChange.sequence)
        ).mappings()
    ]


def _publication_batch_ids(receipt):
    return [
        value
        for value in (receipt["batch_id"], receipt.get("reviewed_name_batch_id"), receipt.get("name_batch_id"))
        if value is not None
    ]


def _publication_undo_guard(conn, receipt, sources, affected):
    """Pin the existing native journals in the same transaction as publication."""
    return {
        "version": "kifu-publication-undo-v1",
        "receipt_sha256": canonical_sha256(receipt),
        "sources_sha256": canonical_sha256(sources),
        "affected_album_ids": sorted(affected),
        "batches": [
            {
                "batch_id": batch_id,
                "bundle_sha256": conn.scalar(select(KifuNameBatch.bundle_sha256).where(KifuNameBatch.id == batch_id)),
                "journal_sha256": canonical_sha256(_journal_changes(conn, batch_id)),
            }
            for batch_id in _publication_batch_ids(receipt)
        ],
    }


def _dedup_journal(conn, batch_id):
    columns = [column for column in KifuDedupChange.__table__.columns if column.name != "created_at"]
    return [
        dict(row)
        for row in conn.execute(
            select(*columns).where(KifuDedupChange.batch_id == batch_id).order_by(KifuDedupChange.id)
        ).mappings()
    ]


def _apply_catalog_repairs(conn, album_ids, *, resource):
    """Only incoming display dedup; existing frozen ranks use the CAS repair tool."""
    with historical_ranks._bounded_queries(conn):
        manifest = catalog_standardization.prepare_dedup_manifest(
            conn, candidate_album_ids=album_ids, resource=resource
        )
        digest = catalog_standardization.dedup_manifest_sha256(manifest)
        batch_id = None
        if manifest["groups"]:
            catalog_standardization.apply_dedup_manifest(conn, manifest, expected_sha256=digest, resource=resource)
            batch_id = conn.scalar(
                select(KifuDedupBatch.id).where(KifuDedupBatch.batch_key == "reviewed-same-game:" + digest)
            )
        affected = set(album_ids) | {
            member["album"]["id"] for group in manifest["groups"] for member in group["members"]
        }
        return {
            "version": "kifu-catalog-repairs-v1",
            "dedup": {
                "manifest": manifest,
                "manifest_sha256": digest,
                "batch_id": batch_id,
                "journal_sha256": canonical_sha256(_dedup_journal(conn, batch_id)),
            },
            "affected_album_ids": sorted(affected),
        }


def _validate_catalog_repairs(conn, artifact, *, undone=False, check_current=True, strict=False, resource=None):
    """Validate the saved child, never select or refreeze publication candidates."""
    repairs = artifact.get("catalog_repairs")
    guard = artifact.get("undo_guard") or {}
    if repairs is None:
        _require("catalog_repairs_sha256" not in guard, "publication dedup child missing")
        return None
    _require(
        isinstance(repairs, dict)
        and set(repairs) == {"version", "dedup", "affected_album_ids"}
        and repairs.get("version") == "kifu-catalog-repairs-v1"
        and guard.get("catalog_repairs_sha256") == canonical_sha256(repairs),
        "publication dedup child artifact changed",
    )
    child = repairs["dedup"]
    _require(
        isinstance(child, dict) and set(child) == {"manifest", "manifest_sha256", "batch_id", "journal_sha256"},
        "publication dedup child contract changed",
    )
    manifest, digest = child["manifest"], child["manifest_sha256"]
    catalog_standardization.validate_dedup_manifest(manifest)
    _require(catalog_standardization.dedup_manifest_sha256(manifest) == digest, "publication dedup manifest changed")
    originals = {row["album_id"] for row in artifact["receipt"]["games"]}
    members = {member["album"]["id"] for group in manifest["groups"] for member in group["members"]}
    _require(
        manifest.get("scope") == {"candidate_album_ids": sorted(originals)}
        and repairs["affected_album_ids"] == sorted(originals | members),
        "publication dedup child membership changed",
    )
    if not manifest["groups"]:
        _require(
            child["batch_id"] is None and child["journal_sha256"] == canonical_sha256([]),
            "empty publication dedup journal changed",
        )
        return repairs
    _require(type(child["batch_id"]) is int and child["batch_id"] > 0, "publication dedup batch missing")
    with historical_ranks._bounded_queries(conn):
        batch = (
            conn.execute(select(KifuDedupBatch.__table__).where(KifuDedupBatch.id == child["batch_id"]))
            .mappings()
            .one_or_none()
        )
        _require(
            batch is not None
            and batch["batch_key"] == "reviewed-same-game:" + digest
            and batch["status"] == ("undone" if undone else "complete"),
            "publication dedup batch changed",
        )
        summary = batch["summary"]
        base = {"manifest": manifest, "manifest_sha256": digest}
        archive = summary.get("compensated_journal") if isinstance(summary, dict) else None
        changes = _dedup_journal(conn, child["batch_id"])
        if archive is not None:
            _require(
                undone
                and summary == {**base, "compensated_journal": archive}
                and not changes
                and isinstance(archive, dict)
                and set(archive) == {"version", "manifest_sha256", "journal_sha256", "album_ids", "changes"}
                and archive["version"] == "kifu-compensated-dedup-journal-v1"
                and archive["manifest_sha256"] == digest
                and archive["journal_sha256"] == child["journal_sha256"]
                and archive["album_ids"] == sorted(members),
                "publication compensated dedup archive changed",
            )
            changes = archive["changes"]
            fields = {column.name for column in KifuDedupChange.__table__.columns if column.name != "created_at"}
            _require(
                isinstance(changes, list)
                and all(
                    isinstance(row, dict)
                    and set(row) == fields
                    and row["batch_id"] == child["batch_id"]
                    and type(row["id"]) is int
                    and row["id"] > 0
                    for row in changes
                )
                and [row["id"] for row in changes] == sorted({row["id"] for row in changes}),
                "publication compensated dedup journal members changed",
            )
        else:
            _require(summary == base, "publication dedup immutable summary changed")
        _require(
            canonical_sha256(changes) == child["journal_sha256"],
            "publication dedup journal changed",
        )
        catalog_standardization._journal_check(conn, batch, manifest, changes=changes)
        if check_current and not undone:
            if resource is not None:
                for group in manifest["groups"]:
                    for member in group["members"]:
                        resource.remember_body(member["album"]["sgf_content"], album_id=member["album"]["id"])
            if strict:
                catalog_standardization._check_images(conn, manifest, after=True, resource=resource)
            else:
                for group in manifest["groups"]:
                    for duplicate in group["duplicate_album_ids"]:
                        proof = catalog_standardization.verified_display_duplicate(conn, duplicate, resource=resource)
                        _require(proof["manifest_sha256"] == digest, "publication dedup original proof changed")
    return repairs


def _archive_compensated_dedup(conn, repairs):
    """Release this new child's album FKs, retaining its original immutable audit."""
    child = repairs["dedup"]
    batch = (
        conn.execute(select(KifuDedupBatch.__table__).where(KifuDedupBatch.id == child["batch_id"])).mappings().one()
    )
    changes = _dedup_journal(conn, child["batch_id"])
    _require(
        batch["status"] == "undone" and canonical_sha256(changes) == child["journal_sha256"],
        "compensated dedup journal changed before archive",
    )
    archive = {
        "version": "kifu-compensated-dedup-journal-v1",
        "manifest_sha256": child["manifest_sha256"],
        "journal_sha256": child["journal_sha256"],
        "album_ids": sorted(
            {member["album"]["id"] for group in child["manifest"]["groups"] for member in group["members"]}
        ),
        "changes": changes,
    }
    existing = batch["summary"].get("compensated_journal")
    _require(existing is None or existing == archive, "compensated dedup archive already differs")
    conn.execute(
        update(KifuDedupBatch)
        .where(KifuDedupBatch.id == child["batch_id"])
        .values(summary={**batch["summary"], "compensated_journal": archive})
    )
    conn.execute(KifuDedupChange.__table__.delete().where(KifuDedupChange.batch_id == child["batch_id"]))


def _check_retained_publication_receipts(conn, batch_id, journals):
    """A later applied receipt can depend on a row without changing that row."""
    deleted_albums, deleted_links = set(), set()
    source_keys = dict(conn.execute(select(KifuSource.id, KifuSource.source_key)).all())
    for changes in journals:
        for change in changes:
            if change["before_image"] is not None:
                continue
            if change["target_table"] == KifuAlbum.__tablename__:
                deleted_albums.add(change["target_row_id"])
            elif change["target_table"] == KifuAlbumSource.__tablename__:
                link = change["after_image"]
                deleted_links.add((link["album_id"], source_keys.get(link["source_id"]), link["origin_path"]))
    if not deleted_albums and not deleted_links:
        return
    artifacts = conn.scalars(
        select(KifuNameBatch.reviewed_artifact).where(
            KifuNameBatch.id != batch_id,
            KifuNameBatch.status == "applied",
            KifuNameBatch.reviewed_artifact["publication_format"].as_string().in_(FORMATS),
        )
    )
    for artifact in artifacts:
        for source in artifact.get("sources", ()):
            _require(
                source["album_id"] not in deleted_albums
                and (source["album_id"], source["source_key"], source["origin_path"]) not in deleted_links,
                "dependent applied publication receipt blocks compensation",
            )


def _check_retained_rank_dependencies(conn, batch_ids, journals, *, resource=None):
    """Reject all dependencies before the first compensation write."""
    created_facts, created_snapshots, changed_snapshots = set(), set(), set()
    for changes in journals:
        for change in changes:
            if change["target_table"] == KifuAlbumRankSnapshot.__tablename__:
                changed_snapshots.add(change["target_row_id"])
            if change["before_image"] is not None:
                continue
            if change["target_table"] == KifuPlayerRankHistory.__tablename__:
                created_facts.add(change["target_row_id"])
            elif change["target_table"] == KifuAlbumRankSnapshot.__tablename__:
                created_snapshots.add(change["target_row_id"])
    if created_facts:
        dependent = conn.scalar(
            select(KifuAlbumRankSnapshot.id)
            .where(
                KifuAlbumRankSnapshot.rank_fact_id.in_(created_facts),
                KifuAlbumRankSnapshot.id.not_in(created_snapshots),
            )
            .limit(1)
        )
        _require(dependent is None, "dependent rank snapshot blocks compensation")
    removed = []
    local_ids = {
        KifuAlbum.__tablename__: "album_id",
        KifuAlbumSource.__tablename__: "source_link_id",
        KifuSource.__tablename__: "source_id",
        KifuPlayer.__tablename__: "player_id",
    }
    for changes in journals:
        for change in changes:
            field = local_ids.get(change["target_table"])
            if field:
                # Restoring a changed row can invalidate an original just as a
                # deletion can. Check all touched exact local bindings first.
                removed.append({field: change["target_row_id"]})
    historical_ranks.assert_retained_rank_basis(conn, removed, excluding_batch_ids=batch_ids, resource=resource)
    if not created_facts and not changed_snapshots:
        return
    for artifact in conn.scalars(
        select(KifuNameBatch.reviewed_artifact).where(
            KifuNameBatch.id.not_in(batch_ids),
            KifuNameBatch.status == "applied",
            KifuNameBatch.reviewed_artifact["publication_format"].as_string() == FORMAT_V2,
        )
    ):
        for binding in artifact.get("rank_bindings", ()):
            _require(
                binding.get("rank_fact_id") not in created_facts
                and binding.get("snapshot_id") not in changed_snapshots,
                "dependent applied rank receipt blocks compensation",
            )
        dispositions = artifact.get("rank_dispositions")
        if dispositions is not None:
            _require(
                artifact.get("undo_guard", {}).get("rank_dispositions_sha256") == canonical_sha256(dispositions),
                "dependent rank disposition guard changed",
            )
            for item in dispositions:
                row = item.get("retained_row")
                _require(
                    row is None
                    or row.get("id") not in changed_snapshots
                    and row.get("rank_fact_id") not in created_facts,
                    "dependent retained rank receipt blocks compensation",
                )


def undo_publication(engine, batch_id, *, lock_timeout_ms=15000):
    """Conditionally compensate one complete publication, or change nothing.

    All parent/child journals and current after-images must still match. Native
    name revisions are reversed before source links and newly inserted albums;
    later edits or dependencies reject the entire transaction. This explicit
    entry point is never called automatically after an uncertain API response.
    """
    resource = historical_ranks.EvidenceBudget()
    tables = {
        **name_batch._UNDO_TABLES,
        KifuSource.__tablename__: KifuSource.__table__,
        KifuAlbumSource.__tablename__: KifuAlbumSource.__table__,
    }
    try:
        with name_batch._locked_write(
            engine, lock_timeout_ms=lock_timeout_ms, search_operation=("catalog_undo", {"batch_id": batch_id})
        ) as conn:
            batch = name_batch._image(conn, KifuNameBatch.__table__, batch_id)
            _require(batch is not None, "publication batch not found")
            artifact = batch["reviewed_artifact"]
            receipt, guard = artifact.get("receipt"), artifact.get("undo_guard")
            _require(
                artifact.get("publication_format") in FORMATS
                and artifact.get("manifest_sha256") == batch["bundle_sha256"]
                and isinstance(receipt, dict)
                and receipt.get("batch_id") == batch_id
                and receipt.get("manifest_sha256") == batch["bundle_sha256"]
                and isinstance(guard, dict)
                and guard.get("version") == "kifu-publication-undo-v1"
                and canonical_sha256(receipt) == guard.get("receipt_sha256")
                and canonical_sha256(artifact.get("sources")) == guard.get("sources_sha256"),
                "publication compensation artifact changed or unavailable",
            )
            batch_ids = _publication_batch_ids(receipt)
            _require(
                len(set(batch_ids)) == len(batch_ids)
                and [item.get("batch_id") for item in guard.get("batches", ())] == batch_ids,
                "publication child batch artifact changed",
            )
            journals = []
            for item in guard["batches"]:
                current = name_batch._image(conn, KifuNameBatch.__table__, item["batch_id"])
                _require(
                    current is not None and current["bundle_sha256"] == item["bundle_sha256"],
                    "publication batch artifact changed",
                )
                changes = _journal_changes(conn, item["batch_id"])
                _require(canonical_sha256(changes) == item["journal_sha256"], "publication journal changed")
                if current["id"] != batch_id:
                    bundle = current["reviewed_artifact"].get("bundle")
                    _require(
                        isinstance(bundle, dict)
                        and canonical_sha256(bundle) == current["bundle_sha256"]
                        and bundle.get("manifest_sha256") == batch["bundle_sha256"],
                        "publication child artifact changed",
                    )
                _require(
                    current["status"] == batch["status"] and current["status"] in {"applied", "undone"},
                    "publication batch status changed",
                )
                journals.append(changes)
            repairs = _validate_catalog_repairs(
                conn, artifact, undone=batch["status"] == "undone", strict=True, resource=resource
            )
            _check_rank_dispositions(
                conn,
                artifact.get("logical_manifest", {}),
                artifact,
                resource=resource,
                check_current=batch["status"] != "undone",
            )
            if batch["status"] == "undone":
                outcome = artifact.get("undo_receipt")
                _require(
                    isinstance(outcome, dict)
                    and outcome.get("batch_id") == batch_id
                    and outcome.get("status") == "undone",
                    "publication undo receipt changed",
                )
                return deepcopy(outcome)
            _check_source_receipts(conn, artifact["sources"], resource=resource)
            _check_retained_rank_dependencies(conn, batch_ids, journals, resource=resource)
            _check_retained_publication_receipts(conn, batch_id, journals)
            deleted_albums = {
                change["target_row_id"]
                for changes in journals
                for change in changes
                if change["target_table"] == KifuAlbum.__tablename__ and change["before_image"] is None
            }
            child_batch_id = repairs["dedup"]["batch_id"] if repairs else None
            foreign_dedup = select(KifuDedupChange.id).where(
                or_(
                    KifuDedupChange.album_id.in_(deleted_albums),
                    KifuDedupChange.duplicate_of_id_before.in_(deleted_albums),
                    KifuDedupChange.duplicate_of_id_after.in_(deleted_albums),
                )
            )
            if child_batch_id is not None:
                foreign_dedup = foreign_dedup.where(KifuDedupChange.batch_id != child_batch_id)
            _require(
                conn.scalar(foreign_dedup.limit(1)) is None, "retained dedup journal blocks publication compensation"
            )
            child_before = {}
            if repairs:
                child_manifest = repairs["dedup"]["manifest"]
                child_before = {
                    member["album"]["id"]: member["album"]
                    for group in child_manifest["groups"]
                    for member in group["members"]
                }
                removed = [
                    {"album_id": album_id}
                    for group in child_manifest["groups"]
                    for album_id in group["duplicate_album_ids"]
                ]
                for group in child_manifest["groups"]:
                    for member in group["members"]:
                        album_id = member["album"]["id"]
                        old_keys = {(link["source_id"], link["origin_path"]) for link in member["source_links"]}
                        for link in catalog_standardization._expected_after(group)[album_id]["source_links"]:
                            if (link["source_id"], link["origin_path"]) not in old_keys:
                                link_id = conn.scalar(
                                    select(KifuAlbumSource.id).where(
                                        KifuAlbumSource.album_id == album_id,
                                        KifuAlbumSource.source_id == link["source_id"],
                                        KifuAlbumSource.origin_path == link["origin_path"],
                                    )
                                )
                                removed.append({"source_link_id": link_id})
                historical_ranks.assert_retained_rank_basis(
                    conn, removed, excluding_batch_ids=batch_ids, resource=resource
                )
            for changes in journals:
                for change in changes:
                    table = tables.get(change["target_table"])
                    _require(table is not None, "publication journal target is not allowlisted")
                    current_image = name_batch._image(conn, table, change["target_row_id"])
                    if table is KifuAlbum.__table__ and change["target_row_id"] in child_before and current_image:
                        current_image = {
                            **current_image,
                            "duplicate_of_id": child_before[change["target_row_id"]]["duplicate_of_id"],
                        }
                    _require(
                        current_image == change["after_image"],
                        "publication after-image changed",
                    )
                    _require(
                        not name_batch._retained_composition_dependency(
                            conn, table, change["target_row_id"], change["before_image"]
                        ),
                        "later composed evidence changed publication dependencies",
                    )
            if repairs and repairs["dedup"]["batch_id"] is not None:
                catalog_standardization.undo_dedup_manifest(
                    conn,
                    repairs["dedup"]["manifest"],
                    expected_sha256=repairs["dedup"]["manifest_sha256"],
                    resource=resource,
                )
                if deleted_albums & set(child_before):
                    _archive_compensated_dedup(conn, repairs)
            for changes in reversed(journals):
                for change in reversed(changes):
                    table = tables[change["target_table"]]
                    key = name_batch._primary_key(table) == change["target_row_id"]
                    if change["before_image"] is None:
                        conn.execute(table.delete().where(key))
                    else:
                        conn.execute(
                            table.update()
                            .where(key)
                            .values(**name_batch._values_for_table(table, change["before_image"]))
                        )
            conn.execute(
                KifuNameBatch.__table__.update().where(KifuNameBatch.id.in_(batch_ids)).values(status="undone")
            )
            _coverage(conn, set(guard["affected_album_ids"]), resource=resource)
            outcome = {
                "batch_id": batch_id,
                "status": "undone",
                "batch_ids": batch_ids,
                "reverted": sum(map(len, journals)),
            }
            conn.execute(
                KifuNameBatch.__table__.update()
                .where(KifuNameBatch.id == batch_id)
                .values(reviewed_artifact={**artifact, "undo_receipt": outcome})
            )
            return outcome
    except IntegrityError as exc:
        raise PublicationError("later dependent row changed publication; compensation refused") from exc


@contextmanager
def _publication_guard(engine):
    """Hold a receiver-wide session lock, including pre-transaction SGF work.

    If a transport disappears the remote process keeps this lock until it
    finishes. A retry fails closed before starting another warm-up or writer.
    Existing name/table transaction locks still protect all catalog mutations.
    """
    if engine.dialect.name != "postgresql":
        yield
        return
    connection = engine.connect()
    acquired = False
    try:
        try:
            acquired = bool(
                connection.scalar(text("SELECT pg_try_advisory_lock(:key)"), {"key": _PUBLICATION_LOCK_KEY})
            )
        except BaseException:
            # The server may have acquired the session lock before a lost reply.
            connection.invalidate()
            raise
        connection.commit()
        _require(acquired, "another incremental publisher is still running; retry after it finishes")
        yield
    finally:
        try:
            if acquired:
                unlocked = connection.scalar(text("SELECT pg_advisory_unlock(:key)"), {"key": _PUBLICATION_LOCK_KEY})
                connection.commit()
                if not unlocked:
                    connection.invalidate()
        except BaseException:
            # Never return a potentially session-locked connection to the pool.
            connection.invalidate()
            raise
        finally:
            connection.close()


def _verify_initial_manifest_ranks(conn, manifest, *, results=None, indexes=None, resource=None):
    games = [
        game
        for game in manifest["games"]
        if any(is_historical_snapshot(x) for x in game.get("rank_snapshots", {}).values())
    ]
    if not games:
        return
    targets = historical_game_targets(games)
    incoming_targets = historical_game_targets(manifest["games"])
    # Rank-only correction has already resolved existing exact source owners.
    if results is not None:
        by_source = {(x["source_key"], x["source_item_id"]): x["album_id"] for x in results}
        for source_games, entries in ((games, targets), (manifest["games"], incoming_targets)):
            for game, pair in zip(source_games, (entries[i : i + 2] for i in range(0, len(entries), 2))):
                for target in pair:
                    target["album"] = {"id": by_source[game["source_key"], game["source_item_id"]]}
    elif indexes is not None:
        for source_games, entries in ((games, targets), (manifest["games"], incoming_targets)):
            for game, pair in zip(source_games, (entries[i : i + 2] for i in range(0, len(entries), 2))):
                for target in pair:
                    album = target["album"]
                    for side in ("black", "white"):
                        album[f"{side}_player_id"] = _resolve_identity(
                            "player",
                            game["metadata"][f"player_{side}"],
                            game.get("identities", {}).get(side, "auto"),
                            indexes,
                        )
    decisions = [game["rank_snapshots"][side] for game in games for side in ("black", "white")]
    historical_ranks.verify_initial_rank_decisions(
        conn, targets, decisions, resource=resource, incoming_targets=incoming_targets
    )


def _manifest_basis_bindings(conn, manifest, results, *, resource=None, rank_dispositions=None):
    resource = resource or historical_ranks.EvidenceBudget()
    by_source = {(x["source_key"], x["source_item_id"]): x["album_id"] for x in results}
    retained = {
        (x["outcome"]["source_key"], x["outcome"]["source_item_id"], x["outcome"]["side"])
        for x in rank_dispositions or []
        if x["outcome"]["status"] != "applied"
    }
    return [
        historical_ranks.bind_rank_decision(
            conn,
            {"album": {"id": by_source[game["source_key"], game["source_item_id"]]}, "side": side},
            snapshot,
            resource=resource,
        )
        for game in manifest["games"]
        for side, snapshot in game.get("rank_snapshots", {}).items()
        if is_historical_snapshot(snapshot) and (game["source_key"], game["source_item_id"], side) not in retained
    ]


def _rank_source_context(conn, game, album_id, resource, *, frozen_canonical_sha256=None):
    from katrain.web.kifu.source_rank_normalization import trusted_source_link, source_binding

    columns = [
        column
        for column in KifuAlbum.__table__.columns
        if column.name not in {"sgf_content", "created_at", "search_text"}
    ]
    with historical_ranks._bounded_queries(conn):
        album = dict(
            conn.execute(
                select(*columns, historical_ranks._body_length(conn, KifuAlbum.sgf_content).label("sgf_bytes")).where(
                    KifuAlbum.id == album_id
                )
            )
            .mappings()
            .one()
        )
        album["sgf_content"] = historical_ranks.load_rank_body(conn, album, resource=resource)
        links = historical_ranks._links(conn, [album_id]).get(album_id, [])
    link = trusted_source_link(album, links)
    _require(link is not None, "retained rank original source ownership missing")
    canonical = _canonical_sgf(album["sgf_content"])
    _require(
        (
            canonical == _canonical_sgf(game["sgf_content"])
            if isinstance(game.get("sgf_content"), str)
            else sha256(canonical.encode()).hexdigest() == frozen_canonical_sha256
        ),
        "retained rank complete canonical SGF changed",
    )
    historical_ranks.validate_rank_source_metadata(album)
    owner_ids = {album[side + "_player_id"] for side in ("black", "white")} - {None}
    names = dict(
        conn.execute(select(KifuPlayer.id, KifuPlayer.canonical_name).where(KifuPlayer.id.in_(owner_ids))).all()
    )
    for side, requested in game.get("rank_snapshots", {}).items():
        if is_historical_snapshot(requested):
            owner = (
                {"canonical_name": names.get(album[side + "_player_id"])}
                if album[side + "_player_id"] is not None
                else None
            )
            _require(requested["player_ref"] == owner, "rank original canonical owner changed")
    return {
        "album": album,
        "links": links,
        "binding": {
            side: {
                **source_binding(album, side, link),
                "player_id": album[side + "_player_id"],
                "player_ref": (
                    {"canonical_name": names.get(album[side + "_player_id"])}
                    if album[side + "_player_id"] is not None
                    else None
                ),
            }
            for side in ("black", "white")
        },
    }


def _rank_outcome(game, side, album_id, binding, status, snapshot=None):
    return {
        "source_key": game["source_key"],
        "source_item_id": game["source_item_id"],
        "album_id": album_id,
        "side": side,
        "status": status,
        "requested_snapshot_sha256": game["rank_snapshots"][side]["content_sha256"],
        "original_source_ref": {
            "source_key": binding["source_key"],
            "origin_path": binding["source_path"],
            "sgf_sha256": binding["sgf_sha256"],
            "slot": side,
        },
        "retained_snapshot": deepcopy(snapshot),
        "original_canonical_sgf_sha256": sha256(_canonical_sgf(game["sgf_content"]).encode()).hexdigest(),
    }


def _assert_retained_rank_row(conn, row, context, *, resource, current_batch_id=None):
    snapshot = row["snapshot"]
    _require(row["snapshot_sha256"] == snapshot.get("content_sha256"), "retained rank snapshot hash changed")
    batch = name_batch._image(conn, KifuNameBatch.__table__, row["native_batch_id"])
    own_pending = row["native_batch_id"] == current_batch_id and batch and batch["status"] == "pending"
    _require(batch is not None and (batch["status"] == "applied" or own_pending), "retained rank batch is not applied")
    journals = list(
        conn.scalars(
            select(KifuNameChange.after_image).where(
                KifuNameChange.batch_id == row["native_batch_id"],
                KifuNameChange.target_table == KifuAlbumRankSnapshot.__tablename__,
                KifuNameChange.target_row_id == row["id"],
            )
        )
    )
    _require(journals == [row], "retained rank current journal changed")
    artifact = batch["reviewed_artifact"]
    if not own_pending:
        native = (
            artifact.get("publication_format") == FORMAT_V2
            and artifact.get("manifest_sha256") == batch["bundle_sha256"]
            and artifact.get("publication_key") == row["publication_key"]
        )
        repaired = (
            artifact.get("format") == "kifu-historical-rank-repair-v1"
            and artifact.get("manifest_sha256") == batch["bundle_sha256"]
            and row["publication_key"] == "historical-rank:" + batch["bundle_sha256"]
        )
        source_repair = row["publication_key"] == "source-rank:" + batch["bundle_sha256"]
        if source_repair:
            from katrain.web.kifu.source_rank_repair import rank_manifest_sha256

            source_repair = rank_manifest_sha256(artifact) == batch["bundle_sha256"]
        _require(native or repaired or source_repair, "retained rank immutable authority changed")
    if is_historical_snapshot(snapshot):
        validate_rank_snapshot(snapshot)
        _require(row["rank_fact_id"] is None, "retained historical rank fact changed")
        live = historical_ranks.bind_rank_decision(
            conn, {"album": {"id": row["album_id"]}, "side": row["side"]}, snapshot, resource=resource
        )
        if not own_pending:
            matching = [
                binding
                for binding in artifact.get("basis_bindings", [])
                if isinstance(binding, dict)
                and binding.get("target", {}).get("album_id") == row["album_id"]
                and binding.get("target", {}).get("side") == row["side"]
            ]
            _require(
                len(matching) == 1
                and matching[0].get("content_sha256") == historical_ranks.snapshot_digest(matching[0])
                and live == matching[0],
                "retained rank basis local binding changed",
            )
    elif snapshot.get("version") == "kifu-source-rank-snapshot-v2":
        from katrain.web.kifu.source_rank_normalization import validate_source_snapshot

        _require(row["rank_fact_id"] is None, "retained source rank fact changed")
        validate_source_snapshot(snapshot, album=context["album"], side=row["side"], source_links=context["links"])
    else:
        validate_rank_snapshot(snapshot)
        digest = snapshot.get("rank_fact_sha256")
        if digest is None:
            _require(row["rank_fact_id"] is None, "retained rank fact membership changed")
        else:
            fact = (
                conn.execute(
                    select(KifuPlayerRankHistory.__table__).where(KifuPlayerRankHistory.id == row["rank_fact_id"])
                )
                .mappings()
                .one_or_none()
            )
            _require(
                fact is not None
                and fact["player_id"] == context["album"][row["side"] + "_player_id"]
                and player_ranks._row_fact(fact, snapshot["player_ref"]["canonical_name"])["content_sha256"] == digest,
                "retained rank immutable fact changed",
            )


def _check_rank_dispositions(conn, manifest, artifact, *, resource, check_current=True):
    items = artifact.get("rank_dispositions")
    guard = artifact.get("undo_guard", {})
    if items is None:
        _require("rank_dispositions_sha256" not in guard, "retained rank dispositions missing")
        return None
    _require(
        isinstance(items, list)
        and guard.get("rank_dispositions_sha256") == canonical_sha256(items)
        and guard.get("receipt_sha256") == canonical_sha256(artifact["receipt"]),
        "retained rank disposition artifact changed",
    )
    outcomes = artifact["receipt"].get("rank_outcomes", [])
    _require(
        len(items) == len(outcomes) and [item.get("outcome") for item in items] == artifact["receipt"]["rank_outcomes"],
        "retained rank outcome membership changed",
    )
    for game in manifest["games"]:
        for snapshot in game.get("rank_snapshots", {}).values():
            validate_rank_snapshot(snapshot)
    games = {(game["source_key"], game["source_item_id"]): game for game in manifest["games"]}
    expected = {
        (*key, side)
        for key, game in games.items()
        for side, snapshot in game.get("rank_snapshots", {}).items()
        if is_historical_snapshot(snapshot)
    }
    mappings = {(row["source_key"], row["source_item_id"]): row["album_id"] for row in artifact["receipt"]["games"]}
    seen = set()
    for item in items:
        _require(
            isinstance(item, dict)
            and set(item) == {"outcome", "source_binding", "retained_row"}
            and isinstance(item["outcome"], dict),
            "retained rank disposition shape changed",
        )
        outcome = item["outcome"]
        key, side = (outcome.get("source_key"), outcome.get("source_item_id")), outcome.get("side")
        slot = (*key, side)
        _require(
            slot in expected
            and slot not in seen
            and mappings.get(key) == outcome.get("album_id")
            and outcome.get("requested_snapshot_sha256") == games[key]["rank_snapshots"][side]["content_sha256"],
            "retained rank outcome slot membership changed",
        )
        seen.add(slot)
    _require(seen == expected, "retained rank outcome slots incomplete")
    if not check_current:
        return items
    contexts = {}
    for item in items:
        _require(set(item) == {"outcome", "source_binding", "retained_row"}, "retained rank disposition shape changed")
        outcome = item["outcome"]
        key, side = (outcome["source_key"], outcome["source_item_id"]), outcome["side"]
        context = contexts.setdefault(key, None)
        if context is None:
            context = contexts[key] = _rank_source_context(
                conn,
                games[key],
                outcome["album_id"],
                resource,
                frozen_canonical_sha256=outcome["original_canonical_sgf_sha256"],
            )
        _require(item["source_binding"] == context["binding"][side], "retained rank original source binding changed")
        current = (
            conn.execute(
                select(KifuAlbumRankSnapshot.__table__).where(
                    KifuAlbumRankSnapshot.album_id == outcome["album_id"], KifuAlbumRankSnapshot.side == side
                )
            )
            .mappings()
            .one_or_none()
        )
        if outcome["status"] == "applied":
            _require(item["retained_row"] is None, "applied rank disposition changed")
        else:
            _require((dict(current) if current else None) == item["retained_row"], "retained rank snapshot CAS changed")
            if current:
                _assert_retained_rank_row(conn, dict(current), context, resource=resource)
                _require(
                    outcome["retained_snapshot"] == current["snapshot"], "retained rank snapshot differs from outcome"
                )
            else:
                _require(
                    outcome["status"] == "deferred" and outcome["retained_snapshot"] is None,
                    "deferred rank no-snapshot CAS changed",
                )
    replay_manifest = {
        **manifest,
        "games": [
            (
                {
                    **game,
                    "sgf_content": game.get("sgf_content")
                    or contexts[game["source_key"], game["source_item_id"]]["album"]["sgf_content"],
                }
                if (game["source_key"], game["source_item_id"]) in contexts
                else game
            )
            for game in manifest["games"]
        ],
    }
    validate_rank_outcomes(replay_manifest, artifact["receipt"])
    return items


def _rank_local_owners(conn, manifest, results, *, non_original_sources=()):
    """Resolve only supplied album side FKs; canonical names are assertions."""
    albums = {
        row["id"]: row
        for row in conn.execute(
            select(KifuAlbum.id, KifuAlbum.black_player_id, KifuAlbum.white_player_id).where(
                KifuAlbum.id.in_([result["album_id"] for result in results])
            )
        ).mappings()
    }
    players = {
        album[f"{side}_player_id"]
        for album in albums.values()
        for side in ("black", "white")
        if album[f"{side}_player_id"] is not None
    }
    canonical = dict(
        conn.execute(select(KifuPlayer.id, KifuPlayer.canonical_name).where(KifuPlayer.id.in_(players))).all()
    )
    by_source = {(result["source_key"], result["source_item_id"]): result["album_id"] for result in results}
    owners = {}
    for game in manifest["games"]:
        album = albums[by_source[game["source_key"], game["source_item_id"]]]
        same = conn.scalar(select(KifuAlbum.sgf_content == game["sgf_content"]).where(KifuAlbum.id == album["id"]))
        _require(
            same is True or (game["source_key"], game["source_item_id"]) in non_original_sources,
            "rank snapshot requires exact album SGF",
        )
        for side in ("black", "white"):
            owner, player_id = game["rank_snapshots"][side]["player_ref"], album[f"{side}_player_id"]
            _require(
                (owner is None and player_id is None)
                or owner is not None
                and canonical.get(player_id) == owner["canonical_name"],
                "rank snapshot local canonical owner mismatch",
            )
            if owner:
                prior = owners.setdefault(owner["canonical_name"], player_id)
                _require(prior == player_id, "rank owner resolves to multiple local players")
    return by_source, owners


def _apply_manifest_ranks(
    conn,
    manifest,
    results,
    batch_id,
    sequence,
    *,
    correction=False,
    identity_index=None,
    resource=None,
    rank_dispositions=None,
):
    if manifest["format"] != FORMAT_V2:
        return sequence, []
    contexts, non_original = {}, set()
    if rank_dispositions is not None:
        by_source = {(row["source_key"], row["source_item_id"]): row["album_id"] for row in results}
        for game in manifest["games"]:
            if any(is_historical_snapshot(snapshot) for snapshot in game["rank_snapshots"].values()):
                key = game["source_key"], game["source_item_id"]
                contexts[key] = _rank_source_context(conn, game, by_source[key], resource)
                for side, snapshot in game["rank_snapshots"].items():
                    binding = contexts[key]["binding"][side]
                    if (
                        is_historical_snapshot(snapshot)
                        and _rank_outcome(game, side, by_source[key], binding, "applied")["original_source_ref"]
                        != snapshot["source_ref"]
                    ):
                        non_original.add(key)
    by_source, owners = _rank_local_owners(conn, manifest, results, non_original_sources=non_original)
    if owners:
        list(
            conn.scalars(
                select(KifuPlayer.id)
                .where(KifuPlayer.id.in_(owners.values()))
                .order_by(KifuPlayer.id)
                .with_for_update()
            )
        )
    used_facts = {
        digest
        for game in manifest["games"]
        if (game["source_key"], game["source_item_id"]) not in non_original
        for digest in (
            *game.get("rank_observations", {}).values(),
            *(snapshot.get("rank_fact_sha256") for snapshot in game["rank_snapshots"].values()),
        )
        if digest
    }
    active_facts = {digest: fact for digest, fact in manifest["rank_facts"].items() if digest in used_facts}
    fact_ids, h = {}, KifuPlayerRankHistory.__table__
    fact_owners = {owners.get(fact["player_ref"]["canonical_name"]) for fact in active_facts.values()}
    before_ids = (
        conn.scalars(
            select(h.c.id).where(
                h.c.player_id.in_(fact_owners), or_(h.c.is_current, h.c.content_sha256.in_(manifest["rank_facts"]))
            )
        )
        if fact_owners
        else ()
    )
    before = {row_id: name_batch._image(conn, h, row_id) for row_id in before_ids}
    for digest, fact in sorted(active_facts.items()):
        player_id = owners.get(fact["player_ref"]["canonical_name"])
        _require(player_id is not None, "rank fact has no bound local player")
        # An older incoming observation may still change the current row's status.
        applied = player_ranks.apply_rank_fact(
            conn, player_id, fact, source_games=manifest["games"], identity_index=identity_index
        )
        fact_ids[digest] = applied["rank_fact_id"]
    for row_id in sorted(set(before) | set(fact_ids.values())):
        after = name_batch._image(conn, h, row_id)
        if before.get(row_id) != after:
            name_batch._record_change(
                conn, batch_id, sequence, KifuPlayerRankHistory, row_id, before.get(row_id), after
            )
            sequence += 1
    bindings = []
    for game in manifest["games"]:
        album_id = by_source[game["source_key"], game["source_item_id"]]
        for side, snapshot in game["rank_snapshots"].items():
            row = (
                conn.execute(
                    select(KifuAlbumRankSnapshot.__table__).where(
                        KifuAlbumRankSnapshot.album_id == album_id, KifuAlbumRankSnapshot.side == side
                    )
                )
                .mappings()
                .one_or_none()
            )
            if is_historical_snapshot(snapshot) and row and not correction and rank_dispositions is not None:
                _assert_retained_rank_row(
                    conn,
                    dict(row),
                    contexts[game["source_key"], game["source_item_id"]],
                    resource=resource,
                    current_batch_id=batch_id,
                )
            if is_historical_snapshot(snapshot) and (game["source_key"], game["source_item_id"]) in non_original:
                context = contexts[game["source_key"], game["source_item_id"]]
                outcome = _rank_outcome(
                    game,
                    side,
                    album_id,
                    context["binding"][side],
                    "retained" if row else "deferred",
                    row["snapshot"] if row else None,
                )
                expected_rank_for_outcome(game, side, outcome)
                rank_dispositions.append(
                    {
                        "outcome": outcome,
                        "source_binding": context["binding"][side],
                        "retained_row": dict(row) if row else None,
                    }
                )
                continue
            values = {
                "album_id": album_id,
                "side": side,
                "rank_fact_id": fact_ids.get(snapshot.get("rank_fact_sha256")),
                "snapshot": deepcopy(snapshot),
                "snapshot_sha256": snapshot["content_sha256"],
                "publication_key": manifest["publication_key"],
                "native_batch_id": batch_id,
            }
            if row:
                _require(
                    correction
                    or row["snapshot"] == snapshot
                    and row["snapshot_sha256"] == snapshot["content_sha256"]
                    and row["rank_fact_id"] == values["rank_fact_id"],
                    "existing frozen rank differs; explicit rank correction required",
                )
                row_id = row["id"]
                if correction:
                    before = name_batch._image(conn, KifuAlbumRankSnapshot.__table__, row_id)
                    conn.execute(
                        KifuAlbumRankSnapshot.__table__.update()
                        .where(KifuAlbumRankSnapshot.id == row_id)
                        .values(**values)
                    )
                    after = name_batch._image(conn, KifuAlbumRankSnapshot.__table__, row_id)
                    name_batch._record_change(conn, batch_id, sequence, KifuAlbumRankSnapshot, row_id, before, after)
                    sequence += 1
            else:
                row_id, after = name_batch._insert(conn, KifuAlbumRankSnapshot, values)
                name_batch._record_change(conn, batch_id, sequence, KifuAlbumRankSnapshot, row_id, None, after)
                sequence += 1
            bindings.append(
                {
                    "album_id": album_id,
                    "side": side,
                    "snapshot_id": row_id,
                    "snapshot_sha256": snapshot["content_sha256"],
                    **(
                        {
                            "publication_key": (
                                row["publication_key"] if row and not correction else manifest["publication_key"]
                            ),
                            "native_batch_id": (row["native_batch_id"] if row and not correction else batch_id),
                        }
                        if is_historical_snapshot(snapshot)
                        else {"rank_fact_sha256": snapshot["rank_fact_sha256"]}
                    ),
                    "rank_fact_id": values["rank_fact_id"],
                }
            )
            if is_historical_snapshot(snapshot) and rank_dispositions is not None:
                context = contexts[game["source_key"], game["source_item_id"]]
                outcome = _rank_outcome(game, side, album_id, context["binding"][side], "applied")
                expected_rank_for_outcome(game, side, outcome)
                rank_dispositions.append(
                    {"outcome": outcome, "source_binding": context["binding"][side], "retained_row": None}
                )
    return sequence, bindings


def _check_rank_replay(
    conn,
    manifest,
    results,
    bindings,
    *,
    identity_index=None,
    basis_bindings=None,
    resource=None,
    rank_dispositions=None,
):
    resource = resource or historical_ranks.EvidenceBudget()
    if manifest["format"] != FORMAT_V2:
        return
    retained = {
        (item["outcome"]["source_key"], item["outcome"]["source_item_id"], item["outcome"]["side"])
        for item in rank_dispositions or []
        if item["outcome"]["status"] != "applied"
    }
    by_source, owners = _rank_local_owners(conn, manifest, results, non_original_sources={key[:2] for key in retained})
    expected = {
        (by_source[game["source_key"], game["source_item_id"]], side): snapshot
        for game in manifest["games"]
        for side, snapshot in game["rank_snapshots"].items()
        if (game["source_key"], game["source_item_id"], side) not in retained
    }
    _require(isinstance(bindings, list) and len(bindings) == len(expected), "rank receipt bindings missing")
    seen = set()
    for binding in bindings:
        key = binding["album_id"], binding["side"]
        _require(key in expected and key not in seen, "rank receipt slot mismatch")
        seen.add(key)
        snapshot = expected[key]
        row = name_batch._image(conn, KifuAlbumRankSnapshot.__table__, binding["snapshot_id"])
        _require(
            row is not None
            and (row["album_id"], row["side"]) == key
            and row["snapshot"] == snapshot
            and row["snapshot_sha256"] == binding["snapshot_sha256"] == snapshot["content_sha256"]
            and row["rank_fact_id"] == binding["rank_fact_id"]
            and (is_historical_snapshot(snapshot) or snapshot["rank_fact_sha256"] == binding["rank_fact_sha256"]),
            "frozen rank snapshot changed after publication",
        )
        if is_historical_snapshot(snapshot):
            _require(
                row["rank_fact_id"] is None and "rank_fact_sha256" not in binding,
                "historical rank cannot claim a legacy fact",
            )
            _require(
                row["publication_key"] == binding.get("publication_key")
                and row["native_batch_id"] == binding.get("native_batch_id"),
                "historical rank publication CAS changed",
            )
            changes = list(
                conn.scalars(
                    select(KifuNameChange.after_image).where(
                        KifuNameChange.batch_id == row["native_batch_id"],
                        KifuNameChange.target_table == KifuAlbumRankSnapshot.__tablename__,
                        KifuNameChange.target_row_id == row["id"],
                    )
                )
            )
            _require(
                len(changes) == 1
                and changes[0] == row
                and conn.scalar(select(KifuNameBatch.status).where(KifuNameBatch.id == row["native_batch_id"]))
                == "applied",
                "historical rank current journal changed",
            )
            frozen = [
                x
                for x in basis_bindings or ()
                if x.get("target", {}).get("album_id") == key[0] and x.get("target", {}).get("side") == key[1]
            ]
            _require(
                len(frozen) == 1
                and historical_ranks.bind_rank_decision(
                    conn, {"album": {"id": key[0]}, "side": key[1]}, snapshot, resource=resource
                )
                == frozen[0],
                "frozen historical rank basis binding changed",
            )
            continue
        digest = binding["rank_fact_sha256"]
        if digest:
            fact = manifest["rank_facts"][digest]
            history = (
                conn.execute(
                    select(KifuPlayerRankHistory.__table__).where(KifuPlayerRankHistory.id == binding["rank_fact_id"])
                )
                .mappings()
                .one_or_none()
            )
            _require(
                history is not None
                and history["player_id"] == owners[fact["player_ref"]["canonical_name"]]
                and player_ranks._row_fact(history, fact["player_ref"]["canonical_name"])["content_sha256"] == digest,
                "immutable rank fact changed after publication",
            )
            player_ranks.verify_rank_fact_for_player(
                conn, history["player_id"], fact, source_games=manifest["games"], identity_index=identity_index
            )


def _rank_correction_sources(conn, manifest, *, check_cas, resource=None):
    resource = resource or historical_ranks.EvidenceBudget()
    """Read exact prior native batches and members only; never discover a library."""
    results, sources, seen = [], [], set()
    for game in manifest["games"]:
        correction = game["rank_correction"]
        original = (
            conn.execute(
                select(KifuNameBatch.__table__).where(
                    KifuNameBatch.bundle_sha256 == correction["original_manifest_sha256"]
                )
            )
            .mappings()
            .one_or_none()
        )
        _require(
            original is not None and original["status"] == "applied", "rank correction original publication missing"
        )
        artifact = original["reviewed_artifact"]
        _require(
            artifact.get("publication_format") in FORMATS
            and artifact.get("manifest_sha256") == original["bundle_sha256"],
            "rank correction original authority changed",
        )
        matches = [
            source
            for source in artifact.get("sources", ())
            if (source.get("source_key"), source.get("source_item_id")) == (game["source_key"], game["source_item_id"])
        ]
        _require(len(matches) == 1, "rank correction original source authority missing")
        source = matches[0]
        _require(
            all(
                source.get(key) == game[key]
                for key in ("source_key", "source_item_id", "origin_path", "raw_sha256", "sgf_sha256")
            ),
            "rank correction exact source assertion changed",
        )
        originals = [
            item
            for item in artifact.get("logical_manifest", {}).get("games", ())
            if (item.get("source_key"), item.get("source_item_id")) == (game["source_key"], game["source_item_id"])
        ]
        _require(
            len(originals) == 1
            and originals[0].get("metadata") == game["metadata"]
            and originals[0].get("source_metadata") == game.get("source_metadata"),
            "rank correction original metadata changed",
        )
        _require(
            all(
                originals[0].get("identities", {}).get(side) == game.get("identities", {}).get(side)
                for side in ("black", "white")
            ),
            "rank correction original canonical identity changed",
        )
        _check_source_receipts(conn, [source], resource=resource)
        album_id = source["album_id"]
        _require(album_id not in seen, "rank correction repeats local album")
        seen.add(album_id)
        album = dict(
            conn.execute(
                select(
                    KifuAlbum.id,
                    KifuAlbum.player_black,
                    KifuAlbum.player_white,
                    KifuAlbum.black_rank,
                    KifuAlbum.white_rank,
                    historical_ranks._body_length(conn, KifuAlbum.sgf_content).label("sgf_bytes"),
                ).where(KifuAlbum.id == album_id)
            )
            .mappings()
            .one()
        )
        album["sgf_content"] = historical_ranks.load_rank_body(
            conn, album, resource=resource, expected_sha=source["album_sgf_sha256"]
        )
        _require(
            album is not None and album["sgf_content"] == game["sgf_content"], "rank correction original SGF changed"
        )
        for key in ("player_black", "player_white", "black_rank", "white_rank"):
            _require(album[key] == game["metadata"].get(key), "rank correction original raw fields changed")
        if check_cas:
            for side, expected in correction["expected_snapshots"].items():
                row = (
                    conn.execute(
                        select(KifuAlbumRankSnapshot.__table__).where(
                            KifuAlbumRankSnapshot.album_id == album_id, KifuAlbumRankSnapshot.side == side
                        )
                    )
                    .mappings()
                    .one_or_none()
                )
                _require(
                    (row is None and expected is None)
                    or row is not None
                    and row["snapshot_sha256"] == row["snapshot"]["content_sha256"] == expected,
                    "rank correction previous snapshot CAS changed",
                )
                if row:
                    from katrain.kifu_ingest.ranks import validate_rank_snapshot

                    validate_rank_snapshot(row["snapshot"])
                    old_snapshot = row["snapshot"]
                    _require(
                        old_snapshot["source_ref"] == game["rank_snapshots"][side]["source_ref"]
                        and old_snapshot["player_ref"] == game["rank_snapshots"][side]["player_ref"],
                        "rank correction previous snapshot identity changed",
                    )
                    digest = old_snapshot.get("rank_fact_sha256")
                    _require(
                        (digest is None) == (row["rank_fact_id"] is None), "rank correction previous fact link changed"
                    )
                    if digest:
                        history = (
                            conn.execute(
                                select(KifuPlayerRankHistory.__table__).where(
                                    KifuPlayerRankHistory.id == row["rank_fact_id"]
                                )
                            )
                            .mappings()
                            .one_or_none()
                        )
                        _require(
                            history is not None
                            and history["player_id"] == album[f"{side}_player_id"]
                            and player_ranks._row_fact(history, old_snapshot["player_ref"]["canonical_name"])[
                                "content_sha256"
                            ]
                            == digest,
                            "rank correction previous immutable fact changed",
                        )
        results.append(
            {
                "source_key": game["source_key"],
                "source_item_id": game["source_item_id"],
                "album_id": album_id,
                "action": "rank_corrected",
            }
        )
        sources.append(deepcopy(source))
    _rank_local_owners(conn, manifest, results)
    _require_public(conn, seen)
    _coverage(conn, seen, resource=resource)
    return results, sources


def _publish_rank_correction(engine, manifest, manifest_hash, lock_timeout_ms):
    resource = historical_ranks.EvidenceBudget()
    for game in manifest["games"]:
        resource.remember_body(game["sgf_content"])
    with name_batch._locked_write(
        engine,
        lock_timeout_ms=lock_timeout_ms,
        search_operation=(
            "catalog_publish",
            {"manifest_sha256": manifest_hash, "publication_key": manifest["publication_key"]},
        ),
    ) as conn:
        previous = (
            conn.execute(select(KifuNameBatch.__table__).where(KifuNameBatch.bundle_sha256 == manifest_hash))
            .mappings()
            .one_or_none()
        )
        results, sources = _rank_correction_sources(conn, manifest, check_cas=previous is None, resource=resource)
        rank_identity_index = (
            player_ranks.build_rank_identity_index(
                conn,
                raw_values={
                    value
                    for fact in manifest["rank_facts"].values()
                    for value in (fact["evidence"]["grade"]["raw_name"], fact["player_ref"]["canonical_name"])
                },
            )
            if manifest["rank_facts"]
            else {}
        )
        if previous:
            artifact = previous["reviewed_artifact"]
            _require(
                previous["status"] == "applied"
                and artifact.get("manifest_sha256") == manifest_hash
                and artifact.get("publication_format") == FORMAT_V2
                and artifact.get("publication_mode") == "rank_only",
                "rank correction receipt is not applied",
            )
            _require(
                artifact.get("sources") == sources and artifact["receipt"]["games"] == results,
                "rank correction receipt membership changed",
            )
            _check_rank_replay(
                conn,
                manifest,
                results,
                artifact.get("rank_bindings"),
                identity_index=rank_identity_index,
                basis_bindings=artifact.get("basis_bindings"),
                resource=resource,
            )
            return deepcopy(artifact["receipt"])
        _require(
            conn.scalar(
                select(KifuNameBatch.id).where(
                    KifuNameBatch.reviewed_artifact["publication_key"].as_string() == manifest["publication_key"]
                )
            )
            is None,
            "publication key already names a different manifest",
        )
        _verify_initial_manifest_ranks(conn, manifest, results=results, resource=resource)
        registry_id, _ = name_batch._source_registry_for_batch(
            conn, _REGISTRY, {"registry_sha256": canonical_sha256(_REGISTRY)}
        )
        batch_id, _ = name_batch._insert(
            conn,
            KifuNameBatch,
            {
                "bundle_sha256": manifest_hash,
                "inventory_sha256": canonical_sha256(sources),
                "source_registry_id": registry_id,
                "status": "pending",
                "reviewed_artifact": {},
            },
        )
        _sequence, bindings = _apply_manifest_ranks(
            conn, manifest, results, batch_id, 1, correction=True, identity_index=rank_identity_index
        )
        receipt = {
            "status": "applied",
            "batch_id": batch_id,
            "manifest_sha256": manifest_hash,
            "games": results,
            "name_batch_id": None,
            "reviewed_name_batch_id": None,
        }
        artifact = {
            "publication_format": FORMAT_V2,
            "publication_mode": "rank_only",
            "publication_key": manifest["publication_key"],
            "manifest_sha256": manifest_hash,
            "sources": sources,
            "receipt": receipt,
            "rank_bindings": bindings,
            **(
                {"basis_bindings": _manifest_basis_bindings(conn, manifest, results, resource=resource)}
                if any(
                    is_historical_snapshot(x) for g in manifest["games"] for x in g.get("rank_snapshots", {}).values()
                )
                else {}
            ),
            "logical_manifest": {
                **manifest,
                "games": [{k: v for k, v in game.items() if k != "sgf_content"} for game in manifest["games"]],
            },
            "undo_guard": _publication_undo_guard(conn, receipt, sources, {r["album_id"] for r in results}),
        }
        conn.execute(
            KifuNameBatch.__table__.update()
            .where(KifuNameBatch.id == batch_id)
            .values(status="applied", applied_at=datetime.now(timezone.utc), reviewed_artifact=artifact)
        )
        return receipt


def publish_manifest(
    engine, manifest, *, expected_manifest_sha256, lock_timeout_ms=15000, sgf_cache=None, expected_rank_outcomes=None
):
    """Publish all games or roll back all rows, evidence, scopes and receipt.

    Replays return the original receipt exactly. A reused source ID with changed
    bytes is a conflict; equal complete canonical SGFs may add a source link.

    ``games`` contain source_key, numeric source_item_id, origin_path, raw_sha256,
    sgf_sha256 (the exact UTF-8 content hash), complete sgf_content, and metadata
    with the raw SGF player/event/date fields. Optional ``identities`` uses black,
    white and event keys: omitted means unambiguous canonical/alias lookup;
    null preserves the literal slot; {canonical_name: ...} binds a logical owner.

    ``decisions`` use kind/key, all five displays and methods, original_language,
    sources, finite source_items, producer and review. See validate_decision for
    the complete review schema. Sources and actual request IDs are retained in
    evidence, with local scope binding recorded separately from text approval.
    Frozen linked-literal/composition/selection profiles are never broadened;
    if their current proof cannot cover a new card the whole publication fails.
    """
    prepared = _validate_manifest(manifest, expected_manifest_sha256)
    with _publication_guard(engine):
        if manifest.get("format") == FORMAT_V2 and manifest.get("mode") == "rank_only":
            try:
                return _publish_rank_correction(engine, manifest, expected_manifest_sha256, lock_timeout_ms)
            except ValueError as exc:
                if isinstance(exc, PublicationError):
                    raise
                raise PublicationError(str(exc)) from exc
        return _publish_prepared(
            engine, manifest, expected_manifest_sha256, prepared, lock_timeout_ms, sgf_cache, expected_rank_outcomes
        )


def _publish_prepared(
    engine, manifest, expected_manifest_sha256, prepared, lock_timeout_ms, sgf_cache, expected_rank_outcomes=None
):
    manifest_hash = expected_manifest_sha256
    resource = historical_ranks.EvidenceBudget()
    for game, _ in prepared:
        resource.remember_body(game["sgf_content"])
    try:
        with name_batch._locked_write(
            engine,
            lock_timeout_ms=lock_timeout_ms,
            search_operation=(
                "catalog_publish",
                {"manifest_sha256": manifest_hash, "publication_key": manifest["publication_key"]},
            ),
        ) as conn:
            if conn.dialect.name == "postgresql":
                conn.execute(
                    text("SELECT set_config('statement_timeout', :timeout, true)"),
                    {"timeout": f"{_STATEMENT_TIMEOUT_MS}ms"},
                )
            identity_indexes = _identity_indexes(conn)
            previous = (
                conn.execute(select(KifuNameBatch.__table__).where(KifuNameBatch.bundle_sha256 == manifest_hash))
                .mappings()
                .one_or_none()
            )
            if previous:
                artifact = previous["reviewed_artifact"]
                if expected_rank_outcomes is not None:
                    _require(
                        portable_rank_outcomes(artifact.get("receipt", {}).get("rank_outcomes", []))
                        == portable_rank_outcomes(expected_rank_outcomes),
                        "frozen TEST rank outcome CAS changed",
                    )
                _require(
                    previous["status"] == "applied"
                    and artifact.get("publication_format") in FORMATS
                    and artifact.get("manifest_sha256") == manifest_hash,
                    "publication receipt is not applied",
                )
                _check_source_receipts(conn, artifact["sources"], resource=resource)
                games_by_source = {(game["source_key"], game["source_item_id"]): game for game, _ in prepared}
                sources_by_key = {
                    (source["source_key"], source["source_item_id"]): source for source in artifact["sources"]
                }
                _require(set(games_by_source) == set(sources_by_key), "publication receipt source membership changed")
                requested_ids = {game["album_id"] for game in artifact["receipt"]["games"]}
                _validate_catalog_repairs(conn, artifact, resource=resource)
                _require(
                    requested_ids == {source["album_id"] for source in artifact["sources"]},
                    "publication receipt album membership changed",
                )
                _require_source_publication(conn, requested_ids, resource=resource)
                for key, game in games_by_source.items():
                    _check_reused_identity_instructions(conn, game, sources_by_key[key]["album_id"], identity_indexes)
                dispositions = _check_rank_dispositions(conn, manifest, artifact, resource=resource)
                _check_rank_replay(
                    conn,
                    manifest,
                    artifact["receipt"]["games"],
                    artifact.get("rank_bindings"),
                    identity_index=identity_indexes["player"],
                    basis_bindings=artifact.get("basis_bindings"),
                    resource=resource,
                    rank_dispositions=dispositions,
                )
                _coverage(conn, requested_ids, resource=resource)
                return deepcopy(artifact["receipt"])
            conflict = conn.scalar(
                select(KifuNameBatch.id).where(
                    KifuNameBatch.reviewed_artifact["publication_key"].as_string() == manifest["publication_key"]
                )
            )
            _require(conflict is None, "publication key already names a different manifest")
            before_inventory, _ = name_batch._snapshot_sha(conn)
            before_catalog = name_batch._catalog_sha(conn)
            raws = {game["metadata"].get("event") for game, _ in prepared if game["metadata"].get("event")}
            captured = _existing_event_proofs(conn, raws)
            player_raws = {
                game["metadata"][field] for game, _ in prepared for field in ("player_black", "player_white")
            }
            raw_players = _existing_player_proofs(conn, player_raws)
            affected = set(conn.scalars(select(KifuAlbum.id).where(KifuAlbum.event.in_(raws))))
            affected.update(
                conn.scalars(
                    select(KifuAlbumEventSelection.album_id).where(KifuAlbumEventSelection.selected_raw.in_(raws))
                )
            )
            for prior in raw_players.values():
                if prior["scope"]:
                    affected.update(row["album_id"] for row in prior["scope"]["content"]["slots"])
            _coverage(conn, affected, resource=resource)
            source_records = _source_records(
                conn, {(game["source_key"], game["source_item_id"]) for game, _ in prepared}
            )
            exact = {}
            lookup_deferred = []
            _verify_initial_manifest_ranks(conn, manifest, indexes=identity_indexes, resource=resource)
            if expected_rank_outcomes is not None:
                _require(isinstance(expected_rank_outcomes, list), "frozen TEST rank outcome list required")
                planned_outcomes = _planned_rank_outcomes(conn, manifest, prepared, source_records, resource)
                _require(
                    portable_rank_outcomes(planned_outcomes) == portable_rank_outcomes(expected_rank_outcomes),
                    "frozen TEST rank outcome CAS changed",
                )
            registry_id, _ = name_batch._source_registry_for_batch(
                conn, _REGISTRY, {"registry_sha256": canonical_sha256(_REGISTRY)}
            )
            batch_id, _ = name_batch._insert(
                conn,
                KifuNameBatch,
                {
                    "bundle_sha256": manifest_hash,
                    "inventory_sha256": before_inventory,
                    "source_registry_id": registry_id,
                    "status": "pending",
                    "reviewed_artifact": {},
                },
            )
            sequence, results, receipts, new_raws = 1, [], [], set()
            for game, canonical in prepared:
                source_identity = (game["source_key"], game["source_item_id"])
                old_source = source_records.get(source_identity)
                if old_source:
                    _check_source_receipts(conn, [old_source], resource=resource)
                    _require(
                        all(old_source[key] == game[key] for key in ("raw_sha256", "sgf_sha256", "origin_path")),
                        "source ID content changed; explicit revision required",
                    )
                    album_id, action = old_source["album_id"], "reused"
                else:
                    origin_owners = _source_owner_ids(conn, game)
                    matches = set(exact.get(canonical, ())) | _bounded_exact_matches(
                        conn, game, canonical, origin_owners, resource, lookup_deferred
                    )
                    source_owner = _select_source_owner(conn, game, matches, origin_owners, resource=resource)
                    if source_owner is not None:
                        album_id, action = source_owner, "reused"
                    else:
                        identities = game.get("identities", {})
                        metadata = derive_metadata(game["sgf_content"], game.get("source_metadata"), game["source_key"])
                        for slot in ("black", "white"):
                            metadata[f"{slot}_player_id"] = _resolve_identity(
                                "player", metadata[f"player_{slot}"], identities.get(slot, "auto"), identity_indexes
                            )
                        metadata["event_id"] = (
                            _resolve_identity(
                                "event", metadata.get("event"), identities.get("event", "auto"), identity_indexes
                            )
                            if metadata.get("event")
                            else None
                        )
                        metadata.update(sgf_content=game["sgf_content"], source_path=game["origin_path"])
                        album_id, after = name_batch._insert(conn, KifuAlbum, metadata)
                        resource.remember_body(game["sgf_content"], album_id=album_id)
                        name_batch._record_change(conn, batch_id, sequence, KifuAlbum, album_id, None, after)
                        sequence += 1
                        exact.setdefault(canonical, []).append(album_id)
                        action = "inserted"
                        if metadata.get("event"):
                            new_raws.add(metadata["event"])
                _require_source_publication(conn, {album_id}, resource=resource)
                if action == "reused":
                    _check_reused_identity_instructions(conn, game, album_id, identity_indexes)
                source_id = conn.scalar(select(KifuSource.id).where(KifuSource.source_key == game["source_key"]))
                if source_id is None:
                    source_id, after = name_batch._insert(conn, KifuSource, {"source_key": game["source_key"]})
                    name_batch._record_change(conn, batch_id, sequence, KifuSource, source_id, None, after)
                    sequence += 1
                link = conn.scalar(
                    select(KifuAlbumSource.id).where(
                        KifuAlbumSource.album_id == album_id,
                        KifuAlbumSource.source_id == source_id,
                        KifuAlbumSource.origin_path == game["origin_path"],
                    )
                )
                if link is None:
                    link_id, after = name_batch._insert(
                        conn,
                        KifuAlbumSource,
                        {
                            "album_id": album_id,
                            "source_id": source_id,
                            "origin_path": game["origin_path"],
                            "match_method": "incremental-exact-sgf" if action == "reused" else "incremental-new",
                        },
                    )
                    name_batch._record_change(conn, batch_id, sequence, KifuAlbumSource, link_id, None, after)
                    sequence += 1
                original = (
                    conn.execute(select(KifuAlbum.duplicate_of_id).where(KifuAlbum.id == album_id)).mappings().one()
                )
                if original["duplicate_of_id"] is not None:
                    from katrain.web.kifu.catalog_standardization import verified_display_duplicate

                    canonical_id = verified_display_duplicate(conn, album_id, resource=resource)["canonical_album_id"]
                    aggregate = conn.scalar(
                        select(KifuAlbumSource.id).where(
                            KifuAlbumSource.album_id == canonical_id,
                            KifuAlbumSource.source_id == source_id,
                            KifuAlbumSource.origin_path == game["origin_path"],
                        )
                    )
                    if aggregate is None:
                        aggregate_id, after = name_batch._insert(
                            conn,
                            KifuAlbumSource,
                            {
                                "album_id": canonical_id,
                                "source_id": source_id,
                                "origin_path": game["origin_path"],
                                "match_method": "reviewed_same_game",
                            },
                        )
                        name_batch._record_change(conn, batch_id, sequence, KifuAlbumSource, aggregate_id, None, after)
                        sequence += 1
                    affected.add(canonical_id)
                affected.add(album_id)
                results.append(
                    {
                        "source_key": game["source_key"],
                        "source_item_id": game["source_item_id"],
                        "album_id": album_id,
                        "action": action,
                    }
                )
                source_scalar = {
                    "id": album_id,
                    "sgf_bytes": conn.scalar(
                        select(historical_ranks._body_length(conn, KifuAlbum.sgf_content)).where(
                            KifuAlbum.id == album_id
                        )
                    ),
                }
                source_body = historical_ranks.load_rank_body(conn, source_scalar, resource=resource)
                receipts.append(
                    {
                        **{
                            key: game[key]
                            for key in ("source_key", "source_item_id", "origin_path", "raw_sha256", "sgf_sha256")
                        },
                        "album_id": album_id,
                        "album_sgf_sha256": sha256(source_body.encode()).hexdigest(),
                    }
                )
            rank_dispositions = []
            sequence, rank_bindings = _apply_manifest_ranks(
                conn,
                manifest,
                results,
                batch_id,
                sequence,
                identity_index=identity_indexes["player"],
                resource=resource,
                rank_dispositions=rank_dispositions,
            )
            after_inventory, _ = name_batch._snapshot_sha(conn)
            reviewed_name_batch_id, sequence = _apply_decisions(
                conn,
                manifest.get("decisions", []),
                results,
                raw_players,
                after_inventory,
                manifest_hash,
                batch_id,
                sequence,
            )
            name_batch_id = _renew_events(conn, captured, new_raws, after_inventory, manifest_hash)
            repairs = _apply_catalog_repairs(conn, {row["album_id"] for row in results}, resource=resource)
            affected.update(repairs["affected_album_ids"])
            _coverage(conn, affected, resource=resource)
            receipt = {
                "status": "applied",
                "batch_id": batch_id,
                "manifest_sha256": manifest_hash,
                "games": results,
                "name_batch_id": name_batch_id,
                "reviewed_name_batch_id": reviewed_name_batch_id,
                **({"rank_outcomes": [item["outcome"] for item in rank_dispositions]} if rank_dispositions else {}),
            }
            if rank_dispositions:
                validate_rank_outcomes(manifest, receipt)
            if expected_rank_outcomes is not None:
                _require(
                    portable_rank_outcomes(receipt.get("rank_outcomes", []))
                    == portable_rank_outcomes(expected_rank_outcomes),
                    "frozen TEST rank outcome final CAS changed",
                )
            conn.execute(
                KifuNameBatch.__table__.update()
                .where(KifuNameBatch.id == batch_id)
                .values(
                    status="applied",
                    applied_at=datetime.now(timezone.utc),
                    reviewed_artifact={
                        "publication_format": manifest["format"],
                        "publication_key": manifest["publication_key"],
                        "manifest_sha256": manifest_hash,
                        "sources": receipts,
                        **({"rank_bindings": rank_bindings} if manifest["format"] == FORMAT_V2 else {}),
                        **(
                            {
                                "basis_bindings": _manifest_basis_bindings(
                                    conn, manifest, results, resource=resource, rank_dispositions=rank_dispositions
                                )
                            }
                            if any(
                                is_historical_snapshot(x)
                                for g in manifest["games"]
                                for x in g.get("rank_snapshots", {}).values()
                            )
                            else {}
                        ),
                        "receipt": receipt,
                        **({"rank_dispositions": rank_dispositions} if rank_dispositions else {}),
                        "catalog_repairs": repairs,
                        "catalog_lookup_deferred": lookup_deferred,
                        "undo_guard": {
                            **_publication_undo_guard(conn, receipt, receipts, affected),
                            "catalog_repairs_sha256": canonical_sha256(repairs),
                            **(
                                {"rank_dispositions_sha256": canonical_sha256(rank_dispositions)}
                                if rank_dispositions
                                else {}
                            ),
                        },
                        "logical_manifest": {
                            **manifest,
                            "games": [
                                {key: value for key, value in game.items() if key != "sgf_content"}
                                for game, _canonical in prepared
                            ],
                        },
                        "before_inventory_sha256": before_inventory,
                        "before_catalog_sha256": before_catalog,
                        "after_inventory_sha256": after_inventory,
                    },
                )
            )
            return receipt
    except ValueError as exc:
        if isinstance(exc, PublicationError):
            raise
        raise PublicationError(str(exc)) from exc
