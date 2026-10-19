"""Refresh the offline progress page from actual PROD batch-592 outputs."""

import json
import re
import subprocess
import sys
import tempfile
from collections import defaultdict
from pathlib import Path


D = Path(__file__).parent
ROOT = D.parents[2]
HTML = ROOT / "docs/resource/kifu-five-language-progress-2026-10-05.html"
PRIOR = D.parent / "kifu-next-throughput-2026-10-09"
PRIMARY = {"cn", "tw", "jp", "ko", "en"}


def main():
    page = HTML.read_text()
    match = re.search(r'<script id="data" type="application/json">(.*?)</script>', page, re.S)
    if not match:
        raise ValueError("current offline progress page lacks embedded data")
    embedded = json.loads(match.group(1))
    if embedded["statistics"]["applied_batch_id"] != 591:
        raise ValueError("offline progress page is not the post-591 baseline")
    stats = json.loads((D / "592-PROD-progress-actual.json").read_text())
    audit = json.loads((D / "592-PROD-progress-audit.json").read_text())
    names = json.loads((D / "592-PROD-live-target-names.json").read_text())["rows"]
    bundle = json.loads(__import__("gzip").open(D / "PROD-final20-bundle.json.gz", "rt").read())
    expected = {(row["owner"]["id"], row["lang"], row["display_name"]) for row in bundle["candidates"]}
    actual = {(row["owner_id"], row["lang"], row["display_name"]) for row in names}
    if (len(names) != 20 or actual != expected or audit["batch_id"] != 592
        or audit["bundle_sha256"] != json.loads((D / "final20-execution-proposed-manifest.json").read_text())["PROD"]["bundle_sha256"]):
        raise ValueError("actual batch-592 names or bundle hash differs")
    catalog = embedded["catalog"]
    before = catalog["names"]["player"]
    existing = {(row["owner_id"], row["lang"]) for row in before}
    if existing & {(owner, lang) for owner, lang, _ in actual}:
        raise ValueError("offline page already contains a batch-592 target name cell")
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
    if actual_done != expected_done or len(actual_done) != 1707:
        raise ValueError("refreshed catalog does not reproduce actual native 592 completion")
    old_stats = embedded["statistics"]
    if (old_stats["event_type_names_games"] != 105977
        or stats["events_done_count"] != old_stats["events_done_count"]):
        raise ValueError("event baseline changed")
    for key in ("event_type_names_games", "event_type_names_games_pct",
                "historical_full_display_games", "historical_full_display_games_pct"):
        stats[key] = old_stats[key]
    with tempfile.TemporaryDirectory(prefix="kifu-592-progress-") as temp:
        temp = Path(temp)
        statistics = temp / "statistics.json"
        catalog_path = temp / "catalog.json"
        statistics.write_text(json.dumps(stats, ensure_ascii=False, sort_keys=True))
        catalog_path.write_text(json.dumps(catalog, ensure_ascii=False, sort_keys=True))
        subprocess.run(
            [sys.executable, str(ROOT / "scripts/render_kifu_name_progress.py"),
             "--statistics", str(statistics), "--catalog", str(catalog_path),
             "--output", str(HTML)], check=True,
        )
    print("refreshed post-592 HTML", len(actual_done), "complete players",
          stats["complete_five_lang_display_games"], "strict complete cards")


if __name__ == "__main__":
    main()
