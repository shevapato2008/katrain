"""Freeze C76 plus the highest saved-count 74 Han source titles, without live eligibility claims."""

import hashlib
import json
from pathlib import Path


D = Path(__file__).resolve().parent
RESOURCE = D.parent
SOURCES = (
    ("kifu-event-title-c76-source-only-20261009.json",
     "9a7d598997a577f7c67c20a6c0608d7f85062b8d759c93e5aaad88b970119218"),
    ("kifu-event-title-next174-han-source-only-20261009.json",
     "14eca96b9bac71d507b24ecab22598a8014fc4c565b12bbe508b22b5364f91b4"),
)
LANGS = {"cn", "tw", "jp", "ko", "en"}


def canonical_sha256(value):
    data = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(data).hexdigest()


def load(name, expected):
    payload = (RESOURCE / name).read_bytes()
    actual = hashlib.sha256(payload).hexdigest()
    if actual != expected:
        raise ValueError(f"source changed: {name}: {actual}")
    return json.loads(payload)


def build():
    c, h = (load(*spec) for spec in SOURCES)
    assert len(c["records"]) == 76 and len(h["records"]) == 174
    c_rows = c["records"]
    h_rows = sorted(h["records"], key=lambda row: (-row["saved_inventory_game_count"], row["raw_value"]))[:74]
    raw_values = [row["raw_value"] for row in c_rows + h_rows]
    assert len(raw_values) == len(set(raw_values)) == 150
    assert sum(row["snapshot_games"] for row in c_rows) == 76
    assert sum(row["saved_inventory_game_count"] for row in h_rows) == 98
    for row in c_rows + h_rows:
        parts = row.get("parts", row.get("old_parser_parts"))
        assert "".join(part["text"] for part in parts) == row["raw_value"]
        assert set(row["names"]) == LANGS
        assert row["core"] == next(part["text"] for part in parts if part["kind"] == "core")
    selection = {
        "status": "unsigned_source_only",
        "selection_rule": "all C76 source order, then first 74 Han sorted by (-saved_inventory_game_count, raw_value)",
        "counts": {"raw_titles": 150, "proposed_name_cells": 750, "saved_inventory_games": 174},
        "sources": [
            {"file": SOURCES[0][0], "file_sha256": SOURCES[0][1], "profile": "sgf_chinese_mixed",
             "raw_values": [row["raw_value"] for row in c_rows]},
            {"file": SOURCES[1][0], "file_sha256": SOURCES[1][1], "profile": "sgf_chinese_mixed",
             "raw_values": [row["raw_value"] for row in h_rows]},
        ],
    }
    packet = {"status": "unsigned_source_only", "selection_sha256": canonical_sha256(selection),
              "sources": {
                  SOURCES[0][0]: {"core_lexicon": c["cores"], "records": c_rows},
                  SOURCES[1][0]: {"core_lexicon": h["core_lexicon"], "records": h_rows},
              }}
    return selection, packet


def main():
    selection, packet = build()
    for name, value in (("selection.json", selection), ("source-packet.json", packet)):
        path = D / name
        content = json.dumps(value, ensure_ascii=False, indent=2) + "\n"
        if path.exists() and path.read_text() != content:
            raise ValueError(f"frozen source differs: {path}")
        path.write_text(content)
        print(f"{name}: {canonical_sha256(value)}")


if __name__ == "__main__":
    main()
