#!/usr/bin/env python3
"""Strict serial runner for the first rank_1d..rank_6d continuation."""

from __future__ import annotations

import sys
from pathlib import Path


_BASE_SOURCE = Path(__file__).with_name("run_golaxy_rank1_6_sampling_extension.py")
_CONTINUATION_ENTRYPOINT_NAME = __name__
__name__ = "_golaxy_rank1_6_sampling_continuation_runner_base"
sys.modules[__name__] = sys.modules[_CONTINUATION_ENTRYPOINT_NAME]
exec(compile(_BASE_SOURCE.read_bytes(), str(_BASE_SOURCE), "exec"), globals())
__name__ = _CONTINUATION_ENTRYPOINT_NAME

import golaxy_rank1_6_sampling_continuation as golaxy_rank1_6_sampling_continuation


golaxy_sampling_campaign = golaxy_rank1_6_sampling_continuation


if __name__ == "__main__":
    raise SystemExit(main())
