"""Fixed SSH transport and actual five-language album API verification."""

from __future__ import annotations

from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import re
import subprocess

from katrain.core.sgf_parser import SGF
from katrain.kifu_ingest.exclusions import assert_source_allowed
from katrain.web.kifu.name_candidates import canonical_sha256


LANGUAGES = ("cn", "tw", "jp", "ko", "en")


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


def send_verified_manifest(manifest, manifest_sha256, test_verification, *, host, key_path, known_hosts, timeout=180):
    """Send a tested logical package to a forced, restricted receiver command."""
    validate_test_verification(manifest, manifest_sha256, test_verification)
    if canonical_sha256(manifest) != manifest_sha256:
        raise ValueError("manifest hash mismatch")
    for game in manifest["games"]:
        assert_source_allowed(game["source_key"], game["source_item_id"])
    if not host or not re.fullmatch(r"[A-Za-z0-9_.@-]+", host):
        raise ValueError("invalid SSH host")
    if not Path(key_path).is_absolute() or not Path(known_hosts).is_absolute():
        raise ValueError("SSH key and known_hosts paths must be absolute")
    command = [
        "ssh",
        "-o",
        "BatchMode=yes",
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
    payload = json.dumps(
        {"manifest": manifest, "manifest_sha256": manifest_sha256, "test_verification": test_verification},
        ensure_ascii=False,
        separators=(",", ":"),
    )
    process = subprocess.run(command, input=payload, text=True, capture_output=True, timeout=timeout, check=False)
    if process.returncode:
        raise RuntimeError(f"receiver exited with status {process.returncode}")
    try:
        response = json.loads(process.stdout)
    except (ValueError, TypeError) as exc:
        raise RuntimeError("receiver returned invalid JSON") from exc
    if response.get("status") != "applied" or response.get("manifest_sha256") != manifest_sha256:
        raise RuntimeError("receiver receipt differs from requested manifest")
    return response


async def verify_album_api(client, base_url, manifest_or_games, receipt, *, timeout=15):
    """Read real detail endpoints; fail closed on content or visible card mismatch."""
    games = manifest_or_games["games"] if isinstance(manifest_or_games, dict) else manifest_or_games
    decisions = (
        {
            (decision["kind"], decision["key"]): decision["displays"]
            for decision in manifest_or_games.get("decisions", [])
        }
        if isinstance(manifest_or_games, dict)
        else {}
    )
    mappings = {(row["source_key"], row["source_item_id"]): row["album_id"] for row in receipt["games"]}
    checked = []
    visible = set()
    for game in games:
        key = game["source_key"], game["source_item_id"]
        album_id = mappings[key]
        cn_card = None
        for lang in LANGUAGES:
            response = await client.get(
                f"{base_url.rstrip('/')}/api/v1/kifu/albums/{album_id}",
                params={"lang": lang},
                timeout=timeout,
            )
            if response.status_code != 200:
                raise ValueError(f"album API {album_id}/{lang} returned {response.status_code}")
            detail = response.json()
            if detail.get("id") != album_id:
                raise ValueError("album API ID mismatch")
            try:
                canonical = SGF.parse_sgf(detail["sgf_content"]).sgf()
            except (KeyError, ValueError, TypeError, IndexError, AttributeError) as exc:
                raise ValueError("album API SGF is invalid") from exc
            if sha256(canonical.encode("utf-8")).hexdigest() != game["sgf_sha256"]:
                raise ValueError("album API SGF hash mismatch")
            for field in ("player_black", "player_white", "event"):
                if detail.get(field) != game["metadata"].get(field):
                    raise ValueError(f"album API {field} mismatch")
            if game["source_key"] not in detail.get("sources", []):
                raise ValueError("album API source link missing")
            for field in ("display_player_black", "display_player_white", "display_event"):
                if not isinstance(detail.get(field), str) or not detail[field].strip():
                    raise ValueError(f"album API {field} missing for {lang}")
                slot = field.removeprefix("display_").removeprefix("player_")
                raw = game["metadata"]["event" if slot == "event" else f"player_{slot}"]
                identity = game.get("identities", {}).get(slot)
                kind = "event" if slot == "event" else "player"
                decision_key = (
                    (kind, identity["canonical_name"]) if isinstance(identity, dict) else (f"raw_{kind}", raw)
                )
                expected = decisions.get(decision_key, {}).get(lang)
                if expected is not None and detail[field] != expected:
                    raise ValueError(f"album API {field} mismatch for {lang}")
            if lang == "cn":
                cn_card = {
                    field: detail[field]
                    for field in (
                        "display_player_black",
                        "display_player_white",
                        "display_event",
                    )
                }
            checked.append({"album_id": album_id, "lang": lang})
        if album_id not in visible:
            queries = [game["metadata"].get("date_played"), game["metadata"]["player_black"]]
            found = False
            for query in dict.fromkeys(value for value in queries if value):
                for page in range(1, 21):
                    response = await client.get(
                        f"{base_url.rstrip('/')}/api/v1/kifu/albums",
                        params={"q": query, "lang": "cn", "page": page, "page_size": 100},
                        timeout=timeout,
                    )
                    if response.status_code != 200:
                        raise ValueError(f"album public list returned {response.status_code}")
                    listing = response.json()
                    rows = listing.get("items")
                    if not isinstance(rows, list) or not isinstance(listing.get("total"), int):
                        raise ValueError("album public list is malformed")
                    for row in rows:
                        if isinstance(row, dict) and row.get("id") == album_id:
                            if any(row.get(field) != value for field, value in cn_card.items()):
                                raise ValueError("album public list card differs from verified detail")
                            found = True
                            break
                    if found:
                        break
                    if page * 100 >= listing["total"]:
                        break
                if found:
                    break
            if not found:
                raise ValueError(f"album {album_id} is absent from the public list")
            visible.add(album_id)
    return {"status": "verified", "games": len(games), "checks": checked}
