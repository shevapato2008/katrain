"""Six-game extension for each rank_1d..rank_6d native-sampling matchup.

The completed four-game campaign remains immutable. This child protocol adds
six alternating-color games per live matchup, producing ten total when the
parent and child evidence are combined.
"""

from __future__ import annotations

import hashlib
import tempfile
from pathlib import Path


_BASE_SOURCE = Path(__file__).with_name("golaxy_rank1_6_sampling_campaign.py")
exec(compile(_BASE_SOURCE.read_bytes(), str(_BASE_SOURCE), "exec"), globals())

LEDGER_PROTOCOL = "golaxy-humansl-rank1-6-sampling-extension-v2"
VALID_SLOTS_PER_STAGE = 6
PARENT_PATH = (
    Path(__file__).resolve().parent
    / "results/golaxy_rank1_6_sampling_campaign_20260802/campaign_v1.jsonl"
)
PARENT_SHA256 = "9c2fc8c55705687ff3107e3940717b5fa22de996851f1e1274a018df1ea62be7"


def _read_parent():
    """Verify the exact completed four-game campaign and inherit its identity."""
    parent_path = Path(PARENT_PATH).resolve()
    try:
        parent_bytes = parent_path.read_bytes()
    except OSError as exc:
        raise ValueError(f"cannot read parent campaign {parent_path}: {exc}") from exc
    if hashlib.sha256(parent_bytes).hexdigest() != PARENT_SHA256:
        raise ValueError(f"parent SHA-256 mismatch for {parent_path}")

    try:
        import golaxy_rank1_6_sampling_campaign as parent_protocol

        with tempfile.TemporaryDirectory(prefix="golaxy-rank1-6-extension-parent-") as directory:
            snapshot = Path(directory) / parent_path.name
            snapshot.write_bytes(parent_bytes)
            parent = parent_protocol.campaign_summary(snapshot)
    except (OSError, ValueError) as exc:
        raise ValueError(f"invalid parent campaign {parent_path}: {exc}") from exc
    if parent.header.get("protocol") != "golaxy-humansl-rank1-6-sampling-v1":
        raise ValueError("parent campaign must use golaxy-humansl-rank1-6-sampling-v1")
    if (
        parent.stopped
        or not isinstance(parent.action, parent_protocol.CampaignDecision)
        or parent.action.status != "completed"
    ):
        raise ValueError("parent campaign must be completed and not stopped")
    identity = parent.header.get("identity_snapshot")
    if not isinstance(identity, dict):
        raise ValueError("parent campaign lacks a valid identity_snapshot")
    return identity
