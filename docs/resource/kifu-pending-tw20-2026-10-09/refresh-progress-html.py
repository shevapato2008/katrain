"""Refresh the offline progress page from actual PROD batch 588 or 589 captures."""

import argparse
import gzip
import json
import re
import subprocess
import sys
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
HTML = ROOT / "docs/resource/kifu-five-language-progress-2026-10-05.html"
SNAPSHOT = HERE / "PROD-approved-name-snapshot.json.gz"
MISSING_KO = HERE / "PROD-old-ko-proof-gap-readonly.json"
LIVE_TW = HERE / "PROD-tw20-names-live.json"
LIVE_589 = HERE / "PROD-new589-names-live.json"
ACTUAL = HERE / "PROD-progress-actual.json"
ACTUAL_589 = HERE / "PROD-progress-after589-actual.json"
BASE = HERE / "PROD-base-entity-coverage-actual.json"
HISTORICAL = HERE / "PROD-ret163-progress-baseline.json"
PRIMARY = {"cn", "tw", "jp", "ko", "en"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--after589", action="store_true", help="Include the 20 qualified partial cells from batch 589")
    args = parser.parse_args()
    statistics_path = HERE / ("PROD-progress-html-after589-statistics.json" if args.after589
                              else "PROD-progress-html-statistics.json")
    catalog_path = HERE / ("PROD-progress-html-after589-catalog.json" if args.after589
                           else "PROD-progress-html-catalog.json")
    match = re.search(r'<script id="data" type="application/json">(.*?)</script>', HTML.read_text(), re.S)
    if not match:
        raise ValueError("current progress page has no embedded catalog")
    previous = json.loads(match.group(1))
    catalog = previous["catalog"]
    before = catalog["names"]["player"]
    snapshot = json.load(gzip.open(SNAPSHOT, "rt"))
    qualified_players = {
        (row["owner"]["id"], row["lang"], row["display_name"])
        for row in snapshot if row["owner"]["kind"] == "player" and row["lang"] in PRIMARY
    }
    qualified_events = {
        (row["owner"]["id"], row["lang"], row["display_name"])
        for row in snapshot if row["owner"]["kind"] == "event" and row["lang"] in PRIMARY
    }
    old_players = {(row["owner_id"], row["lang"], row["display_name"]) for row in before}
    old_events = {
        (row["owner_id"], row["lang"], row["display_name"])
        for row in catalog["names"]["event"]
    }
    gaps = json.loads(MISSING_KO.read_text())["rows"]
    missing_ko = {(row["player_id"], "ko", row["ko_display_name"]) for row in gaps}
    live = json.loads(LIVE_TW.read_text())["rows"]
    bundle = json.load(gzip.open(HERE / "PROD-unsigned-bundle.json.gz", "rt"))
    expected = {(row["owner"]["id"], row["lang"], row["display_name"]) for row in bundle["candidates"]}
    actual_tw = {(row["owner_id"], row["lang"], row["display_name"]) for row in live}
    if len(live) != 20 or actual_tw != expected or any(row["status"] != "verified" for row in live):
        raise ValueError("live TW20 names differ from applied candidates")
    new589 = json.loads(LIVE_589.read_text())["rows"] if args.after589 else []
    expected589 = {(row["owner_id"], row["lang"], row["display_name"]) for row in new589}
    if args.after589:
        bundle589 = json.load(gzip.open(HERE / "PROD-589-unsigned-bundle.json.gz", "rt"))
        if len(new589) != 20 or expected589 != {
            (row["owner"]["id"], row["lang"], row["display_name"])
            for row in bundle589["candidates"]
        } or any(row["status"] != "verified" for row in new589):
            raise ValueError("live batch 589 cells differ from applied candidates")
    allowed_extra = (missing_ko, actual_tw, actual_tw | expected589) if args.after589 else (missing_ko, actual_tw)
    if len(missing_ko) != 28 or old_players - qualified_players not in allowed_extra:
        raise ValueError("existing HTML differs from qualified names beyond the known proof gaps or TW20")
    if qualified_players - old_players or old_events != qualified_events:
        raise ValueError("existing HTML omits other qualified names or differs in events")
    catalog["names"]["player"] = sorted(
        [row for row in before if (row["owner_id"], row["lang"], row["display_name"])
         not in missing_ko | actual_tw | expected589]
        + [{key: row[key] for key in ("owner_id", "lang", "display_name", "status", "reference_url", "decision_kind")}
           for row in live + new589],
        key=lambda row: (row["owner_id"], row["lang"]),
    )
    after = {(row["owner_id"], row["lang"], row["display_name"]) for row in catalog["names"]["player"]}
    if after != qualified_players | actual_tw | expected589 or len(after) != len(catalog["names"]["player"]):
        raise ValueError("refreshed player catalog is not the qualified post-batch set")

    stats = json.loads((ACTUAL_589 if args.after589 else ACTUAL).read_text())
    direct = json.loads(BASE.read_text())
    if len(stats["players_done"]) != stats["players_done_count"] or len(stats["events_done"]) != stats["events_done_count"]:
        raise ValueError("actual completed lists disagree with counts")
    if direct["player_qualified_ids"] != stats["players_done_count"] or direct["event_qualified_ids"] != stats["events_done_count"]:
        raise ValueError("direct entity count used different qualified IDs")
    stats["base_entity_names_games"] = direct["base_entity_names_games"]
    stats["base_entity_names_games_pct"] = round(100 * direct["base_entity_names_games"] / stats["games"], 4)
    stats["event_type_names_games"] = direct["qualified_event_id_games"]
    stats["event_type_names_games_pct"] = round(100 * direct["qualified_event_id_games"] / stats["games"], 4)
    stats["unqualified_legacy_ko_count"] = len(missing_ko)
    stats["coverage_method"] = (
        ("批次589后 katrain-kifu-importer:jp-original-display-prod-20261009-r2 " if args.after589
         else "批次588后 katrain-kifu-importer:verified-cn-display-prod-20261008-r1 ")
        +
        "的 strict_slot_approvals；旧报表口径不直接可比"
    )
    historical = json.loads(HISTORICAL.read_text())
    stats["historical_full_display_games"] = historical["complete_five_lang_display_games"]
    stats["historical_full_display_games_pct"] = historical["complete_five_lang_display_games_pct"]
    statistics_path.write_text(json.dumps(stats, ensure_ascii=False, sort_keys=True, indent=2) + "\n")
    catalog_path.write_text(json.dumps(catalog, ensure_ascii=False, sort_keys=True) + "\n")
    subprocess.run(
        [sys.executable, str(ROOT / "scripts/render_kifu_name_progress.py"),
         "--statistics", str(statistics_path), "--catalog", str(catalog_path), "--output", str(HTML)],
        check=True,
    )
    print(f"refreshed HTML: {stats['players_done_count']} players, {stats['complete_five_lang_display_games']} strict cards")


if __name__ == "__main__":
    main()
