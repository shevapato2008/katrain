#!/usr/bin/env python3
"""Strict serial runner for the final 24-game rank continuation."""

from __future__ import annotations

import sys
from pathlib import Path


_BASE_SOURCE = Path(__file__).with_name("run_golaxy_rank1_6_sampling_continuation.py")
_FINAL_CONTINUATION_ENTRYPOINT_NAME = __name__
__name__ = "_golaxy_rank1_6_sampling_final_continuation_runner_base"
sys.modules[__name__] = sys.modules[_FINAL_CONTINUATION_ENTRYPOINT_NAME]
exec(compile(_BASE_SOURCE.read_bytes(), str(_BASE_SOURCE), "exec"), globals())
__name__ = _FINAL_CONTINUATION_ENTRYPOINT_NAME

import golaxy_rank1_6_sampling_final_continuation as golaxy_rank1_6_sampling_final_continuation


golaxy_sampling_campaign = golaxy_rank1_6_sampling_final_continuation


if __name__ == "__main__":
    raise SystemExit(main())
