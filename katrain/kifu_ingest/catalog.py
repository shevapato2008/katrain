"""Atomic publication of logical, independently reviewed incremental game manifests.

Model/network work happens before this API. IDs are always resolved in the target
database. The existing strict first-pass proof/journal format is retained; the
versioned ``incremental_binding`` explains which content was reviewed outside the
transaction and which finite IDs/scopes were bound by deterministic code.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
import re
from urllib.parse import urlparse

from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from katrain.core.sgf_parser import SGF
from katrain.kifu_ingest.exclusions import assert_source_allowed
from katrain.kifu_ingest.preparation import derive_metadata
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
    KifuPlayerAlias,
    KifuRawEventName,
    KifuRawEventValue,
    KifuRawPlayerName,
    KifuRawPlayerValue,
    KifuSource,
)
from katrain.web.kifu import name_batch, name_first_pass
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
BINDING_VERSION = "kifu-incremental-binding-v1"
LANGUAGES = ("cn", "tw", "jp", "ko", "en")
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
        manifest.get("format") == FORMAT
        and isinstance(manifest.get("publication_key"), str)
        and manifest["publication_key"].strip(),
        "manifest format or publication key missing",
    )
    games = manifest.get("games")
    _require(isinstance(games, list) and games, "manifest needs a finite game list")
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


def _check_reused_identity_instructions(conn, game, album_id, indexes):
    instructions = game.get("identities", {})
    if not instructions:
        return
    album = name_batch._image(conn, KifuAlbum.__table__, album_id)
    _require(album is not None, "reused identity album is missing")
    for slot in ("black", "white", "event"):
        if slot not in instructions:
            continue
        kind = "event" if slot == "event" else "player"
        raw_field = "event" if slot == "event" else f"player_{slot}"
        id_field = "event_id" if slot == "event" else f"{slot}_player_id"
        expected = _resolve_identity(kind, game["metadata"].get(raw_field), instructions[slot], indexes)
        _require(album[id_field] == expected, "explicit identity instruction differs from reused album identity")


def _coverage(conn, ids):
    if not ids:
        return
    with Session(bind=conn) as db:
        albums = (
            db.query(KifuAlbum)
            .filter(KifuAlbum.id.in_(ids), KifuAlbum.duplicate_of_id.is_(None), KifuAlbum.list_hidden_reason.is_(None))
            .all()
        )
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
    name_batch._check_cross_bundle_collisions(conn, candidates, owners=declarations, research_by_hash=research_by_hash)
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
            album = name_batch._image(conn, KifuAlbum.__table__, game["album_id"])
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


def _source_records(conn):
    """Read committed source identities from atomic publication receipts."""
    result = {}
    for artifact in conn.scalars(
        select(KifuNameBatch.reviewed_artifact).where(
            KifuNameBatch.status == "applied",
            KifuNameBatch.reviewed_artifact["publication_format"].as_string() == FORMAT,
        )
    ):
        if isinstance(artifact, dict) and artifact.get("publication_format") == FORMAT:
            for source in artifact.get("sources", ()):
                key = (source["source_key"], source["source_item_id"])
                _require(key not in result or result[key] == source, "conflicting committed source receipts")
                result[key] = source
    return result


def _check_source_receipts(conn, receipts):
    for source in receipts:
        content = conn.scalar(select(KifuAlbum.sgf_content).where(KifuAlbum.id == source["album_id"]))
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
            KifuNameBatch.reviewed_artifact["publication_format"].as_string() == FORMAT,
        )
    )
    for artifact in artifacts:
        for source in artifact.get("sources", ()):
            _require(
                source["album_id"] not in deleted_albums
                and (source["album_id"], source["source_key"], source["origin_path"]) not in deleted_links,
                "dependent applied publication receipt blocks compensation",
            )


def undo_publication(engine, batch_id, *, lock_timeout_ms=15000):
    """Conditionally compensate one complete publication, or change nothing.

    All parent/child journals and current after-images must still match. Native
    name revisions are reversed before source links and newly inserted albums;
    later edits or dependencies reject the entire transaction. This explicit
    entry point is never called automatically after an uncertain API response.
    """
    tables = {
        **name_batch._UNDO_TABLES,
        KifuSource.__tablename__: KifuSource.__table__,
        KifuAlbumSource.__tablename__: KifuAlbumSource.__table__,
    }
    try:
        with name_batch._locked_write(engine, lock_timeout_ms=lock_timeout_ms) as conn:
            batch = name_batch._image(conn, KifuNameBatch.__table__, batch_id)
            _require(batch is not None, "publication batch not found")
            artifact = batch["reviewed_artifact"]
            receipt, guard = artifact.get("receipt"), artifact.get("undo_guard")
            _require(
                artifact.get("publication_format") == FORMAT
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
            if batch["status"] == "undone":
                outcome = artifact.get("undo_receipt")
                _require(
                    isinstance(outcome, dict)
                    and outcome.get("batch_id") == batch_id
                    and outcome.get("status") == "undone",
                    "publication undo receipt changed",
                )
                return deepcopy(outcome)
            _check_source_receipts(conn, artifact["sources"])
            _check_retained_publication_receipts(conn, batch_id, journals)
            for changes in journals:
                for change in changes:
                    table = tables.get(change["target_table"])
                    _require(table is not None, "publication journal target is not allowlisted")
                    _require(
                        name_batch._image(conn, table, change["target_row_id"]) == change["after_image"],
                        "publication after-image changed",
                    )
                    _require(
                        not name_batch._retained_composition_dependency(
                            conn, table, change["target_row_id"], change["before_image"]
                        ),
                        "later composed evidence changed publication dependencies",
                    )
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
            _coverage(conn, set(guard["affected_album_ids"]))
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


def publish_manifest(engine, manifest, *, expected_manifest_sha256, lock_timeout_ms=15000, sgf_cache=None):
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
    manifest_hash = expected_manifest_sha256
    sgf_cache = {} if sgf_cache is None else sgf_cache
    if not sgf_cache:
        warm_sgf_cache(engine, sgf_cache)
    try:
        with name_batch._locked_write(engine, lock_timeout_ms=lock_timeout_ms) as conn:
            identity_indexes = _identity_indexes(conn)
            previous = (
                conn.execute(select(KifuNameBatch.__table__).where(KifuNameBatch.bundle_sha256 == manifest_hash))
                .mappings()
                .one_or_none()
            )
            if previous:
                artifact = previous["reviewed_artifact"]
                _require(
                    previous["status"] == "applied"
                    and artifact.get("publication_format") == FORMAT
                    and artifact.get("manifest_sha256") == manifest_hash,
                    "publication receipt is not applied",
                )
                _check_source_receipts(conn, artifact["sources"])
                games_by_source = {(game["source_key"], game["source_item_id"]): game for game, _ in prepared}
                sources_by_key = {
                    (source["source_key"], source["source_item_id"]): source for source in artifact["sources"]
                }
                _require(set(games_by_source) == set(sources_by_key), "publication receipt source membership changed")
                requested_ids = {game["album_id"] for game in artifact["receipt"]["games"]}
                _require(
                    requested_ids == {source["album_id"] for source in artifact["sources"]},
                    "publication receipt album membership changed",
                )
                _require_public(conn, requested_ids)
                for key, game in games_by_source.items():
                    _check_reused_identity_instructions(conn, game, sources_by_key[key]["album_id"], identity_indexes)
                _coverage(conn, requested_ids)
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
            _coverage(conn, affected)
            source_records = _source_records(conn)
            exact = {}
            wanted = {sha256(canonical.encode("utf-8")).hexdigest(): canonical for _, canonical in prepared}
            originals = (
                conn.execution_options(stream_results=True)
                .execute(select(KifuAlbum.id, KifuAlbum.sgf_content))
                .yield_per(500)
            )
            for old in originals.mappings():
                canonical_hash = _cached_canonical_sha(old["sgf_content"], sgf_cache)
                if canonical_hash in wanted and _canonical_sgf(old["sgf_content"]) == wanted[canonical_hash]:
                    exact.setdefault(wanted[canonical_hash], []).append(old["id"])
            # PostgreSQL server-side cursors are for the streaming read only.
            conn.execution_options(stream_results=False)
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
                    _check_source_receipts(conn, [old_source])
                    _require(
                        all(old_source[key] == game[key] for key in ("raw_sha256", "sgf_sha256", "origin_path")),
                        "source ID content changed; explicit revision required",
                    )
                    album_id, action = old_source["album_id"], "reused"
                else:
                    origin_owners = set(
                        conn.scalars(
                            select(KifuAlbumSource.album_id)
                            .join(KifuSource, KifuSource.id == KifuAlbumSource.source_id)
                            .where(
                                KifuSource.source_key == game["source_key"],
                                KifuAlbumSource.origin_path == game["origin_path"],
                            )
                        )
                    )
                    origin_owners.update(
                        conn.scalars(select(KifuAlbum.id).where(KifuAlbum.source_path == game["origin_path"]))
                    )
                    matches = set(exact.get(canonical, ()))
                    _require(not origin_owners or origin_owners <= matches, "existing source path content changed")
                    _require(len(matches) <= 1, "multiple exact SGFs require explicit duplicate resolution")
                    if matches:
                        album_id, action = next(iter(matches)), "reused"
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
                        name_batch._record_change(conn, batch_id, sequence, KifuAlbum, album_id, None, after)
                        sequence += 1
                        exact.setdefault(canonical, []).append(album_id)
                        action = "inserted"
                        if metadata.get("event"):
                            new_raws.add(metadata["event"])
                _require_public(conn, {album_id})
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
                affected.add(album_id)
                results.append(
                    {
                        "source_key": game["source_key"],
                        "source_item_id": game["source_item_id"],
                        "album_id": album_id,
                        "action": action,
                    }
                )
                receipts.append(
                    {
                        **{
                            key: game[key]
                            for key in ("source_key", "source_item_id", "origin_path", "raw_sha256", "sgf_sha256")
                        },
                        "album_id": album_id,
                        "album_sgf_sha256": sha256(
                            conn.scalar(select(KifuAlbum.sgf_content).where(KifuAlbum.id == album_id)).encode("utf-8")
                        ).hexdigest(),
                    }
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
            _coverage(conn, affected)
            receipt = {
                "status": "applied",
                "batch_id": batch_id,
                "manifest_sha256": manifest_hash,
                "games": results,
                "name_batch_id": name_batch_id,
                "reviewed_name_batch_id": reviewed_name_batch_id,
            }
            conn.execute(
                KifuNameBatch.__table__.update()
                .where(KifuNameBatch.id == batch_id)
                .values(
                    status="applied",
                    applied_at=datetime.now(timezone.utc),
                    reviewed_artifact={
                        "publication_format": FORMAT,
                        "publication_key": manifest["publication_key"],
                        "manifest_sha256": manifest_hash,
                        "sources": receipts,
                        "receipt": receipt,
                        "undo_guard": _publication_undo_guard(conn, receipt, receipts, affected),
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
