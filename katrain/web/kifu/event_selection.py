"""Exact duplicate-GN rule and reversible, independently reviewed event selections."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
import re

from sqlalchemy import select

from katrain.core.sgf_parser import ParseError, SGF
from katrain.web.core.models_db import (
    KifuAlbum, KifuAlbumEventSelection, KifuAlbumSource, KifuEventSelectionBatch, KifuEvent,
    KifuEventName, KifuNameBatch, KifuNameChange, KifuNameResearchEvidence, KifuNameSourceRegistry, KifuSource,
)
from katrain.web.kifu.name_candidates import (
    CandidateError, LANGUAGES, _iso_date, _played_date_bounds, _validate_candidate,
    canonical_sha256, identity_scope_sha256,
)
from katrain.web.kifu.name_evidence import registry_sha256
from katrain.web.kifu.name_parse import parse_event
from katrain.web.kifu.provenance import classify_source_path, sgf_sha256


class EventSelectionError(ValueError):
    """The reviewed selection does not match the live album or audit evidence."""


RULE_VERSION = "19x19-gnugo-second-gn-v1"
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_MEMBER_KEYS = {
    "album_id",
    "old_event",
    "old_event_id",
    "old_source",
    "old_source_path",
    "old_date_played",
    "old_round_name",
    "old_board_size",
    "sgf_sha256",
    "property_name",
    "property_index",
    "selected_raw",
    "rule_version",
}
_REVIEW_KEYS = {
    "reviewer_id",
    "reviewer_model",
    "reviewed_at",
    "review_conclusion",
    "evidence_scope",
    "status",
    "member_set_sha256",
    "basis",
    "review_signature",
}
_BUNDLE_KEYS = {
    "selection_format",
    "rule_version",
    "members",
    "member_set_sha256",
    "producer_id",
    "producer_model",
    "produced_at",
    "scope_frozen_at",
    "review",
}
_EVIDENCE_SCOPE_KEYS = {"member_set_sha256", "album_count", "reviewed_material"}
_ALBUM_PREIMAGE = {
    "event": "old_event",
    "event_id": "old_event_id",
    "source": "old_source",
    "source_path": "old_source_path",
    "date_played": "old_date_played",
    "round_name": "old_round_name",
    "board_size": "old_board_size",
}


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise EventSelectionError(message)


def _timestamp(value: object, label: str) -> datetime:
    _require(isinstance(value, str), f"{label} is required")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise EventSelectionError(f"{label} is invalid") from exc
    _require(parsed.tzinfo is not None, f"{label} needs a timezone")
    return parsed


def selected_second_gn(root, source_folder: str) -> str | None:
    """Return GN[1] only for the audited 19x19 program-label pattern."""
    game_names = root.get_list_property("GN") or []
    game_comments = root.get_list_property("GC") or []
    if (
        "EV" not in root.properties
        and source_folder == "19x19"
        and root.get_property("SO") == "https://19x19.com"
        and len(game_names) == 2
        and game_names[0] == "GNUGo3.8"
        and game_names[1]
        and parse_event(game_names[1], None).category not in {"program_source_label", "corrupt_data"}
        and len(game_comments) == 1
        and (game_comments[0] == game_names[1] or game_comments[0].startswith(game_names[1] + " | "))
    ):
        return game_names[1]
    return None


def validate_bundle(bundle: dict) -> dict:
    """Validate the finite artifact and its independently signed member set offline."""
    _require(isinstance(bundle, dict) and set(bundle) == _BUNDLE_KEYS, "selection bundle fields differ")
    _require(
        bundle["selection_format"] == 1 and bundle["rule_version"] == RULE_VERSION,
        "selection bundle rule version differs",
    )
    members = bundle["members"]
    _require(isinstance(members, list) and members, "finite members are required")
    _require(
        isinstance(bundle["producer_id"], str) and bool(bundle["producer_id"].strip()), "producer identity is required"
    )
    _require(
        isinstance(bundle["producer_model"], str) and bool(bundle["producer_model"].strip()),
        "actual producer model is required",
    )
    produced_at = _timestamp(bundle["produced_at"], "production time")
    frozen_at = _timestamp(bundle["scope_frozen_at"], "scope freeze time")
    _require(produced_at <= frozen_at, "scope freeze precedes production")
    ids = []
    for index, member in enumerate(members):
        _require(isinstance(member, dict) and set(member) == _MEMBER_KEYS, f"member[{index}] fields differ")
        album_id = member["album_id"]
        _require(type(album_id) is int and album_id > 0, f"member[{index}] album ID invalid")
        ids.append(album_id)
        _require(
            member["old_event"] == "GNUGo3.8" and member["old_event_id"] is None,
            f"member[{index}] legacy event preimage differs",
        )
        _require(
            member["old_board_size"] == 19
            and member["old_source"] == "https://19x19.com"
            and isinstance(member["old_source_path"], str)
            and classify_source_path(member["old_source_path"]) == "19x19",
            f"member[{index}] source preimage differs",
        )
        _require(
            member["property_name"] == "GN"
            and member["property_index"] == 1
            and member["rule_version"] == RULE_VERSION,
            f"member[{index}] selection rule differs",
        )
        _require(
            isinstance(member["selected_raw"], str) and bool(member["selected_raw"].strip()),
            f"member[{index}] selected value is empty",
        )
        _require(
            isinstance(member["sgf_sha256"], str) and _SHA256.fullmatch(member["sgf_sha256"]) is not None,
            f"member[{index}] SGF SHA-256 invalid",
        )
        for field in ("old_date_played", "old_round_name"):
            _require(member[field] is None or isinstance(member[field], str), f"member[{index}] {field} invalid")
    _require(ids == sorted(set(ids)), "duplicate or unsorted member IDs")
    member_hash = canonical_sha256(members)
    _require(bundle["member_set_sha256"] == member_hash, "member set hash mismatch")
    review = bundle["review"]
    _require(isinstance(review, dict) and set(review) == _REVIEW_KEYS, "review signature fields differ")
    _require(
        review["status"] == "approved" and review["member_set_sha256"] == member_hash,
        "member set lacks approved independent review",
    )
    _require(
        isinstance(review["reviewer_id"], str)
        and bool(review["reviewer_id"].strip())
        and review["reviewer_id"] != bundle["producer_id"],
        "reviewer must differ from producer",
    )
    _require(
        isinstance(review["reviewer_model"], str) and bool(review["reviewer_model"].strip()),
        "actual reviewer model is required",
    )
    _require(review["review_conclusion"] == "approved_second_gn_selection", "explicit review conclusion differs")
    scope = review["evidence_scope"]
    _require(
        isinstance(scope, dict)
        and set(scope) == _EVIDENCE_SCOPE_KEYS
        and scope["member_set_sha256"] == member_hash
        and scope["album_count"] == len(members)
        and isinstance(scope["reviewed_material"], str)
        and bool(scope["reviewed_material"].strip()),
        "review evidence scope does not bind the frozen member set",
    )
    _require(isinstance(review["basis"], str) and bool(review["basis"].strip()), "review basis is required")
    reviewed_at = _timestamp(review["reviewed_at"], "review time")
    _require(reviewed_at > frozen_at, "review precedes or coincides with scope freeze")
    signed = {key: value for key, value in review.items() if key != "review_signature"}
    _require(review["review_signature"] == canonical_sha256(signed), "independent review signature mismatch")
    return {
        "ready": True,
        "member_count": len(members),
        "member_set_sha256": member_hash,
        "bundle_sha256": canonical_sha256(bundle),
    }


def _album_preimage(album: dict, member: dict) -> None:
    for current_key, member_key in _ALBUM_PREIMAGE.items():
        _require(album[current_key] == member[member_key], f"album {member['album_id']} {current_key} preimage changed")
    _require(
        sgf_sha256(album["sgf_content"]) == member["sgf_sha256"], f"album {member['album_id']} SGF preimage changed"
    )
    try:
        root = SGF.parse_sgf(album["sgf_content"])
        selected = selected_second_gn(root, classify_source_path(album["source_path"]))
    except (ParseError, ValueError, TypeError, AttributeError, IndexError) as exc:
        raise EventSelectionError(f"album {member['album_id']} SGF cannot be checked") from exc
    _require(
        selected is not None and selected == member["selected_raw"],
        f"album {member['album_id']} reviewed GN[1] differs from SGF",
    )


def _image(row) -> dict:
    return {key: value.isoformat() if isinstance(value, datetime) else value for key, value in row.items()}


def audited_selection_images(batch) -> dict[int, dict] | None:
    """Return signed after-images only for an intact, independently reviewed applied batch."""
    try:
        if batch["status"] != "applied":
            return None
        artifact = batch["reviewed_artifact"]
        bundle = artifact["bundle"]
        report = validate_bundle(bundle)
        before = artifact["before_images"]
        after = artifact["after_images"]
        review = bundle["review"]
        reviewed_at = _timestamp(review["reviewed_at"], "review time")
        stored_reviewed_at = batch["reviewed_at"]
        if stored_reviewed_at.tzinfo is None:
            reviewed_at = reviewed_at.replace(tzinfo=None)
        if not (
            report["bundle_sha256"] == batch["bundle_sha256"]
            and report["member_set_sha256"] == batch["member_set_sha256"]
            and before == bundle["members"]
            and isinstance(after, list) and len(before) == len(after)
            and batch["producer_id"] == bundle["producer_id"]
            and batch["reviewer_id"] == review["reviewer_id"]
            and stored_reviewed_at == reviewed_at
        ):
            return None
        images = {}
        image_keys = set(KifuAlbumEventSelection.__table__.columns.keys())
        for member, image in zip(before, after):
            expected = {
                "album_id": member["album_id"],
                "event_id": None,
                "batch_id": batch["id"],
                "selected_raw": member["selected_raw"],
                "sgf_sha256": member["sgf_sha256"],
                "property_name": member["property_name"],
                "property_index": member["property_index"],
                "status": "approved",
                "rule_version": member["rule_version"],
                "reviewer_id": review["reviewer_id"],
                "reviewed_at": stored_reviewed_at.isoformat(),
            }
            if not isinstance(image, dict) or set(image) != image_keys or any(
                image.get(key) != value for key, value in expected.items()
            ):
                return None
            images[member["album_id"]] = image
        return images
    except (EventSelectionError, KeyError, TypeError, AttributeError, ValueError):
        return None


def selection_matches_audit(selection, images: dict[int, dict] | None) -> bool:
    """Require the entire live selection row to match its approved after-image."""
    return bool(images is not None and images.get(selection["album_id"]) == _image(selection))


def name_link_proof_sha256(batch_id: int, bundle_sha256: str, change_id: int,
                           before_image: dict, after_image: dict) -> str:
    """Pin the exact applied name-ledger row used to justify one selected-event FK."""
    return canonical_sha256({"batch_id": batch_id, "bundle_sha256": bundle_sha256,
                             "change_id": change_id, "before_image": before_image,
                             "after_image": after_image})


def _same_review_time(stored: datetime, signed: str) -> bool:
    expected = _timestamp(signed, "name review time")
    return stored == (expected.replace(tzinfo=None) if stored.tzinfo is None else expected)


def _raw_scope_sha256(conn, raw: str, cache: dict, source_batch_cache: dict) -> str | None:
    """Rebuild the original raw-event slots from live albums and source-valid selections."""
    if raw in cache:
        return cache[raw]
    slots = [[album_id, "event"] for album_id in conn.scalars(select(KifuAlbum.id).where(KifuAlbum.event == raw))]
    selections = list(conn.execute(select(KifuAlbumEventSelection.__table__).where(
        KifuAlbumEventSelection.selected_raw == raw)).mappings())
    selection_ids = {row["album_id"] for row in selections}
    albums = {row["id"]: row for row in conn.execute(select(KifuAlbum.__table__).where(
        KifuAlbum.id.in_(selection_ids))).mappings()} if selection_ids else {}
    batch_ids = {row["batch_id"] for row in selections}
    missing_batch_ids = batch_ids - source_batch_cache.keys()
    batches = {row["id"]: row for row in conn.execute(select(KifuEventSelectionBatch.__table__).where(
        KifuEventSelectionBatch.id.in_(missing_batch_ids))).mappings()} if missing_batch_ids else {}
    for batch_id in missing_batch_ids:
        batch = batches.get(batch_id)
        images = audited_selection_images(batch) if batch is not None else None
        members = {item["album_id"]: item for item in batch["reviewed_artifact"]["bundle"]["members"]} \
            if images is not None else {}
        source_batch_cache[batch_id] = (images, members)
    for selection in selections:
        images, members = source_batch_cache[selection["batch_id"]]
        album = albums.get(selection["album_id"])
        source_image = (images or {}).get(selection["album_id"])
        member = members.get(selection["album_id"])
        if (album is None or source_image is None or member is None
                or {**source_image, "event_id": selection["event_id"]} != _image(selection)
                or any(album[key] != member[old_key] for key, old_key in _ALBUM_PREIMAGE.items())
                or sgf_sha256(album["sgf_content"]) != selection["sgf_sha256"]):
            cache[raw] = None
            return None
        try:
            selected = selected_second_gn(SGF.parse_sgf(album["sgf_content"]),
                                          classify_source_path(album["source_path"]))
        except (ParseError, ValueError, TypeError, AttributeError, IndexError):
            selected = None
        if selected != raw:
            cache[raw] = None
            return None
        slots.append([selection["album_id"], "selected_event"])
    cache[raw] = canonical_sha256(sorted(slots)) if slots else None
    return cache[raw]


def _reviewed_name_links(conn, batch, raw_scope_cache: dict, source_batch_cache: dict) -> tuple[dict, dict] | None:
    """Check the finite v4 identity scope independently of change-row images."""
    try:
        if batch["status"] != "applied":
            return None
        artifact = batch["reviewed_artifact"]
        bundle = artifact["bundle"]
        if (bundle["bundle_format"] != 4 or bundle["inventory_format"] != 4
                or canonical_sha256(bundle) != batch["bundle_sha256"]
                or bundle["inventory_sha256"] != batch["inventory_sha256"]):
            return None
        members, candidates, owners, links = (bundle[key] for key in ("members", "candidates", "owners", "album_links"))
        if (not all(isinstance(items, list) and items for items in (members, candidates, owners, links))
                or bundle["member_set_sha256"] != canonical_sha256(members)
                or bundle["owner_set_sha256"] != canonical_sha256(owners)
                or bundle["link_set_sha256"] != canonical_sha256(links)):
            return None
        def member_key(item):
            owner = item["owner"]
            return (owner["kind"], owner.get("id", owner.get("ref")), item["lang"])

        member_keys = [member_key(item) for item in members]
        if len(set(member_keys)) != len(member_keys):
            return None
        member_map = {member_key(item): item for item in members}
        if (len(candidates) != len(members) or {member_key(item) for item in candidates} != set(member_map)
                or any(item.get("raw_value") != member_map[member_key(item)].get("raw_value")
                       or item.get("review_status") != "approved"
                       or not item.get("producer_id") or not item.get("reviewer_id")
                       or item["producer_id"] == item["reviewer_id"] for item in candidates)):
            return None
        declarations = {}
        for declaration in owners:
            target = declaration["owner"]
            token = f"{target['kind']}:{target['id']}" if "id" in target else f"{target['kind']}:@{target['ref']}"
            if token in declarations:
                return None
            declarations[token] = declaration
        groups = {}
        seen = set()
        for link in links:
            album_id = link["album_id"]
            if link["slot"] != "selected_event" or album_id in seen:
                return None
            seen.add(album_id)
            target = link["target"]
            if target["kind"] != "event":
                return None
            token = f"event:{target['id']}" if "id" in target else f"event:@{target['ref']}"
            declaration = declarations.get(token)
            if declaration is None:
                return None
            review = link["identity_review"]
            context = declaration["identity_context"]
            if (review["event_period"] != {key: context[key] for key in ("start_date", "end_date")}
                    or review["event_region"] != context["region"]):
                return None
            if (review["status"] != "approved" or not review["producer_id"] or not review["producer_model"]
                    or not review["reviewer_id"] or not review["reviewer_model"]
                    or review["producer_id"] == review["reviewer_id"]
                    or not review["review_conclusion"] or not review["identity_basis"]
                    or not review["event_period_basis"] or not review["event_region_basis"]
                    or not review["source_checks"]):
                return None
            produced = _timestamp(review["produced_at"], "identity production time")
            frozen = _timestamp(review["scope_frozen_at"], "identity freeze time")
            reviewed = _timestamp(review["reviewed_at"], "identity review time")
            if not produced <= frozen < reviewed:
                return None
            for check in review["source_checks"]:
                if (not check["url"].startswith("https://") or not _SHA256.fullmatch(check["body_sha256"])
                        or not check["body_excerpt"] or not check["identity_match"]
                        or _timestamp(check["fetched_at"], "source capture time") > produced):
                    return None
            group_key = (token, link["selection_before_image"]["selected_raw"])
            groups.setdefault(group_key, []).append(link)
        for (token, _raw), group in groups.items():
            expected_scope = identity_scope_sha256(bundle, group, declarations[token])
            first_review = group[0]["identity_review"]
            if any(link["identity_review"] != first_review
                   or link["identity_review"]["scope_sha256"] != expected_scope
                   or link["raw_scope_sha256"] != _raw_scope_sha256(conn, _raw, raw_scope_cache,
                                                                      source_batch_cache)
                   for link in group):
                return None
            target = group[0]["target"]
            if any(member_key(item) not in member_map for item in (
                    {"owner": target, "lang": lang} for lang in LANGUAGES)):
                return None
        if not _name_batch_targets_proved(conn, batch, bundle, declarations, candidates, groups):
            return None
        return ({link["album_id"]: link for link in links}, declarations)
    except (EventSelectionError, CandidateError, KeyError, TypeError, AttributeError, ValueError):
        return None


def _name_batch_targets_proved(conn, batch, bundle, declarations, candidates, groups) -> bool:
    """Check persisted approval and ledger proof; historical inventory is unavailable for replay."""
    registry_row = conn.execute(select(KifuNameSourceRegistry.__table__).where(
        KifuNameSourceRegistry.id == batch["source_registry_id"])).mappings().one_or_none()
    if registry_row is None:
        return False
    registry = registry_row["registry"]
    if (registry_row["version"] != bundle.get("registry_version")
            or registry_row["sha256"] != bundle.get("registry_sha256")
            or registry_sha256(registry) != registry_row["sha256"]
            or set(registry.get("language_tags", {})) != LANGUAGES):
        return False
    expected_research_hashes = sorted(row["research_sha256"] for row in candidates if row.get("research_sha256"))
    if batch["reviewed_artifact"].get("research_hashes") != expected_research_hashes:
        return False
    changes = list(conn.execute(select(KifuNameChange.__table__).where(
        KifuNameChange.batch_id == batch["id"],
        KifuNameChange.target_table.in_((KifuEventName.__tablename__, KifuNameResearchEvidence.__tablename__))
    )).mappings())
    name_changes = {change["target_row_id"]: change for change in changes
                    if change["target_table"] == KifuEventName.__tablename__}
    evidence_changes = {change["target_row_id"]: change for change in changes
                        if change["target_table"] == KifuNameResearchEvidence.__tablename__}
    names = {row["id"]: row for row in conn.execute(select(KifuEventName.__table__).where(
        KifuEventName.id.in_(name_changes))).mappings()} if name_changes else {}
    later_changes = list(conn.execute(select(KifuNameChange.__table__).where(
        KifuNameChange.target_table == KifuEventName.__tablename__,
        KifuNameChange.target_row_id.in_(name_changes),
        KifuNameChange.batch_id != batch["id"])).mappings()) if name_changes else []
    later_batch_ids = {change["batch_id"] for change in later_changes}
    later_statuses = {row["id"]: row["status"] for row in conn.execute(select(
        KifuNameBatch.id, KifuNameBatch.status).where(KifuNameBatch.id.in_(later_batch_ids))).mappings()}
    name_history = {}
    for change in later_changes:
        original = name_changes[change["target_row_id"]]
        if change["id"] > original["id"] and later_statuses.get(change["batch_id"]) == "applied":
            name_history.setdefault(change["target_row_id"], []).append(change)
    evidence = {row["id"]: row for row in conn.execute(select(KifuNameResearchEvidence.__table__).where(
        KifuNameResearchEvidence.id.in_(evidence_changes))).mappings()} if evidence_changes else {}
    candidate_map = {(canonical_sha256(row["owner"]), row["lang"]): row for row in candidates}
    resolved = batch["reviewed_artifact"].get("resolved_refs", {})
    for token, _raw in groups:
        owner = declarations[token]["owner"]
        owner_id = resolved.get(token)
        if type(owner_id) is not int or owner_id <= 0:
            return False
        if "id" in owner and owner_id != owner["id"]:
            return False
        for lang in LANGUAGES:
            candidate = candidate_map.get((canonical_sha256(owner), lang))
            if candidate is None or candidate.get("review_status") != "approved":
                return False
            matching_names = [row for row in names.values() if row["event_id"] == owner_id and row["lang"] == lang]
            if len(matching_names) != 1:
                return False
            name = matching_names[0]
            name_change = name_changes[name["id"]]
            expected_name = name_change["after_image"]
            for later in sorted(name_history.get(name["id"], ()), key=lambda item: item["id"]):
                if later["before_image"] != expected_name:
                    return False
                expected_name = later["after_image"]
            original_name = name_change["after_image"]
            original_evidence_id = original_name.get("evidence_id") if isinstance(original_name, dict) else None
            evidence_row = evidence.get(original_evidence_id)
            evidence_change = evidence_changes.get(original_evidence_id)
            if (expected_name != _image(name) or original_name.get("status") != "verified"
                    or evidence_row is None or evidence_change is None
                    or evidence_change["before_image"] is not None
                    or evidence_change["after_image"] != _image(evidence_row)
                    or evidence_row["event_id"] != owner_id or evidence_row["lang"] != lang
                    or evidence_row["source_registry_id"] != registry_row["id"]
                    or evidence_row["review_status"] != "approved"
                    or evidence_row["candidate_name"] != candidate.get("display_name")
                    or evidence_row["producer_id"] != candidate.get("producer_id")
                    or evidence_row["producer_model"] != candidate.get("producer_model")
                    or not _same_review_time(evidence_row["produced_at"], candidate.get("produced_at"))
                    or evidence_row["reviewer_id"] != candidate.get("reviewer_id")
                    or evidence_row["reviewer_model"] != candidate.get("reviewer_model")
                    or not _same_review_time(evidence_row["reviewed_at"], candidate.get("reviewed_at"))
                    or evidence_row["decision_kind"] != candidate.get("decision_kind")
                    or evidence_row["generation_rule_version"] != candidate.get("generation_rule_version")
                    or original_name.get("event_id") != owner_id or original_name.get("lang") != lang
                    or original_name.get("display_name") != candidate.get("display_name")
                    or original_name.get("decision_kind") != candidate.get("decision_kind")
                    or original_name.get("generation_rule_version") != candidate.get("generation_rule_version")
                    or original_name.get("revision") != evidence_row["revision"]):
                return False
            payload = evidence_row["research_payload"]
            research = payload.get("research") if isinstance(payload, dict) else None
            if payload.get("candidate") != candidate or canonical_sha256(research) != candidate.get("research_sha256"):
                return False
            _validate_candidate(candidate, research, registry, {"event": {owner_id}},
                                declarations=declarations, link_targets={token})
            preimage = candidate.get("name_preimage_sha256")
            if preimage != (canonical_sha256(name_change["before_image"])
                            if name_change["before_image"] is not None else None):
                return False
            binding = candidate.get("preimage_binding")
            if (not isinstance(binding, dict) or binding.get("name_preimage_sha256") != preimage
                    or not binding.get("actor_id") or binding["actor_id"] == candidate["reviewer_id"]
                    or not binding.get("actor_model") or not _timestamp(binding.get("captured_at"), "name capture time")
                    <= _timestamp(binding.get("bound_at"), "name binding time")
                    <= _timestamp(candidate.get("reviewed_at"), "name review time")):
                return False
    return True


def verified_selection_rows(conn, selections) -> dict[int, dict]:
    """Batch-check source, live SGF and unique name-link evidence for read consumers."""
    from katrain.web.kifu.name_inventory import ASSOCIATION_COLUMNS, SOURCE_COLUMNS

    selections = [dict(row) for row in selections]
    if not selections:
        return {}
    album_ids = {row["album_id"] for row in selections}
    source_ids = {row["batch_id"] for row in selections}
    albums = {row["id"]: row for row in conn.execute(
        select(KifuAlbum.__table__).where(KifuAlbum.id.in_(album_ids))).mappings()}
    associations = {album_id: {key: album[key] for key in ASSOCIATION_COLUMNS if key != "sources"} | {"sources": []}
                    for album_id, album in albums.items()}
    for source_id, album_id, dataset_id, key, path, method in conn.execute(
            select(*SOURCE_COLUMNS).join(KifuSource, KifuAlbumSource.source_id == KifuSource.id)
            .where(KifuAlbumSource.album_id.in_(album_ids)).order_by(KifuAlbumSource.id)):
        associations[album_id]["sources"].append([source_id, dataset_id, key, path, method])
    source_batches = {row["id"]: row for row in conn.execute(
        select(KifuEventSelectionBatch.__table__).where(KifuEventSelectionBatch.id.in_(source_ids))).mappings()}
    source_images = {batch_id: audited_selection_images(source_batches.get(batch_id))
                     if source_batches.get(batch_id) is not None else None for batch_id in source_ids}
    source_members = {batch_id: {member["album_id"]: member for member in batch["reviewed_artifact"]["bundle"]["members"]}
                      for batch_id, batch in source_batches.items() if source_images[batch_id] is not None}
    changes = {}
    for change in conn.execute(select(KifuNameChange.__table__).where(
            KifuNameChange.target_table == KifuAlbumEventSelection.__tablename__,
            KifuNameChange.target_row_id.in_(album_ids))).mappings():
        changes.setdefault(change["target_row_id"], []).append(change)
    name_ids = {change["batch_id"] for group in changes.values() for change in group}
    name_batches = {row["id"]: row for row in conn.execute(
        select(KifuNameBatch.__table__).where(KifuNameBatch.id.in_(name_ids))).mappings()} if name_ids else {}
    raw_scope_cache = {}
    source_batch_cache = {batch_id: (source_images[batch_id], source_members.get(batch_id, {}))
                          for batch_id in source_ids}
    reviewed_links = {batch_id: _reviewed_name_links(conn, batch, raw_scope_cache, source_batch_cache)
                      for batch_id, batch in name_batches.items()}
    event_ids = {row["event_id"] for row in selections if row["event_id"] is not None}
    events = {row["id"]: row for row in conn.execute(select(KifuEvent.__table__).where(
        KifuEvent.id.in_(event_ids))).mappings()} if event_ids else {}
    event_changes = {}
    if name_ids:
        for change in conn.execute(select(KifuNameChange.__table__).where(
                KifuNameChange.batch_id.in_(name_ids),
                KifuNameChange.target_table == KifuEvent.__tablename__)).mappings():
            event_changes[(change["batch_id"], change["target_row_id"])] = change
    verified = {}
    for selection in selections:
        album_id = selection["album_id"]
        album = albums.get(album_id)
        source_image = (source_images.get(selection["batch_id"]) or {}).get(album_id)
        member = source_members.get(selection["batch_id"], {}).get(album_id)
        if album is None or source_image is None or member is None:
            continue
        if any(album[current_key] != member[member_key] for current_key, member_key in _ALBUM_PREIMAGE.items()):
            continue
        content = album["sgf_content"]
        if not isinstance(content, str) or sgf_sha256(content) != selection["sgf_sha256"]:
            continue
        try:
            raw = selected_second_gn(SGF.parse_sgf(content), classify_source_path(album["source_path"]))
        except (ParseError, ValueError, TypeError, AttributeError, IndexError):
            continue
        if raw != selection["selected_raw"]:
            continue
        current_image = _image(selection)
        active = [(change, name_batches[change["batch_id"]]) for change in changes.get(album_id, ())
                  if change["batch_id"] in name_batches and name_batches[change["batch_id"]]["status"] == "applied"]
        proof = {"event_id": selection["event_id"], "source_after_image": source_image,
                 "source_after_sha256": canonical_sha256(source_image),
                 "name_batch_id": None, "name_proof_sha256": None}
        if selection_matches_audit(selection, source_images[selection["batch_id"]]) and not active:
            verified[album_id] = proof
            continue
        if (type(selection["event_id"]) is not int or selection["event_id"] <= 0
                or {**source_image, "event_id": selection["event_id"]} != current_image):
            continue
        if len(active) != 1:
            continue
        change, name_batch = active[0]
        reviewed = reviewed_links.get(name_batch["id"])
        if (reviewed is None or change["before_image"] != source_image
                or change["after_image"] != current_image):
            continue
        link, declarations = reviewed[0].get(album_id), reviewed[1]
        if (link is None or link["selection_batch_id"] != selection["batch_id"]
                or link["association_sha256"] != canonical_sha256(associations[album_id])
                or link["selection_bundle_sha256"] != source_batches[selection["batch_id"]]["bundle_sha256"]
                or link["selection_before_image"] != source_image
                or link["selection_before_sha256"] != proof["source_after_sha256"]
                or link["production_sgf_sha256"] != selection["sgf_sha256"]
                or link["expected"]["old_id"] is not None
                or any(album[field] != link["expected"][field] for field in (
                    "player_black", "player_white", "event", "date_played", "round_name",
                    "black_rank", "white_rank"))):
            continue
        target = link["target"]
        token = f"event:{target['id']}" if "id" in target else f"event:@{target['ref']}"
        resolved = name_batch["reviewed_artifact"].get("resolved_refs", {})
        if resolved.get(token) != selection["event_id"]:
            continue
        declaration = declarations[token]
        context = declaration["identity_context"]
        played_bounds = _played_date_bounds(album["date_played"])
        if (played_bounds is None or _iso_date(context["start_date"]) is None
                or _iso_date(context["end_date"]) is None
                or not _iso_date(context["start_date"]) <= played_bounds[0]
                or not played_bounds[1] <= _iso_date(context["end_date"])):
            continue
        event_row = events.get(selection["event_id"])
        if event_row is None:
            continue
        if "id" in target:
            if declaration.get("preimage", {}).get("canonical_name") != event_row["canonical_name"]:
                continue
        else:
            if declaration.get("create", {}).get("canonical_name") != event_row["canonical_name"]:
                continue
            created = event_changes.get((name_batch["id"], selection["event_id"]))
            if created is None or created["before_image"] is not None or created["after_image"] != _image(event_row):
                continue
        proof["name_batch_id"] = name_batch["id"]
        proof["name_proof_sha256"] = name_link_proof_sha256(name_batch["id"], name_batch["bundle_sha256"],
                                                             change["id"], source_image, current_image)
        verified[album_id] = proof
    return verified


def _audit_images_match_review(batch) -> bool:
    return audited_selection_images(batch) is not None


def _inspect(conn, bundle: dict) -> dict:
    result = validate_bundle(bundle)
    albums = KifuAlbum.__table__
    selections = KifuAlbumEventSelection.__table__
    for member in bundle["members"]:
        album = conn.execute(select(albums).where(albums.c.id == member["album_id"])).mappings().one_or_none()
        _require(album is not None, f"album {member['album_id']} preimage missing")
        _album_preimage(album, member)
        current = conn.execute(
            select(selections.c.album_id).where(selections.c.album_id == member["album_id"])
        ).scalar_one_or_none()
        _require(current is None, f"album {member['album_id']} already selected")
    return {**result, "status": "ready"}


def dry_run_bundle(engine, bundle: dict) -> dict:
    """Read every live preimage without writing or migrating the catalog."""
    validate_bundle(bundle)
    if engine.dialect.name == "sqlite" and engine.url.database not in (None, ":memory:"):
        _require(Path(engine.url.database).is_file(), "SQLite database does not exist for dry-run")
    with engine.connect() as conn:
        return _inspect(conn, bundle)


@contextmanager
def _locked_write(engine):
    conn = engine.connect()
    try:
        if engine.dialect.name == "postgresql":
            conn = conn.execution_options(isolation_level="READ COMMITTED")
            conn.begin()
            conn.exec_driver_sql("SELECT pg_advisory_xact_lock(%s)", (720220261003,))
            conn.exec_driver_sql(
                "LOCK TABLE kifu_albums, kifu_album_event_selections, "
                "kifu_event_selection_batches IN SHARE ROW EXCLUSIVE MODE"
            )
        elif engine.dialect.name == "sqlite":
            conn.exec_driver_sql("PRAGMA foreign_keys=ON")
            _require(
                conn.exec_driver_sql("PRAGMA foreign_keys").scalar_one() == 1, "SQLite foreign keys must be enabled"
            )
            conn.exec_driver_sql("BEGIN IMMEDIATE")
        else:
            raise EventSelectionError("Only PostgreSQL and SQLite are supported")
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def apply_bundle(engine, bundle: dict, *, expected_bundle_sha256: str | None = None) -> dict:
    """Atomically add only the reviewed derived selections after live rechecks."""
    report = validate_bundle(bundle)
    _require(expected_bundle_sha256 is not None, "trusted full bundle SHA-256 is required")
    _require(
        isinstance(expected_bundle_sha256, str)
        and _SHA256.fullmatch(expected_bundle_sha256) is not None
        and expected_bundle_sha256 == report["bundle_sha256"],
        "trusted full bundle SHA-256 does not match",
    )
    batches = KifuEventSelectionBatch.__table__
    selections = KifuAlbumEventSelection.__table__
    with _locked_write(engine) as conn:
        prior = (
            conn.execute(select(batches).where(batches.c.bundle_sha256 == report["bundle_sha256"]))
            .mappings()
            .one_or_none()
        )
        if prior is not None:
            artifact = prior["reviewed_artifact"]
            _require(
                prior["status"] == "applied"
                and artifact["bundle"] == bundle
                and _audit_images_match_review(prior),
                "bundle was undone or its audit artifact changed",
            )
            for member in bundle["members"]:
                album = (
                    conn.execute(select(KifuAlbum.__table__).where(KifuAlbum.id == member["album_id"]))
                    .mappings()
                    .one_or_none()
                )
                _require(album is not None, f"album {member['album_id']} changed since apply")
                try:
                    _album_preimage(album, member)
                except EventSelectionError as exc:
                    raise EventSelectionError(f"album {member['album_id']} changed since apply") from exc
            for expected in artifact["after_images"]:
                current = (
                    conn.execute(select(selections).where(selections.c.album_id == expected["album_id"]))
                    .mappings()
                    .one_or_none()
                )
                _require(
                    current is not None and _image(current) == expected,
                    f"selection for album {expected['album_id']} changed since apply",
                )
            return {
                "status": "already_applied",
                "batch_id": prior["id"],
                "change_count": 0,
                "bundle_sha256": report["bundle_sha256"],
            }
        _inspect(conn, bundle)
        review = bundle["review"]
        reviewed_at = datetime.fromisoformat(review["reviewed_at"].replace("Z", "+00:00"))
        artifact = {"bundle": bundle, "before_images": bundle["members"], "after_images": []}
        batch_id = conn.execute(
            batches.insert().values(
                bundle_sha256=report["bundle_sha256"],
                member_set_sha256=report["member_set_sha256"],
                reviewed_artifact=artifact,
                producer_id=bundle["producer_id"],
                reviewer_id=review["reviewer_id"],
                reviewed_at=reviewed_at,
                status="applied",
                applied_at=datetime.now(timezone.utc),
            )
        ).inserted_primary_key[0]
        for member in bundle["members"]:
            conn.execute(
                selections.insert().values(
                    album_id=member["album_id"],
                    event_id=None,
                    batch_id=batch_id,
                    selected_raw=member["selected_raw"],
                    sgf_sha256=member["sgf_sha256"],
                    property_name="GN",
                    property_index=1,
                    status="approved",
                    rule_version=RULE_VERSION,
                    reviewer_id=review["reviewer_id"],
                    reviewed_at=reviewed_at,
                )
            )
            after = conn.execute(select(selections).where(selections.c.album_id == member["album_id"])).mappings().one()
            artifact["after_images"].append(_image(after))
        conn.execute(batches.update().where(batches.c.id == batch_id).values(reviewed_artifact=artifact))
        return {
            "status": "applied",
            "batch_id": batch_id,
            "change_count": len(bundle["members"]),
            "bundle_sha256": report["bundle_sha256"],
        }


def batch_status(engine, batch_id: int) -> dict:
    with engine.connect() as conn:
        batch = (
            conn.execute(select(KifuEventSelectionBatch.__table__).where(KifuEventSelectionBatch.id == batch_id))
            .mappings()
            .one_or_none()
        )
        _require(batch is not None, f"batch {batch_id} not found")
        return {
            "batch_id": batch_id,
            "status": batch["status"],
            "bundle_sha256": batch["bundle_sha256"],
            "member_set_sha256": batch["member_set_sha256"],
            "member_count": len(batch["reviewed_artifact"]["before_images"]),
        }


def undo_batch(engine, batch_id: int) -> dict:
    """Remove this batch only if every album and selection still matches its after-image."""
    batches = KifuEventSelectionBatch.__table__
    selections = KifuAlbumEventSelection.__table__
    albums = KifuAlbum.__table__
    with _locked_write(engine) as conn:
        batch = conn.execute(select(batches).where(batches.c.id == batch_id)).mappings().one_or_none()
        _require(batch is not None, f"batch {batch_id} not found")
        _require(batch["status"] == "applied", "batch is not applied")
        artifact = batch["reviewed_artifact"]
        before = artifact["before_images"]
        after = artifact["after_images"]
        _require(_audit_images_match_review(batch), "batch audit images changed")
        for member, expected in zip(before, after):
            album = conn.execute(select(albums).where(albums.c.id == member["album_id"])).mappings().one_or_none()
            _require(album is not None, f"album {member['album_id']} changed since apply")
            try:
                _album_preimage(album, member)
            except EventSelectionError as exc:
                raise EventSelectionError(f"album {member['album_id']} changed since apply") from exc
            row = (
                conn.execute(select(selections).where(selections.c.album_id == member["album_id"]))
                .mappings()
                .one_or_none()
            )
            _require(
                row is not None and _image(row) == expected,
                f"selection for album {member['album_id']} changed since apply",
            )
        for member in before:
            conn.execute(selections.delete().where(selections.c.album_id == member["album_id"]))
        conn.execute(
            batches.update()
            .where(batches.c.id == batch_id)
            .values(status="undone", undone_at=datetime.now(timezone.utc))
        )
        return {"status": "undone", "batch_id": batch_id, "reverted": len(before)}
