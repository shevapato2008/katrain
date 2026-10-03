"""Scoped Chinese orthographic approvals, with isolated SQLite import rehearsals."""

import asyncio
import hashlib
from copy import deepcopy

import pytest
from sqlalchemy.orm import Session

from katrain.web.api.v1.endpoints import kifu
from katrain.web.core.models_db import KifuAlbum, KifuPlayer, KifuPlayerName, KifuNameResearchEvidence
from katrain.web.kifu.name_batch import apply_bundle, catalog_snapshot_sha, dry_run_bundle, BatchError
from katrain.web.kifu.name_candidates import canonical_sha256, validate_bundle
from katrain.web.kifu.name_coverage import coverage_report
from katrain.web.kifu.name_inventory import build_inventory
from tests.web_ui.test_kifu_name_api import _request
from tests.web_ui.test_kifu_name_transliteration import signed, registry
from tests.web_ui.test_kifu_name_transliteration_integration import catalog


def fixture(lang="tw"):
    original, output = ("刘元赫", "劉元赫") if lang == "tw" else ("劉元赫", "刘元赫")
    source_lang, source_script, target_script, region = (
        ("zh-Hans", "Hans", "Hant", "TW") if lang == "tw" else ("zh-Hant", "Hant", "Hans", "CN")
    )
    engine, bundle, _, _ = catalog()
    with Session(engine) as db:
        db.query(KifuPlayer).update({"canonical_name": original})
        db.query(KifuAlbum).update({"player_black": original, "sgf_content": f"(;PB[{original}]PW[White];B[aa])"})
        db.commit()
    inventory = build_inventory(engine)
    bundle.update(inventory_sha256=inventory["sha256"], catalog_sha256=catalog_snapshot_sha(engine))
    bundle.pop("transliteration")
    row = bundle["candidates"][0]
    row.update(
        lang=lang, display_name=output, decision_kind="generated", generation_rule_version="primary-orthographic-v1"
    )
    for field in ("transliteration_batch_sha256", "source_anchor_sha256", "rule_sha256"):
        row.pop(field, None)
    bundle["members"][0]["lang"] = lang
    bundle["member_set_sha256"] = canonical_sha256(bundle["members"])
    body = f"CWA000001 {original} Chinese-origin professional player"
    anchor = {
        "evidence_kind": "primary_orthographic",
        "version": 1,
        **signed(
            {
                "owner": deepcopy(row["owner"]),
                "original_name": original,
                "source_lang": source_lang,
                "source_script": source_script,
                "chinese_origin": True,
                "binding": {
                    "kind": "official_person",
                    "person_id_namespace": "cwa_player_no",
                    "person_id": "CWA000001",
                    "owner": row["owner"],
                    "identity_basis": "Official ID matched to this reviewed player",
                },
                "sources": [
                    {
                        "url": "https://example.org/official",
                        "tier": "official",
                        "fetched_at": "2026-10-03T09:00:00Z",
                        "http_status": 200,
                        "body_sha256": hashlib.sha256(body.encode()).hexdigest(),
                        "body_text": body,
                        "body_excerpt": body,
                        "observed_lang": source_lang,
                        "language_basis": "reviewed_text",
                        "identity_basis": "Official Chinese original and person ID",
                        "record_locator": "CWA000001",
                    }
                ],
            },
            "approved_orthographic_original",
        ),
    }
    rules = signed(
        {
            "version": "primary-orthographic-v1",
            "lang": lang,
            "source_lang": source_lang,
            "source_script": source_script,
            "target_script": target_script,
            "target_region": region,
            "mappings": [
                {
                    "input": a,
                    "output": b,
                    "normative_version": "fixture-1",
                    "normative_url": "https://example.org/norm",
                    "location": a,
                    "human_name_applicable": True,
                }
                for a, b in zip(original, output)
            ],
            "excluded_characters": list("于钟岳胡杰"),
            "excluded_names": ["胡子扬", "孔杰"],
            "exceptions_checked": True,
        },
        "approved_orthographic_rule",
    )
    member = {
        "owner": row["owner"],
        "original_name": original,
        "lang": lang,
        "display_name": output,
        "source_anchor_sha256": canonical_sha256(anchor),
        "rule_sha256": canonical_sha256(rules),
        "codepoint_changes": [
            {"position": i, "input": f"U+{ord(a):04X}", "output": f"U+{ord(b):04X}"}
            for i, (a, b) in enumerate(zip(original, output))
        ],
    }
    batch = signed(
        {
            "version": "primary-orthographic-v1",
            "rule_sha256": canonical_sha256(rules),
            "members": [member],
            "frozen_at": "2026-10-03T12:45:00Z",
            "members_sha256": canonical_sha256([member]),
            "catalog_sha256": bundle["catalog_sha256"],
            "approved_name_snapshot_sha256": canonical_sha256([]),
            "known_aliases": [],
            "unresolved_conflicts": [],
            "complete_name_review": [member],
            "sampled_members": [canonical_sha256(member)],
        },
        "approved_orthographic_batch",
    )
    batch["approval"].update(produced_at="2026-10-03T12:00:00Z", reviewed_at="2026-10-03T13:00:00Z")
    bundle["primary_orthographic"] = {"version": "primary-orthographic-v1", "rules": [rules], "batches": [batch]}
    refresh(bundle, anchor)
    return engine, bundle, [anchor], inventory


def refresh(bundle, anchor):
    section = bundle["primary_orthographic"]
    rule, batch = section["rules"][0], section["batches"][0]
    anchor["approval"]["content_sha256"] = canonical_sha256(anchor["content"])
    rule["approval"]["content_sha256"] = canonical_sha256(rule["content"])
    member = batch["content"]["members"][0]
    row = bundle["candidates"][0]
    row["preimage_binding"].update(bound_at="2026-10-03T12:30:00Z")
    member.update(
        source_anchor_sha256=canonical_sha256(anchor),
        rule_sha256=canonical_sha256(rule),
        name_preimage_sha256=row["name_preimage_sha256"],
        preimage_binding_sha256=canonical_sha256(row["preimage_binding"]),
    )
    batch["content"].update(
        rule_sha256=canonical_sha256(rule),
        members_sha256=canonical_sha256([member]),
        complete_name_review=[deepcopy(member)],
        sampled_members=[canonical_sha256(member)],
    )
    batch["approval"]["content_sha256"] = canonical_sha256(batch["content"])
    row = bundle["candidates"][0]
    row.update(member)
    row.update(
        {
            k: batch["approval"][k]
            for k in ("producer_id", "producer_model", "produced_at", "reviewer_id", "reviewer_model", "reviewed_at")
        }
    )
    row.update(
        orthographic_batch_sha256=canonical_sha256(batch),
        research_sha256="",
        review_conclusion="approved_orthographic_batch",
    )
    row["preimage_binding"].update(bound_at="2026-10-03T12:30:00Z")


def test_valid_finite_orthographic_bundle():
    engine, bundle, anchors, inventory = fixture()
    try:
        report = validate_bundle(bundle, registry(), inventory, anchors, approved_name_snapshot=[])
        assert report["write_ready"], report
        assert dry_run_bundle(engine, bundle, registry(), inventory, anchors)["write_ready"]
    finally:
        engine.dispose()


@pytest.mark.parametrize(
    "mutation",
    [
        "jp",
        "ko",
        "en",
        "event",
        "non_chinese",
        "ambiguous",
        "exception",
        "self_review",
        "stale_source",
        "stale_rule",
        "stale_members",
        "scope",
        "conventional",
        "alias",
        "binder",
    ],
)
def test_reject_orthographic_scope_or_proof(mutation):
    engine, bundle, anchors, inventory = fixture()
    try:
        rule = bundle["primary_orthographic"]["rules"][0]["content"]
        batch = bundle["primary_orthographic"]["batches"][0]
        snapshot = []
        if mutation in {"jp", "ko", "en"}:
            rule["lang"] = mutation
        elif mutation == "event":
            anchors[0]["content"]["owner"]["kind"] = "event"
        elif mutation == "non_chinese":
            anchors[0]["content"]["chinese_origin"] = False
        elif mutation == "ambiguous":
            rule["mappings"].append({**rule["mappings"][0], "output": "留"})
        elif mutation == "exception":
            rule["excluded_names"].append("刘元赫")
        elif mutation == "scope":
            anchors[0]["content"]["binding"]["owner"] = {"kind": "player", "id": 999}
        elif mutation == "conventional":
            snapshot = [
                {
                    "owner": bundle["candidates"][0]["owner"],
                    "lang": "tw",
                    "display_name": "劉元赫",
                    "decision_kind": "conventional",
                    "review_status": "approved",
                }
            ]
            batch["content"]["approved_name_snapshot_sha256"] = canonical_sha256(snapshot)
        elif mutation == "alias":
            batch["content"]["known_aliases"] = [{"owner": {"kind": "player", "id": 99}, "name": "劉元赫"}]
        if mutation.startswith("stale_"):
            if mutation == "stale_source":
                anchors[0]["content"]["original_name"] = "刘元浩"
            elif mutation == "stale_rule":
                rule["target_region"] = "HK"
            else:
                batch["content"]["members"][0]["display_name"] = "劉元浩"
        else:
            refresh(bundle, anchors[0])
            if mutation == "self_review":
                batch["approval"]["reviewer_id"] = batch["approval"]["producer_id"]
            if mutation == "binder":
                batch["approval"]["reviewer_id"] = bundle["candidates"][0]["preimage_binding"]["actor_id"]
        report = validate_bundle(bundle, registry(), inventory, anchors, approved_name_snapshot=snapshot)
        assert not report["write_ready"], report
    finally:
        engine.dispose()


@pytest.mark.parametrize("lang", ["cn", "tw"])
@pytest.mark.parametrize(
    "drift", ["source", "name", "rule", "member", "artifact", "proof", "owner", "signature", "version", "decision"]
)
def test_import_display_search_coverage_and_tampering(monkeypatch, lang, drift):
    monkeypatch.setenv("KIFU_STRICT_NAMES", "1")
    engine, bundle, anchors, inventory = fixture(lang)
    output = bundle["candidates"][0]["display_name"]
    try:
        applied = apply_bundle(engine, bundle, registry(), inventory, anchors)
        assert applied["status"] == "applied"
        assert apply_bundle(engine, bundle, registry(), inventory, anchors)["status"] == "already_applied"
        with Session(engine) as db:
            page = asyncio.run(kifu.list_kifu_albums(_request(), q=output, page=1, page_size=20, lang=lang, db=db))
            assert page.total == 1 and page.items[0].display_player_black == output
        assert coverage_report(engine, inventory, languages=(lang,))["languages"][lang]["by_decision"]["generated"] == 1
        with Session(engine) as db:
            evidence = db.query(KifuNameResearchEvidence).one()
            payload = deepcopy(evidence.research_payload)
            if drift == "source":
                payload["primary_orthographic"]["source_anchor"]["content"]["original_name"] = "刘元浩"
            elif drift == "proof":
                payload.pop("primary_orthographic")
            elif drift == "owner":
                payload["candidate"]["owner"] = {"kind": "player", "id": 999}
            elif drift == "signature":
                evidence.reviewer_id = "changed-reviewer"
            elif drift == "decision":
                db.query(KifuPlayerName).update({"decision_kind": "conventional"})
                evidence.decision_kind = "conventional"
            elif drift == "version":
                db.query(KifuPlayerName).update({"generation_rule_version": "none"})
                evidence.generation_rule_version = "none"
                payload["candidate"]["generation_rule_version"] = "none"
            elif drift == "name":
                db.query(KifuPlayerName).update({"display_name": "劉元浩"})
            else:
                from katrain.web.core.models_db import KifuNameBatch

                stored = db.get(KifuNameBatch, applied["batch_id"])
                artifact = deepcopy(stored.reviewed_artifact)
                if drift == "rule":
                    artifact["bundle"]["primary_orthographic"]["rules"][0]["content"]["mappings"][0]["output"] = "留"
                elif drift == "member":
                    artifact["bundle"]["primary_orthographic"]["batches"][0]["content"]["members"][0][
                        "display_name"
                    ] = "劉元浩"
                else:
                    artifact["approved_name_snapshot"] = [{"changed": True}]
                stored.reviewed_artifact = artifact
            evidence.research_payload = payload
            db.commit()
        with Session(engine) as db:
            page = asyncio.run(kifu.list_kifu_albums(_request(), q=output, page=1, page_size=20, lang=lang, db=db))
            assert page.total == 0
        assert (
            coverage_report(engine, inventory, languages=(lang,))["languages"][lang]["by_decision"].get("generated", 0)
            == 0
        )
    finally:
        engine.dispose()


def test_locked_import_rechecks_true_preimage_catalog_and_aliases():
    from katrain.web.core.models_db import KifuPlayerAlias

    for drift in ("preimage", "catalog", "aliases"):
        engine, bundle, anchors, inventory = fixture()
        try:
            if drift == "preimage":
                bundle["candidates"][0]["name_preimage_sha256"] = "f" * 64
                bundle["candidates"][0]["preimage_binding"]["name_preimage_sha256"] = "f" * 64
                refresh(bundle, anchors[0])
            else:
                with Session(engine) as db:
                    if drift == "catalog":
                        db.add(KifuPlayer(id=99, canonical_name="Other"))
                    else:
                        db.add(KifuPlayerAlias(player_id=17, alias="Some Alias", normalized_alias="some alias"))
                    db.commit()
                if drift == "aliases":
                    bundle["catalog_sha256"] = catalog_snapshot_sha(engine)
                    bundle["primary_orthographic"]["batches"][0]["content"]["catalog_sha256"] = bundle["catalog_sha256"]
                    refresh(bundle, anchors[0])
            with pytest.raises(
                BatchError, match="preimage changed|catalog supplement snapshot changed|alias snapshot changed"
            ):
                apply_bundle(engine, bundle, registry(), inventory, anchors)
            with Session(engine) as db:
                assert db.query(KifuPlayerName).count() == 0
        finally:
            engine.dispose()


@pytest.mark.parametrize("drift", ["binder", "preimage", "freeze"])
def test_complete_name_approval_signs_final_preimage_binding(drift):
    engine, bundle, anchors, inventory = fixture()
    try:
        if drift == "binder":
            bundle["candidates"][0]["preimage_binding"]["actor_id"] = "unsigned-new-binder"
        elif drift == "preimage":
            bundle["candidates"][0]["name_preimage_sha256"] = "a" * 64
            bundle["candidates"][0]["preimage_binding"]["name_preimage_sha256"] = "a" * 64
        else:
            batch = bundle["primary_orthographic"]["batches"][0]
            batch["content"]["frozen_at"] = "2026-10-03T12:00:00Z"
            batch["approval"]["content_sha256"] = canonical_sha256(batch["content"])
            bundle["candidates"][0]["orthographic_batch_sha256"] = canonical_sha256(batch)
        report = validate_bundle(bundle, registry(), inventory, anchors, approved_name_snapshot=[])
        assert not report["write_ready"], report
    finally:
        engine.dispose()


def test_raw_player_orthographic_name_applies_only_to_frozen_scope(monkeypatch):
    from katrain.web.core.models_db import KifuRawPlayerValue
    from katrain.web.kifu.name_raw_player_scope import CONTEXT_FIELDS
    from tests.web_ui.test_kifu_raw_player_scope import _scope
    from tests.web_ui.test_kifu_name_batch import _v2_wrap

    monkeypatch.setenv("KIFU_STRICT_NAMES", "1")
    engine, bundle, anchors, _ = fixture()
    try:
        owner = {"kind": "raw_player", "id": 7}
        with Session(engine) as db:
            db.add(KifuRawPlayerValue(id=7, raw_value="刘元赫", category="readable_unlinked", review_status="approved"))
            db.query(KifuAlbum).update({"black_player_id": None})
            db.commit()
        inventory = build_inventory(engine)
        bundle["inventory_sha256"] = inventory["sha256"]
        scope = _scope()
        album = dict(zip(inventory["association_columns"], inventory["album_associations"][0]))
        scope["content"].update(
            inventory_sha256=inventory["sha256"],
            raw_value="刘元赫",
            slots=[{"album_id": album["id"], "slot": "black", "context": {k: album[k] for k in CONTEXT_FIELDS}}],
        )
        scope["approval"]["content_sha256"] = canonical_sha256(scope["content"])
        scope_hash = canonical_sha256(scope)
        row = bundle["candidates"][0]
        row.update(owner=owner, raw_value="刘元赫", raw_display_scope_sha256=scope_hash)
        bundle["members"][0].update(owner=owner, raw_value="刘元赫")
        bundle["member_set_sha256"] = canonical_sha256(bundle["members"])
        source = anchors[0]["content"]
        source.update(
            owner=owner,
            raw_value="刘元赫",
            raw_display_scope_sha256=scope_hash,
            binding={
                "kind": "finite_raw_scope",
                "person_id_namespace": "cwa_player_no",
                "person_id": "CWA000001",
                "owner": owner,
                "identity_basis": "Finite independently approved raw spelling and scope",
                "mapping": signed(
                    {
                        "owner": owner,
                        "raw_value": "刘元赫",
                        "original_name": "刘元赫",
                        "raw_display_scope_sha256": scope_hash,
                    },
                    "approved_exact_raw_original_mapping",
                    reviewer="mapping-reviewer",
                ),
            },
        )
        anchors[0]["approval"].update(produced_at="2026-10-03T11:15:00Z", reviewed_at="2026-10-03T11:30:00Z")
        member = bundle["primary_orthographic"]["batches"][0]["content"]["members"][0]
        member.update(owner=owner, raw_value="刘元赫", raw_display_scope_sha256=scope_hash)
        declaration = {
            "owner": owner,
            "preimage": {"raw_value": "刘元赫", "category": "readable_unlinked", "review_status": "approved"},
            "occurrence_album_ids": [album["id"]],
            "occurrence_sha256": canonical_sha256([album["id"]]),
            "raw_display_scope": scope,
        }
        bundle = _v2_wrap(engine, inventory, bundle, [declaration], [])
        bundle["primary_orthographic"]["batches"][0]["content"]["catalog_sha256"] = bundle["catalog_sha256"]
        refresh(bundle, anchors[0])
        report = validate_bundle(bundle, registry(), inventory, anchors, approved_name_snapshot=[])
        assert report["write_ready"], report
        apply_bundle(engine, bundle, registry(), inventory, anchors)
        with Session(engine) as db:
            page = asyncio.run(kifu.list_kifu_albums(_request(), q="劉元赫", page=1, page_size=20, lang="tw", db=db))
            assert page.total == 1 and page.items[0].display_player_black == "劉元赫"
            db.add(
                KifuAlbum(
                    player_black="刘元赫",
                    player_white="White",
                    sgf_content="(;PB[刘元赫]PW[White])",
                    source_path="new-same-name.sgf",
                )
            )
            db.commit()
            page = asyncio.run(kifu.list_kifu_albums(_request(), q="劉元赫", page=1, page_size=20, lang="tw", db=db))
            assert page.total == 1
            assert db.query(KifuAlbum).filter(KifuAlbum.black_player_id.isnot(None)).count() == 0
    finally:
        engine.dispose()


def raw_anchor_for_review():
    engine, _, anchors, _ = fixture()
    engine.dispose()
    anchor = anchors[0]
    source = anchor["content"]
    owner = {"kind": "raw_player", "id": 7}
    source.update(owner=owner, raw_value=source["original_name"], raw_display_scope_sha256="d" * 64)
    source["binding"] = {
        "kind": "finite_raw_scope",
        "person_id_namespace": "cwa_player_no",
        "person_id": "CWA000001",
        "owner": owner,
        "identity_basis": "Reviewed exact raw scope",
        "mapping": signed(
            {
                "owner": owner,
                "raw_value": source["original_name"],
                "original_name": source["original_name"],
                "raw_display_scope_sha256": "d" * 64,
            },
            "approved_exact_raw_original_mapping",
        ),
    }
    source["binding"]["mapping"]["approval"]["reviewed_at"] = "2026-10-03T09:30:00Z"
    source["binding"]["mapping"]["approval"]["produced_at"] = "2026-10-03T09:00:00Z"
    anchor["approval"]["content_sha256"] = canonical_sha256(source)
    return anchor


@pytest.mark.parametrize("defect", ["missing_key", "non_official", "missing_person_in_body"])
def test_raw_original_requires_official_person_body_even_with_approved_scope(defect):
    from katrain.web.kifu.name_evidence import EvidenceError, validate_primary_orthographic_anchor

    anchor = raw_anchor_for_review()
    content = anchor["content"]
    if defect == "missing_key":
        content["binding"].pop("person_id")
    if defect == "non_official":
        content["sources"][0]["tier"] = "language_go"
    elif defect == "missing_person_in_body":
        source = content["sources"][0]
        source["body_text"] = source["body_excerpt"] = "刘元赫 professional player"
        source["body_sha256"] = hashlib.sha256(source["body_text"].encode()).hexdigest()
    anchor["approval"]["content_sha256"] = canonical_sha256(content)
    with pytest.raises(EvidenceError):
        validate_primary_orthographic_anchor(anchor)


@pytest.mark.parametrize("defect", ["source_after_production", "mapping_after_production", "review_at_production"])
def test_orthographic_anchor_production_follows_all_dependencies(defect):
    from katrain.web.kifu.name_evidence import EvidenceError, validate_primary_orthographic_anchor

    if defect == "mapping_after_production":
        anchor = raw_anchor_for_review()
        anchor["content"]["binding"]["mapping"]["approval"]["reviewed_at"] = "2026-10-03T10:30:00Z"
    else:
        engine, _, anchors, _ = fixture()
        engine.dispose()
        anchor = anchors[0]
        if defect == "source_after_production":
            anchor["content"]["sources"][0]["fetched_at"] = "2026-10-03T10:30:00Z"
        else:
            anchor["approval"]["reviewed_at"] = anchor["approval"]["produced_at"]
    anchor["approval"]["content_sha256"] = canonical_sha256(anchor["content"])
    with pytest.raises(EvidenceError):
        validate_primary_orthographic_anchor(anchor)
