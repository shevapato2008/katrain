"""Read-only, exact current-state capture for the finite literal event title selection.

Run in the pinned native importer image with KATRAIN_DATABASE_URL supplied by
the runner. The database transaction is PostgreSQL REPEATABLE READ, READ ONLY.
No plan, approval, or database write is produced.
"""

import argparse
from datetime import datetime, timezone
import gzip
import hashlib
import json
import os
import sys
from pathlib import Path

from sqlalchemy import create_engine, inspect, select, text

from katrain.core.sgf_parser import SGF
from katrain.web.core.models_db import (
    KifuAlbum, KifuAlbumEventSelection, KifuNameResearchEvidence,
    KifuNameSourceRegistry, KifuRawEventName, KifuRawEventValue,
)
from katrain.web.kifu.identity import normalize_alias
from katrain.web.kifu.name_batch import _OWNER, _catalog_sha, _image, _snapshot_parts
from katrain.web.kifu.name_candidates import canonical_sha256
from katrain.web.kifu.raw_event_translation import (
    SGF_CHINESE_MIXED_PROFILE, SGF_ENGLISH_PROFILE,
    eligible_raw_title_owner, validate_chinese_mixed_literal_parts, validate_english_literal_parts,
)
SELECTION = Path(__file__).with_name("selection.json")
SOURCE_PACKET = Path(__file__).with_name("source-packet.json")
LANGS = ("cn", "tw", "jp", "ko", "en")
if not __debug__:
    raise RuntimeError("capture assertions must be enabled")


def root_fragment(sgf):
    """Clip the SGF root while respecting escaped brackets and branches."""
    start = sgf.find("(")
    if start < 0:
        raise ValueError("missing SGF collection")
    inside = escaped = seen_node = False
    for index in range(start + 1, len(sgf)):
        char = sgf[index]
        if inside:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == "]":
                inside = False
        elif char == "[":
            inside = True
        elif char == ";":
            if seen_node:
                return sgf[start:index] + ")"
            seen_node = True
        elif char in "()" and seen_node:
            return sgf[start:index] + ")"
    raise ValueError("unterminated SGF root")


def source_records(selection):
    packet = json.loads(SOURCE_PACKET.read_text())
    assert packet["selection_sha256"] == canonical_sha256(selection)
    records = []
    for source in selection["sources"]:
        by_raw = {row["raw_value"]: row for row in packet["sources"][source["file"]]["records"]}
        assert len(by_raw) == len(source["raw_values"])
        for raw in source["raw_values"]:
            row = by_raw[raw]
            parts = row.get("parts", row.get("old_parser_parts"))
            validator = (validate_english_literal_parts if source["profile"] == SGF_ENGLISH_PROFILE
                         else validate_chinese_mixed_literal_parts)
            validator(raw, parts)
            assert set(row["names"]) == set(LANGS)
            records.append({"raw_value": raw, "profile": source["profile"],
                            "source_file": source["file"],
                            "owner_id_hint": row.get("owner_id_from_2026_10_04_snapshot",
                                                     row.get("raw_owner_id_hint_2026_10_04")),
                            "old_parts": parts, "core": row["core"], "names": row["names"]})
    assert len(records) <= 150 and len(records) == len({row["raw_value"] for row in records})
    assert all(row["owner_id_hint"] for row in records)
    seen = {}
    for row in records:
        for lang, name in row["names"].items():
            key = (lang, normalize_alias(name))
            assert key not in seen, (key, seen.get(key), row["raw_value"])
            seen[key] = row["raw_value"]
    return records, seen, canonical_sha256(packet)


def sgf_ref(album, raw):
    content = album["sgf_content"]
    props = dict(SGF.parse_sgf(root_fragment(content)).properties)
    gn, ev = props.get("GN", []), props.get("EV", [])
    if not gn or gn[0] != raw or ev:
        raise ValueError(f"album {album['id']} first GN/empty EV mismatch: {gn!r}, {ev!r}")
    return {"album_id": album["id"], "source_path": album["source_path"],
            "sgf_sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
            "gn_values": gn, "ev_values": ev}


def frozen_post_owner_scope(environment, manifest, selection, packet_sha256):
    """Load this environment's actual pre-owner album scope, bound by the manifest."""
    path = Path(__file__).with_name(f"{environment}-capture.json.gz")
    payload = path.read_bytes()
    capture_sha256 = hashlib.sha256(payload).hexdigest()
    matrix = json.loads(Path(__file__).with_name(
        "sgf_chinese_mixed-name-matrix-unsigned.json").read_text())
    assert matrix["owner_manifest_canonical_sha256"] == canonical_sha256(manifest)
    assert matrix["capture_file_sha256"][environment] == capture_sha256
    assert matrix["source_packet_canonical_sha256"] == packet_sha256
    frozen = json.loads(gzip.decompress(payload))
    members = manifest["member_manifest"][environment]
    assert frozen["environment"] == environment and frozen["status"] == "unsigned_read_only"
    assert frozen["selection_sha256"] == manifest["selection_sha256"] == canonical_sha256(selection)
    assert frozen["source_packet_sha256"] == manifest["source_packet_sha256"] == packet_sha256
    assert frozen["raw_count_requested"] == 150
    assert (frozen["base_sha256"], frozen["inventory_sha256"], frozen["catalog_sha256"]) == (
        members["base_sha256"], members["inventory_sha256"], members["catalog_sha256"])
    by_raw = {row["raw_value"]: row for row in frozen["records"]}
    by_member = {row["raw_value"]: row for row in members["members"]}
    assert len(by_raw) == 150 and len(by_member) == manifest["raw_value_count"]
    for raw, member in by_member.items():
        before = by_raw[raw]
        assert not before["reasons"]
        assert before["owner"]["id"] == member["raw_event_id"]
        assert before["album_ids"] == member["album_ids"]
        assert before["scope_rows"] == member["scope_rows"]
        assert before["scope_sha256"] == member["scope_sha256"]
        assert len(before["full_physical_album_sha256"]) == 64
    return by_raw, by_member, capture_sha256


def post_owner_scope_reasons(current, frozen, member):
    """Report album/SGF/physical drift; owner review fields may change separately."""
    reasons = []
    if current["album_ids"] != frozen["album_ids"] or current["album_ids"] != member["album_ids"]:
        reasons.append("post-owner album IDs differ from frozen pre-owner scope")
    if (current["scope_rows"] != frozen["scope_rows"]
            or current["scope_rows"] != member["scope_rows"]
            or current["scope_sha256"] != frozen["scope_sha256"]
            or current["scope_sha256"] != member["scope_sha256"]):
        reasons.append("post-owner album scope differs from frozen pre-owner scope")
    if current["original_sgf_refs"] != frozen["original_sgf_refs"]:
        reasons.append("post-owner SGF references differ from frozen pre-owner scope")
    if current["full_physical_album_sha256"] != frozen["full_physical_album_sha256"]:
        reasons.append("post-owner physical album image differs from frozen pre-owner scope")
    return reasons


def capture(conn, environment, selection, stage="pre-owner"):
    records, proposal_keys, packet_sha256 = source_records(selection)
    if stage == "post-owner":
        manifest = json.loads(Path(__file__).with_name("sgf_chinese_mixed-owner-research-unsigned.json").read_text())
        frozen_by_raw, members_by_raw, frozen_file_sha256 = frozen_post_owner_scope(
            environment, manifest, selection, packet_sha256)
        chosen = {row["raw_value"] for row in manifest["records"]}
        assert len(chosen) == manifest["raw_value_count"] <= 150
        assert chosen == set(members_by_raw)
        records = [row for row in records if row["raw_value"] in chosen]
        proposal_keys = {(lang, normalize_alias(name)): row["raw_value"]
                         for row in records for lang, name in row["names"].items()}
        assert len(records) == len(chosen) and len(proposal_keys) == 5 * len(chosen)
    else:
        assert stage == "pre-owner"
    album_columns = {column["name"] for column in inspect(conn).get_columns("kifu_albums")}
    optional_album_columns = tuple(column for column in ("event_edition_id", "list_hidden_reason")
                                   if column in album_columns)
    inventory, supplement, base = _snapshot_parts(conn, inventory_format=4)
    result = {"status": "post_owner_read_only" if stage == "post-owner" else "unsigned_read_only",
              "environment": environment,
              "captured_at": datetime.now(timezone.utc).isoformat(),
              "selection_sha256": canonical_sha256(selection),
              "source_packet_sha256": packet_sha256,
              "raw_count_requested": len(records), "inventory_format": 4,
              "inventory_sha256": inventory, "base_sha256": base,
              "selection_supplement": supplement, "catalog_sha256": _catalog_sha(conn),
              "physical_optional_album_columns": list(optional_album_columns),
              "records": [], "rejections": [], "external_collisions": []}
    if stage == "post-owner":
        result["frozen_preowner_capture_file_sha256"] = frozen_file_sha256
        result["owner_manifest_sha256"] = canonical_sha256(manifest)
    latest_registry = conn.execute(select(KifuNameSourceRegistry.__table__).order_by(
        KifuNameSourceRegistry.id.desc()).limit(1)).mappings().one_or_none()
    result["latest_registry"] = (_image(conn, KifuNameSourceRegistry.__table__, latest_registry["id"])
                                 if latest_registry else None)
    for row in records:
        raw = row["raw_value"]
        reasons = []
        owners = conn.execute(select(KifuRawEventValue.__table__).where(
            KifuRawEventValue.raw_value == raw)).mappings().all()
        owner = _image(conn, KifuRawEventValue.__table__, owners[0]["id"]) if len(owners) == 1 else None
        if owner is None:
            reasons.append("missing/nonunique current raw owner")
        if owner is not None:
            if stage == "post-owner":
                if not eligible_raw_title_owner(owner):
                    reasons.append("owner lacks approved literal title review")
            elif owner["category"] != "unclassified_pending" or owner["review_status"] != "pending":
                reasons.append("owner is not pending unclassified")
            try:
                parts = [{"kind": part["kind"], "text": part["text"]}
                         for part in owner["parsed_data"]["structure"]["parts"]]
                (validate_english_literal_parts if row["profile"] == SGF_ENGLISH_PROFILE
                 else validate_chinese_mixed_literal_parts)(raw, parts)
                if parts != row["old_parts"]:
                    reasons.append("current parser parts differ from archived exact parts")
            except (KeyError, TypeError, ValueError) as exc:
                parts = None
                reasons.append(f"invalid current parser parts: {exc}")
            names = [_image(conn, KifuRawEventName.__table__, name["id"]) for name in conn.execute(
                select(KifuRawEventName.__table__).where(KifuRawEventName.raw_event_id == owner["id"])).mappings()]
            evidences = [_image(conn, KifuNameResearchEvidence.__table__, evidence["id"])
                         for evidence in conn.execute(select(KifuNameResearchEvidence.__table__).where(
                             KifuNameResearchEvidence.raw_event_id == owner["id"])).mappings()]
            if names or evidences:
                reasons.append("owner already has name/evidence rows")
        else:
            parts, names, evidences = None, [], []
        albums = conn.execute(select(KifuAlbum.__table__).where(KifuAlbum.event == raw)
                              .order_by(KifuAlbum.id)).mappings().all()
        extras_by_id = {}
        physical_images = []
        if optional_album_columns:
            columns = ", ".join(optional_album_columns)
            extra_rows = conn.execute(text(f"SELECT id, {columns} FROM kifu_albums WHERE event = :raw"),
                                      {"raw": raw}).mappings()
            extras_by_id = {extra["id"]: dict(extra) for extra in extra_rows}
        physical_rows = conn.execute(text("SELECT * FROM kifu_albums WHERE event = :raw ORDER BY id"),
                                     {"raw": raw}).mappings().all()
        assert [physical["id"] for physical in physical_rows] == [album["id"] for album in albums]
        for physical in physical_rows:
            values = {key: value.isoformat() if hasattr(value, "isoformat") else value
                      for key, value in physical.items()}
            values["sgf_content"] = {"sha256": hashlib.sha256(
                (physical["sgf_content"] or "").encode("utf-8")).hexdigest()}
            physical_images.append(values)
        if not albums:
            reasons.append("no current albums for raw")
        scope, refs = [], []
        for album in albums:
            extra = extras_by_id.get(album["id"], {})
            if (album["event_id"] is not None or extra.get("event_edition_id") is not None
                    or album["duplicate_of_id"] is not None or extra.get("list_hidden_reason") is not None):
                reasons.append(f"album {album['id']} linked, duplicated, or hidden")
            try:
                ref = sgf_ref(album, raw)
                refs.append(ref)
                scope.append({"id": album["id"], "event": album["event"],
                              "event_id": album["event_id"], "round_name": album["round_name"],
                              "date_played": album["date_played"], "black_rank": album["black_rank"],
                              "white_rank": album["white_rank"], "source_path": album["source_path"],
                              "sgf_sha256": ref["sgf_sha256"]})
            except Exception as exc:
                reasons.append(f"album {album['id']} SGF parse/GN/EV: {exc}")
        ids = [album["id"] for album in albums]
        if ids:
            selection_row = conn.scalar(select(KifuAlbumEventSelection.album_id).where(
                (KifuAlbumEventSelection.album_id.in_(ids)) |
                (KifuAlbumEventSelection.selected_raw == raw)).limit(1))
            if selection_row is not None:
                reasons.append("album/raw has event selection")
        record = {**row, "owner": owner,
                                  "archived_prod_owner_id_hint_matches":
                                      owner is not None and owner["id"] == row["owner_id_hint"],
                                  "current_parts": parts,
                                  "name_preimages": names, "evidence_preimages": evidences,
                                  "optional_album_preimages": extras_by_id,
                                  "full_physical_album_sha256": canonical_sha256(physical_images),
                                  "album_ids": ids, "scope_rows": scope,
                                  "scope_sha256": canonical_sha256(scope), "original_sgf_refs": refs,
                                  "reasons": []}
        if stage == "post-owner":
            if owner is None or owner["id"] != members_by_raw[raw]["raw_event_id"]:
                reasons.append("post-owner exact raw owner differs from frozen pre-owner owner")
            reasons.extend(post_owner_scope_reasons(
                record, frozen_by_raw[raw], members_by_raw[raw]))
        record["reasons"] = sorted(set(reasons))
        result["records"].append(record)
        if reasons:
            result["rejections"].append({"raw_value": raw, "reasons": record["reasons"]})
    # Same normalized-name rule as the existing name bundle; retain exact conflicting rows.
    for kind, (_owner_model, name_model, owner_column) in _OWNER.items():
        for existing in conn.execute(select(name_model.__table__).where(
                name_model.lang.in_(LANGS), name_model.status == "verified")).mappings():
            key = (existing["lang"], normalize_alias(existing["display_name"]))
            if key in proposal_keys:
                result["external_collisions"].append({"raw_value": proposal_keys[key],
                    "lang": key[0], "normalized_name": key[1], "existing_kind": kind,
                    "existing_owner_id": existing[owner_column], "existing_name_id": existing["id"]})
    result["current_null_games"] = sum(len(r["album_ids"]) for r in result["records"] if not r["reasons"])
    result["eligible_raw_count"] = sum(not r["reasons"] for r in result["records"])
    result["ready_for_unsigned_owner_review"] = not result["rejections"] and not result["external_collisions"]
    if stage == "post-owner":
        result["ready_for_unsigned_name_review"] = (result["eligible_raw_count"] == len(records)
                                                     and result["ready_for_unsigned_owner_review"])
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--environment", choices=("TEST", "PROD"), required=True)
    parser.add_argument("--stage", choices=("pre-owner", "post-owner"), default="pre-owner")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--stdout", action="store_true")
    args = parser.parse_args()
    if (args.output is None) == (not args.stdout):
        parser.error("choose exactly one of --output or --stdout")
    selection = json.loads(SELECTION.read_text())
    engine = create_engine(os.environ["KATRAIN_DATABASE_URL"])
    with engine.connect() as conn:
        with conn.begin():
            conn.exec_driver_sql("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
            result = capture(conn, args.environment, selection, args.stage)
    if args.stdout:
        sys.stdout.write(json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n")
    else:
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
        print(json.dumps({"environment": args.environment,
                          "eligible_raw_count": result["eligible_raw_count"],
                          "current_null_games": result["current_null_games"],
                          "rejections": len(result["rejections"]),
                          "external_collisions": len(result["external_collisions"]),
                          "ready_for_unsigned_owner_review": result["ready_for_unsigned_owner_review"]}))


if __name__ == "__main__":
    main()
