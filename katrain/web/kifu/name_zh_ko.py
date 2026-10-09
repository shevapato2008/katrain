"""The reviewed, finite NIKL Chinese player-name rule used by the first batch.

These entries transcribe *verified* Hanyu Pinyin. They never derive a reading
from Han characters or assert that NIKL endorsed an individual player name.
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

# Every entry has an exact source locator. Only syllables in the independently
# reviewed first batch are frozen here; a new name needs a new rule review.
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


def used_entries(reading_words: list[list[str]]) -> dict[str, dict[str, str]]:
    """Return the exact finite source entries used in a segmented reading."""
    if (not isinstance(reading_words, list) or len(reading_words) != 2
            or any(not isinstance(word, list) or not word for word in reading_words)):
        raise ValueError("a surname and given-name syllable list are required")
    syllables = [syllable for word in reading_words for syllable in word]
    if any(not isinstance(syllable, str) or syllable not in SYLLABLES for syllable in syllables):
        raise ValueError("unknown or invalid reviewed Hanyu Pinyin syllable")
    return {syllable: deepcopy(SYLLABLES[syllable]) for syllable in syllables}


def render_name(reading_words: list[list[str]]) -> str:
    """Join reviewed surname and given syllables in the project's player format."""
    entries = used_entries(reading_words)
    return "".join(entries[syllable]["hangul"] for word in reading_words for syllable in word)
