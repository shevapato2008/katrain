"""Pure portable rank decisions shared by preparation, publication and API output.

Facts are deduplicated at manifest level. Snapshots bind their exact source slot
and logical owner, so neither local database IDs nor today's profile are needed
to reproduce an old card.
"""

from copy import deepcopy
from datetime import datetime, timezone
import json
import re

from katrain.web.kifu.name_candidates import canonical_sha256
from katrain.web.kifu.name_parse import parse_player
from katrain.web.kifu.player_ranks import build_source_rank_fact, normalize_rank, validate_rank_fact


FORMAT_V2 = "kifu-incremental-manifest-v2"
SNAPSHOT_VERSION = "kifu-rank-snapshot-v1"
POLICY_VERSION = "source-library-current-v1"
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


def rank_decision_request(game):
    """The independent disk cache key intentionally excludes mutable profiles."""
    return {
        "policy_version": POLICY_VERSION,
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


def _raw_rank(game, side):
    raw = game["metadata"].get(f"{side}_rank") or ""
    parsed = parse_player(game["metadata"].get(f"player_{side}"), raw)
    return raw or parsed.display_rank or "", parsed.display_rank or ""


def freeze_game_ranks(game, *, library_facts=None, identity_evidence=None, matched_at=None):
    """Freeze source > qualified library current > explicit unknown, without I/O."""
    matched_at = _utc(matched_at)
    library_facts, identity_evidence = library_facts or {}, identity_evidence or {}
    facts, snapshots, observations = {}, {}, {}
    for side in ("black", "white"):
        owner = game.get("identities", {}).get(side)
        raw, original_display = _raw_rank(game, side)
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
            "policy_version": POLICY_VERSION,
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


def validate_rank_snapshot(snapshot):
    """Validate standalone snapshot shape and self hash (not its DB authority)."""
    _require(isinstance(snapshot, dict) and set(snapshot) == _FIELDS, "rank snapshot shape invalid")
    _require(
        snapshot["version"] == SNAPSHOT_VERSION and snapshot["policy_version"] == POLICY_VERSION,
        "rank snapshot policy invalid",
    )
    _require(snapshot["content_sha256"] == snapshot_sha256(snapshot), "rank snapshot hash mismatch")
    ref, owner = snapshot["source_ref"], snapshot["player_ref"]
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
            owner = game.get("identities", {}).get(side)
            raw, original_display = _raw_rank(game, side)
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
        "rank": raw_rank or (snapshot["display_rank"] if snapshot["origin"] == "library_current" else ""),
        "rank_origin": "source" if raw_rank else snapshot["origin"],
        "rank_source": deepcopy(source),
    }
