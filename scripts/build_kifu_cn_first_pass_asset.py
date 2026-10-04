"""Build the bounded Chinese display fallback from read-only catalog snapshots.

This is a presentation asset. It never approves an identity or modifies SGF data.
"""

from __future__ import annotations

import gzip
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RESOURCE = ROOT / "docs/resource"
OUTPUT = ROOT / "katrain/web/kifu/data/cn_first_pass_2026-10-05.json.gz"

# These exact romanized spellings have identifiable Chinese Wikipedia pages.
# A short list is enough to clear the weighted 95% player-slot threshold.
PLAYER_NAMES = {
    "Iwamoto Kaoru": ("岩本薰", "https://zh.wikipedia.org/wiki/岩本薰"),
    "Fujisawa Hosai": ("藤泽朋斋", "https://zh.wikipedia.org/wiki/藤泽朋斋"),
    "Rin Kaiho": ("林海峰", "https://zh.wikipedia.org/wiki/林海峰_(围棋)"),
    "ChoChikun": ("赵治勋", "https://zh.wikipedia.org/wiki/赵治勋"),
    "Cho Chikun": ("赵治勋", "https://zh.wikipedia.org/wiki/赵治勋"),
    "Takemiya Masaki": ("武宫正树", "https://zh.wikipedia.org/wiki/武宫正树"),
    "Takagawa Shukaku": ("高川格", "https://zh.wikipedia.org/wiki/高川格"),
    "Kobayashi Koichi": ("小林光一", "https://zh.wikipedia.org/wiki/小林光一"),
}


def has_han(value: str | None) -> bool:
    return bool(value and any("\u3400" <= ch <= "\u9fff" for ch in value))


def safe_chinese_event(value: str | None) -> bool:
    if not has_han(value) or not value or len(value) > 150:
        return False
    if re.search(r"[\u3040-\u30ff]|\?|(?i:\.sgf)|[A-Za-z]{7,}", value):
        return False
    return True


def load_candidates(environment: str):
    canonical = {
        int(event_id): name for event_id, name in json.loads(
            (RESOURCE / f"kifu-cn-first-pass-event-canonical-{environment}-2026-10-05.json").read_text()
        ).items()
    }
    candidates = RESOURCE / f"kifu-event-display-weighted-{environment}-candidates-2026-10-05.jsonl.gz"
    raw_map = {}
    overrides = {}
    with gzip.open(candidates, "rt", encoding="utf-8") as stream:
        for line in stream:
            row = json.loads(line)
            kind = row.get("kind")
            if kind == "raw_candidate":
                tier = row["candidate_kind"]
                raw = row["raw"]
                if row["event_id"] is None and raw:
                    oteai = re.fullmatch(r"JapanPromotionTournament,([12]\d{3}),(Spring|Fall)", raw)
                    if oteai:
                        season = "春季" if oteai.group(2) == "Spring" else "秋季"
                        raw_map[(raw, None)] = f"{oteai.group(1)}年{season}大手合"
                        continue
                    if raw == "Hayago Meijin":
                        raw_map[(raw, None)] = "日本早碁名人战"
                        continue
                    if raw == "20-game match":
                        raw_map[(raw, None)] = "二十番棋"
                        continue
                if tier not in {
                    "EXISTING_EVENT_ID_CHINESE", "EXISTING_CHINESE_LABEL_CLEAN", "RESEARCHED_EXACT_CORE_DISPLAY"
                }:
                    continue
                value = raw if tier == "EXISTING_CHINESE_LABEL_CLEAN" else row["display_candidate"]
                if not safe_chinese_event(value):
                    continue
                raw_map[(raw, canonical.get(row["event_id"]))] = value
            elif kind == "album_override" and safe_chinese_event(row["display_candidate"]):
                overrides[row["album_id"]] = [
                    row["exact_raw"], row["sgf_sha256"], row["display_candidate"]
                ]
    return raw_map, overrides


def build() -> dict:
    prod_map, prod_overrides = load_candidates("prod")
    test_map, test_overrides = load_candidates("test")
    shared = prod_map.keys() & test_map.keys()
    conflicts = {key for key in shared if prod_map[key] != test_map[key]}
    if conflicts:
        raise ValueError(f"Conflicting cross-environment event displays: {len(conflicts)}")
    if prod_overrides != test_overrides:
        raise ValueError("Exact album SGF display overrides differ between environments")
    merged = {**prod_map, **test_map}
    return {
        "format": "kifu-cn-first-pass-v1",
        "generated_date": "2026-10-05",
        "player_raw": {raw: {"display": name, "source": source} for raw, (name, source) in PLAYER_NAMES.items()},
        "event_raw_canonical": [[raw, canonical, value] for (raw, canonical), value in sorted(
            merged.items(), key=lambda item: (item[0][0], item[0][1] or "")
        )],
        "event_album_sgf": [[album_id, *value] for album_id, value in sorted(prod_overrides.items())],
        "filters": ["no inferred aliases", "no kana", "no damaged question mark", "no filename", "no long Latin run"],
    }


if __name__ == "__main__":
    payload = build()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("wb") as out, gzip.GzipFile(filename="", fileobj=out, mode="wb", mtime=0) as stream:
        stream.write(json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
    print(json.dumps({"output": str(OUTPUT), "raw_keys": len(payload["event_raw_canonical"]),
                      "sgf_overrides": len(payload["event_album_sgf"]),
                      "player_keys": len(payload["player_raw"])}, ensure_ascii=False))
