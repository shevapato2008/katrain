import asyncio
import sys
from types import SimpleNamespace

import pytest

from katrain.web.tutorials.media_timing import VOICE, align_boundary_spans, synthesize_audio


def test_capture_pronunciation_keeps_display_text_and_real_word_timing(tmp_path, monkeypatch):
    calls = []

    class Communicate:
        def __init__(self, text, voice, **kwargs):
            calls.append((text, voice, kwargs))

        async def stream(self):
            yield {"type": "audio", "data": b"audio"}
            for i, text in enumerate(["黑衣", "提", "籽", "再", "提籽"]):
                yield {"type": "WordBoundary", "text": text, "offset": i * 1000000, "duration": 800000}

    monkeypatch.setitem(sys.modules, "edge_tts", SimpleNamespace(Communicate=Communicate))
    narration = "黑1提子，再提子。"
    boundaries = asyncio.run(synthesize_audio(narration, VOICE, tmp_path / "audio.mp3"))
    assert calls == [("黑衣提籽，再提籽。", VOICE, {"boundary": "WordBoundary"})]
    assert [b["text"] for b in boundaries] == ["黑1", "提", "子", "再", "提子"]
    assert [(b["start_ms"], b["duration_ms"]) for b in boundaries] == [(i * 100, 80) for i in range(5)]
    assert len(align_boundary_spans(narration, boundaries)) == 5


def test_pronunciation_is_term_scoped_not_a_global_zi_replacement():
    from katrain.web.tutorials.media_pronunciation import prepare_speech

    text = "这样子拿起棋子，再提子。"
    spoken, recipe = prepare_speech(text, VOICE)
    assert spoken == "这样子拿起棋子，再提籽。"
    assert recipe and len(recipe) == 64
    assert prepare_speech("这样子拿起棋子。", VOICE) == ("这样子拿起棋子。", None)
    assert prepare_speech(text, "en-US-AriaNeural") == (text, None)


def test_changed_boundary_text_is_rejected_instead_of_guessing_timing(tmp_path, monkeypatch):
    class Communicate:
        def __init__(self, *args, **kwargs):
            pass

        async def stream(self):
            yield {"type": "audio", "data": b"audio"}
            yield {"type": "WordBoundary", "text": "其他文字", "offset": 0, "duration": 1000000}

    monkeypatch.setitem(sys.modules, "edge_tts", SimpleNamespace(Communicate=Communicate))
    with pytest.raises(ValueError, match="pronunciation"):
        asyncio.run(synthesize_audio("提子", VOICE, tmp_path / "audio.mp3"))


def test_single_character_override_cannot_change_unrelated_words(monkeypatch):
    from katrain.web.tutorials import media_pronunciation

    monkeypatch.setattr(
        media_pronunciation,
        "pronunciation_lexicon",
        lambda: {"schema_version": 1, "locale": "zh-CN", "terms": [{"term": "子", "pinyin": "zǐ", "tts_text": "籽"}]},
    )
    with pytest.raises(ValueError, match="pronunciation"):
        media_pronunciation.prepare_speech("这样子", VOICE)


@pytest.mark.parametrize("term,spoken", [("黑一", "黑衣"), ("白一", "白衣"), ("黑1", "黑衣"), ("白1", "白衣")])
def test_number_one_is_a_first_tone_identifier(term, spoken):
    from katrain.web.tutorials.media_pronunciation import prepare_speech

    text = f"先看{term}，{term}下在左边，再看{term}提子。"
    expected = f"先看{spoken}，{spoken}下在左边，再看{spoken}提籽。"
    assert prepare_speech(text, VOICE)[0] == expected


def test_number_one_override_does_not_match_longer_numbers_or_unrelated_yi():
    from katrain.web.tutorials.media_pronunciation import prepare_speech

    text = "黑10、黑11、黑一百、白10、白11、白一百、黑1A、白一百零一。只剩一口气，一起看一下这样子。"
    assert prepare_speech(text, VOICE) == (text, None)


def test_numbered_stone_boundary_text_restores_original_labels_and_times(tmp_path, monkeypatch):
    calls = []

    class Communicate:
        def __init__(self, text, voice, **kwargs):
            calls.append(text)

        async def stream(self):
            yield {"type": "audio", "data": b"audio"}
            for i, text in enumerate(["黑", "衣", "白衣", "黑衣", "白", "衣", "提籽"]):
                yield {"type": "WordBoundary", "text": text, "offset": (i + 1) * 1000000, "duration": 700000}

    monkeypatch.setitem(sys.modules, "edge_tts", SimpleNamespace(Communicate=Communicate))
    narration = "黑一，白一；黑1，白1提子。"
    boundaries = asyncio.run(synthesize_audio(narration, VOICE, tmp_path / "audio.mp3"))
    assert calls == ["黑衣，白衣；黑衣，白衣提籽。"]
    assert [b["text"] for b in boundaries] == ["黑", "一", "白一", "黑1", "白", "1", "提子"]
    assert [(b["start_ms"], b["duration_ms"]) for b in boundaries] == [((i + 1) * 100, 70) for i in range(7)]
    assert len(align_boundary_spans(narration, boundaries)) == 7


def test_matching_api_and_new_rules_invalidate_only_affected_audio(monkeypatch):
    from katrain.web.tutorials import media_pronunciation

    lexicon = media_pronunciation.pronunciation_lexicon()
    latest = {**lexicon, "terms": list(lexicon["terms"])}
    old = {**lexicon, "terms": [entry for entry in lexicon["terms"] if entry.get("match_scope") != "stone_number"]}
    monkeypatch.setattr(media_pronunciation, "pronunciation_lexicon", lambda: old)
    capture_sha = media_pronunciation.prepare_speech("提子。", VOICE)[1]
    old_affected_sha = media_pronunciation.prepare_speech("黑一提子。", VOICE)[1]
    monkeypatch.setattr(media_pronunciation, "pronunciation_lexicon", lambda: latest)

    matches = media_pronunciation.matched_pronunciation_rules("黑一、白1提子；黑11还有一口气。", VOICE)
    assert {entry["term"] for entry in matches} == {"黑一", "白1", "提子"}
    assert media_pronunciation.matched_pronunciation_rules("黑11，还有一口气。", VOICE) == []
    assert media_pronunciation.matched_pronunciation_rules("黑一提子。", "en-US-AriaNeural") == []
    assert media_pronunciation.prepare_speech("提子。", VOICE)[1] == capture_sha
    assert media_pronunciation.pronunciation_is_current(
        "提子。", VOICE, {"pronunciation_sha256": capture_sha}, {"pronunciation_sha256": capture_sha}
    )
    assert media_pronunciation.pronunciation_is_current("一口气。", VOICE, {}, {})
    assert not media_pronunciation.pronunciation_is_current(
        "黑一提子。", VOICE, {"pronunciation_sha256": old_affected_sha}, {"pronunciation_sha256": old_affected_sha}
    )
    current_sha = media_pronunciation.prepare_speech("黑一提子。", VOICE)[1]
    assert media_pronunciation.pronunciation_is_current(
        "黑一提子。", VOICE, {"pronunciation_sha256": current_sha}, {"pronunciation_sha256": current_sha}
    )
    assert not media_pronunciation.pronunciation_is_current(
        "黑一提子。", VOICE, {"pronunciation_sha256": current_sha}, {}
    )


def test_territory_and_counting_action_have_explicit_tts_pronunciations():
    from katrain.web.tutorials.media_pronunciation import prepare_speech

    text = "比较黑空与白空，确认实空。先学数目方法，再开始数目，双方进行数目。"
    spoken, fingerprint = prepare_speech(text, VOICE)
    assert spoken == "比较黑控与白控，确认实控。先学鼠目方法，再开始鼠目，双方进行鼠目。"
    assert fingerprint and len(fingerprint) == 64
    assert prepare_speech(text, "en-US-AriaNeural") == (text, None)


def test_territory_rules_preserve_empty_points_and_quantity_nouns():
    from katrain.web.tutorials.media_pronunciation import prepare_speech

    text = "观察真实空间，包围空间；避免黑空三角、白空三角。数空点时注意棋子数目和目数。"
    assert prepare_speech(text, VOICE) == (text, None)
    assert prepare_speech("黑空的空点与白空的边界。", VOICE)[0] == "黑控的空点与白控的边界。"


def test_new_pronunciations_restore_original_captions_without_retiming():
    from katrain.web.tutorials.media_pronunciation import prepare_speech, restore_boundary_text

    original = "黑空，开始数目。"
    spoken, _ = prepare_speech(original, VOICE)
    boundaries = [
        {"text": "黑控", "start_ms": 120, "duration_ms": 200},
        {"text": "开始", "start_ms": 450, "duration_ms": 180},
        {"text": "鼠目", "start_ms": 700, "duration_ms": 210},
    ]
    restored = restore_boundary_text(original, spoken, boundaries)
    assert [b["text"] for b in restored] == ["黑空", "开始", "数目"]
    assert [(b["start_ms"], b["duration_ms"]) for b in restored] == [(120, 200), (450, 180), (700, 210)]
