#!/usr/bin/env python3
"""
Scan data/life-n-death/ directory and generate index.json

Usage: python scripts/generate_tsumego_index.py
"""

import json
import sys
from pathlib import Path

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from katrain.core.sgf_parser import SGF


DATA_DIR = Path("data/life-n-death")
OUTPUT_FILE = DATA_DIR / "index.json"


def parse_category(comment: str) -> str:
    """Extract problem type from SGF comment."""
    if "吃子" in comment:
        return "capturing"
    elif "对杀" in comment:
        return "semeai"
    elif "手筋" in comment:
        return "tesuji"
    elif "官子" in comment:
        return "endgame"
    elif "布局" in comment:
        return "opening"
    elif "中盘" in comment:
        return "midgame"
    else:
        return "life-death"


def extract_metadata(sgf_path: Path, level: str) -> dict:
    """Extract problem metadata from SGF file."""
    root = SGF.parse_file(str(sgf_path))

    problem_id = sgf_path.stem
    comment = root.get_property("C", "") or ""
    gc = root.get_property("GC", "") or ""
    pl = root.get_property("PL", "B") or "B"

    return {
        "id": problem_id,
        "level": level.lower(),
        "category": parse_category(comment + gc),
        "hint": "黑先" if pl.upper() == "B" else "白先",
        "boardSize": root.board_size[0],
        "initialBlack": root.get_list_property("AB", []),
        "initialWhite": root.get_list_property("AW", []),
        "source": root.get_property("SO", ""),
    }


def generate_index():
    """Generate index.json from SGF files."""
    index = {"levels": {}, "problems": {}}

    for level_dir in sorted(DATA_DIR.iterdir()):
        if not level_dir.is_dir() or level_dir.name.startswith("."):
            continue

        level = level_dir.name.lower()
        index["levels"][level] = {"categories": {}}

        for sgf_file in sorted(level_dir.glob("*.sgf")):
            try:
                meta = extract_metadata(sgf_file, level)
            except Exception as e:
                print(f"  ERROR parsing {sgf_file}: {e}")
                continue

            problem_id = meta["id"]
            category = meta["category"]

            # Add to problems dict (by ID)
            index["problems"][problem_id] = meta

            # Add to levels structure (by level/category)
            if category not in index["levels"][level]["categories"]:
                index["levels"][level]["categories"][category] = []
            index["levels"][level]["categories"][category].append(problem_id)

    # Write output
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)

    # Summary
    print(f"Generated {OUTPUT_FILE}")
    for level, data in index["levels"].items():
        total = sum(len(ids) for ids in data["categories"].values())
        cats = ", ".join(f"{k}:{len(v)}" for k, v in data["categories"].items())
        print(f"  {level.upper()}: {total} problems ({cats})")
    print(f"  Total: {len(index['problems'])} problems")


if __name__ == "__main__":
    generate_index()
