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
EVENT_GLOSSARY = ROOT / "katrain/web/kifu/data/cn_event_core_glossary_2026-10-05.json"
PLAYER_GLOSSARY = ROOT / "katrain/web/kifu/data/cn_player_raw_glossary_2026-10-05.json"

# These are descriptions of a game format, not tournament identities. Render
# them literally and retain the original EV value for later catalog review.
EVENT_DESCRIPTIONS = {
    "21-game match": "二十一番棋",
    "30-game match": "三十番棋",
    "Teaching game": "指导棋",
    "Teaching Game": "指导棋",
    "Teachinggame": "指导棋",
    "Shusai's Retirement Game": "秀哉引退棋",
    "Honinbo Shusai's Retirement Game": "本因坊秀哉引退棋",
    "Win and Continue": "胜者续战",
    "Challenge match": "挑战对局",
    "9-game match": "九番棋",
    "1-game match": "单局对抗赛",
    "2-game match": "两局对抗赛",
    "3-game match": "三局对抗赛",
    "4-game match": "四局对抗赛",
    "Three-game match": "三局对抗赛",
    "Special game": "特别对局",
    "Special Game": "特别对局",
    "Game": "对局",
    "Special teaching game": "特别指导棋",
    "Teacher-pupil game": "师徒对局",
    "Televised game": "电视转播对局",
    "Radio game": "广播对局",
    "Consultation game": "商议棋",
    "Second consultation game": "第二局商议棋",
    "New Year Relay Game": "新年联棋",
    "New Year's relay game": "新年联棋",
    "Japan-China Go Exchange": "中日围棋交流赛",
    "Japan-ChinaGoExchange": "中日围棋交流赛",
    "East-West Japan Match": "日本东西对抗赛",
    "East-West match": "东西对抗赛",
    "Special Invitation Match": "特别邀请对局",
    "Pro qualification game": "职业资格赛对局",
    "9x9 game": "九路棋对局",
}

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


def translated_event_core(raw: str, core: str | None, glossary: dict) -> str | None:
    """Render only exact, simple edition/year forms of a reviewed event core."""
    entry = glossary.get(core)
    if not entry:
        return None
    translated = entry["zh"]
    if raw == core:
        years = re.findall(r"(?<!\d)((?:18|19|20)\d{2})(?!\d)", core)
        if len(years) == 1 and years[0] not in translated:
            return f"{years[0]}年{translated}"
        return translated
    ordinal = r"([1-9]\d{0,2})(?:st|nd|rd|th)"
    prefix = re.fullmatch(rf"{ordinal}\s*{re.escape(core)}", raw, flags=re.IGNORECASE)
    suffix = re.fullmatch(rf"{re.escape(core)},\s*{ordinal}", raw, flags=re.IGNORECASE)
    if prefix or suffix:
        return f"第{(prefix or suffix).group(1)}{entry.get('unit', '届')}{translated}"
    year = re.fullmatch(rf"{re.escape(core)},\s*((?:18|19|20)\d{{2}})", raw, flags=re.IGNORECASE)
    if year:
        return f"{year.group(1)}年{translated}"
    return None


def load_candidates(environment: str):
    glossary = json.loads(EVENT_GLOSSARY.read_text(encoding="utf-8"))
    glossary = {**{name: {"zh": display} for name, display in EVENT_DESCRIPTIONS.items()}, **glossary}
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
                    if row["category"] == "unclassified_pending":
                        translated = translated_event_core(raw, row.get("core"), glossary)
                        if translated and safe_chinese_event(translated):
                            raw_map[(raw, None)] = translated
                            continue
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
    players = {raw: {"display": name, "source": source} for raw, (name, source) in PLAYER_NAMES.items()}
    player_glossary = json.loads(PLAYER_GLOSSARY.read_text(encoding="utf-8"))
    for raw, entry in player_glossary.items():
        existing = players.get(raw)
        if existing and existing["display"] != entry["zh"]:
            raise ValueError(f"Conflicting Chinese player display for {raw!r}")
        players[raw] = {"display": entry["zh"], "source": entry["source"]}
    return {
        "format": "kifu-cn-first-pass-v1",
        "generated_date": "2026-10-05",
        "player_raw": players,
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
