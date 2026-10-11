"""Refresh the offline progress page from actual PROD batch-590 outputs."""

import json
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path


D = Path(__file__).parent
ROOT = D.parents[2]
HTML = ROOT / "docs/resource/kifu-five-language-progress-2026-10-05.html"
OLD = D.parent / "kifu-pending-tw20-2026-10-09"
PRIMARY = {"cn", "tw", "jp", "ko", "en"}


def main():
    page = HTML.read_text()
    match = re.search(r'<script id="data" type="application/json">(.*?)</script>', page, re.S)
    if not match:
        raise ValueError("current offline progress page lacks embedded data")
    embedded = json.loads(match.group(1))
    if embedded["statistics"]["applied_batch_id"] != 589:
        raise ValueError("offline progress page is not the post-589 baseline")
    stats = json.loads((D / "590-PROD-progress-actual.json").read_text())
    audit = json.loads((D / "590-PROD-progress-audit.json").read_text())
    names = json.loads((D / "590-PROD-live-ko-names.json").read_text())["rows"]
    approved = json.loads((D / "PROD-ko20-candidates.approved.json").read_text())
    expected = {(row["owner"]["id"], row["lang"], row["display_name"]) for row in approved}
    actual = {(row["owner_id"], row["lang"], row["display_name"]) for row in names}
    gaps = json.loads((OLD / "PROD-old-ko-proof-gap-readonly.json").read_text())["rows"]
    all_gaps = {(row["player_id"], "ko", row["ko_display_name"]) for row in gaps}
    if (len(names) != 20 or actual != expected or not actual <= all_gaps
        or audit["bundle_sha256"] != "940e48a38af5fdba5bb6b17ebc6eda3c88cd1a32917b664797af243e3fae10f1"):
        raise ValueError("actual batch-590 names, proof-gap scope, or bundle hash differs")
    catalog = embedded["catalog"]
    before = catalog["names"]["player"]
    existing = {(row["owner_id"], row["lang"], row["display_name"]) for row in before}
    if existing & actual:
        raise ValueError("offline page already contains one of the 20 restored KO names")
    catalog["names"]["player"] = sorted(
        before + [{key: row[key] for key in
                   ("owner_id", "lang", "display_name", "status", "reference_url", "decision_kind")}
                  for row in names],
        key=lambda row: (row["owner_id"], row["lang"]),
    )
    completed = defaultdict(set)
    for row in catalog["names"]["player"]:
        if row["lang"] in PRIMARY:
            completed[row["owner_id"]].add(row["lang"])
    actual_done = {owner_id for owner_id, langs in completed.items() if langs == PRIMARY}
    expected_done = {row["player_id"] for row in stats["players_done"]}
    if actual_done != expected_done or len(actual_done) != 1667 or len(all_gaps - actual) != 8:
        raise ValueError("refreshed catalog does not reproduce actual native 590 completion")
    old_stats = embedded["statistics"]
    if (old_stats["event_type_names_games"] != 105977
        or stats["events_done_count"] != old_stats["events_done_count"]):
        raise ValueError("event baseline changed")
    for key in ("event_type_names_games", "event_type_names_games_pct",
                "historical_full_display_games", "historical_full_display_games_pct"):
        stats[key] = old_stats[key]
    (D / "590-PROD-progress-html-statistics.json").write_text(
        json.dumps(stats, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    )
    (D / "590-PROD-progress-html-catalog.json").write_text(
        json.dumps(catalog, ensure_ascii=False, sort_keys=True) + "\n"
    )
    subprocess.run(
        [sys.executable, str(ROOT / "scripts/render_kifu_name_progress.py"),
         "--statistics", str(D / "590-PROD-progress-html-statistics.json"),
         "--catalog", str(D / "590-PROD-progress-html-catalog.json"),
         "--output", str(HTML)], check=True,
    )
    print("refreshed post-590 HTML", len(actual_done), "complete players",
          stats["complete_five_lang_display_games"], "strict complete cards")


if __name__ == "__main__":
    main()
