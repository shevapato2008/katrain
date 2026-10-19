"""Read-only identity leads for all parsed kifu player groups.

The output is a research queue, not an identity approval or a database import.
Every group in the frozen inventory is emitted, including unresolved groups.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
import gzip
import hashlib
import json
from pathlib import Path
import re
import sys
import time
from urllib.parse import urlencode
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from katrain.web.kifu.name_parse import parse_player  # noqa: E402

API = "https://www.wikidata.org/w/api.php"
USER_AGENT = "KifuPlayerNameResearch/0.1 (read-only name translation research)"
GO_DESCRIPTION = re.compile(r"(?:\bgo\s+player\b|\bgo\s+professional\b|\bweiqi\b|\bbaduk\b|囲碁棋士|围棋(?:棋手|选手)|圍棋(?:棋手|選手)|바둑\s*기사)", re.I)
NON_PERSON = {"unknown", "black", "white", "?", "-", "none"}


def read_json(path: Path):
    raw = path.read_bytes()
    return json.loads(gzip.decompress(raw) if path.suffix == ".gz" else raw), hashlib.sha256(raw).hexdigest()


def api(params: dict, *, retries: int = 1):
    query = urlencode({**params, "format": "json"})
    url = f"{API}?{query}"
    for attempt in range(retries):
        try:
            with urlopen(Request(url, headers={"User-Agent": USER_AGENT}), timeout=6) as response:
                return json.load(response), url
        except Exception:
            if attempt == retries - 1:
                raise
            time.sleep(2 ** attempt)


def groups(inventory: dict):
    counts = defaultdict(int)
    spellings = defaultdict(list)
    for row in inventory["scopes"]["all"]["values"]["player"]:
        parsed = parse_player(row["value"], None)
        key = (parsed.category, parsed.name)
        counts[key] += row["occurrences"]
        spellings[key].append([row["value"], row["occurrences"]])
    return [
        {"rank": rank, "name": name, "category": category, "slots": slots,
         "raw_spellings": sorted(spellings[(category, name)], key=lambda x: -x[1])}
        for rank, ((category, name), slots) in enumerate(
            sorted(counts.items(), key=lambda item: (-item[1], item[0][1].encode("utf-8"), item[0][0])), 1)
    ]


def search_lead(name: str):
    result, url = api({"action": "wbsearchentities", "search": name, "language": "zh", "uselang": "en", "limit": 10})
    hits = [
        {"qid": item["id"], "label": item.get("label"), "description": item.get("description"),
         "match": item.get("match"), "entity_url": f"https://www.wikidata.org/wiki/{item['id']}",
         "go_description": bool(GO_DESCRIPTION.search(item.get("description") or ""))}
        for item in result.get("search", [])
    ]
    go_hits = [hit for hit in hits if hit["go_description"]]
    return {"search_url": url, "hits": hits, "candidate_qids": [hit["qid"] for hit in go_hits]}


def roster_leads(path: Path):
    """Reuse frozen official-roster searches; none establishes game identity."""
    if not path.exists():
        return {}
    rows = json.loads(path.read_text(encoding="utf-8"))
    result = {}
    for row in rows:
        hits = [
            {"qid": hit["id"], "label": hit.get("label"), "description": hit.get("description"),
             "match": hit.get("match"), "entity_url": f"https://www.wikidata.org/wiki/{hit['id']}",
             "go_description": bool(GO_DESCRIPTION.search(hit.get("description") or ""))}
            for hit in row["hits"]
        ]
        qids = [hit["qid"] for hit in hits if hit["go_description"]]
        result[row["name"]] = {
            "roster_id": row["roster_id"], "roster_birthdate": row.get("birthdate"),
            "roster_source_url": "https://www.weiqi.org.cn/player/professional",
            "cached_search_response_sha256": row["sha256"], "hits": hits, "candidate_qids": qids,
        }
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", type=Path, default=Path("/tmp/kifu-five-prod-inventory-post7.json.gz"))
    parser.add_argument("--catalog", type=Path, default=Path("docs/resource/kifu-catalog-snapshot-2026-10-04.json"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=0, help="live API searches among highest-frequency uncached groups")
    parser.add_argument("--delay", type=float, default=0.15)
    parser.add_argument("--roster-summary", type=Path,
                        default=Path.home() / ".local/share/kifu-name-audit/2026-10-03/china-professional-roster/wikidata-all678/summary.json")
    args = parser.parse_args(argv)
    inventory, inventory_sha = read_json(args.inventory)
    catalog, catalog_sha = read_json(args.catalog)
    rows = groups(inventory)
    if len(rows) != 6433 or len(catalog["kifu_players"]) < 880:
        raise ValueError("frozen inventory or catalog does not match expected scope")
    catalog_names = defaultdict(list)
    for player in catalog["kifu_players"]:
        catalog_names[player["canonical_name"]].append(player["id"])
    for row in rows:
        row["catalog_exact_name_ids"] = catalog_names.get(row["name"], [])
        row["group_key"] = [row["category"], row["name"]]
        row["raw_values"] = [{"raw_value": raw, "slots": count} for raw, count in row["raw_spellings"]]
        row["candidate_chinese_name"] = row["name"] if row["category"] == "readable_unlinked" else None
        row["match_status"] = "unmatched"
        row["status"] = "pending_search"
        if row["category"] != "readable_unlinked" or row["name"].strip().casefold() in NON_PERSON:
            row["status"] = "non_person_or_unreadable"
    frozen_roster = roster_leads(args.roster_summary)
    for row in rows:
        if row["status"] != "pending_search" or row["name"] not in frozen_roster:
            continue
        row.update(frozen_roster[row["name"]])
        qids = row["candidate_qids"]
        row["status"] = "roster_single_go_candidate" if len(qids) == 1 else (
            "roster_ambiguous_go_candidates" if qids else "roster_no_go_candidate")
        row["match_status"] = "ambiguous" if len(qids) > 1 else "unconfirmed"
    if args.output.exists():
        prior = json.loads(args.output.read_text(encoding="utf-8"))
        if (prior.get("scope", {}).get("inventory_sha256") != inventory_sha
                or prior.get("scope", {}).get("catalog_sha256") != catalog_sha):
            raise ValueError("existing output snapshot hash differs; choose a new output path")
        saved = {tuple(row["group_key"]): row for row in prior["groups"]
                 if row["status"] in ("single_go_search_candidate", "ambiguous_go_candidates",
                                      "no_go_search_candidate", "search_error")}
        for row in rows:
            old = saved.get(tuple(row["group_key"]))
            if row["status"] == "pending_search" and old:
                row.update({key: old[key] for key in ("status", "match_status", "search_url", "hits", "candidate_qids", "error")
                            if key in old})
    live_searched = 0
    for row in rows:
        if live_searched >= args.limit:
            break
        if row["status"] != "pending_search":
            continue
        live_searched += 1
        try:
            lead = search_lead(row["name"])
        except Exception as exc:
            row["status"] = "search_error"
            row["error"] = str(exc)
            continue
        row.update(lead)
        qids = lead["candidate_qids"]
        row["status"] = "single_go_search_candidate" if len(qids) == 1 else ("ambiguous_go_candidates" if qids else "no_go_search_candidate")
        row["match_status"] = "ambiguous" if len(qids) > 1 else "unconfirmed"
        time.sleep(args.delay)
    for row in rows:
        row["candidates"] = [
            {"qid": qid, "entity_url": f"https://www.wikidata.org/wiki/{qid}",
             "evidence_url": row.get("search_url") or row.get("roster_source_url"),
             "candidate_chinese_name": row["candidate_chinese_name"], "match_status": row["match_status"]}
            for qid in row.get("candidate_qids", [])
        ]
    output = {"scope": {"inventory_sha256": inventory_sha, "catalog_sha256": catalog_sha,
                         "game_count": inventory["counts"]["all"], "player_group_count": len(rows),
                         "player_slot_count": sum(row["slots"] for row in rows), "live_search_count": live_searched,
                         "roster_cached_group_count": sum("roster_id" in row for row in rows)},
              "policy": "Research leads only. Search uniqueness, labels, and exact catalog name do not approve identity or game bindings.",
              "groups": rows}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as stream:
        json.dump(output, stream, ensure_ascii=False, separators=(",", ":"))
        stream.write("\n")
    from collections import Counter
    print(json.dumps(dict(Counter(row["status"] for row in rows)), ensure_ascii=False))


if __name__ == "__main__":
    main()
