"""Small source-aware rank policy and immutable per-game overlays.

This policy deliberately does not change generic user-strength parsing, native
v1 receipts, SGF text, raw columns, or today's player-rank projection.
"""

from copy import deepcopy
from hashlib import sha256
import json
import re
import unicodedata

from katrain.web.kifu.player_ranks import normalize_rank

SNAPSHOT_VERSION = "kifu-source-rank-snapshot-v2"
POLICY_VERSION = "trusted-source-rank-v2"
_CWI_BUCKETS = {"Go_Seigen", "CWI_1950_1978", "CWI_Dosaku", "CWI_History_Full", "CWI_Jowa", "CWI_Shusaku"}
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_FIELDS = {
    "version",
    "policy_version",
    "source_ref",
    "player_id",
    "raw_rank",
    "display_rank",
    "rank_value",
    "rank_system",
    "evidence",
    "content_sha256",
}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def digest(value):
    return sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


def snapshot_digest(snapshot):
    return digest({key: value for key, value in snapshot.items() if key != "content_sha256"})


def normalize_source_rank(raw_rank, *, source_key=None):
    """Return neutral canonical text; unqualified historic/unknown d is unspecified."""
    if not isinstance(raw_rank, str):
        return None
    raw = "".join(unicodedata.normalize("NFKC", raw_rank).split()).casefold()
    explicit_ama = re.fullmatch(r"([1-9]\d?)(d|dan|k|kyu)ama", raw)
    parsed = normalize_rank(raw[:-3] if explicit_ama else raw)
    if parsed is None:
        return None
    parsed = dict(parsed)
    if not explicit_ama and re.fullmatch(r"[1-9]\d?(d|dan)", raw) and source_key != "19x19":
        parsed["rank_system"] = "dan_unspecified"
    suffix = {"professional_dan": "p", "amateur_dan": "d", "kyu": "k", "dan_unspecified": "段"}
    return {"display_rank": str(parsed["rank_value"]) + suffix[parsed["rank_system"]], **parsed}


def trusted_source_link(album, source_links):
    """Require one source family and its exact original path, never SO/directory alone."""
    links = [
        dict(link)
        for link in source_links
        if link["album_id"] == album["id"] and link["origin_path"] == album["source_path"]
    ]
    if len(links) != 1:
        return None
    link = links[0]
    path = link["origin_path"]
    parts = path.split("/") if isinstance(path, str) else []
    if len(parts) < 4 or parts[:2] != ["data", "kifu-album"] or any(part in {"", ".", ".."} for part in parts):
        return None
    family = link["source_key"]
    if not path.lower().endswith(".sgf") or not (
        family == "19x19" and parts[2] == "19x19" or family == "CWI" and parts[2] in _CWI_BUCKETS
    ):
        return None
    return link


def source_binding(album, side, link):
    return {
        "album_id": album["id"],
        "source_link_id": link["id"],
        "source_id": link["source_id"],
        "source_key": link["source_key"],
        "source_path": link["origin_path"],
        "sgf_sha256": sha256(album["sgf_content"].encode()).hexdigest(),
        "slot": side,
    }


def build_source_snapshot(album, side, link, *, historical_evidence=None):
    require(side in {"black", "white"}, "rank side invalid")
    require(trusted_source_link(album, [link]) == link, "rank source link invalid")
    raw = album.get(f"{side}_rank") or ""
    decision = normalize_source_rank(raw, source_key=link["source_key"])
    require(decision is not None, "rank is not normalizable")
    evidence = {"kind": "source_convention"}
    if historical_evidence:
        require(
            decision["rank_system"] == "dan_unspecified" and link["source_key"] == "CWI",
            "historical refinement requires legacy unspecified dan",
        )
        evidence = deepcopy(historical_evidence)
        require(
            evidence.get("kind") == "same_game_historical_professional"
            and evidence.get("rank_value") == decision["rank_value"],
            "historical grade mismatch",
        )
        decision.update(rank_system="professional_dan", display_rank=str(decision["rank_value"]) + "p")
    result = {
        "version": SNAPSHOT_VERSION,
        "policy_version": POLICY_VERSION,
        "source_ref": source_binding(album, side, link),
        "player_id": album.get(f"{side}_player_id"),
        "raw_rank": raw,
        **decision,
        "evidence": evidence,
    }
    result["content_sha256"] = snapshot_digest(result)
    return result


def validate_source_snapshot(snapshot, *, album, side, source_links):
    require(isinstance(snapshot, dict) and set(snapshot) == _FIELDS, "source rank snapshot shape invalid")
    require(
        snapshot["version"] == SNAPSHOT_VERSION and snapshot["policy_version"] == POLICY_VERSION,
        "source rank policy invalid",
    )
    require(snapshot["content_sha256"] == snapshot_digest(snapshot), "source rank snapshot hash mismatch")
    require(len(json.dumps(snapshot, ensure_ascii=False).encode()) <= 32 * 1024, "source rank snapshot too large")
    link = trusted_source_link(album, source_links)
    require(
        link is not None and snapshot["source_ref"] == source_binding(album, side, link), "source rank binding mismatch"
    )
    require(
        snapshot["player_id"] == album.get(f"{side}_player_id")
        and snapshot["raw_rank"] == (album.get(f"{side}_rank") or ""),
        "source rank owner/raw mismatch",
    )
    evidence = snapshot["evidence"]
    require(isinstance(evidence, dict), "source rank evidence invalid")
    if evidence == {"kind": "source_convention"}:
        expected = build_source_snapshot(album, side, link)
    else:
        require(evidence.get("kind") == "same_game_historical_professional", "source rank evidence kind invalid")
        proof = evidence.get("counterpart")
        require(
            isinstance(proof, dict)
            and proof.get("source_key") == "19x19"
            and isinstance(proof.get("sgf_sha256"), str)
            and _SHA.fullmatch(proof["sgf_sha256"])
            and isinstance(proof.get("operation_sha256"), str)
            and _SHA.fullmatch(proof["operation_sha256"]),
            "counterpart binding invalid",
        )
        counterpart_grade = normalize_source_rank(proof.get("raw_rank"), source_key="19x19")
        require(
            proof.get("slot") == side
            and counterpart_grade is not None
            and counterpart_grade["rank_system"] == "professional_dan"
            and counterpart_grade["rank_value"] == snapshot["rank_value"],
            "counterpart historical grade invalid",
        )
        require(
            evidence.get("date") == proof.get("date")
            and isinstance(evidence.get("date"), str)
            and re.fullmatch(r"\d{4}-\d{2}-\d{2}", evidence["date"]),
            "counterpart precise date invalid",
        )
        require(
            evidence.get("ordered_player_ids") == proof.get("ordered_player_ids")
            and isinstance(evidence.get("ordered_player_ids"), list)
            and len(evidence["ordered_player_ids"]) == 2
            and all(isinstance(x, int) and x > 0 for x in evidence["ordered_player_ids"]),
            "counterpart player identity invalid",
        )
        expected = build_source_snapshot(album, side, link, historical_evidence=evidence)
    require(snapshot == expected, "source rank decision mismatch")
    return snapshot
