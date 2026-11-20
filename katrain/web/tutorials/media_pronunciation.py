"""Go-specific speech spelling, kept separate from saved narration and captions."""

import hashlib
import json
import re
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=1)
def pronunciation_lexicon():
    return json.loads(Path(__file__).with_name("go_pronunciations.json").read_text(encoding="utf-8"))


def _apply_speech_rules(text, voice):
    lexicon = pronunciation_lexicon()
    if not voice.startswith(lexicon["locale"] + "-"):
        return text, []
    overrides = {r["term"]: r for r in lexicon["terms"] if r.get("tts_text")}
    if not overrides:
        return text, []
    applied = {}

    def term_pattern(term):
        pattern = re.escape(term)
        scope = overrides[term].get("match_scope")
        if scope == "stone_number":
            # A label's entire numeral must be 1, never the prefix of 10/11/一百.
            pattern += r"(?![A-Za-z0-9０-９零〇一二两三四五六七八九十百千万亿壹贰叁肆伍陆柒捌玖拾佰仟萬億])"
        elif scope == "territory_compound":
            # E.g. 真[实空]间 and 黑[空三角] still describe empty space/shape.
            pattern += r"(?!间|点|交叉点|邻点|盘|棋盘|三角|旷)"
        elif scope is not None:
            raise ValueError("Unknown TTS pronunciation match scope")
        return pattern

    def replace(match):
        term = match.group()
        entry = overrides[term]
        spoken = entry["tts_text"]
        if len(term) < 2 or len(term) != len(spoken) or not term.isalnum() or not spoken.isalnum():
            raise ValueError("TTS pronunciation overrides must preserve alphanumeric character count")
        applied[term] = {k: entry[k] for k in ("term", "pinyin", "tts_text", "match_scope") if k in entry}
        return spoken

    pattern = "|".join(term_pattern(t) for t in sorted(overrides, key=len, reverse=True))
    spoken = re.sub(pattern, replace, text)
    return spoken, [applied[k] for k in sorted(applied)]


def matched_pronunciation_rules(text, voice):
    """Return only effective rules actually matched by this narration and voice."""
    return _apply_speech_rules(text, voice)[1]


def prepare_speech(text, voice):
    """Apply explicit TTS spellings and fingerprint only the matched rules."""
    spoken, applied = _apply_speech_rules(text, voice)
    if not applied:
        return text, None
    recipe = {"schema_version": pronunciation_lexicon()["schema_version"], "terms": applied}
    fingerprint = hashlib.sha256(json.dumps(recipe, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    return spoken, fingerprint


def restore_boundary_text(original, spoken, boundaries):
    """Restore original glyphs while retaining every actual TTS time boundary."""
    letters = lambda text: "".join(c for c in text if c.isalnum())
    expected = letters(spoken)
    actual = "".join(letters(b["text"]) for b in boundaries)
    source = letters(original)
    if actual != expected or len(source) != len(expected):
        raise ValueError("TTS pronunciation boundaries do not match the exact synthesis text")
    result, cursor = [], 0
    for boundary in boundaries:
        count = len(letters(boundary["text"]))
        result.append({**boundary, "text": source[cursor : cursor + count]})
        cursor += count
    return result


def pronunciation_is_current(text, voice, audio, timing):
    _, fingerprint = prepare_speech(text, voice)
    return (audio or {}).get("pronunciation_sha256") == fingerprint == (timing or {}).get("pronunciation_sha256")
