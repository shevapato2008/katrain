"""Finite six-language transliteration is checked offline without absence claims."""

from copy import deepcopy

import pytest

from katrain.web.kifu.name_candidates import canonical_sha256, validate_bundle
from katrain.web.kifu.name_evidence import EvidenceError, validate_transliteration_anchor
from tests.web_ui.test_kifu_name_candidates import bundle, candidate, inventory, member, registry


def signed(content, conclusion, producer="producer", reviewer="reviewer"):
    return {
        "content": content,
        "approval": {
            "status": "approved",
            "content_sha256": canonical_sha256(content),
            "producer_id": producer,
            "producer_model": "gpt-6-luna",
            "produced_at": "2026-10-03T10:00:00Z",
            "reviewer_id": reviewer,
            "reviewer_model": "gpt-6-sol",
            "reviewed_at": "2026-10-03T11:00:00Z",
            "conclusion": conclusion,
        },
    }


def source_anchor(owner=None, original="李元赫", words=None):
    words = words or [["li"], ["yuan", "he"]]
    return {
        "evidence_kind": "transliteration_anchor",
        **signed(
            {
                "owner": owner or {"kind": "player", "id": 17},
                "entity_kind": "player",
                "original_name": original,
                "source_lang": "zh-Hans",
                "reading_system": "pinyin-syllables-v1",
                "reading_words": words,
                "reading_text": " ".join(token for word in words for token in word),
                "source_reading": "li yuan he",
                "reading_normalization_basis": "Reviewed toneless Pinyin syllables and word boundaries",
                "reading_normalization_version": "pinyin-source-v1",
                "sources": [
                    {
                        "url": "https://example.org/player",
                        "fetched_at": "2026-10-03T09:00:00Z",
                        "http_status": 200,
                        "body_sha256": "b" * 64,
                        "body_excerpt": f"{original} li yuan he",
                        "observed_lang": "zh-Hans",
                        "language_basis": "reviewed_text",
                        "identity_basis": "Exact player profile and independently checked reading",
                    }
                ],
            },
            "approved_original_name_and_reading",
        ),
    }


def two_publisher_anchor():
    anchor = source_anchor()
    content = anchor["content"]
    content.update(
        anchor_format=2,
        source_reading_kind="published_roman_name",
        source_reading="Li Yuanhe",
        source_link={
            "method": "official_name_dob_to_localized_profile_id_v1",
            "official_match_count": 1,
            "official_scope_sha256": "a" * 64,
            "unresolved_conflicts": [],
            "review_basis": "One official record, matching full DOB and one GoRatings person ID",
        },
    )
    shared = {
        "fetched_at": "2026-10-03T09:00:00Z",
        "http_status": 200,
        "body_sha256": "b" * 64,
        "language_basis": "reviewed_text",
        "identity_basis": "Exact professional person record and full birth date",
        "birthdate": "1971-01-24",
    }
    content["sources"] = [
        {
            **shared,
            "role": "original",
            "body_sha256": "a" * 64,
            "url": "https://wqapi.cwql.org.cn/playerInfo/professional/list",
            "body_excerpt": "CWA000001 李元赫 1971-01-24",
            "observed_lang": "zh-Hans",
            "publisher_id": "china_go_association",
            "person_id_namespace": "cwa_player_no",
            "person_id": "CWA000001",
            "exact_name": "李元赫",
            "record_locator": "playerNo=CWA000001",
        },
        {
            **shared,
            "role": "identity_bridge",
            "url": "https://www.goratings.org/zh/players/123.html",
            "body_excerpt": "李元赫 1971-01-24",
            "observed_lang": "zh",
            "publisher_id": "goratings",
            "person_id_namespace": "goratings_player_id",
            "person_id": "123",
            "exact_name": "李元赫",
            "record_locator": "profile heading and birthdate",
        },
        {
            **shared,
            "role": "reading",
            "url": "https://www.goratings.org/en/players/123.html",
            "body_excerpt": "Li Yuanhe 1971-01-24",
            "observed_lang": "en",
            "publisher_id": "goratings",
            "person_id_namespace": "goratings_player_id",
            "person_id": "123",
            "exact_name": "Li Yuanhe",
            "record_locator": "profile heading and birthdate",
        },
    ]
    anchor["approval"]["content_sha256"] = canonical_sha256(content)
    return anchor


def test_two_publisher_anchor_preserves_real_source_languages_and_enters_six_language_bundle():
    proposed, anchors, snapshot = transliteration_bundle()
    anchors[:] = [two_publisher_anchor()]
    refresh_bindings(proposed, anchors)
    assert check(proposed, anchors, snapshot)["ready"] is True


@pytest.mark.parametrize(
    "mutation",
    [
        "missing_bridge", "different_dob", "different_profile_id", "wrong_namespace",
        "duplicate_official_name", "reading_language_lie", "missing_person_excerpt",
        "duplicate_role", "unresolved_conflict", "wrong_official_url", "changed_word_boundary",
        "unknown_format", "boolean_format", "v2_fields_in_v1", "stale_signature",
        "wrong_roster_hash", "invalid_birthdate", "traditional_language_lie",
        "bridge_traditional_language_lie", "unicode_official_id", "unicode_profile_id",
    ],
)
def test_two_publisher_anchor_rejects_unlinked_or_misrepresented_reading(mutation):
    anchor = two_publisher_anchor()
    content = anchor["content"]
    original, bridge, reading = content["sources"]
    if mutation == "missing_bridge":
        content["sources"].pop(1)
    elif mutation == "different_dob":
        reading["birthdate"] = "1972-01-24"
    elif mutation == "different_profile_id":
        reading["person_id"] = "124"
        reading["url"] = "https://www.goratings.org/en/players/124.html"
    elif mutation == "wrong_namespace":
        bridge["person_id_namespace"] = "cwa_player_no"
    elif mutation == "duplicate_official_name":
        content["source_link"]["official_match_count"] = 2
    elif mutation == "reading_language_lie":
        reading["observed_lang"] = "zh-Hans"
    elif mutation == "missing_person_excerpt":
        reading["body_excerpt"] = "Li Yuanhe"
    elif mutation == "duplicate_role":
        bridge["role"] = "original"
    elif mutation == "unresolved_conflict":
        content["source_link"]["unresolved_conflicts"] = ["DOB differs"]
    elif mutation == "wrong_official_url":
        original["url"] = "https://other.example.org/playerInfo/professional/list"
    elif mutation == "changed_word_boundary":
        content["reading_words"] = [["li", "yuan", "he"]]
    elif mutation == "unknown_format":
        content["anchor_format"] = 3
    elif mutation == "boolean_format":
        content["anchor_format"] = True
    elif mutation == "v2_fields_in_v1":
        content["anchor_format"] = 1
    elif mutation == "wrong_roster_hash":
        content["source_link"]["official_scope_sha256"] = "c" * 64
    elif mutation == "invalid_birthdate":
        reading["birthdate"] = "1971-02-30"
    elif mutation == "traditional_language_lie":
        original["observed_lang"] = "zh-Hant"
    elif mutation == "bridge_traditional_language_lie":
        bridge["observed_lang"] = "zh-Hant"
    elif mutation == "unicode_official_id":
        original["person_id"] = "CWA０００００１"
        original["body_excerpt"] = "CWA０００００１ 李元赫 1971-01-24"
    elif mutation == "unicode_profile_id":
        for source, lang in ((bridge, "zh"), (reading, "en")):
            source["person_id"] = "1２3"
            source["url"] = f"https://www.goratings.org/{lang}/players/1２3.html"
    elif mutation == "stale_signature":
        content["source_link"]["review_basis"] = "Changed after approval"
    else:
        raise AssertionError(mutation)
    if mutation != "stale_signature":
        anchor["approval"]["content_sha256"] = canonical_sha256(content)
    with pytest.raises(EvidenceError):
        validate_transliteration_anchor(anchor)


def transliteration_bundle(lang="ru", snapshot=None):
    snapshot = [] if snapshot is None else snapshot
    output = {
        "de": "Li Yuanhe",
        "es": "Li Yuanhe",
        "fr": "Li Yuanhe",
        "tr": "Li Yuanhe",
        "ru": "Ли Юаньхэ",
        "ua": "Лі Юаньхе",
    }[lang]
    mapping = {"li": "li", "yuan": "yuan", "he": "he"}
    if lang == "ru":
        mapping = {"li": "ли", "yuan": "юань", "he": "хэ"}
    if lang == "ua":
        mapping = {"li": "лі", "yuan": "юань", "he": "хе"}
    anchor = source_anchor()
    rule = signed(
        {
            "version": f"zh-{lang}-test-v1",
            "lang": lang,
            "source_lang": "zh-Hans",
            "reading_system": "pinyin-syllables-v1",
            "entity_kind": "player",
            "operation": "syllable_map_v1",
            "token_map": mapping,
            "sources": [
                {
                    "url": "https://example.org/transliteration",
                    "fetched_at": "2026-10-03T09:00:00Z",
                    "http_status": 200,
                    "body_sha256": "c" * 64,
                    "body_excerpt": "Language-specific transliteration rule and reviewed examples",
                    "language_basis": "reviewed_text",
                    "observed_lang": "uk" if lang == "ua" else lang,
                    "identity_basis": "Reviewed target-language spelling rule",
                }
            ],
        },
        "approved_transliteration_rule",
    )
    item = {
        "owner": anchor["content"]["owner"],
        "lang": lang,
        "display_name": output,
        "source_anchor_sha256": canonical_sha256(anchor),
        "rule_sha256": canonical_sha256(rule),
    }
    batch = signed(
        {
            "version": "secondary-transliteration-v1",
            "lang": lang,
            "source_lang": "zh-Hans",
            "reading_system": "pinyin-syllables-v1",
            "entity_kind": "player",
            "rule_sha256": canonical_sha256(rule),
            "approved_name_snapshot_sha256": canonical_sha256(snapshot),
            "members": [item],
        },
        "approved_transliteration_batch",
    )
    batch["approval"].update(produced_at="2026-10-03T12:00:00Z", reviewed_at="2026-10-03T13:00:00Z")
    approval = batch["approval"]
    row = candidate(
        lang=lang,
        display_name=output,
        decision_kind="transliterated",
        research_sha256="",
        generation_rule_version=rule["content"]["version"],
        source_anchor_sha256=item["source_anchor_sha256"],
        rule_sha256=item["rule_sha256"],
        transliteration_batch_sha256=canonical_sha256(batch),
        **{
            key: approval[key]
            for key in ("producer_id", "producer_model", "produced_at", "reviewer_id", "reviewer_model", "reviewed_at")
        },
        review_conclusion="approved_transliteration_batch",
    )
    proposed = bundle(
        members=[member(lang=lang)],
        candidates=[row],
        transliteration={
            "version": "secondary-transliteration-v1",
            "rules": [rule],
            "batches": [batch],
        },
    )
    return proposed, [anchor], snapshot


def check(proposed, anchors, snapshot):
    return validate_bundle(proposed, registry(), inventory(), anchors, approved_name_snapshot=snapshot)


@pytest.mark.parametrize("lang", ["de", "es", "fr", "ru", "tr", "ua"])
def test_six_languages_accept_signed_finite_transliteration_without_negative_search(lang):
    proposed, anchors, snapshot = transliteration_bundle(lang)
    result = check(proposed, anchors, snapshot)
    assert result["ready"] is True
    assert result["approved"] == 1
    assert result["write_ready"] is False
    assert any("preimage" in error for error in result["write_errors"])


@pytest.mark.parametrize(
    "mutation",
    [
        "member_added",
        "member_removed",
        "output",
        "rule",
        "reading",
        "original",
        "source",
        "wrong_system",
        "missing_source",
        "anchor_self_review",
        "rule_self_review",
        "batch_self_review",
        "candidate_self_review",
        "rule_old_hash",
        "anchor_old_hash",
        "batch_old_hash",
        "snapshot",
        "unsupported_token",
        "wrong_script",
        "claimed_absence",
        "conventional",
        "unapproved_anchor",
        "unapproved_rule",
        "unapproved_batch",
    ],
)
def test_changed_transliteration_dependencies_and_exceptional_names_are_rejected(mutation):
    proposed, anchors, snapshot = transliteration_bundle()
    row = proposed["candidates"][0]
    rule = proposed["transliteration"]["rules"][0]
    batch = proposed["transliteration"]["batches"][0]
    anchor = anchors[0]
    if mutation == "member_added":
        batch["content"]["members"].append(deepcopy(batch["content"]["members"][0]))
    elif mutation == "member_removed":
        batch["content"]["members"] = []
    elif mutation == "output":
        row["display_name"] = "Ли Юанхэ"
    elif mutation == "rule":
        rule["content"]["token_map"]["he"] = "хе"
    elif mutation == "reading":
        anchor["content"]["reading_words"] = [["li"], ["he"]]
    elif mutation == "original":
        anchor["content"]["original_name"] = "Other"
    elif mutation == "source":
        anchor["content"]["sources"][0]["body_sha256"] = "0" * 64
    elif mutation == "wrong_system":
        anchor["content"]["reading_system"] = "hepburn-syllables-v1"
    elif mutation == "missing_source":
        anchor["content"]["sources"] = []
    elif mutation in {"anchor_self_review", "rule_self_review", "batch_self_review"}:
        record = {"anchor_self_review": anchor, "rule_self_review": rule, "batch_self_review": batch}[mutation]
        record["approval"]["reviewer_id"] = record["approval"]["producer_id"]
    elif mutation == "candidate_self_review":
        row["reviewer_id"] = row["producer_id"]
    elif mutation == "rule_old_hash":
        row["rule_sha256"] = "0" * 64
    elif mutation == "anchor_old_hash":
        row["source_anchor_sha256"] = "0" * 64
    elif mutation == "batch_old_hash":
        row["transliteration_batch_sha256"] = "0" * 64
    elif mutation == "snapshot":
        snapshot.append(
            {
                "owner": {"kind": "player", "id": 19},
                "lang": "ru",
                "display_name": "Другой",
                "decision_kind": "conventional",
                "review_status": "approved",
            }
        )
    elif mutation == "unsupported_token":
        anchor["content"]["reading_words"] = [["unknown"]]
    elif mutation == "wrong_script":
        row["display_name"] = "Li Yuanhe"
    elif mutation == "claimed_absence":
        row["scope_status"] = "not_found_in_scope"
    elif mutation == "conventional":
        row["decision_kind"] = "conventional"
    elif mutation in {"unapproved_anchor", "unapproved_rule", "unapproved_batch"}:
        {"unapproved_anchor": anchor, "unapproved_rule": rule, "unapproved_batch": batch}[mutation]["approval"][
            "status"
        ] = "pending"
    assert check(proposed, anchors, snapshot)["ready"] is False


@pytest.mark.parametrize("lang", ["en", "cn", "tw", "jp", "ko"])
def test_original_five_languages_cannot_use_batch_transliteration(lang):
    proposed, anchors, snapshot = transliteration_bundle()
    proposed["candidates"][0]["lang"] = lang
    proposed["members"][0]["lang"] = lang
    proposed["member_set_sha256"] = canonical_sha256(proposed["members"])
    assert check(proposed, anchors, snapshot)["ready"] is False


@pytest.mark.parametrize(
    "owner_id,decision,display",
    [
        (17, "conventional", "Другой вариант"),
        (19, "transliterated", "Ли Юаньхэ"),
        (19, "conventional", "Ли Юаньхэ"),
    ],
)
def test_existing_conventional_and_cross_batch_same_language_collision_are_rejected(owner_id, decision, display):
    snapshot = [
        {
            "owner": {"kind": "player", "id": owner_id},
            "lang": "ru",
            "display_name": display,
            "decision_kind": decision,
            "review_status": "approved",
        }
    ]
    proposed, anchors, snapshot = transliteration_bundle(snapshot=snapshot)
    assert check(proposed, anchors, snapshot)["ready"] is False


def test_new_decision_requires_explicit_current_approved_name_snapshot():
    proposed, anchors, snapshot = transliteration_bundle()
    assert validate_bundle(proposed, registry(), inventory(), anchors)["ready"] is False


def refresh_bindings(proposed, anchors):
    """Test approvals deliberately sign the changed data; recomputation must still reject it."""
    section = proposed["transliteration"]
    for record in [*anchors, *section["rules"]]:
        record["approval"]["content_sha256"] = canonical_sha256(record["content"])
    for batch, row, anchor in zip(section["batches"], proposed["candidates"], anchors):
        rule = next(rule for rule in section["rules"] if rule["content"]["lang"] == row["lang"])
        rule_hash = canonical_sha256(rule)
        entry = batch["content"]["members"][0]
        entry.update(
            owner=row["owner"],
            lang=row["lang"],
            display_name=row["display_name"],
            source_anchor_sha256=canonical_sha256(anchor),
            rule_sha256=rule_hash,
        )
        batch["content"]["rule_sha256"] = rule_hash
        batch["approval"]["content_sha256"] = canonical_sha256(batch["content"])
        row.update(
            source_anchor_sha256=entry["source_anchor_sha256"],
            rule_sha256=rule_hash,
            transliteration_batch_sha256=canonical_sha256(batch),
        )
    proposed["member_set_sha256"] = canonical_sha256(proposed["members"])


@pytest.mark.parametrize("exception", ["wrong_output", "unknown_syllable", "unsafe_operation", "wrong_reading_system"])
def test_even_newly_signed_batch_must_recompute_every_output_and_reject_exceptions(exception):
    proposed, anchors, snapshot = transliteration_bundle()
    if exception == "wrong_output":
        proposed["candidates"][0]["display_name"] = "Ли Юанхэ"
    elif exception == "unknown_syllable":
        anchors[0]["content"].update(reading_words=[["xyz"]], reading_text="xyz", source_reading="xyz")
        anchors[0]["content"]["sources"][0]["body_excerpt"] = "李元赫 xyz"
    elif exception == "unsafe_operation":
        proposed["transliteration"]["rules"][0]["content"]["operation"] = "eval"
    elif exception == "wrong_reading_system":
        anchors[0]["content"]["reading_system"] = "hepburn-syllables-v1"
    refresh_bindings(proposed, anchors)
    result = check(proposed, anchors, snapshot)
    assert result["ready"] is False
    expected = {
        "wrong_output": "mechanical recomputation",
        "unknown_syllable": "unsupported token",
        "unsafe_operation": "operation invalid",
        "wrong_reading_system": "reading system invalid",
    }[exception]
    assert any(expected in error for error in result["errors"])


@pytest.mark.parametrize("lang", ["de", "es", "fr", "tr"])
def test_explicit_roman_copy_rule_is_available_only_for_reviewed_roman_readings(lang):
    proposed, anchors, snapshot = transliteration_bundle(lang)
    rule = proposed["transliteration"]["rules"][0]
    rule["content"].update(operation="copy_roman_words_v1")
    rule["content"].pop("token_map")
    refresh_bindings(proposed, anchors)
    assert check(proposed, anchors, snapshot)["ready"] is True


@pytest.mark.parametrize("lang", ["de", "es", "fr", "tr"])
def test_roman_copy_rule_accepts_truthfully_labeled_english_rule_source(lang):
    proposed, anchors, snapshot = transliteration_bundle(lang)
    rule = proposed["transliteration"]["rules"][0]
    rule["content"].update(operation="copy_roman_words_v1")
    rule["content"].pop("token_map")
    rule["content"]["sources"][0]["observed_lang"] = "en"
    rule["content"]["sources"][0]["identity_basis"] = "English Roman name copy guidance"
    refresh_bindings(proposed, anchors)
    assert check(proposed, anchors, snapshot)["ready"] is True


def test_roman_copy_rule_accepts_reviewed_latin_guidance_without_forged_language():
    proposed, anchors, snapshot = transliteration_bundle("de")
    rule = proposed["transliteration"]["rules"][0]
    rule["content"].update(operation="copy_roman_words_v1")
    rule["content"].pop("token_map")
    source = rule["content"]["sources"][0]
    source["observed_lang"] = "en"
    spanish = {**source, "url": "https://example.org/spanish-guidance", "observed_lang": "es"}
    rule["content"]["sources"].append(spanish)
    refresh_bindings(proposed, anchors)
    assert check(proposed, anchors, snapshot)["ready"] is True
    spanish["observed_lang"] = "ja"
    refresh_bindings(proposed, anchors)
    assert check(proposed, anchors, snapshot)["ready"] is False


@pytest.mark.parametrize("lang", ["de", "ru", "ua"])
def test_english_rule_source_does_not_authorize_syllable_transliteration(lang):
    proposed, anchors, snapshot = transliteration_bundle(lang)
    rule = proposed["transliteration"]["rules"][0]
    rule["content"]["sources"][0]["observed_lang"] = "en"
    refresh_bindings(proposed, anchors)
    result = check(proposed, anchors, snapshot)
    assert result["ready"] is False
    assert any("source provenance or language invalid" in error for error in result["errors"])


def test_two_signed_batches_cannot_hide_a_same_language_collision():
    proposed, anchors, snapshot = transliteration_bundle()
    other, other_anchors, _ = transliteration_bundle()
    other["candidates"][0]["owner"] = other["members"][0]["owner"] = {"kind": "player", "id": 18}
    other_anchors[0]["content"]["owner"] = {"kind": "player", "id": 18}
    other_anchors[0]["content"]["original_name"] = "另一个人"
    other_anchors[0]["content"]["sources"][0]["body_excerpt"] = "另一个人 li yuan he"
    refresh_bindings(other, other_anchors)
    proposed["candidates"].extend(other["candidates"])
    proposed["members"].extend(other["members"])
    proposed["member_set_sha256"] = canonical_sha256(proposed["members"])
    proposed["transliteration"]["batches"].extend(other["transliteration"]["batches"])
    anchors.extend(other_anchors)
    result = check(proposed, anchors, snapshot)
    assert result["ready"] is False
    assert any("cross-batch collision" in error for error in result["errors"])


def test_signed_batch_cannot_drop_a_candidate_from_its_complete_member_set():
    proposed, anchors, snapshot = transliteration_bundle()
    proposed["candidates"] = []
    result = check(proposed, anchors, snapshot)
    assert result["ready"] is False
    assert any("complete signed candidate set" in error for error in result["errors"])


def test_reused_rule_version_cannot_name_two_different_signed_maps():
    proposed, anchors, snapshot = transliteration_bundle()
    duplicate = deepcopy(proposed["transliteration"]["rules"][0])
    duplicate["content"]["token_map"]["he"] = "хе"
    duplicate["approval"]["content_sha256"] = canonical_sha256(duplicate["content"])
    proposed["transliteration"]["rules"].append(duplicate)
    result = check(proposed, anchors, snapshot)
    assert any("rule version" in error for error in result["errors"])


def raw_transliteration_bundle():
    proposed, anchors, snapshot = transliteration_bundle()
    owner = {"kind": "raw_player", "id": 7}
    proposed["members"][0].update(owner=owner, raw_value="李元赫")
    proposed["candidates"][0].update(owner=owner, raw_value="李元赫")
    anchors[0]["content"].update(owner=owner, raw_value="李元赫")
    proposed["transliteration"]["batches"][0]["content"]["members"][0]["raw_value"] = "李元赫"
    refresh_bindings(proposed, anchors)
    inv = inventory()
    inv["album_associations"][0][1] = "李元赫"
    return proposed, anchors, snapshot, inv


def test_raw_spelling_cannot_change_under_an_unchanged_signed_transliteration_batch():
    proposed, anchors, snapshot, inv = raw_transliteration_bundle()
    assert validate_bundle(proposed, registry(), inv, anchors, approved_name_snapshot=snapshot)["ready"] is True
    proposed["members"][0]["raw_value"] = proposed["candidates"][0]["raw_value"] = "木谷实"
    proposed["member_set_sha256"] = canonical_sha256(proposed["members"])
    result = validate_bundle(proposed, registry(), inv, anchors, approved_name_snapshot=snapshot)
    assert result["ready"] is False
    assert any("raw" in error for error in result["errors"])


@pytest.mark.parametrize("source_reading", ["李元赫", "zhang wei"])
def test_signed_source_must_have_matching_phonetic_reading_not_just_original_name(source_reading):
    proposed, anchors, snapshot = transliteration_bundle()
    anchors[0]["content"]["source_reading"] = source_reading
    anchors[0]["content"]["sources"][0]["body_excerpt"] = f"李元赫 {source_reading}"
    refresh_bindings(proposed, anchors)
    result = check(proposed, anchors, snapshot)
    assert result["ready"] is False
    assert any("phonetic" in error or "normalization" in error for error in result["errors"])


@pytest.mark.parametrize("lang", ["ru", "ua"])
def test_signed_maps_cannot_emit_cyrillic_letters_outside_target_alphabet(lang):
    proposed, anchors, snapshot = transliteration_bundle(lang)
    proposed["transliteration"]["rules"][0]["content"]["token_map"]["li"] = "Ӿӿ"
    proposed["candidates"][0]["display_name"] = "Ӿӿ " + proposed["candidates"][0]["display_name"].split(" ", 1)[1]
    refresh_bindings(proposed, anchors)
    result = check(proposed, anchors, snapshot)
    assert result["ready"] is False
    assert any("token map invalid" in error for error in result["errors"])
