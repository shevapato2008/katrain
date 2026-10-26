"""Explicit, small CLI for local inventory and immutable Kifu publication."""

from __future__ import annotations

import argparse
import asyncio
from dataclasses import asdict
from datetime import date, datetime, timezone
from hashlib import sha256
import inspect
import json
import logging
import os
from pathlib import Path
import sys

from sqlalchemy import create_engine

from katrain.core.sgf_parser import SGF
from katrain.kifu_ingest.catalog import (
    FORMAT,
    _validate_manifest,
    check_identity_instructions,
    lookup_qualified_identities,
    publish_manifest,
    qualified_raw_event_templates,
    qualified_raw_player_templates,
    validate_decision,
    validate_identity_check_request,
    validate_identity_check_response,
)
from katrain.kifu_ingest.exclusions import assert_source_allowed, historical_excluded_ids
from katrain.kifu_ingest.inventory import scan_inventory
from katrain.kifu_ingest.names import NameRejected, NeedsCredentials, QwenNameService, wiki_sources
from katrain.kifu_ingest.preparation import derive_metadata
from katrain.kifu_ingest.ranks import FORMAT_V2, freeze_game_ranks, merge_rank_facts, preflight_manifest_budget
from katrain.kifu_ingest.state import StateStore
from katrain.kifu_ingest.sync import IdentityCheckUnavailable, validate_test_verification
from katrain.web.kifu.name_candidates import canonical_sha256
from katrain.web.kifu.player_ranks import lookup_library_rank_facts, lookup_professional_identity_evidence


MAX_RECEIVE_BYTES = 16 * 1024 * 1024
logger = logging.getLogger(__name__)
_RANK_LOOKUP_REASONS = frozenset(
    {
        "identity_not_unique",
        "local_owner_mismatch",
        "current_conflict",
        "current_system_unspecified",
        "stored_fact_invalid",
        "same_day_raw_rank_conflict",
        "no_verifiable_raw_rank",
        "professional_identity_unverified",
        "official_grade_above_library_grade",
        "recent_raw_rank_conflict",
    }
)


def _engine():
    dsn = os.getenv("KIFU_INGEST_DATABASE_URL")
    if not dsn:
        raise ValueError("KIFU_INGEST_DATABASE_URL is required")
    return create_engine(dsn, pool_pre_ping=True)


def _read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _output(value):
    print(json.dumps(value, ensure_ascii=False, sort_keys=True, default=str))


def _validated(manifest, expected=None):
    if not isinstance(manifest, dict):
        raise ValueError("manifest must be an object")
    digest = canonical_sha256(manifest)
    _validate_manifest(manifest, expected or digest)
    if len(manifest["games"]) > 100:
        raise ValueError("manifest exceeds 100 games")
    for game in manifest["games"]:
        assert_source_allowed(game["source_key"], game["source_item_id"])
        if (
            game["source_key"] != "19x19"
            or game["origin_path"] != f"data/kifu-album/19x19/{game['source_item_id']}.sgf"
        ):
            raise ValueError("only numeric 19x19 source paths are allowed")
    return digest


def _receive_payload():
    stream = getattr(sys.stdin, "buffer", sys.stdin)
    data = stream.read(MAX_RECEIVE_BYTES + 1)
    if len(data) > MAX_RECEIVE_BYTES:
        raise ValueError("receiver payload exceeds limit")
    payload = json.loads(data)
    if not isinstance(payload, dict):
        raise ValueError("receiver payload must be an object")
    return payload


async def derive_staged_record(item):
    """Read one staged SGF and isolate its metadata before batch name work."""
    source_id = item["external_id"]
    assert_source_allowed("19x19", source_id)
    path = Path(item["raw_sgf_path"])
    raw = await asyncio.to_thread(path.read_bytes)
    raw_hash = sha256(raw).hexdigest()
    if raw_hash != item["raw_sha256"]:
        raise ValueError("staged SGF changed since download")
    root = SGF.parse_sgf(raw.decode("utf-8"))
    content = root.sgf()
    content_hash = sha256(content.encode("utf-8")).hexdigest()
    metadata = derive_metadata(content, item.get("metadata"))
    return {
        "source_key": "19x19",
        "source_item_id": source_id,
        "origin_path": f"data/kifu-album/19x19/{source_id}.sgf",
        "raw_sha256": raw_hash,
        "sgf_content": content,
        "sgf_sha256": content_hash,
        "metadata": metadata,
        "source_metadata": item.get("metadata"),
        "identities": {},
    }


async def isolate_unportable_identities(games, resolved, check_identities, isolated):
    """Check exact canonical instructions before selecting or paying for names."""
    instructions, members, needs_qualification = [], [], []
    positions = {}
    for game in games:
        for slot in ("black", "white", "event"):
            kind = "event" if slot == "event" else "player"
            raw = game["metadata"]["event" if slot == "event" else f"player_{slot}"]
            match = resolved[kind].get(raw, {})
            if match.get("status") not in {"qualified", "missing_qualified_five_languages"}:
                continue
            key = kind, raw, match["canonical_name"]
            if key not in positions:
                positions[key] = len(instructions)
                instructions.append(
                    {
                        **dict(zip(("kind", "raw", "canonical_name"), key)),
                        "name_decision": match["status"] != "qualified",
                    }
                )
                members.append(set())
                needs_qualification.append(match["status"] == "qualified")
            members[positions[key]].add(game["source_item_id"])
    if not instructions:
        return set()
    request = {"operation": "check-identities", "game_count": len(games), "instructions": instructions}
    validate_identity_check_request(request)
    if check_identities is None:
        raise IdentityCheckUnavailable("production identity check unavailable")
    try:
        response = (
            await check_identities(request)
            if inspect.iscoroutinefunction(check_identities)
            else await asyncio.to_thread(check_identities, request)
        )
        validate_identity_check_response(request, response)
    except (OSError, ValueError, TypeError):
        raise IdentityCheckUnavailable("production identity check unavailable") from None
    excluded = set()
    for index, status in enumerate(response["results"]):
        if status == "qualified" or status == "missing_qualified_five_languages" and not needs_qualification[index]:
            continue
        for source_id in sorted(members[index] - excluded):
            isolated.append((source_id, f"production {instructions[index]['kind']} identity {status}"))
            excluded.add(source_id)
    return excluded


def _professional_identity_evidence(engine, player_ids):
    if not player_ids:
        return {}
    with engine.connect() as conn:
        return lookup_professional_identity_evidence(conn, player_ids)


async def _freeze_ranks(games, resolved, decision_store):
    """Read immutable per-game checkpoints before consulting today's profiles."""
    decisions, pending, requested = {}, [], {}
    for game in games:
        decision = (
            await asyncio.to_thread(decision_store.load_rank_decision, game) if decision_store is not None else None
        )
        if decision is None:
            pending.append(game)
            for side in ("black", "white"):
                match = resolved["player"].get(game["metadata"][f"player_{side}"], {})
                if (
                    match.get("status") in {"qualified", "missing_qualified_five_languages"}
                    and type(match.get("id")) is int
                ):
                    requested[match["id"]] = match
        else:
            decisions[game["source_item_id"]] = decision
    return decisions, pending, requested


async def prepare_staged_games(
    items, *, engine, client, names, isolated=None, check_identities=None, decision_store=None
):
    """Freeze at most 100 staged games; review each distinct missing name once."""
    if not items or len(items) > 100:
        raise ValueError("staged batch must contain 1 to 100 games")
    games = [await derive_staged_record(item) for item in items]
    players = {game["metadata"][f"player_{slot}"] for game in games for slot in ("black", "white")}
    events = {game["metadata"]["event"] for game in games}
    resolved = await asyncio.to_thread(
        lookup_qualified_identities,
        engine,
        player_values=players,
        event_values=events,
    )
    isolated = isolated if isolated is not None else []
    excluded = await isolate_unportable_identities(games, resolved, check_identities, isolated)
    pending = {}
    for game in games:
        if game["source_item_id"] in excluded:
            continue
        game_pending = {}
        ambiguous = None
        for slot in ("black", "white", "event"):
            kind = "event" if slot == "event" else "player"
            raw_name = game["metadata"]["event" if slot == "event" else f"player_{slot}"]
            match = resolved[kind].get(raw_name, {"status": "unresolved"})
            if match["status"] == "ambiguous":
                ambiguous = f"ambiguous {kind} identity requires review"
                break
            if match["status"] == "qualified":
                game["identities"][slot] = {"canonical_name": match["canonical_name"]}
                continue
            if match["status"] == "missing_qualified_five_languages":
                decision_kind, key = kind, match["canonical_name"]
                game["identities"][slot] = {"canonical_name": key}
            else:
                decision_kind, key = f"raw_{kind}", raw_name
                game["identities"][slot] = None
            member = {
                "source_key": "19x19",
                "source_item_id": game["source_item_id"],
                "slot": slot,
                "sgf_sha256": game["sgf_sha256"],
            }
            game_pending.setdefault((decision_kind, key), []).append(member)
        if ambiguous:
            excluded.add(game["source_item_id"])
            isolated.append((game["source_item_id"], ambiguous))
            continue
        for name_key, members in game_pending.items():
            pending.setdefault(name_key, []).extend(members)
    # Freeze source observations and fallbacks before any paid name calls.
    rank_games = [game for game in games if game["source_item_id"] not in excluded]
    rank_decisions, unfrozen, requested = await _freeze_ranks(rank_games, resolved, decision_store)
    library = await asyncio.to_thread(lookup_library_rank_facts, engine, list(requested.values())) if requested else {}
    identity_proofs = await asyncio.to_thread(_professional_identity_evidence, engine, list(requested))
    portable_facts = {
        requested[player_id]["canonical_name"]: result["fact"]
        for player_id, result in library.items()
        if player_id in requested
        and isinstance(result, dict)
        and result.get("status") == "qualified"
        and isinstance(result.get("fact"), dict)
    }
    portable_proofs = {
        requested[player_id]["canonical_name"]: proof
        for player_id, proof in identity_proofs.items()
        if player_id in requested
    }
    for game in unfrozen:
        decision = freeze_game_ranks(game, library_facts=portable_facts, identity_evidence=portable_proofs)
        if decision_store is not None:
            await asyncio.to_thread(decision_store.save_rank_decision, game, decision)
        rank_decisions[game["source_item_id"]] = decision
    rank_facts = merge_rank_facts(*(rank_decisions[game["source_item_id"]]["rank_facts"] for game in rank_games))
    for game in rank_games:
        decision = rank_decisions[game["source_item_id"]]
        game.update({key: decision[key] for key in ("rank_snapshots", "rank_observations")})
    rank_counts = {
        key: 0
        for key in ("cached", "source", "library_current", "unknown", "unknown_identity", "unknown_system", "conflict")
    }
    rank_counts["cached"] = 2 * (len(rank_games) - len(unfrozen))
    lookup_reasons, lookup_failures = {}, {}
    for player_id, result in library.items():
        if isinstance(result, dict) and result.get("status") in {"unknown_identity", "unknown_system", "conflict"}:
            rank_counts[result["status"]] += 1
            reason = result.get("reason")
            if not isinstance(reason, str) or reason not in _RANK_LOOKUP_REASONS:
                reason = "lookup_reason_unavailable"
            lookup_reasons[reason] = lookup_reasons.get(reason, 0) + 1
            lookup_failures[player_id] = reason
    ages, unresolved_slots = [], []
    unfrozen_ids = {game["source_item_id"] for game in unfrozen}
    for game in rank_games:
        for side, snapshot in game["rank_snapshots"].items():
            rank_counts[snapshot["origin"]] += 1
            if snapshot["source_as_of"]:
                ages.append((datetime.now(timezone.utc).date() - date.fromisoformat(snapshot["source_as_of"])).days)
            if snapshot["origin"] != "unknown" or len(unresolved_slots) >= 200:
                continue
            # A frozen unknown is historical, even if a new game queried this owner.
            reason = "frozen_unknown"
            if game["source_item_id"] in unfrozen_ids:
                match = resolved["player"].get(game["metadata"][f"player_{side}"], {})
                reason = "identity_not_unique"
                if (
                    match.get("status") in {"qualified", "missing_qualified_five_languages"}
                    and type(match.get("id")) is int
                ):
                    reason = lookup_failures.get(match["id"], "rank_fact_unavailable")
            unresolved_slots.append({"source_item_id": game["source_item_id"], "side": side, "reason": reason})
    logger.info(
        "kifu_rank_decisions %s",
        json.dumps(
            {
                **rank_counts,
                "lookup_reasons": lookup_reasons,
                "unresolved_slots": unresolved_slots,
                "profile_refresh_deferred": True,
                "external_rank_refreshes": 0,
                "source_age_days_min": min(ages) if ages else None,
                "source_age_days_max": max(ages) if ages else None,
            },
            sort_keys=True,
        ),
    )
    preflight_manifest_budget({"format": FORMAT_V2, "games": rank_games, "rank_facts": rank_facts, "decisions": []})
    decisions = []
    raw_event_keys = {key for kind, key in pending if kind == "raw_event"}
    reusable_events = {"templates": {}}
    if raw_event_keys:
        reusable_events = await asyncio.to_thread(qualified_raw_event_templates, engine, raw_values=raw_event_keys)
        for key in reusable_events["templates"]:
            pending.pop(("raw_event", key), None)
    raw_player_keys = {key for kind, key in pending if kind == "raw_player"}
    templates = (
        await asyncio.to_thread(qualified_raw_player_templates, engine, raw_values=raw_player_keys)
        if raw_player_keys
        else {"templates": {}}
    )
    # Frozen native proofs cannot extend to these new occurrences. Isolate all
    # their games before any name work, including other names shared with them.
    for kind, result in (("raw_event", reusable_events), ("raw_player", templates)):
        for key, reason in result.get("unavailable", {}).items():
            if reason != "no_native_generated_scope_refresh":
                continue
            for member in pending.get((kind, key), ()):
                source_id = member["source_item_id"]
                if source_id not in excluded:
                    excluded.add(source_id)
                    isolated.append((source_id, f"{kind} {key!r}: {reason}"))
    for name_key in list(pending):
        pending[name_key] = [member for member in pending[name_key] if member["source_item_id"] not in excluded]
        if not pending[name_key]:
            del pending[name_key]
    requests = {}
    for (kind, key), members in pending.items():
        members = [member for member in members if member["source_item_id"] not in excluded]
        if not members:
            continue
        template = templates["templates"].get(key) if kind == "raw_player" else None
        context = (
            {f"verified_reuse_{field}": template[field] for field in ("displays", "original_language", "methods")}
            if template
            else None
        )
        request = {
            "kind": kind,
            "key": key,
            "source_items": members,
            "context": context,
            "template_sources": template["sources"] if template else [],
        }
        requests[kind, key] = request
        decision = (
            await asyncio.to_thread(decision_store.load_name_decision, request) if decision_store is not None else None
        )
        if decision is not None:
            # Preserve the original evidence snapshot and both real request IDs.
            # A cache hit still passes today's text rules and fresh native gates.
            candidate = {field: decision[field] for field in ("displays", "methods", "original_language")}
            candidate["source_urls"] = [source["url"] for source in decision["sources"]]
            if "cn_conversion_note" in decision:
                candidate["cn_conversion_note"] = decision["cn_conversion_note"]
            try:
                validate_decision(decision)
                QwenNameService._candidate(candidate, kind, key, decision["sources"], context=context)
            except (ValueError, NameRejected) as exc:
                raise ValueError("approved name checkpoint fails current validation") from exc
            decisions.append(decision)
            continue
        if names is None or not getattr(names, "key", None):
            raise NeedsCredentials("needs_credentials: five-language name review is not enabled")
        evidence = []
        if kind in {"player", "raw_player"}:
            evidence = (await wiki_sources(key, client))["sources"]
        if template:
            evidence.extend(template["sources"])
        try:
            decision = await names.translate_and_review(
                kind,
                key,
                members,
                sources=evidence,
                context=context,
            )
            if template and any(
                decision[field] != template[field] for field in ("displays", "original_language", "methods")
            ):
                raise NameRejected("reviewed raw player meaning differs from qualified reusable text")
            if decision_store is not None:
                validate_decision(decision)
                await asyncio.to_thread(decision_store.save_name_decision, request, decision)
            decisions.append(decision)
        except NameRejected as exc:
            for source_id in {member["source_item_id"] for member in members}:
                excluded.add(source_id)
                isolated.append((source_id, str(exc)))
    # A valid review signs its exact finite source_items. Re-review only decisions
    # whose scope was narrowed after another name failed; never copy its signature.
    index = 0
    while index < len(decisions):
        decision = decisions[index]
        members = [member for member in decision["source_items"] if member["source_item_id"] not in excluded]
        if not members:
            decisions.pop(index)
            continue
        if len(members) != len(decision["source_items"]):
            try:
                decisions[index] = await names.review_existing_decision(decision, members)
                if decision_store is not None:
                    request = {**requests[decision["kind"], decision["key"]], "source_items": members}
                    validate_decision(decisions[index])
                    await asyncio.to_thread(decision_store.save_name_decision, request, decisions[index])
            except NameRejected as exc:
                for source_id in {member["source_item_id"] for member in members}:
                    excluded.add(source_id)
                    isolated.append((source_id, str(exc)))
                decisions.pop(index)
                index = 0
                continue
        index += 1
    games = [game for game in games if game["source_item_id"] not in excluded]
    if not games:
        raise NameRejected("all staged games require isolated name review")
    manifest = {
        "format": FORMAT_V2,
        "publication_key": (
            f"19x19-{games[0]['source_item_id']}-{games[0]['raw_sha256'][:16]}"
            if len(games) == 1
            else f"19x19-batch-{canonical_sha256([(game['source_item_id'], game['raw_sha256']) for game in games])[:24]}"
        ),
        "games": games,
        "decisions": decisions,
        "rank_facts": {
            digest: fact
            for digest, fact in rank_facts.items()
            if any(
                digest
                in (
                    *game["rank_observations"].values(),
                    *(snap["rank_fact_sha256"] for snap in game["rank_snapshots"].values()),
                )
                for game in games
            )
        },
    }
    _validated(manifest)
    return manifest


async def prepare_staged_game(item, *, engine, client, names, check_identities=None):
    return await prepare_staged_games(
        [item], engine=engine, client=client, names=names, check_identities=check_identities
    )


def main(argv=None):
    parser = argparse.ArgumentParser(prog="kifu_incremental")
    commands = parser.add_subparsers(dest="command", required=True)
    inventory = commands.add_parser("inventory")
    inventory.add_argument("--source-dir", required=True)
    inventory.add_argument("--after", default="2026-01-30")
    inventory.add_argument("--known-paths", help="JSON array of already imported source paths")
    inventory.add_argument("--excluded-ids", help="JSON array of excluded numeric IDs")
    prepare = commands.add_parser("prepare")
    prepare.add_argument("--games", required=True, help="JSON array of prepared games")
    prepare.add_argument("--decisions", required=True, help="JSON array of independently reviewed decisions")
    prepare.add_argument("--publication-key", required=True)
    prepare.add_argument("--output", required=True)
    run = commands.add_parser("run-once")
    run.add_argument("--manifest", required=True)
    mode = run.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    commands.add_parser("receive")
    commands.add_parser("status")
    args = parser.parse_args(argv)
    try:
        if args.command == "inventory":
            summary = scan_inventory(
                args.source_dir,
                after=args.after,
                known_source_paths=_read_json(args.known_paths) if args.known_paths else (),
                excluded_source_ids=historical_excluded_ids().union(
                    _read_json(args.excluded_ids) if args.excluded_ids else ()
                ),
                on_entry=lambda item: _output({"type": "entry", **asdict(item)}),
            )
            _output({"type": "summary", **asdict(summary)})
        elif args.command == "prepare":
            manifest = {
                "format": FORMAT,
                "publication_key": args.publication_key,
                "games": _read_json(args.games),
                "decisions": _read_json(args.decisions),
            }
            digest = _validated(manifest)
            target = Path(args.output)
            if target.exists():
                raise ValueError("manifest output already exists")
            target.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
            _output({"status": "prepared", "manifest_sha256": digest, "path": str(target)})
        elif args.command == "run-once":
            manifest = _read_json(args.manifest)
            digest = _validated(manifest)
            if args.dry_run:
                _output({"status": "validated", "manifest_sha256": digest, "games": len(manifest["games"])})
            else:
                receipt = publish_manifest(_engine(), manifest, expected_manifest_sha256=digest)
                _output({"status": "applied", "manifest_sha256": digest, "receipt": receipt})
        elif args.command == "receive":
            payload = _receive_payload()
            if payload.get("operation") == "check-identities":
                try:
                    validate_identity_check_request(payload)
                    result = check_identity_instructions(_engine(), payload)
                except Exception:
                    _output({"status": "error", "error": "identity check unavailable"})
                    return 2
                _output(result)
                return 0
            if "operation" in payload:
                raise ValueError("receiver operation invalid")
            manifest = payload.get("manifest")
            expected = payload.get("manifest_sha256")
            digest = _validated(manifest, expected)
            if expected != digest:
                raise ValueError("manifest hash mismatch")
            validate_test_verification(manifest, digest, payload.get("test_verification"))
            receipt = publish_manifest(_engine(), manifest, expected_manifest_sha256=digest)
            _output({"status": "applied", "manifest_sha256": digest, "receipt": receipt})
        else:
            _output({"status": "ok", **StateStore(_engine()).snapshot_status()})
        return 0
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
        _output({"status": "error", "error": str(exc)})
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
