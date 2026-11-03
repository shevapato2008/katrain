"""Bounded raw-grade reads and exact public official subject captures."""

from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path

import pytest
from sqlalchemy import create_engine, event, func, select

from katrain.web.core import models_db as m
from katrain.web.kifu import player_ranks as ranks

CAPTURES = json.loads((Path(__file__).parent / "data/kifu_official_rank_captures.json").read_text())
GRADES = {"藤泽里菜": 7, "上野梨纱": 4, "高星": 5, "王爽": 5, "唐奕": 5, "周泓余": 7}
NOW = datetime(2026, 10, 25, tzinfo=timezone.utc)


@pytest.fixture
def engine():
    engine = create_engine("sqlite:///:memory:")
    m.Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


def seed_owner(conn, capture, player_id=1, *, approved=True, wrong_owner=False, forged_hash=False):
    canonical = capture["canonical_name"]
    conn.execute(m.KifuPlayer.__table__.insert().values(id=player_id, canonical_name=canonical))
    conn.execute(
        m.KifuNameSourceRegistry.__table__.insert().values(
            id=player_id, version=f"rank-test-{player_id}", sha256="0" * 64, registry={}
        )
    )
    body = deepcopy(capture["capture"])
    if forged_hash:
        body["body_sha256"] = "f" * 64
    check = {}
    if "identity_bridges" in capture["capture_path"]:
        check["identity_bridges"] = [body]
    else:
        check["identity_corroboration"] = body
    owner = {"kind": "player", "id": player_id + 10 if wrong_owner else player_id}
    payload = {
        "candidate": {"owner": owner, "display_name": capture["approved_name"]},
        "research": {
            "owner": owner,
            "candidate_name": capture["approved_name"],
            "original_name": capture["original_name"],
            "source_checks": [check],
        },
    }
    conn.execute(
        m.KifuNameResearchEvidence.__table__.insert().values(
            id=player_id,
            player_id=player_id,
            lang="cn",
            revision=1,
            source_registry_id=player_id,
            candidate_name=capture["approved_name"],
            decision_kind="conventional",
            generation_rule_version="none",
            research_payload=payload,
            producer_id="producer",
            producer_model="test",
            reviewer_id="reviewer",
            reviewer_model="test",
            reviewed_at=NOW,
            review_status="approved" if approved else "pending",
        )
    )
    conn.execute(
        m.KifuPlayerName.__table__.insert().values(
            player_id=player_id,
            lang="cn",
            display_name=capture["approved_name"],
            status="verified",
            revision=1,
            evidence_id=player_id,
            decision_kind="conventional",
            generation_rule_version="none",
        )
    )
    return payload


def album(
    conn,
    canonical,
    *,
    player_id=1,
    item="1",
    day="2026-10-19",
    rank="七段",
    sgf_rank=None,
    created_at=None,
    side="black",
    root_name=None,
    source_path=None,
):
    root_name = root_name or canonical
    color = "B" if side == "black" else "W"
    sgf = f"(;FF[4]P{color}[{root_name}]{color}R[{rank if sgf_rank is None else sgf_rank}]DT[{day}])"
    values = {
        "player_black": root_name if side == "black" else "对手",
        "player_white": root_name if side == "white" else "对手",
        f"{side}_player_id": player_id,
        f"{side}_rank": rank,
        "sgf_content": sgf,
        "date_sort": day,
        "date_played": day,
        "source_path": source_path or f"data/kifu-album/19x19/{item}.sgf",
    }
    if created_at:
        values["created_at"] = created_at
    return conn.execute(m.KifuAlbum.__table__.insert().values(**values)).inserted_primary_key[0]


def resolved(canonical, player_id=1, status="qualified"):
    return {"id": player_id, "canonical_name": canonical, "status": status}


@pytest.mark.parametrize("capture", CAPTURES, ids=lambda c: c["canonical_name"])
def test_six_real_cached_official_subjects_type_the_raw_grade(engine, capture):
    canonical = capture["canonical_name"]
    grade = GRADES[canonical]
    with engine.begin() as conn:
        seed_owner(conn, capture)
        album(conn, canonical, rank="一二三四五六七八九"[grade - 1] + "段")
    result = ranks.lookup_library_rank_facts(engine, [resolved(canonical)], observed_at=NOW)[1]
    assert result["status"] == "qualified", result
    fact = result["fact"]
    assert (fact["rank_value"], fact["rank_system"]) == (grade, "professional_dan")
    assert fact["valid_from"] is None and fact["source_as_of"] == "2026-10-19"
    proof = fact["evidence"]["professional_identity"]
    assert proof["body_sha256"] == capture["capture"]["body_sha256"]
    # The original HTTP hash is deliberately NOT an excerpt hash.
    assert proof["body_sha256"] != sha256(proof["body_excerpt"].encode()).hexdigest()
    assert proof["capture_sha256"]
    if canonical in {"藤泽里菜", "上野梨纱"}:
        assert proof["identity_field"] == {"field": "棋士段位", "value": "一二三四五六七八九"[grade - 1] + "段"}
    if canonical == "唐奕":
        assert proof["subject_key"] == "CWA000149"
        assert proof["identity_field"]["playerName"] == "唐奕"
    with engine.begin() as conn:
        ranks.verify_rank_fact_for_player(conn, 1, fact)
        assert ranks.apply_rank_fact(conn, 1, fact)["status"] == "qualified"
    cached = ranks.lookup_library_rank_facts(engine, [resolved(canonical)])[1]
    assert cached["fact"]["content_sha256"] == fact["content_sha256"]


@pytest.mark.parametrize("change", ["not_approved", "wrong_owner", "wrong_capture", "comment_only"])
def test_unapproved_wrong_owner_other_person_or_comment_cannot_type_grade(engine, change):
    capture = deepcopy(next(c for c in CAPTURES if c["canonical_name"] == "高星"))
    with engine.begin() as conn:
        payload = seed_owner(conn, capture, approved=change != "not_approved", wrong_owner=change == "wrong_owner")
        if change == "wrong_capture":
            payload["research"]["source_checks"] = [
                {
                    "identity_bridges": [
                        {
                            "url": "https://zh.wikipedia.org/wiki/金彩瑛",
                            "body_excerpt": "金彩瑛 九段 高星",
                            "body_sha256": "a" * 64,
                            "http_status": 200,
                        }
                    ]
                }
            ]
        if change == "comment_only":
            payload["research"]["source_checks"] = [{"identity_basis": "高星职业九段，已确认", "body_sha256": "a" * 64}]
        conn.execute(m.KifuNameResearchEvidence.__table__.update().values(research_payload=payload))
        album(conn, "高星", rank="五段")
    assert ranks.lookup_library_rank_facts(engine, [resolved("高星")])[1]["status"] == "unknown_system"


def test_native_identity_requires_the_actual_local_capture_not_self_consistent_hash(engine):
    capture = deepcopy(next(c for c in CAPTURES if c["canonical_name"] == "唐奕"))
    with engine.begin() as conn:
        seed_owner(conn, capture)
        album(conn, "唐奕", rank="五段")
    fact = ranks.lookup_library_rank_facts(engine, [resolved("唐奕")])[1]["fact"]
    forged = deepcopy(fact)
    proof = forged["evidence"]["professional_identity"]
    proof["body_sha256"] = "f" * 64
    proof.pop("capture_sha256")
    proof["capture_sha256"] = ranks._digest(proof)
    forged["content_sha256"] = ranks.rank_fact_sha256(forged)
    ranks.validate_rank_fact(forged)  # Self-consistency does not establish authority.
    with engine.begin() as conn:
        with pytest.raises(ValueError, match="approved owner evidence"):
            ranks.verify_rank_fact_for_player(conn, 1, forged)


def test_new_chinese_source_can_get_official_identity_without_any_library_grade(engine):
    capture = next(c for c in CAPTURES if c["canonical_name"] == "上野梨纱")
    with engine.begin() as conn:
        seed_owner(conn, capture)
        proofs = ranks.lookup_professional_identity_evidence(conn, [1])
        fact = ranks.build_source_rank_fact(
            canonical_name="上野梨纱",
            raw_rank="五段",
            sgf_content="(;PB[上野梨纱]BR[五段]DT[2026-10-25])",
            slot="black",
            source_ref={"source_key": "19x19", "source_item_id": "2"},
            identity_evidence=proofs[1],
        )
        assert fact["rank_value"] == 5  # The profile's four is identity only.
        assert fact["rank_system"] == "professional_dan"


def test_profile_never_retypes_an_explicit_amateur_grade(engine):
    capture = next(c for c in CAPTURES if c["canonical_name"] == "藤泽里菜")
    with engine.begin() as conn:
        seed_owner(conn, capture)
        album(conn, "藤泽里菜", rank="9d")
    fact = ranks.lookup_library_rank_facts(engine, [resolved("藤泽里菜")])[1]["fact"]
    assert (fact["rank_value"], fact["rank_system"]) == (9, "amateur_dan")


def test_latest_basis_beats_later_upload_time_and_never_reads_overlay(engine):
    with engine.begin() as conn:
        conn.execute(m.KifuPlayer.__table__.insert().values(id=1, canonical_name="甲"))
        recent = album(conn, "甲", rank="8p", day="2026-10-19", item="1", created_at=datetime(2026, 10, 19))
        album(conn, "甲", rank="7p", day="2026-10-01", item="2", created_at=datetime(2026, 10, 25))
        empty = album(conn, "甲", rank="", day="2026-10-24", item="3")
        conn.execute(
            m.KifuAlbumRankSnapshot.__table__.insert().values(
                album_id=empty,
                side="black",
                snapshot={"rank_value": 9},
                snapshot_sha256="a" * 64,
                publication_key="some-overlay",
                native_batch_id=1,
            )
        )
    result = ranks.lookup_library_rank_facts(engine, [resolved("甲")])[1]
    assert result["fact"]["rank_value"] == 8
    assert result["fact"]["source_as_of"] == "2026-10-19"
    with engine.connect() as conn:
        assert conn.scalar(select(func.count()).select_from(m.KifuPlayerRankHistory)) == 0


def test_fourth_highest_day_grade_conflict_is_not_hidden_by_three_candidate_limit(engine):
    with engine.begin() as conn:
        conn.execute(m.KifuPlayer.__table__.insert().values(id=1, canonical_name="甲"))
        album(conn, "甲", rank="8p", item="1")
        for item in ("2", "3", "4"):
            album(conn, "甲", rank="7p", item=item)
    result = ranks.lookup_library_rank_facts(engine, [resolved("甲")])[1]
    assert result["status"] == "conflict"


def test_professional_downgrade_among_recent_raw_candidates_is_conflict(engine):
    with engine.begin() as conn:
        conn.execute(m.KifuPlayer.__table__.insert().values(id=1, canonical_name="甲"))
        album(conn, "甲", rank="8p", day="2026-10-01", item="1")
        album(conn, "甲", rank="7p", day="2026-10-02", item="2")
    assert ranks.lookup_library_rank_facts(engine, [resolved("甲")])[1]["status"] == "conflict"


def test_resolved_id_owner_mismatch_or_ambiguity_never_uses_names_as_identity_index(engine):
    with engine.begin() as conn:
        conn.execute(
            m.KifuPlayer.__table__.insert(), [{"id": 1, "canonical_name": "甲"}, {"id": 2, "canonical_name": "乙"}]
        )
        album(conn, "甲", rank="7p")
    assert (
        ranks.lookup_library_rank_facts(engine, [resolved("甲", status="ambiguous")])[1]["status"] == "unknown_identity"
    )
    assert ranks.lookup_library_rank_facts(engine, [resolved("乙")])[1]["status"] == "unknown_identity"
    assert (
        ranks.lookup_library_rank_facts(engine, [resolved("甲", status="missing_qualified_five_languages")])[1][
            "status"
        ]
        == "qualified"
    )
    with pytest.raises(ValueError, match="limit"):
        ranks.lookup_library_rank_facts(engine, [resolved("甲")] * 201)


def test_raw_column_and_source_sgf_must_agree_with_bound_owner(engine):
    with engine.begin() as conn:
        conn.execute(m.KifuPlayer.__table__.insert().values(id=1, canonical_name="甲"))
        album(conn, "甲", rank="7p", sgf_rank="8p")
    assert ranks.lookup_library_rank_facts(engine, [resolved("甲")])[1]["status"] == "unknown_system"
    with engine.begin() as conn:
        conn.execute(m.KifuAlbum.__table__.delete())
        album(conn, "甲", rank="7p", root_name="另一个人")
    assert ranks.lookup_library_rank_facts(engine, [resolved("甲")])[1]["status"] == "unknown_system"


def test_batch_lookup_uses_constant_number_of_reads_and_fetches_only_candidates(engine):
    with engine.begin() as conn:
        for i in range(1, 7):
            conn.execute(m.KifuPlayer.__table__.insert().values(id=i, canonical_name=f"人{i}"))
            album(conn, f"人{i}", player_id=i, item=str(i), rank="7p")
    statements = []

    def capture(_conn, _cursor, statement, _parameters, _context, _executemany):
        statements.append(statement)

    event.listen(engine, "before_cursor_execute", capture)
    try:
        results = ranks.lookup_library_rank_facts(engine, [resolved(f"人{i}", i) for i in range(1, 7)])
    finally:
        event.remove(engine, "before_cursor_execute", capture)
    assert len(results) == 6 and all(v["status"] == "qualified" for v in results.values())
    assert len(statements) <= 10, len(statements)
    assert sum("SELECT kifu_albums.id, kifu_albums.sgf_content" in sql for sql in statements) == 1


def test_embedded_source_grade_agrees_with_cleaned_raw_column_and_bound_owner(engine):
    with engine.begin() as conn:
        seed_owner(conn, next(c for c in CAPTURES if c["canonical_name"] == "唐奕"))
        conn.execute(
            m.KifuAlbum.__table__.insert().values(
                player_black="唐奕",
                player_white="对手",
                black_player_id=1,
                black_rank="五段",
                date_sort="2026-10-19",
                date_played="2026-10-19",
                sgf_content="(;PB[唐奕 五段]PW[对手]DT[2026-10-19])",
                source_path="data/kifu-album/19x19/1.sgf",
            )
        )
    result = ranks.lookup_library_rank_facts(engine, [resolved("唐奕")])[1]
    assert result["status"] == "qualified", result
    assert result["fact"]["rank_value"] == 5


def test_no_sgf_dt_uses_explicit_album_date_basis_and_native_rechecks_it(engine):
    with engine.begin() as conn:
        seed_owner(conn, next(c for c in CAPTURES if c["canonical_name"] == "藤泽里菜"))
        album_id = conn.execute(
            m.KifuAlbum.__table__.insert().values(
                player_black="藤泽里菜",
                player_white="对手",
                black_player_id=1,
                black_rank="七段",
                date_sort="2026-10-19",
                date_played="2026-10-19",
                sgf_content="(;PB[藤泽里菜]PW[对手]BR[七段])",
                source_path="data/kifu-album/19x19/1.sgf",
            )
        ).inserted_primary_key[0]
    result = ranks.lookup_library_rank_facts(engine, [resolved("藤泽里菜")])[1]
    assert result["status"] == "qualified", result
    fact = result["fact"]
    assert fact["source_as_of"] == "2026-10-19"
    assert fact["evidence"]["grade"]["date_basis"] == {"kind": "album_date_sort", "value": "2026-10-19"}
    with engine.begin() as conn:
        ranks.verify_rank_fact_for_player(conn, 1, fact)
        conn.execute(m.KifuAlbum.__table__.update().where(m.KifuAlbum.id == album_id).values(date_sort="2026-10-18"))
        with pytest.raises(ValueError, match="source|date"):
            ranks.verify_rank_fact_for_player(conn, 1, fact)


def test_new_source_without_dt_requires_exact_derived_metadata_date_anchor(engine):
    from katrain.kifu_ingest.preparation import derive_metadata

    content = "(;PB[甲]PW[乙]BR[7p]EV[赛])"
    source = {"playTime": {"date": {"year": 2026, "month": 10, "day": 19}}}
    game = {
        "source_key": "19x19",
        "source_item_id": "1",
        "sgf_content": content,
        "source_metadata": source,
        "metadata": derive_metadata(content, source),
    }
    fact = ranks.build_source_rank_fact(
        canonical_name="甲",
        raw_rank="7p",
        sgf_content=content,
        slot="black",
        source_ref={"source_key": "19x19", "source_item_id": "1"},
        source_as_of="2026-10-19",
    )
    assert fact["evidence"]["grade"]["date_basis"]["kind"] == "album_date_sort"
    with engine.begin() as conn:
        conn.execute(m.KifuPlayer.__table__.insert().values(id=1, canonical_name="甲"))
        ranks.verify_rank_fact_for_player(conn, 1, fact, source_games=[game])
        forged = deepcopy(fact)
        forged["source_as_of"] = "2099-01-01"
        forged["evidence"]["grade"]["date_basis"]["value"] = "2099-01-01"
        forged["content_sha256"] = ranks.rank_fact_sha256(forged)
        ranks.validate_rank_fact(forged)
        with pytest.raises(ValueError, match="date"):
            ranks.verify_rank_fact_for_player(conn, 1, forged, source_games=[game])


def test_explicit_sgf_dt_cannot_be_overridden_by_album_date_sort(engine):
    with engine.begin() as conn:
        conn.execute(m.KifuPlayer.__table__.insert().values(id=1, canonical_name="甲"))
        album_id = album(conn, "甲", rank="7p", day="2026-10-18")
        conn.execute(m.KifuAlbum.__table__.update().where(m.KifuAlbum.id == album_id).values(date_sort="2026-10-19"))
    assert ranks.lookup_library_rank_facts(engine, [resolved("甲")])[1]["status"] == "unknown_system"


@pytest.mark.parametrize("has_good_same_owner_candidate", [False, True])
def test_malformed_candidate_is_isolated_from_other_candidates_and_players(engine, has_good_same_owner_candidate):
    with engine.begin() as conn:
        conn.execute(
            m.KifuPlayer.__table__.insert(), [{"id": 1, "canonical_name": "甲"}, {"id": 2, "canonical_name": "乙"}]
        )
        if has_good_same_owner_candidate:
            album(conn, "甲", player_id=1, rank="7p", item="1")
        bad_album_id = album(conn, "甲", player_id=1, rank="7p", item="2")
        conn.execute(
            m.KifuAlbum.__table__.update().where(m.KifuAlbum.id == bad_album_id).values(sgf_content="broken SGF")
        )
        album(conn, "乙", player_id=2, rank="8p", item="3")
    results = ranks.lookup_library_rank_facts(engine, [resolved("甲", 1), resolved("乙", 2)])
    assert results[1]["status"] == ("qualified" if has_good_same_owner_candidate else "unknown_system")
    if has_good_same_owner_candidate:
        assert results[1]["fact"]["rank_value"] == 7
    assert results[2]["status"] == "qualified"
    assert results[2]["fact"]["rank_value"] == 8


def rank_alias(conn, player_id, alias):
    from katrain.web.kifu.identity import normalize_alias

    conn.execute(
        m.KifuPlayerAlias.__table__.insert().values(
            player_id=player_id, alias=alias, normalized_alias=normalize_alias(alias)
        )
    )


@pytest.mark.parametrize("raw_alias", ["Raw Alias", "ＲＡＷ    Alias"])
def test_unique_bound_alias_can_verify_source_observation_and_library_grade(engine, raw_alias):
    with engine.begin() as conn:
        conn.execute(
            m.KifuPlayer.__table__.insert(), [{"id": 1, "canonical_name": "甲"}, {"id": 2, "canonical_name": "乙"}]
        )
        rank_alias(conn, 1, "Raw Alias")
        album(conn, "甲", player_id=1, root_name=raw_alias, rank="7p")
        content = f"(;PB[{raw_alias}]PW[乙]BR[7p]DT[2026-10-19])"
        game = {
            "source_key": "19x19",
            "source_item_id": "new",
            "sgf_content": content,
            "identities": {"black": {"canonical_name": "甲"}},
        }
        fact = ranks.build_source_rank_fact(
            canonical_name="甲",
            raw_rank="7p",
            sgf_content=content,
            slot="black",
            source_ref={"source_key": "19x19", "source_item_id": "new"},
        )
        ranks.verify_rank_fact_for_player(conn, 1, fact, source_games=[game])
    result = ranks.lookup_library_rank_facts(engine, [resolved("甲")])[1]
    assert result["status"] == "qualified", result
    assert result["fact"]["rank_value"] == 7
    with engine.begin() as conn:
        ranks.verify_rank_fact_for_player(conn, 1, result["fact"])
        identity_index = ranks.build_rank_identity_index(conn, raw_values=[raw_alias, "甲"])
        statements = []

        def capture(_conn, _cursor, statement, _parameters, _context, _executemany):
            statements.append(statement)

        event.listen(conn, "before_cursor_execute", capture)
        try:
            assert (
                ranks.apply_rank_fact(conn, 1, result["fact"], identity_index=identity_index)["status"] == "qualified"
            )
        finally:
            event.remove(conn, "before_cursor_execute", capture)
        assert not any("FROM kifu_players" in sql and "WHERE" not in sql for sql in statements)


@pytest.mark.parametrize("collision", ["another_alias", "another_canonical", "only_other_owner"])
def test_alias_ambiguity_or_wrong_owner_cannot_authorize_rank_fact(engine, collision):
    with engine.begin() as conn:
        conn.execute(
            m.KifuPlayer.__table__.insert(),
            [
                {"id": 1, "canonical_name": "甲"},
                {"id": 2, "canonical_name": "Raw Alias" if collision == "another_canonical" else "乙"},
            ],
        )
        if collision != "only_other_owner":
            rank_alias(conn, 1, "Raw Alias")
        if collision != "another_canonical":
            rank_alias(conn, 2, "RAW ALIAS")
        album(conn, "甲", player_id=1, root_name="ＲＡＷ    Alias", rank="7p")
        content = "(;PB[ＲＡＷ    Alias]PW[乙]BR[7p]DT[2026-10-19])"
        game = {
            "source_key": "19x19",
            "source_item_id": "new",
            "sgf_content": content,
            "identities": {"black": {"canonical_name": "甲"}},
        }
        fact = ranks.build_source_rank_fact(
            canonical_name="甲",
            raw_rank="7p",
            sgf_content=content,
            slot="black",
            source_ref={"source_key": "19x19", "source_item_id": "new"},
        )
        with pytest.raises(ValueError, match="alias|owner|ambiguous"):
            ranks.verify_rank_fact_for_player(conn, 1, fact, source_games=[game])
    assert ranks.lookup_library_rank_facts(engine, [resolved("甲")])[1]["status"] != "qualified"


def test_rank_identity_index_preserves_exact_nfkc_casefold_collision_semantics(engine):
    with engine.begin() as conn:
        conn.execute(
            m.KifuPlayer.__table__.insert(),
            [{"id": 1, "canonical_name": "甲"}, {"id": 2, "canonical_name": "ＳＴＲＡＳＳＥ"}],
        )
        rank_alias(conn, 1, "Straße")
        index = ranks.build_rank_identity_index(conn, raw_values=["  STRASSE 九段", "not alias"])
    assert index == {"strasse": {1, 2}, "not alias": set()}


@pytest.mark.parametrize(
    ("canonical", "original", "url", "heading"),
    [
        (
            "於之莹",
            "於之瑩",
            "https://www.baduk.or.kr/record/player_view.asp?pkey=20000560",
            "기사정보 상세 위즈잉( 於之瑩 ) 8단",
        ),
        (
            "芮乃伟",
            "芮乃偉",
            "https://m.baduk.or.kr/record/gisa_info.asp?PRPL_CODE=10000186",
            "기사정보 | 한국기원 기사정보 9단 루이나이웨이 (芮乃偉)",
        ),
        (
            "党毅飞",
            "黨毅飛",
            "https://www.baduk.or.kr/record/player_view.asp?pkey=20000536",
            "기사정보 상세 당이페이( 黨毅飛 ) 9단",
        ),
        (
            "辜梓豪",
            "辜梓豪",
            "https://m.baduk.or.kr/record/gisa_info.asp?PRPL_CODE=20000629",
            "기사정보 | 한국기원 기사정보 9단 구쯔하오 (辜梓豪)",
        ),
    ],
)
def test_new_owner_capture_types_only_source_first_raw_sgf_grade_and_native_rechecks_capture(
    engine, canonical, original, url, heading
):
    capture = {
        "canonical_name": canonical,
        "approved_name": canonical,
        "original_name": original,
        "capture_path": "research.source_checks[0].identity_corroboration",
        "capture": {
            "url": url,
            "http_status": 200,
            "body_sha256": "a" * 64,
            "body_excerpt": heading + " 생년월일 소속 중국 배우자 9단 승단이력 1단",
        },
    }
    with engine.begin() as conn:
        seed_owner(conn, capture)
        album_id = album(conn, canonical, rank="二段")
        proof = ranks.lookup_professional_identity_evidence(conn, [1])[1]
        fact = ranks.build_source_rank_fact(
            canonical_name=canonical,
            raw_rank="二段",
            sgf_content=conn.scalar(select(m.KifuAlbum.sgf_content).where(m.KifuAlbum.id == album_id)),
            slot="black",
            source_ref={"source_key": "19x19", "source_item_id": "1"},
            identity_evidence=proof,
        )
    assert (fact["rank_value"], fact["rank_system"]) == (2, "professional_dan")
    with engine.begin() as conn:
        ranks.verify_rank_fact_for_player(conn, 1, fact)
        # A plausible numeric key is still not the actual independently approved capture.
        forged = deepcopy(fact)
        proof = forged["evidence"]["professional_identity"]
        proof["url"] = proof["url"][:-1] + "7"
        proof["subject_key"] = proof["subject_key"][:-1] + "7"
        proof.pop("capture_sha256")
        proof["capture_sha256"] = ranks._digest(proof)
        forged["content_sha256"] = ranks.rank_fact_sha256(forged)
        ranks.validate_rank_fact(forged)
        with pytest.raises(ValueError, match="approved owner evidence"):
            ranks.verify_rank_fact_for_player(conn, 1, forged)


@pytest.mark.parametrize("approved_alias", [True, False])
def test_approved_same_row_alias_is_required_for_different_original_spelling(engine, approved_alias):
    capture = {
        "canonical_name": "冯韵嘉",
        "approved_name": "馮韻嘉" if approved_alias else "冯韵嘉",
        "original_name": "冯韵嘉",
        "capture_path": "research.source_checks[0].identity_corroboration",
        "capture": {
            "url": "https://m.baduk.or.kr/record/gisa_info.asp?PRPL_CODE=10001143",
            "http_status": 200,
            "body_sha256": "b" * 64,
            "body_excerpt": "기사정보 | 한국기원 기사정보 4단 펑윈자 (馮韻嘉) 생년월일 소속 중국",
        },
    }
    with engine.begin() as conn:
        seed_owner(conn, capture)
        album(conn, "冯韵嘉", rank="五段")
    result = ranks.lookup_library_rank_facts(engine, [resolved("冯韵嘉")])[1]
    assert result["status"] == ("qualified" if approved_alias else "unknown_system")
    if approved_alias:
        assert result["fact"]["rank_value"] == 5
        with engine.begin() as conn:
            ranks.verify_rank_fact_for_player(conn, 1, result["fact"])
    else:
        proof = ranks._identity_proof("冯韵嘉", "馮韻嘉", "冯韵嘉", capture["capture"], capture["capture_path"])
        fact = ranks.build_source_rank_fact(
            canonical_name="冯韵嘉",
            raw_rank="五段",
            sgf_content="(;PB[冯韵嘉]BR[五段]DT[2026-10-19])",
            slot="black",
            source_ref={"source_key": "19x19", "source_item_id": "1"},
            identity_evidence=proof,
        )
        with engine.begin() as conn:
            with pytest.raises(ValueError, match="approved owner evidence"):
                ranks.verify_rank_fact_for_player(conn, 1, fact)


@pytest.mark.parametrize("stored_current", [False, True])
@pytest.mark.parametrize("profile", ["korean", "japanese", "haifong"])
def test_library_fallback_rejects_grade_below_own_official_heading_without_invalidating_source_fact(
    engine, stored_current, profile
):
    if profile == "japanese":
        capture = next(c for c in CAPTURES if c["canonical_name"] == "藤泽里菜")
    elif profile == "haifong":
        capture = {
            "canonical_name": "杨子萱",
            "approved_name": "杨子萱",
            "original_name": "楊子萱",
            "capture_path": "research.source_checks[0].identity_corroboration",
            "capture": {
                "url": "https://www.haifong.org/profession/venue/C52F5EFDF989D8CE3BA53AB7A2355F45",
                "http_status": 200,
                "body_sha256": "d" * 64,
                "body_excerpt": "海峰棋院-楊子萱 棋譜 關於海峰 職業棋士 世界賽 棋譜 職業棋士 楊子萱 六段 歷史成績 簡介 老師九段",
            },
        }
    else:
        capture = {
            "canonical_name": "李小溪05",
            "approved_name": "李小溪05",
            "original_name": "李小溪(05)",
            "capture_path": "research.source_checks[0].identity_corroboration",
            "capture": {
                "url": "https://m.baduk.or.kr/record/gisa_info.asp?PRPL_CODE=20002111",
                "http_status": 200,
                "body_sha256": "c" * 64,
                "body_excerpt": "기사정보 | 한국기원 기사정보 6단 리샤오시05 (李小溪05) 생년월일 소속 중국 승단이력 6단 / 2026.08.19",
            },
        }
    canonical = capture["canonical_name"]
    with engine.begin() as conn:
        seed_owner(conn, capture)
        album_id = album(conn, canonical, rank="一段", day="2020-07-28", item="41407549")
        proof = ranks.lookup_professional_identity_evidence(conn, [1])[1]
        historical = ranks.build_source_rank_fact(
            canonical_name=canonical,
            raw_rank="一段",
            sgf_content=conn.scalar(select(m.KifuAlbum.sgf_content).where(m.KifuAlbum.id == album_id)),
            slot="black",
            source_ref={"source_key": "19x19", "source_item_id": "41407549"},
            identity_evidence=proof,
        )
        assert ranks.verify_rank_fact_for_player(conn, 1, historical) == historical
        if stored_current:
            assert ranks.apply_rank_fact(conn, 1, historical)["status"] == "qualified"
            row = conn.execute(select(m.KifuPlayerRankHistory.__table__)).mappings().one()
            assert ranks._row_fact(row, canonical) == historical
    assert ranks.lookup_library_rank_facts(engine, [resolved(canonical)])[1] == {
        "status": "conflict",
        "reason": "official_grade_above_library_grade",
    }
    assert ranks.validate_rank_fact(historical) == historical
    assert historical["rank_value"] == 1 and historical["valid_from"] is None


@pytest.mark.parametrize("stored_current", [False, True])
def test_library_fallback_keeps_raw_grade_above_own_official_heading(engine, stored_current):
    capture = next(c for c in CAPTURES if c["canonical_name"] == "藤泽里菜")
    with engine.begin() as conn:
        seed_owner(conn, capture)
        album(conn, "藤泽里菜", rank="八段")
    result = ranks.lookup_library_rank_facts(engine, [resolved("藤泽里菜")])[1]
    assert result["status"] == "qualified"
    if stored_current:
        with engine.begin() as conn:
            ranks.apply_rank_fact(conn, 1, result["fact"])
        result = ranks.lookup_library_rank_facts(engine, [resolved("藤泽里菜")])[1]
    assert (result["status"], result["fact"]["rank_value"]) == ("qualified", 8)


@pytest.mark.parametrize("stored_current", [False, True])
def test_library_fallback_does_not_infer_heading_grade_from_chinese_roster_codes(engine, stored_current):
    capture = next(c for c in CAPTURES if c["canonical_name"] == "唐奕")
    with engine.begin() as conn:
        seed_owner(conn, capture)
        album(conn, "唐奕", rank="一段")
    result = ranks.lookup_library_rank_facts(engine, [resolved("唐奕")])[1]
    assert result["status"] == "qualified"
    if stored_current:
        with engine.begin() as conn:
            ranks.apply_rank_fact(conn, 1, result["fact"])
        result = ranks.lookup_library_rank_facts(engine, [resolved("唐奕")])[1]
    assert (result["status"], result["fact"]["rank_value"]) == ("qualified", 1)
