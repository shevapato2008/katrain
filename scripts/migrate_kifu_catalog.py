"""Local wrapper for the Web image's kifu catalog migration entry point."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from katrain.web.kifu.migrate_catalog import main


if __name__ == "__main__":
    main()
