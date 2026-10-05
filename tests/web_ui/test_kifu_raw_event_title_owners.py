"""Finite raw owner approvals change review status without changing games."""

from copy import deepcopy

import pytest
from sqlalchemy import select

from katrain.web.core.models_db import KifuAlbum, KifuRawEventValue
from katrain.web.core.models_db import KifuAlbumSource, KifuEvent, KifuSource
from katrain.web.kifu.name_batch import BatchError, _image, undo_batch
from katrain.web.kifu.name_batch import _affected_albums, _check_raw_owner, _team_raw_scope
from katrain.web.kifu.name_candidates import canonical_sha256
from katrain.web.kifu.raw_event_translation import GEOGRAPHIC39_RAW_VALUES
from scripts.kifu_raw_event_title_owners import RAW_VALUES, apply_plan, inspect_plan, prepare_plan
from tests.web_ui.test_kifu_name_batch import engine  # noqa: F401
from tests.web_ui.test_kifu_name_candidates import registry


TEAM_ALL_IDS = tuple(map(int, """
    36589 36611 36612 36663 36668 36677 36678 36684 36708 36709 36710 36714 36715 36716 36731 36732
    36733 36734 36745 36746 36747 36748 36753 36754 40302 40303 40304 40305 40306 40312 40313 40314
    40315 40316 40317 40334 40335 40337 40338 40339 40346 40347 40348 40349 40350 40351 40352 40353
    40354 40363 40364 40365 40366 40367 40368 40369 41993 42002 42007 42407 42434 42441 42454 42457
    42476 42481 42482 43200 43204 46945 56988 56990 56995 57008 57010 57733 58190 58192 58193 58304
    58305 58321 58322 58508 58514 59044 59062 59083 59085 59087 59088 59090 59101 59105 60015 60017
    60143 60150 60158 60162 60210 60276 60288 60306 60320 60406 60413 60427 60433 60445 60451 61503
    61508 61708 61753 61798 62076 62103 62105 62113 62114 65293 66378 66387 68471 68473 68475 69860
    70308 70720 71946 75865 76551 76691 76696 76711 76713 76721 76808 77213 77368 77379 77783 77785
    78257 78259 78260 78267 83000 83045 83080 83081 83088 89940 89941 89947 90989 90990 90994 94974
    97078 97099 97100 97101 97106 100392 100393 100915 100916 100917 103375 103379 103658 104091 104092 104239
    105445 105446 105621 105622 105636 105637 105638 105640 105641 105643 105644 105748 105756 106155 106157 106158
    106161 106163 106166 106168 106170 106171 106172 106174 106646 106648 106649 106650 106651 106738 106739 111950
    111951 111996 112005 112006 112007 112009 112010 112014 112055 112199 112201 112202 112213 112714 112716 112753
    112760 112764 112766 112771 112780 112782 114910 114915 114916 115488 115489 115490 115491 115500 115501 115502
    115506 115508 115510 115513 116012 116447 116448 116450 117603 117958 118974 123871 125707 125897 125989 126809
    126812 126813 126816 130696 130710 130726 130727 130741 130799 130800 130808 130815 130817 130818 131296 131297
    133500 133501 133502 133505 133511 134314 134316 134319 137115 137116 137121 137127 137128 137130 137131 137267
    137268 137342 137624 137626 137753 137767 137768 137789 138139 138148 138150 139165 139202 139882 139944 139951
    139952 139953 141092 141104 142877 144471 144474 144482 144483 144955 145385 145552 145773 146611 146615 146855
    146856 146862 146863 146889
""".split()))
TEAM_EXCLUDED_IDS = frozenset(map(int, """
    36663 36668 36708 36709 36710 40334 40335 42407 42481 42482 46945 56988 60017 69860 76808 77213
    83045 83088 90990 94974 100915 100916 100917 112014 118974 126816 130741 137116 137626 139944
""".split()))


def owner_fixture(engine):
    records, members = [], []
    next_album = 1000
    with engine.begin() as conn:
        for index, raw in enumerate(RAW_VALUES):
            owner_id = 100 + index
            count = 265 if index == 0 else 206 if index == 7 else 1
            ids = list(range(next_album, next_album + count))
            next_album += count
            conn.execute(KifuRawEventValue.__table__.insert().values(
                id=owner_id, raw_value=raw, category="unclassified_pending", parser_version="original-parser",
                parsed_data={"raw": raw}, review_status="pending"))
            conn.execute(KifuAlbum.__table__.insert(), [
                {"id": album_id, "player_black": "A", "player_white": "B", "event": raw,
                 "sgf_content": f"(;EV[{raw}])", "source_path": f"{album_id}.sgf", "black_rank": "1d"}
                for album_id in ids
            ])
            before = _image(conn, KifuRawEventValue.__table__, owner_id)
            records.append({"raw_value": raw, "owners": {"TEST": {"raw_event_id": owner_id,
                                                                       "preimage": before}}})
            members.append({"raw_value": raw, "album_ids": ids})
    return {"records": records, "member_manifest": {"TEST": {"members": members}}}


def test_first24_owner_plan_is_cas_scoped_and_undoable(engine):
    manifest = owner_fixture(engine)
    plan = prepare_plan(engine, manifest, "TEST", registry(), producer_id="producer-1",
                        producer_model="gpt-6-sol", reviewer_id="reviewer-2", reviewer_model="gpt-6-astra",
                        review_conclusion="Reviewed each literal raw title without event identity claims")
    assert "profile" not in plan
    with engine.connect() as conn:
        assert inspect_plan(conn, plan, registry(), canonical_sha256(manifest))["albums"] == 493
    tampered = deepcopy(plan)
    tampered["changes"][0]["after"]["category"] = "formal_event_candidate"
    with engine.connect() as conn, pytest.raises(BatchError):
        inspect_plan(conn, tampered, registry(), canonical_sha256(manifest))
    self_reviewed = deepcopy(plan)
    self_reviewed["reviewer_id"] = self_reviewed["producer_id"]
    with engine.connect() as conn, pytest.raises(BatchError):
        inspect_plan(conn, self_reviewed, registry(), canonical_sha256(manifest))
    with engine.begin() as conn:
        conn.execute(KifuAlbum.__table__.update().where(KifuAlbum.id == 1000).values(black_rank="2d"))
    with engine.connect() as conn, pytest.raises(BatchError):
        inspect_plan(conn, plan, registry(), canonical_sha256(manifest))
    with engine.begin() as conn:
        conn.execute(KifuAlbum.__table__.update().where(KifuAlbum.id == 1000).values(black_rank="1d"))
    applied = apply_plan(engine, plan, registry(), canonical_sha256(manifest), canonical_sha256(plan))
    with engine.connect() as conn:
        assert conn.scalar(select(KifuRawEventValue.review_status).where(KifuRawEventValue.id == 100)) == "approved"
        assert conn.scalar(select(KifuAlbum.event_id).where(KifuAlbum.id == 1000)) is None
    undo_batch(engine, applied["batch_id"])
    with engine.connect() as conn:
        assert conn.scalar(select(KifuRawEventValue.review_status).where(KifuRawEventValue.id == 100)) == "pending"


AGON_RAWS = (
    "第11届阿含桐山杯本选第1轮", "第11届阿含桐山杯本选第2轮", "第11届阿含桐山杯本选第3轮",
    "第11届阿含桐山杯本选第4轮", "第11届阿含桐山杯本选第一轮", "第12届阿含桐山杯本选第一轮",
    "第12届阿含桐山杯本选第二轮", "第16届阿含桐山杯本选第2轮", "第16届阿含桐山杯本选第3轮",
    "第十届阿含桐山杯本选第一轮",
)
CMB_RAWS = ("第9届招商银行杯第3轮", "第9届招商银行杯第一轮")
LEAGUE20 = (
    ("2004年围棋甲级联赛第18轮", 19),
    ("2004年围棋甲级联赛第14轮", 15),
    ("2004年围棋甲级联赛第20轮", 15),
    ("2004年围棋甲级联赛第11轮", 14),
    ("2004年围棋甲级联赛第16轮", 14),
    ("2004年围棋甲级联赛第二轮", 13),
    ("2004年围棋甲级联赛第22轮", 12),
    ("2004年围棋甲级联赛第九轮", 11),
    ("2004年围棋甲级联赛第七轮", 10),
    ("2004年围棋甲级联赛第六轮", 10),
    ("2004年围棋甲级联赛第十轮", 10),
    ("2004年围棋甲级联赛第15轮", 9),
    ("2004年围棋甲级联赛第三轮", 9),
    ("2004年围棋甲级联赛第13轮", 8),
    ("2004年围棋甲级联赛第17轮", 8),
    ("2004年围棋甲级联赛第19轮", 8),
    ("2004年围棋甲级联赛第21轮", 8),
    ("2004年围棋甲级联赛第四轮", 8),
    ("2004年围棋甲级联赛第12轮", 7),
    ("2004年围棋甲级联赛第一轮", 6),
)
GENERIC49 = (
    ("10-game match", 245),
    ("2000年全国围棋个人赛", 15),
    ("全国围棋个人赛", 10),
    ("1981年全国围棋个人赛", 9),
    ("1984年全国围棋个人赛", 9),
    ("2001年全国围棋个人赛第三轮", 9),
    ("2001年全国围棋个人赛第五轮", 9),
    ("1980年全国围棋个人赛", 8),
    ("2001年全国围棋个人赛第七轮", 8),
    ("1974年全国围棋个人赛", 7),
    ("1978年全国围棋个人赛", 7),
    ("2001年全国围棋个人赛第一轮", 7),
    ("2001年全国围棋个人赛第九轮", 7),
    ("2001年全国围棋个人赛第六轮", 7),
    ("1982年全国围棋个人赛", 6),
    ("2001年全国围棋个人赛第二轮", 6),
    ("2001年全国围棋个人赛第八轮", 6),
    ("1977年全国围棋个人赛", 5),
    ("1983年全国围棋个人赛", 4),
    ("2001年全国围棋个人赛", 4),
    ("2001年全国围棋个人赛第四轮", 4),
    ("2002年全国围棋个人赛第一轮", 3),
    ("2006年全国围棋个人赛第四轮", 3),
    ("2002年全国围棋个人赛第六轮", 2),
    ("2004年全国围棋个人赛第一轮", 2),
    ("2004年全国围棋个人赛第七轮", 2),
    ("2004年全国围棋个人赛第九轮", 2),
    ("2004年全国围棋个人赛第二轮", 2),
    ("2004年全国围棋个人赛第六轮", 2),
    ("2006年全国围棋个人赛第七轮", 2),
    ("2006年全国围棋个人赛第九轮", 2),
    ("2006年全国围棋个人赛第八轮", 2),
    ("2001年全国围棋个人赛第十轮", 1),
    ("2002年全国围棋个人赛第九轮", 1),
    ("2002年全国围棋个人赛第五轮", 1),
    ("2002年全国围棋个人赛第四轮", 1),
    ("2004年全国围棋个人赛第三轮", 1),
    ("2004年全国围棋个人赛第五轮", 1),
    ("2004年全国围棋个人赛第八轮", 1),
    ("2004年全国围棋个人赛第四轮", 1),
    ("2005年全国围棋个人赛第八轮", 1),
    ("2006年全国围棋个人赛第一轮", 1),
    ("2006年全国围棋个人赛第三轮", 1),
    ("2006年全国围棋个人赛第二轮", 1),
    ("2006年全国围棋个人赛第五轮", 1),
    ("2006年全国围棋个人赛第六轮", 1),
    ("全国围棋个人赛第1轮", 1),
    ("升段赛", 125),
    ("2002年升段赛", 1),
)
GEOGRAPHIC39 = (
    ("2001年中国围棋段位赛", 69),
    ("2007年中国围棋段位赛第一轮", 35),
    ("2007年中国围棋段位赛第12轮", 32),
    ("2007年中国围棋段位赛第六轮", 32),
    ("2005年中国围棋段位赛", 26),
    ("2013年中国围棋段位赛", 19),
    ("2002年中国围棋段位赛", 12),
    ("2007年中国围棋段位赛第二轮", 10),
    ("2007年中国围棋段位赛第九轮", 5),
    ("2004年中国围棋段位赛", 4),
    ("2007年中国围棋段位赛第11轮", 4),
    ("2007年中国围棋段位赛第七轮", 4),
    ("2007年中国围棋段位赛第三轮", 3),
    ("2007年中国围棋段位赛第五轮", 3),
    ("2007年中国围棋段位赛第八轮", 3),
    ("2007年中国围棋段位赛第十轮", 3),
    ("2007年中国围棋段位赛第四轮", 2),
    ("2008年中国围棋段位赛第12轮", 2),
    ("2008年中国围棋段位赛第三轮", 2),
    ("2008年中国围棋段位赛第五轮", 2),
    ("2008年中国围棋段位赛第八轮", 2),
    ("2008年中国围棋段位赛第六轮", 2),
    ("2008年中国围棋段位赛第四轮", 2),
    ("2004年中国围棋段位赛第10轮", 1),
    ("2004年中国围棋段位赛第11轮", 1),
    ("2004年中国围棋段位赛第12轮", 1),
    ("2004年中国围棋段位赛第4轮", 1),
    ("2004年中国围棋段位赛第5轮", 1),
    ("2004年中国围棋段位赛第6轮", 1),
    ("2004年中国围棋段位赛第7轮", 1),
    ("2004年中国围棋段位赛第8轮", 1),
    ("2004年中国围棋段位赛第9轮", 1),
    ("2007年中国围棋段位赛第10轮", 1),
    ("2008年中国围棋段位赛第11轮", 1),
    ("2008年中国围棋段位赛第一轮", 1),
    ("2008年中国围棋段位赛第七轮", 1),
    ("2008年中国围棋段位赛第九轮", 1),
    ("2008年中国围棋段位赛第二轮", 1),
    ("2008年中国围棋段位赛第十轮", 1),
)


TOKYO11 = (
    ("10th Tokyo Shinbun Cup", 57), ("7th Tokyo Shinbun Cup", 40), ("9th Tokyo Shinbun Cup", 20),
    ("11th Tokyo Shinbun Cup", 17), ("5th Tokyo Shinbun Cup", 9), ("8th Tokyo Shinbun Cup", 9),
    ("6th Tokyo Shinbun Cup", 8), ("3rd Tokyo Shinbun Cup", 7), ("1st Tokyo Shinbun Cup", 4),
    ("2nd Tokyo Shinbun Cup", 2), ("4th Tokyo Shinbun Cup", 2),
)


def finite_fixture(engine, raws, counts):
    records, members = [], []
    next_album = 2000
    with engine.begin() as conn:
        for index, (raw, count) in enumerate(zip(raws, counts)):
            owner_id = 200 + index
            ids = list(range(next_album, next_album + count))
            next_album += count
            conn.execute(KifuRawEventValue.__table__.insert().values(
                id=owner_id, raw_value=raw, category="unclassified_pending", parser_version="original-parser",
                parsed_data={"raw": raw}, review_status="pending"))
            conn.execute(KifuAlbum.__table__.insert(), [
                {"id": album_id, "player_black": "A", "player_white": "B", "event": raw,
                 "sgf_content": f"(;EV[{raw}])", "source_path": f"{album_id}.sgf"}
                for album_id in ids
            ])
            before = _image(conn, KifuRawEventValue.__table__, owner_id)
            records.append({"raw_value": raw, "owners": {"TEST": {"raw_event_id": owner_id, "preimage": before}}})
            members.append({"raw_value": raw, "album_ids": ids})
    return {"records": records, "member_manifest": {"TEST": {"members": members}}}


@pytest.mark.parametrize("profile,raws,counts,total", [
    ("agon10", AGON_RAWS, (49, 24, 14, 7, 5, 60, 25, 1, 1, 19), 205),
    ("cmb2", CMB_RAWS, (1, 1), 2),
    ("generic49", tuple(raw for raw, _ in GENERIC49), tuple(count for _, count in GENERIC49), 557),
    ("geographic39", tuple(raw for raw, _ in GEOGRAPHIC39), tuple(count for _, count in GEOGRAPHIC39), 294),
    ("league20", tuple(raw for raw, _ in LEAGUE20), tuple(count for _, count in LEAGUE20), 214),
    ("castle1", ("Castle Game",), (539,), 539),
    ("tokyo11", tuple(raw for raw, _ in TOKYO11), tuple(count for _, count in TOKYO11), 175),
])
def test_next_finite_profiles_pin_raws_and_game_totals(engine, profile, raws, counts, total):
    if profile == "generic49":
        assert "团体赛" not in raws
    if profile == "geographic39":
        assert set(raws) == GEOGRAPHIC39_RAW_VALUES
    manifest = finite_fixture(engine, raws, counts)
    kwargs = {"producer_id": "producer-1", "producer_model": "gpt-6-sol",
              "reviewer_id": "reviewer-2", "reviewer_model": "gpt-6-astra",
              "review_conclusion": "Reviewed exact literal raw titles"}
    with pytest.raises(BatchError):
        prepare_plan(engine, manifest, "TEST", registry(), **kwargs)
    with pytest.raises(BatchError):
        prepare_plan(engine, manifest, "TEST", registry(), profile="arbitrary", **kwargs)
    plan = prepare_plan(engine, manifest, "TEST", registry(), profile=profile, **kwargs)
    with engine.connect() as conn:
        assert inspect_plan(conn, plan, registry(), canonical_sha256(manifest), profile=profile) == {
            "ready": True, "raw_owners": len(raws), "albums": total, "name_writes": 0, "fk_writes": 0}
        with pytest.raises(BatchError):
            inspect_plan(conn, plan, registry(), canonical_sha256(manifest))
    wrong_raw = deepcopy(manifest)
    wrong_raw["records"][0]["raw_value"] = (
        "团体赛" if profile == "generic49" else
        "2007年中华围棋段位赛第一轮" if profile == "geographic39" else
        wrong_raw["records"][0]["raw_value"] + "X")
    with pytest.raises(BatchError):
        prepare_plan(engine, wrong_raw, "TEST", registry(), profile=profile, **kwargs)
    wrong_count = deepcopy(manifest)
    wrong_count["records"].pop()
    with pytest.raises(BatchError):
        prepare_plan(engine, wrong_count, "TEST", registry(), profile=profile, **kwargs)
    with engine.begin() as conn:
        conn.execute(KifuAlbum.__table__.update().where(KifuAlbum.id == 2000).values(black_rank="2d"))
    with engine.connect() as conn, pytest.raises(BatchError):
        inspect_plan(conn, plan, registry(), canonical_sha256(manifest), profile=profile)
    with engine.begin() as conn:
        conn.execute(KifuAlbum.__table__.update().where(KifuAlbum.id == 2000).values(black_rank=None))
    applied = apply_plan(engine, plan, registry(), canonical_sha256(manifest), canonical_sha256(plan), profile=profile)
    assert applied["change_count"] == len(raws)
    undo_batch(engine, applied["batch_id"])
    with engine.connect() as conn:
        assert conn.scalar(select(KifuRawEventValue.review_status).where(KifuRawEventValue.id == 200)) == "pending"


@pytest.mark.parametrize("profile,raws,counts", [
    ("agon10", AGON_RAWS, (48, 24, 14, 7, 5, 60, 25, 1, 1, 19)),
    ("cmb2", CMB_RAWS, (1, 2)),
    ("generic49", tuple(raw for raw, _ in GENERIC49),
     tuple(count - 1 if index == 0 else count for index, (_, count) in enumerate(GENERIC49))),
    ("geographic39", tuple(raw for raw, _ in GEOGRAPHIC39),
     tuple(count - 1 if index == 0 else count for index, (_, count) in enumerate(GEOGRAPHIC39))),
])
def test_finite_profile_rejects_changed_game_total(engine, profile, raws, counts):
    manifest = finite_fixture(engine, raws, counts)
    with pytest.raises(BatchError):
        prepare_plan(engine, manifest, "TEST", registry(), profile=profile,
                     producer_id="producer-1", producer_model="gpt-6-sol",
                     reviewer_id="reviewer-2", reviewer_model="gpt-6-astra",
                     review_conclusion="Reviewed exact literal raw titles")


def team_fixture(engine):
    assert len(TEAM_ALL_IDS) == 324 and len(TEAM_EXCLUDED_IDS) == 30
    with engine.begin() as conn:
        conn.execute(KifuEvent.__table__.insert(), [
            {"id": 73, "canonical_name": "Existing event"},
            {"id": 74, "canonical_name": "Different event"},
        ])
        conn.execute(KifuSource.__table__.insert().values(id=1, source_key="historic", display_name="Historic"))
        conn.execute(KifuRawEventValue.__table__.insert().values(
            id=73686, raw_value="团体赛", category="unclassified_pending", parser_version="original-parser",
            parsed_data={"raw": "团体赛"}, review_status="pending"))
        conn.execute(KifuAlbum.__table__.insert(), [
            {"id": album_id, "player_black": "A", "player_white": "B", "event": "团体赛",
             "event_id": 73 if album_id in TEAM_EXCLUDED_IDS else None,
             "sgf_content": f"(;EV[团体赛]C[{album_id}])", "source_path": f"{album_id}.sgf",
             "black_rank": "1d"}
            for album_id in TEAM_ALL_IDS
        ])
        conn.execute(KifuAlbumSource.__table__.insert(), [
            {"album_id": album_id, "source_id": 1, "origin_path": f"{album_id}.sgf",
             "match_method": "source_path"}
            for album_id in TEAM_ALL_IDS
        ])
        before = _image(conn, KifuRawEventValue.__table__, 73686)
        scope = _team_raw_scope(conn)
    manifest = {"records": [{"raw_value": "团体赛", "owners": {"TEST": {
        "raw_event_id": 73686, "preimage": before, "album_scope_preimage": scope["rows"]}}}],
        "member_manifest": {"TEST": {"members": [{"raw_value": "团体赛", "album_ids": list(TEAM_ALL_IDS)}]}}}
    return manifest


def test_team1_exact_mixed_scope_approval_name_gate_and_undo(engine):
    manifest = team_fixture(engine)
    kwargs = {"producer_id": "producer-1", "producer_model": "gpt-6-sol",
              "reviewer_id": "reviewer-2", "reviewer_model": "gpt-6-astra",
              "review_conclusion": "Reviewed exact 324 album mixed scope"}
    missing_linked = deepcopy(manifest)
    missing_linked["member_manifest"]["TEST"]["members"][0]["album_ids"] = [
        album_id for album_id in TEAM_ALL_IDS if album_id not in TEAM_EXCLUDED_IDS]
    with pytest.raises(BatchError):
        prepare_plan(engine, missing_linked, "TEST", registry(), profile="team1", **kwargs)
    stale_capture = deepcopy(manifest)
    stale_capture["records"][0]["owners"]["TEST"]["album_scope_preimage"][0]["album"]["sgf_content"] = "changed"
    with pytest.raises(BatchError):
        prepare_plan(engine, stale_capture, "TEST", registry(), profile="team1", **kwargs)
    plan = prepare_plan(engine, manifest, "TEST", registry(), profile="team1", **kwargs)
    change = plan["changes"][0]
    assert len(change["occurrence_album_ids"]) == 324
    assert change["after"]["review_metadata"]["team_scope"]["eligible_count"] == 294
    assert "album_scope_preimage" not in change["after"]["review_metadata"]
    with engine.connect() as conn:
        assert inspect_plan(conn, plan, registry(), canonical_sha256(manifest), profile="team1")["albums"] == 324
    forged = deepcopy(plan)
    forged["changes"][0]["after"]["review_metadata"]["team_scope"]["eligible_count"] = 295
    with engine.connect() as conn, pytest.raises(BatchError):
        inspect_plan(conn, forged, registry(), canonical_sha256(manifest), profile="team1")
    first_id = TEAM_ALL_IDS[0]
    with engine.begin() as conn:
        conn.execute(KifuAlbum.__table__.update().where(KifuAlbum.id == first_id).values(sgf_content="changed"))
    with engine.connect() as conn, pytest.raises(BatchError):
        inspect_plan(conn, plan, registry(), canonical_sha256(manifest), profile="team1")
    with engine.begin() as conn:
        conn.execute(KifuAlbum.__table__.update().where(KifuAlbum.id == first_id).values(
            sgf_content=f"(;EV[团体赛]C[{first_id}])"))
    applied = apply_plan(engine, plan, registry(), canonical_sha256(manifest), canonical_sha256(plan), profile="team1")
    assert applied["change_count"] == 1
    candidate = {"owner": {"kind": "raw_event", "id": 73686}, "raw_value": "团体赛",
                 "decision_kind": "translated"}
    with engine.connect() as conn:
        _check_raw_owner(conn, candidate)
        assert _affected_albums(conn, [candidate]) == list(TEAM_ALL_IDS)
    without_scope = deepcopy(change["after"]["review_metadata"])
    without_scope.pop("team_scope")
    with engine.begin() as conn:
        conn.execute(KifuRawEventValue.__table__.update().where(KifuRawEventValue.id == 73686).values(
            review_metadata=without_scope))
    with engine.connect() as conn, pytest.raises(BatchError):
        _check_raw_owner(conn, candidate)
    with engine.begin() as conn:
        conn.execute(KifuRawEventValue.__table__.update().where(KifuRawEventValue.id == 73686).values(
            review_metadata=change["after"]["review_metadata"]))
    linked_id = min(TEAM_EXCLUDED_IDS)
    with engine.begin() as conn:
        conn.execute(KifuAlbum.__table__.update().where(KifuAlbum.id == linked_id).values(event_id=74))
    with engine.connect() as conn, pytest.raises(BatchError):
        _check_raw_owner(conn, candidate)
    with engine.begin() as conn:
        conn.execute(KifuAlbum.__table__.update().where(KifuAlbum.id == linked_id).values(event_id=73))
        conn.execute(KifuAlbumSource.__table__.update().where(KifuAlbumSource.album_id == first_id).values(
            origin_path="changed.sgf"))
    with engine.connect() as conn, pytest.raises(BatchError):
        _check_raw_owner(conn, candidate)
    with engine.begin() as conn:
        conn.execute(KifuAlbumSource.__table__.update().where(KifuAlbumSource.album_id == first_id).values(
            origin_path=f"{first_id}.sgf"))
    undo_batch(engine, applied["batch_id"])
    with engine.connect() as conn:
        assert conn.scalar(select(KifuRawEventValue.review_status).where(KifuRawEventValue.id == 73686)) == "pending"
        assert conn.scalar(select(KifuAlbum.event_id).where(KifuAlbum.id == linked_id)) == 73


def test_national15_owner_profile_uses_fresh_complete_scope_total(engine):
    raws = tuple(f"2020中国国家队积分大循环第{n}轮" for n in range(1, 14)) + (
        "2013职业棋手精英赛", "2014日本国家队新浪网络训练赛")
    assert canonical_sha256(sorted(raws)) == "a1c386f0d6b606f2ed588d8b98bfd39398cec584bba683ab07e0dc7f9dede77d"
    manifest = finite_fixture(engine, raws, (3,) + (1,) * 14)
    manifest["current_null_games"] = 17
    kwargs = {"producer_id": "producer-1", "producer_model": "gpt-6-sol",
              "reviewer_id": "reviewer-2", "reviewer_model": "gpt-6-astra",
              "review_conclusion": "Reviewed complete SGF literal GN scopes"}
    plan = prepare_plan(engine, manifest, "TEST", registry(), profile="national15", **kwargs)
    assert plan["game_total"] == 17
    with engine.connect() as conn:
        assert inspect_plan(conn, plan, registry(), canonical_sha256(manifest), profile="national15")["albums"] == 17
    bad = deepcopy(manifest)
    bad["current_null_games"] = 16
    with pytest.raises(BatchError, match="album total"):
        prepare_plan(engine, bad, "TEST", registry(), profile="national15", **kwargs)


def chinese_manifest_fixture(engine, raws):
    from scripts.kifu_raw_event_title_owners import _scope_rows
    from katrain.web.kifu.name_structure import structure_event
    manifest = finite_fixture(engine, raws, (1,) * len(raws))
    manifest.update(raw_value_count=len(raws), raw_value_set_sha256=canonical_sha256(sorted(raws)),
                    current_null_games=len(raws))
    with engine.begin() as conn:
        for record, member in zip(manifest["records"], manifest["member_manifest"]["TEST"]["members"]):
            raw = record["raw_value"]
            owner = record["owners"]["TEST"]
            parsed = {"structure": structure_event(raw)}
            conn.execute(KifuRawEventValue.__table__.update().where(KifuRawEventValue.id == owner["raw_event_id"]).values(parsed_data=parsed))
            conn.execute(KifuAlbum.__table__.update().where(KifuAlbum.event == raw).values(sgf_content=f"(;GN[{raw}])"))
            owner["preimage"] = _image(conn, KifuRawEventValue.__table__, owner["raw_event_id"])
            member["scope_rows"] = _scope_rows(conn, raw)
    return manifest


@pytest.mark.parametrize("raws", [("全运会",), ("第4届台湾碁圣战分组循环赛", "2012韩国网站联赛第3轮")])
def test_sgf_chinese_profile_reuses_two_exact_manifests(engine, raws):
    manifest = chinese_manifest_fixture(engine, raws)
    kwargs = {"producer_id": "producer-1", "producer_model": "gpt-6-sol",
              "reviewer_id": "reviewer-2", "reviewer_model": "gpt-6-astra", "review_conclusion": "Reviewed finite Chinese GN titles"}
    plan = prepare_plan(engine, manifest, "TEST", registry(), profile="sgf_chinese", **kwargs)
    assert plan["raw_count"] == len(raws) and plan["game_total"] == len(raws)
    for change in plan["changes"]:
        parts = [{"kind": p["kind"], "text": p["text"]} for p in change["before"]["parsed_data"]["structure"]["parts"]]
        assert change["after"]["review_metadata"]["sgf_literal"]["raw_parts_sha256"] == canonical_sha256(parts)
    digest = canonical_sha256(manifest)
    with engine.connect() as conn:
        assert inspect_plan(conn, plan, registry(), digest, profile="sgf_chinese", manifest=manifest)["albums"] == len(raws)
        with pytest.raises(BatchError):
            inspect_plan(conn, plan, registry(), digest, profile="sgf_chinese")
        bad = deepcopy(manifest)
        bad["current_null_games"] += 1
        with pytest.raises(BatchError):
            inspect_plan(conn, plan, registry(), digest, profile="sgf_chinese", manifest=bad)
        bad_plan = deepcopy(plan)
        bad_plan["changes"][0]["after"]["review_metadata"]["sgf_literal"]["raw_parts_sha256"] = "0" * 64
        with pytest.raises(BatchError):
            inspect_plan(conn, bad_plan, registry(), digest, profile="sgf_chinese", manifest=manifest)
    result = apply_plan(engine, plan, registry(), digest, canonical_sha256(plan), profile="sgf_chinese", manifest=manifest)
    assert result["change_count"] == len(raws)
    replay = apply_plan(engine, plan, registry(), digest, canonical_sha256(plan), profile="sgf_chinese", manifest=manifest)
    assert replay["status"] == "already_applied" and replay["change_count"] == 0
    other_manifest = deepcopy(manifest)
    other_manifest["decision_note"] = "different frozen artifact"
    with pytest.raises(BatchError, match="signed owner plan"):
        apply_plan(engine, plan, registry(), canonical_sha256(other_manifest), canonical_sha256(plan),
                   profile="sgf_chinese", manifest=other_manifest)
    undo_batch(engine, result["batch_id"])


@pytest.mark.parametrize("damage", ["limit", "raw_hash", "member", "scope", "non_chinese"])
def test_sgf_chinese_profile_rejects_changed_or_unbounded_manifest(engine, damage):
    manifest = chinese_manifest_fixture(engine, ("全运会",))
    if damage == "limit":
        manifest["records"] *= 151
        manifest["raw_value_count"] = 151
    elif damage == "raw_hash":
        manifest["raw_value_set_sha256"] = "0" * 64
    elif damage == "member":
        manifest["member_manifest"]["TEST"]["members"][0]["album_ids"] = [999]
    elif damage == "scope":
        manifest["member_manifest"]["TEST"]["members"][0]["scope_rows"][0]["sgf_sha256"] = "0" * 64
    else:
        manifest["records"][0]["raw_value"] = "Cup"
        manifest["raw_value_set_sha256"] = canonical_sha256(["Cup"])
    with pytest.raises(BatchError):
        prepare_plan(engine, manifest, "TEST", registry(), profile="sgf_chinese", producer_id="producer-1",
                     producer_model="gpt-6-sol", reviewer_id="reviewer-2", reviewer_model="gpt-6-astra",
                     review_conclusion="Reviewed finite Chinese GN titles")
