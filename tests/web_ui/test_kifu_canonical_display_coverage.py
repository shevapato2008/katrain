"""Publication validates approved canonical display behind a verified source alias."""

from copy import deepcopy
from hashlib import sha256

import pytest
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from katrain.kifu_ingest import catalog
from katrain.web.core.models_db import (
    KifuAlbum,
    KifuAlbumSource,
    KifuDedupBatch,
    KifuNameResearchEvidence,
    KifuPlayerName,
    KifuRawPlayerName,
)
from katrain.web.kifu import catalog_standardization as dedup
from katrain.web.kifu.identity import strict_slot_approvals
from tests.web_ui.test_kifu_catalog_standardization import sgf
from tests.web_ui.test_kifu_incremental_catalog import (
    LANGUAGES,
    decision,
    make_engine,
    manifest,
    publish,
    state,
)


def game(item, *, day="2026-02-01", linked_white=False):
    value = manifest(str(item))
    body = (
        sgf(comment=str(item))
        .replace("PB[Black]", "PB[Black Alias]")
        .replace("PW[White]", "PW[White Alias]")
        .replace("DT[1989-01-17]", f"DT[{day}]EV[Summer Cup]")
    )
    value["games"][0].update(
        sgf_content=body,
        sgf_sha256=sha256(body.encode()).hexdigest(),
        raw_sha256=sha256(body.encode()).hexdigest(),
        metadata={
            "player_black": "Black Alias",
            "player_white": "White Alias",
            "event": "Summer Cup",
            "date_played": day,
        },
        identities={"black": "auto", "white": "auto" if linked_white else None},
    )
    return value


@pytest.fixture
def reviewed_alias(tmp_path):
    engine = make_engine(tmp_path / "canonical-display.db")
    originals, receipts = [], []
    # Both originals predate the reviewed display dedup. Their explicit unlinked
    # white slots receive a real signed finite name scope through native publish.
    for item in (99171, 99172):
        value = game(item)
        approved = decision(value, "raw_player", "White Alias", slot="white")
        with engine.connect() as conn:
            approved["displays"] = dict(
                conn.execute(
                    select(KifuPlayerName.lang, KifuPlayerName.display_name).where(KifuPlayerName.player_id == 18)
                ).all()
            )
        approved["review"]["content_sha256"] = catalog.review_content_sha256(approved)
        value["decisions"] = [approved]
        receipts.append(publish(engine, value))
        originals.append(value)
    canonical, alias = [receipt["games"][0]["album_id"] for receipt in receipts]
    with engine.begin() as conn:
        reviewed = dedup.prepare_dedup_manifest(conn)
        assert reviewed["groups"][0]["canonical_album_id"] == canonical
        assert reviewed["groups"][0]["duplicate_album_ids"] == [alias]
        dedup.apply_dedup_manifest(conn, reviewed, expected_sha256=dedup.dedup_manifest_sha256(reviewed))
        assert dedup.verified_display_duplicate(conn, alias)["canonical_album_id"] == canonical
    yield engine, canonical, alias, originals, receipts
    engine.dispose()


def test_native_publish_checks_canonical_from_prior_frozen_raw_scope(reviewed_alias):
    engine, canonical, alias, originals, receipts = reviewed_alias
    with Session(engine) as db:
        albums = db.query(KifuAlbum).filter(KifuAlbum.id.in_([canonical, alias])).all()
        for lang in LANGUAGES:
            slots = strict_slot_approvals(db, albums, lang)
            assert all(slots[canonical])
            assert slots[alias][1] is None
    with engine.connect() as conn:
        prior = catalog._existing_player_proofs(conn, {"White Alias"})
        assert any(row["album_id"] == alias for row in prior[("White Alias", "cn")]["scope"]["content"]["slots"])
        evidence = conn.execute(select(KifuNameResearchEvidence.__table__)).mappings().all()
        sources = conn.execute(select(KifuAlbumSource.__table__)).mappings().all()
        bodies = dict(conn.execute(select(KifuAlbum.id, KifuAlbum.sgf_content)).all())

    frozen = game(99173, day="2026-02-02", linked_white=True)
    expected_manifest = deepcopy(frozen)
    receipt = publish(engine, frozen)
    assert frozen == expected_manifest
    assert publish(engine, frozen) == receipt
    for original, original_receipt in zip(originals, receipts):
        assert publish(engine, original) == original_receipt
    with engine.connect() as conn:
        current_evidence = conn.execute(select(KifuNameResearchEvidence.__table__)).mappings().all()
        current_sources = conn.execute(select(KifuAlbumSource.__table__)).mappings().all()
        assert all(row in current_evidence for row in evidence)
        assert all(row in current_sources for row in sources)
        assert dict(conn.execute(select(KifuAlbum.id, KifuAlbum.sgf_content)).all()).items() >= bodies.items()
        assert conn.scalar(select(KifuAlbum.duplicate_of_id).where(KifuAlbum.id == alias)) == canonical


def test_coverage_deduplicates_actual_canonical_ids(reviewed_alias, monkeypatch):
    engine, canonical, alias, _, _ = reviewed_alias
    checked = []
    original = catalog.strict_slot_approvals

    def inspect_ids(db, albums, lang, **kwargs):
        checked.append((lang, [album.id for album in albums]))
        return original(db, albums, lang, **kwargs)

    monkeypatch.setattr(catalog, "strict_slot_approvals", inspect_ids)
    with engine.connect() as conn:
        catalog._coverage(conn, {canonical, alias})
    assert checked == [(lang, [canonical]) for lang in LANGUAGES]


def test_true_missing_canonical_language_still_rejects_atomic_publish(reviewed_alias):
    engine, canonical, _, _, _ = reviewed_alias
    with engine.begin() as conn:
        conn.execute(KifuRawPlayerName.__table__.delete().where(KifuRawPlayerName.lang == "ko"))
    before = state(engine)
    with pytest.raises(catalog.PublicationError, match=rf"coverage missing for ko: \[{canonical}\]"):
        publish(engine, game(99173, day="2026-02-02", linked_white=True))
    assert state(engine) == before


@pytest.mark.parametrize("damage", ["journal", "cycle", "nonpublic"])
def test_unverified_alias_does_not_grant_canonical_coverage_or_source_authority(reviewed_alias, monkeypatch, damage):
    engine, canonical, alias, _, _ = reviewed_alias
    with engine.begin() as conn:
        if damage == "journal":
            row = conn.execute(select(KifuDedupBatch.__table__)).mappings().one()
            summary = deepcopy(row["summary"])
            summary["manifest_sha256"] = "0" * 64
            conn.execute(update(KifuDedupBatch).where(KifuDedupBatch.id == row["id"]).values(summary=summary))
        elif damage == "cycle":
            conn.execute(update(KifuAlbum).where(KifuAlbum.id == canonical).values(duplicate_of_id=alias))
        else:
            conn.execute(update(KifuAlbum).where(KifuAlbum.id == canonical).values(list_hidden_reason="excluded"))
    checked = []
    original = catalog.strict_slot_approvals

    def inspect_ids(db, albums, lang, **kwargs):
        checked.extend(album.id for album in albums)
        return original(db, albums, lang, **kwargs)

    monkeypatch.setattr(catalog, "strict_slot_approvals", inspect_ids)
    before = state(engine)
    with engine.connect() as conn:
        with pytest.raises(ValueError):
            dedup.verified_display_duplicate(conn, alias)
        # Existing behavior ignores an unproved hidden alias; it never promotes
        # that alias's claimed target into the public display approval set.
        catalog._coverage(conn, {alias})
        with pytest.raises(ValueError):
            catalog._require_source_publication(conn, {alias})
    assert checked == []
    assert state(engine) == before
