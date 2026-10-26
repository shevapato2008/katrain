"""Official identity parsing uses exact subject fields, without a person whitelist."""

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path

import pytest

from katrain.web.kifu import player_ranks as ranks


def capture(url, body):
    return {"url": url, "body_excerpt": body, "body_sha256": sha256(body.encode()).hexdigest(), "http_status": 200}


KOREAN_SUBJECTS = [
    ("於之瑩", "20000560", "위즈잉", "8", False),
    ("芮乃偉", "10000186", "루이나이웨이", "9", True),
    ("黨毅飛", "20000536", "당이페이", "9", False),
    ("辜梓豪", "20000629", "구쯔하오", "9", True),
]


def korean_capture(name, key, korean, grade, mobile=False):
    if mobile:
        url = f"https://m.baduk.or.kr/record/gisa_info.asp?PRPL_CODE={key}"
        heading = f"기사정보 | 한국기원 기사정보 {grade}단 {korean} ({name})"
    else:
        url = f"https://www.baduk.or.kr/record/player_view.asp?pkey={key}"
        heading = f"기록실 기사정보 상세 {korean}( {name} ) {grade}단"
    return capture(url, heading + " 생년월일 소속 중국 특기사항 아버지 9단 스승 9단 승단이력 1단")


@pytest.mark.parametrize(("name", "key", "korean", "grade", "mobile"), KOREAN_SUBJECTS)
def test_korean_subject_headings_support_new_exact_owners(name, key, korean, grade, mobile):
    source = korean_capture(name, key, korean, grade, mobile)
    assert ranks._official_subject(source, name) == {
        "subject_key": key,
        "subject_name": name,
        "identity_field": {"field": "기사정보 subject heading", "value": grade + "단"},
        "url": source["url"],
        "body_sha256": source["body_sha256"],
        "body_excerpt": source["body_excerpt"],
    }


def test_korean_native_heading_is_an_exact_original_name_too():
    source = korean_capture("張子涵", "20000822", "장쯔한", "4")
    result = ranks._official_subject(source, "장쯔한")
    assert result["subject_name"] == "장쯔한"
    assert result["identity_field"]["value"] == "4단"


def japanese_capture(name="小池 芳弘", key="ki000465.html", grade="七"):
    return capture(
        f"https://www.nihonkiin.or.jp/player/htm/{key}",
        f"{name} | 棋士 | 囲碁の日本棋院 日本棋院ホーム 棋士 {name} {name} "
        f"（コイケ ヨシヒロ / KOIKE, Yoshihiro） ファンメッセージ 性別 男 棋士段位 {grade}段 "
        "出身地 神奈川県 プロフィール 高林拓二七段 門下。 2016年度入段。",
    )


@pytest.mark.parametrize(
    ("name", "key", "grade"),
    [
        ("一力 遼", "ki000435.htm", "九"),
        ("山田 規三生", "ki000292.html", "九"),
        ("小池 芳弘", "ki000465.html", "七"),
        ("福岡 航太朗", "ki000488.html", "八"),
    ],
)
def test_japanese_current_main_heading_supports_profile_key_and_both_extensions(name, key, grade):
    result = ranks._official_subject(japanese_capture(name, key, grade), name.replace(" ", "\\u3000"))
    assert result["subject_key"] == key.rsplit(".", 1)[0]
    assert result["subject_name"] == name.replace(" ", "")
    assert result["identity_field"] == {"field": "棋士段位", "value": grade + "段"}


@pytest.mark.parametrize(("name", "key"), [("赵奕斐", "CWA000607"), ("罗楚玥", "CWA000636"), ("潘阳", "CWA000466")])
def test_exact_chinese_professional_roster_record_has_no_player_number_whitelist(name, key):
    record = {"playerNo": key, "playerName": name, "playerGrade": "Z06"}
    source = capture(
        "https://wqapi.cwql.org.cn/playerInfo/professional/list", 'truncated","x":1},' + json.dumps(record)
    )
    result = ranks._official_subject(source, name)
    assert result["subject_key"] == key and result["subject_name"] == name
    assert result["identity_field"] == {
        "field": "professional_roster_membership",
        "value": key,
        "playerName": name,
        "playerGrade": "Z06",
    }


@pytest.mark.parametrize(
    ("original", "approved", "subject", "key", "native"),
    [
        ("冯韵嘉", "馮韻嘉", "馮韻嘉", "10001143", "펑윈자"),
        ("李小溪(05)", "李小溪05", "李小溪05", "20002111", "리샤오시05"),
    ],
)
def test_only_an_exact_approved_display_name_can_bridge_different_original_spelling(
    original, approved, subject, key, native
):
    source = korean_capture(subject, key, native, "6", True)
    with pytest.raises(ValueError):
        ranks._official_subject(source, original)
    proof = ranks._identity_proof(
        "canonical must not be searched", approved, original, source, "research.source_checks[0]"
    )
    assert proof["subject_name"] == approved
    assert ranks._validate_identity(proof, "canonical must not be searched") == proof


@pytest.mark.parametrize(
    ("source", "original"),
    [
        (japanese_capture(), "高林拓二"),
        (
            capture(
                "https://www.nihonkiin.or.jp/player/htm/ki000489.html",
                japanese_capture()["body_excerpt"] + " 上野梨紗 棋士段位 四段",
            ),
            "上野梨紗",
        ),
        (
            capture(
                "https://www.nihonkiin.or.jp/player/htm/ki000465.html",
                japanese_capture()["body_excerpt"].replace("棋士段位 七段", "棋士段位 不明") + " 小池芳弘 九段",
            ),
            "小池芳弘",
        ),
        (
            capture("https://www.nihonkiin.or.jp/player/htm/ki000465.html", japanese_capture()["body_excerpt"] * 2),
            "小池芳弘",
        ),
        (korean_capture("於之瑩", "20000560", "위즈잉", "8"), "王爽"),
        (
            capture(
                "https://www.baduk.or.kr/record/player_view.asp?pkey=20000560",
                "기사정보 상세 위즈잉( 於之瑩 ) 생년월일 아버지 9단 승단이력 8단",
            ),
            "於之瑩",
        ),
        (
            capture(
                "https://m.baduk.or.kr/record/gisa_info.asp?PRPL_CODE=10000186",
                "기사정보 루이나이웨이 (芮乃偉) 생년월일 배우자 9단 승단이력 9단",
            ),
            "芮乃偉",
        ),
        (
            capture(
                "https://www.baduk.or.kr/record/player_view.asp?pkey=20000560",
                korean_capture("於之瑩", "20000560", "위즈잉", "8")["body_excerpt"] * 2,
            ),
            "於之瑩",
        ),
    ],
)
def test_other_person_parent_history_or_ambiguous_profile_never_establishes_identity(source, original):
    with pytest.raises(ValueError):
        ranks._official_subject(source, original)


@pytest.mark.parametrize("change", ["wrong_name", "duplicate_name", "duplicate_key", "bad_key"])
def test_roster_requires_one_exact_complete_owner_and_unambiguous_well_formed_key(change):
    record = {"playerNo": "CWA000607", "playerName": "赵奕斐", "playerGrade": "Z06"}
    records = [record]
    if change == "wrong_name":
        record["playerName"] = "别的棋手"
    elif change == "duplicate_name":
        records.append({**record, "playerNo": "CWA000608"})
    elif change == "duplicate_key":
        records.append({**record, "playerName": "别的棋手"})
    else:
        record["playerNo"] = "CWA000607/other"
    source = capture("https://wqapi.cwql.org.cn/playerInfo/professional/list", json.dumps(records))
    with pytest.raises(ValueError):
        ranks._official_subject(source, "赵奕斐")


def test_roster_record_with_duplicate_identity_fields_is_ambiguous():
    source = capture(
        "https://wqapi.cwql.org.cn/playerInfo/professional/list",
        '{"playerNo":"CWA000607","playerName":"别的棋手","playerName":"赵奕斐","playerGrade":"Z06"}',
    )
    with pytest.raises(ValueError):
        ranks._official_subject(source, "赵奕斐")


@pytest.mark.parametrize(
    "url",
    [
        "http://www.baduk.or.kr/record/player_view.asp?pkey=20000560",
        "https://www.baduk.or.kr.evil.test/record/player_view.asp?pkey=20000560",
        "https://www.baduk.or.kr@evil.test/record/player_view.asp?pkey=20000560",
        "https://guest@www.baduk.or.kr/record/player_view.asp?pkey=20000560",
        "https://www.baduk.or.kr/record/player_view.asp?pkey=20000560#bio",
        "https://www.baduk.or.kr/record/player_view.asp;other?pkey=20000560",
        "https://www.baduk.or.kr/record/player_view.asp?pkey=20000560&extra=",
        "https://www.baduk.or.kr/record/player_view.asp?pkey=20000560&pkey=20000560",
        "https://www.baduk.or.kr/record/player_view.asp?pkey=../../20000560",
        "https://www.baduk.or.kr/record/player_view.asp?pkey=200005600",
        "https://www.baduk.or.kr/record/player_view.asp?PRPL_CODE=20000560",
        "https://m.baduk.or.kr/record/player_view.asp?pkey=20000560",
        "https://www.nihonkiin.or.jp/player/htm/ki000465/other.html",
        "https://www.nihonkiin.or.jp/player/htm/ki000465.html?extra=",
        "https://www.nihonkiin.or.jp/player/htm/ki000465.html;other",
        "https://wqapi.cwql.org.cn.evil.test/playerInfo/professional/list",
    ],
)
def test_official_url_only_accepts_exact_supported_hosts_paths_and_key_schemas(url):
    source = korean_capture("於之瑩", "20000560", "위즈잉", "8")
    original = "於之瑩"
    if "nihonkiin.or.jp" in url:
        source, original = japanese_capture(), "小池芳弘"
    elif "cwql.org.cn" in url:
        source = capture("", '{"playerNo":"CWA000607","playerName":"赵奕斐","playerGrade":"Z06"}')
        original = "赵奕斐"
    source["url"] = url
    with pytest.raises(ValueError):
        ranks._official_subject(source, original)


FROZEN_DIGESTS = {
    "藤泽里菜": (
        "535c33ab8e82fa729975aa386c27c64596b6646bd5d4cb95f5c10e07a8252804",
        "b740736db3e34ec7881062e25568ad940519dd68205886db8aad4f6854ce9527",
    ),
    "周泓余": (
        "b2b1470871a7ff94797a67c27a1e76e030f4cd466486cfa7c0d7a0a25bfc4ec7",
        "5a8bf77df33fc3da47ca63fc49c3fc1751859113c21bc1d5fc5e61bc3f0911bc",
    ),
    "唐奕": (
        "6a6b12d167de0a191645924e4e59417ee1b6a46aa9d9f0c08b5bc5497c907e84",
        "3b268bd62f673bdfc867ea2ae7023a0f662b51eb93673b828331400512003e4c",
    ),
    "高星": (
        "0af8ea8602732425b7c1a69de89f7c624d4ee153b7ccdcdcc512f41a6c6ff4ff",
        "f67beaad1ba32afa8bab4e034d7789833577f08a2ed12b3d7ba0e0fd0fe9f596",
    ),
    "上野梨纱": (
        "b468c106f1218ec8242641aabd75d3f5b13d28a550547b87ff31c94145cb03f9",
        "2ee997d5ced0162636399b7f376c7946783296f35255c6031bae0204158e6d43",
    ),
    "王爽": (
        "e3b5538ac74d4e76e4503f6e1b5e6eda8489081f5944b9f0a9e4af9e8419bb20",
        "461cb22e73eaa347536e0f0b686414fd6f2159c100b01207fc59f06fdf015578",
    ),
}
LEGACY_CAPTURES = json.loads((Path(__file__).parent / "data/kifu_official_rank_captures.json").read_text())


@pytest.mark.parametrize("row", LEGACY_CAPTURES, ids=lambda row: row["canonical_name"])
def test_six_previously_published_proof_and_fact_digests_remain_frozen(row):
    canonical = row["canonical_name"]
    proof = ranks._identity_proof(
        canonical, row["approved_name"], row["original_name"], row["capture"], row["capture_path"]
    )
    fact = ranks.build_source_rank_fact(
        canonical_name=canonical,
        raw_rank="五段",
        sgf_content=f"(;PB[{canonical}]BR[五段]DT[2026-10-19])",
        slot="black",
        source_ref={"source_key": "19x19", "source_item_id": "frozen"},
        identity_evidence=proof,
        observed_at="2026-10-25T00:00:00+00:00",
    )
    assert (proof["capture_sha256"], fact["content_sha256"]) == FROZEN_DIGESTS[canonical]
    assert ranks.validate_rank_fact(deepcopy(fact)) == fact
