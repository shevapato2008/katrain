"""Package retained missing-name sources; no database access or approval."""

import collections
import datetime
import gzip
import hashlib
import html
import json
import re
from pathlib import Path


D = Path(__file__).parent
ROOT = D.parents[2]
PRIOR = ROOT / "docs/resource/kifu-next-throughput-2026-10-09"
JP_IDS = (3771, 6642, 6635, 4568)
DAUM_IDS = (4071, 6366, 6547, 6329, 3820, 5495, 368, 5473, 6552,
            5952, 5468, 5349, 5790, 6550, 6322, 5094)
HELD_IDS = (5244, 4499, 6496, 3900)
LANGUAGES = {"cn", "tw", "jp", "ko", "en"}


def read(path):
    with gzip.open(path, "rt") if path.suffix == ".gz" else open(path) as stream:
        return json.load(stream)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inventory(capture):
    columns = capture["inventory"]["association_columns"]
    indexes = (columns.index("black_player_id"), columns.index("white_player_id"))
    counts = collections.Counter()
    for association in capture["inventory"]["album_associations"]:
        for index in indexes:
            if association[index] is not None:
                counts[association[index]] += 1
    names = collections.defaultdict(dict)
    for row in capture["approved_name_snapshot"]:
        if row["owner"]["kind"] == "player" and row["lang"] in LANGUAGES:
            names[row["owner"]["id"]][row["lang"]] = row["display_name"]
    return counts, names


def same_name_owner(prod_id, prod, test):
    slots, names = prod
    test_slots, test_names = test
    four = names[prod_id]
    assert len(four) == 4 and "ko" not in four
    match = [player_id for player_id, test_four in test_names.items() if test_four == four]
    assert len(match) == 1 and test_slots[match[0]] == slots[prod_id], (prod_id, match)
    return match[0], slots[prod_id], four


def main():
    shortlist = read(D / "shortlist.json")
    prod_path = ROOT / shortlist["basis"]["prod_fresh_capture"]
    test_path = ROOT / shortlist["basis"]["test_fresh_capture"]
    assert sha(prod_path) == shortlist["basis"]["prod_file_sha256"]
    assert sha(test_path) == shortlist["basis"]["test_file_sha256"]
    prod, test = inventory(read(prod_path)), inventory(read(test_path))
    daum_meta_path = D / "sources/daum-korean-player-list-capture.json"
    daum_meta = read(daum_meta_path)
    raw_path = D / daum_meta["raw_body_file"]
    assert sha(raw_path) == daum_meta["raw_body_sha256"]
    raw = raw_path.read_bytes().decode("utf-8")
    search_path = D / "sources/search-4071.json"
    search = read(search_path)
    assert search["data"]["web"][0]["url"] == daum_meta["url"]
    igo_meta = read(D / "sources/igo-four-capture-summary.json")
    recovery = read(PRIOR / "old-ko28-applied-evidence-recovery.json")
    nikl_path = PRIOR / "reused-NIKL-three-page-captures.json"
    nikl = read(nikl_path)
    result = []
    for player_id in JP_IDS:
        test_id, slots, four = same_name_owner(player_id, prod, test)
        assert four["jp"] in (D / igo_meta[str(player_id)]["raw_body_file"]).read_bytes().decode("utf-8")
        research = next(row["research"] for row in recovery[str(player_id)] if row["research"]["lang"] == "ko")
        generated = research["generated_proposal"]
        reading = research["reading"]
        assert all(segment in (D / igo_meta[str(player_id)]["raw_body_file"]).read_bytes().decode("utf-8")
                   for segment in reading.split())
        result.append({
            "prod_player_id": player_id, "test_player_id": test_id,
            "slots_per_environment": slots, "missing_language": "ko",
            "qualified_existing_names": four,
            "source_only_proposal": generated["display_name"],
            "evidence_kind": "generated_from_complete_japanese_kana_pending_root_review",
            "japanese_reading": reading,
            "japanese_profile": igo_meta[str(player_id)],
            "earlier_korean_research": {
                "archive_path": recovery[str(player_id)][0]["archive"],
                "negative_closure": research.get("negative_closure"),
                "generated_steps": generated["steps"],
                "historical_research_status": research.get("scope_status"),
            },
            "normative_rule_capture": {
                "path": str(nikl_path.relative_to(ROOT)), "file_sha256": sha(nikl_path),
                "rules": [{"url": rule["capture"]["url"],
                           "body_sha256": rule["capture"]["body_sha256"]}
                          for rule in nikl["rules"]],
            },
            "source_status": "original_reading_and_rule_retained; current conflict publication review pending",
            "authoritative_pages_status": "Current owner authoritative_pages JSON was not retained in the pinned r3 snapshot; no saved page-apply record matched this owner.",
            "write_permission": "source research only; root owns approval, SQL, Git and deployment",
        })
    for player_id in DAUM_IDS:
        test_id, slots, four = same_name_owner(player_id, prod, test)
        anchors = {four["cn"], four["tw"]}
        snippets = re.findall(r"<P[^>]*>.*?</P>", raw, re.IGNORECASE | re.DOTALL)
        matches = []
        for snippet in snippets:
            flat = html.unescape(re.sub(r"<[^>]+>", "", snippet)).strip()
            if "/" not in flat or not any(anchor in flat for anchor in anchors):
                continue
            parts = flat.split()
            if len(parts) < 2:
                continue
            hanzi = parts[-1].split("/")
            if any(anchor == text.strip() for anchor in anchors for text in hanzi):
                ko = parts[0].replace("(여)", "")
                assert re.fullmatch(r"[가-힣]+", ko), (player_id, flat)
                matches.append((ko, flat))
        assert len(matches) == 1, (player_id, matches)
        ko, line = matches[0]
        result.append({
            "prod_player_id": player_id, "test_player_id": test_id,
            "slots_per_environment": slots, "missing_language": "ko",
            "qualified_existing_names": four,
            "source_only_proposal": ko,
            "evidence_kind": "direct_korean_community_publication_pending_root_review",
            "exact_published_line": line,
            "korean_publication": {**daum_meta,
                                    "search_scrape_file": str(search_path.relative_to(ROOT)),
                                    "search_scrape_file_sha256": sha(search_path),
                                    "publisher": "Daum cafe 바둑과 사람, 고추잠자리",
                                    "page_posted_at_display": "12.10.24"},
            "source_status": "direct_Korean_Hanzi_pair_on_community_page; not_professional_authority",
            "authoritative_pages_status": "Current owner authoritative_pages JSON was not retained in the pinned r3 snapshot; no saved page-apply record matched this owner.",
            "write_permission": "source research only; root owns approval, SQL, Git and deployment",
        })
    assert len(result) == 20 and len({row["prod_player_id"] for row in result}) == 20
    assert not {row["prod_player_id"] for row in result} & set(HELD_IDS)
    result.sort(key=lambda row: (-row["slots_per_environment"], row["prod_player_id"]))
    package = {
        "status": "source_only_unbound_unapproved",
        "produced_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "producer_id": "/root/next20_packet_recovered", "producer_model": "gpt-6-sol",
        "basis": shortlist["basis"],
        "scope": {"people": len(result), "slots_per_environment": sum(row["slots_per_environment"] for row in result),
                  "direct_korean_community_names": len(DAUM_IDS),
                  "japanese_rule_proposals": len(JP_IDS),
                  "held_prior_conflicts": list(HELD_IDS)},
        "shared_source_pages": [
            {"source": "Daum Korean/Hanzi Go-player list", "owner_ids": list(DAUM_IDS),
             "capture_metadata": str(daum_meta_path.relative_to(ROOT)),
             "raw_body_sha256": daum_meta["raw_body_sha256"],
             "authority": "community publication, not a professional registry"},
            {"source": "NIKL official Japanese personal-name transcription rules", "owner_ids": list(JP_IDS),
             "capture_file": str(nikl_path.relative_to(ROOT)), "capture_file_sha256": sha(nikl_path),
             "authority": "normative rule source, not a publication of any individual's Korean name"},
        ],
        "limits": [
            "No live database capture, target preimage, owner binding, signing, SQL, Git or approval in this source-only packet.",
            "Only each missing Korean cell is researched; the four existing qualified languages are inventory context.",
            "Daum page pairs Hangul and Hanzi directly, but it is a community post and requires root source-quality review.",
            "Japanese proposals are generated from published complete kana and retained NIKL captures; root must review current conflicting publications before approval.",
            "The first four high-slot Korean conflicts remain excluded, as directed.",
        ],
        "players": result,
    }
    path = D / "source-only-20-research.json"
    path.write_text(json.dumps(package, ensure_ascii=False, sort_keys=True, indent=2) + "\n")
    lines = ["# Next 20 missing Korean names: source-only research", "",
             "These 20 owners each had four qualified names in the retained post-590 snapshots. They cover "
             f"{package['scope']['slots_per_environment']} album player slots per environment. All proposals need root review and fresh bindings later.", "",
             "| PROD / TEST | Slots | Published or proposed Korean | Evidence |", "|---:|---:|---|---|"]
    for row in result:
        kind = "Japanese full kana + NIKL (generated)" if row["prod_player_id"] in JP_IDS else "Daum Hanzi/Hangul list (community)"
        lines.append(f"| {row['prod_player_id']} / {row['test_player_id']} | {row['slots_per_environment']} | {row['source_only_proposal']} | {kind} |")
    lines += ["", "The Daum page was posted 2012-10-24; its current HTTP 200 raw response is retained under `sources/` with a capture timestamp and SHA-256. Its Korean names appear beside exact Hanzi matching a qualified CN or TW row. The four Japanese raw profile captures include full kana; the prior NIKL official-page captures and historical bounded Korean searches are linked in the JSON. These Japanese spellings are generated proposals, not claims of Korean publication.", "",
              "The Daum page is shared by 16 owners; the retained official NIKL rules are shared by four. Neither has been added to any owner's authoritative_pages field here. The pinned native r3 snapshot did not retain those current JSON fields, and no saved page-apply record matched these owners. The four earlier conflict owners 5244, 4499, 6496, 3900 remain held. The source-only packet has no live target preimage or batch write request. Root owns approval and any subsequent SQL/Git/deployment.", ""]
    (D / "source-only-20-research.md").write_text("\n".join(lines))
    print("source-only", len(result), "owners", package["scope"]["slots_per_environment"], "slots")


if __name__ == "__main__":
    main()
