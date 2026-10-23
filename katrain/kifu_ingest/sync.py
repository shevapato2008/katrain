"""Fixed SSH transport and actual five-language album API verification."""

from __future__ import annotations

import asyncio
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import re
import subprocess
import time

from katrain.core.sgf_parser import SGF
from katrain.kifu_ingest.catalog import validate_identity_check_request, validate_identity_check_response
from katrain.kifu_ingest.exclusions import assert_source_allowed
from katrain.kifu_ingest.verification import AlbumCheckpoint, VerificationGET, normalized_target
from katrain.web.kifu.name_candidates import canonical_sha256


LANGUAGES = ("cn", "tw", "jp", "ko", "en")
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


def send_verified_manifest(manifest, manifest_sha256, test_verification, *, host, key_path, known_hosts, timeout=180):
    """Send a tested logical package to a forced, restricted receiver command."""
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
    )
    process = subprocess.run(command, input=payload, text=True, capture_output=True, timeout=timeout, check=False)
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


def _validate_detail_evidence(evidence, game, album_id, lang, decisions):
    if (
        not isinstance(evidence, dict)
        or set(evidence) != {"album_id", "lang", "sgf_sha256", "metadata", "source_key", "displays"}
        or type(evidence["album_id"]) is not int
        or evidence["album_id"] != album_id
        or evidence["lang"] != lang
    ):
        raise ValueError("album API ID or language mismatch")
    if evidence["sgf_sha256"] != game["sgf_sha256"]:
        raise ValueError("album API SGF hash mismatch")
    if not isinstance(evidence["metadata"], dict) or set(evidence["metadata"]) != set(_ORIGINAL_FIELDS):
        raise ValueError("album API original metadata is malformed")
    for field in _ORIGINAL_FIELDS:
        if evidence["metadata"][field] != game["metadata"].get(field):
            raise ValueError(f"album API {field} mismatch")
    if evidence["source_key"] != game["source_key"]:
        raise ValueError("album API source link missing")
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


def _detail_evidence(detail, game, album_id, lang, decisions):
    if not isinstance(detail, dict) or detail.get("id") != album_id:
        raise ValueError("album API ID mismatch")
    try:
        canonical = SGF.parse_sgf(detail["sgf_content"]).sgf()
    except (KeyError, ValueError, TypeError, IndexError, AttributeError) as exc:
        raise ValueError("album API SGF is invalid") from exc
    sources = detail.get("sources")
    evidence = {
        "album_id": detail["id"],
        "lang": lang,
        "sgf_sha256": sha256(canonical.encode("utf-8")).hexdigest(),
        "metadata": {field: detail.get(field) for field in _ORIGINAL_FIELDS},
        "source_key": game["source_key"] if isinstance(sources, list) and game["source_key"] in sources else None,
        "displays": {field: detail.get(field) for field in _DISPLAY_FIELDS},
    }
    _validate_detail_evidence(evidence, game, album_id, lang, decisions)
    return evidence


async def verify_album_api(
    client,
    base_url,
    manifest_or_games,
    receipt,
    *,
    timeout=30,
    deadline=None,
    checkpoint_dir=None,
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
    games = manifest_or_games["games"] if isinstance(manifest_or_games, dict) else manifest_or_games
    decisions = (
        {(row["kind"], row["key"]): row["displays"] for row in manifest_or_games.get("decisions", [])}
        if isinstance(manifest_or_games, dict)
        else {}
    )
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
            _validate_detail_evidence(detail, game, album_id, lang, decisions)
        cn_card = next(detail["displays"] for detail in completed["details"] if detail["lang"] == "cn")
        card = completed["public_card"]
        if (
            not isinstance(card, dict)
            or set(card) != {"album_id", "lang", "query", "page", "page_size", "displays"}
            or type(card["album_id"]) is not int
            or card["album_id"] != album_id
            or card["lang"] != "cn"
            or card["query"] not in (game["metadata"].get("date_played"), game["metadata"]["player_black"])
            or not card["query"]
            or type(card["page"]) is not int
            or not 1 <= card["page"] <= 20
            or type(card["page_size"]) is not int
            or card["page_size"] != 100
            or card["displays"] != cn_card
        ):
            raise ValueError("checkpoint public card is invalid")

    checkpoint = AlbumCheckpoint(
        checkpoint_dir, manifest_or_games, receipt, target, LANGUAGES, validate_completed, wall_clock
    )
    checked = []
    listings = {}
    for key, (game, album_id) in expected_albums.items():
        get.remaining()
        completed = checkpoint.get(key)
        if completed is None:
            details = []
            for lang in LANGUAGES:
                response = await get.get(f"{target}/api/v1/kifu/albums/{album_id}", {"lang": lang})
                if response.status_code != 200:
                    raise ValueError(f"album API {album_id}/{lang} returned {response.status_code}")
                details.append(_detail_evidence(response.json(), game, album_id, lang, decisions))
            cn_card = next(detail["displays"] for detail in details if detail["lang"] == "cn")
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
                        if row["id"] == album_id:
                            if any(row.get(field) != value for field, value in cn_card.items()):
                                raise ValueError("album public list card differs from verified detail")
                            public_card = {
                                "album_id": album_id,
                                "lang": "cn",
                                "query": query,
                                "page": page,
                                "page_size": 100,
                                "displays": {field: row[field] for field in _DISPLAY_FIELDS},
                            }
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
        checked.extend({"album_id": album_id, "lang": detail["lang"]} for detail in completed["details"])
    get.remaining()
    result = {"status": "verified", "games": len(games), "checks": checked}
    validate_test_verification({"games": games}, "", {**result, "manifest_sha256": ""})
    get.remaining()
    return result
