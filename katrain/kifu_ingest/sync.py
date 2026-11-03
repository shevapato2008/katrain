"""Fixed SSH transport and actual five-language album API verification."""

from __future__ import annotations

import asyncio
from collections import Counter
from copy import deepcopy
from hashlib import sha256
import inspect
import json
import math
import os
from pathlib import Path
import re
import selectors
import subprocess
import time

from katrain.core.sgf_parser import SGF
from katrain.kifu_ingest.catalog import validate_identity_check_request, validate_identity_check_response
from katrain.kifu_ingest.exclusions import assert_source_allowed
from katrain.kifu_ingest.ranks import (
    FORMAT_V2,
    display_rank_for_game_slot,
    validate_manifest_ranks,
    validate_rank_outcomes,
    expected_rank_for_outcome,
    is_historical_snapshot,
)
from katrain.kifu_ingest.verification import AlbumCheckpoint, RANK_ALGORITHM_VERSION, VerificationGET, normalized_target
from katrain.web.kifu.name_candidates import canonical_sha256
from katrain.web.kifu.name_parse import parse_player


LANGUAGES = ("cn", "tw", "jp", "ko", "en")
_MAX_VERIFICATION_BYTES = 4 * 1024 * 1024
_MAX_RECEIVER_BYTES = 16 * 1024 * 1024
_MAX_RANK_CONTEXT_BYTES = 1024 * 1024
CURRENT_RANK_ALGORITHM = "kifu-current-rank-verification-v1"
_CONTEXT_VERSION = "kifu-rank-publication-context-v1"
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_SAFE_RECEIVER_ERRORS = frozenset(
    {
        "invalid research: incremental research differs from reviewed text or sources",
        "invalid research: retained original differs from output",
        "invalid research: incremental renewal must preserve a pinned prior display",
        "invalid research: raw player needs readable literal and signed finite scope",
        "reviewed text conflicts with an existing qualified name",
        "raw-player scope renewal needs qualified native prior proof",
        "decision cannot replace an unqualified evidence-backed name",
        "incoming name decisions have conflicting displays",
        "first pass cannot replace verified or evidence-backed name",
        "generated raw-player scope refresh original source meaning differs",
        "generated raw scope refresh source meaning changed",
        "publication key already names a different manifest",
    }
)


def _safe_receiver_error(stdout):
    """Return known native guard text only; never forward arbitrary remote output."""
    if not isinstance(stdout, str) or len(stdout) > 65536:
        return None
    try:
        response = json.loads(stdout)
    except (ValueError, TypeError):
        return None
    if not isinstance(response, dict) or response.get("status") != "error":
        return None
    error = response.get("error")
    if not isinstance(error, str):
        return None
    if error in _SAFE_RECEIVER_ERRORS:
        return error
    collision = re.match(r"(first-pass|cross-bundle) normalized name collision: (cn|tw|jp|ko|en):", error)
    if collision:
        # Names and all other dynamic suffixes remain private, even if an
        # unexpected remote exception appends credentials or a traceback.
        return f"{collision[1]} normalized name collision: {collision[2]} (name omitted)"
    return None


def validate_test_verification(manifest, digest, verification):
    if (
        not isinstance(verification, dict)
        or verification.get("status") != "verified"
        or verification.get("manifest_sha256") != digest
    ):
        raise ValueError("test verification is required before production sync")
    if (
        any(
            key in verification
            for key in (
                "rank_publication_context",
                "rank_context_sha256",
                "database_identity",
            )
        )
        or verification.get("algorithm") == CURRENT_RANK_ALGORITHM
    ):
        raise ValueError("current rank supplement cannot replace original test verification")
    if isinstance(manifest, dict) and manifest.get("format") == FORMAT_V2:
        return _validate_rank_report(manifest, digest, verification)
    games = manifest.get("games", []) if isinstance(manifest, dict) else []
    checks = verification.get("checks")
    if verification.get("games") != len(games) or not isinstance(checks, list) or len(checks) != 5 * len(games):
        raise ValueError("test five-language verification is incomplete")
    languages = {lang: Counter() for lang in LANGUAGES}
    for check in checks:
        if (
            not isinstance(check, dict)
            or check.get("lang") not in languages
            or not isinstance(check.get("album_id"), int)
        ):
            raise ValueError("test five-language verification is invalid")
        languages[check["lang"]][check["album_id"]] += 1
    if (
        any(sum(counts.values()) != len(games) for counts in languages.values())
        or len({tuple(sorted(counts.items())) for counts in languages.values()}) != 1
    ):
        raise ValueError("test five-language verification is incomplete")


def _receiver_command(host, key_path, known_hosts):
    if not host or not re.fullmatch(r"[A-Za-z0-9_.@-]+", host):
        raise ValueError("invalid SSH host")
    if not Path(key_path).is_absolute() or not Path(known_hosts).is_absolute():
        raise ValueError("SSH key and known_hosts paths must be absolute")
    return [
        "ssh",
        "-o",
        "BatchMode=yes",
        "-o",
        "ServerAliveInterval=30",
        "-o",
        "ServerAliveCountMax=6",
        "-o",
        "StrictHostKeyChecking=yes",
        "-o",
        f"UserKnownHostsFile={known_hosts}",
        "-i",
        str(key_path),
        "--",
        host,
        "kifu-incremental-receive",
    ]


class IdentityCheckUnavailable(RuntimeError):
    """Defer preparation rather than selecting TEST-only canonical identities."""


class RankPublicationContextUnavailable(RuntimeError):
    """The fixed authenticated read did not yield bounded current authority."""


def _json_bytes(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _validate_context_schema(context, manifest_sha256, receipt_sha256):
    """Validate wire bytes and bindings; this does not establish DB authority."""
    fields = {
        "version",
        "manifest_sha256",
        "receipt_sha256",
        "database_identity",
        "source_mapping_sha256",
        "slots",
        "content_sha256",
    }
    if (
        not isinstance(context, dict)
        or set(context) != fields
        or len(_json_bytes(context)) > _MAX_RANK_CONTEXT_BYTES
        or context["version"] != _CONTEXT_VERSION
        or context["manifest_sha256"] != manifest_sha256
        or context["receipt_sha256"] != receipt_sha256
        or any(
            not isinstance(context[k], str) or not _SHA.fullmatch(context[k])
            for k in ("manifest_sha256", "receipt_sha256", "source_mapping_sha256", "content_sha256")
        )
        or context["content_sha256"] != canonical_sha256({k: v for k, v in context.items() if k != "content_sha256"})
        or not isinstance(context["slots"], list)
        or len(context["slots"]) > 200
    ):
        raise ValueError("rank publication context is invalid")
    database = context["database_identity"]
    if not isinstance(database, dict):
        raise ValueError("rank publication context database is invalid")
    if database.get("dialect") == "sqlite":
        valid_database = (
            set(database) == {"dialect", "database_sha256"}
            and isinstance(database["database_sha256"], str)
            and _SHA.fullmatch(database["database_sha256"])
        )
    else:
        valid_database = (
            set(database) == {"dialect", "database", "schema", "database_oid", "server_sha256"}
            and database.get("dialect") == "postgresql"
            and all(isinstance(database[k], str) and 0 < len(database[k]) <= 256 for k in ("database", "schema"))
            and type(database["database_oid"]) is int
            and database["database_oid"] > 0
            and isinstance(database["server_sha256"], str)
            and _SHA.fullmatch(database["server_sha256"])
        )
    if not valid_database:
        raise ValueError("rank publication context database is invalid")
    slot_fields = {
        "source_key",
        "source_item_id",
        "album_id",
        "side",
        "snapshot_id",
        "original_snapshot_sha256",
        "current_snapshot_sha256",
        "repair_part_sha256",
        "repair_batch_id",
        "predecessor_after_sha256",
        "successor_before_sha256",
        "successor_after_sha256",
        "expected",
    }
    seen = set()
    for slot in context["slots"]:
        if (
            not isinstance(slot, dict)
            or set(slot) != slot_fields
            or any(
                not isinstance(slot[k], str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", slot[k])
                for k in ("source_key", "source_item_id")
            )
            or slot["side"] not in ("black", "white")
            or any(type(slot[k]) is not int or slot[k] <= 0 for k in ("album_id", "snapshot_id", "repair_batch_id"))
            or any(
                not isinstance(slot[k], str) or not _SHA.fullmatch(slot[k])
                for k in slot_fields
                if k.endswith("_sha256")
            )
            or slot["original_snapshot_sha256"] == slot["current_snapshot_sha256"]
            or slot["predecessor_after_sha256"] != slot["successor_before_sha256"]
        ):
            raise ValueError("rank publication context slot is invalid")
        key = slot["source_key"], slot["source_item_id"], slot["side"]
        if key in seen:
            raise ValueError("rank publication context slot is duplicated")
        seen.add(key)
        expected = slot["expected"]
        if (
            not isinstance(expected, dict)
            or set(expected) != {"rank", "rank_origin", "rank_source"}
            or not isinstance(expected["rank"], str)
            or len(expected["rank"]) > 128
            or expected["rank_origin"] not in ("source", "historical_type", "historical_prior", "unknown")
        ):
            raise ValueError("rank publication context expectation is invalid")
        source = expected["rank_source"]
        if (
            not isinstance(source, dict)
            or set(source)
            != {
                "policy_version",
                "snapshot_sha256",
                "rank_system",
                "origin",
                "source_ref",
                "source_as_of",
                "refusal_reason",
            }
            or source["policy_version"] != "historical-rank-as-of-v1"
            or source["snapshot_sha256"] != slot["current_snapshot_sha256"]
            or source["origin"] != expected["rank_origin"]
            or source["rank_system"] not in (None, "professional_dan", "amateur_dan", "kyu", "dan_unspecified")
            or source["source_as_of"] is not None
            and (
                not isinstance(source["source_as_of"], str)
                or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", source["source_as_of"])
            )
            or source["refusal_reason"] is not None
            and (not isinstance(source["refusal_reason"], str) or not 0 < len(source["refusal_reason"]) <= 64)
        ):
            raise ValueError("rank publication context provenance is invalid")
        ref = source["source_ref"]
        if (
            not isinstance(ref, dict)
            or set(ref) != {"source_key", "origin_path", "sgf_sha256", "slot"}
            or ref["source_key"] != slot["source_key"]
            or ref["slot"] != slot["side"]
            or not isinstance(ref["origin_path"], str)
            or not 0 < len(ref["origin_path"]) <= 1024
            or not isinstance(ref["sgf_sha256"], str)
            or not _SHA.fullmatch(ref["sgf_sha256"])
        ):
            raise ValueError("rank publication context source is invalid")
    return context


def _bound_current_ranks(manifest, receipt, context):
    _validate_context_schema(context, canonical_sha256(manifest), canonical_sha256(receipt))
    games = {(g["source_key"], g["source_item_id"]): g for g in manifest["games"]}
    mappings = receipt.get("games")
    if not isinstance(mappings, list) or len(mappings) != len(games):
        raise ValueError("rank publication context receipt membership is invalid")
    ids = {}
    for row in mappings:
        if (
            not isinstance(row, dict)
            or not {"source_key", "source_item_id", "album_id"} <= row.keys()
            or not isinstance(row["source_key"], str)
            or not isinstance(row["source_item_id"], str)
            or type(row["album_id"]) is not int
            or row["album_id"] <= 0
        ):
            raise ValueError("rank publication context receipt mapping is invalid")
        key = row["source_key"], row["source_item_id"]
        if key not in games or key in ids:
            raise ValueError("rank publication context receipt membership is invalid")
        ids[key] = row["album_id"]
    mapping = sorted(
        ({"source_key": key[0], "source_item_id": key[1], "album_id": value} for key, value in ids.items()),
        key=lambda row: (row["source_key"], row["source_item_id"], row["album_id"]),
    )
    if context["source_mapping_sha256"] != canonical_sha256(mapping):
        raise ValueError("rank publication context source mapping changed")
    current = {}
    for slot in context["slots"]:
        key = slot["source_key"], slot["source_item_id"]
        game = games.get(key)
        snapshot = game["rank_snapshots"][slot["side"]] if game else None
        if (
            game is None
            or ids[key] != slot["album_id"]
            or is_historical_snapshot(snapshot)
            or snapshot["content_sha256"] != slot["original_snapshot_sha256"]
            or slot["expected"]["rank_source"]["source_ref"]["sgf_sha256"] != game["sgf_sha256"]
            or slot["expected"]["rank_source"]["source_ref"]["origin_path"]
            != game.get("origin_path", f"data/kifu-album/{key[0]}/{key[1]}.sgf")
        ):
            raise ValueError("rank publication context original slot binding changed")
        current[(*key, slot["side"])] = slot["expected"]
    return current


def _read_rank_context_bytes(command, payload, timeout):
    """Read at most the response ceiling, killing SSH on overflow or timeout."""
    deadline = time.monotonic() + timeout
    with subprocess.Popen(
        command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=0
    ) as process:
        try:
            with process.stdin:
                process.stdin.write(payload)
            chunks, size = [], 0
            with selectors.DefaultSelector() as selector:
                selector.register(process.stdout, selectors.EVENT_READ)
                while True:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0 or not selector.select(remaining):
                        raise subprocess.TimeoutExpired(command, timeout)
                    chunk = os.read(process.stdout.fileno(), min(65536, _MAX_RANK_CONTEXT_BYTES + 1 - size))
                    if not chunk:
                        break
                    size += len(chunk)
                    if size > _MAX_RANK_CONTEXT_BYTES:
                        raise ValueError("rank publication context response exceeds budget")
                    chunks.append(chunk)
            if process.wait(timeout=max(0, deadline - time.monotonic())):
                raise ValueError("rank publication context read failed")
            return b"".join(chunks)
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()


def read_rank_publication_context(*, host, key_path, known_hosts, manifest_sha256, receipt_sha256, timeout=30):
    """Resolve one exact publication through the existing authenticated receiver.

    This is a read operation only. A failed read never falls back to sending a
    publication, and arbitrary remote output is not forwarded to the caller.
    """
    try:
        if (
            any(not isinstance(value, str) or not _SHA.fullmatch(value) for value in (manifest_sha256, receipt_sha256))
            or type(timeout) not in (int, float)
            or not math.isfinite(timeout)
            or timeout <= 0
        ):
            raise ValueError("invalid rank publication context request")
        payload = _json_bytes(
            {
                "operation": "read-rank-publication-context-v1",
                "manifest_sha256": manifest_sha256,
                "receipt_sha256": receipt_sha256,
            }
        )
        if len(payload) > 1024:
            raise ValueError("rank publication context request exceeds budget")
        raw = _read_rank_context_bytes(_receiver_command(host, key_path, known_hosts), payload, min(30, timeout))
        response = json.loads(raw.decode("utf-8"))
        if not isinstance(response, dict) or set(response) != {"status", "context"} or response["status"] != "resolved":
            raise ValueError("rank publication context response is invalid")
        return _validate_context_schema(response["context"], manifest_sha256, receipt_sha256)
    except (OSError, subprocess.SubprocessError, ValueError, TypeError, KeyError, UnicodeError):
        raise RankPublicationContextUnavailable("rank publication context unavailable") from None


def check_production_identities(request, *, host, key_path, known_hosts, timeout=180):
    validate_identity_check_request(request)
    try:
        process = subprocess.run(
            _receiver_command(host, key_path, known_hosts),
            input=json.dumps(request, ensure_ascii=False, separators=(",", ":")),
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
        if process.returncode or len(process.stdout) > 65536:
            raise ValueError("identity check transport failed")
        response = json.loads(process.stdout)
        return validate_identity_check_response(request, response)
    except (OSError, subprocess.SubprocessError, ValueError, TypeError):
        raise IdentityCheckUnavailable("production identity check unavailable") from None


def send_verified_manifest(manifest, manifest_sha256, test_verification, *, host, key_path, known_hosts, timeout=None):
    """Wait for a native receipt; transport cancellation cannot stop its writer.

    Publication admission has a cooperative round budget. SSH keepalives still
    detect connection loss; the remote publication guard prevents a second
    receiver from warming/publishing while a disconnected writer finishes.
    """
    validate_test_verification(manifest, manifest_sha256, test_verification)
    if canonical_sha256(manifest) != manifest_sha256:
        raise ValueError("manifest hash mismatch")
    for game in manifest["games"]:
        assert_source_allowed(game["source_key"], game["source_item_id"])
    command = _receiver_command(host, key_path, known_hosts)
    payload = json.dumps(
        {"manifest": manifest, "manifest_sha256": manifest_sha256, "test_verification": test_verification},
        ensure_ascii=False,
        separators=(",", ":"),
        allow_nan=False,
    )
    if len(payload.encode("utf-8")) > _MAX_RECEIVER_BYTES:
        raise ValueError("manifest and verification exceed receiver payload budget")
    process = subprocess.run(command, input=payload, text=True, capture_output=True, timeout=timeout, check=False)
    if process.returncode == 3:
        from katrain.web.kifu.search_sync import SearchIndexPending

        try:
            pending = json.loads(process.stdout)
            valid = (
                isinstance(pending, dict)
                and pending.get("status") == "search_index_pending"
                and pending.get("operation_ref")
                == {"manifest_sha256": manifest_sha256, "publication_key": manifest["publication_key"]}
            )
        except (ValueError, TypeError):
            valid = False
        if valid:
            raise SearchIndexPending(pending["operation_ref"])
    if process.returncode:
        reason = _safe_receiver_error(process.stdout) if process.returncode == 2 else None
        message = f"receiver exited with status {process.returncode}"
        raise RuntimeError((f"{message}: {reason}" if reason else message)[:384])
    try:
        response = json.loads(process.stdout)
    except (ValueError, TypeError) as exc:
        raise RuntimeError("receiver returned invalid JSON") from exc
    if response.get("status") != "applied" or response.get("manifest_sha256") != manifest_sha256:
        raise RuntimeError("receiver receipt differs from requested manifest")
    return response


_DISPLAY_FIELDS = ("display_player_black", "display_player_white", "display_event")
_ORIGINAL_FIELDS = ("player_black", "player_white", "event")


def _game_outcomes(game, rank_outcomes):
    return {
        side: (rank_outcomes or {}).get((game["source_key"], game["source_item_id"], side))
        for side in ("black", "white")
    }


def _validate_shared_album_mappings(games, mappings, rank_outcomes):
    """Shared IDs require the same original source and actual rank decision."""
    by_source = {(g["source_key"], g["source_item_id"]): g for g in games}
    owners = {}
    for key, album_id in mappings.items():
        previous = owners.setdefault(album_id, key)
        if previous == key:
            continue
        for side in ("black", "white"):
            current = rank_outcomes.get((*key, side))
            prior = rank_outcomes.get((*previous, side))
            if (
                current is None
                or prior is None
                or current["original_source_ref"] != prior["original_source_ref"]
                or current["original_canonical_sgf_sha256"] != prior["original_canonical_sgf_sha256"]
                or expected_rank_for_outcome(by_source[key], side, current)
                != expected_rank_for_outcome(by_source[previous], side, prior)
            ):
                raise ValueError("album shared receipt source coverage is invalid")


def _validate_detail_evidence(
    evidence, game, album_id, lang, decisions, rank_aware=False, *, rank_outcomes=None, current_ranks=None
):
    fields = {"album_id", "lang", "sgf_sha256", "metadata", "source_key", "displays"}
    actual_outcomes = _game_outcomes(game, rank_outcomes)
    has_outcomes = any(actual_outcomes.values())
    if rank_aware:
        fields |= {"source_item_id", "ranks"}
        if has_outcomes:
            fields.add("original_sgf_sha256")
    if (
        not isinstance(evidence, dict)
        or set(evidence) != fields
        or type(evidence["album_id"]) is not int
        or evidence["album_id"] != album_id
        or evidence["lang"] != lang
    ):
        raise ValueError("album API ID or language mismatch")
    canonical_sha = (
        sha256(SGF.parse_sgf(game["sgf_content"]).sgf().encode()).hexdigest() if has_outcomes else game["sgf_sha256"]
    )
    if evidence["sgf_sha256"] != canonical_sha:
        raise ValueError("album API SGF hash mismatch")
    if has_outcomes and any(
        evidence["original_sgf_sha256"] != outcome["original_source_ref"]["sgf_sha256"]
        for outcome in actual_outcomes.values()
        if outcome
    ):
        raise ValueError("album API original SGF SHA differs from retained rank source")
    original_fields = (*_ORIGINAL_FIELDS, "black_rank", "white_rank") if rank_aware else _ORIGINAL_FIELDS
    if not isinstance(evidence["metadata"], dict) or set(evidence["metadata"]) != set(original_fields):
        raise ValueError("album API original metadata is malformed")
    for field in original_fields:
        if evidence["metadata"][field] != game["metadata"].get(field):
            raise ValueError(f"album API {field} mismatch")
    if evidence["source_key"] != game["source_key"]:
        raise ValueError("album API source link missing")
    if rank_aware:
        if evidence["source_item_id"] != game["source_item_id"]:
            raise ValueError("album API rank source item mismatch")
        ranks = evidence["ranks"]
        if not isinstance(ranks, dict) or set(ranks) != {"black", "white"}:
            raise ValueError("album API rank slots are malformed")
        for side in ("black", "white"):
            parsed = parse_player(game["metadata"].get(f"player_{side}"), game["metadata"].get(f"{side}_rank"))
            outcome = actual_outcomes[side]
            expected = (
                expected_rank_for_outcome(game, side, outcome)
                if outcome
                else display_rank_for_game_slot(game["rank_snapshots"][side], parsed.display_rank)
            )
            expected = (current_ranks or {}).get((game["source_key"], game["source_item_id"], side), expected)
            actual = ranks[side]
            if (
                not isinstance(actual, dict)
                or set(actual) != {"display_rank", "origin", "source"}
                or actual["display_rank"] not in (("", None) if expected["rank"] == "" else (expected["rank"],))
                or actual["origin"] != expected["rank_origin"]
                or actual["source"] != expected["rank_source"]
            ):
                raise ValueError(f"album API {side} rank or snapshot provenance mismatch")
    displays = evidence["displays"]
    if not isinstance(displays, dict) or set(displays) != set(_DISPLAY_FIELDS):
        raise ValueError("album API display fields are malformed")
    for field in _DISPLAY_FIELDS:
        if not isinstance(displays[field], str) or not displays[field].strip():
            raise ValueError(f"album API {field} missing for {lang}")
        slot = field.removeprefix("display_").removeprefix("player_")
        raw = game["metadata"]["event" if slot == "event" else f"player_{slot}"]
        identity = game.get("identities", {}).get(slot)
        kind = "event" if slot == "event" else "player"
        decision_key = (kind, identity["canonical_name"]) if isinstance(identity, dict) else (f"raw_{kind}", raw)
        expected = decisions.get(decision_key, {}).get(lang)
        if expected is not None and displays[field] != expected:
            raise ValueError(f"album API {field} mismatch for {lang}")


def _detail_evidence(
    detail,
    game,
    album_id,
    lang,
    decisions,
    rank_aware=False,
    *,
    include_sgf=True,
    rank_outcomes=None,
    current_ranks=None,
    original_sgf_sha256=None,
):
    if not isinstance(detail, dict) or detail.get("id") != album_id:
        raise ValueError("album API ID mismatch")
    if include_sgf:
        try:
            canonical = SGF.parse_sgf(detail["sgf_content"]).sgf()
        except (KeyError, ValueError, TypeError, IndexError, AttributeError) as exc:
            raise ValueError("album API SGF is invalid") from exc
        sgf_sha256 = sha256(canonical.encode("utf-8")).hexdigest()
    else:
        # List responses have no SGF body. Both frozen side references below
        # must independently bind the same hash as the verified detail.
        sgf_sha256 = (
            sha256(SGF.parse_sgf(game["sgf_content"]).sgf().encode()).hexdigest()
            if any(_game_outcomes(game, rank_outcomes).values())
            else game["sgf_sha256"]
        )
    sources = detail.get("sources")
    original_fields = (*_ORIGINAL_FIELDS, "black_rank", "white_rank") if rank_aware else _ORIGINAL_FIELDS
    evidence = {
        "album_id": detail["id"],
        "lang": lang,
        "sgf_sha256": sgf_sha256,
        "metadata": {field: detail.get(field) for field in original_fields},
        "source_key": game["source_key"] if isinstance(sources, list) and game["source_key"] in sources else None,
        "displays": {field: detail.get(field) for field in _DISPLAY_FIELDS},
    }
    if rank_aware:
        if any(_game_outcomes(game, rank_outcomes).values()):
            evidence["original_sgf_sha256"] = (
                sha256(detail["sgf_content"].encode()).hexdigest() if include_sgf else original_sgf_sha256
            )
        rank_fields = {
            field
            for side in ("black", "white")
            for field in (f"{side}_rank", f"display_{side}_rank", f"{side}_rank_origin", f"{side}_rank_source")
        }
        if not rank_fields <= detail.keys():
            raise ValueError("album API rank fields are missing")
        evidence.update(
            source_item_id=game["source_item_id"],
            ranks={
                side: {
                    "display_rank": detail[f"display_{side}_rank"],
                    "origin": detail[f"{side}_rank_origin"],
                    "source": detail[f"{side}_rank_source"],
                }
                for side in ("black", "white")
            },
        )
    _validate_detail_evidence(
        evidence, game, album_id, lang, decisions, rank_aware, rank_outcomes=rank_outcomes, current_ranks=current_ranks
    )
    return evidence


def _validate_display_duplicate(proof, game, album_id, *, stored_sgf_sha256):
    from katrain.web.kifu.catalog_standardization import full_operation_fingerprint

    fields = {
        "version",
        "album_id",
        "canonical_album_id",
        "sgf_sha256",
        "canonical_sgf_sha256",
        "operation_sha256",
        "batch_key",
        "manifest_sha256",
    }
    if (
        not isinstance(proof, dict)
        or set(proof) != fields
        or proof.get("version") != "reviewed-same-game-v1"
        or type(proof.get("album_id")) is not int
        or proof["album_id"] != album_id
        or type(proof.get("canonical_album_id")) is not int
        or proof["canonical_album_id"] <= 0
        or proof["canonical_album_id"] == album_id
        or any(
            not isinstance(proof.get(key), str) or not re.fullmatch(r"[0-9a-f]{64}", proof[key])
            for key in ("sgf_sha256", "canonical_sgf_sha256", "operation_sha256", "manifest_sha256")
        )
        or proof["batch_key"] != "reviewed-same-game:" + proof["manifest_sha256"]
        or proof["sgf_sha256"] != stored_sgf_sha256
        or proof["operation_sha256"] != full_operation_fingerprint(game["sgf_content"])
    ):
        raise ValueError("album display duplicate proof is invalid")
    return proof


def _validate_public_card(
    card, game, album_id, cn_detail, decisions, rank_aware=False, *, rank_outcomes=None, current_ranks=None
):
    fields = {"album_id", "lang", "query", "page", "page_size", "displays"}
    duplicate = isinstance(card, dict) and "display_duplicate" in card
    if duplicate:
        fields |= {"display_duplicate", "canonical_card", "original_sgf_sha256"}
        proof = _validate_display_duplicate(
            card["display_duplicate"], game, album_id, stored_sgf_sha256=card.get("original_sgf_sha256")
        )
        canonical = card.get("canonical_card")
        if (
            not isinstance(canonical, dict)
            or set(canonical) != {"album_id", "sgf_sha256", "displays"}
            or canonical["album_id"] != proof["canonical_album_id"]
            or canonical["sgf_sha256"] != proof["canonical_sgf_sha256"]
            or not isinstance(canonical["displays"], dict)
            or set(canonical["displays"]) != set(_DISPLAY_FIELDS)
            or any(not isinstance(v, str) or not v.strip() for v in canonical["displays"].values())
        ):
            raise ValueError("album display duplicate canonical card is invalid")
    if rank_aware:
        fields |= {"source_key", "source_item_id", "sgf_sha256", "metadata", "ranks"}
        if any(_game_outcomes(game, rank_outcomes).values()):
            fields.add("original_sgf_sha256")
    if (
        not isinstance(card, dict)
        or set(card) != fields
        or type(card["album_id"]) is not int
        or card["album_id"] != album_id
        or card["lang"] != "cn"
        or card["query"] not in (game["metadata"].get("date_played"), game["metadata"]["player_black"])
        or not card["query"]
        or type(card["page"]) is not int
        or not 1 <= card["page"] <= 20
        or type(card["page_size"]) is not int
        or card["page_size"] != 100
        or card["displays"] != cn_detail["displays"]
    ):
        raise ValueError("checkpoint public card is invalid")
    if rank_aware:
        evidence = {
            key: value
            for key, value in card.items()
            if key not in {"query", "page", "page_size", "display_duplicate", "canonical_card"}
            and (key != "original_sgf_sha256" or any(_game_outcomes(game, rank_outcomes).values()))
        }
        _validate_detail_evidence(
            evidence, game, album_id, "cn", decisions, True, rank_outcomes=rank_outcomes, current_ranks=current_ranks
        )
        if evidence != cn_detail:
            raise ValueError("album public list card differs from verified detail")


def _decision_map(manifest):
    return {(row["kind"], row["key"]): row["displays"] for row in manifest.get("decisions", [])}


def _validate_rank_report(manifest, digest, verification, *, current_ranks=None):
    algorithm = CURRENT_RANK_ALGORITHM if current_ranks else RANK_ALGORITHM_VERSION
    if verification.get("algorithm") != algorithm:
        raise ValueError("test rank-aware verification is required")
    if canonical_sha256(manifest) != digest:
        raise ValueError("test rank-aware manifest hash mismatch")
    if (
        len(json.dumps(verification, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8"))
        > _MAX_VERIFICATION_BYTES
    ):
        raise ValueError("test rank-aware verification exceeds report payload budget")
    validate_manifest_ranks(manifest)
    publication_receipt = verification.get("publication_receipt")
    if (
        manifest.get("mode", "publish") == "publish"
        and any(
            is_historical_snapshot(snapshot)
            for game in manifest["games"]
            for snapshot in game["rank_snapshots"].values()
        )
        and publication_receipt is None
    ):
        raise ValueError("test v3 verification requires the actual rank outcome receipt")
    rank_outcomes = {}
    if publication_receipt is not None:
        if (
            not isinstance(publication_receipt, dict)
            or publication_receipt.get("status") != "applied"
            or publication_receipt.get("manifest_sha256") != digest
            or canonical_sha256(publication_receipt) != verification.get("receipt_sha256")
        ):
            raise ValueError("test rank outcome publication receipt changed")
        rank_outcomes = validate_rank_outcomes(manifest, publication_receipt)
        if not rank_outcomes:
            raise ValueError("test rank outcome receipt is empty")
    games = {(game["source_key"], game["source_item_id"]): game for game in manifest["games"]}
    checks, cards, mappings = (
        verification.get("checks"),
        verification.get("public_cards"),
        verification.get("album_mappings"),
    )
    if (
        len(games) != len(manifest["games"])
        or type(verification.get("games")) is not int
        or verification["games"] != len(games)
        or not isinstance(checks, list)
        or len(checks) != len(LANGUAGES) * len(games)
        or not isinstance(cards, list)
        or len(cards) != len(games)
        or not isinstance(mappings, list)
        or len(mappings) != len(games)
        or not isinstance(verification.get("receipt_sha256"), str)
        or not re.fullmatch(r"[0-9a-f]{64}", verification["receipt_sha256"])
    ):
        raise ValueError("test rank-aware finite verification is incomplete")
    decisions, checked, album_ids = _decision_map(manifest), {}, {}
    for mapping in mappings:
        if (
            not isinstance(mapping, dict)
            or set(mapping) != {"source_key", "source_item_id", "album_id"}
            or not isinstance(mapping["source_key"], str)
            or not isinstance(mapping["source_item_id"], str)
            or type(mapping["album_id"]) is not int
            or mapping["album_id"] <= 0
        ):
            raise ValueError("test rank-aware receipt mapping is invalid")
        key = mapping["source_key"], mapping["source_item_id"]
        if key not in games or key in album_ids:
            raise ValueError("test rank-aware receipt mapping coverage is invalid")
        album_ids[key] = mapping["album_id"]
    _validate_shared_album_mappings(list(games.values()), album_ids, rank_outcomes)
    if publication_receipt is not None:
        actual_mappings = {(g["source_key"], g["source_item_id"]): g["album_id"] for g in publication_receipt["games"]}
        if actual_mappings != album_ids or len(actual_mappings) != len(publication_receipt["games"]):
            raise ValueError("test rank outcome receipt membership changed")
    for evidence in checks:
        if (
            not isinstance(evidence, dict)
            or not isinstance(evidence.get("source_key"), str)
            or not isinstance(evidence.get("source_item_id"), str)
            or evidence.get("lang") not in LANGUAGES
            or type(evidence.get("album_id")) is not int
            or evidence["album_id"] <= 0
        ):
            raise ValueError("test rank-aware detail evidence is invalid")
        key = evidence["source_key"], evidence["source_item_id"]
        slot = (*key, evidence["lang"])
        if key not in games or slot in checked or album_ids[key] != evidence["album_id"]:
            raise ValueError("test rank-aware game/language/album coverage is invalid")
        _validate_detail_evidence(
            evidence,
            games[key],
            album_ids[key],
            evidence["lang"],
            decisions,
            True,
            rank_outcomes=rank_outcomes,
            current_ranks=current_ranks,
        )
        checked[slot] = evidence
    if set(checked) != {(*key, lang) for key in games for lang in LANGUAGES}:
        raise ValueError("test rank-aware language coverage is incomplete")
    public = set()
    for card in cards:
        if (
            not isinstance(card, dict)
            or not isinstance(card.get("source_key"), str)
            or not isinstance(card.get("source_item_id"), str)
        ):
            raise ValueError("test rank-aware public card is invalid")
        key = card["source_key"], card["source_item_id"]
        if key not in games or key in public:
            raise ValueError("test rank-aware public coverage is invalid")
        _validate_public_card(
            card,
            games[key],
            album_ids[key],
            checked[(*key, "cn")],
            decisions,
            True,
            rank_outcomes=rank_outcomes,
            current_ranks=current_ranks,
        )
        public.add(key)


def validate_current_rank_verification(manifest, receipt, report, context, target):
    """Validate a supplement against freshly resolved trusted DB context.

    The caller must obtain ``context`` from its internal local/fixed-SSH loader;
    the context embedded in a saved report is never its own authority.
    """
    current_ranks = _bound_current_ranks(manifest, receipt, context)
    fields = {
        "status",
        "algorithm",
        "manifest_sha256",
        "receipt_sha256",
        "target",
        "database_identity",
        "rank_context_sha256",
        "rank_publication_context",
        "games",
        "checks",
        "public_cards",
        "album_mappings",
    }
    if isinstance(report, dict) and "publication_receipt" in report:
        fields.add("publication_receipt")
    mappings = [{k: row[k] for k in ("source_key", "source_item_id", "album_id")} for row in receipt["games"]]
    if (
        not current_ranks
        or not isinstance(report, dict)
        or set(report) != fields
        or report["status"] != "current_rank_verified"
        or report["algorithm"] != CURRENT_RANK_ALGORITHM
        or report["manifest_sha256"] != canonical_sha256(manifest)
        or report["receipt_sha256"] != canonical_sha256(receipt)
        or report["target"] != normalized_target(target)
        or report["database_identity"] != context["database_identity"]
        or report["rank_context_sha256"] != context["content_sha256"]
        or report["rank_publication_context"] != context
        or report["album_mappings"] != mappings
    ):
        raise ValueError("current rank verification context or target binding changed")
    _validate_rank_report(manifest, canonical_sha256(manifest), report, current_ranks=current_ranks)


async def verify_album_api(
    client,
    base_url,
    manifest_or_games,
    receipt,
    *,
    timeout=30,
    deadline=None,
    checkpoint_dir=None,
    rank_context_loader=None,
    clock=time.monotonic,
    wall_clock=time.time,
    sleep=asyncio.sleep,
):
    """Verify all albums, resuming exact-bound complete albums for at most 24h.

    ``deadline`` is absolute monotonic time; each GET also has an independent
    wall-clock cap and inactivity timeout. ``checkpoint_dir`` is an absolute
    local stage directory, held under the caller's staging writer lock. Its
    filenames and bindings are computed here from the complete inputs.
    """
    get = VerificationGET(client, timeout=timeout, deadline=deadline, clock=clock, sleep=sleep)
    get.remaining()
    target = normalized_target(base_url)
    rank_aware = isinstance(manifest_or_games, dict) and manifest_or_games.get("format") == FORMAT_V2
    rank_outcomes = {}
    current_ranks, rank_context = {}, None
    if rank_aware:
        validate_manifest_ranks(manifest_or_games)
        rank_outcomes = validate_rank_outcomes(manifest_or_games, receipt)
        # The compatibility resolver accepts only wholly legacy publications.
        # Mixed cached V1/new V3 requests retain their existing outcome checks.
        if rank_context_loader is not None and all(
            snapshot.get("version") == "kifu-rank-snapshot-v1"
            for game in manifest_or_games["games"]
            for snapshot in game["rank_snapshots"].values()
        ):
            # This callable is installed by trusted orchestration code. No
            # request/report/API field can provide or replace the context.
            if not callable(rank_context_loader):
                raise ValueError("rank publication context loader must be callable")
            context_timeout = min(30, get.remaining())

            async def load_context():
                args = canonical_sha256(manifest_or_games), canonical_sha256(receipt)
                if inspect.iscoroutinefunction(rank_context_loader):
                    loaded = rank_context_loader(*args, timeout=context_timeout)
                else:
                    loaded = await asyncio.to_thread(rank_context_loader, *args, timeout=context_timeout)
                return await loaded if inspect.isawaitable(loaded) else loaded

            rank_context = deepcopy(await asyncio.wait_for(load_context(), timeout=context_timeout))
            get.remaining()
            current_ranks = _bound_current_ranks(manifest_or_games, receipt, rank_context)
    games = manifest_or_games["games"] if isinstance(manifest_or_games, dict) else manifest_or_games
    decisions = _decision_map(manifest_or_games) if isinstance(manifest_or_games, dict) else {}
    mappings = {}
    for row in receipt["games"]:
        key = row["source_key"], row["source_item_id"]
        if key in mappings or type(row["album_id"]) is not int or row["album_id"] <= 0:
            raise ValueError("album receipt mapping is invalid")
        mappings[key] = row["album_id"]
    expected_albums = {}
    for game in games:
        key = game["source_key"], game["source_item_id"]
        checkpoint_key = canonical_sha256(key)
        if checkpoint_key in expected_albums or key not in mappings:
            raise ValueError("album manifest or receipt coverage is invalid")
        expected_albums[checkpoint_key] = (game, mappings[key])
    if rank_aware:
        if len(mappings) != len(expected_albums):
            raise ValueError("album receipt source coverage is invalid")
        _validate_shared_album_mappings(games, mappings, rank_outcomes)

    def validate_completed(key, completed):
        if (
            key not in expected_albums
            or not isinstance(completed, dict)
            or set(completed) != {"source_key", "source_item_id", "album_id", "completed_at", "details", "public_card"}
        ):
            raise ValueError("checkpoint album structure is invalid")
        game, album_id = expected_albums[key]
        if (
            completed["source_key"] != game["source_key"]
            or completed["source_item_id"] != game["source_item_id"]
            or type(completed["album_id"]) is not int
            or completed["album_id"] != album_id
            or not isinstance(completed["details"], list)
            or len(completed["details"]) != len(LANGUAGES)
        ):
            raise ValueError("checkpoint album coverage is invalid")
        for lang, detail in zip(LANGUAGES, completed["details"]):
            _validate_detail_evidence(
                detail,
                game,
                album_id,
                lang,
                decisions,
                rank_aware,
                rank_outcomes=rank_outcomes,
                current_ranks=current_ranks,
            )
        cn_detail = next(detail for detail in completed["details"] if detail["lang"] == "cn")
        _validate_public_card(
            completed["public_card"],
            game,
            album_id,
            cn_detail,
            decisions,
            rank_aware,
            rank_outcomes=rank_outcomes,
            current_ranks=current_ranks,
        )

    checkpoint = AlbumCheckpoint(
        checkpoint_dir,
        manifest_or_games,
        receipt,
        target,
        LANGUAGES,
        validate_completed,
        wall_clock,
        algorithm=(
            CURRENT_RANK_ALGORITHM + ":" + rank_context["content_sha256"]
            if current_ranks
            else RANK_ALGORITHM_VERSION if rank_aware else None
        ),
    )
    checked = []
    public_cards = []
    listings = {}
    for key, (game, album_id) in expected_albums.items():
        get.remaining()
        completed = checkpoint.get(key)
        if completed is None:
            details = []
            duplicate_proof = None
            for lang in LANGUAGES:
                response = await get.get(f"{target}/api/v1/kifu/albums/{album_id}", {"lang": lang})
                if response.status_code != 200:
                    raise ValueError(f"album API {album_id}/{lang} returned {response.status_code}")
                payload = response.json()
                observed = payload.get("display_duplicate")
                if observed is not None:
                    if not isinstance(payload.get("sgf_content"), str):
                        raise ValueError("album original SGF is missing")
                    _validate_display_duplicate(
                        observed, game, album_id, stored_sgf_sha256=sha256(payload["sgf_content"].encode()).hexdigest()
                    )
                if lang == LANGUAGES[0]:
                    duplicate_proof = observed
                elif observed != duplicate_proof:
                    raise ValueError("album display duplicate proof changed between languages")
                details.append(
                    _detail_evidence(
                        payload,
                        game,
                        album_id,
                        lang,
                        decisions,
                        rank_aware,
                        rank_outcomes=rank_outcomes,
                        current_ranks=current_ranks,
                    )
                )
            cn_detail = next(detail for detail in details if detail["lang"] == "cn")
            cn_card = cn_detail["displays"]
            public_album_id = album_id
            canonical_card = None
            if duplicate_proof is not None:
                public_album_id = duplicate_proof["canonical_album_id"]
                response = await get.get(f"{target}/api/v1/kifu/albums/{public_album_id}", {"lang": "cn"})
                canonical_detail = response.json() if response.status_code == 200 else None
                if (
                    not isinstance(canonical_detail, dict)
                    or canonical_detail.get("id") != public_album_id
                    or not isinstance(canonical_detail.get("sgf_content"), str)
                    or sha256(canonical_detail["sgf_content"].encode()).hexdigest()
                    != duplicate_proof["canonical_sgf_sha256"]
                    or canonical_detail.get("display_duplicate") is not None
                ):
                    raise ValueError("album display duplicate canonical detail differs from journal")
                cn_card = {field: canonical_detail.get(field) for field in _DISPLAY_FIELDS}
                canonical_card = {
                    "album_id": public_album_id,
                    "sgf_sha256": duplicate_proof["canonical_sgf_sha256"],
                    "displays": cn_card,
                }
            queries = [game["metadata"].get("date_played"), game["metadata"]["player_black"]]
            public_card = None
            for query in dict.fromkeys(value for value in queries if value):
                for page in range(1, 21):
                    get.remaining()
                    cache_key = target, query, "cn", page, 100
                    if cache_key not in listings:
                        response = await get.get(
                            f"{target}/api/v1/kifu/albums", {"q": query, "lang": "cn", "page": page, "page_size": 100}
                        )
                        if response.status_code != 200:
                            raise ValueError(f"album public list returned {response.status_code}")
                        listing = response.json()
                        if (
                            not isinstance(listing, dict)
                            or not isinstance(listing.get("items"), list)
                            or type(listing.get("total")) is not int
                            or listing["total"] < 0
                            or len(listing["items"]) > min(100, listing["total"])
                            or any(
                                not isinstance(row, dict) or type(row.get("id")) is not int for row in listing["items"]
                            )
                        ):
                            raise ValueError("album public list is malformed")
                        listings[cache_key] = listing
                    listing = listings[cache_key]
                    for row in listing["items"]:
                        if row["id"] == public_album_id:
                            if any(row.get(field) != value for field, value in cn_card.items()):
                                raise ValueError("album public list card differs from verified detail")
                            public_card = {
                                "album_id": album_id,
                                "lang": "cn",
                                "query": query,
                                "page": page,
                                "page_size": 100,
                                "displays": cn_detail["displays"],
                            }
                            if duplicate_proof is not None:
                                public_card.update(
                                    display_duplicate=duplicate_proof,
                                    canonical_card=canonical_card,
                                    original_sgf_sha256=duplicate_proof["sgf_sha256"],
                                )
                            if rank_aware:
                                try:
                                    public_card.update(
                                        cn_detail
                                        if duplicate_proof is not None
                                        else _detail_evidence(
                                            row,
                                            game,
                                            album_id,
                                            "cn",
                                            decisions,
                                            True,
                                            include_sgf=False,
                                            rank_outcomes=rank_outcomes,
                                            current_ranks=current_ranks,
                                            original_sgf_sha256=cn_detail.get("original_sgf_sha256"),
                                        )
                                    )
                                    _validate_public_card(
                                        public_card,
                                        game,
                                        album_id,
                                        cn_detail,
                                        decisions,
                                        True,
                                        rank_outcomes=rank_outcomes,
                                        current_ranks=current_ranks,
                                    )
                                except ValueError as exc:
                                    raise ValueError("album public list card rank or snapshot mismatch") from exc
                            _validate_public_card(
                                public_card,
                                game,
                                album_id,
                                cn_detail,
                                decisions,
                                rank_aware,
                                rank_outcomes=rank_outcomes,
                                current_ranks=current_ranks,
                            )
                            break
                    if public_card is not None or page * 100 >= listing["total"]:
                        break
                if public_card is not None:
                    break
            if public_card is None:
                raise ValueError(f"album {album_id} is absent from the public list")
            get.remaining()
            completed = {
                "source_key": game["source_key"],
                "source_item_id": game["source_item_id"],
                "album_id": album_id,
                "completed_at": wall_clock(),
                "details": details,
                "public_card": public_card,
            }
            checkpoint.save(key, completed)
        if rank_aware:
            checked.extend(completed["details"])
            public_cards.append(completed["public_card"])
        else:
            checked.extend({"album_id": album_id, "lang": detail["lang"]} for detail in completed["details"])
    get.remaining()
    result = {"status": "verified", "games": len(games), "checks": checked}
    if rank_aware:
        result.update(
            algorithm=RANK_ALGORITHM_VERSION,
            public_cards=public_cards,
            receipt_sha256=canonical_sha256(receipt),
            album_mappings=[
                {"source_key": key[0], "source_item_id": key[1], "album_id": album_id}
                for key, album_id in mappings.items()
            ],
        )
        if rank_outcomes:
            result["publication_receipt"] = deepcopy(receipt)
        digest = canonical_sha256(manifest_or_games)
        if current_ranks:
            result.update(
                status="current_rank_verified",
                algorithm=CURRENT_RANK_ALGORITHM,
                manifest_sha256=digest,
                target=target,
                database_identity=rank_context["database_identity"],
                rank_context_sha256=rank_context["content_sha256"],
                rank_publication_context=rank_context,
            )
            validate_current_rank_verification(manifest_or_games, receipt, result, rank_context, target)
        else:
            validate_test_verification(manifest_or_games, digest, {**result, "manifest_sha256": digest})
    else:
        validate_test_verification({"games": games}, "", {**result, "manifest_sha256": ""})
    get.remaining()
    return result
