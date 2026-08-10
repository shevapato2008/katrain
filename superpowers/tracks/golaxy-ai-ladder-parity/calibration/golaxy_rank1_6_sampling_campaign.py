"""Frozen rank_1d..rank_6d native-sampling screen against Golaxy quasi/full dan levels.

This protocol deliberately reuses the validated append-only machinery from the
completed sampling campaign without changing that historical module's constants.
"""

from __future__ import annotations

import hashlib
import tempfile
from pathlib import Path


_BASE_SOURCE = Path(__file__).with_name("golaxy_sampling_campaign.py")
exec(compile(_BASE_SOURCE.read_bytes(), str(_BASE_SOURCE), "exec"), globals())

LEDGER_PROTOCOL = "golaxy-humansl-rank1-6-sampling-v1"
VALID_SLOTS_PER_STAGE = 4
PARENT_PATH = Path(__file__).resolve().parent / "results/golaxy_sampling_campaign_20260730/campaign_v3.jsonl"
PARENT_SHA256 = "7b8a3fa348f95fa8756824171631b5a9af30895df2f84e0310aa9d437ef8818e"

ALL_MATCHUPS = (
    ("sampling_quasi_1d", "rank_1d@1", 1200, "live"),
    ("sampling_1d", "rank_1d@1", 1300, "live"),
    ("sampling_quasi_2d", "rank_2d@1", 1400, "live"),
    ("sampling_2d", "rank_2d@1", 1500, "live"),
    ("sampling_quasi_3d", "rank_3d@1", 1600, "live"),
    ("sampling_3d", "rank_3d@1", 1700, "live"),
    ("sampling_quasi_4d", "rank_4d@1", 1800, "live"),
    ("sampling_4d", "rank_4d@1", 1900, "live"),
    ("sampling_quasi_5d", "rank_5d@1", 2000, "carry"),
    ("sampling_5d", "rank_5d@1", 2100, "live"),
    ("sampling_quasi_6d", "rank_6d@1", 2200, "carry"),
    ("sampling_6d", "rank_6d@1", 2300, "live"),
)
CARRY_STAGES = tuple(stage for stage, _player, _level, source in ALL_MATCHUPS if source == "carry")
STAGES = tuple((stage, player, level) for stage, player, level, source in ALL_MATCHUPS if source == "live")
STAGE_ORDER = tuple(stage for stage, _player, _level in STAGES)


def _read_parent():
    """Verify the exact completed v3 ledger and inherit its engine identity."""
    parent_path = Path(PARENT_PATH).resolve()
    try:
        parent_bytes = parent_path.read_bytes()
    except OSError as exc:
        raise ValueError(f"cannot read parent campaign {parent_path}: {exc}") from exc
    if hashlib.sha256(parent_bytes).hexdigest() != PARENT_SHA256:
        raise ValueError(f"parent SHA-256 mismatch for {parent_path}")

    try:
        import golaxy_sampling_campaign as parent_protocol

        with tempfile.TemporaryDirectory(prefix="golaxy-rank1-6-parent-") as directory:
            snapshot = Path(directory) / parent_path.name
            snapshot.write_bytes(parent_bytes)
            parent = parent_protocol.campaign_summary(snapshot)
    except (OSError, ValueError) as exc:
        raise ValueError(f"invalid parent campaign {parent_path}: {exc}") from exc
    if parent.header.get("protocol") != "golaxy-humansl-sampling-v1":
        raise ValueError("parent campaign must use golaxy-humansl-sampling-v1")
    if parent.stopped or not isinstance(parent.action, parent_protocol.CampaignDecision) or parent.action.status != "completed":
        raise ValueError("parent campaign must be completed and not stopped")
    identity = parent.header.get("identity_snapshot")
    if not isinstance(identity, dict):
        raise ValueError("parent campaign lacks a valid identity_snapshot")
    return identity
