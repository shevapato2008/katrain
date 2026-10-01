#!/usr/bin/env python3
"""Local entry point for the deployable kifu catalog backfill module."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from katrain.web.kifu.catalog_backfill import backfill_catalog, main, undo_dedup_batch


if __name__ == "__main__":
    raise SystemExit(main())
