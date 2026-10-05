"""Approve finite reviewed raw event titles, preserving every SGF and FK.

Prepare is read-only. Apply requires the reviewed plan hash and the research
manifest hash supplied out of band. The ordinary name-batch journal handles undo.
"""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path

from sqlalchemy import create_engine, select

from katrain.web.core.models_db import (
    KifuAlbum, KifuAlbumEventSelection, KifuNameBatch, KifuRawEventName, KifuRawEventValue,
)
from katrain.web.kifu.name_batch import (
    BatchError, _catalog_sha, _fail, _image, _insert, _locked_write, _record_change,
    _snapshot_parts, _source_registry_for_batch, _team_raw_scope, _TEAM_OWNER_ID, _TEAM_RAW, _values_for_table,
)
from katrain.web.kifu.name_candidates import CandidateError, _check_signature, canonical_sha256
from katrain.web.kifu.name_evidence import registry_sha256


RAW_VALUES = (
    "友情杯", "友情杯第１轮", "友情杯第２轮", "友情杯第４轮", "友情杯第３轮", "友情杯第５轮", "友情杯第６轮",
    "第7届招商银行杯电视快棋赛第一轮", "第三届招商银行杯电视快棋赛", "第五届招商银行杯电视快棋赛第一轮",
    "第一届招商银行杯电视快棋赛", "第二届招商银行杯电视快棋赛", "第6届招商银行杯电视快棋赛第一轮",
    "第7届招商银行杯电视快棋赛第二轮", "第四届招商银行杯电视快棋赛第二轮", "第6届招商银行杯电视快棋赛第二轮",
    "第五届招商银行杯电视快棋赛第二轮", "第5届招商银行杯电视快棋赛第三轮",
    "第四届招商银行杯电视快棋赛第三轮", "第四届招商银行杯电视快棋赛第一轮",
    "第1届招商银行杯电视快棋赛", "第5届招商银行杯电视快棋赛", "第5届招商银行杯电视快棋赛第二轮",
    "第2届招商银行杯电视快棋赛",
)
OPERATION = "raw-event-title-owner-review-v1"
_RAW_SET_SHA256 = "60334be3560437f13c50afc7cf3b3324ad2f93a33ec5666b91e5f74b24ff6116"
PROFILE_LIMITS = {
    "first24": {"raw_set_sha256": _RAW_SET_SHA256, "raw_count": 24, "game_total": 493},
    "agon10": {"raw_set_sha256": "2d3598c64fa103cfa1914e9942352151e81dabe76b865b546ba99341a2547a81",
               "raw_count": 10, "game_total": 205},
    "cmb2": {"raw_set_sha256": "9e3ee2d49f318e2a7495ad4040e996d7dffee7a96d838642366d592a2864ee9d",
             "raw_count": 2, "game_total": 2},
    "generic49": {"raw_set_sha256": "17b041004df08a99aa9845060e0d6009f103e612110673e48a6260e2bd1395ab",
                  "raw_count": 49, "game_total": 557},
    "geographic39": {"raw_set_sha256": "996b55aae2bacf4b5b1273d14fb75e5f4c95d1d5bc0451f3759606a1fd4da315",
                     "raw_count": 39, "game_total": 294},
    "team1": {"raw_set_sha256": "6fac391a238c31cdff80bad25d6f2452e9d30f898301a0815af4b3c556cdebfa",
              "raw_count": 1, "game_total": 324},
}


def _profile_limits(profile):
    _fail(profile in PROFILE_LIMITS, "unknown finite raw title owner profile")
    return PROFILE_LIMITS[profile]


def _scope_rows(conn, raw):
    albums = conn.execute(select(KifuAlbum.__table__).where(KifuAlbum.event == raw)
                          .order_by(KifuAlbum.id)).mappings().all()
    _fail(bool(albums), f"no albums for raw event {raw}")
    _fail(all(album["event_id"] is None and album["duplicate_of_id"] is None
              and album["list_hidden_reason"] is None
              for album in albums), f"raw event {raw} gained a link, duplicate, or hidden album")
    ids = [album["id"] for album in albums]
    selected = conn.scalar(select(KifuAlbumEventSelection.album_id).where(
        (KifuAlbumEventSelection.album_id.in_(ids)) | (KifuAlbumEventSelection.selected_raw == raw)).limit(1))
    _fail(selected is None, f"raw event {raw} gained a selected event scope")
    return [{"id": album["id"], "event": album["event"], "event_id": album["event_id"],
             "round_name": album["round_name"], "date_played": album["date_played"],
             "black_rank": album["black_rank"], "white_rank": album["white_rank"],
             "source_path": album["source_path"],
             "sgf_sha256": hashlib.sha256((album["sgf_content"] or "").encode("utf-8")).hexdigest()}
            for album in albums]


def prepare_plan(engine, manifest, environment, registry, *, producer_id, producer_model,
                 reviewer_id, reviewer_model, review_conclusion, produced_at=None, reviewed_at=None,
                 profile="first24"):
    """Build the exact signed after-images after an independent category review."""
    _fail(environment in {"TEST", "PROD"}, "unknown target environment")
    limits = _profile_limits(profile)
    records = manifest.get("records")
    _fail(isinstance(records, list) and len(records) == limits["raw_count"]
          and canonical_sha256(sorted(record["raw_value"] for record in records)) == limits["raw_set_sha256"],
          "research manifest is outside the selected finite owners")
    members = manifest["member_manifest"][environment]["members"]
    by_raw = {member["raw_value"]: member for member in members}
    _fail(len(by_raw) == len(members) == limits["raw_count"]
          and set(by_raw) == {record["raw_value"] for record in records},
          "research member manifest has different raw owners")
    _fail(sum(len(member["album_ids"]) for member in members) == limits["game_total"],
          "research finite owner album total changed")
    if profile == "first24":
        _fail(sum(len(by_raw[raw]["album_ids"]) for raw in RAW_VALUES[:7]) == 271
              and sum(len(by_raw[raw]["album_ids"]) for raw in RAW_VALUES[7:]) == 222,
              "research first-24 group totals changed")
    now = datetime.now(timezone.utc).isoformat()
    signature = {"producer_id": producer_id, "producer_model": producer_model,
                 "produced_at": produced_at or now, "review_status": "approved",
                 "reviewer_id": reviewer_id, "reviewer_model": reviewer_model,
                 "reviewed_at": reviewed_at or now, "review_conclusion": review_conclusion}
    _check_signature(signature)
    digest = canonical_sha256(manifest)
    with engine.connect() as conn:
        inventory_sha, _, _ = _snapshot_parts(conn, inventory_format=4)
        plan = {**signature, "operation": OPERATION, "bundle_format": 2,
                "environment": environment, "research_manifest_sha256": digest,
                "raw_set_sha256": limits["raw_set_sha256"], "inventory_sha256": inventory_sha,
                "catalog_sha256": _catalog_sha(conn), "registry_sha256": registry_sha256(registry),
                "changes": []}
        if profile != "first24":
            plan["profile"] = profile
        for record in records:
            raw = record["raw_value"]
            source_owner = record["owners"][environment]
            before = _image(conn, KifuRawEventValue.__table__, source_owner["raw_event_id"])
            _fail(before == source_owner["preimage"] and before["raw_value"] == raw,
                  f"research owner preimage changed for {raw}")
            if profile == "team1":
                _fail(raw == _TEAM_RAW and before["id"] == _TEAM_OWNER_ID,
                      "team profile requires the fixed existing raw owner")
                team = _team_raw_scope(conn)
                scope, ids = team["rows"], team["all_ids"]
                _fail(source_owner.get("album_scope_preimage") == scope,
                      "team complete album/source preimage differs from reviewed capture")
            else:
                scope = _scope_rows(conn, raw)
                ids = [row["id"] for row in scope]
            _fail(ids == by_raw[raw]["album_ids"], f"research album scope changed for {raw}")
            review = {**signature, "status": "approved", "version": OPERATION,
                      "raw_value": raw, "raw_event_id": before["id"],
                      "scope_sha256": canonical_sha256(scope),
                      "research_manifest_sha256": digest,
                      "category_basis": "Readable literal raw event title; no event identity or link approved"}
            if profile == "team1":
                review["team_scope"] = team["review_scope"]
            after = {**before, "review_status": "approved", "review_metadata": review}
            plan["changes"].append({"before": before, "after": after,
                                    "scope_rows": scope, "occurrence_album_ids": ids})
        return plan


def inspect_plan(conn, plan, registry, expected_manifest_sha256, *, profile="first24"):
    limits = _profile_limits(profile)
    try:
        _check_signature(plan)
    except CandidateError as exc:
        raise BatchError(str(exc)) from exc
    _fail(plan.get("profile", "first24") == profile
          and plan.get("review_status") == "approved" and plan.get("operation") == OPERATION
          and plan.get("bundle_format") == 2 and plan.get("environment") in {"TEST", "PROD"},
          "raw title owner plan is not approved")
    _fail(plan.get("research_manifest_sha256") == expected_manifest_sha256
          and plan.get("registry_sha256") == registry_sha256(registry), "research or registry hash differs")
    changes = plan.get("changes")
    _fail(isinstance(changes, list) and len(changes) == limits["raw_count"]
          and canonical_sha256(sorted(change["before"]["raw_value"] for change in changes)) == limits["raw_set_sha256"]
          and plan.get("raw_set_sha256") == limits["raw_set_sha256"],
          "plan exceeds the selected finite owners")
    _fail(_catalog_sha(conn) == plan["catalog_sha256"], "catalog preimage changed")
    current_inventory, _, _ = _snapshot_parts(conn, inventory_format=4)
    _fail(current_inventory == plan["inventory_sha256"], "album/source inventory changed")
    count = 0
    group_counts = [0, 0]
    for change in changes:
        before, after = change["before"], change["after"]
        _fail(before["category"] == after["category"] == "unclassified_pending"
              and before["parser_version"] == after["parser_version"]
              and before["parsed_data"] == after["parsed_data"]
              and before["review_status"] == "pending" and after["review_status"] == "approved"
              and {key for key in before if before[key] != after[key]} == {"review_status", "review_metadata"},
              "owner plan changes fields outside review approval")
        _fail(_image(conn, KifuRawEventValue.__table__, before["id"]) == before,
              "raw owner complete preimage changed")
        _fail(conn.scalar(select(KifuRawEventName.id).where(KifuRawEventName.raw_event_id == before["id"]).limit(1))
              is None, "raw owner already has names")
        if profile == "team1":
            _fail(before["id"] == _TEAM_OWNER_ID and before["raw_value"] == _TEAM_RAW,
                  "team profile owner differs")
            team = _team_raw_scope(conn)
            scope, ids = team["rows"], team["all_ids"]
        else:
            scope = _scope_rows(conn, before["raw_value"])
            ids = [row["id"] for row in scope]
        _fail(scope == change["scope_rows"] and ids == change["occurrence_album_ids"],
              "raw event EV, SGF, rank, source link, or album scope changed")
        review = after["review_metadata"]
        _fail(isinstance(review, dict) and review.get("status") == review.get("review_status") == "approved"
              and review.get("version") == OPERATION and review.get("raw_value") == before["raw_value"]
              and review.get("raw_event_id") == before["id"]
              and review.get("scope_sha256") == canonical_sha256(scope)
              and review.get("research_manifest_sha256") == expected_manifest_sha256
              and all(review.get(key) == plan[key] for key in (
                  "producer_id", "producer_model", "produced_at", "reviewer_id",
                  "reviewer_model", "reviewed_at", "review_conclusion")),
              "raw owner independent review differs from signed scope")
        if profile == "team1":
            _fail(review.get("team_scope") == team["review_scope"],
                  "team fixed eligible/linked partition differs from signed review")
        count += len(scope)
        if profile == "first24":
            group_counts[0 if before["raw_value"] in RAW_VALUES[:7] else 1] += len(scope)
    _fail(count == limits["game_total"], "finite owner album total changed")
    if profile == "first24":
        _fail(group_counts == [271, 222], "first 24 owner group totals changed")
    return {"ready": True, "raw_owners": limits["raw_count"], "albums": count,
            "name_writes": 0, "fk_writes": 0}


def apply_plan(engine, plan, registry, expected_manifest_sha256, expected_plan_sha256, *, profile="first24"):
    _profile_limits(profile)
    _fail(plan.get("profile", "first24") == profile, "raw title owner profile differs")
    digest = canonical_sha256(plan)
    _fail(digest == expected_plan_sha256, "owner plan hash differs from independently reviewed bytes")
    with _locked_write(engine) as conn:
        previous = conn.execute(select(KifuNameBatch.__table__).where(
            KifuNameBatch.bundle_sha256 == digest)).mappings().one_or_none()
        if previous:
            _fail(previous["status"] == "applied" and previous["reviewed_artifact"]["bundle"] == plan
                  and all(_image(conn, KifuRawEventValue.__table__, change["after"]["id"]) == change["after"]
                          for change in plan["changes"]), "prior raw owner approval changed")
            return {"status": "already_applied", "batch_id": previous["id"], "change_count": 0}
        report = inspect_plan(conn, plan, registry, expected_manifest_sha256, profile=profile)
        registry_id, _ = _source_registry_for_batch(conn, registry, plan)
        batch_id, _ = _insert(conn, KifuNameBatch, {
            "bundle_sha256": digest, "inventory_sha256": plan["inventory_sha256"],
            "source_registry_id": registry_id, "reviewed_artifact": {"bundle": plan}, "status": "pending"})
        table = KifuRawEventValue.__table__
        for sequence, change in enumerate(plan["changes"], 1):
            before, after = change["before"], change["after"]
            conn.execute(table.update().where(table.c.id == before["id"]).values(
                **_values_for_table(table, {"review_status": "approved",
                                            "review_metadata": after["review_metadata"]})))
            _fail(_image(conn, table, before["id"]) == after, "raw owner after-image differs")
            _record_change(conn, batch_id, sequence, KifuRawEventValue, before["id"], before, after)
        conn.execute(KifuNameBatch.__table__.update().where(KifuNameBatch.id == batch_id).values(
            status="applied", applied_at=datetime.now(timezone.utc)))
        return dict(report, status="applied", batch_id=batch_id, change_count=len(plan["changes"]))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("prepare", "dry-run", "apply"))
    parser.add_argument("--plan", type=Path)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--environment", choices=("TEST", "PROD"))
    parser.add_argument("--profile", choices=tuple(PROFILE_LIMITS), default="first24")
    parser.add_argument("--producer-id")
    parser.add_argument("--producer-model")
    parser.add_argument("--reviewer-id")
    parser.add_argument("--reviewer-model")
    parser.add_argument("--review-conclusion")
    parser.add_argument("--expected-manifest-sha256", required=True)
    parser.add_argument("--expected-plan-sha256")
    args = parser.parse_args()
    registry = json.loads(args.registry.read_text())
    engine = create_engine(os.environ["KATRAIN_DATABASE_URL"])
    if args.mode == "prepare":
        manifest = json.loads(args.manifest.read_text())
        _fail(canonical_sha256(manifest) == args.expected_manifest_sha256, "research manifest hash differs")
        result = prepare_plan(engine, manifest, args.environment, registry,
                              producer_id=args.producer_id, producer_model=args.producer_model,
                              reviewer_id=args.reviewer_id, reviewer_model=args.reviewer_model,
                              review_conclusion=args.review_conclusion, profile=args.profile)
    else:
        result = json.loads(args.plan.read_text())
        if args.mode == "dry-run":
            with engine.connect() as conn:
                result = inspect_plan(conn, result, registry, args.expected_manifest_sha256, profile=args.profile)
        else:
            result = apply_plan(engine, result, registry, args.expected_manifest_sha256,
                                args.expected_plan_sha256, profile=args.profile)
    print(json.dumps(result, ensure_ascii=False))
