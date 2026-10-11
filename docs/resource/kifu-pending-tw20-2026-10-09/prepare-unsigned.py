"""Build an unsigned TW candidate packet from captured, applied CN source images."""

import json
from pathlib import Path

from katrain.web.kifu.name_evidence import registry_sha256


DIRECTORY = Path(__file__).parent
TARGETS = [
    (6752, 12521, "塙保時"), (6765, 12534, "加納一夫"),
    (6768, 12537, "金井新一"), (5365, 11141, "泉谷實"),
    (5211, 10991, "染谷一雄"), (3993, 9789, "出雲榮次"),
    (6713, 12482, "中根鳳次郎"), (6447, 12211, "馬帥"),
    (5581, 11354, "田永善"), (6376, 12142, "陳軼哲"),
    (5893, 11662, "許才源"), (4552, 10342, "崔殷奎"),
    (3906, 9703, "何天予"), (5933, 11702, "賈欣怡"),
    (4023, 9819, "劉棣懷"), (4572, 10362, "川端篤士"),
    (5040, 10822, "李柱衡"), (4801, 10588, "曹志林"),
    (6215, 11981, "金秀英"), (6458, 12222, "高光明"),
]


def build():
    anchors = []
    manifest = []
    for environment, index in (("PROD", 0), ("TEST", 1)):
        source_file = DIRECTORY / f"{environment}-cn-source-readonly.json"
        captured = json.loads(source_file.read_text())
        by_id = {row["id"]: row for row in captured["rows"]}
        assert len(by_id) == len(TARGETS) == 20
        assert set(by_id) == {pair[index] for pair in TARGETS}
        for prod_id, test_id, target in TARGETS:
            player_id = (prod_id, test_id)[index]
            row = by_id[player_id]
            name, evidence, batch = (row[key] for key in
                                     ("source_name", "source_evidence", "source_batch"))
            assert row["current_tw"] is None
            assert name and evidence and batch
            assert (name["player_id"] == evidence["player_id"] == player_id
                    and name["lang"] == evidence["lang"] == "cn"
                    and name["display_name"] == evidence["candidate_name"]
                    and name["evidence_id"] == evidence["id"]
                    and name["status"] == "verified"
                    and name["decision_kind"] == evidence["decision_kind"] == "conventional"
                    and evidence["review_status"] == "approved"
                    and batch["status"] == "applied")
            owner = {"kind": "player", "id": player_id}
            binding = {
                "kind": "verified_chinese_display",
                "owner": owner,
                "source_name": name,
                "source_evidence": evidence,
                "source_batch": {
                    "id": batch["id"],
                    "bundle_sha256": batch["bundle_sha256"],
                    "evidence_creation_sha256": registry_sha256(evidence),
                },
            }
            content = {
                "reference_kind": "verified_chinese_display",
                "owner": owner,
                "original_name": name["display_name"],
                "source_lang": "zh-Hans",
                "source_script": "Hans",
                "binding": binding,
            }
            anchors.append({"environment": environment, "content": content,
                            "candidate_tw_display": target})
            manifest.append({
                "environment": environment, "player_id": player_id,
                "canonical_name": row["canonical_name"],
                "cn_display": name["display_name"], "candidate_tw_display": target,
                "source_evidence_id": evidence["id"], "source_batch_id": batch["id"],
                "source_name_sha256": registry_sha256(name),
                "source_evidence_sha256": registry_sha256(evidence),
                "unsigned_anchor_content_sha256": registry_sha256(content),
                "linked_games": row["games"],
                "tw_preimage": None,
            })
    for environment in ("PROD", "TEST"):
        subset = [row for row in manifest if row["environment"] == environment]
        assert sum(row["linked_games"] for row in subset) == 1185
    (DIRECTORY / "unsigned-anchor-content.json").write_text(
        json.dumps(anchors, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    )
    (DIRECTORY / "unsigned-manifest.json").write_text(
        json.dumps({"status": "unsigned_pending_independent_review", "rows": manifest},
                   ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    )
    print("prepared", len(manifest), "unsigned environment-specific anchors")


if __name__ == "__main__":
    build()
