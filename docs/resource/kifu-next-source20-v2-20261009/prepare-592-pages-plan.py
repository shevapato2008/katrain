"""Derive an offline URL/role preview plan from the 20 approved research records."""

import gzip
import json
from pathlib import Path
from types import SimpleNamespace

from katrain.web.kifu.name_evidence import registry_sha256
from katrain.web.kifu.player_pages import pages_from_evidence


D = Path(__file__).resolve().parent


def read(name):
    return json.loads(gzip.decompress((D / name).read_bytes()))


def context(url):
    if "baduk.or.kr/record/player_view.asp" in url:
        return "opponent_row_in_other_player_page"
    if "/news/N_news_view.oro" in url:
        return "published_go_news"
    if "namu.wiki" in url or "zh.wikipedia.org/zh-hant/" in url:
        return "go_event_table"
    if "ko.wikipedia.org/w/index.php" in url:
        return "disambiguation_entry_red_person_link"
    if "pairgo.or.jp" in url:
        return "organizer_entrant_list"
    if "/info/N_player_view.oro" in url:
        return "go_player_profile"
    return "published_player_record"


result = {}
for env in ("PROD", "TEST"):
    bundle = read(f"{env}-post591-final20-unsigned-bundle.json.gz")
    evidence = read(f"{env}-post591-final20-unsigned-evidence.json.gz")
    registry = read(f"{env}-root-approved-fresh.json.gz")["registry"]
    by_owner = {row["owner"]["id"]: row for row in evidence}
    rows = {}
    for candidate in bundle["candidates"]:
        owner = candidate["owner"]["id"]
        research = by_owner[owner]
        name = SimpleNamespace(player_id=owner, lang=candidate["lang"],
                               display_name=candidate["display_name"],
                               decision_kind=candidate["decision_kind"],
                               generation_rule_version=candidate["generation_rule_version"])
        record = SimpleNamespace(id=1, research_payload={"candidate": candidate, "research": research},
                                 **{key: candidate[key] for key in
                                    ("producer_id", "producer_model", "reviewer_id", "reviewer_model")})
        source = SimpleNamespace(registry=registry, sha256=registry_sha256(registry), version=registry["version"])
        pages = pages_from_evidence(name, record, source)
        rows[str(owner)] = [{"url": page["url"], "source_id": page["source_id"],
                             "language": page["language"], "role": page["role"],
                             "page_context": context(page["url"])} for page in pages]
    assert len(rows) == 20 and sum(map(len, rows.values())) >= 20
    result[env] = rows
(D / "592-pages-proposed-plan.json").write_text(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n")
print(json.dumps({env: {"players": len(rows), "pages": sum(map(len, rows.values()))}
                  for env, rows in result.items()}, ensure_ascii=False))
