"""Report non-Chinese event displays from a frozen aggregate and display asset.

The aggregate has no SGF bytes, so album overrides are counted only if their
recorded raw text still belongs to an unlinked aggregate group. Runtime SHA
guards remain authoritative for an individual album.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import gzip
import json
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CAPTURE = ROOT / "docs/resource/kifu-event-display-weighted-prod-capture-2026-10-04.json"
DEFAULT_ASSET = ROOT / "katrain/web/kifu/data/cn_first_pass_2026-10-05.json.gz"
HAN = re.compile(r"[\u3400-\u9fff]")


def read_json(path: Path):
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as stream:
        return json.load(stream)


def build_report(capture: dict, asset: dict) -> dict:
    if asset.get("format") != "kifu-cn-first-pass-v1":
        raise ValueError("Unexpected display asset format")

    canonical = {row["id"]: row["canonical_name"] for row in capture["events"]}
    displays = {(raw, name): display for raw, name, display in asset["event_raw_canonical"]}
    overrides = Counter(raw for _, raw, _, _ in asset["event_album_sgf"])
    unlinked_games = Counter()
    for row in capture["raw_groups"]:
        if row["event_id"] is None:
            unlinked_games[row["raw"]] += row["games"]
    for raw, count in overrides.items():
        if count > unlinked_games[raw]:
            raise ValueError(f"Album overrides exceed unlinked aggregate games for {raw!r}")

    raw_rows = []
    core_counts = Counter()
    core_raw_counts = defaultdict(int)
    category_counts = Counter()
    covered_games = 0
    override_games = 0
    for row in capture["raw_groups"]:
        raw, event_id = row["raw"], row["event_id"]
        name = canonical.get(event_id)
        display = displays.get((raw, name), name if name is not None else raw)
        if display and HAN.search(display):
            covered_games += row["games"]
            continue

        applied_overrides = overrides[raw] if event_id is None else 0
        remaining = row["games"] - applied_overrides
        if remaining < 0:
            raise ValueError(f"Negative residual games for {raw!r}")
        override_games += applied_overrides
        if not remaining:
            continue
        core = row["core"] or raw
        category = row["category"] or "null_event"
        raw_rows.append(
            {
                "raw": raw,
                "core": core,
                "category": category,
                "event_id": event_id,
                "display": display,
                "games": remaining,
                "overridden_album_games": applied_overrides,
            }
        )
        core_counts[(core, category)] += remaining
        core_raw_counts[(core, category)] += 1
        category_counts[category] += remaining

    raw_rows.sort(key=lambda r: (-r["games"], r["raw"] or ""))
    cores = [
        {"core": core, "category": category, "games": games, "raw_groups": core_raw_counts[(core, category)]}
        for (core, category), games in core_counts.items()
    ]
    cores.sort(key=lambda r: (-r["games"], r["core"] or ""))
    total_games = capture["totals"]["games"]
    nonblank = capture["totals"]["nonblank_event"]
    residual = sum(category_counts.values())
    if covered_games + override_games + residual != total_games:
        raise ValueError("Aggregate games do not reconcile")
    return {
        "format": "kifu-cn-event-residual-v1",
        "capture_meta": capture["meta"],
        "asset_generated_date": asset["generated_date"],
        "headlines": {
            "games": total_games,
            "nonblank_event_games": nonblank,
            "han_display_games": covered_games + override_games,
            "residual_nonhan_or_null_games": residual,
            "residual_nonhan_nonblank_games": residual - category_counts["null_event"],
            "null_event_games": category_counts["null_event"],
            "asset_album_overrides_total": len(asset["event_album_sgf"]),
            "asset_album_overrides_counted": override_games,
            "asset_album_overrides_already_han": len(asset["event_album_sgf"]) - override_games,
            "residual_raw_groups": len(raw_rows),
            "residual_core_groups": len(cores),
            "category_games": dict(sorted(category_counts.items())),
        },
        "raws": raw_rows,
        "cores": cores,
        "limitation": "Album overrides are counted from the asset and matching raw aggregate; their runtime SGF SHA guards cannot be rechecked without SGF bytes.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture", type=Path, default=DEFAULT_CAPTURE)
    parser.add_argument("--asset", type=Path, default=DEFAULT_ASSET)
    parser.add_argument("--output", type=Path, help="Write full JSON here; otherwise write to stdout")
    args = parser.parse_args()
    report = build_report(read_json(args.capture), read_json(args.asset))
    serialized = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(serialized, encoding="utf-8")
        print(json.dumps(report["headlines"], ensure_ascii=False))
    else:
        print(serialized, end="")


if __name__ == "__main__":
    main()
