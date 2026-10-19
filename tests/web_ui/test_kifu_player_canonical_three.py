import copy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from katrain.web.kifu import player_canonical_three as three
from katrain.web.core.db import Base
from katrain.web.core.models_db import KifuAlbum, KifuEvent, KifuPlayer, KifuPlayerAlias, KifuPlayerName


REVIEW_DIR = Path(__file__).resolve().parents[2] / "docs/resource"


@pytest.fixture(params=("test", "prod"))
def review(request):
    env = request.param
    path = REVIEW_DIR / f"kifu-player-exact-canonical-three-frozen-review-{env}-2026-10-04.json"
    return env, json.loads(path.read_text())


def test_frozen_members_exactly_cover_reviewed_null_scope(review):
    environment, frozen = review
    albums = three.validate_review(frozen, environment)
    assert len(albums) == 2105
    assert len(frozen["candidate_slots"]) == 1529
    assert len(frozen["held_slots"]) == 580


def test_capture_allows_only_known_intervening_changes(monkeypatch, review):
    environment, frozen = review
    albums = {r["id"]: {k: v for k, v in r.items() if k != "album_row_sha256"}
              for r in frozen["live_album_preimage"]}
    deltas = three.approved_intervening_deltas(frozen, environment, three.validate_review(frozen, environment))
    assert len(deltas) == 83
    assert {album_id for album_id, column in deltas if column == "event_id" and album_id in three.NEXT_EVENT_ALBUMS} == three.NEXT_EVENT_ALBUMS
    assert sum(hold["album_id"] in three.NEXT_EVENT_ALBUMS for hold in frozen["held_slots"]) == 7
    for (album_id, column), (old, new) in deltas.items():
        albums[album_id][column] = new
    monkeypatch.setattr(three, "_albums", lambda db, review: albums)
    monkeypatch.setattr(three, "_ancillary", lambda db, review: {
        key: sorted(review[key], key=lambda row: row["id"]) for key in three.TABLES})
    monkeypatch.setattr(three, "_collision_guard", lambda db, review: None)
    monkeypatch.setattr(three, "_event_catalog_guard", lambda db: None)
    monkeypatch.setattr(three, "_next15_catalog_guard", lambda db, environment: None)
    class FakeDB:
        bind = SimpleNamespace(dialect=SimpleNamespace(name="sqlite"))
        def scalars(self, query):
            return [SimpleNamespace(**r) for r in frozen["catalog_preimage"]]
        def execute(self, query):
            return SimpleNamespace(all=lambda: [])
    db = FakeDB()
    plan = three._capture(db, frozen, environment, "pinned")
    assert plan["counts"] == {"candidate_slots": 1529, "held_slots": 580}
    mixed_id, mixed_column = next(key for key in deltas if key[1] != "event_id")
    changed = copy.deepcopy(albums)
    changed[mixed_id][mixed_column] = 999999
    monkeypatch.setattr(three, "_albums", lambda db, review: changed)
    with pytest.raises(ValueError, match="intervening approved postimage"):
        three._capture(db, frozen, environment, "pinned")
    next15_id, next15_column = next(key for key in deltas if key[1] != "event_id" and
                                     key[0] not in three.MIXED11_OPPONENT_ALBUMS)
    changed = copy.deepcopy(albums)
    changed[next15_id][next15_column] = 999999
    monkeypatch.setattr(three, "_albums", lambda db, review: changed)
    with pytest.raises(ValueError, match="intervening approved postimage"):
        three._capture(db, frozen, environment, "pinned")
    next_event_id = next(i for i in three.NEXT_EVENT_ALBUMS)
    changed = copy.deepcopy(albums)
    changed[next_event_id]["event_id"] = None
    monkeypatch.setattr(three, "_albums", lambda db, review: changed)
    with pytest.raises(ValueError, match="intervening approved postimage"):
        three._capture(db, frozen, environment, "pinned")
    changed = copy.deepcopy(albums)
    changed[next_event_id]["event_id"] = 888888
    monkeypatch.setattr(three, "_albums", lambda db, review: changed)
    with pytest.raises(ValueError, match="intervening approved postimage"):
        three._capture(db, frozen, environment, "pinned")
    event_id, event_column = next(key for key in deltas if key[1] == "event_id")
    changed = copy.deepcopy(albums)
    changed[event_id][event_column] = 888888
    monkeypatch.setattr(three, "_albums", lambda db, review: changed)
    with pytest.raises(ValueError, match="intervening approved postimage"):
        three._capture(db, frozen, environment, "pinned")
    changed = copy.deepcopy(albums)
    changed[mixed_id]["sgf_sha256"] = "0" * 64
    monkeypatch.setattr(three, "_albums", lambda db, review: changed)
    with pytest.raises(ValueError, match="frozen album preimage"):
        three._capture(db, frozen, environment, "pinned")
    next15_hold = next(hold for hold in frozen["held_slots"] if hold["album_id"] == 55993)
    changed = copy.deepcopy(albums)
    changed[next15_hold["album_id"]][f"{next15_hold['side']}_player_id"] = frozen["targets"][next15_hold["raw_name"]]
    monkeypatch.setattr(three, "_albums", lambda db, review: changed)
    with pytest.raises(ValueError, match="frozen album preimage"):
        three._capture(db, frozen, environment, "pinned")
    changed = copy.deepcopy(albums)
    event_hold = next(hold for hold in frozen["held_slots"] if hold["album_id"] in three.NEXT_EVENT_ALBUMS)
    changed[event_hold["album_id"]][f"{event_hold['side']}_player_id"] = frozen["targets"][event_hold["raw_name"]]
    monkeypatch.setattr(three, "_albums", lambda db, review: changed)
    with pytest.raises(ValueError, match="frozen album preimage"):
        three._capture(db, frozen, environment, "pinned")
    changed = copy.deepcopy(albums)
    held_id = frozen["held_slots"][0]["album_id"]
    held_side = frozen["held_slots"][0]["side"]
    changed[held_id][f"{held_side}_player_id"] = frozen["targets"][frozen["held_slots"][0]["raw_name"]]
    monkeypatch.setattr(three, "_albums", lambda db, review: changed)
    with pytest.raises(ValueError, match="frozen album preimage"):
        three._capture(db, frozen, environment, "pinned")


def test_member_or_hold_mutation_rejected(review):
    environment, frozen = review
    changed = copy.deepcopy(frozen)
    changed["candidate_slots"][0][0] += 1
    with pytest.raises(ValueError, match="member hash"):
        three.validate_review(changed, environment)
    changed = copy.deepcopy(frozen)
    changed["held_slots"].pop()
    with pytest.raises(ValueError, match="counts"):
        three.validate_review(changed, environment)


def test_album_source_timestamp_padding_only_is_equivalent():
    frozen = [{"id": 1, "album_id": 7, "source_id": 1, "origin_path": "7.sgf",
               "match_method": "source_path", "created_at": "2026-09-30T19:51:48.80822+00:00"}]
    live = [{**frozen[0], "created_at": "2026-09-30T19:51:48.808220+00:00"}]
    assert three._ancillary_preimage_equal("album_sources_preimage", live, frozen)
    assert three._parse_created_at("2026-09-30T19:51:59.38943+00:00") == three._parse_created_at(
        "2026-09-30T19:51:59.389430+00:00")
    assert three._parse_created_at("2026-09-30T19:51:59.38943+00:00") != three._parse_created_at(
        "2026-09-30T19:51:59.389431+00:00")
    assert not three._ancillary_preimage_equal("catalog_preimage", live, frozen)
    changed_time = [{**live[0], "created_at": "2026-09-30T19:51:48.808221+00:00"}]
    assert not three._ancillary_preimage_equal("album_sources_preimage", changed_time, frozen)
    changed_source = [{**live[0], "origin_path": "different.sgf"}]
    assert not three._ancillary_preimage_equal("album_sources_preimage", changed_source, frozen)


def test_next_event_plan_checks_environment_specific_opponent_fk(review):
    environment, frozen = review
    original = copy.deepcopy(three.validate_review(frozen, environment))
    original[36687]["white_player_id"] = 999999
    with pytest.raises(ValueError, match="next event exact album preimage"):
        three.approved_intervening_deltas(frozen, environment, original)


def test_next15_plan_checks_source_and_sgf_preimage(review):
    environment, frozen = review
    original = copy.deepcopy(three.validate_review(frozen, environment))
    original[49152]["source_path"] = "changed.sgf"
    with pytest.raises(ValueError, match="next15 exact opponent preimage"):
        three.approved_intervening_deltas(frozen, environment, original)
    original = copy.deepcopy(three.validate_review(frozen, environment))
    original[49152]["sgf_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="next15 exact opponent preimage"):
        three.approved_intervening_deltas(frozen, environment, original)


def test_all_three_traditional_names_share_their_simplified_collision_key():
    for traditional, simplified in (("趙善津", "赵善津"), ("工藤紀夫", "工藤纪夫"),
                                    ("周鶴洋", "周鹤洋"), ("週鶴洋", "周鹤洋")):
        assert three._identity_key(traditional) == three._identity_key(simplified)


@pytest.mark.parametrize("kind", ("canonical", "alias", "name", "zhou_canonical"))
def test_traditional_spelling_on_other_owner_is_collision(tmp_path, kind):
    engine = create_engine(f"sqlite:///{tmp_path/'collision.db'}")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add_all([KifuPlayer(id=1, canonical_name="赵善津"), KifuPlayer(id=2, canonical_name="其他")])
        if kind == "canonical":
            db.add(KifuPlayer(id=3, canonical_name="趙善津"))
        elif kind == "zhou_canonical":
            db.add(KifuPlayer(id=3, canonical_name="週鶴洋"))
        elif kind == "alias":
            db.add(KifuPlayerAlias(player_id=2, alias="趙善津", normalized_alias="趙善津"))
        else:
            db.add(KifuPlayerName(player_id=2, lang="tw", display_name="趙善津", status="review"))
        db.commit()
    with Session(engine) as db, pytest.raises(ValueError, match="normalized .* collision"):
        three._collision_guard(db, {"targets": {"赵善津": 1, "工藤纪夫": 3, "周鹤洋": 4}})
    engine.dispose()


def test_intervening_event_catalog_target_is_exact(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path/'event-catalog.db'}")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add(KifuEvent(id=75, canonical_name="别的赛事"))
        db.commit()
    with Session(engine) as db, pytest.raises(ValueError, match="event target catalog"):
        three._event_catalog_guard(db)
    with Session(engine) as db:
        db.get(KifuEvent, 75).canonical_name = "中日围棋对抗赛"
        db.commit()
    with Session(engine) as db:
        three._event_catalog_guard(db)
    engine.dispose()


def test_next15_catalog_target_binding_is_exact(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path/'next15-catalog.db'}")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add(KifuPlayer(id=12553, canonical_name="错误周俊勋"))
        db.commit()
    with Session(engine) as db, pytest.raises(ValueError, match="next15 target catalog"):
        three._next15_catalog_guard(db, "test")
    engine.dispose()


def test_dry_rolls_back_apply_commits_and_cas_rejects_stale_slot(monkeypatch, tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path/'transaction.db'}")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add(KifuPlayer(id=42, canonical_name="周鹤洋"))
        db.add(KifuAlbum(id=7, player_black="周鹤洋", player_white="对手", date_played="2020-01-01",
                         source_path="7.sgf", sgf_content="(;PB[周鹤洋]PW[对手])"))
        db.commit()
    review = {"candidate_slots": [[7, "black", "周鹤洋", "2020-01-01", None, 42]],
              "live_album_preimage": [{"id": 7, "player_black": "周鹤洋", "player_white": "对手",
                                       "date_played": "2020-01-01", "black_player_id": None,
                                       "white_player_id": None, "sgf_sha256": "unused"}]}
    monkeypatch.setattr(three, "_ancillary", lambda db, review: {})
    monkeypatch.setattr(three, "_collision_guard", lambda db, review: None)
    monkeypatch.setattr(three, "_event_catalog_guard", lambda db: None)
    monkeypatch.setattr(three, "_next15_catalog_guard", lambda db, environment: None)
    with Session(engine) as db:
        before = three._albums(db, review)[7]
    plan = {"format": "kifu-player-canonical-three-exact-plan-v1", "environment": "test", "albums": [before],
            "ancillary": {}, "counts": {"candidate_slots": 1, "held_slots": 0}}
    monkeypatch.setattr(three, "_capture", lambda db, review, environment, sha: plan)
    assert three.run(engine, review, "test", "pin", plan)["committed"] is False
    with Session(engine) as db:
        assert db.get(KifuAlbum, 7).black_player_id is None
    assert three.run(engine, review, "test", "pin", plan, apply=True,
                     plan_sha256="approved", approved_plan_sha256="approved")["committed"] is True
    with Session(engine) as db:
        assert db.get(KifuAlbum, 7).black_player_id == 42
        db.get(KifuAlbum, 7).black_player_id = 99
        db.commit()
    with pytest.raises(ValueError, match="compare-and-swap failed"):
        three.run(engine, review, "test", "pin", plan)
    with Session(engine) as db:
        assert db.get(KifuAlbum, 7).black_player_id == 99
    engine.dispose()
