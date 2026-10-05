"""Player page links come from current independently approved name evidence."""

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json

import pytest
from sqlalchemy import JSON, create_engine, event, select
from sqlalchemy.orm import Session

from katrain.web.core.models_db import (
    Base,
    KifuEvent,
    KifuEventAlias,
    KifuNameResearchEvidence,
    KifuNameSourceRegistry,
    KifuPlayer,
    KifuPlayerAlias,
    KifuPlayerName,
    KifuRawEventValue,
    KifuRawPlayerValue,
)
from katrain.web.kifu.name_batch import _check_owner_manifest, catalog_snapshot_sha, name_preimage_sha256
from katrain.web.kifu.name_candidates import canonical_sha256

OWNER = {"kind": "player", "id": 17}
OFFICIAL = "https://www.nihonkiin.or.jp/player/htm/ki000001.html"
WIKI = "https://en.wikipedia.org/wiki/Go_Seigen"
REGISTRY = {
    "version": "fixture-1",
    "sources": [
        {"id": "wiki-en", "tier": "wikipedia_article", "language": "en", "home_url": "https://en.wikipedia.org/"},
        {"id": "wiki-ja", "tier": "wikipedia_article", "language": "ja", "home_url": "https://ja.wikipedia.org/"},
        {"id": "nihon", "tier": "official", "language": "ja", "home_url": "https://www.nihonkiin.or.jp/"},
        {"id": "rating-en", "tier": "language_go", "language": "en", "home_url": "https://www.goratings.org/en/"},
        {"id": "rating-zh", "tier": "language_go", "language": "zh", "home_url": "https://www.goratings.org/zh/"},
    ],
}


def capture(**fields):
    return {
        "http_status": 200,
        "body_sha256": "a" * 64,
        "body_excerpt": "呉清源 / Go Seigen, professional Go player",
        "identity_basis": "Same professional and birth date",
        "fetched_at": "2026-10-05T00:00:00Z",
        **fields,
    }


def add_name(db, *, lang="en", display="Go Seigen", source_id="wiki-en", url=WIKI):
    research = {
        "owner": OWNER,
        "lang": lang,
        "registry_version": REGISTRY["version"],
        "registry_sha256": canonical_sha256(REGISTRY),
        "scope_status": "found",
        "candidate_name": display,
        "original_name": "呉清源",
        "original_language": "ja",
        "original_language_basis_url": OFFICIAL,
        "original_language_evidence": capture(),
        "source_checks": [
            capture(
                owner=OWNER,
                source_id=source_id,
                url=url,
                status="found",
                candidate_name=display,
                observed_lang="ja" if lang == "jp" else lang,
                identity_corroboration=capture(source_id="nihon", url=OFFICIAL, original_name="呉清源"),
            )
        ],
        # Research may remain pending: the independently approved candidate binds its exact hash.
        "review_status": "pending",
    }
    candidate = {
        "owner": OWNER,
        "lang": lang,
        "display_name": display,
        "decision_kind": "conventional",
        "generation_rule_version": "none",
        "review_status": "approved",
        "producer_id": "producer",
        "reviewer_id": "reviewer",
        "producer_model": "gpt-6-astra",
        "reviewer_model": "gpt-6.1-sol",
        "research_sha256": canonical_sha256(research),
    }
    evidence = KifuNameResearchEvidence(
        player_id=17,
        lang=lang,
        revision=1,
        source_registry_id=1,
        candidate_name=display,
        decision_kind="conventional",
        generation_rule_version="none",
        research_payload={"candidate": candidate, "research": research},
        producer_id="producer",
        producer_model="gpt-6-astra",
        reviewer_id="reviewer",
        reviewer_model="gpt-6.1-sol",
        reviewed_at=datetime.now(timezone.utc),
        review_status="approved",
    )
    db.add(evidence)
    db.flush()
    db.add(
        KifuPlayerName(
            player_id=17,
            lang=lang,
            display_name=display,
            status="verified",
            revision=1,
            decision_kind="conventional",
            generation_rule_version="none",
            evidence_id=evidence.id,
        )
    )
    return evidence


@pytest.fixture
def engine(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'pages.db'}")
    Base.metadata.create_all(engine)
    with Session(engine) as db, db.begin():
        db.add_all([KifuPlayer(id=17, canonical_name="吴清源"), KifuPlayer(id=18, canonical_name="其他棋手")])
        db.add(
            KifuNameSourceRegistry(
                id=1, version=REGISTRY["version"], sha256=canonical_sha256(REGISTRY), registry=REGISTRY
            )
        )
        db.flush()
        add_name(db)
    yield engine
    engine.dispose()


def pages(engine, player_id=17):
    with Session(engine) as db:
        return db.get(KifuPlayer, player_id).authoritative_pages


def mutate_research(engine, change, *, rebind=True):
    with Session(engine) as db, db.begin():
        evidence = db.get(KifuNameResearchEvidence, 1)
        payload = deepcopy(evidence.research_payload)
        change(payload["research"])
        if rebind:
            payload["candidate"]["research_sha256"] = canonical_sha256(payload["research"])
        evidence.research_payload = payload


def test_storage_uses_json_with_an_empty_list(engine):
    assert hasattr(KifuPlayer, "authoritative_pages"), "player page storage is missing"
    assert isinstance(KifuPlayer.__table__.c.authoritative_pages.type, JSON)
    assert pages(engine) == []


def test_collects_current_wikipedia_official_and_profile_sources(engine):
    from katrain.web.kifu.player_pages import sync_player_pages

    with Session(engine) as db, db.begin():
        add_name(db, lang="jp", display="呉清源", source_id="wiki-ja", url="https://ja.wikipedia.org/wiki/呉清源")

    def add_profile(research):
        research["source_checks"].append(
            capture(
                owner=OWNER,
                source_id="rating-en",
                url="https://www.goratings.org/en/players/1.html",
                status="found",
                candidate_name="Go Seigen",
                observed_lang="en",
                identity_bridges=[capture(url="https://www.goratings.org/zh/players/1.html")],
            )
        )

    mutate_research(engine, add_profile)
    report = sync_player_pages(engine, apply=True)
    result = {page["url"]: page for page in pages(engine)}
    assert report["players_changed"] == 1 and report["pages_added"] == 5
    assert result[OFFICIAL] == {
        "url": OFFICIAL,
        "source_id": "nihon",
        "language": "ja",
        "role": "official",
        "evidence_ids": [1, 2],
    }
    assert result[WIKI]["role"] == "wikipedia_article"
    assert result["https://www.goratings.org/zh/players/1.html"]["source_id"] == "rating-zh"
    assert result["https://www.goratings.org/zh/players/1.html"]["language"] == "zh"
    assert pages(engine, 18) == []


@pytest.mark.parametrize(
    "field,value",
    [
        ("status", "review"),
        ("player_id", 18),
        ("lang", "ko"),
        ("revision", 2),
        ("display_name", "Different Player"),
        ("decision_kind", "generated"),
        ("generation_rule_version", "other-rule"),
        ("evidence_id", None),
    ],
)
def test_rejects_name_evidence_mismatch(engine, field, value):
    from katrain.web.kifu.player_pages import sync_player_pages

    with Session(engine) as db, db.begin():
        setattr(db.query(KifuPlayerName).one(), field, value)
    assert sync_player_pages(engine, apply=True)["pages_added"] == 0
    assert pages(engine) == [] and pages(engine, 18) == []


@pytest.mark.parametrize("field,value", [("review_status", "pending"), ("reviewer_model", None)])
def test_rejects_unapproved_evidence(engine, field, value):
    from katrain.web.kifu.player_pages import sync_player_pages

    with Session(engine) as db, db.begin():
        setattr(db.get(KifuNameResearchEvidence, 1), field, value)
    assert sync_player_pages(engine, apply=True)["pages_added"] == 0


@pytest.mark.parametrize(
    "change,rebind",
    [
        (lambda research: research.update(owner={"kind": "player", "id": 18}), True),
        (lambda research: research.update(lang="ko"), True),
        (lambda research: research.update(candidate_name="Wrong Player"), True),
        (
            lambda research: research.update(original_language_basis_url="https://www.nihonkiin.or.jp/other-player"),
            False,
        ),
    ],
)
def test_rejects_cross_player_or_unbound_payload(engine, change, rebind):
    from katrain.web.kifu.player_pages import sync_player_pages

    mutate_research(engine, change, rebind=rebind)
    assert sync_player_pages(engine, apply=True)["pages_added"] == 0


def test_does_not_collect_negative_search_unregistered_or_other_player_links(engine):
    from katrain.web.kifu.player_pages import sync_player_pages

    def add_bad_links(research):
        positive = research["source_checks"][0]
        for fields in [
            {"status": "not_found", "url": "https://en.wikipedia.org/wiki/Rejected"},
            {"url": "https://en.wikipedia.org/w/index.php?search=Go+Seigen"},
            {"url": "https://en.wikipedia.org/wiki/Special:Search/Go_Seigen"},
            {"url": "https://unregistered.example/Go_Seigen"},
            {"url": "https://en.wikipedia.org/wiki/Another_Player", "owner": {"kind": "player", "id": 18}},
            {"url": "https://en.wikipedia.org/wiki/No_Capture", "http_status": 404},
        ]:
            research["source_checks"].append({**deepcopy(positive), **fields})
        positive["rejected_leads"] = [{"url": "https://en.wikipedia.org/wiki/Rejected_Citation"}]
        positive["identity_bridges"] = [
            capture(url="https://www.goratings.org/en/players/2.html", body_excerpt="Other player")
        ]

    mutate_research(engine, add_bad_links)
    sync_player_pages(engine, apply=True)
    assert {page["url"] for page in pages(engine)} == {WIKI, OFFICIAL}


def test_invalid_manual_value_is_not_replaced(engine):
    from katrain.web.kifu.player_pages import sync_player_pages

    with Session(engine) as db, db.begin():
        db.get(KifuPlayer, 17).authoritative_pages = {"legacy_manual_value": True}
    with pytest.raises(ValueError, match="JSON array"):
        sync_player_pages(engine, apply=True)
    assert pages(engine) == {"legacy_manual_value": True}


def test_merge_preserves_manual_fields_dry_run_and_replay_do_not_write(engine):
    from katrain.web.kifu.player_pages import sync_player_pages

    manual = {
        "url": OFFICIAL,
        "source_id": "manual",
        "language": "ja",
        "role": "curated",
        "note": "Keep this",
        "evidence_ids": [99],
    }
    with Session(engine) as db, db.begin():
        db.get(KifuPlayer, 17).authoritative_pages = [manual]
    statements = []

    @event.listens_for(engine, "before_cursor_execute")
    def record(_conn, _cursor, statement, _parameters, _context, _many):
        statements.append(statement)

    preview = sync_player_pages(engine)
    assert preview["players_changed"] == 1 and preview["committed"] is False
    assert pages(engine) == [manual] and not any(sql.lstrip().upper().startswith("UPDATE") for sql in statements)
    sync_player_pages(engine, apply=True)
    updated = {page["url"]: page for page in pages(engine)}
    assert updated[OFFICIAL] == {**manual, "evidence_ids": [1, 99]}
    statements.clear()
    assert sync_player_pages(engine, apply=True)["players_changed"] == 0
    assert not any(sql.lstrip().upper().startswith("UPDATE") for sql in statements)


def test_page_updates_leave_old_catalog_and_name_preimages_unchanged(engine):
    from katrain.web.kifu.player_pages import sync_player_pages

    digest = hashlib.sha256()
    with engine.connect() as conn:
        for model in (KifuPlayer, KifuEvent, KifuPlayerAlias, KifuEventAlias, KifuRawPlayerValue, KifuRawEventValue):
            for row in conn.execute(select(model.__table__).order_by(model.id)).mappings():
                old = {
                    key: value.isoformat() if isinstance(value, datetime) else value
                    for key, value in row.items()
                    if key != "authoritative_pages"
                }
                digest.update(model.__tablename__.encode() + b":" + canonical_sha256(old).encode() + b"\n")
    old_catalog = digest.hexdigest()
    old_name = name_preimage_sha256(engine, OWNER, "en")
    assert catalog_snapshot_sha(engine) == old_catalog
    sync_player_pages(engine, apply=True)
    assert catalog_snapshot_sha(engine) == old_catalog
    assert name_preimage_sha256(engine, OWNER, "en") == old_name
    with engine.connect() as conn:
        _check_owner_manifest(conn, {"owners": [{"owner": OWNER, "preimage": {"id": 17, "canonical_name": "吴清源"}}]})


def test_cli_defaults_to_explicit_preview_and_supports_player_scope(engine, capsys):
    from scripts.kifu_player_pages import main

    assert main(["dry-run", "--database-url", str(engine.url), "--player-id", "18"]) == 0
    assert json.loads(capsys.readouterr().out)["players_changed"] == 0
    assert pages(engine) == []
    assert main(["apply", "--database-url", str(engine.url), "--player-id", "17"]) == 0
    assert json.loads(capsys.readouterr().out)["players_changed"] == 1
    assert len(pages(engine)) == 2
