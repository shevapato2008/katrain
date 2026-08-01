"""Pure evidence importer and scheduler for the Golaxy b18 20-game extension."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path


MODEL = "b18"
MODEL_SHA256 = "9d7a6afed8ff5b74894727e156f04f0cd36060a24824892008fbb6e0cba51f1d"
REFEREE_MODEL = "b28"
REFEREE_MODEL_SHA256 = "798da8fe3e9819f09535240b1bc29cb3047a4fa981433c56c491e57007a3d3f0"
GOLAXY_LEVEL = 36
GOLAXY_LEVEL_NAME = "星阵3星"
GOLAXY_API_LEVEL = 3300
CANDIDATE_VISITS = (32, 64)
TARGET_CONCLUSIVE = 20
PARENT_PATH = (
    Path(__file__).resolve().parent
    / "results/golaxy_b18_binary_stars_20260726/binary_search_v5.jsonl"
)
PARENT_SHA256 = "9a5796b624924266efa6eb6937a4cb4833468bfa0270e5f115fc6d2714fc4082"

_CARRY_LINES = (2, 3, 4, 5, 6, 17, 18, 19, 20, 21, 22, 23, 24, 25)
_CONCLUSIVE_OUTCOMES = frozenset(("our_win", "our_loss"))
_INCONCLUSIVE_OUTCOMES = frozenset(
    ("inconclusive_score", "inconclusive_unsettled", "inconclusive_unstable")
)
_ACCEPTED_OUTCOMES = _CONCLUSIVE_OUTCOMES | _INCONCLUSIVE_OUTCOMES


@dataclass(frozen=True)
class GameRequest:
    visits: int
    color: str


@dataclass(frozen=True)
class CandidateSummary:
    visits: int
    conclusive: int
    wins: int
    losses: int
    inconclusive: int
    black: int
    white: int


@dataclass(frozen=True)
class CampaignDecision:
    status: str
    candidates: tuple[CandidateSummary, ...]


def _validate_source_row(row: Mapping[str, object], line_number: int) -> None:
    expected_fields = {
        "type": "carry_result",
        "level": GOLAXY_LEVEL,
        "level_name": GOLAXY_LEVEL_NAME,
        "api_level": GOLAXY_API_LEVEL,
    }
    for field, expected in expected_fields.items():
        if row.get(field) != expected:
            raise ValueError(f"parent line {line_number} has wrong {field}")
    if "rung" in row and row["rung"] != GOLAXY_LEVEL:
        raise ValueError(f"parent line {line_number} has wrong rung")
    if row.get("visits") not in CANDIDATE_VISITS:
        raise ValueError(f"parent line {line_number} has wrong visits")
    if row.get("color") not in {"B", "W"}:
        raise ValueError(f"parent line {line_number} has wrong color")

    outcome = row.get("outcome")
    if not isinstance(outcome, Mapping):
        raise ValueError(f"parent line {line_number} has invalid outcome")
    result = outcome.get("result")
    if result not in _CONCLUSIVE_OUTCOMES:
        raise ValueError(f"parent line {line_number} has invalid outcome")
    if outcome.get("conclusive") is not True:
        raise ValueError(f"parent line {line_number} has invalid conclusive status")
    if outcome.get("our_color") != row["color"]:
        raise ValueError(f"parent line {line_number} has inconsistent outcome color")
    if outcome.get("our_win") is not (result == "our_win"):
        raise ValueError(f"parent line {line_number} has inconsistent outcome result")


def load_frozen_carries(parent_path: Path, expected_sha256: str) -> tuple[dict, ...]:
    """Load only the approved b18 rows after verifying the direct parent's bytes."""

    parent_path = Path(parent_path)
    raw = parent_path.read_bytes()
    actual_sha256 = hashlib.sha256(raw).hexdigest()
    if actual_sha256 != expected_sha256:
        raise ValueError(f"parent SHA256 mismatch: expected {expected_sha256}, got {actual_sha256}")

    try:
        rows = [json.loads(line) for line in raw.decode("utf-8").splitlines()]
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("parent is not valid UTF-8 JSONL") from exc
    if not rows or not isinstance(rows[0], Mapping) or rows[0].get("model") != MODEL:
        raise ValueError("parent header has wrong model")
    if len(rows) < _CARRY_LINES[-1]:
        raise ValueError("parent is missing approved source rows")

    selected = [(line_number, rows[line_number - 1]) for line_number in _CARRY_LINES]
    fingerprints: set[str] = set()
    for line_number, row in selected:
        if not isinstance(row, Mapping):
            raise ValueError(f"parent line {line_number} is not an object")
        fingerprint = json.dumps(row, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        if fingerprint in fingerprints:
            raise ValueError(f"duplicate selected source row at parent line {line_number}")
        fingerprints.add(fingerprint)
        _validate_source_row(row, line_number)

    for visits, expected_count, expected_colors, expected_outcomes in (
        (32, 4, {"B": 2, "W": 2}, {"our_win": 1, "our_loss": 3}),
        (64, 10, {"B": 5, "W": 5}, {"our_win": 7, "our_loss": 3}),
    ):
        candidate = [(line_number, row) for line_number, row in selected if row["visits"] == visits]
        colors = {color: sum(row["color"] == color for _line, row in candidate) for color in ("B", "W")}
        outcomes = {
            outcome: sum(row["outcome"]["result"] == outcome for _line, row in candidate)
            for outcome in _CONCLUSIVE_OUTCOMES
        }
        if len(candidate) != expected_count or outcomes != expected_outcomes:
            raise ValueError(f"wrong inherited counts for visits {visits}")
        if colors != expected_colors or [row["color"] for _line, row in candidate] != [
            "B" if index % 2 == 0 else "W" for index in range(expected_count)
        ]:
            raise ValueError(f"wrong inherited color balance for visits {visits}")

    carries = []
    for line_number, row in selected:
        source_outcome = dict(row["outcome"])
        result = source_outcome["result"]
        carries.append(
            {
                "type": "carry_result",
                "visits": row["visits"],
                "color": row["color"],
                "outcome": result,
                "result": result,
                "conclusive": True,
                "origin_result_id": f"legacy:{actual_sha256}:{line_number}",
                "direct_parent_sha256": actual_sha256,
                "direct_parent_line": line_number,
                "source_outcome": source_outcome,
            }
        )
    return tuple(carries)


def _validate_evidence(evidence: Sequence[Mapping[str, object]]) -> tuple[Mapping[str, object], ...]:
    validated: list[Mapping[str, object]] = []
    conclusive_counts = {visits: 0 for visits in CANDIDATE_VISITS}
    seen_result_ids: set[str] = set()
    for index, row in enumerate(evidence, 1):
        if not isinstance(row, Mapping):
            raise ValueError(f"evidence row {index} is not an object")
        visits = row.get("visits")
        if visits not in CANDIDATE_VISITS:
            raise ValueError(f"evidence row {index} has invalid visits")
        result = row.get("result", row.get("outcome"))
        if result not in _ACCEPTED_OUTCOMES or (
            "result" in row and "outcome" in row and row["result"] != row["outcome"]
        ):
            raise ValueError(f"evidence row {index} has invalid outcome")
        conclusive = row.get("conclusive")
        if conclusive is not (result in _CONCLUSIVE_OUTCOMES):
            raise ValueError(f"evidence row {index} has inconsistent conclusive status")

        expected_color = "B" if conclusive_counts[visits] % 2 == 0 else "W"
        if row.get("color") != expected_color:
            raise ValueError(f"evidence row {index} has invalid color sequence")
        if conclusive:
            conclusive_counts[visits] += 1
            if conclusive_counts[visits] > TARGET_CONCLUSIVE:
                raise ValueError(f"candidate {visits} has more than {TARGET_CONCLUSIVE} conclusive results")

        result_id = row.get("origin_result_id")
        if result_id is not None:
            if not isinstance(result_id, str) or not result_id:
                raise ValueError(f"evidence row {index} has invalid origin_result_id")
            if result_id in seen_result_ids:
                raise ValueError(f"duplicate evidence origin_result_id: {result_id}")
            seen_result_ids.add(result_id)
        validated.append(row)
    return tuple(validated)


def summarize_candidate(evidence: Sequence[Mapping[str, object]], visits: int) -> CandidateSummary:
    if visits not in CANDIDATE_VISITS:
        raise ValueError(f"invalid candidate visits: {visits}")
    validated = _validate_evidence(evidence)
    rows = [row for row in validated if row["visits"] == visits]
    conclusive_rows = [row for row in rows if row["conclusive"]]
    outcomes = [row.get("result", row.get("outcome")) for row in rows]
    return CandidateSummary(
        visits=visits,
        conclusive=len(conclusive_rows),
        wins=outcomes.count("our_win"),
        losses=outcomes.count("our_loss"),
        inconclusive=len(rows) - len(conclusive_rows),
        black=sum(row["color"] == "B" for row in conclusive_rows),
        white=sum(row["color"] == "W" for row in conclusive_rows),
    )


def next_action(evidence: Sequence[Mapping[str, object]]) -> GameRequest | CampaignDecision:
    validated = _validate_evidence(evidence)
    summaries = tuple(summarize_candidate(validated, visits) for visits in CANDIDATE_VISITS)
    for summary in summaries:
        if summary.conclusive < TARGET_CONCLUSIVE:
            return GameRequest(summary.visits, "B" if summary.conclusive % 2 == 0 else "W")
    return CampaignDecision("completed", summaries)
