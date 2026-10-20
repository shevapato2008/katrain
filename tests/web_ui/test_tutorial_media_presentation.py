"""Recording presentation is separate from source board/rule replay authority."""

import copy
import hashlib

import pytest

from katrain.web.tutorials.media_timing import build_step_cues, narration_hash


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
