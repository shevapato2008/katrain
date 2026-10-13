from pathlib import Path

import pytest

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from katrain.web.core.db import Base
from katrain.web.core.models_db import (
    KifuAlbum,
    KifuEvent,
    KifuEventAlias,
    KifuEventName,
    KifuPlayer,
    KifuPlayerAlias,
    KifuPlayerName,
    PlayerTranslationDB,
    TournamentTranslationDB,
)
from scripts.backfill_kifu_catalog import backfill_catalog
from scripts.seed_kifu_translations import load_seed


SEED = load_seed(Path(__file__).resolve().parents[2] / "docs/resource/kifu-name-seed.json")


def _db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return engine


def _album(path, black="Go Seigen", white="Kitani Minoru", event="吴清源杯"):
    return KifuAlbum(
        player_black=black,
        player_white=white,
        event=event,
        sgf_content=f"(;PB[{black}]PW[{white}])",
        source_path=path,
    )


def test_backfill_uses_only_audited_aliases_and_preserves_original_names():
    engine = _db()
    with Session(engine) as db:
        db.add_all(
            [
                _album("data/kifu-album/CWI_History_Full/a.sgf"),
                _album("data/kifu-album/19x19/b.sgf", black="吴清源", white="Mystery"),
            ]
        )
        unverified = KifuPlayer(canonical_name="Mystery Person")
        db.add(unverified)
        db.flush()
        db.add(KifuPlayerAlias(player_id=unverified.id, alias="Mystery", normalized_alias="mystery"))
        db.commit()

        report = backfill_catalog(db, SEED, dry_run=False, dedupe=False, batch_size=1)
        albums = db.query(KifuAlbum).order_by(KifuAlbum.id).all()
        assert report["identity_updates"] >= 4
        assert albums[0].black_player_id == albums[1].black_player_id
        assert albums[0].white_player_id is not None
        assert albums[1].white_player_id is None
        assert albums[0].event_id == albums[1].event_id
        assert albums[0].player_black == "Go Seigen"
        assert albums[1].player_black == "吴清源"
        assert report["identity_coverage"]["player"]["distinct_names"] == 4
        assert report["identity_coverage"]["player"]["linked"] == 3
        assert report["identity_coverage"]["event"]["linked"] == 1
        assert report["name_seed_coverage"]["player"]["languages"]["ru"]["fallback_total"] > 0

        again = backfill_catalog(db, SEED, dry_run=False, dedupe=False, batch_size=1)
        assert again["identity_updates"] == 0
        assert again["source_links_added"] == 0
        preview = backfill_catalog(db, SEED, dry_run=True, dedupe=False, batch_size=1)
        assert preview["identity_updates"] == 0
        assert preview["source_links_added"] == 0


def test_dry_run_does_not_create_entities_or_change_album():
    engine = _db()
    with Session(engine) as db:
        album = _album("data/kifu-album/CWI_Dosaku/a.sgf")
        db.add(album)
        db.commit()
        report = backfill_catalog(db, SEED, dry_run=True, batch_size=1)
        db.refresh(album)
        assert report["identity_updates"] >= 2
        assert album.black_player_id is None
        assert db.query(KifuPlayer).count() == 0


def test_conflicting_existing_identity_alias_is_left_unlinked_for_review():
    engine = _db()
    with Session(engine) as db:
        album = _album("data/kifu-album/CWI_History_Full/conflict.sgf")
        other = KifuPlayer(canonical_name="Different Person")
        db.add_all([album, other])
        db.flush()
        db.add(KifuPlayerAlias(player_id=other.id, alias="Go Seigen", normalized_alias="go seigen"))
        db.commit()

        report = backfill_catalog(db, SEED, dry_run=False, dedupe=False)
        db.refresh(album)
        assert album.black_player_id is None
        assert report["ambiguous_names"] >= 1


def test_seed_entities_persist_even_when_album_table_is_empty():
    engine = _db()
    with Session(engine) as db:
        backfill_catalog(db, SEED, dry_run=False, dedupe=False)
    with Session(engine) as db:
        assert db.query(KifuPlayer).count() == 5


def test_cwi_promotion_event_links_to_oteai_without_changing_sgf_event():
    engine = _db()
    with Session(engine) as db:
        album = _album(
            "data/kifu-album/CWI_History_Full/oteai.sgf",
            event="JapanPromotionTournament,1934,Fall",
        )
        db.add(album)
        db.commit()

        report = backfill_catalog(db, SEED, dry_run=False, dedupe=False)
        db.refresh(album)
        assert report["identity_updates"] >= 1
        assert album.event == "JapanPromotionTournament,1934,Fall"
        assert db.get(KifuEvent, album.event_id).canonical_name == "Oteai"

        again = backfill_catalog(db, SEED, dry_run=False, dedupe=False)
        assert again["identity_updates"] == 0


def test_backfill_links_player_names_with_embedded_dan_to_verified_identity():
    engine = _db()
    with Session(engine) as db:
        album = _album(
            "data/kifu-album/19x19/embedded-rank.sgf",
            black="吴清源六段",
            white="木谷实六段",
        )
        db.add(album)
        db.commit()
        backfill_catalog(db, SEED, dry_run=False, dedupe=False)
        db.refresh(album)
        assert db.get(KifuPlayer, album.black_player_id).canonical_name == "Go Seigen"
        assert db.get(KifuPlayer, album.white_player_id).canonical_name == "Kitani Minoru"
        assert album.player_black == "吴清源六段"


def test_backfill_does_not_strip_past_a_conflicting_raw_player_alias():
    engine = _db()
    with Session(engine) as db:
        album = _album("data/kifu-album/19x19/conflicting-rank.sgf", black="吴清源六段")
        other = KifuPlayer(canonical_name="Different Person")
        db.add_all([album, other])
        db.flush()
        db.add(KifuPlayerAlias(player_id=other.id, alias="吴清源六段", normalized_alias="吴清源六段"))
        db.commit()

        report = backfill_catalog(db, SEED, dry_run=False, dedupe=False)
        db.refresh(album)
        assert album.black_player_id is None
        assert report["ambiguous_names"] >= 1


def test_audited_seed_upgrades_existing_review_name_with_its_evidence():
    engine = _db()
    with Session(engine) as db:
        player = KifuPlayer(canonical_name="Go Seigen")
        db.add(player)
        db.flush()
        db.add(
            KifuPlayerName(
                player_id=player.id,
                lang="en",
                display_name="Old unverified name",
                status="review",
                reference_kind="legacy_unverified",
            )
        )
        db.commit()
        backfill_catalog(db, SEED, dry_run=False, dedupe=False)
        name = db.query(KifuPlayerName).filter_by(player_id=player.id, lang="en").one()
        assert name.display_name == SEED["entities"][0]["names"]["en"]["value"]
        assert name.status == "verified"
        assert name.reference_url == SEED["entities"][0]["names"]["en"]["source_url"]
        assert name.reference_kind == "audited_seed"
        assert name.verified_at is not None


def test_audited_seed_refuses_conflicting_verified_name():
    engine = _db()
    with Session(engine) as db:
        player = KifuPlayer(canonical_name="Go Seigen")
        db.add(player)
        db.flush()
        db.add(
            KifuPlayerName(
                player_id=player.id,
                lang="en",
                display_name="Different verified name",
                status="verified",
                reference_url="https://example.org/independent-source",
            )
        )
        db.commit()
        with pytest.raises(ValueError, match="verified name conflict"):
            backfill_catalog(db, SEED, dry_run=False, dedupe=False)
        db.rollback()
        assert (
            db.query(KifuPlayerName).filter_by(player_id=player.id, lang="en").one().display_name
            == "Different verified name"
        )


def test_legacy_translations_become_review_candidates_without_search_aliases_or_album_links():
    engine = _db()
    with Session(engine) as db:
        db.add_all(
            [
                _album(
                    "data/kifu-album/other/legacy.sgf", black="Unnamed Player", white="Nobody", event="Mysterious Cup"
                ),
                PlayerTranslationDB(
                    canonical_name="Unnamed Player",
                    en="Invented English",
                    cn="无名棋手",
                    aliases=["Unverified Alias"],
                    source="llm",
                ),
                PlayerTranslationDB(canonical_name="吴清源", ko="오청원", source="llm"),
                TournamentTranslationDB(original="Mysterious Cup", en="Mysterious Cup", cn="神秘杯", source="llm"),
                TournamentTranslationDB(original="Final", en="Final", cn="决赛", source="llm"),
            ]
        )
        db.commit()

        report = backfill_catalog(db, SEED, dry_run=False, dedupe=False)
        album = db.query(KifuAlbum).one()
        assert album.black_player_id is None
        assert album.event_id is None
        player = db.query(KifuPlayer).filter_by(canonical_name="Unnamed Player").one()
        event = db.query(KifuEvent).filter_by(canonical_name="Mysterious Cup").one()
        assert db.query(KifuPlayerName).filter_by(player_id=player.id, lang="en").one().status == "review"
        assert db.query(KifuEventName).filter_by(event_id=event.id, lang="cn").one().status == "review"
        assert db.query(KifuPlayerAlias).filter_by(player_id=player.id).count() == 0
        assert db.query(KifuEventAlias).filter_by(event_id=event.id).count() == 0
        assert db.query(KifuPlayer).filter_by(canonical_name="吴清源").count() == 0
        go_player = db.query(KifuPlayer).filter_by(canonical_name="Go Seigen").one()
        assert db.query(KifuPlayerName).filter_by(player_id=go_player.id, lang="ko").one().status == "review"
        assert db.query(KifuEvent).filter_by(canonical_name="Final").count() == 0
        assert report["legacy_review_names_added"] >= 4
        assert report["legacy_aliases_pending_review"] == 1
        assert report["name_seed_coverage"]["player"]["languages"]["en"]["review"] == 1
