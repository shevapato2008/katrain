"""Select the next high-frequency one-hole players from retained read-only snapshots."""

import collections
import datetime
import gzip
import hashlib
import json
from pathlib import Path


D = Path(__file__).parent
ROOT = D.parents[2]
FRESH = ROOT / "docs/resource/kifu-next20-2026-10-09"
OLD = ROOT / "docs/resource/kifu-next-throughput-2026-10-09"
PRIOR = ROOT / "docs/resource/kifu-pending-tw20-2026-10-09"
LANGUAGES = {"cn", "tw", "jp", "ko", "en"}
CURRENT_20 = {4771, 5397, 5297, 6599, 6626, 4235, 6629, 6686, 6259,
              600, 229, 595, 385, 662, 320, 446, 391, 5396, 4276, 4782}
HELD = {
    5244: "Nihon Kiin name contains a fullwidth surname/given space; Igo uses 橋本善美 and requires a separately reviewed identity bridge.",
    4499: "Nihon Kiin fullwidth spaced original and alternate Igo spelling differ; prior positive path was held.",
    6496: "Captured Hangame Korean name uses 타다오; prior generated candidate used 다다오.",
    3900: "Captured Korean Wikipedia pupil article uses 사토우 스나오; prior generated candidate used 사토 스나오.",
}


def read(path):
    with gzip.open(path, "rt") if str(path).endswith(".gz") else open(path) as stream:
        return json.load(stream)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def counts_and_names(capture):
    inventory = capture["inventory"]
    columns = inventory["association_columns"]
    indexes = (columns.index("black_player_id"), columns.index("white_player_id"))
    slots = collections.Counter()
    for row in inventory["album_associations"]:
        for index in indexes:
            if row[index] is not None:
                slots[row[index]] += 1
    names = collections.defaultdict(dict)
    for row in capture["approved_name_snapshot"]:
        if row["owner"]["kind"] == "player" and row["lang"] in LANGUAGES:
            names[row["owner"]["id"]][row["lang"]] = row["display_name"]
    return slots, names


def source_status(player_id, prior, recovery):
    if player_id in recovery:
        rows = recovery[player_id]
        jp = next(row["research"] for row in rows if row["research"]["lang"] == "jp")
        ko = next(row["research"] for row in rows if row["research"]["lang"] == "ko")
        check = next((item for item in jp.get("source_checks", []) if item.get("status") == "found"), None)
        positive = [item for item in ko.get("source_checks", []) if item.get("status") == "found"]
        rejected = [lead for item in ko.get("source_checks", []) for lead in item.get("rejected_leads", [])]
        result = {
            "status": "archived_japanese_source_reusable_for_identity_only",
            "archive": rows[0]["archive"],
            "japanese_source": ({"url": check["url"], "body_sha256": check["body_sha256"],
                                 "http_status": check.get("http_status")}
                                if check else None),
            "archived_ko_scope_status": ko.get("scope_status"),
            "archived_ko_positive_count": len(positive),
            "archived_ko_rejected_leads": [{"candidate_name": lead.get("candidate_name"),
                                             "reason": lead.get("rejection_basis", "")}
                                            for lead in rejected[:3]],
            "source_reuse_scope": "Original Japanese identity and reading lead only; hidden KO proof remains unqualified.",
        }
        profile = OLD / "fresh-known-source-captures" / f"{player_id}.json.gz"
        if profile.exists():
            captured = read(profile)["profile_capture"]
            result["retained_profile_capture"] = {"path": str(profile.relative_to(ROOT)),
                                                   "file_sha256": digest(profile),
                                                   "url": captured["url"],
                                                   "body_sha256": captured["body_sha256"],
                                                   "http_status": captured.get("http_status")}
        if player_id in HELD:
            result["hold_reason"] = HELD[player_id]
        else:
            result["hold_reason"] = "Archived Korean search has no approved direct Korean publication; positive path needs actual complete kana and independent review."
        return result
    lead = prior.get(player_id)
    urls = lead.get("source_urls", []) if lead else []
    shared = [url for url in urls if "wikipedia.org" in url and ("%E5%9B%B4%E6%A3%8B%E6%A3%8B%E5%A3%AB%E5%88%97%E8%A1%A8" in url or "圍棋棋士列表" in url)]
    return {
        "status": "source_leads_only_no_target_language_publication_retained",
        "prior_source_urls": urls,
        "shared_original_language_list_pages": shared,
        "source_reuse_scope": "Saved URLs may support the already qualified original-language identity; they do not prove the missing target-language name.",
        "hold_reason": lead.get("status", "no retained missing-language publication") if lead else "no retained missing-language publication",
    }


def main():
    prod_path = FRESH / "PROD-mixed20-fresh-post590-pages.json.gz"
    test_path = FRESH / "TEST-mixed20-fresh-post590-pages.json.gz"
    prod, test = read(prod_path), read(test_path)
    assert prod["batch590"]["status"] == test["batch590"]["status"] == "applied"
    prod_slots, prod_names = counts_and_names(prod)
    test_slots, test_names = counts_and_names(test)
    by_four = collections.defaultdict(list)
    for test_id, names in test_names.items():
        if len(names) == 4:
            by_four[tuple(sorted(names.items()))].append(test_id)
    prior = {row["player_id"]: row for row in read(PRIOR / "next20-shortlist-after589.json")["top40"]}
    recovery = {int(key): value for key, value in read(OLD / "old-ko28-applied-evidence-recovery.json").items()}
    candidates = []
    for player_id, slots in sorted(prod_slots.items(), key=lambda item: (-item[1], item[0])):
        if player_id in CURRENT_20:
            continue
        names = prod_names[player_id]
        if len(names) != 4:
            continue
        missing = list(LANGUAGES - set(names))
        if len(missing) != 1:
            continue
        matches = by_four[tuple(sorted(names.items()))]
        assert len(matches) == 1, (player_id, matches)
        test_id = matches[0]
        assert test_slots[test_id] == slots, (player_id, test_id)
        source = source_status(player_id, prior, recovery)
        missing_lang = missing[0]
        next_source_needed = (
            "Resolve the recorded conflicting Korean spelling/identity against a direct same-person Korean Go publication."
            if player_id in HELD else
            "Reuse the archived Japanese identity proof; retain an actual same-person complete kana profile and review NIKL output, or find a direct Korean publication."
            if player_id in recovery else
            "Find direct published English name and bind it to this player; existing CN/JP/KO/TW names remain unchanged."
            if missing_lang == "en" else
            "Find direct published Taiwanese personal-name form or review this 昇 exception individually; do not apply the broad character rule."
            if missing_lang == "tw" else
            "Find a direct same-person Korean publication; the saved original-language list/profile links do not establish Korean spelling."
        )
        candidates.append({
            "rank": len(candidates) + 1, "prod_player_id": player_id,
            "test_player_id": test_id, "linked_slots_per_environment": slots,
            "qualified_existing_names": {lang: names[lang] for lang in sorted(names)},
            "missing_language": missing_lang, "missing_name_proposal": None,
            "prior_canonical_label": (prior.get(player_id) or {}).get("canonical_name") or
                                     names.get("cn") or names.get("jp"),
            "source": source,
            "next_source_needed": next_source_needed,
            "authoritative_pages_status": "Current per-owner JSON pages were not in the pinned r3 read-only capture; no saved 2026-10-05/08 page-apply record matched this owner. Recheck only before an authorized write.",
            "write_permission": "source research only; root owns approval, SQL, Git and deployment",
        })
        if len(candidates) == 20:
            break
    assert len(candidates) == 20
    result = {
        "status": "source_only_no_new_capture_or_sql",
        "produced_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "producer_id": "/root/next20_packet_recovered", "producer_model": "gpt-6-sol",
        "basis": {"prod_fresh_capture": str(prod_path.relative_to(ROOT)),
                  "prod_file_sha256": digest(prod_path),
                  "test_fresh_capture": str(test_path.relative_to(ROOT)),
                  "test_file_sha256": digest(test_path),
                  "prod_inventory_sha256": prod["inventory"]["sha256"],
                  "test_inventory_sha256": test["inventory"]["sha256"],
                  "preceding_batch": 590,
                  "excluded_prepared_mixed20": sorted(CURRENT_20)},
        "scope": {"players": 20, "linked_slots_per_environment": sum(row["linked_slots_per_environment"] for row in candidates),
                  "missing_language_counts": dict(collections.Counter(row["missing_language"] for row in candidates))},
        "limits": ["Only the missing cell is a target; the four qualified names per owner are unchanged and are not re-reviewed here.",
                   "A shared Chinese Wikipedia player-list page is an original-language identity lead, not a Korean or English publication for an individual.",
                   "Old hidden KO rows and rejected Wikidata labels remain unqualified; no generated KO spelling is approved by this shortlist.",
                   "Current authoritative_pages JSON is unavailable in the saved native r3 context; this sheet does not claim current page URLs or permissions.",
                   "No source was fetched, no database query or SQL write was made, and no candidate was signed."],
        "players": candidates,
    }
    D.mkdir(exist_ok=True)
    (D / "shortlist.json").write_text(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n")
    lines = ["# Next high-frequency 20: missing-name source shortlist", "",
             "Read-only source planning from the saved post-590 TEST/PROD snapshots. The prepared mixed20 owners are excluded; each row below already has four qualified names. No target spelling is approved.", "",
             "| Rank | PROD / TEST | Slots | Missing | Existing source label | Source state |",
             "|---:|---:|---:|---|---|---|"]
    for row in candidates:
        names = row["qualified_existing_names"]
        label = names.get("jp") if row["prod_player_id"] in recovery else names.get("cn") or names.get("jp")
        state = "held prior KO proof" if row["prod_player_id"] in HELD else "archived JP source; KO absent" if row["prod_player_id"] in recovery else "source leads only"
        lines.append(f"| {row['rank']} | {row['prod_player_id']} / {row['test_player_id']} | {row['linked_slots_per_environment']} | {row['missing_language']} | {label} | {state} |")
    lines += ["", "The first eight have archived Japanese identity sources and hidden Korean proof records. Four have specific conflicts documented in `shortlist.json`; they remain held. Other saved original-language URLs, including shared Chinese Wikipedia lists, do not establish a missing Korean or English name. For 田村昇, the old broad orthographic rule excluded 昇; individual source/rule review is still needed for TW.", "",
              "Current `authoritative_pages` values were absent from the pinned native r3 capture. The saved 2026-10-05/08 page-apply records had no matching owner among these 20, so page sharing is recorded only as a source lead. Root will check current pages and target preimages before any later binding or write.", "",
              f"Snapshot SHA-256: PROD `{digest(prod_path)}`; TEST `{digest(test_path)}`. Slots across this shortlist: {result['scope']['linked_slots_per_environment']} per environment.", ""]
    (D / "shortlist.md").write_text("\n".join(lines))
    print("source-only", len(candidates), "players", result["scope"]["linked_slots_per_environment"], "slots")


if __name__ == "__main__":
    main()
