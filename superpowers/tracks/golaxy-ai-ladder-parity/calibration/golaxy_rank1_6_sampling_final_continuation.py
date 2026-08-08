"""Final 24-game continuation for the four remaining rank matchups."""

from __future__ import annotations

import hashlib
import tempfile
from pathlib import Path


_BASE_SOURCE = Path(__file__).with_name("golaxy_rank1_6_sampling_continuation.py")
exec(compile(_BASE_SOURCE.read_bytes(), str(_BASE_SOURCE), "exec"), globals())

LEDGER_PROTOCOL = "golaxy-humansl-rank1-6-sampling-final-continuation-v4"
VALID_SLOTS_PER_STAGE = 6
FIRST_HUMANSL_COLOR = "B"
STAGES = (
    ("sampling_quasi_4d", "rank_4d@1", 1800),
    ("sampling_4d", "rank_4d@1", 1900),
    ("sampling_5d", "rank_5d@1", 2100),
    ("sampling_6d", "rank_6d@1", 2300),
)
STAGE_ORDER = tuple(stage for stage, _player, _level in STAGES)
PARENT_PATH = (
    Path(__file__).resolve().parent
    / "results/golaxy_rank1_6_sampling_continuation_20260802/campaign_v3.jsonl"
)
PARENT_SHA256 = "b5f3878c2c162d2b6b350c1a570b1d82c71a95a0d35a43447a1302adef4dcc37"


def _read_parent():
    """Verify the exact completed first continuation and inherit identity."""
    parent_path = Path(PARENT_PATH).resolve()
    try:
        parent_bytes = parent_path.read_bytes()
    except OSError as exc:
        raise ValueError(f"cannot read parent campaign {parent_path}: {exc}") from exc
    if hashlib.sha256(parent_bytes).hexdigest() != PARENT_SHA256:
        raise ValueError(f"parent SHA-256 mismatch for {parent_path}")

    try:
        import golaxy_rank1_6_sampling_continuation as parent_protocol

        with tempfile.TemporaryDirectory(prefix="golaxy-rank1-6-final-parent-") as directory:
            snapshot = Path(directory) / parent_path.name
            snapshot.write_bytes(parent_bytes)
            parent = parent_protocol.campaign_summary(snapshot)
    except (OSError, ValueError) as exc:
        raise ValueError(f"invalid parent campaign {parent_path}: {exc}") from exc
    if parent.header.get("protocol") != "golaxy-humansl-rank1-6-sampling-continuation-v3":
        raise ValueError("parent campaign must use golaxy-humansl-rank1-6-sampling-continuation-v3")
    if (
        parent.stopped
        or not isinstance(parent.action, parent_protocol.CampaignDecision)
        or parent.action.status != "completed"
        or parent.unknown_charged_attempts
    ):
        raise ValueError("parent campaign must be completed with no unknown charged attempts")
    if sum(row.get("type") == "result" for row in parent.records) != 5:
        raise ValueError("parent campaign must contain exactly five continuation results")
    identity = parent.header.get("identity_snapshot")
    if not isinstance(identity, dict):
        raise ValueError("parent campaign lacks a valid identity_snapshot")
    return identity
