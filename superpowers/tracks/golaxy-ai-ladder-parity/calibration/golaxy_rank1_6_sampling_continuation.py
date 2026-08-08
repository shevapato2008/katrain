"""First continuation after the rank_1d..rank_6d extension stopped remotely.

The stopped parent already contains one added rank_3d@1 vs Golaxy 3d game
with HumanSL as Black. This child adds the five missing games, White first.
"""

from __future__ import annotations

import hashlib
import tempfile
from pathlib import Path


_BASE_SOURCE = Path(__file__).with_name("golaxy_rank1_6_sampling_extension.py")
exec(compile(_BASE_SOURCE.read_bytes(), str(_BASE_SOURCE), "exec"), globals())

LEDGER_PROTOCOL = "golaxy-humansl-rank1-6-sampling-continuation-v3"
VALID_SLOTS_PER_STAGE = 5
FIRST_HUMANSL_COLOR = "W"
STAGES = (("sampling_3d", "rank_3d@1", 1700),)
STAGE_ORDER = tuple(stage for stage, _player, _level in STAGES)
PARENT_PATH = (
    Path(__file__).resolve().parent
    / "results/golaxy_rank1_6_sampling_extension_20260802/campaign_v2.jsonl"
)
PARENT_SHA256 = "e40e0c4a63b5861c05d5deebb14725d3f6abda6bbb846f4a46dc938c75e34ba9"


def _read_parent():
    """Verify the exact stopped extension and inherit its engine identity."""
    parent_path = Path(PARENT_PATH).resolve()
    try:
        parent_bytes = parent_path.read_bytes()
    except OSError as exc:
        raise ValueError(f"cannot read parent campaign {parent_path}: {exc}") from exc
    if hashlib.sha256(parent_bytes).hexdigest() != PARENT_SHA256:
        raise ValueError(f"parent SHA-256 mismatch for {parent_path}")

    try:
        import golaxy_rank1_6_sampling_extension as parent_protocol

        with tempfile.TemporaryDirectory(prefix="golaxy-rank1-6-continuation-parent-") as directory:
            snapshot = Path(directory) / parent_path.name
            snapshot.write_bytes(parent_bytes)
            parent = parent_protocol.campaign_summary(snapshot)
    except (OSError, ValueError) as exc:
        raise ValueError(f"invalid parent campaign {parent_path}: {exc}") from exc
    if parent.header.get("protocol") != "golaxy-humansl-rank1-6-sampling-extension-v2":
        raise ValueError("parent campaign must use golaxy-humansl-rank1-6-sampling-extension-v2")
    if not parent.stopped or parent.unknown_charged_attempts:
        raise ValueError("parent campaign must be stopped with no unknown charged attempts")
    if sum(row.get("type") == "result" for row in parent.records) != 31:
        raise ValueError("parent campaign must contain exactly 31 valid extension results")
    identity = parent.header.get("identity_snapshot")
    if not isinstance(identity, dict):
        raise ValueError("parent campaign lacks a valid identity_snapshot")
    return identity
