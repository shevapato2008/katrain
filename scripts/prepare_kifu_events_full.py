"""Export every frozen kifu EV spelling and conservative deduplication hints.

The output is an offline review packet. Equal parser cores are grouped, while
near-duplicate spellings are only flagged; no event identity is asserted and no
database is opened. The JSONL files can be processed in independent batches.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import gzip
import hashlib
import json
from pathlib import Path
import re
import sys
import unicodedata

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from katrain.web.kifu.catalog_preprocess_events import prepare_event_raw_values


VERSION = "kifu-event-preprocess-v1"
_YEAR_PREFIX = re.compile(r"^([12]\d{3})(?!\d)")
_BARE_EDITION = re.compile(r"^(?:第)?([1-9]\d{0,2}|[一二三四五六七八九十百]+|首)(期|届)")
_JOINED_YEAR_EDITION = re.compile(r"^([12]\d{3})([1-9]\d?)(期|届)")
_STAGE = re.compile(r"(预选|预赛|循环圈|本战|本赛|资格赛|季后赛|(?:16|32|64|128|8|4)强(?:战|赛)?|半决赛|决赛|挑战赛)(.*)$")
_LEAGUE_ROUND = re.compile(r"(?P<round>(?:第)?[1-9]\d{0,2}轮)(?P<fixture>.*)$")
_NON_SERIES_LABELS = {"hoensha game", "castle game"}


def normalized_spelling(value: str) -> str:
    """A spelling comparison key, never an identity key."""
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def split_type_candidate(core: str) -> dict:
    """Extract only anchored edition/year and an explicit trailing stage cue.

    Sponsor text stays in the type candidate. This function never merges IDs.
    """
    text = core.strip()
    if normalized_spelling(text) in _NON_SERIES_LABELS:
        return {"type_candidate": None, "year": None, "edition": None,
                "stage": None, "round": None, "fixture": None, "reason": "historic_game_label"}
    year = edition = stage = round_name = fixture = None
    joined = _JOINED_YEAR_EDITION.match(text)
    if joined:
        year, number, unit = joined.groups()
        edition = number + unit
        text = text[joined.end():].strip()
    else:
        match = _YEAR_PREFIX.match(text)
        if match:
            year = match.group(1)
            text = text[match.end():].strip()
        match = _BARE_EDITION.match(text)
        if match:
            edition = match.group(1) + match.group(2)
            text = text[match.end():].strip()
    match = _STAGE.search(text)
    if match and match.start() > 0 and any(marker in text[:match.start()] for marker in "赛战杯棋联"):
        stage = text[match.start():]
        text = text[:match.start()].strip()
    # In team leagues the teams/board often follow a bare round number. The
    # original spelling and fixture remain available; neither enters type ID.
    match = _LEAGUE_ROUND.search(text)
    if match and match.start() > 0 and any(marker in text[:match.start()] for marker in "联赛甲乙"):
        round_name, fixture = match.group("round"), match.group("fixture") or None
        text = text[:match.start()].strip()
    return {"type_candidate": text or None, "year": year, "edition": edition,
            "stage": stage, "round": round_name, "fixture": fixture,
            "reason": None if text else "empty_type_after_split"}


def build_packet(inventory: dict, inventory_sha: str, batch_size: int = 500) -> tuple[dict, list, list, list, list, list]:
    if batch_size < 1:
        raise ValueError("batch_size must be positive")
    staged = prepare_event_raw_values(inventory)
    raw_rows = []
    by_core = defaultdict(list)
    excluded = Counter()
    grammar_counts = Counter()
    for index, row in enumerate(staged):
        data = row["parsed_data"]
        structure = data["structure"]
        core = data["series_core"]
        split = split_type_candidate(core) if core else None
        if split and split["type_candidate"] is None:
            core = None
        entry = {
            "version": VERSION, "inventory_sha256": inventory_sha,
            "batch": index // batch_size, "raw_value": data["original_raw_value"],
            "occurrences": data["occurrences"], "category": row["category"],
            "series_core": core, "grammar": structure["grammar"],
            "type_candidate": split["type_candidate"] if split else None,
            "core_year": split["year"] if split else None,
            "core_edition": split["edition"] if split else None,
            "stage": split["stage"] if split else None,
            "core_round": split["round"] if split else None,
            "fixture": split["fixture"] if split else None,
            "components": [{"kind": part["kind"], "value": part["value"], "text": part["text"]}
                           for part in structure["components"]],
            "parts": [{"kind": part["kind"], "text": part["text"]} for part in structure["parts"]],
            "exceptions": sorted(set(data["parse_exceptions"] + structure["exceptions"]
                                     + ([split["reason"]] if split and split["reason"] else []))),
            "review_status": "excluded_nonseries" if core is None else "candidate_unverified",
        }
        if "".join(part["text"] for part in entry["parts"]) != (entry["raw_value"] or ""):
            raise ValueError(f"lossy event parse at raw row {index}")
        raw_rows.append(entry)
        grammar_counts[entry["grammar"]] += 1
        if core is None:
            excluded[split["reason"] if split and split["reason"] else entry["category"]] += entry["occurrences"]
        else:
            by_core[core].append(entry)

    core_rows = []
    folded = defaultdict(list)
    for core, members in by_core.items():
        folded[normalized_spelling(core)].append(core)
        core_rows.append({
            "version": VERSION, "inventory_sha256": inventory_sha,
            "series_core": core, "raw_value_count": len(members),
            "occurrences": sum(row["occurrences"] for row in members),
            "grammars": dict(sorted(Counter(row["grammar"] for row in members).items())),
            "review_status": "candidate_unverified",
        })
    core_rows.sort(key=lambda row: (-row["occurrences"], row["series_core"].encode("utf-8")))
    for index, row in enumerate(core_rows):
        row["batch"] = index // batch_size

    alias_candidates = []
    for key, spellings in folded.items():
        if len(spellings) < 2:
            continue
        spellings.sort(key=lambda item: item.encode("utf-8"))
        alias_candidates.append({
            "version": VERSION, "inventory_sha256": inventory_sha,
            "comparison_key": key, "series_cores": spellings,
            "occurrences": sum(sum(row["occurrences"] for row in by_core[core]) for core in spellings),
            "review_status": "possible_alias_unverified",
        })
    alias_candidates.sort(key=lambda row: (-row["occurrences"], row["comparison_key"].encode("utf-8")))

    by_type = defaultdict(list)
    for row in core_rows:
        split = split_type_candidate(row["series_core"])
        row.update(split)
        if split["type_candidate"]:
            by_type[split["type_candidate"]].append(row)
    type_rows = []
    for name, members in by_type.items():
        type_rows.append({"version": VERSION, "inventory_sha256": inventory_sha,
                          "type_candidate": name, "series_cores": [row["series_core"] for row in members],
                          "raw_value_count": sum(row["raw_value_count"] for row in members),
                          "occurrences": sum(row["occurrences"] for row in members),
                          "review_status": "candidate_unverified"})
    type_rows.sort(key=lambda row: (-row["occurrences"], row["type_candidate"].encode("utf-8")))
    for index, row in enumerate(type_rows):
        row["batch"] = index // batch_size

    # parse_event reports classification_review for virtually all tournament
    # strings; retain only concrete structural concerns in this queue.
    unresolved = [row for row in raw_rows if row["review_status"] == "candidate_unverified"
                  and (row["grammar"] == "unparsed"
                       or set(row["exceptions"]) - {"classification_review", "identity_unverified"})]
    manifest = {
        "version": VERSION, "inventory_sha256": inventory_sha,
        "snapshot_time": inventory.get("snapshot_time"), "batch_size": batch_size,
        "albums": inventory["counts"]["all"], "raw_values": len(raw_rows),
        "series_cores": len(core_rows),
        "type_candidates": len(type_rows),
        "candidate_series_games": sum(row["occurrences"] for row in core_rows),
        "excluded_games": sum(excluded.values()), "excluded_games_by_category": dict(sorted(excluded.items())),
        "grammar_raw_values": dict(sorted(grammar_counts.items())),
        "possible_alias_groups": len(alias_candidates),
        "unresolved_raw_values": len(unresolved),
        "unresolved_games": sum(row["occurrences"] for row in unresolved),
    }
    if manifest["candidate_series_games"] + manifest["excluded_games"] != manifest["albums"]:
        raise ValueError("event slots do not reconcile")
    return manifest, raw_rows, core_rows, type_rows, alias_candidates, unresolved


def write_jsonl(path: Path, rows: list[dict]) -> None:
    with gzip.open(path, "wt", encoding="utf-8") if path.suffix == ".gz" else path.open("w", encoding="utf-8") as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--catalog", type=Path, help="optional catalog snapshot for legacy ID review")
    parser.add_argument("--batch-size", type=int, default=500)
    args = parser.parse_args(argv)
    raw = args.inventory.read_bytes()
    inventory_sha = hashlib.sha256(raw).hexdigest()
    payload = gzip.decompress(raw) if raw[:2] == b"\x1f\x8b" else raw
    manifest, raw_rows, core_rows, types, aliases, unresolved = build_packet(
        json.loads(payload), inventory_sha, args.batch_size)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    prefix = f"{VERSION}-{inventory_sha[:12]}"
    for label, rows in (("raw", raw_rows), ("cores", core_rows), ("types", types),
                        ("alias-candidates", aliases), ("unresolved", unresolved)):
        write_jsonl(args.output_dir / f"{prefix}-{label}.jsonl.gz", rows)
    if args.catalog:
        catalog = json.loads(args.catalog.read_text(encoding="utf-8"))
        inventory_raw = {row["raw_value"] for row in raw_rows}
        legacy = []
        for row in catalog["kifu_events"]:
            name = row["canonical_name"]
            legacy.append({"id": row["id"], "canonical_name": name,
                           "raw_ev_match": name in inventory_raw,
                           **split_type_candidate(name),
                           "review_status": "legacy_id_boundary_pending"})
        write_jsonl(args.output_dir / f"{prefix}-legacy-ids.jsonl.gz", legacy)
        manifest["legacy_event_ids"] = len(legacy)
        manifest["legacy_ids_matching_raw_ev"] = sum(row["raw_ev_match"] for row in legacy)
    (args.output_dir / f"{prefix}-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
