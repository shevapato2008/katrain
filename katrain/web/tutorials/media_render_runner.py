"""Owned local rendering child. The task runner controls its process group."""

import json
import sys
from pathlib import Path

from katrain.web.tutorials.media_render import render_video


def main():
    spec = json.loads(Path(sys.argv[1]).read_text())
    spec["audio_path"] = Path(spec["audio_path"])
    spec["output_path"] = Path(spec["output_path"])
    render_video(**spec)


if __name__ == "__main__":
    main()
