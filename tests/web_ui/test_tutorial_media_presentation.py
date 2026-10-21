"""Recording presentation is separate from source board/rule replay authority."""

import copy
import hashlib

import pytest

from katrain.web.tutorials.media_timing import build_step_cues, narration_hash, digest


def diagram():
    return {
        "schema_version": 2,
        "size": 9,
        "stones": {"B": [[8, 8], [1, 1], [3, 1]], "W": [[0, 1], [2, 1], [4, 1]]},
        "labels": {f"{i},1": str(i + 1) for i in range(5)},
        "letters": {},
        "shapes": {},
        "unknown_stones": [],
        "source_region": {"col": 0, "row": 0, "cols": 9, "rows": 9, "confirmed": False},
        "replay": {"status": "needs_calibration"},
    }


def timing(text, words=None):
    words = words or list(text)
    return {
        "schema_version": 1,
        "audio_sha256": hashlib.sha256(b"audio").hexdigest(),
        "narration_sha256": narration_hash(text),
        "voice": "test",
        "duration_ms": 10000,
        "boundaries": [{"text": word, "start_ms": 100 + i * 200, "duration_ms": 150} for i, word in enumerate(words)],
    }


def build(payload, text, **kwargs):
    return build_step_cues(payload, text, timing(text), **kwargs)


def test_saved_numbered_diagram_has_background_then_exact_spoken_end_cumulative_frames():
    value = diagram()
    before = copy.deepcopy(value)
    text = "白1，黑2，白3，黑4，白5。"
    result = build(value, text)
    assert result["status"] == "complete", result
    assert result["mode"] == "presentation"
    assert result["frames"][0]["payload"]["stones"] == {"B": [[8, 8]], "W": []}
    assert result["frames"][0]["payload"]["labels"] == {}
    assert [cue["at_ms"] for cue in result["cues"]] == [0, 450, 1050, 1650, 2250, 2850]
    for count, frame in enumerate(result["frames"]):
        assert len(frame["payload"]["labels"]) == count
        assert sum(map(len, frame["payload"]["stones"].values())) == count + 1
    assert result["frames"][-1]["payload"]["stones"] == value["stones"]
    assert result["frames"][-1]["payload"]["labels"] == value["labels"]
    assert value == before


def test_marked_stone_and_empty_letter_do_not_reveal_other_markers_or_click_twice():
    value = diagram()
    value["labels"] = {}
    value["shapes"] = {"1,1": "triangle"}
    value["letters"] = {"1,1": "A", "6,6": "B"}
    text = "黑三角，A，B，再看黑三角。"
    result = build(value, text)
    assert result["status"] == "complete", result
    initial, shape, letter, independent = result["frames"]
    assert [1, 1] not in initial["payload"]["stones"]["B"]
    assert shape["payload"]["shapes"] == {"1,1": "triangle"}
    assert shape["payload"]["letters"] == {}
    assert letter["payload"]["letters"] == {"1,1": "A"}
    assert independent["payload"]["letters"] == {"1,1": "A", "6,6": "B"}
    assert independent["payload"]["stones"] == shape["payload"]["stones"]
    from katrain.web.tutorials.media_render import _stone_click_times, PLACEMENT_DURATION_MS

    assert _stone_click_times(result["frames"], result, 10000) == [result["events"][0]["at_ms"] + PLACEMENT_DURATION_MS]


@pytest.mark.parametrize("text", ["白1，白3，黑2，黑4，白5。", "白1，黑2，白5。", "白1到白5。"])
def test_missing_or_out_of_order_numbers_never_complete_or_fall_back(text):
    result = build(diagram(), text)
    assert result["status"] == "pending"
    assert result["reason"]
    assert result["frames"] == []


def test_repeated_number_is_ignored_after_first_reference():
    result = build(diagram(), "白1，黑2，白3，黑4，白5，再看白1。")
    assert result["status"] == "complete", result
    assert len(result["events"]) == 5


def test_same_shape_at_two_points_needs_explicit_mapping():
    value = diagram()
    value["labels"] = {}
    value["shapes"] = {"0,1": "triangle", "1,1": "triangle"}
    text = "三角。"
    assert build(value, text)["status"] == "pending"
    plan = {"schema_version": 1, "bindings": [{"span": [0, 2], "object_ids": ["shapes:0,1", "shapes:1,1"]}]}
    result = build(value, text, presentation_plan=plan)
    assert result["status"] == "complete", result
    assert len(result["events"]) == 1
    assert result["frames"][-1]["payload"]["shapes"] == value["shapes"]


def test_symbol_cannot_reveal_later_numbered_stone_early():
    value = diagram()
    value["shapes"] = {"1,1": "triangle"}
    result = build(value, "黑三角，白1，黑2，白3，黑4，白5。")
    assert result["status"] == "pending"
    assert "number" in result["reason"].lower()


@pytest.mark.parametrize(
    "binding",
    [
        {"span": [-1, 2], "object_ids": ["labels:0,1"]},
        {"span": [0, 200], "object_ids": ["labels:0,1"]},
        {"span": [0, 0], "object_ids": ["labels:0,1"]},
        {"span": [0, 2], "object_ids": ["invented"]},
        {"span": [0, 2], "object_ids": ["labels:0,1", "labels:0,1"]},
    ],
)
def test_invalid_or_incomplete_explicit_bindings_rejected(binding):
    result = build(diagram(), "白1。", presentation_plan={"schema_version": 1, "bindings": [binding]})
    assert result["status"] == "pending"


def test_stale_text_and_bad_real_word_end_are_rejected():
    text = "白1，黑2，白3，黑4，白5。"
    stale = timing(text)
    stale["narration_sha256"] = "0" * 64
    assert build_step_cues(diagram(), text, stale)["status"] == "pending"
    stale = timing(text)
    stale["boundaries"][0]["duration_ms"] = -1
    assert build_step_cues(diagram(), text, stale)["status"] == "pending"


def test_no_annotations_can_be_static_but_metaphor_cannot_invent_markers():
    value = diagram()
    value["labels"] = {}
    result = build(value, "这个愚形三角需要避免。")
    assert result["mode"] == "static" and result["status"] == "complete"
    assert result["objects"] == [] and len(result["frames"]) == 1


def test_source_bound_arrow_adds_no_stone_and_rejects_foreign_image():
    value = diagram()
    value["labels"] = {}
    source = {"source_pointer": "/chapters/0/figures/0", "image_sha256": "a" * 64}
    arrow = {"id": "arrow:direction", "from": [0, 0], "to": [2, 2], **source}
    plan = {"schema_version": 1, "arrows": [arrow], "bindings": [{"span": [0, 2], "object_ids": ["arrow:direction"]}]}
    result = build(value, "箭头。", presentation_plan=plan, source_identity=source)
    assert result["status"] == "complete", result
    assert result["frames"][-1]["payload"]["stones"] == result["frames"][0]["payload"]["stones"]
    assert result["frames"][-1]["payload"]["presentation_arrows"] == [arrow]
    from katrain.web.tutorials.media_render import _stone_click_times

    assert _stone_click_times(result["frames"], result, 10000) == []
    assert build(value, "箭头。", presentation_plan=plan)["status"] == "pending"
    assert (
        build(value, "箭头。", presentation_plan=plan, source_identity={**source, "image_sha256": "b" * 64})["status"]
        == "pending"
    )


def test_real_replay_keeps_capture_pass_and_reuse_after_exact_end_cues():
    from tests.web_ui.test_tutorial_media import board

    value = board()
    before = copy.deepcopy(value)
    result = build(value, "黑41，白42，再看黑43。")
    assert result["status"] == "complete", result
    assert result["mode"] == "replay"
    assert result["frames"][1]["captured"] == [[1, 1]]
    assert result["frames"][2]["currentMove"]["kind"] == "pass"
    assert {tuple(p) for p in result["frames"][-1]["payload"]["stones"]["B"]} == {
        tuple(p) for p in value["stones"]["B"]
    }
    assert value == before


def test_renderer_checks_recomputed_presentation_proof_and_frames(tmp_path):
    from katrain.web.tutorials.media_render import _validate_inputs

    value = diagram()
    text = "白1，黑2，白3，黑4，白5。"
    speech = timing(text)
    proof = build_step_cues(value, text, speech)
    audio = tmp_path / "audio.mp3"
    audio.write_bytes(b"audio")
    assert _validate_inputs(text, value, proof["frames"], speech, proof, audio, "2d") == 10000
    forged = copy.deepcopy(proof["frames"])
    forged[0]["payload"]["stones"]["W"].append([0, 1])
    with pytest.raises(ValueError, match="presentation|proof|snapshot"):
        _validate_inputs(text, value, forged, speech, proof, audio, "2d")
    proof["events"][0]["at_ms"] -= 100
    with pytest.raises(ValueError, match="presentation|proof|snapshot"):
        _validate_inputs(text, value, proof["frames"], speech, proof, audio, "2d")


def test_pending_required_objects_cannot_render_static(tmp_path):
    from katrain.web.tutorials.media_render import _validate_inputs

    text = "背景。"
    value = diagram()
    speech = timing(text)
    proof = build_step_cues(value, text, speech)
    audio = tmp_path / "audio.mp3"
    audio.write_bytes(b"audio")
    with pytest.raises(ValueError, match="presentation|reference|cue"):
        _validate_inputs(text, value, [], speech, proof, audio, "2d")


def test_video_never_synthesizes_missing_or_stale_audio(tmp_path, monkeypatch):
    from katrain.web.tutorials.media_tasks import MediaWorker

    worker = MediaWorker(lambda: None, storage=object())
    monkeypatch.setattr(worker, "_stage", lambda *args: None)

    async def forbidden(*args):
        pytest.fail("A video task must never synthesize audio")

    monkeypatch.setattr(worker, "_speech", forbidden)
    snapshot = {"narration": "背景。", "voice": "test", "book_slug": "test", "board_payload": diagram()}
    with pytest.raises(RuntimeError, match="completed audio"):
        worker._generate("id", snapshot, "video", "2d", tmp_path)


def test_source_bound_explicit_numeric_choice_annotations_are_not_moves():
    value = diagram()
    value["labels"] = {"0,1": "1", "2,1": "1"}  # Printed alternative selection labels, same color.
    text = "左侧1，右侧1。"
    source = {"source_pointer": "/choices/0", "image_sha256": "a" * 64}
    plan = {
        "schema_version": 1,
        "annotation_object_ids": ["labels:0,1", "labels:2,1"],
        "bindings": [{"span": [0, 3], "object_ids": ["labels:0,1"]}, {"span": [4, 7], "object_ids": ["labels:2,1"]}],
    }
    assert build(value, text)["status"] == "pending"
    assert build(value, text, presentation_plan=plan)["status"] == "pending"
    result = build(value, text, presentation_plan=plan, source_identity=source)
    assert result["status"] == "complete", result
    assert [obj["role"] for obj in result["objects"]] == ["annotation", "annotation"]
    assert len(result["events"]) == 2


def test_multiple_numbered_moves_in_one_real_word_boundary_must_revise_audio():
    text = "白1，黑2，白3，黑4，白5。"
    result = build_step_cues(diagram(), text, timing(text, [text]))
    assert result["status"] == "pending"
    assert "distinct" in result["reason"]


@pytest.mark.parametrize("field", ["voice", "narration_sha256", "duration_ms"])
def test_video_rejects_audio_metadata_inconsistent_with_its_own_timing(tmp_path, monkeypatch, field):
    from katrain.web.tutorials.media_tasks import MediaWorker

    worker = MediaWorker(lambda: None, storage=object())
    monkeypatch.setattr(worker, "_stage", lambda *args: None)
    text = "背景。"
    speech = timing(text)
    audio = {
        "asset": "audio.mp3",
        "sha256": speech["audio_sha256"],
        "voice": speech["voice"],
        "narration_sha256": speech["narration_sha256"],
        "duration_ms": speech["duration_ms"],
    }
    audio[field] = 20000 if field == "duration_ms" else "stale"
    snapshot = {
        "narration": text,
        "voice": "test",
        "book_slug": "test",
        "audio": audio,
        "speech_timing": speech,
        "audio_asset": "audio.mp3",
        "board_payload": diagram(),
    }
    with pytest.raises(RuntimeError, match="completed audio"):
        worker._generate("id", snapshot, "video", "2d", tmp_path)


def captured_number_board():
    # White 1 at the corner is later captured by black 2; no final white label survives.
    return {
        "schema_version": 2,
        "size": 9,
        "stones": {"B": [[1, 0], [0, 1]], "W": []},
        "labels": {"0,1": "2"},
        "unknown_stones": [],
        "source_region": {"col": 0, "row": 0, "cols": 9, "rows": 9, "confirmed": True},
        "replay": {
            "status": "complete",
            "initial": {
                "stones": {"B": [[1, 0]], "W": []},
                "unknown_stones": [],
                "known_region": {"col": 0, "row": 0, "cols": 9, "rows": 9},
                "to_play": "W",
            },
            "moves": [
                {"kind": "move", "color": "W", "point": [0, 0], "printed_number": "1"},
                {"kind": "move", "color": "B", "point": [0, 1], "printed_number": "2"},
            ],
            "evidence": {"kind": "source", "source_pointer": "/local/0", "description": "checked"},
        },
    }


def test_captured_numbered_replay_move_keeps_its_printed_label_until_capture():
    value = captured_number_board()
    result = build(value, "白1，黑2。")
    assert result["status"] == "complete", result
    assert result["frames"][1]["payload"]["stones"]["W"] == [[0, 0]]
    assert result["frames"][1]["payload"]["labels"] == {"0,0": "1"}
    assert result["frames"][2]["payload"]["stones"]["W"] == []
    assert result["frames"][2]["payload"]["labels"] == {"0,1": "2"}
    assert result["frames"][2]["captured"] == [[0, 0]]


def test_initial_only_marker_is_discovered_hidden_then_revealed_without_changing_capture_rules():
    value = captured_number_board()
    value["replay"]["initial"]["stones"]["W"] = [[0, 0]]
    value["replay"]["initial"]["shapes"] = {"0,0": "triangle"}
    value["replay"]["initial"]["to_play"] = "B"
    value["replay"]["moves"] = value["replay"]["moves"][1:]
    before = copy.deepcopy(value)
    assert build(value, "黑2。")["status"] == "pending"
    result = build(value, "白三角，黑2。")
    assert result["status"] == "complete", result
    assert any(obj["kind"] == "shapes" and obj["value"] == "triangle" for obj in result["objects"])
    assert result["frames"][0]["payload"]["stones"]["W"] == []
    assert result["frames"][0]["payload"]["shapes"] == {}
    assert result["frames"][1]["payload"]["stones"]["W"] == [[0, 0]]
    assert result["frames"][1]["payload"]["shapes"] == {"0,0": "triangle"}
    assert result["frames"][-1]["payload"]["stones"]["W"] == []
    assert result["frames"][-1]["payload"]["shapes"] == {}
    assert result["frames"][-1]["captured"] == [[0, 0]]
    assert value == before


@pytest.mark.parametrize("text", ["白一，黑二，白三，黑四，白五。", "白1，黑二，白3，黑四，白五。"])
def test_chinese_printed_number_aliases_reuse_exact_speech_end_boundaries(text):
    result = build(diagram(), text)
    assert result["status"] == "complete", result
    assert [event["at_ms"] for event in result["events"]] == [450, 1050, 1650, 2250, 2850]
    assert result["frames"][-1]["payload"]["labels"] == diagram()["labels"]


def test_two_digit_chinese_aliases_and_explicit_spans_do_not_require_new_audio():
    value = diagram()
    value["labels"] = {key: str(int(label) + 20) for key, label in value["labels"].items()}
    text = "白二十一，黑二十二，白二十三，黑二十四，白二十五。"
    plan = {
        "schema_version": 1,
        "bindings": [{"span": [i * 5, i * 5 + 4], "object_ids": [f"labels:{i},1"]} for i in range(5)],
    }
    proof = build(value, text, presentation_plan=plan)
    assert proof["status"] == "complete", proof
    assert [event["at_ms"] for event in proof["events"]] == [850, 1850, 2850, 3850, 4850]


def test_chinese_alias_boundaries_do_not_match_prefix_of_another_number():
    from katrain.web.tutorials.media_presentation import _matches

    assert [match.group() for match in _matches({"number": 11, "stone_color": "B"}, "黑十一。")] == ["黑十一"]
    for number, text in [(1, "黑十一"), (2, "黑二十三"), (11, "黑一百一十一"), (1, "黑一2")]:
        assert _matches({"number": number, "stone_color": "B"}, text) == []
    assert build(diagram(), "白一到白五。")["status"] == "pending"


@pytest.mark.parametrize("explicit", [False, True])
def test_first_descriptive_number_and_color_reference_uses_original_speech_end(explicit):
    text = "请看左下角，标着数字一的是黑子。黑一。"
    value = diagram()
    value.update(stones={"B": [[3, 1]], "W": []}, labels={"3,1": "1"})
    words = ["请", "看", "左下角", "标", "着", "数字", "一", "的", "是", "黑子", "黑", "一"]
    starts = [100, 300, 538, 1488, 1688, 1800, 2150, 2312, 2412, 2550, 3625, 3875]
    durations = [200, 212, 712, 200, 100, 350, 162, 100, 125, 500, 250, 125]
    speech = timing(text)
    speech["boundaries"] = [
        {"text": word, "start_ms": start, "duration_ms": duration}
        for word, start, duration in zip(words, starts, durations)
    ]
    plan = {"schema_version": 1, "bindings": [{"span": [6, 15], "object_ids": ["labels:3,1"]}]}
    original = copy.deepcopy(value)
    result = build_step_cues(value, text, speech, presentation_plan=plan if explicit else None)
    assert result["status"] == "complete", result
    assert [(event["span"], event["at_ms"]) for event in result["events"]] == [([6, 15], 3050)]
    assert result["frames"][0]["payload"]["stones"]["B"] == []
    assert result["frames"][1]["payload"]["labels"] == {"3,1": "1"}
    assert value == original


@pytest.mark.parametrize("number,token,color", [(1, "1", "B"), (11, "十一", "B"), (23, "二十三", "W")])
def test_literal_descriptive_reference_accepts_exact_arabic_and_chinese_numbers(number, token, color):
    from katrain.web.tutorials.media_presentation import _matches

    phrase = f"标着数字{token}的是{'黑' if color == 'B' else '白'}子"
    assert [match.group() for match in _matches({"number": number, "stone_color": color}, phrase + "。")] == [phrase]


@pytest.mark.parametrize(
    "phrase",
    [
        "标着数字一的是白子。",
        "标着数字十一的是黑子。",
        "标着数字11的是黑子。",
        "数字一旁边的是黑子。",
        "不是标着数字一的是黑子。",
        "可能标着数字一的是黑子。",
        "标着数字一的是黑子吗？",
        "标着数字一的是黑子或白子。",
        "标着数字一的是黑子，还是白子。",
    ],
)
def test_descriptive_reference_does_not_guess_color_number_negation_or_alternatives(phrase):
    from katrain.web.tutorials.media_presentation import _matches

    assert _matches({"number": 1, "stone_color": "B"}, phrase) == []
    value = diagram()
    value.update(stones={"B": [[3, 1]], "W": []}, labels={"3,1": "1"})
    plan = {"schema_version": 1, "bindings": [{"span": [0, len(phrase)], "object_ids": ["labels:3,1"]}]}
    assert build(value, phrase, presentation_plan=plan)["status"] == "pending"
    if "标着" in phrase:
        start = phrase.index("标着")
        plan["bindings"][0]["span"] = [start, start + len("标着数字一的是黑子")]
        assert build(value, phrase, presentation_plan=plan)["status"] == "pending"


@pytest.mark.parametrize("prefix", ["可能，", "假设：", "不一定，", "可能，请看左下角，"])
@pytest.mark.parametrize("explicit", [False, True])
def test_reverse_reference_keeps_qualifiers_across_commas_and_colons(prefix, explicit):
    phrase = "标着数字一的是黑子"
    text = prefix + phrase + "。"
    value = diagram()
    value.update(stones={"B": [[3, 1]], "W": []}, labels={"3,1": "1"})
    plan = {
        "schema_version": 1,
        "bindings": [{"span": [len(prefix), len(prefix) + len(phrase)], "object_ids": ["labels:3,1"]}],
    }
    assert build(value, text, presentation_plan=plan if explicit else None)["status"] == "pending"


def test_initial_annotation_mentioned_after_capture_or_replacement_is_rejected():
    value = captured_number_board()
    value["replay"]["initial"]["stones"]["W"] = [[0, 0]]
    value["replay"]["initial"]["shapes"] = {"0,0": "triangle"}
    value["replay"]["initial"]["to_play"] = "B"
    value["replay"]["moves"] = value["replay"]["moves"][1:]
    result = build(value, "黑2，白三角。")
    assert result["status"] == "pending"
    assert result["frames"] == []
    assert "lifetime" in result["reason"]


def historical_capture_source():
    value = captured_number_board()
    value["stones"]["W"] = [[0, 0]]
    value["labels"]["0,0"] = "1"  # The book retains the captured historical white stone.
    source = {"source_pointer": "/local/0", "image_sha256": "a" * 64}
    replay = copy.deepcopy(value["replay"])
    value["replay"] = {"status": "needs_calibration", "initial": None, "moves": []}
    plan = {
        "schema_version": 1,
        "bindings": [{"span": [0, 2], "object_ids": ["labels:0,0"]}, {"span": [3, 5], "object_ids": ["labels:0,1"]}],
        "source_replay": {
            "schema_version": 1,
            "initial": replay["initial"],
            "moves": replay["moves"],
            **source,
            "evidence_description": "Source numbered local construction; black 2 captures white 1.",
        },
    }
    return value, plan, source


def test_source_bound_local_sequence_captures_historical_printed_stone_without_mutating_saved_replay():
    from katrain.web.tutorials.replay import validate_replay

    value, plan, source = historical_capture_source()
    before = copy.deepcopy(value)
    proof = build(value, "白1，黑2。", presentation_plan=plan, source_identity=source)
    assert proof["status"] == "complete", proof
    assert proof["mode"] == "source_replay"
    assert proof["frames"][1]["payload"]["labels"] == {"0,0": "1"}
    assert proof["frames"][-1]["captured"] == [[0, 0]]
    assert proof["frames"][-1]["payload"]["stones"]["W"] == []
    assert proof["frames"][-1]["payload"]["labels"] == {"0,1": "2"}
    assert value == before and validate_replay(value)["status"] == "needs_calibration"


@pytest.mark.parametrize(
    "change",
    [
        "no_source",
        "foreign_source",
        "missing_background",
        "invented_initial",
        "wrong_saved_number",
        "unknown",
        "outside_known_region",
    ],
)
def test_source_local_sequence_rejects_unbound_or_replaced_source_data(change):
    value, plan, source = historical_capture_source()
    if change == "no_source":
        source = None
    elif change == "foreign_source":
        source["image_sha256"] = "b" * 64
    elif change == "missing_background":
        plan["source_replay"]["initial"]["stones"]["B"] = []
    elif change == "invented_initial":
        plan["source_replay"]["initial"]["stones"]["B"].append([8, 8])
    elif change == "wrong_saved_number":
        plan["source_replay"]["moves"][0]["printed_number"] = "9"
    elif change == "unknown":
        plan["source_replay"]["initial"]["unknown_stones"] = [{"point": [8, 8], "color": None}]
    elif change == "outside_known_region":
        plan["source_replay"]["initial"]["known_region"] = {"col": 1, "row": 0, "cols": 8, "rows": 9}
    proof = build(value, "白1，黑2。", presentation_plan=plan, source_identity=source)
    assert proof["status"] == "pending"
    assert proof["frames"] == []


def test_source_noted_missing_number_reuses_captured_point_and_preserves_historical_chart():
    # Source-supported local sequence: black 9 captures white 4; black 11 fills that point after white 10.
    points = [
        [2, 15],
        [4, 16],
        [6, 16],
        [2, 16],
        [1, 16],
        [3, 15],
        [2, 17],
        [2, 14],
        [3, 16],
        [1, 15],
        [2, 16],
        [4, 14],
        [4, 17],
        [2, 10],
    ]
    moves = [
        {"kind": "move", "color": "B" if i % 2 == 0 else "W", "point": p, "printed_number": str(i + 1)}
        for i, p in enumerate(points)
    ]
    moves[10]["source_note"] = "黑十一粘劫：在已被黑9提去的白4[2,16]处连接。"
    saved = [(i + 1, m) for i, m in enumerate(moves) if i != 10]
    value = {
        "schema_version": 2,
        "size": 19,
        "unknown_stones": [],
        "stones": {c: [m["point"] for _, m in saved if m["color"] == c] for c in ("B", "W")},
        "labels": {",".join(map(str, m["point"])): str(n) for n, m in saved},
        "replay": {"status": "needs_calibration"},
    }
    source = {"source_pointer": "/figures/7", "image_sha256": "a" * 64}
    text = "，".join(("黑" if m["color"] == "B" else "白") + m["printed_number"] for m in moves) + "。"
    spans = []
    cursor = 0
    for n, m in enumerate(moves, 1):
        end = cursor + 1 + len(m["printed_number"])
        object_id = "replay:11" if n == 11 else "labels:" + ",".join(map(str, m["point"]))
        spans.append({"span": [cursor, end], "object_ids": [object_id]})
        cursor = end + 1
    plan = {
        "schema_version": 1,
        "bindings": spans,
        "source_replay": {
            "schema_version": 1,
            "initial": {
                "stones": {"B": [], "W": []},
                "to_play": "B",
                "unknown_stones": [],
                "known_region": {"col": 0, "row": 9, "cols": 8, "rows": 10},
            },
            "moves": moves,
            **source,
            "evidence_description": "Original local numbered construction and 黑十一粘劫 source note.",
        },
    }
    before = copy.deepcopy(value)
    speech = timing(text)
    speech["duration_ms"] = 20000
    proof = build_step_cues(value, text, speech, presentation_plan=plan, source_identity=source)
    assert proof["status"] == "complete", proof
    assert proof["frames"][9]["captured"] == [[2, 16]]
    assert [2, 16] not in proof["frames"][9]["payload"]["stones"]["W"]
    assert proof["frames"][11]["payload"]["labels"]["2,16"] == "11"
    assert [2, 16] in proof["frames"][11]["payload"]["stones"]["B"]
    assert value == before
    value["shapes"] = {"2,16": "triangle"}
    plan["bindings"][3]["object_ids"].append("shapes:2,16")
    marked = build_step_cues(value, text, speech, presentation_plan=plan, source_identity=source)
    assert marked["status"] == "complete", marked
    assert marked["frames"][4]["payload"]["shapes"] == {"2,16": "triangle"}
    assert marked["frames"][9]["payload"]["shapes"] == {}
    del plan["source_replay"]["moves"][10]["source_note"]
    assert build_step_cues(value, text, speech, presentation_plan=plan, source_identity=source)["status"] == "pending"


def test_source_recording_renderer_accepts_recomputed_rule_frames_and_rejects_restored_historical_stone(tmp_path):
    from katrain.web.tutorials.media_render import _validate_inputs

    value, plan, source = historical_capture_source()
    text = "白1，黑2。"
    speech = timing(text)
    proof = build_step_cues(value, text, speech, presentation_plan=plan, source_identity=source)
    audio = tmp_path / "audio.mp3"
    audio.write_bytes(b"audio")
    assert _validate_inputs(text, value, proof["frames"], speech, proof, audio, "2d") == speech["duration_ms"]
    forged = copy.deepcopy(proof["frames"])
    forged[-1]["payload"]["stones"]["W"] = [[0, 0]]
    with pytest.raises(ValueError, match="proof|snapshot"):
        _validate_inputs(text, value, forged, speech, proof, audio, "2d")


def test_historical_marked_stone_does_not_transfer_to_later_same_color_stone_at_same_point():
    value, plan, source = historical_capture_source()
    for color, points in {"W": [[1, 1], [0, 2]], "B": [[8, 8]]}.items():
        value["stones"][color].extend(points)
    value["labels"]["8,8"] = "4"
    value["shapes"] = {"0,0": "triangle"}
    plan["source_replay"]["initial"]["stones"]["W"] = [[1, 1], [0, 2]]
    plan["source_replay"]["moves"].extend(
        [
            {
                "kind": "pass",
                "color": "W",
                "point": None,
                "printed_number": "3",
                "source_note": "Source explicitly passes.",
            },
            {"kind": "move", "color": "B", "point": [8, 8], "printed_number": "4"},
            {
                "kind": "move",
                "color": "W",
                "point": [0, 0],
                "printed_number": "5",
                "source_note": "Source returns to white 1 after intervening steps.",
            },
        ]
    )
    text = "白1，黑2，白3，黑4，白5，白三角。"
    plan["bindings"] = [
        {"span": [0, 2], "object_ids": ["labels:0,0"]},
        {"span": [3, 5], "object_ids": ["labels:0,1"]},
        {"span": [6, 8], "object_ids": ["replay:3"]},
        {"span": [9, 11], "object_ids": ["labels:8,8"]},
        {"span": [12, 14], "object_ids": ["replay:5"]},
        {"span": [15, 18], "object_ids": ["shapes:0,0"]},
    ]
    result = build(value, text, presentation_plan=plan, source_identity=source)
    assert result["status"] == "pending"
    assert "lifetime" in result["reason"]


@pytest.mark.parametrize("mention_before_capture", [True, False])
def test_source_initial_marked_background_stone_keeps_initial_identity_across_same_color_reuse(mention_before_capture):
    value, plan, source = historical_capture_source()
    value["labels"].pop("0,0")  # This is a marked initial white stone, not white 1.
    value["labels"]["8,8"] = "4"
    value["shapes"] = {"0,0": "triangle"}
    value["stones"]["B"].append([8, 8])
    value["stones"]["W"].extend([[1, 1], [0, 2]])
    local = plan["source_replay"]
    local["initial"]["stones"]["W"] = [[0, 0], [1, 1], [0, 2]]
    local["initial"]["shapes"] = {"0,0": "triangle"}
    local["initial"]["to_play"] = "B"
    local["moves"] = [
        local["moves"][1],
        {
            "kind": "pass",
            "color": "W",
            "point": None,
            "printed_number": "3",
            "source_note": "Source explicitly passes.",
        },
        {"kind": "move", "color": "B", "point": [8, 8], "printed_number": "4"},
        {
            "kind": "move",
            "color": "W",
            "point": [0, 0],
            "printed_number": "5",
            "source_note": "Source returns after intervening steps.",
        },
    ]
    references = [
        ("白三角", "shapes:0,0"),
        ("黑2", "labels:0,1"),
        ("白3", "replay:2"),
        ("黑4", "labels:8,8"),
        ("白5", "replay:4"),
    ]
    if not mention_before_capture:
        references.append(references.pop(0))
    plan["bindings"] = []
    text = ""
    for reference, object_id in references:
        start = len(text)
        text += reference + "，"
        plan["bindings"].append({"span": [start, len(text) - 1], "object_ids": [object_id]})
    before = copy.deepcopy(value)
    proof = build(value, text, presentation_plan=plan, source_identity=source)
    assert value == before
    if mention_before_capture:
        assert proof["status"] == "complete", proof
        assert proof["frames"][0]["payload"]["stones"]["W"] == [[0, 2], [1, 1]]
        assert proof["frames"][0]["payload"]["shapes"] == {}
        assert proof["frames"][1]["payload"]["shapes"] == {"0,0": "triangle"}
        assert proof["frames"][2]["payload"]["shapes"] == {}
        assert proof["frames"][-1]["payload"]["shapes"] == {}
        assert [0, 0] in proof["frames"][-1]["payload"]["stones"]["W"]
    else:
        assert proof["status"] == "pending"
        assert proof["frames"] == []
        assert "lifetime" in proof["reason"]


def test_source_initial_cannot_omit_saved_marked_background_identity_to_attach_it_later():
    value, plan, source = historical_capture_source()
    value["labels"].pop("0,0")
    value["shapes"] = {"0,0": "triangle"}
    local = plan["source_replay"]
    local["initial"]["stones"]["W"] = [[0, 0]]
    local["initial"]["to_play"] = "B"
    local["moves"] = local["moves"][1:]
    local["initial"].pop("shapes", None)
    plan["bindings"] = [{"span": [0, 3], "object_ids": ["shapes:0,0"]}, {"span": [4, 6], "object_ids": ["labels:0,1"]}]
    proof = build(value, "白三角，黑2。", presentation_plan=plan, source_identity=source)
    assert proof["status"] == "pending"
    assert "initial" in proof["reason"].lower()


def test_symbol_background_reveal_lands_without_claiming_an_ordered_move():
    value = diagram()
    value["labels"] = {}
    value["shapes"] = {"1,1": "triangle"}
    proof = build(value, "黑三角。")
    assert proof["status"] == "complete", proof
    frame = proof["frames"][1]
    assert frame["currentMove"] is None and frame["last"] is None
    assert frame["appeared_stones"] == [{"color": "B", "point": [1, 1]}]
    from katrain.web.tutorials.media_render import _stone_click_times, PLACEMENT_DURATION_MS

    assert _stone_click_times(proof["frames"], proof, 10000) == [proof["events"][0]["at_ms"] + PLACEMENT_DURATION_MS]


def test_source_bound_numeric_choice_reveal_has_no_last_move_ring():
    value = diagram()
    value["labels"] = {"0,1": "1", "2,1": "1"}
    source = {"source_pointer": "/choices/0", "image_sha256": "a" * 64}
    plan = {
        "schema_version": 1,
        "annotation_object_ids": ["labels:0,1", "labels:2,1"],
        "bindings": [{"span": [0, 3], "object_ids": ["labels:0,1"]}, {"span": [4, 7], "object_ids": ["labels:2,1"]}],
    }
    proof = build(value, "左侧1，右侧1。", presentation_plan=plan, source_identity=source)
    assert proof["status"] == "complete", proof
    assert all(frame["currentMove"] is None and frame["last"] is None for frame in proof["frames"])
    assert all(frame["appeared_stones"] for frame in proof["frames"][1:])
    numbered = build(diagram(), "白1，黑2，白3，黑4，白5。")
    assert numbered["frames"][1]["currentMove"] == {"kind": "move", "color": "W", "point": [0, 1]}
    assert numbered["frames"][1]["last"] == [0, 1]


def source_unnumbered_A_capture():
    initial = {"B": [[4, 15], [3, 16], [5, 16]], "W": [[2, 13], [3, 15], [2, 16], [7, 16]]}
    value = {
        "schema_version": 2,
        "size": 19,
        "unknown_stones": [],
        "stones": {"B": [*initial["B"], [4, 17]], "W": [*initial["W"], [3, 17]]},
        "labels": {"3,17": "1", "4,17": "2"},
        "letters": {"4,16": "A"},
        "shapes": {"3,16": "triangle"},
        "replay": {"status": "needs_calibration"},
    }
    source = {"source_pointer": "/chapters/1/intro/0/elements/1", "image_sha256": "a" * 64}
    references = [
        ("黑三角", "shapes:3,16"),
        ("白1", "labels:3,17"),
        ("A", "letters:4,16"),
        ("黑2", "labels:4,17"),
        ("白棋在A落子", "replay:3"),
    ]
    text, bindings = "", []
    for reference, object_id in references:
        start = len(text)
        text += reference + "，"
        bindings.append({"span": [start, len(text) - 1], "object_ids": [object_id]})
    plan = {
        "schema_version": 1,
        "bindings": bindings,
        "source_replay": {
            **source,
            "evidence_description": "Source says W1 atari, B2 ko instead of A, then white A captures black triangle.",
            "initial": {
                "stones": initial,
                "to_play": "W",
                "unknown_stones": [],
                "known_region": {"col": 0, "row": 0, "cols": 19, "rows": 19},
                "shapes": value["shapes"],
            },
            "moves": [
                {"kind": "move", "color": "W", "point": [3, 17], "printed_number": "1"},
                {"kind": "move", "color": "B", "point": [4, 17], "printed_number": "2"},
                {
                    "kind": "move",
                    "color": "W",
                    "point": [4, 16],
                    "source_note": "原文白棋在A提去三角黑子；此动作没有印刷编号，不补造白3。",
                },
            ],
        },
    }
    return value, text, plan, source


def test_source_unnumbered_A_action_uses_explicit_step_and_real_rules_without_inventing_printed_number():
    value, text, plan, source = source_unnumbered_A_capture()
    before = copy.deepcopy(value)
    proof = build(value, text, presentation_plan=plan, source_identity=source)
    assert proof["status"] == "complete", proof
    assert proof["mode"] == "source_replay"
    assert value == before
    triangle = proof["frames"][1]
    assert triangle["currentMove"] is None and triangle["last"] is None
    assert triangle["appeared_stones"] == [{"color": "B", "point": [3, 16]}]
    assert [3, 16] in proof["frames"][2]["payload"]["stones"]["B"]  # Correct atari target exists before W1.
    letter = proof["frames"][3]
    assert letter["currentMove"] is None and letter["last"] is None
    final = proof["frames"][-1]
    assert final["currentMove"]["kind"] == "move" and final["currentMove"]["printed_number"] is None
    assert final["last"] == [4, 16] and final["captured"] == [[3, 16]]
    assert [4, 16] in final["payload"]["stones"]["W"] and [3, 16] not in final["payload"]["stones"]["B"]
    assert final["payload"]["shapes"] == {}
    assert final["payload"]["labels"] == value["labels"]
    assert final["payload"]["letters"] == {"4,16": "A"}
    action = next(obj for obj in proof["objects"] if obj["id"] == "replay:3")
    assert action["number"] is None and action["value"] is None and action["replay_step"] == 3


def test_source_unnumbered_action_requires_source_note_and_explicit_spoken_binding():
    value, text, plan, source = source_unnumbered_A_capture()
    no_note = copy.deepcopy(plan)
    no_note["source_replay"]["moves"][-1].pop("source_note")
    assert build(value, text, presentation_plan=no_note, source_identity=source)["status"] == "pending"
    no_span = copy.deepcopy(plan)
    no_span["bindings"] = no_span["bindings"][:-1]
    assert build(value, text, presentation_plan=no_span, source_identity=source)["status"] == "pending"


def margin_callout_fixture():
    source = {"source_pointer": "/routes/0", "image_sha256": "a" * 64}
    value = {
        "schema_version": 2,
        "size": 19,
        "stones": {"B": [], "W": []},
        "unknown_stones": [],
        "labels": {},
        "letters": {},
        "shapes": {},
        "replay": {"status": "needs_calibration"},
    }
    text, bindings, callouts = "", [], []
    for group, side, indexes in [
        ("top-left", "top", range(4)),
        ("top-right", "top", range(18, 14, -1)),
        ("right-top", "right", range(4)),
        ("right-bottom", "right", range(18, 14, -1)),
    ]:
        start = len(text)
        text += {"top-left": "左上", "top-right": "右上", "right-top": "右侧上", "right-bottom": "右侧下"}[
            group
        ] + "四个。"
        ids = []
        for number, index in enumerate(indexes, 1):
            object_id = f"callout:{group}-{number}"
            ids.append(object_id)
            callouts.append(
                {
                    "id": object_id,
                    "anchor": [index, 0] if side == "top" else [18, index],
                    "side": side,
                    "text": "一二三四"[number - 1] + "路线",
                    **source,
                }
            )
        bindings.append({"span": [start, len(text) - 1], "object_ids": ids})
    return value, text, {"schema_version": 1, "bindings": bindings, "callouts": callouts}, source


def test_source_margin_callouts_reveal_four_groups_without_stones_clicks_or_saved_board_changes():
    from katrain.web.tutorials.media_render import _stone_click_times

    value, text, plan, source = margin_callout_fixture()
    original = copy.deepcopy(value)
    proof = build(value, text, presentation_plan=plan, source_identity=source)
    assert proof["status"] == "complete", proof
    assert proof["mode"] == "presentation"
    assert len(proof["objects"]) == 16 and all(
        obj["kind"] == "callout" and obj["point"] is None for obj in proof["objects"]
    )
    assert [len(frame["payload"]["presentation_callouts"]) for frame in proof["frames"]] == [0, 4, 8, 12, 16]
    assert all(
        frame["payload"]["stones"] == {"B": [], "W": []}
        and not frame["appeared_stones"]
        and frame["currentMove"] is None
        and frame["last"] is None
        for frame in proof["frames"]
    )
    assert _stone_click_times(proof["frames"], proof, 10000) == []
    assert value == original
    assert build(value, text, presentation_plan=plan)["status"] == "pending"
    assert (
        build(value, text, presentation_plan=plan, source_identity={**source, "image_sha256": "b" * 64})["status"]
        == "pending"
    )
    plan["bindings"].pop()
    assert build(value, text, presentation_plan=plan, source_identity=source)["status"] == "pending"


@pytest.mark.parametrize(
    "update",
    [
        {"anchor": [0, 1]},
        {"side": "left"},
        {"anchor": [19, 0]},
        {"text": "这是一段过长文字"},
        {"text": "   "},
        {"id": "arrow:wrong"},
        {"extra_world_point": [0, -2]},
    ],
)
def test_callouts_accept_only_short_source_bound_top_or_right_grid_edge_captions(update):
    value, text, plan, source = margin_callout_fixture()
    plan["callouts"][0].update(update)
    assert build(value, text, presentation_plan=plan, source_identity=source)["status"] == "pending"


def test_absent_or_empty_callouts_leave_existing_nested_plan_and_proof_bytes_stable():
    from katrain.web.admin.routers.tutorial_media import MediaTaskWrite
    from katrain.web.tutorials.media_presentation import PresentationPlan

    plan = {
        "schema_version": 1,
        "bindings": [{"span": [i * 3, i * 3 + 2], "object_ids": [f"labels:{i},1"]} for i in range(5)],
    }
    for candidate in (plan, {**plan, "callouts": []}):
        canonical = PresentationPlan.model_validate(candidate).model_dump(by_alias=True)
        assert "callouts" not in canonical
        nested = MediaTaskWrite.model_validate(
            {"kind": "audio", "expected_updated_at": None, "presentation_plan": candidate}
        ).model_dump()
        assert "callouts" not in nested["presentation_plan"]
        import json

        serialized = MediaTaskWrite.model_validate(
            {"kind": "audio", "expected_updated_at": None, "presentation_plan": candidate}
        ).model_dump_json()
        assert "callouts" not in json.loads(serialized)["presentation_plan"]
        proof = build(diagram(), "白1，黑2，白3，黑4，白5。", presentation_plan=candidate)
        assert proof["presentation_sha256"] == "01ffb03202fa6e59123a644453a46fe20f90e7b2f6297c75d2a39e284f54a1ef"
        assert all("presentation_callouts" not in frame["payload"] for frame in proof["frames"])


def test_source_board_region_labels_reveal_nine_text_objects_without_action_or_margin_semantics():
    from katrain.web.tutorials.media_render import _stone_click_times

    value, _, _, source = margin_callout_fixture()
    groups = [
        ("隅", [[2, 2], [16, 2], [2, 16], [16, 16]], [0, 2]),
        ("边", [[9, 2], [2, 9], [16, 9], [9, 16]], [3, 4]),
        ("中央", [[9, 9]], [5, 7]),
    ]
    callouts, bindings = [], []
    for group, (word, anchors, span) in enumerate(groups):
        ids = []
        for index, anchor in enumerate(anchors):
            identity = f"callout:region-{group}-{index}"
            ids.append(identity)
            callouts.append({"id": identity, "anchor": anchor, "side": "board", "text": word, **source})
        bindings.append({"span": span, "object_ids": ids})
    plan = {"schema_version": 1, "bindings": bindings, "callouts": callouts}
    original = copy.deepcopy(value)
    proof = build(value, "角部，边，中腹。", presentation_plan=plan, source_identity=source)
    assert proof["status"] == "complete", proof
    assert [len(frame["payload"]["presentation_callouts"]) for frame in proof["frames"]] == [0, 4, 8, 9]
    assert all(
        obj["kind"] == "callout" and obj["stone_color"] is None and obj["point"] is None for obj in proof["objects"]
    )
    assert all(
        frame["payload"]["stones"] == {"B": [], "W": []}
        and not frame["appeared_stones"]
        and frame["currentMove"] is None
        and frame["last"] is None
        for frame in proof["frames"]
    )
    assert _stone_click_times(proof["frames"], proof, 10000) == [] and value == original
    assert build(value, "角部，边，中腹。", presentation_plan=plan)["status"] == "pending"
    plan["callouts"][0]["anchor"] = [19, 2]
    assert build(value, "角部，边，中腹。", presentation_plan=plan, source_identity=source)["status"] == "pending"


def test_existing_margin_callout_proof_hash_is_unchanged_by_board_text_support():
    value, text, plan, source = margin_callout_fixture()
    assert (
        build(value, text, presentation_plan=plan, source_identity=source)["presentation_sha256"]
        == "cd4f7078ffc159aa15a19adc3dd5e4218cd461e0cbf7e126f1e8e2ac360f546d"
    )


def forbidden_ko_fixture():
    value = {
        "schema_version": 2,
        "size": 19,
        "unknown_stones": [],
        "stones": {"B": [[4, 15], [3, 16], [5, 16], [4, 17]], "W": [[2, 13], [3, 15], [2, 16], [7, 16], [3, 17]]},
        "labels": {"3,16": "1"},
        "letters": {},
        "shapes": {},
        "replay": {"status": "needs_calibration"},
    }
    prior = copy.deepcopy(value)
    prior["stones"]["B"].remove([3, 16])
    prior["stones"]["W"].append([4, 16])
    prior.update(labels={"4,16": "1"}, shapes={"4,15": "triangle", "5,16": "triangle", "4,17": "triangle"})
    source = {
        "source_pointer": "/p11",
        "image_sha256": "b" * 64,
        "figure_id": 4826,
        "book_id": 1,
        "reference": {
            "figure_id": 4825,
            "book_id": 1,
            "page": 10,
            "source_pointer": "/p10",
            "image_sha256": "a" * 64,
            "board_payload": prior,
            "board_review_sha256": digest({"content_sha256": "c" * 64}),
            "page_image_path": "p10.png",
            "bbox": None,
        },
    }
    text = "先看白一。下面演示的是规则禁止的假设变化，实际对局中不能这样走。假设黑一立即反提。这一步违反打劫规则。"
    declaration = "下面演示的是规则禁止的假设变化，实际对局中不能这样走"
    white, prohibition, black = text.index("白一"), text.index(declaration), text.index("假设黑一立即反提")
    plan = {
        "schema_version": 1,
        "bindings": [
            {"span": [white, white + 2], "object_ids": ["reference:4825:labels:4,16"]},
            {"span": [black, black + 8], "object_ids": ["labels:3,16"]},
        ],
        "forbidden_ko": {
            "schema_version": 1,
            "initial_figure_id": 4825,
            "initial_object_id": "labels:4,16",
            "result_object_id": "labels:3,16",
            "source_pointer": "/p11",
            "image_sha256": "b" * 64,
            "initial_source_pointer": "/p10",
            "initial_image_sha256": "a" * 64,
            "initial_board_sha256": digest(prior),
            "initial_board_review_sha256": source["reference"]["board_review_sha256"],
            "prohibition_span": [prohibition, prohibition + len(declaration)],
        },
    }
    speech = timing(text)
    speech["duration_ms"] = len(text) * 200 + 1000
    return value, text, plan, source, speech


def test_forbidden_ko_reveals_source_initial_silently_then_captures_without_claiming_legal_replay():
    from katrain.web.tutorials.media_render import _stone_click_times, PLACEMENT_DURATION_MS
    from katrain.web.tutorials.replay import validate_replay

    value, text, plan, source, speech = forbidden_ko_fixture()
    original = copy.deepcopy((value, source))
    proof = build_step_cues(value, text, speech, presentation_plan=plan, source_identity=source)
    assert proof["status"] == "complete", proof
    assert proof["mode"] == "forbidden_ko"
    initial, revealed, captured = proof["frames"]
    assert [3, 16] not in initial["payload"]["stones"]["B"] and [4, 16] not in initial["payload"]["stones"]["W"]
    assert initial["payload"]["labels"] == {} and all(not f["payload"]["shapes"] for f in proof["frames"])
    assert revealed["payload"]["labels"] == {"4,16": "1"} and [4, 16] in revealed["payload"]["stones"]["W"]
    assert revealed["appeared_stones"] == [] and revealed["currentMove"] is None and revealed["last"] is None
    assert revealed["presentation_action"]["kind"] == "initial_reveal"
    assert captured["payload"]["stones"] == value["stones"] and captured["payload"]["labels"] == value["labels"]
    assert captured["captured"] == [[4, 16]] and captured["appeared_stones"] == [{"color": "B", "point": [3, 16]}]
    assert captured["currentMove"]["kind"] == "forbidden_ko_capture"
    assert [e["kind"] for e in proof["events"]] == ["initial_reveal", "forbidden_ko_capture"]
    assert proof["prohibition"]["at_ms"] < proof["events"][1]["at_ms"]
    assert _stone_click_times(proof["frames"], proof, speech["duration_ms"]) == [
        proof["events"][1]["at_ms"] + PLACEMENT_DURATION_MS
    ]
    assert (value, source) == original and validate_replay(value)["status"] == "needs_calibration"


@pytest.mark.parametrize(
    "invalid",
    [
        "missing_source",
        "foreign_book",
        "wrong_figure",
        "wrong_sha",
        "wrong_label",
        "extra_stone",
        "not_ko",
        "missing_prohibition",
        "extra_capture",
        "request_board_hash",
        "request_review_hash",
        "early_capture",
        "missing_binding",
        "stale_audio",
    ],
)
def test_forbidden_ko_is_bounded_to_exact_sources_single_ko_and_prior_spoken_prohibition(invalid):
    value, text, plan, source, speech = forbidden_ko_fixture()
    if invalid == "missing_source":
        source = None
    elif invalid == "foreign_book":
        source["reference"]["book_id"] = 2
    elif invalid == "wrong_figure":
        source["reference"]["figure_id"] = 44
    elif invalid == "wrong_sha":
        plan["forbidden_ko"]["initial_image_sha256"] = "d" * 64
    elif invalid == "wrong_label":
        source["reference"]["board_payload"]["labels"]["4,16"] = "2"
    elif invalid == "extra_stone":
        source["reference"]["board_payload"]["stones"]["B"].append([0, 0])
    elif invalid == "not_ko":
        value["stones"]["W"].remove([3, 15])
        source["reference"]["board_payload"]["stones"]["W"].remove([3, 15])
        plan["forbidden_ko"]["initial_board_sha256"] = digest(source["reference"]["board_payload"])
    elif invalid == "extra_capture":
        for board in (value, source["reference"]["board_payload"]):
            board["stones"]["B"].extend([[3, 14], [2, 15]])
        plan["forbidden_ko"]["initial_board_sha256"] = digest(source["reference"]["board_payload"])
    elif invalid == "request_board_hash":
        plan["forbidden_ko"]["initial_board_sha256"] = "f" * 64
    elif invalid == "request_review_hash":
        plan["forbidden_ko"]["initial_board_review_sha256"] = "f" * 64
    elif invalid == "missing_prohibition":
        plan["forbidden_ko"]["prohibition_span"] = [0, 2]
    elif invalid == "early_capture":
        plan["bindings"][1]["span"] = [0, 4]
    elif invalid == "missing_binding":
        plan["bindings"].pop(0)
    elif invalid == "stale_audio":
        speech["narration_sha256"] = "x"
    if invalid in ("wrong_label", "extra_stone"):
        plan["forbidden_ko"]["initial_board_sha256"] = digest(source["reference"]["board_payload"])
    proof = build_step_cues(value, text, speech, presentation_plan=plan, source_identity=source)
    assert proof["status"] == "pending" and proof["frames"] == [], proof


def test_absent_forbidden_ko_keeps_existing_proof_and_nested_schema_bytes_identical():
    from katrain.web.admin.routers.tutorial_media import MediaTaskWrite

    value, text, plan, source = margin_callout_fixture()
    baseline = build(value, text, presentation_plan=plan, source_identity=source)
    for candidate in (plan, {**plan, "forbidden_ko": None}):
        parsed = MediaTaskWrite.model_validate(
            {"kind": "audio", "expected_updated_at": None, "presentation_plan": candidate}
        ).model_dump(mode="json")
        assert "forbidden_ko" not in parsed["presentation_plan"]
        assert build(value, text, presentation_plan=candidate, source_identity=source) == baseline


def test_forbidden_ko_does_not_interpolate_a_prohibition_and_action_in_one_word_boundary():
    value, text, plan, source, speech = forbidden_ko_fixture()
    split = plan["forbidden_ko"]["prohibition_span"][0]
    action_end = plan["bindings"][1]["span"][1]
    speech["boundaries"] = [
        {"text": text[:split], "start_ms": 100, "duration_ms": 800},
        {"text": text[split:action_end], "start_ms": 1000, "duration_ms": 1000},
        {"text": text[action_end:], "start_ms": 2100, "duration_ms": 1000},
    ]
    proof = build_step_cues(value, text, speech, presentation_plan=plan, source_identity=source)
    assert proof["status"] == "pending" and "finish before" in proof["reason"]


def test_reference_initial_stone_cannot_be_imported_by_normal_source_replay():
    value, text, _, source, speech = forbidden_ko_fixture()
    prior = source["reference"]["board_payload"]
    plan = {
        "schema_version": 1,
        "bindings": [{"span": [0, 4], "object_ids": ["labels:3,16"]}],
        "source_replay": {
            "schema_version": 1,
            "initial": {
                "stones": prior["stones"],
                "unknown_stones": [],
                "known_region": {"col": 0, "row": 0, "cols": 19, "rows": 19},
                "to_play": "B",
            },
            "moves": [{"kind": "move", "color": "B", "point": [3, 16], "printed_number": "1"}],
            "source_pointer": "/p11",
            "image_sha256": "b" * 64,
            "evidence_description": "Cannot import external initial ownership.",
        },
    }
    assert build_step_cues(value, text, speech, presentation_plan=plan, source_identity=source)["status"] == "pending"
