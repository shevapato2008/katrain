"""Pure portable rank decisions shared by preparation, publication and API output.

Facts are deduplicated at manifest level. Snapshots bind their exact source slot
and logical owner, so neither local database IDs nor today's profile are needed
to reproduce an old card.
"""

from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
import json
import re

from katrain.web.kifu.name_candidates import canonical_sha256
from katrain.web.kifu.name_parse import parse_player
from katrain.web.kifu.player_ranks import build_source_rank_fact, normalize_rank, validate_rank_fact


FORMAT_V2 = "kifu-incremental-manifest-v2"
SNAPSHOT_VERSION = "kifu-rank-snapshot-v1"
POLICY_VERSION = "source-library-current-v1"
SOURCE_POLICY_VERSION = "source-library-current-starpoint-v2"
# The unchanged 16 MiB transport also carries the bounded <=4 MiB v2 report.
MAX_MANIFEST_BYTES = 12 * 1024 * 1024
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_FIELDS = {
    "version",
    "policy_version",
    "source_ref",
    "player_ref",
    "origin",
    "raw_rank",
    "display_rank",
    "rank_value",
    "rank_system",
    "rank_fact_sha256",
    "source_as_of",
    "valid_from",
    "observed_at",
    "matched_at",
    "source_proof",
    "content_sha256",
}


def _require(value, message):
    if not value:
        raise ValueError(message)


def _utc(value=None):
    value = value or datetime.now(timezone.utc).isoformat()
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    _require(parsed.tzinfo is not None, "rank timestamp requires timezone")
    return parsed.astimezone(timezone.utc).isoformat()


def snapshot_sha256(snapshot):
    return canonical_sha256({key: value for key, value in snapshot.items() if key != "content_sha256"})


def merge_rank_facts(*fact_maps):
    """Deduplicate immutable facts using their earliest observation as representative.

    Snapshot observation/match times belong to each frozen decision. Selecting a
    shared fact representative never changes the input maps or those snapshots.
    """
    merged = {}
    for facts in fact_maps:
        for digest, fact in facts.items():
            validate_rank_fact(fact)
            _require(digest == fact["content_sha256"], "rank fact map hash mismatch")
            previous = merged.get(digest)
            if previous is None or datetime.fromisoformat(fact["observed_at"]) < datetime.fromisoformat(
                previous["observed_at"]
            ):
                merged[digest] = fact
    return merged


def rank_decision_request(game, *, historical=False):
    """The independent disk cache key intentionally excludes mutable profiles."""
    return {
        "policy_version": "historical-rank-as-of-v1" if historical else POLICY_VERSION,
        "source_key": game["source_key"],
        "source_item_id": game["source_item_id"],
        "sgf_sha256": game["sgf_sha256"],
        "raw_sha256": game["raw_sha256"],
        "source_metadata_sha256": canonical_sha256(game.get("source_metadata")),
        "slots": {
            side: {"player_ref": game.get("identities", {}).get(side), "raw_rank": game["metadata"].get(f"{side}_rank")}
            for side in ("black", "white")
        },
    }


def _proof(fact):
    if fact is None:
        return None
    identity = fact["evidence"]["professional_identity"]
    return {
        "source_kind": fact["source_kind"],
        "source_ref": deepcopy(fact["source_ref"]),
        "capture_sha256": identity["capture_sha256"] if identity else None,
    }


def _display(fact):
    suffix = {"professional_dan": "p", "amateur_dan": "d", "kyu": "k", "dan_unspecified": "段"}
    return str(fact["rank_value"]) + suffix[fact["rank_system"]]


def _raw_rank(game, side, *, source_policy=False):
    raw = game["metadata"].get(f"{side}_rank") or ""
    parsed = parse_player(game["metadata"].get(f"player_{side}"), raw)
    display = parsed.display_rank or ""
    if source_policy and game["source_key"] == "19x19" and raw and not display:
        from katrain.web.kifu.source_rank_normalization import normalize_source_rank

        decision = normalize_source_rank(raw, source_key="19x19")
        if decision:
            display = decision["display_rank"]
    return raw or parsed.display_rank or "", display


def freeze_game_ranks(game, *, library_facts=None, identity_evidence=None, matched_at=None):
    """Freeze source > qualified library current > explicit unknown, without I/O."""
    matched_at = _utc(matched_at)
    library_facts, identity_evidence = library_facts or {}, identity_evidence or {}
    facts, snapshots, observations = {}, {}, {}
    for side in ("black", "white"):
        owner = game.get("identities", {}).get(side)
        _, legacy_display = _raw_rank(game, side)
        raw, original_display = _raw_rank(game, side, source_policy=True)
        policy = SOURCE_POLICY_VERSION if original_display != legacy_display else POLICY_VERSION
        source_fact = None
        if owner is not None and raw:
            try:
                source_fact = build_source_rank_fact(
                    canonical_name=owner["canonical_name"],
                    raw_rank=raw,
                    sgf_content=game["sgf_content"],
                    slot=side,
                    source_ref={"source_key": game["source_key"], "source_item_id": game["source_item_id"]},
                    source_as_of=game["metadata"].get("date_sort"),
                    identity_evidence=identity_evidence.get(owner["canonical_name"]),
                    observed_at=matched_at,
                )
            except (TypeError, ValueError, KeyError):
                # Unusable evidence is isolated to this player; the legal SGF remains usable.
                try:
                    source_fact = build_source_rank_fact(
                        canonical_name=owner["canonical_name"],
                        raw_rank=raw,
                        sgf_content=game["sgf_content"],
                        slot=side,
                        source_ref={"source_key": game["source_key"], "source_item_id": game["source_item_id"]},
                        source_as_of=game["metadata"].get("date_sort"),
                        observed_at=matched_at,
                    )
                except (TypeError, ValueError, KeyError):
                    source_fact = None
        observations[side] = source_fact["content_sha256"] if source_fact else None
        used = source_fact
        if raw:
            origin, display = "source", original_display
            parsed = normalize_rank(raw)
            if policy == SOURCE_POLICY_VERSION:
                from katrain.web.kifu.source_rank_normalization import normalize_source_rank

                parsed = normalize_source_rank(raw, source_key="19x19")
        else:
            candidate = library_facts.get(owner["canonical_name"]) if owner else None
            try:
                if candidate is not None:
                    validate_rank_fact(candidate, canonical_name=owner["canonical_name"])
                    _require(candidate["rank_system"] != "dan_unspecified", "fallback rank system unknown")
            except (TypeError, ValueError, KeyError):
                candidate = None
            used = candidate
            origin, display = ("library_current", _display(used)) if used else ("unknown", "")
            parsed = used
        if source_fact:
            facts.setdefault(source_fact["content_sha256"], source_fact)
        if used:
            facts.setdefault(used["content_sha256"], used)
            parsed = used
        snapshot = {
            "version": SNAPSHOT_VERSION,
            "policy_version": policy,
            "source_ref": {
                "source_key": game["source_key"],
                "source_item_id": game["source_item_id"],
                "sgf_sha256": game["sgf_sha256"],
                "slot": side,
            },
            "player_ref": deepcopy(owner),
            "origin": origin,
            "raw_rank": raw,
            "display_rank": display,
            "rank_value": parsed["rank_value"] if parsed else None,
            "rank_system": parsed["rank_system"] if parsed else None,
            "rank_fact_sha256": used["content_sha256"] if used else None,
            "source_as_of": used["source_as_of"] if used else None,
            "valid_from": used["valid_from"] if used else None,
            "observed_at": used["observed_at"] if used else matched_at,
            "matched_at": matched_at,
            "source_proof": _proof(used),
        }
        snapshot["content_sha256"] = snapshot_sha256(snapshot)
        snapshots[side] = snapshot
    return {"rank_snapshots": snapshots, "rank_observations": observations, "rank_facts": deepcopy(facts)}


def is_historical_snapshot(snapshot):
    return isinstance(snapshot, dict) and snapshot.get("version") == "kifu-rank-snapshot-v3"


def historical_game_targets(games):
    """Portable proposed slots; pending rows deliberately carry no local IDs."""
    targets = []
    for game in games:
        album = {**game["metadata"], "id": None, "sgf_content": game["sgf_content"], "source_path": game["origin_path"]}
        links = [
            {
                "source_key": game["source_key"],
                "origin_path": game["origin_path"],
                "album_id": None,
                "id": None,
                "source_id": None,
            }
        ]
        for side in ("black", "white"):
            owner = game.get("identities", {}).get(side)
            targets.append(
                {
                    "album": album,
                    "side": side,
                    "source_links": links,
                    "player_ref": owner if isinstance(owner, dict) else None,
                }
            )
    return targets


def freeze_historical_game_ranks(conn, games, *, matched_at=None):
    """Freeze a bounded incoming batch from existing original evidence only."""
    from katrain.web.kifu.historical_ranks import prepare_rank_decisions

    when = _utc(matched_at)
    decisions = prepare_rank_decisions(conn, historical_game_targets(games), matched_at=when)["decisions"]
    result = []
    for index, game in enumerate(games):
        # Inferences are never promoted to original rank facts. Keep only true
        # source observations under the existing immutable fact contract.
        source = freeze_game_ranks(game, matched_at=when)
        result.append({**source, "rank_snapshots": dict(zip(("black", "white"), decisions[2 * index : 2 * index + 2]))})
    return result


def _validate_historical_slot(game, side, snapshot, observations, facts, used):
    from katrain.web.kifu.historical_ranks import validate_rank_source_metadata

    source = validate_rank_source_metadata({**game["metadata"], "sgf_content": game["sgf_content"]})
    _require(
        sha256(game["sgf_content"].encode()).hexdigest() == game["sgf_sha256"]
        and snapshot["source_ref"]
        == {
            "source_key": game["source_key"],
            "origin_path": game["origin_path"],
            "sgf_sha256": game["sgf_sha256"],
            "slot": side,
        }
        and snapshot["player_ref"] == game.get("identities", {}).get(side)
        and snapshot["raw_rank"] == (game["metadata"].get(f"{side}_rank") or "")
        and snapshot["raw_name"] == game["metadata"].get(f"player_{side}")
        and snapshot["target_date"] == source["target_date"],
        "rank snapshot source/slot/owner/raw/date binding mismatch",
    )
    original = freeze_game_ranks(game, matched_at=snapshot["matched_at"])
    observation = observations[side]
    _require(observation == original["rank_observations"][side], "original rank observation changed")
    if observation:
        _require(
            observation in facts
            and {k: v for k, v in facts[observation].items() if k != "observed_at"}
            == {k: v for k, v in original["rank_facts"][observation].items() if k != "observed_at"},
            "original rank observation source mismatch",
        )
        used.add(observation)


def validate_rank_snapshot(snapshot):
    """Validate standalone snapshot shape and self hash (not its DB authority)."""
    if is_historical_snapshot(snapshot):
        from katrain.web.kifu.historical_ranks import validate_rank_decision

        return validate_rank_decision(snapshot)
    _require(isinstance(snapshot, dict) and set(snapshot) == _FIELDS, "rank snapshot shape invalid")
    _require(
        snapshot["version"] == SNAPSHOT_VERSION
        and snapshot["policy_version"] in {POLICY_VERSION, SOURCE_POLICY_VERSION},
        "rank snapshot policy invalid",
    )
    _require(snapshot["content_sha256"] == snapshot_sha256(snapshot), "rank snapshot hash mismatch")
    ref, owner = snapshot["source_ref"], snapshot["player_ref"]
    if snapshot["policy_version"] == SOURCE_POLICY_VERSION:
        _require(isinstance(ref, dict) and ref.get("source_key") == "19x19", "starpoint rank policy source invalid")
    _require(
        isinstance(ref, dict)
        and set(ref) == {"source_key", "source_item_id", "sgf_sha256", "slot"}
        and isinstance(ref["source_key"], str)
        and 0 < len(ref["source_key"]) <= 64
        and isinstance(ref["source_item_id"], str)
        and re.fullmatch(r"[0-9]+", ref["source_item_id"])
        and isinstance(ref["sgf_sha256"], str)
        and _SHA.fullmatch(ref["sgf_sha256"])
        and ref["slot"] in {"black", "white"},
        "rank snapshot source invalid",
    )
    _require(
        owner is None
        or isinstance(owner, dict)
        and set(owner) == {"canonical_name"}
        and isinstance(owner["canonical_name"], str)
        and 0 < len(owner["canonical_name"]) <= 512,
        "rank snapshot owner invalid",
    )
    _require(
        snapshot["origin"] in {"source", "library_current", "unknown"}
        and all(isinstance(snapshot[k], str) and len(snapshot[k]) <= 128 for k in ("raw_rank", "display_rank")),
        "rank snapshot display invalid",
    )
    if snapshot["origin"] == "library_current":
        _require(
            not snapshot["raw_rank"]
            and snapshot["player_ref"] is not None
            and snapshot["rank_system"] in {"professional_dan", "amateur_dan", "kyu"}
            and type(snapshot["rank_value"]) is int
            and 1 <= snapshot["rank_value"] <= (30 if snapshot["rank_system"] == "kyu" else 9)
            and snapshot["display_rank"] == _display(snapshot)
            and isinstance(snapshot["rank_fact_sha256"], str)
            and _SHA.fullmatch(snapshot["rank_fact_sha256"]),
            "rank fallback snapshot display invalid",
        )
    elif snapshot["origin"] == "unknown":
        _require(
            not snapshot["raw_rank"]
            and snapshot["display_rank"] == ""
            and all(
                snapshot[key] is None
                for key in (
                    "rank_value",
                    "rank_system",
                    "rank_fact_sha256",
                    "source_as_of",
                    "valid_from",
                    "source_proof",
                )
            ),
            "unknown rank snapshot invalid",
        )
    else:
        _require(bool(snapshot["raw_rank"]), "source rank snapshot lacks original rank")
    _require(
        (snapshot["rank_value"] is None and snapshot["rank_system"] is None)
        or type(snapshot["rank_value"]) is int
        and snapshot["rank_system"] in {"professional_dan", "amateur_dan", "kyu", "dan_unspecified"}
        and 1 <= snapshot["rank_value"] <= (30 if snapshot["rank_system"] == "kyu" else 9),
        "rank snapshot grade/system invalid",
    )
    if snapshot["policy_version"] == SOURCE_POLICY_VERSION:
        from katrain.web.kifu.source_rank_normalization import normalize_source_rank

        decision = normalize_source_rank(snapshot["raw_rank"], source_key="19x19")
        _require(
            snapshot["origin"] == "source"
            and decision is not None
            and all(snapshot[key] == decision[key] for key in ("display_rank", "rank_value", "rank_system")),
            "starpoint source rank decision mismatch",
        )
    digest = snapshot["rank_fact_sha256"]
    proof = snapshot["source_proof"]
    _require(digest is None or isinstance(digest, str) and _SHA.fullmatch(digest), "rank fact digest invalid")
    _require(
        (digest is None and proof is None)
        or digest is not None
        and isinstance(proof, dict)
        and set(proof) == {"source_kind", "source_ref", "capture_sha256"}
        and proof["source_kind"] == "explicit_album_rank",
        "rank compact source proof invalid",
    )
    if proof:
        ref = proof["source_ref"]
        _require(
            isinstance(ref, dict)
            and set(ref) == {"kind", "source_key", "source_item_id", "sgf_sha256", "slot"}
            and ref["kind"] == "explicit_album_rank"
            and isinstance(ref["source_key"], str)
            and re.fullmatch(r"[a-z0-9_-]{1,64}", ref["source_key"])
            and isinstance(ref["source_item_id"], str)
            and re.fullmatch(r"[a-zA-Z0-9_-]{1,64}", ref["source_item_id"])
            and isinstance(ref["sgf_sha256"], str)
            and _SHA.fullmatch(ref["sgf_sha256"])
            and ref["slot"] in {"black", "white"}
            and (
                proof["capture_sha256"] is None
                or isinstance(proof["capture_sha256"], str)
                and _SHA.fullmatch(proof["capture_sha256"])
            ),
            "rank compact fact source invalid",
        )
    for key in ("observed_at", "matched_at"):
        _require(isinstance(snapshot[key], str) and snapshot[key], "rank snapshot timestamp missing")
        _utc(snapshot[key])
    for key in ("source_as_of", "valid_from"):
        value = snapshot[key]
        _require(
            value is None or isinstance(value, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", value),
            "rank snapshot date invalid",
        )
        if value:
            datetime.strptime(value, "%Y-%m-%d")
    return snapshot


def validate_manifest_ranks(manifest):
    """Fully validate finite v2 fact references, original grades and bindings."""
    if manifest.get("format") != FORMAT_V2:
        return manifest  # Historical v1 bytes and proofs are deliberately untouched.
    games, facts = manifest.get("games"), manifest.get("rank_facts")
    _require(
        isinstance(games, list) and 1 <= len(games) <= 100 and isinstance(facts, dict) and len(facts) <= 400,
        "rank manifest bounds invalid",
    )
    for digest, fact in facts.items():
        validate_rank_fact(fact)
        _require(digest == fact["content_sha256"], "rank fact map hash mismatch")
    used = set()
    for game in games:
        snapshots, observations = game.get("rank_snapshots"), game.get("rank_observations")
        _require(
            isinstance(snapshots, dict)
            and set(snapshots) == {"black", "white"}
            and isinstance(observations, dict)
            and set(observations) == {"black", "white"},
            "rank slots missing",
        )
        for side, snapshot in snapshots.items():
            validate_rank_snapshot(snapshot)
            if is_historical_snapshot(snapshot):
                _validate_historical_slot(game, side, snapshot, observations, facts, used)
                continue
            owner = game.get("identities", {}).get(side)
            raw, original_display = _raw_rank(
                game, side, source_policy=snapshot["policy_version"] == SOURCE_POLICY_VERSION
            )
            _require(
                snapshot["source_ref"]
                == {
                    "source_key": game["source_key"],
                    "source_item_id": game["source_item_id"],
                    "sgf_sha256": game["sgf_sha256"],
                    "slot": side,
                }
                and snapshot["player_ref"] == owner
                and snapshot["raw_rank"] == raw,
                "rank snapshot source/slot/owner/raw binding mismatch",
            )
            digest = snapshot["rank_fact_sha256"]
            observation = observations[side]
            for reference in (digest, observation):
                _require(
                    reference is None or isinstance(reference, str) and reference in facts,
                    "rank fact reference missing",
                )
                if reference:
                    used.add(reference)
                    _require(owner is not None and facts[reference]["player_ref"] == owner, "rank fact owner mismatch")
            fact = facts.get(digest)
            if observation:
                source = facts[observation]
                _require(
                    source["source_ref"] == {"kind": "explicit_album_rank", **snapshot["source_ref"]}
                    and source["evidence"]["grade"]["sgf_content"] == game["sgf_content"]
                    and source["evidence"]["grade"]["raw_rank"] == raw,
                    "rank observation source mismatch",
                )
            if raw:
                _require(
                    snapshot["origin"] == "source"
                    and snapshot["display_rank"] == original_display
                    and digest == observation,
                    "original source rank assertion changed",
                )
                parsed = normalize_rank(raw)
                if snapshot["policy_version"] == SOURCE_POLICY_VERSION:
                    from katrain.web.kifu.source_rank_normalization import normalize_source_rank

                    parsed = normalize_source_rank(raw, source_key="19x19")
                if owner and observation is None:
                    try:
                        expected_source = build_source_rank_fact(
                            canonical_name=owner["canonical_name"],
                            raw_rank=raw,
                            sgf_content=game["sgf_content"],
                            slot=side,
                            source_ref={"source_key": game["source_key"], "source_item_id": game["source_item_id"]},
                            source_as_of=game["metadata"].get("date_sort"),
                            observed_at=snapshot["matched_at"],
                        )
                    except (ValueError, TypeError):
                        expected_source = None
                    _require(expected_source is None, "bound source rank observation missing")
            elif fact:
                _require(
                    snapshot["origin"] == "library_current"
                    and snapshot["display_rank"] == _display(fact)
                    and fact["rank_system"] != "dan_unspecified"
                    and observation is None,
                    "fallback rank assertion invalid",
                )
                parsed = fact
            else:
                _require(
                    snapshot["origin"] == "unknown" and snapshot["display_rank"] == "" and observation is None,
                    "unknown rank assertion invalid",
                )
                parsed = None
            if fact:
                parsed = fact
            _require(
                snapshot["rank_value"] == (parsed["rank_value"] if parsed else None)
                and snapshot["rank_system"] == (parsed["rank_system"] if parsed else None)
                and snapshot["source_proof"] == _proof(fact)
                and snapshot["source_as_of"] == (fact["source_as_of"] if fact else None)
                and snapshot["valid_from"] == (fact["valid_from"] if fact else None),
                "rank snapshot fact decision mismatch",
            )
        if manifest.get("mode") == "rank_only":
            correction = game.get("rank_correction")
            _require(
                isinstance(correction, dict)
                and set(correction) == {"original_manifest_sha256", "expected_snapshots"}
                and isinstance(correction["original_manifest_sha256"], str)
                and _SHA.fullmatch(correction["original_manifest_sha256"])
                and isinstance(correction["expected_snapshots"], dict)
                and set(correction["expected_snapshots"]) == {"black", "white"}
                and all(
                    value is None or isinstance(value, str) and _SHA.fullmatch(value)
                    for value in correction["expected_snapshots"].values()
                ),
                "rank correction CAS invalid",
            )
    _require(used == set(facts), "unreferenced rank fact")
    _require(manifest.get("mode", "publish") in {"publish", "rank_only"}, "rank manifest mode invalid")
    _require(
        manifest.get("mode") != "rank_only" or not manifest.get("decisions"), "rank correction cannot change names"
    )
    preflight_manifest_budget(manifest)
    return manifest


def preflight_manifest_budget(manifest):
    """Leave room for the bounded receiver envelope, without increasing its cap."""
    size = len(json.dumps(manifest, ensure_ascii=False, sort_keys=True, allow_nan=False).encode("utf-8"))
    _require(size <= MAX_MANIFEST_BYTES - 4096, "rank manifest exceeds receiver payload budget")
    return size


def display_rank_for_game_slot(snapshot, raw_rank=""):
    """Return raw-first display and compact frozen provenance for list/detail APIs."""
    if snapshot is None:
        return {"rank": raw_rank or "", "rank_origin": "source" if raw_rank else "unknown", "rank_source": None}
    validate_rank_snapshot(snapshot)
    if is_historical_snapshot(snapshot):
        basis = snapshot["basis"]
        return {
            "rank": snapshot["display_rank"],
            "rank_origin": snapshot["origin"],
            "rank_source": {
                "policy_version": snapshot["policy_version"],
                "snapshot_sha256": snapshot["content_sha256"],
                "rank_system": snapshot["rank_system"],
                "origin": snapshot["origin"],
                "source_ref": deepcopy(snapshot["source_ref"]),
                "source_as_of": basis[0]["raw_date"] if basis else snapshot["target_date"],
                "refusal_reason": snapshot["refusal_reason"],
            },
        }
    proof = snapshot["source_proof"] or {}
    source = {
        key: snapshot[key]
        for key in (
            "origin",
            "policy_version",
            "rank_fact_sha256",
            "source_as_of",
            "valid_from",
            "observed_at",
            "matched_at",
            "source_ref",
        )
    }
    source.update(
        snapshot_sha256=snapshot["content_sha256"],
        canonical_name=(snapshot["player_ref"] or {}).get("canonical_name"),
        source_kind=proof.get("source_kind"),
    )
    if proof.get("source_ref"):
        source["fact_source_ref"] = proof["source_ref"]
    return {
        "rank": (
            snapshot["display_rank"]
            if snapshot["policy_version"] == SOURCE_POLICY_VERSION
            else raw_rank or (snapshot["display_rank"] if snapshot["origin"] == "library_current" else "")
        ),
        "rank_origin": "source" if raw_rank else snapshot["origin"],
        "rank_source": deepcopy(source),
    }


_OUTCOME_FIELDS = {
    "source_key",
    "source_item_id",
    "album_id",
    "side",
    "status",
    "requested_snapshot_sha256",
    "original_source_ref",
    "retained_snapshot",
    "original_canonical_sgf_sha256",
}


def _retained_rank_display(game, side, snapshot, original_ref, album_id):
    """Validate the original portable assertion, then reproduce its API projection."""
    from katrain.web.kifu.source_rank_normalization import (
        SNAPSHOT_VERSION as SOURCE_VERSION,
        snapshot_digest,
        validate_source_snapshot,
    )

    owner = game.get("identities", {}).get(side)
    raw, display = _raw_rank(game, side)
    if snapshot.get("version") == SOURCE_VERSION:
        # v2 contains local IDs. Keep its signed bytes in the receipt, validate
        # the policy with an equivalent canonical body, and retain its real raw
        # body SHA in the API provenance. The HTTP verifier checks that SHA.
        _require(snapshot.get("content_sha256") == snapshot_digest(snapshot), "retained rank hash mismatch")
        ref = snapshot.get("source_ref")
        _require(
            isinstance(ref, dict)
            and ref.get("album_id") == album_id
            and all(type(ref.get(key)) is int and ref[key] > 0 for key in ("album_id", "source_link_id", "source_id")),
            "retained source rank local binding invalid",
        )
        _require(
            {
                "source_key": ref.get("source_key"),
                "origin_path": ref.get("source_path"),
                "sgf_sha256": ref.get("sgf_sha256"),
                "slot": ref.get("slot"),
            }
            == original_ref,
            "retained rank source mismatch",
        )
        album = {
            **game["metadata"],
            "id": ref.get("album_id"),
            "source_path": ref.get("source_path"),
            "sgf_content": game["sgf_content"],
            f"{side}_player_id": snapshot.get("player_id"),
        }
        link = {
            "album_id": album["id"],
            "id": ref.get("source_link_id"),
            "source_id": ref.get("source_id"),
            "origin_path": ref.get("source_path"),
            "source_key": ref.get("source_key"),
        }
        shadow = deepcopy(snapshot)
        shadow["source_ref"]["sgf_sha256"] = sha256(game["sgf_content"].encode()).hexdigest()
        shadow["content_sha256"] = snapshot_digest(shadow)
        validate_source_snapshot(shadow, album=album, side=side, source_links=[link])
        return {
            "rank": snapshot["display_rank"],
            "rank_origin": "source",
            "rank_source": {
                "policy_version": snapshot["policy_version"],
                "snapshot_sha256": snapshot["content_sha256"],
                "rank_system": snapshot["rank_system"],
                "source_ref": deepcopy(snapshot["source_ref"]),
                "source_kind": snapshot["evidence"]["kind"],
            },
        }
    validate_rank_snapshot(snapshot)
    if is_historical_snapshot(snapshot):
        from katrain.web.kifu.historical_ranks import validate_rank_source_metadata

        _require(
            snapshot["source_ref"] == original_ref
            and snapshot["raw_rank"] == (game["metadata"].get(f"{side}_rank") or "")
            and snapshot["raw_name"] == game["metadata"].get(f"player_{side}")
            and snapshot["target_date"]
            == validate_rank_source_metadata({**game["metadata"], "sgf_content": game["sgf_content"]})["target_date"],
            "retained historical target mismatch",
        )
    else:
        ref = snapshot["source_ref"]
        _require(
            original_ref
            == {
                "source_key": ref["source_key"],
                "origin_path": f"data/kifu-album/{ref['source_key']}/{ref['source_item_id']}.sgf",
                "sgf_sha256": ref["sgf_sha256"],
                "slot": ref["slot"],
            }
            and snapshot["raw_rank"] == raw,
            "retained native target mismatch",
        )
    _require(snapshot["player_ref"] == owner, "retained rank canonical owner mismatch")
    return display_rank_for_game_slot(snapshot, display)


def expected_rank_for_outcome(game, side, outcome):
    """Derive a rank expectation; a disposition never bypasses rank validation."""
    from katrain.core.sgf_parser import SGF
    from katrain.web.kifu.source_rank_normalization import normalize_source_rank, trusted_source_link

    requested = game["rank_snapshots"][side]
    _require(is_historical_snapshot(requested), "rank outcome requires a v3 request")
    _require(
        isinstance(outcome, dict)
        and set(outcome) == _OUTCOME_FIELDS
        and outcome["source_key"] == game["source_key"]
        and outcome["source_item_id"] == game["source_item_id"]
        and outcome["side"] == side
        and type(outcome["album_id"]) is int
        and outcome["album_id"] > 0
        and outcome["requested_snapshot_sha256"] == requested["content_sha256"],
        "rank outcome request binding mismatch",
    )
    ref = outcome["original_source_ref"]
    _require(
        isinstance(ref, dict)
        and set(ref) == {"source_key", "origin_path", "sgf_sha256", "slot"}
        and isinstance(ref["sgf_sha256"], str)
        and _SHA.fullmatch(ref["sgf_sha256"])
        and ref["slot"] == side,
        "rank outcome original source invalid",
    )
    link = {"album_id": outcome["album_id"], "origin_path": ref["origin_path"], "source_key": ref["source_key"]}
    _require(
        trusted_source_link({"id": outcome["album_id"], "source_path": ref["origin_path"]}, [link]) is not None,
        "rank outcome original ownership invalid",
    )
    _require(
        outcome["original_canonical_sgf_sha256"]
        == sha256(SGF.parse_sgf(game["sgf_content"]).sgf().encode()).hexdigest(),
        "rank outcome canonical SGF mismatch",
    )
    status, retained = outcome["status"], outcome["retained_snapshot"]
    if status == "applied":
        _require(ref == requested["source_ref"] and retained is None, "applied rank outcome differs from request")
        return display_rank_for_game_slot(requested)
    _require(ref != requested["source_ref"], "retained rank outcome still owns requested source")
    if status == "retained":
        _require(isinstance(retained, dict), "retained rank snapshot missing")
        return _retained_rank_display(game, side, retained, ref, outcome["album_id"])
    _require(status == "deferred" and retained is None, "rank outcome disposition invalid")
    parsed = parse_player(game["metadata"].get(f"player_{side}"), game["metadata"].get(f"{side}_rank"))
    raw = game["metadata"].get(f"{side}_rank")
    normalized = normalize_source_rank(raw or parsed.display_rank, source_key=ref["source_key"])
    fallback = normalized["display_rank"] if normalized else parsed.display_rank
    value = display_rank_for_game_slot(None, fallback)
    if raw:
        value["rank_origin"] = "source"
    return value


def validate_rank_outcomes(manifest, receipt):
    """Bind each optional new-v3 receipt slot to its actual, finite rank result."""
    if "rank_outcomes" not in receipt:
        return {}
    outcomes = receipt["rank_outcomes"]
    games = {(g["source_key"], g["source_item_id"]): g for g in manifest["games"]}
    _require(
        isinstance(receipt.get("games"), list) and 1 <= len(receipt["games"]) <= 100,
        "rank outcome receipt game bounds invalid",
    )
    mappings = {}
    for game in receipt["games"]:
        _require(isinstance(game, dict), "rank outcome receipt mapping malformed")
        key = game.get("source_key"), game.get("source_item_id")
        _require(
            key in games and key not in mappings and type(game.get("album_id")) is int and game["album_id"] > 0,
            "rank outcome receipt mapping invalid",
        )
        mappings[key] = game["album_id"]
    _require(set(mappings) == set(games), "rank outcome receipt source coverage invalid")
    expected = {
        (key[0], key[1], side)
        for key, game in games.items()
        for side, snapshot in game.get("rank_snapshots", {}).items()
        if is_historical_snapshot(snapshot)
    }
    _require(
        isinstance(outcomes, list) and len(outcomes) == len(expected) and bool(expected),
        "rank outcome coverage invalid",
    )
    result = {}
    for outcome in outcomes:
        _require(isinstance(outcome, dict), "rank outcome malformed")
        key = outcome.get("source_key"), outcome.get("source_item_id")
        slot = (*key, outcome.get("side"))
        _require(
            slot in expected and slot not in result and mappings.get(key) == outcome.get("album_id"),
            "rank outcome source/album/slot coverage invalid",
        )
        expected_rank_for_outcome(games[key], outcome["side"], outcome)
        result[slot] = outcome
    _require(set(result) == expected, "rank outcome slots incomplete")
    for key in games:
        refs = [
            tuple(x["original_source_ref"][field] for field in ("source_key", "origin_path", "sgf_sha256"))
            for slot, x in result.items()
            if slot[:2] == key
        ]
        _require(len(set(refs)) <= 1, "rank outcome sides have different original owners or bodies")
    return result


def portable_rank_outcomes(outcomes):
    """Allow target local IDs to differ; retained v2 internal IDs stay strict."""
    return sorted(
        ({key: value for key, value in outcome.items() if key != "album_id"} for outcome in outcomes),
        key=lambda x: (x["source_key"], x["source_item_id"], x["side"]),
    )
