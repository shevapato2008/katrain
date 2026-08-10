#!/usr/bin/env python3
"""Compose deterministic same-viewport Galaxy visual comparison evidence."""

import argparse
import re
import sys
from pathlib import Path

from PIL import Image, ImageChops


VIEWPORT_DIRECTORY = re.compile(r"^(?P<width>[1-9]\d*)x(?P<height>[1-9]\d*)$")


def compose_viewport(viewport: Path) -> None:
    reference_path = viewport / "reference.png"
    implementation_path = viewport / "implementation.png"
    for source in (reference_path, implementation_path):
        if not source.is_file():
            raise RuntimeError(f"{viewport.name}: missing required source {source.name}")

    with Image.open(reference_path) as opened_reference, Image.open(implementation_path) as opened_implementation:
        reference = opened_reference.convert("RGBA")
        implementation = opened_implementation.convert("RGBA")
        if reference.size != implementation.size:
            raise RuntimeError(
                f"{viewport.name}: source dimensions differ: "
                f"reference.png={reference.size}, implementation.png={implementation.size}"
            )

        expected = tuple(map(int, viewport.name.split("x")))
        if reference.size != expected:
            raise RuntimeError(
                f"{viewport.name}: source dimensions {reference.size} do not match viewport directory {expected}"
            )

        width, height = reference.size
        side_by_side = Image.new("RGBA", (width * 2, height))
        side_by_side.paste(reference, (0, 0))
        side_by_side.paste(implementation, (width, 0))
        side_by_side.save(viewport / "side-by-side.png")
        Image.blend(reference, implementation, 0.5).save(viewport / "overlay.png")
        ImageChops.difference(reference, implementation).save(viewport / "diff.png")


def compose_visual_root(visual_root: Path) -> int:
    viewport_directories = sorted(
        path for path in visual_root.iterdir() if path.is_dir() and VIEWPORT_DIRECTORY.fullmatch(path.name)
    )
    if not viewport_directories:
        raise RuntimeError(f"no <width>x<height> viewport directories found in {visual_root}")
    for viewport in viewport_directories:
        compose_viewport(viewport)
    return len(viewport_directories)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--visual-root", required=True, type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        count = compose_visual_root(args.visual_root)
    except (OSError, RuntimeError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    print(f"Composed {count} viewport comparisons in {args.visual_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
