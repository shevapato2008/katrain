from copy import deepcopy
from pathlib import Path
import hashlib

import pytest

from katrain.web.kifu.name_candidates import canonical_sha256
from katrain.web.kifu.name_evidence import EvidenceError, validate_transliteration_anchor
from tests.web_ui.test_kifu_name_transliteration import two_publisher_anchor


def localized_anchor(tmp_path):
    anchor = two_publisher_anchor()
    content = anchor["content"]
    content.update(
        anchor_format=4,
        owner={"kind": "raw_player", "id": 7},
        raw_value="李元赫",
        raw_display_scope_sha256="a" * 64,
        original_language_basis="Reviewed Chinese source script",
        reading_applicability_basis="Reviewed reading across the exact signed slots",
        spelling_exceptions_basis="All signed slots reviewed for exceptions",
        source_link={
            "method": "localized_name_dob_to_profile_id_v1",
            "unresolved_conflicts": [],
            "review_basis": "Same publisher, ID and DOB",
        },
    )
    content["sources"] = content["sources"][1:]
    content["sources"][0]["role"] = "original"
    for source in content["sources"]:
        body = source["body_excerpt"]
        path = tmp_path / (source["role"] + ".html")
        path.write_bytes(body.encode())
        source.update(
            body_path=str(path),
            body_encoding="utf-8",
            body_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
            record_span=[0, len(body)],
            name_span=[0, len(source["exact_name"])],
            birthdate_span=[len(body) - 10, len(body)],
        )
    anchor["approval"]["content_sha256"] = canonical_sha256(content)
    return anchor


def test_format4_accepts_localized_raw_source(tmp_path):
    validate_transliteration_anchor(localized_anchor(tmp_path))


@pytest.mark.parametrize("fault", ["id", "dob", "language", "raw", "body", "span", "owner", "link"])
def test_format4_rejects_unbound_source(tmp_path, fault):
    anchor = localized_anchor(tmp_path)
    content = anchor["content"]
    source = content["sources"][1]
    if fault == "id":
        source["person_id"] = "124"
    if fault == "dob":
        source["birthdate"] = "1971-02-24"
    if fault == "language":
        source["observed_lang"] = "zh"
    if fault == "raw":
        content["raw_value"] = "李元赫異"
    if fault == "body":
        source["body_sha256"] = "f" * 64
    if fault == "span":
        source["record_span"] = [0, 2]
    if fault == "owner":
        content["owner"] = {"kind": "player", "id": 7}
        content.pop("raw_value")
    if fault == "link":
        content["source_link"]["official_match_count"] = 1
    anchor["approval"]["content_sha256"] = canonical_sha256(content)
    with pytest.raises(EvidenceError):
        validate_transliteration_anchor(anchor)


def test_format4_bundle_apply_replay_qualification_and_undo(tmp_path, monkeypatch):
    monkeypatch.setenv("KIFU_STRICT_NAMES", "1")
    from sqlalchemy.orm import Session
    from katrain.web.core.models_db import KifuRawPlayerName, KifuAlbum, KifuPlayer
    from katrain.web.kifu.name_batch import apply_bundle, dry_run_bundle, undo_batch
    from katrain.web.kifu import identity
    from katrain.web.kifu.name_candidates import validate_bundle
    from tests.web_ui.test_kifu_name_transliteration import refresh_bindings, registry
    from tests.web_ui.test_kifu_name_transliteration_integration import scoped_raw_catalog

    engine, proposed, anchors, inventory = scoped_raw_catalog()
    try:
        old = anchors[0]["content"]
        anchor = localized_anchor(tmp_path)
        anchor["content"].update(owner=old["owner"], raw_display_scope_sha256=old["raw_display_scope_sha256"])
        anchors[:] = [anchor]
        refresh_bindings(proposed, anchors)
        row = proposed["candidates"][0]
        row["preimage_binding"]["source_candidate_sha256"] = canonical_sha256(
            {key: value for key, value in row.items() if key != "preimage_binding"}
        )
        assert validate_bundle(proposed, registry(), inventory, anchors, approved_name_snapshot=[])["write_ready"]
        assert dry_run_bundle(engine, proposed, registry(), inventory, anchors)["write_ready"]
        applied = apply_bundle(engine, proposed, registry(), inventory, anchors)
        assert applied["status"] == "applied"
        assert apply_bundle(engine, proposed, registry(), inventory, anchors)["change_count"] == 0
        for source in anchor["content"]["sources"]:
            Path(source["body_path"]).unlink()
        with Session(engine) as db:
            assert len(identity._approved_raw_player_names(db, values={"李元赫"}, lang="ru")) == 1
            name = db.query(KifuRawPlayerName).one()
            album = db.query(KifuAlbum).first()
            display = name.display_name
            clause = identity.strict_raw_player_search_clause(db, {"李元赫"}, display)
            assert db.query(KifuAlbum.id).filter(clause).all() == [(album.id,)]
            extra = KifuAlbum(
                player_black="李元赫",
                player_white="Other",
                event="Cup",
                sgf_content="(;B[aa])",
                source_path="outside-scope.sgf",
            )
            db.add(extra)
            db.flush()
            assert db.query(KifuAlbum.id).filter(clause).all() == [(album.id,)]
            player = KifuPlayer(canonical_name="Unrelated player")
            db.add(player)
            db.flush()
            album.black_player_id = player.id
            db.flush()
            assert db.query(KifuAlbum.id).filter(clause).all() == []
            assert identity.strict_slot_approvals(db, [album, extra], "ru")[album.id][0] is None
            db.rollback()
        legacy = deepcopy(proposed)
        legacy["bundle_format"] = 1
        for key in ("owners", "owner_set_sha256", "catalog_sha256", "album_links", "link_set_sha256"):
            legacy.pop(key)
        assert not validate_bundle(legacy, registry(), inventory, anchors, approved_name_snapshot=[])["ready"]
        assert undo_batch(engine, applied["batch_id"])["status"] == "undone"
        with Session(engine) as db:
            assert db.query(KifuRawPlayerName).count() == 0
    finally:
        engine.dispose()


def test_format4_capture_must_precede_production(tmp_path):
    anchor = localized_anchor(tmp_path)
    anchor["content"]["sources"][0]["fetched_at"] = "2026-10-03T10:30:00Z"
    anchor["approval"]["content_sha256"] = canonical_sha256(anchor["content"])
    with pytest.raises(EvidenceError):
        validate_transliteration_anchor(anchor)


def test_format4_verifies_optional_third_record_and_exact_mapping_for_raw_variant(tmp_path):
    anchor = localized_anchor(tmp_path)
    content = anchor["content"]
    content["raw_value"] = "李元赫別"
    raw_source = deepcopy(content["sources"][0])
    raw_source.update(role="raw_spelling", exact_name=content["raw_value"])
    body = content["raw_value"] + " " + raw_source["birthdate"]
    path = tmp_path / "raw.html"
    path.write_bytes(body.encode())
    raw_source.update(
        body_path=str(path),
        body_excerpt=body,
        body_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        record_span=[0, len(body)],
        name_span=[0, len(content["raw_value"])],
        birthdate_span=[len(body) - 10, len(body)],
    )
    content["sources"].append(raw_source)
    content["raw_original_mapping"] = {
        "raw_value": content["raw_value"],
        "original_name": content["original_name"],
        "review_basis": "Exact observed alternative spelling reviewed in same profile",
    }
    anchor["approval"]["content_sha256"] = canonical_sha256(content)
    validate_transliteration_anchor(anchor)
    wrong_page = deepcopy(anchor)
    wrong_page["content"]["sources"][2]["person_id"] = "124"
    wrong_page["approval"]["content_sha256"] = canonical_sha256(wrong_page["content"])
    with pytest.raises(EvidenceError):
        validate_transliteration_anchor(wrong_page)
    for field in ("raw_original_mapping",):
        bad = deepcopy(anchor)
        bad["content"].pop(field)
        bad["approval"]["content_sha256"] = canonical_sha256(bad["content"])
        with pytest.raises(EvidenceError):
            validate_transliteration_anchor(bad)


def prior_mapping_anchor(tmp_path):
    from tests.web_ui.test_kifu_name_transliteration import signed

    anchor = localized_anchor(tmp_path)
    content = anchor["content"]
    content["raw_value"] = "李元赫別"
    mapping = {
        "raw_value": content["raw_value"],
        "original_name": content["original_name"],
        "source_lang": content["source_lang"],
        "raw_display_scope_sha256": content["raw_display_scope_sha256"],
        "method": "prior_reviewed_exact_raw_mapping_v1",
        "research_record_sha256": "c" * 64,
        "research_record_url": "https://example.org/review/exact-mapping",
        "review_basis": "Reuse independently approved exact spelling correspondence",
    }
    content["raw_original_mapping"] = signed(mapping, "approved_exact_raw_original_mapping")
    content["raw_original_mapping"]["approval"].update(
        produced_at="2026-10-03T08:00:00Z", reviewed_at="2026-10-03T09:00:00Z"
    )
    anchor["approval"]["content_sha256"] = canonical_sha256(content)
    return anchor


def test_format4_accepts_two_pages_with_prior_signed_exact_mapping(tmp_path):
    validate_transliteration_anchor(prior_mapping_anchor(tmp_path))


@pytest.mark.parametrize(
    "field",
    [
        "raw_value",
        "original_name",
        "source_lang",
        "raw_display_scope_sha256",
        "research_record_sha256",
        "research_record_url",
    ],
)
def test_format4_prior_mapping_must_bind_exact_scope_and_provenance(tmp_path, field):
    anchor = prior_mapping_anchor(tmp_path)
    anchor["content"]["raw_original_mapping"]["content"][field] = "wrong"
    anchor["content"]["raw_original_mapping"]["approval"]["content_sha256"] = canonical_sha256(
        anchor["content"]["raw_original_mapping"]["content"]
    )
    anchor["approval"]["content_sha256"] = canonical_sha256(anchor["content"])
    with pytest.raises(EvidenceError):
        validate_transliteration_anchor(anchor)


@pytest.mark.parametrize("fault", ["stale", "same_reviewer", "late", "unsigned"])
def test_format4_two_page_mapping_requires_prior_independent_signature(tmp_path, fault):
    anchor = prior_mapping_anchor(tmp_path)
    mapping = anchor["content"]["raw_original_mapping"]
    if fault == "stale":
        mapping["content"]["review_basis"] = "changed"
    if fault == "same_reviewer":
        mapping["approval"]["reviewer_id"] = mapping["approval"]["producer_id"]
    if fault == "late":
        mapping["approval"]["reviewed_at"] = "2026-10-03T12:00:00Z"
    if fault == "unsigned":
        anchor["content"]["raw_original_mapping"] = mapping["content"]
    anchor["approval"]["content_sha256"] = canonical_sha256(anchor["content"])
    with pytest.raises(EvidenceError):
        validate_transliteration_anchor(anchor)


def test_format4_prior_mapping_review_must_precede_anchor_production(tmp_path):
    anchor = prior_mapping_anchor(tmp_path)
    anchor["content"]["raw_original_mapping"]["approval"]["reviewed_at"] = "2026-10-03T10:30:00Z"
    anchor["approval"]["content_sha256"] = canonical_sha256(anchor["content"])
    with pytest.raises(EvidenceError):
        validate_transliteration_anchor(anchor)
