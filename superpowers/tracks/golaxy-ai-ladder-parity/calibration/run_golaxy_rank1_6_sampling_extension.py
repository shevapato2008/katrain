#!/usr/bin/env python3
"""Strict serial runner for the six-game rank_1d..rank_6d extension."""

from __future__ import annotations

import sys
from pathlib import Path


_BASE_SOURCE = Path(__file__).with_name("run_golaxy_rank1_6_sampling_campaign.py")
_EXTENSION_ENTRYPOINT_NAME = __name__
__name__ = "_golaxy_rank1_6_sampling_extension_runner_base"
sys.modules[__name__] = sys.modules[_EXTENSION_ENTRYPOINT_NAME]
exec(compile(_BASE_SOURCE.read_bytes(), str(_BASE_SOURCE), "exec"), globals())
__name__ = _EXTENSION_ENTRYPOINT_NAME

import golaxy_rank1_6_sampling_extension as golaxy_rank1_6_sampling_extension


golaxy_sampling_campaign = golaxy_rank1_6_sampling_extension


if __name__ == "__main__":
    raise SystemExit(main())
