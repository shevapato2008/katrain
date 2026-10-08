"""Scoped Chinese orthographic approvals, with isolated SQLite import rehearsals."""

import asyncio
import hashlib
from copy import deepcopy
from datetime import datetime, timezone

import pytest
from sqlalchemy.orm import Session

from katrain.web.api.v1.endpoints import kifu
from katrain.web.core.models_db import KifuAlbum, KifuPlayer, KifuPlayerName, KifuNameResearchEvidence, KifuNameBatch, KifuNameChange
from katrain.web.kifu.name_batch import apply_bundle, catalog_snapshot_sha, dry_run_bundle, BatchError, approved_name_snapshot, name_preimage_sha256
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


def verified_chinese_display_fixture(original="加纳一夫", output="加納一夫"):
    """A Japanese owner with a separately approved conventional CN display."""
    from tests.web_ui.test_kifu_name_api import _evidence
    from katrain.web.kifu.name_batch import _image

    engine, bundle, anchors, inventory = fixture()
    with Session(engine) as db:
        player = db.get(KifuPlayer, 17)
        player.canonical_name = "加藤一夫"
        db.query(KifuAlbum).update({"player_black": "加藤一夫", "sgf_content": "(;PB[加藤一夫]PW[White];B[aa])"})
        source_evidence = _evidence(db, "player", 17, "cn", original)
        source_evidence.produced_at = datetime(2026, 10, 3, 8, 0, tzinfo=timezone.utc)
        source_evidence.reviewed_at = datetime(2026, 10, 3, 9, 0, tzinfo=timezone.utc)
        source_research = {"scope_status": "found", "candidate_name": original}
        source_candidate = {"owner": {"kind": "player", "id": 17}, "lang": "cn", "display_name": original,
                            "decision_kind": "conventional", "review_status": "approved",
                            "research_sha256": canonical_sha256(source_research)}
        source_evidence.research_payload = {"candidate": source_candidate, "research": source_research}
        db.add(KifuPlayerName(player_id=17, lang="cn", display_name=original, status="verified",
                              decision_kind="conventional", generation_rule_version="test-v1", revision=1,
                              evidence_id=source_evidence.id))
        db.flush()
        source_name = db.query(KifuPlayerName).filter_by(player_id=17, lang="cn").one()
        source_bundle = {"candidates": [source_candidate]}
        source_batch = KifuNameBatch(bundle_sha256=canonical_sha256(source_bundle), inventory_sha256="b" * 64,
                                     source_registry_id=source_evidence.source_registry_id,
                                     reviewed_artifact={"bundle": source_bundle,
                                                        "research_hashes": [canonical_sha256(source_research)]}, status="applied")
        db.add(source_batch)
        db.flush()
        conn = db.connection()
        name_image = _image(conn, KifuPlayerName.__table__, source_name.id)
        evidence_image = _image(conn, KifuNameResearchEvidence.__table__, source_evidence.id)
        source_change = KifuNameChange(batch_id=source_batch.id, sequence=1,
                                       target_table="kifu_name_research_evidence", target_row_id=source_evidence.id,
                                       before_image=None, after_image=evidence_image)
        db.add(source_change)
        db.add(KifuNameChange(batch_id=source_batch.id, sequence=2, target_table="kifu_player_names",
                              target_row_id=source_name.id, before_image=None, after_image=name_image))
        source_batch_id = source_batch.id
        source_bundle_sha256 = source_batch.bundle_sha256
        db.commit()
    inventory = build_inventory(engine)
    bundle.update(inventory_sha256=inventory["sha256"], catalog_sha256=catalog_snapshot_sha(engine))
    row = bundle["candidates"][0]
    row.update(lang="tw", display_name=output, name_preimage_sha256=None)
    bundle["members"][0]["lang"] = "tw"
    bundle["member_set_sha256"] = canonical_sha256(bundle["members"])
    anchor = anchors[0]
    anchor["content"] = {
        "reference_kind": "verified_chinese_display", "owner": row["owner"], "original_name": original,
        "source_lang": "zh-Hans", "source_script": "Hans",
        "binding": {"kind": "verified_chinese_display", "owner": row["owner"],
                    "source_name": name_image, "source_evidence": evidence_image,
                    "source_batch": {"id": source_batch_id, "bundle_sha256": source_bundle_sha256,
                                     "evidence_creation_sha256": canonical_sha256(evidence_image)}},
    }
    rule = bundle["primary_orthographic"]["rules"][0]["content"]
    rule.update(mappings=[{**rule["mappings"][0], "input": a, "output": b}
                          for a, b in zip(original, output)])
    member = bundle["primary_orthographic"]["batches"][0]["content"]["members"][0]
    member.update(reference_kind="verified_chinese_display", original_name=original, display_name=output,
                  codepoint_changes=[{"position": i, "input": f"U+{ord(a):04X}", "output": f"U+{ord(b):04X}"}
                                     for i, (a, b) in enumerate(zip(original, output))])
    snapshot = approved_name_snapshot(engine)
    bundle["primary_orthographic"]["batches"][0]["content"].update(
        approved_name_snapshot_sha256=canonical_sha256(snapshot), catalog_sha256=bundle["catalog_sha256"]
    )
    refresh(bundle, anchor)
    return engine, bundle, anchors, inventory, snapshot


@pytest.mark.parametrize("original,output", [("加纳一夫", "加納一夫"), ("金井新一", "金井新一")])
def test_verified_chinese_display_import_and_readback(monkeypatch, original, output):
    monkeypatch.setenv("KIFU_STRICT_NAMES", "1")
    engine, bundle, anchors, inventory, snapshot = verified_chinese_display_fixture(original, output)
    try:
        report = validate_bundle(bundle, registry(), inventory, anchors, approved_name_snapshot=snapshot)
        assert report["write_ready"], report
        assert dry_run_bundle(engine, bundle, registry(), inventory, anchors)["write_ready"]
        assert apply_bundle(engine, bundle, registry(), inventory, anchors)["status"] == "applied"
        with Session(engine) as db:
            page = asyncio.run(kifu.list_kifu_albums(_request(), q=output, page=1, page_size=20, lang="tw", db=db))
            assert page.total == 1 and page.items[0].display_player_black == output
            assert db.query(KifuPlayerName).filter_by(player_id=17, lang="tw").one().decision_kind == "generated"
    finally:
        engine.dispose()


def test_verified_chinese_display_does_not_resolve_sheng_variant():
    engine, bundle, anchors, inventory, snapshot = verified_chinese_display_fixture("加升一夫", "加昇一夫")
    try:
        report = validate_bundle(bundle, registry(), inventory, anchors, approved_name_snapshot=snapshot)
        assert not report["write_ready"]
        assert any("exceptional mapping" in error for error in report["errors"])
    finally:
        engine.dispose()


def test_verified_chinese_display_locked_import_rechecks_source_preimage():
    engine, bundle, anchors, inventory, _ = verified_chinese_display_fixture()
    try:
        with Session(engine) as db:
            db.query(KifuPlayerName).filter_by(player_id=17, lang="cn").update({"display_name": "加纳二夫"})
            db.commit()
        with pytest.raises(BatchError):
            apply_bundle(engine, bundle, registry(), inventory, anchors)
        with Session(engine) as db:
            assert db.query(KifuPlayerName).filter_by(player_id=17, lang="tw").count() == 0
    finally:
        engine.dispose()


def test_verified_chinese_display_cannot_replace_resigned_existing_tw():
    engine, bundle, anchors, inventory, snapshot = verified_chinese_display_fixture()
    try:
        with Session(engine) as db:
            db.add(KifuPlayerName(player_id=17, lang="tw", display_name="待核名稱", status="review",
                                  decision_kind="conventional", generation_rule_version="none", revision=1))
            db.commit()
        row = bundle["candidates"][0]
        preimage = name_preimage_sha256(engine, row["owner"], "tw")
        assert isinstance(preimage, str) and len(preimage) == 64
        row["name_preimage_sha256"] = preimage
        row["preimage_binding"]["name_preimage_sha256"] = preimage
        refresh(bundle, anchors[0])
        report = validate_bundle(bundle, registry(), inventory, anchors, approved_name_snapshot=snapshot)
        assert not report["write_ready"], report
        with pytest.raises(BatchError):
            apply_bundle(engine, bundle, registry(), inventory, anchors)
        with Session(engine) as db:
            assert db.query(KifuPlayerName).filter_by(player_id=17, lang="tw").one().display_name == "待核名稱"
    finally:
        engine.dispose()


@pytest.mark.parametrize("drift", ["foreign_owner", "source_value", "source_review", "source_decision", "source_proof", "target_filled", "direction", "ambiguous"])
def test_verified_chinese_display_rejects_bad_source_or_target(drift):
    engine, bundle, anchors, inventory, snapshot = verified_chinese_display_fixture()
    try:
        source = anchors[0]["content"]
        if drift == "foreign_owner":
            source["binding"]["owner"] = {"kind": "player", "id": 99}
        elif drift == "source_value":
            source["binding"]["source_name"]["display_name"] = "加纳二夫"
        elif drift == "source_review":
            source["binding"]["source_name"]["status"] = "review"
        elif drift == "source_decision":
            source["binding"]["source_evidence"]["decision_kind"] = "generated"
        elif drift == "source_proof":
            source["binding"]["source_batch"]["bundle_sha256"] = "f" * 64
        elif drift == "direction":
            source["source_lang"] = "zh-Hant"
        elif drift == "ambiguous":
            source["original_name"] = "加升一夫"
        else:
            with Session(engine) as db:
                db.add(KifuPlayerName(player_id=17, lang="tw", display_name="已有名稱", status="review",
                                      decision_kind="conventional", generation_rule_version="none", revision=1))
                db.commit()
        if drift != "target_filled":
            refresh(bundle, anchors[0])
            if drift != "source_proof":
                assert not validate_bundle(bundle, registry(), inventory, anchors, approved_name_snapshot=snapshot)["write_ready"]
        with pytest.raises(BatchError):
            apply_bundle(engine, bundle, registry(), inventory, anchors)
        with Session(engine) as db:
            assert db.query(KifuPlayerName).filter_by(player_id=17, lang="tw").count() == (1 if drift == "target_filled" else 0)
    finally:
        engine.dispose()


@pytest.mark.parametrize("drift", ["source_name", "source_evidence", "source_journal", "source_batch", "masked_target"])
def test_verified_chinese_display_reader_rejects_damaged_proof(monkeypatch, drift):
    monkeypatch.setenv("KIFU_STRICT_NAMES", "1")
    engine, bundle, anchors, inventory, _ = verified_chinese_display_fixture()
    try:
        apply_bundle(engine, bundle, registry(), inventory, anchors)
        with Session(engine) as db:
            name = db.query(KifuPlayerName).filter_by(player_id=17, lang="tw").one()
            evidence = db.get(KifuNameResearchEvidence, name.evidence_id)
            if drift == "source_name":
                db.query(KifuPlayerName).filter_by(player_id=17, lang="cn").update({"display_name": "加纳二夫"})
            elif drift == "source_evidence":
                db.query(KifuNameResearchEvidence).filter_by(id=anchors[0]["content"]["binding"]["source_evidence"]["id"]).update(
                    {"decision_kind": "generated"})
            elif drift == "source_journal":
                source_id = anchors[0]["content"]["binding"]["source_evidence"]["id"]
                journal = db.query(KifuNameChange).filter_by(target_table="kifu_name_research_evidence", target_row_id=source_id).one()
                journal.after_image = {"changed": True}
            elif drift == "source_batch":
                source_batch = db.get(KifuNameBatch, anchors[0]["content"]["binding"]["source_batch"]["id"])
                source_batch.bundle_sha256 = "f" * 64
            else:
                name.decision_kind = evidence.decision_kind = "conventional"
                name.generation_rule_version = evidence.generation_rule_version = "none"
                payload = deepcopy(evidence.research_payload)
                payload["candidate"].update(decision_kind="conventional", generation_rule_version="none")
                payload.pop("primary_orthographic")
                evidence.research_payload = payload
            db.commit()
        with Session(engine) as db:
            page = asyncio.run(kifu.list_kifu_albums(_request(), q="加納一夫", page=1, page_size=20, lang="tw", db=db))
            assert page.total == 0
        assert coverage_report(engine, inventory, languages=("tw",))["languages"]["tw"]["by_decision"].get("generated", 0) == 0
    finally:
        engine.dispose()


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


def test_orthographic_candidates_cannot_override_collisions():
    engine, bundle, anchors, inventory = fixture()
    try:
        bundle["candidates"][0].update(
            collision_decision="distinct_people_confirmed", collision_basis="Distinct people"
        )
        assert not validate_bundle(bundle, registry(), inventory, anchors, approved_name_snapshot=[])["ready"]
    finally:
        engine.dispose()


def test_later_conventional_candidate_cannot_override_existing_orthographic_name():
    from katrain.web.kifu.name_batch import _check_cross_bundle_collisions

    engine, bundle, anchors, inventory = fixture()
    try:
        apply_bundle(engine, bundle, registry(), inventory, anchors)
        with Session(engine) as db:
            evidence = db.query(KifuNameResearchEvidence).one()
            payload = deepcopy(evidence.research_payload)
            payload["candidate"].update(
                collision_decision="distinct_people_confirmed", collision_basis="Distinct people"
            )
            evidence.research_payload = payload
            db.commit()
        incoming = {
            "owner": {"kind": "player", "id": 99},
            "lang": "tw",
            "display_name": "劉元赫",
            "decision_kind": "conventional",
            "generation_rule_version": "none",
            "collision_decision": "distinct_people_confirmed",
            "collision_basis": "Distinct people",
        }
        with engine.connect() as conn, pytest.raises(BatchError, match="cross-bundle normalized name collision"):
            _check_cross_bundle_collisions(conn, [incoming])
    finally:
        engine.dispose()


@pytest.mark.parametrize("count", [100, 300])
def test_runtime_context_hashes_entire_batch_once_and_not_per_name(monkeypatch, count):
    from types import SimpleNamespace
    from datetime import datetime
    from katrain.web.kifu import name_orthographic as orthographic

    engine, bundle, anchors, _ = fixture()
    engine.dispose()
    section = bundle["primary_orthographic"]
    rule, batch = section["rules"][0], section["batches"][0]
    rows, sources, members = [], [], []
    # Distinct complete Han names, each with a genuine 100 KB captured fixture body.
    clean_suffixes = [
        chr(code)
        for code in range(0x4E00, 0x5100)
        if chr(code) not in orthographic.EXCLUDED_CHARACTERS | set(rule["content"]["excluded_characters"])
    ]
    for number in range(count):
        suffix = clean_suffixes[number]
        original, output = "刘元赫" + suffix, "劉元赫" + suffix
        owner = {"kind": "player", "id": 1000 + number}
        source = deepcopy(anchors[0])
        source["content"].update(owner=owner, original_name=original)
        source["content"]["binding"]["owner"] = owner
        body = "CWA000001 " + original + " " + "x" * 100000
        capture = source["content"]["sources"][0]
        capture.update(body_text=body, body_excerpt=body[:80], body_sha256=hashlib.sha256(body.encode()).hexdigest())
        source["approval"]["content_sha256"] = canonical_sha256(source["content"])
        sources.append(source)
        member = deepcopy(batch["content"]["members"][0])
        member.update(
            owner=owner, original_name=original, display_name=output, source_anchor_sha256=canonical_sha256(source)
        )
        member["codepoint_changes"].append(
            {"position": 3, "input": f"U+{ord(suffix):04X}", "output": f"U+{ord(suffix):04X}"}
        )
        members.append(member)
        row = deepcopy(bundle["candidates"][0])
        row.update(member)
        rows.append(row)
        if suffix not in "刘元赫":
            rule["content"]["mappings"].append({**rule["content"]["mappings"][1], "input": suffix, "output": suffix})
    rule["approval"]["content_sha256"] = canonical_sha256(rule["content"])
    rule_hash = canonical_sha256(rule)
    # Known exceptional characters are irrelevant to measuring this clean batch.
    for member, row in zip(members, rows):
        member["rule_sha256"] = row["rule_sha256"] = rule_hash
    batch["content"].update(
        rule_sha256=rule_hash,
        members=members,
        members_sha256=canonical_sha256(members),
        complete_name_review=deepcopy(members),
        sampled_members=[canonical_sha256(m) for m in members[:20]],
    )
    batch["approval"]["content_sha256"] = canonical_sha256(batch["content"])
    batch_hash = canonical_sha256(batch)
    for row in rows:
        row["orthographic_batch_sha256"] = batch_hash
    bundle["candidates"] = rows
    artifact = {
        "bundle": bundle,
        "approved_name_snapshot": [],
        "orthographic_anchors": sources,
        "orthographic_anchor_hashes": sorted(canonical_sha256(a) for a in sources),
        "research_hashes": sorted(canonical_sha256(a) for a in sources),
    }
    persisted = SimpleNamespace(
        id=1, status="applied", bundle_sha256=canonical_sha256(bundle), reviewed_artifact=artifact
    )
    hashes = []
    source_ids = {id(source) for source in sources}
    source_hashes = []
    actual_hash = orthographic.registry_sha256

    def counted(value):
        if value is batch:
            hashes.append(value)
        if id(value) in source_ids:
            source_hashes.append(id(value))
        return actual_hash(value)

    monkeypatch.setattr(orthographic, "registry_sha256", counted)
    context = orthographic.persisted_batch_bindings(persisted)
    assert context is not None
    assert len(hashes) == 1
    assert len(source_hashes) == count and set(source_hashes) == source_ids
    for row, source in zip(rows, sources):
        name = SimpleNamespace(
            player_id=row["owner"]["id"],
            lang="tw",
            display_name=row["display_name"],
            decision_kind="generated",
            generation_rule_version="primary-orthographic-v1",
        )
        evidence = SimpleNamespace(
            decision_kind="generated",
            research_payload={
                "candidate": row,
                "research": None,
                "primary_orthographic": {"batch_id": 1, "source_anchor": source},
            },
            **{key: row[key] for key in ("producer_id", "producer_model", "reviewer_id", "reviewer_model")},
            produced_at=datetime.fromisoformat(row["produced_at"].replace("Z", "+00:00")),
            reviewed_at=datetime.fromisoformat(row["reviewed_at"].replace("Z", "+00:00")),
        )
        assert orthographic.persisted_name_eligible(name, evidence, "player_id", None, persisted, context)
    assert len(hashes) == 1
    assert len(source_hashes) == count
    sources[0]["content"]["sources"][0]["body_text"] += " tampered after the first read"
    assert orthographic.persisted_batch_bindings(persisted) is None


def hanja_fixture():
    engine, bundle, anchors, inventory = fixture()
    original = "李昌植"  # U+F9E1 compatibility Hanja must survive unchanged.
    source = anchors[0]["content"]
    body = '<html lang="ko"><body><p>이창식(<em>李昌植</em>)</p><a href="/record/diary.asp?foreignKey=10000001">기사</a></body></html>'
    source.pop("chinese_origin")
    source.update(
        reference_kind="official_hanja_preserved",
        korean_name="이창식",
        original_name=original,
        source_lang="ko",
        source_script="Hanja",
    )
    source["binding"].update(person_id_namespace="kba_pkey", person_id="10000001")
    source["sources"] = [
        {
            **source["sources"][0],
            "url": "https://www.baduk.or.kr/record/player_view.asp?pkey=10000001",
            "source_role": "official_person_page",
            "body_text": body,
            "body_excerpt": body,
            "body_sha256": hashlib.sha256(body.encode()).hexdigest(),
            "observed_lang": "ko",
            "record_locator": "pkey=10000001",
        }
    ]
    rule = bundle["primary_orthographic"]["rules"][0]
    rule["content"] = {
        "version": "primary-orthographic-v1",
        "reference_kind": "official_hanja_preserved",
        "lang": "tw",
        "source_lang": "ko",
        "source_script": "Hanja",
        "target_script": "Hanja",
        "target_region": "TW",
        "preservation": "exact_codepoints",
    }
    member = bundle["primary_orthographic"]["batches"][0]["content"]["members"][0]
    member.update(
        reference_kind="official_hanja_preserved",
        original_name=original,
        display_name=original,
        codepoint_changes=[
            {"position": i, "input": f"U+{ord(c):04X}", "output": f"U+{ord(c):04X}"} for i, c in enumerate(original)
        ],
    )
    refresh(bundle, anchors[0])
    return engine, bundle, anchors, inventory


def test_official_hanja_exact_retention_import_and_reader(monkeypatch):
    monkeypatch.setenv("KIFU_STRICT_NAMES", "1")
    engine, bundle, anchors, inventory = hanja_fixture()
    try:
        report = validate_bundle(bundle, registry(), inventory, anchors, approved_name_snapshot=[])
        assert report["write_ready"], report
        applied = apply_bundle(engine, bundle, registry(), inventory, anchors)
        assert applied["status"] == "applied"
        with Session(engine) as db:
            page = asyncio.run(kifu.list_kifu_albums(_request(), q="李昌植", page=1, page_size=20, lang="tw", db=db))
            assert page.total == 1 and page.items[0].display_player_black == "李昌植"
            evidence = db.query(KifuNameResearchEvidence).one().research_payload
            assert evidence["candidate"]["reference_kind"] == "official_hanja_preserved"
            assert evidence["primary_orthographic"]["source_anchor"]["content"]["sources"][0]["observed_lang"] == "ko"
    finally:
        engine.dispose()


def test_official_hanja_exact_search_uses_applied_proof():
    from katrain.web.core.models_db import KifuNameBatch
    from katrain.web.kifu.identity import matching_entity_ids

    engine, bundle, anchors, inventory = hanja_fixture()
    try:
        applied = apply_bundle(engine, bundle, registry(), inventory, anchors)
        with Session(engine) as db:
            assert matching_entity_ids(db, "李昌植", exact=True) == ({17}, set())
            assert matching_entity_ids(db, "李昌植", exact=False) == (set(), set())
            batch = db.get(KifuNameBatch, applied["batch_id"])
            artifact = deepcopy(batch.reviewed_artifact)
            artifact["bundle"]["primary_orthographic"]["batches"][0]["content"]["members"][0][
                "display_name"
            ] = "李昌浩"
            batch.reviewed_artifact = artifact
            db.commit()
        with Session(engine) as db:
            assert matching_entity_ids(db, "李昌植", exact=True) == (set(), set())
    finally:
        engine.dispose()


@pytest.mark.parametrize(
    "mutation",
    [
        "nfkc",
        "changed",
        "missing",
        "person_id",
        "role",
        "language",
        "url",
        "korean_name",
        "split_row",
        "body_id",
        "owner_binding",
        "raw",
        "verified",
        "alias",
        "fake_chinese",
    ],
)
def test_official_hanja_rejects_invalid_source_output_or_conflict(mutation):
    engine, bundle, anchors, inventory = hanja_fixture()
    try:
        source = anchors[0]["content"]
        captured = source["sources"][0]
        member = bundle["primary_orthographic"]["batches"][0]["content"]["members"][0]
        batch = bundle["primary_orthographic"]["batches"][0]["content"]
        snapshot = []
        if mutation in {"nfkc", "changed"}:
            member["display_name"] = "李昌植" if mutation == "nfkc" else "李昌埴"
        elif mutation == "missing":
            source["original_name"] = "李?植"
        elif mutation == "person_id":
            source["binding"]["person_id"] = "10000002"
        elif mutation == "role":
            captured["source_role"] = "news_article"
        elif mutation == "language":
            captured["observed_lang"] = "zh-Hant"
        elif mutation == "url":
            captured["url"] = "https://example.org/record/player_view.asp?pkey=10000001"
        elif mutation == "korean_name":
            source["korean_name"] = "김창식"
        elif mutation == "split_row":
            captured["body_text"] = captured["body_text"].replace("이창식(<em>李昌植</em>)", "이창식</p><p>李昌植")
            captured["body_excerpt"] = captured["body_text"]
            captured["body_sha256"] = hashlib.sha256(captured["body_text"].encode()).hexdigest()
        elif mutation == "body_id":
            captured["body_text"] = captured["body_text"].replace("foreignKey=10000001", "foreignKey=100000010")
            captured["body_excerpt"] = captured["body_text"]
            captured["body_sha256"] = hashlib.sha256(captured["body_text"].encode()).hexdigest()
        elif mutation == "owner_binding":
            source["binding"]["owner"] = {"kind": "player", "id": 999}
        elif mutation == "raw":
            source["owner"] = {"kind": "raw_player", "id": 7}
        elif mutation == "verified":
            snapshot = [
                {
                    "owner": member["owner"],
                    "lang": "tw",
                    "display_name": "已有名稱",
                    "decision_kind": "generated",
                    "review_status": "approved",
                }
            ]
            batch["approved_name_snapshot_sha256"] = canonical_sha256(snapshot)
        elif mutation == "alias":
            batch["known_aliases"] = [{"owner": {"kind": "player", "id": 99}, "name": "李昌植"}]
        else:
            source.pop("reference_kind")
            source.pop("korean_name")
            source["chinese_origin"] = True
        refresh(bundle, anchors[0])
        report = validate_bundle(bundle, registry(), inventory, anchors, approved_name_snapshot=snapshot)
        assert not report["write_ready"], report
    finally:
        engine.dispose()
