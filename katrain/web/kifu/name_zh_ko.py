"""Bounded NIKL transcription of sourced, reviewed Mandarin player-name syllables.

These entries transcribe *verified* Hanyu Pinyin. They never derive a reading
from Han characters, certify Pinyin legality or endorse an individual name.
"""

from __future__ import annotations

from copy import deepcopy


SOURCE_BASIS = "normative_zh_ko_v1"
RULE_VERSION = "nikl-zh-ko-personal-name-v1"
RULE_URL = "https://korean.go.kr/kornorms/m/m_regltn.do?regltn_code=0003"
RULE_BODY_SHA256 = "92977a7c4e2d255aa62d91011372bea1a198f5c3ee6f92db5b02fa6366fb9d9b"
RULE_LOCATORS = {
    "table_locator": "Chapter 2 Table 5, raw HTML line 1573; note line 1578",
    "scope_locator": "Chapter 4 section 2 item 1, raw HTML line 13706",
    "tone_locator": "Chapter 3 Chinese section item 1, raw HTML line 6666",
}

# Historical entries and their proof locators remain frozen byte-for-byte.
SYLLABLES = {
    "wang": {"hangul": "왕", "kind": "direct_table_entry",
             "locator": "Table 5 finals: wang (uang) -> 왕, zero-initial form."},
    "hong": {"hangul": "훙", "kind": "reviewed_composition",
             "locator": "Table 5 initial h -> ㅎ plus final weng (ong) -> 웡 (웅); parenthetical ong -> 웅 follows an initial, giving 훙. Note at raw line 1578."},
    "wei": {"hangul": "웨이", "kind": "direct_table_entry",
            "locator": "Table 5 finals: wei (ui) -> 웨이 (우이); unparenthesized zero-initial wei."},
    "weng": {"hangul": "웡", "kind": "direct_table_entry",
             "locator": "Table 5 finals: weng (ong) -> 웡 (웅); unparenthesized zero-initial weng."},
    "zi": {"hangul": "쯔", "kind": "direct_table_entry",
           "locator": "Table 5 initials: z [zi] -> ㅉ [쯔]; bracketed independent syllable. Note at raw line 1578."},
    "yu": {"hangul": "위", "kind": "direct_table_entry",
           "locator": "Table 5 finals: yu (u) -> 위; distinct from wu (u) -> 우."},
    "huang": {"hangul": "황", "kind": "reviewed_composition",
              "locator": "Chapter 2 Table 5, raw HTML line 1573: initial h -> ㅎ plus final wang (uang) -> 왕; select post-initial uang under the note at line 1578, giving 황."},
    "jia": {"hangul": "자", "kind": "reviewed_composition",
            "locator": "Chapter 2 Table 5, raw HTML line 1573: initial j -> ㅈ plus final ya (ia) -> 야; post-initial ia under note line 1578. Chapter 3 Chinese section item 2, raw line 6707 and example line 6710: 쟈 -> 자."},
    "yin": {"hangul": "인", "kind": "direct_table_entry",
            "locator": "Chapter 2 Table 5 finals, raw HTML line 1573: yin (in) -> 인; zero-initial yin."},
    "yang": {"hangul": "양", "kind": "direct_table_entry",
             "locator": "Chapter 2 Table 5 finals, raw HTML line 1573: yang (iang) -> 양; zero-initial yang."},
    "yi": {"hangul": "이", "kind": "direct_table_entry",
           "locator": "Chapter 2 Table 5 finals, raw HTML line 1573: yi (i) -> 이; zero-initial yi."},
    "lun": {"hangul": "룬", "kind": "reviewed_composition",
            "locator": "Chapter 2 Table 5, raw HTML line 1573: initial l -> ㄹ plus final wen (un) -> 원 (운); select parenthetical post-initial un -> 운 under note line 1578, giving 룬."},
    "ke": {"hangul": "커", "kind": "reviewed_composition",
           "locator": "Chapter 2 Table 5, raw HTML line 1573: initial k -> ㅋ plus final e -> 어, giving 커."},
    "pei": {"hangul": "페이", "kind": "reviewed_composition",
            "locator": "Chapter 2 Table 5, raw HTML line 1573: initial p -> ㅍ plus final ei -> 에이, giving 페이."},
    "chen": {"hangul": "천", "kind": "reviewed_composition",
             "locator": "Chapter 2 Table 5, raw HTML line 1573: initial ch -> ㅊ plus final en -> 언, giving 천; this is not the independent chi -> 츠 entry."},
    "han": {"hangul": "한", "kind": "reviewed_composition",
            "locator": "Chapter 2 Table 5, raw HTML line 1573: initial h -> ㅎ plus final an -> 안, giving 한."},
    "li": {"hangul": "리", "kind": "reviewed_composition",
           "locator": "Chapter 2 Table 5, raw HTML line 1573: initial l -> ㄹ plus final yi (i) -> 이; select post-initial i under note line 1578, giving 리."},
    "jie": {"hangul": "제", "kind": "reviewed_composition",
            "locator": "Chapter 2 Table 5, raw HTML line 1573: initial j -> ㅈ plus final ye (ie) -> 예; select post-initial ie under note line 1578. Chapter 3 Chinese section item 2, raw lines 6707 and 6711: 졔 -> 제."},
}

# The original eighteen entries remain valid with the old exact capture. New
# entries below require the separately captured www body checked by review.
LEGACY_RULE_SYLLABLES = frozenset(SYLLABLES)
CURRENT_RULE_URL = "https://www.korean.go.kr/kornorms/m/m_regltn.do?regltn_code=0003"
CURRENT_RULE_BODY_SHA256 = "fba7508fd4dfb60eee30561ff8e11c64493fb3f0bd9fecceacb1fcedd13c6731"
SYLLABLES.update({
    "qing": {"hangul": "칭", "kind": "reviewed_composition",
             "locator": "Chapter 2 Table 5, raw HTML line 1573: q -> ㅊ and post-initial ing from ying (ing) -> 잉 under note line 1578; compose 칭."},
    "hai": {"hangul": "하이", "kind": "reviewed_composition",
            "locator": "Chapter 2 Table 5, raw HTML line 1573: h -> ㅎ and ai -> 아이; compose 하이."},
    "xiao": {"hangul": "샤오", "kind": "reviewed_composition",
             "locator": "Chapter 2 Table 5, raw HTML line 1573: x -> ㅅ and post-initial iao from yao (iao) -> 야오 under note line 1578; compose 샤오. The Chapter 3 simplification does not list x/ㅅ."},
    "rui": {"hangul": "루이", "kind": "reviewed_composition",
            "locator": "Chapter 2 Table 5, raw HTML line 1573: r -> ㄹ and post-initial ui from wei (ui) -> 우이 under note line 1578; compose 루이."},
    "shan": {"hangul": "산", "kind": "reviewed_composition",
             "locator": "Chapter 2 Table 5, raw HTML line 1573: sh -> ㅅ and an -> 안; compose 산."},
    "ye": {"hangul": "예", "kind": "direct_table_entry",
           "locator": "Chapter 2 Table 5, raw HTML line 1573: zero-initial ye (ie) -> 예."},
    "hui": {"hangul": "후이", "kind": "reviewed_composition",
            "locator": "Chapter 2 Table 5, raw HTML line 1573: h -> ㅎ and post-initial ui from wei (ui) -> 우이 under note line 1578; compose 후이."},
    "dong": {"hangul": "둥", "kind": "reviewed_composition",
             "locator": "Chapter 2 Table 5, raw HTML line 1573: d -> ㄷ and post-initial ong from weng (ong) -> 웅 under note line 1578; compose 둥."},
    "tian": {"hangul": "톈", "kind": "reviewed_composition",
             "locator": "Chapter 2 Table 5, raw HTML line 1573: t -> ㅌ and post-initial ian from yan (ian) -> 옌 under note line 1578; compose 톈. The Chapter 3 simplification does not list t/ㅌ."},
    "xu": {"hangul": "쉬", "kind": "reviewed_composition",
           "locator": "Chapter 2 Table 5, raw HTML line 1573: x -> ㅅ and post-initial u/ü from yu (u) -> 위; compose 쉬. Chinese MOE spelling explanation, requested https://www.moe.gov.cn/s78/A18/A18_ztzl/jnhypyfa/201805/t20180517_336341.html, actual HTTP final http://www.moe.gov.cn/s78/A18/A18_ztzl/jnhypyfa/201805/t20180517_336341.html, body SHA-256 184692fa2fd97dc8b356c5cef1c0e56fec58995de076a1e82fa8c4070a3d484d, raw HTML line 206: jqxy followed by ü omits the dots."},
    "jian": {"hangul": "젠", "kind": "reviewed_composition",
             "locator": "Chapter 2 Table 5, raw HTML line 1573: j -> ㅈ and post-initial ian from yan (ian) -> 옌, composing 졘; Chapter 3 item 2 at raw line 6707 makes ㅖ after ㅈ into ㅔ, hence 젠. Raw lines 6710-6711 show analogous examples, not a literal 졘 -> 젠 example."},
    "ying": {"hangul": "잉", "kind": "direct_table_entry",
             "locator": "Chapter 2 Table 5, raw HTML line 1573: zero-initial ying (ing) -> 잉."},
})
# Historical thirty-entry snapshot; current capture support also includes the
# bounded component rules below, without enumerating a legal Pinyin universe.
CURRENT_RULE_SYLLABLES = frozenset(SYLLABLES)


COMPONENT_RULE_VERSION = "nikl-table5-components-v1"
# Captured NIKL Table 5, raw HTML line 1573; the note at 1578 distinguishes
# standalone forms from forms after a consonant. These are rule components,
# not a Cartesian-product catalogue of legal Mandarin syllables.
INITIALS = {
    "b": "ㅂ", "p": "ㅍ", "m": "ㅁ", "f": "ㅍ", "d": "ㄷ", "t": "ㅌ", "n": "ㄴ", "l": "ㄹ",
    "g": "ㄱ", "k": "ㅋ", "h": "ㅎ", "j": "ㅈ", "q": "ㅊ", "x": "ㅅ", "zh": "ㅈ", "ch": "ㅊ",
    "sh": "ㅅ", "r": "ㄹ", "z": "ㅉ", "c": "ㅊ", "s": "ㅆ",
}
# (standalone spelling, printed post-initial aliases, standalone Hangul,
# post-initial Hangul). Keep all 38 actual rows, including differing u forms.
FINAL_ROWS = (
    ("a", (), "아", "아"), ("o", (), "오", "오"), ("e", (), "어", "어"), ("ê", (), "에", "에"),
    ("yi", ("i",), "이", "이"), ("wu", ("u",), "우", "우"), ("yu", ("u",), "위", "위"),
    ("ai", (), "아이", "아이"), ("ei", (), "에이", "에이"), ("ao", (), "아오", "아오"),
    ("ou", (), "어우", "어우"), ("an", (), "안", "안"), ("en", (), "언", "언"),
    ("ang", (), "앙", "앙"), ("eng", (), "엉", "엉"), ("er", ("r",), "얼", "얼"),
    ("yai", (), "야이", "야이"), ("yao", ("iao",), "야오", "야오"),
    ("you", ("iou", "iu"), "유", "유"), ("yan", ("ian",), "옌", "옌"),
    ("yin", ("in",), "인", "인"), ("yang", ("iang",), "양", "양"), ("ying", ("ing",), "잉", "잉"),
    ("wa", ("ua",), "와", "와"), ("wo", ("uo",), "워", "워"), ("wai", ("uai",), "와이", "와이"),
    ("wei", ("ui",), "웨이", "우이"), ("wan", ("uan",), "완", "완"),
    ("wen", ("un",), "원", "운"), ("wang", ("uang",), "왕", "왕"),
    ("weng", ("ong",), "웡", "웅"), ("yue", ("ue",), "웨", "웨"),
    ("yuan", ("uan",), "위안", "위안"), ("yun", ("un",), "윈", "윈"),
    ("ya", ("ia",), "야", "야"), ("yo", (), "요", "요"), ("ye", ("ie",), "예", "예"),
    ("yong", ("iong",), "융", "융"),
)
_ZERO_INITIAL_FINALS = {row[0]: row for row in FINAL_ROWS}
_UMLAUT_FINALS = {row[1][0]: row for row in FINAL_ROWS if row[0] in {"yu", "yue", "yuan", "yun"}}
_POST_INITIAL_FINALS = {
    alias: row for row in FINAL_ROWS if row[0] not in {"yu", "yue", "yuan", "yun", "er", "yai", "yo"}
    for alias in row[1] or (row[0],)
}
_APICAL_SYLLABLES = {"zhi": "즈", "chi": "츠", "shi": "스", "ri": "르", "zi": "쯔", "ci": "츠", "si": "쓰"}
_MOE_UMLAUT_LOCATOR = (
    " Chinese MOE spelling explanation, requested "
    "https://www.moe.gov.cn/s78/A18/A18_ztzl/jnhypyfa/201805/t20180517_336341.html, "
    "actual HTTP final http://www.moe.gov.cn/s78/A18/A18_ztzl/jnhypyfa/201805/t20180517_336341.html, "
    "body SHA-256 184692fa2fd97dc8b356c5cef1c0e56fec58995de076a1e82fa8c4070a3d484d, "
    "raw HTML line 206: jqxy followed by ü omits the dots."
)


def _component_entry(syllable: str) -> dict[str, str]:
    """Render a confirmed syllable using only table rows and reviewed spelling branches."""
    locator = "Chapter 2 Table 5, raw HTML line 1573; note at raw HTML line 1578: "
    if syllable in _APICAL_SYLLABLES:
        hangul = _APICAL_SYLLABLES[syllable]
        locator += f"initial {syllable[:-1]} [{syllable}] -> [{hangul}]; bracketed independent syllable."
        kind = "direct_table_entry"
    elif syllable in _ZERO_INITIAL_FINALS:
        row = _ZERO_INITIAL_FINALS[syllable]
        hangul = row[2]
        locator += f"final {syllable} -> {hangul}; standalone zero-initial form."
        kind = "direct_table_entry"
    else:
        initial = next((key for key in sorted(INITIALS, key=len, reverse=True) if syllable.startswith(key)), "")
        final = syllable[len(initial):]
        row = None
        spelling_locator = ""
        if initial in {"j", "q", "x"} and final in _UMLAUT_FINALS:
            row = _UMLAUT_FINALS[final]
            spelling_locator = _MOE_UMLAUT_LOCATOR
        elif initial in {"n", "l"} and final.startswith("ü"):
            row = _UMLAUT_FINALS.get("u" + final[1:])
            spelling_locator = " Written ü selects the rounded final, distinct from wu/u." + _MOE_UMLAUT_LOCATOR
        elif initial:
            row = _POST_INITIAL_FINALS.get(final)
        if row is None:
            raise ValueError("unknown or uncovered reviewed Hanyu Pinyin syllable")
        onset = INITIALS[initial]
        hangul = row[3]
        # Every table final starts with a precomposed vowel syllable (initial ㅇ).
        offset = ord(hangul[0]) - 0xAC00
        vowel, coda = offset // 28 % 21, offset % 28
        simplified = {2: 0, 7: 5, 12: 8, 17: 13}.get(vowel, vowel) if onset in {"ㅈ", "ㅉ", "ㅊ"} else vowel
        hangul = chr(0xAC00 + "ㄱㄲㄴㄷㄸㄹㅁㅂㅃㅅㅆㅇㅈㅉㅊㅋㅌㅍㅎ".index(onset) * 588
                     + simplified * 28 + coda) + hangul[1:]
        cell = row[0] + (f" ({', '.join(row[1])})" if row[1] else "")
        locator += (f"initial {initial} -> {onset} plus final {cell} -> {row[2]}; "
                    f"select post-initial {final} -> {row[3]} under the note, giving {hangul}.")
        if simplified != vowel:
            locator += " Chapter 3 Chinese section item 2, raw HTML line 6707: simplify ㅑ/ㅖ/ㅛ/ㅠ after ㅈ/ㅉ/ㅊ to ㅏ/ㅔ/ㅗ/ㅜ."
        locator += spelling_locator
        kind = "reviewed_composition"
    return {"hangul": hangul, "kind": kind, "locator": locator, "method": COMPONENT_RULE_VERSION}


def used_entries(reading_words: list[list[str]]) -> dict[str, dict[str, str]]:
    """Return reproducible rule entries; source and identity approval remain separate."""
    if (not isinstance(reading_words, list) or len(reading_words) != 2
            or any(not isinstance(word, list) or not word for word in reading_words)):
        raise ValueError("a surname and given-name syllable list are required")
    syllables = [syllable for word in reading_words for syllable in word]
    if any(not isinstance(syllable, str) or not syllable for syllable in syllables):
        raise ValueError("unknown or invalid reviewed Hanyu Pinyin syllable")
    return {syllable: deepcopy(SYLLABLES[syllable]) if syllable in SYLLABLES else _component_entry(syllable)
            for syllable in syllables}


def render_name(reading_words: list[list[str]]) -> str:
    """Join reviewed surname and given syllables in the project's player format."""
    entries = used_entries(reading_words)
    return "".join(entries[syllable]["hangul"] for word in reading_words for syllable in word)
