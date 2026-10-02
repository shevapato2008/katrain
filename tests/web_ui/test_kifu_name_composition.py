"""Synthetic approvals exercise the finite Honinbo composition contract, not production evidence."""

from copy import deepcopy

import pytest

import katrain.web.kifu.name_candidates as candidate_module
from katrain.web.kifu.name_candidates import canonical_sha256, validate_bundle
from katrain.web.kifu.name_composition import HONINBO_RAWS, render_edition
from katrain.web.kifu.name_parse import parse_event
from katrain.web.kifu.name_evidence import registry_sha256

LANGS = ("en", "cn", "tw", "jp", "ko", "de", "es", "fr", "ru", "tr", "ua")
BASES = (
    "Honinbo",
    "本因坊战",
    "本因坊戰",
    "本因坊戦",
    "본인방전",
    "Hon’inbō",
    "Torneo Hon'inbō",
    "Tournoi Hon'inbō",
    "Турнир Хонинбо",
    "Honinbo Turnuvası",
    "Турнір на звання Хон'імбо",
)
SERIES = {"kind": "event", "id": 7}
T0, T1, T2, T3 = (f"2026-10-02T{hour:02d}:00:00Z" for hour in (10, 11, 12, 13))


def fixture():
    sources = []
    for lang in LANGS:
        sources.append(
            {
                "id": lang,
                "tier": "official",
                "home_url": f"https://{lang}.example.org/",
                "language": {"cn": "zh-Hans", "tw": "zh-Hant", "jp": "ja", "ua": "uk"}.get(lang, lang),
            }
        )
    registry = {
        "version": "test-composition-v1",
        "language_tags": {lang: source["language"] for lang, source in zip(LANGS, sources)},
        "sources": sources,
        "language_scopes": {
            lang: {"required_source_ids": [lang], "complete_for_negative_claims": True} for lang in LANGS
        },
    }
    columns = ["id", "player_black", "player_white", "event", "black_player_id", "white_player_id", "event_id"]
    inventory = {
        "inventory_format": 2,
        "sha256": "a" * 64,
        "association_columns": columns,
        "album_associations": [[n, "Black", "White", raw, None, None, 7] for n, raw in enumerate(HONINBO_RAWS, 1)],
    }
    research = []
    base_rows = []
    rules = []
    for lang, base in zip(LANGS, BASES):
        check = {
            "owner": SERIES,
            "source_id": lang,
            "query": base,
            "status": "found",
            "url": f"https://{lang}.example.org/name",
            "fetched_at": T0,
            "http_status": 200,
            "body_sha256": "b" * 64,
            "body_excerpt": base,
            "observed_lang": registry["language_tags"][lang],
            "language_basis": "reviewed_text",
            "candidate_name": base,
            "identity_basis": "Synthetic series match",
        }
        evidence = {
            "owner": SERIES,
            "lang": lang,
            "registry_version": registry["version"],
            "registry_sha256": registry_sha256(registry),
            "scope_status": "found",
            "candidate_name": base,
            "source_checks": [check],
            "original_name": "本因坊戦",
            "original_language": "ja",
            "original_language_basis_url": check["url"],
            "reading": "honinbo",
            "reading_basis_url": check["url"],
            "producer_id": "researcher",
            "producer_model": "test",
            "review_status": "pending",
        }
        research.append(evidence)
        base_row = {
            "owner": SERIES,
            "lang": lang,
            "display_name": base,
            "decision_kind": "conventional",
            "research_sha256": canonical_sha256(evidence),
            "generation_rule_version": "none",
            "producer_id": "researcher",
            "producer_model": "test",
            "produced_at": T1,
            "review_status": "approved",
            "reviewer_id": "base-reviewer",
            "reviewer_model": "test",
            "reviewed_at": T2,
            "review_conclusion": "Synthetic base approval",
        }
        base_rows.append(base_row)
        content = {
            "series_owner": SERIES,
            "lang": lang,
            "base_candidate_sha256": canonical_sha256(base_row),
            "renderer_version": "honinbo-edition-v1",
            "style": lang,
            "sources": [
                {
                    "url": check["url"],
                    "body_lang": registry["language_tags"][lang],
                    "captured_at": T0,
                    "body_sha256": "b" * 64,
                    "excerpt": "Synthetic grammar example",
                    "basis": "Synthetic rule construction",
                }
            ],
        }
        rules.append(
            {
                "content": content,
                "approval": {
                    "status": "approved",
                    "content_sha256": canonical_sha256(content),
                    "producer_id": "rule-author",
                    "producer_model": "test",
                    "produced_at": T1,
                    "reviewer_id": "rule-reviewer",
                    "reviewer_model": "test",
                    "reviewed_at": T2,
                    "conclusion": "Synthetic rule approval",
                },
            }
        )
    raws = [
        {
            "owner": {"kind": "raw_event", "id": n},
            "raw_value": raw,
            "edition": n,
            "occurrence_album_ids": [n],
            "occurrence_sha256": canonical_sha256([n]),
            "raw_scope_sha256": canonical_sha256([[n, "event"]]),
        }
        for n, raw in enumerate(HONINBO_RAWS, 1)
    ]
    scope_content = {
        "series_owner": SERIES,
        "inventory_sha256": inventory["sha256"],
        "catalog_sha256": None,
        "raws": raws,
        "sources": [
            {
                "url": "https://en.example.org/edition",
                "body_lang": "en",
                "captured_at": T0,
                "body_sha256": "b" * 64,
                "excerpt": "Synthetic Honinbo edition evidence",
                "basis": "Synthetic source identifies numbered Honinbo editions",
            }
        ],
    }
    scope = {
        "content": scope_content,
        "approval": {
            "status": "approved",
            "content_sha256": canonical_sha256(scope_content),
            "producer_id": "scope-author",
            "producer_model": "test",
            "produced_at": T1,
            "reviewer_id": "scope-reviewer",
            "reviewer_model": "test",
            "reviewed_at": T2,
            "conclusion": "Synthetic decomposition approval",
        },
    }
    members = [{"owner": row["owner"], "lang": row["lang"]} for row in base_rows]
    candidates = list(base_rows)
    for raw in raws:
        for lang, base, rule in zip(LANGS, BASES, rules):
            row = {
                "owner": raw["owner"],
                "raw_value": raw["raw_value"],
                "lang": lang,
                "display_name": render_edition(rule["content"], base, raw["edition"]),
                "decision_kind": "composed",
                "research_sha256": "",
                "generation_rule_version": "honinbo-edition-v1",
                "series_owner": SERIES,
                "base_candidate_sha256": rule["content"]["base_candidate_sha256"],
                "composition_rule_sha256": canonical_sha256(rule),
                "edition": raw["edition"],
                "raw_scope_sha256": raw["raw_scope_sha256"],
                "producer_id": "name-author",
                "producer_model": "test",
                "produced_at": T2,
                "review_status": "approved",
                "reviewer_id": "name-reviewer",
                "reviewer_model": "test",
                "reviewed_at": T3,
                "review_conclusion": "Synthetic composed name approval",
            }
            row["composition_review_sha256"] = canonical_sha256(
                {
                    key: value
                    for key, value in row.items()
                    if key
                    not in {
                        "reviewer_id",
                        "reviewer_model",
                        "reviewed_at",
                        "review_conclusion",
                        "composition_review_sha256",
                    }
                }
            )
            candidates.append(row)
            members.append({"owner": raw["owner"], "raw_value": raw["raw_value"], "lang": lang})
    bundle = {
        "bundle_format": 1,
        "inventory_format": 2,
        "inventory_sha256": inventory["sha256"],
        "registry_version": registry["version"],
        "registry_sha256": registry_sha256(registry),
        "rule_version": "candidate-v1",
        "members": members,
        "member_set_sha256": canonical_sha256(members),
        "candidates": candidates,
        "composition": {"version": "honinbo-composition-v1", "scope": scope, "rules": rules},
    }
    return bundle, registry, inventory, research


def report(bundle, registry, inventory, research):
    return validate_bundle(bundle, registry, inventory, research)


def test_exact_frozen_raws_and_grammatical_branches():
    assert len(HONINBO_RAWS) == 34
    assert HONINBO_RAWS[0] == "1st Honinbo" and HONINBO_RAWS[-1] == "34th Honinbo"
    assert len(set(HONINBO_RAWS)) == 34
    for raw in HONINBO_RAWS:
        assert parse_event(raw, "League").category == "unclassified_pending"
    assert parse_event("JapanPromotionTournament,1934,Fall", None).category == "formal_event_candidate"
    bundle, registry, inventory, research = fixture()
    result = report(bundle, registry, inventory, research)
    assert result["ready"], result["errors"]
    assert result["approved"] == 385
    en = bundle["composition"]["rules"][0]["content"]
    for n, suffix in (
        (1, "st"),
        (2, "nd"),
        (3, "rd"),
        (11, "th"),
        (12, "th"),
        (13, "th"),
        (21, "st"),
        (22, "nd"),
        (23, "rd"),
        (31, "st"),
        (32, "nd"),
        (33, "rd"),
    ):
        assert render_edition(en, "Honinbo", n) == f"{n}{suffix} Honinbo"
    assert render_edition(bundle["composition"]["rules"][7]["content"], BASES[7], 1).startswith("1re édition")
    assert render_edition(bundle["composition"]["rules"][3]["content"], BASES[3], 34) == "第34期本因坊戦"


def test_later_write_preimage_binding_does_not_change_approved_base_dependency():
    bundle, registry, inventory, research = fixture()
    bundle["candidates"][0]["name_preimage_sha256"] = None
    bundle["candidates"][0]["preimage_binding"] = {"actor_id": "synthetic-binder"}
    result = report(bundle, registry, inventory, research)
    assert result["ready"], result["errors"]


@pytest.mark.parametrize(
    "field,value",
    [
        ("display_name", "Other series"),
        ("owner", {"kind": "event", "id": 8}),
        ("lang", "fr"),
        ("research_sha256", "f" * 64),
    ],
)
def test_write_binding_does_not_hide_changed_approved_base(field, value):
    bundle, registry, inventory, research = fixture()
    base = bundle["candidates"][0]
    base["name_preimage_sha256"] = None
    base["preimage_binding"] = {"actor_id": "synthetic-binder"}
    base[field] = value
    assert not report(bundle, registry, inventory, research)["ready"]


def test_scope_review_must_precede_candidate_production():
    bundle, registry, inventory, research = fixture()
    bundle["composition"]["scope"]["approval"]["reviewed_at"] = T3
    assert not report(bundle, registry, inventory, research)["ready"]


def test_composed_rows_participate_in_display_collision_check(monkeypatch):
    bundle, registry, inventory, research = fixture()
    original = candidate_module.normalize_alias
    monkeypatch.setattr(
        candidate_module,
        "normalize_alias",
        lambda name: "same-name" if name in {"1st Honinbo", "2nd Honinbo"} else original(name),
    )
    result = report(bundle, registry, inventory, research)
    assert any("possible name collision" in error for error in result["errors"])


@pytest.mark.parametrize(
    "mutation",
    [
        "ordinal",
        "extra_raw",
        "missing_raw",
        "occurrence",
        "scope_hash",
        "series",
        "language",
        "base_hash",
        "rule_hash",
        "rule_content",
        "scope_content",
        "rule_unsigned",
        "scope_unsigned",
        "candidate_stale",
        "base_changed",
        "display",
        "duplicate",
        "collision",
        "scope_source",
        "catalog",
        "missing_candidate",
        "candidate_unsigned",
        "invalid_source_url",
    ],
)
def test_composition_rejects_tampering_and_incomplete_sets(mutation):
    bundle, registry, inventory, research = fixture()
    row = bundle["candidates"][11]
    scope = bundle["composition"]["scope"]
    rule = bundle["composition"]["rules"][0]
    if mutation == "ordinal":
        row["edition"] = 2
    elif mutation == "extra_raw":
        scope["content"]["raws"].append({**scope["content"]["raws"][0], "raw_value": "35th Honinbo"})
    elif mutation == "missing_raw":
        scope["content"]["raws"].pop()
    elif mutation == "occurrence":
        scope["content"]["raws"][0]["occurrence_album_ids"] = []
    elif mutation == "scope_hash":
        row["raw_scope_sha256"] = "f" * 64
    elif mutation == "series":
        row["series_owner"] = {"kind": "event", "id": 8}
    elif mutation == "language":
        rule["content"]["lang"] = "fr"
    elif mutation == "base_hash":
        row["base_candidate_sha256"] = "f" * 64
    elif mutation == "rule_hash":
        row["composition_rule_sha256"] = "f" * 64
    elif mutation == "rule_content":
        rule["content"]["style"] = "fr"
    elif mutation == "scope_content":
        scope["content"]["series_owner"] = {"kind": "event", "id": 8}
    elif mutation == "rule_unsigned":
        rule["approval"]["reviewer_id"] = rule["approval"]["producer_id"]
    elif mutation == "scope_unsigned":
        scope["approval"]["status"] = "pending"
    elif mutation == "candidate_stale":
        row["reviewed_at"] = T1
    elif mutation == "base_changed":
        bundle["candidates"][0]["display_name"] = "Changed"
    elif mutation == "display":
        row["display_name"] = "wrong"
    elif mutation == "duplicate":
        bundle["candidates"].append(deepcopy(row))
    elif mutation == "collision":
        bundle["candidates"][12]["display_name"] = row["display_name"]
    elif mutation == "scope_source":
        scope["content"].pop("sources")
    elif mutation == "catalog":
        scope["content"]["catalog_sha256"] = "f" * 64
    elif mutation == "missing_candidate":
        bundle["candidates"].pop()
    elif mutation == "candidate_unsigned":
        row["composition_review_sha256"] = "f" * 64
    elif mutation == "invalid_source_url":
        scope["content"]["sources"][0]["url"] = "https://"
    if mutation in {"scope_source", "catalog", "invalid_source_url"}:
        scope["approval"]["content_sha256"] = canonical_sha256(scope["content"])
    result = report(bundle, registry, inventory, research)
    assert not result["ready"], mutation


@pytest.mark.parametrize(
    "raw",
    [
        "0th Honinbo",
        "35th Honinbo",
        "1st honinbo",
        "01st Honinbo",
        "1st Honinbo ",
        "1st Oteai",
        "JapanPromotionTournament,1934,Fall",
        "Honinbo",
        "2st Honinbo",
    ],
)
def test_unlisted_raw_values_cannot_be_rendered(raw):
    bundle, registry, inventory, research = fixture()
    bundle["composition"]["scope"]["content"]["raws"][0]["raw_value"] = raw
    assert not report(bundle, registry, inventory, research)["ready"]
