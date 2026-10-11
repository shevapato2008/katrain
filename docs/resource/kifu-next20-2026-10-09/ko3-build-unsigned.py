"""Validate three pending JA-to-KO source records without database access."""

import datetime
import gzip
import hashlib
import html
import json
from pathlib import Path

from katrain.web.kifu.name_evidence import registry_sha256, validate_research_record


D = Path(__file__).parent
OLD = D.parent / "kifu-next-throughput-2026-10-09"
REGISTRY = json.loads((OLD / "source-registry-reused.json").read_text())
RULES = json.loads((OLD / "reused-NIKL-three-page-captures.json").read_text())["rules"]
CAPTURES = json.load(gzip.open(D / "ko3-actual-source-captures.json.gz", "rt"))
REASONS = {
    5396: "は→하, ま→마, な→나, medial か→카; initial た→다, medial か→카, み→미, つ→쓰.",
    4276: "お→오, medial く→쿠, む→무, ら→라; や→야, す→스, し→시.",
    4782: "あ→아, medial け→케, ど→도; initial か→가, ず→즈, み→미.",
}
KANA = {
    5396: ("はまなか", "たかみつ", "하마나카", "다카미쓰"),
    4276: ("おくむら", "やすし", "오쿠무라", "야스시"),
    4782: ("あけど", "かずみ", "아케도", "가즈미"),
}
HITS = {
    5396: [("candidate_go", "https://namu.wiki/w/%EC%A0%9C38%ED%9A%8C%20%EC%99%95%EC%A2%8C%EC%A0%84",
            "Captured tournament bracket uses the same complete Hangul spelling. It is a conflict lead, not identity authority.")],
    4276: [("candidate_go", "https://baduk.hangame.com/people.nhn?m=list&kind=3",
            "Captured professional-Go directory uses the same complete Hangul spelling; no competing spelling appears in this result."),
           ("candidate_go", "https://namu.wiki/w/%EC%A0%9C43%ED%9A%8C%20%EC%99%95%EC%A2%8C%EC%A0%84",
            "Captured tournament bracket uses the same complete Hangul spelling; it is not used as identity authority.")],
    4782: [],
}


def result_slice(body, url):
    start = body.find('href="' + html.escape(url, quote=True) + '"')
    if start < 0:
        start = body.find('href="' + url + '"')
    assert start >= 0, url
    return body[max(0, start - 100):start + 5000]


def main():
    records, summary = [], []
    for row in CAPTURES:
        player_id = row["player_id"]
        ja_surname, ja_given, ko_surname, ko_given = KANA[player_id]
        reading = ja_surname + " " + ja_given
        output = ko_surname + " " + ko_given
        assert row["candidate_name"] == output
        owner = {"kind": "player", "id": player_id}
        igo, official = row["igo_profile"], row["official_profile"]
        source_id = "igorating" if igo["url"].startswith("https://www.") else "igorating-bare"
        basis = ("The specialist Go profile contains the exact compact Japanese name and complete kana. "
                 "An independently retained Nihon Kiin personal page matches the name, complete kana, "
                 f"Roman name and Japanese Go affiliation: {official['url']} "
                 f"(captured body SHA-256 {official['body_sha256']}). Existing PROD owner ID and "
                 "qualified JP/EN names must be bound by the root reviewer against fresh preimages.")
        check = {"owner": owner, "source_id": source_id, "query": row["original_name"],
                 "url": igo["url"], "fetched_at": igo["fetched_at"], "http_status": 200,
                 "status": "found", "candidate_name": row["original_name"],
                 "body_sha256": igo["body_sha256"], "body_excerpt": igo["body_excerpt"],
                 "language_basis": "reviewed_text", "observed_lang": "ja", "identity_basis": basis}
        queries = []
        for source_query in row["queries"]:
            matches = [{"url": url,
                        "text": result_slice(source_query["capture"]["body_text"], url),
                        "resolution": reason}
                       for role, url, reason in HITS[player_id]
                       if role == source_query["role"]]
            queries.append({"role": source_query["role"], "query": source_query["query"],
                            "capture": source_query["capture"], "relevant_results": matches,
                            "conclusion": "no_unresolved_conflict"})
        applications = [
            {"rule_role": "personal_names", "input": row["original_name"], "output": output,
             "reason": "NIKL Chapter 4, Section 2, Article 3 applies Japanese transcription to Japanese personal names regardless of era."},
            {"rule_role": "kana_table", "input": reading, "output": output,
             "reason": REASONS[player_id] + " Surname and given name each use word-initial forms at their first kana."},
            {"rule_role": "japanese_details", "input": reading, "output": output,
             "reason": "NIKL Japanese details were checked; this name has no long vowel or small っ requiring an extra change."},
        ]
        for item in applications:
            item["locator"] = next(rule["capture"]["locator"] for rule in RULES if rule["role"] == item["rule_role"])
        produced_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
        record = {"owner": owner, "lang": "ko", "source_lang": "ja",
                  "registry_version": REGISTRY["version"], "registry_sha256": registry_sha256(REGISTRY),
                  "review_status": "pending", "producer_id": "/root/restore_tw_twenty",
                  "producer_model": "gpt-6; exact runtime variant unavailable", "produced_at": produced_at,
                  "scope_status": "generated_from_original", "source_basis": "normative_ja_ko_v1",
                  "generation_rule_version": "nikl-ja-ko-personal-name-v1",
                  "candidate_name": output, "original_name": row["original_name"],
                  "original_language": "ja", "original_language_basis_url": igo["url"],
                  "reading": reading, "reading_basis_url": igo["url"], "source_checks": [check],
                  "positive_generation": {"version": 1,
                      "identity": {"owner": owner, "original_name": row["original_name"],
                                   "reading": reading, "status": "verified",
                                   "method": "reviewed_owner_binding", "basis": basis, "capture": igo},
                      "reading": {"surname": ja_surname, "given": ja_given, "capture": igo},
                      "rules": RULES,
                      "explanation": {"surname": ko_surname, "given": ko_given,
                                      "output": output, "rule_applications": applications},
                      "conflict_queries": queries, "unresolved_conflicts": []}}
        validate_research_record(record, REGISTRY)
        records.append(record)
        summary.append({"player_id": player_id, "original_name": row["original_name"],
                        "reading": reading, "candidate_name": output,
                        "official_url": official["url"], "official_body_sha256": official["body_sha256"],
                        "igo_url": igo["url"], "igo_body_sha256": igo["body_sha256"],
                        "conflict_results_per_query": [len(q["relevant_results"]) for q in queries],
                        "research_sha256": registry_sha256(record)})
    raw = json.dumps(records, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    (D / "ko3-unsigned-research.json.gz").write_bytes(gzip.compress(raw, mtime=0))
    request = {"status": "unsigned_pending_root_source_rule_review",
               "created_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
               "producer_id": "/root/restore_tw_twenty",
               "producer_model": "gpt-6; exact runtime variant unavailable",
               "research_file": str(D / "ko3-unsigned-research.json.gz"),
               "research_array_sha256": hashlib.sha256(raw).hexdigest(),
               "capture_file": str(D / "ko3-actual-source-captures.json.gz"),
               "normative_reused_capture_file": str(OLD / "reused-NIKL-three-page-captures.json"),
               "records": summary,
               "limitations": ["Two bounded Naver first-page queries per person; no universal absence claim.",
                               "Current TEST/PROD owner preimages and whole-batch metadata are deferred until root permits post-590 binding.",
                               "The independently retained Nihon Kiin pages use spaces between surname and given name; compact Igo text satisfies the existing literal source-check gate."]}
    (D / "ko3-source-rule-review-request.json").write_text(json.dumps(request, ensure_ascii=False, indent=2) + "\n")
    print("PASS", len(records), "unsigned validated research records", request["research_array_sha256"])


if __name__ == "__main__":
    main()
