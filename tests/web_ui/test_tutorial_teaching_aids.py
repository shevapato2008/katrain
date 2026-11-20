"""Source-pinned teaching overlays use existing real speech and rule frames."""

import copy
from types import SimpleNamespace

import pytest

from tests.web_ui.test_tutorial_media_presentation import build, diagram, historical_capture_source


def teaching_aid_fixture():
    value = diagram()
    value["labels"] = {}
    source = {"source_pointer": "/teaching/0", "image_sha256": "a" * 64}
    text = "目标黑子，左边气点，向右看，全部气点。"
    aids, bindings = [], []
    for identity, kind, points, channel, phrase in [
        ("target", "group", [[1, 1]], "target", "目标黑子"),
        ("left", "liberties", [[0, 0]], "focus", "左边气点"),
        ("direction", "line", [[1, 1], [3, 1]], "relation", "向右看"),
        ("all", "liberties", [[0, 0], [1, 0]], "focus", "全部气点"),
    ]:
        object_id = "aid:" + identity
        aids.append({"id": object_id, "kind": kind, "points": points, "channel": channel, "purpose": phrase, **source})
        start = text.index(phrase)
        bindings.append({"span": [start, start + len(phrase)], "object_ids": [object_id]})
    return value, text, {"schema_version": 1, "bindings": bindings, "teaching_aids": aids}, source


def test_teaching_aids_use_real_speech_replace_channel_and_keep_board_immutable():
    from katrain.web.tutorials.media_render import _stone_click_times

    value, text, plan, source = teaching_aid_fixture()
    before, original_plan = copy.deepcopy(value), copy.deepcopy(plan)
    proof = build(value, text, presentation_plan=plan, source_identity=source)
    assert proof["status"] == "complete", proof
    assert all(
        obj["kind"] == "teaching_aid" and obj["point"] is None and obj["stone_color"] is None
        for obj in proof["objects"]
    )
    assert [event["at_ms"] for event in proof["events"]] == [850, 1850, 2650, 3650]
    assert [[aid["id"] for aid in frame["payload"]["presentation_teaching_aids"]] for frame in proof["frames"]] == [
        [],
        ["aid:target"],
        ["aid:target", "aid:left"],
        ["aid:target", "aid:left", "aid:direction"],
        ["aid:target", "aid:all", "aid:direction"],
    ]
    assert all(frame["payload"]["stones"] == before["stones"] for frame in proof["frames"])
    assert all(frame["currentMove"] is None and frame["captured"] == [] for frame in proof["frames"])
    assert _stone_click_times(proof["frames"], proof, 10000) == []
    assert value == before and plan == original_plan
    proof["frames"][-1]["payload"]["presentation_teaching_aids"][0]["points"].append([3, 1])
    assert plan == original_plan
    assert proof["frames"][1]["payload"]["presentation_teaching_aids"][0]["points"] == [[1, 1]]


@pytest.mark.parametrize(
    "update",
    [
        {"kind": "liberties", "points": [[1, 1]]},
        {"kind": "group", "points": [[0, 0]]},
        {"points": [[-1, 0]]},
        {"points": [[9, 0]]},
        {"points": [[0, 0, 1]]},
        {"points": [[True, 1]]},
        {"points": [[1.0, 1]]},
        {"points": [["1", 1]]},
        {"kind": "arrow", "points": [[0, 0]]},
        {"kind": "line", "points": [[0, 0], [0, 0]]},
        {"label": "字" * 33},
        {"channel": "气点"},
        {"purpose": ""},
        {"tone": "arbitrary-css"},
    ],
)
def test_teaching_aid_geometry_and_metadata_require_saved_board_semantics(update):
    value, text, plan, source = teaching_aid_fixture()
    plan["teaching_aids"][0].update(update)
    proof = build(value, text, presentation_plan=plan, source_identity=source)
    assert proof["status"] == "pending" and proof["frames"] == [], proof


@pytest.mark.parametrize("change", ["missing_source", "source_pointer", "image_sha256", "duplicate_id", "unbound"])
def test_teaching_aids_require_current_source_unique_ids_and_explicit_bindings(change):
    value, text, plan, source = teaching_aid_fixture()
    if change == "missing_source":
        source = None
    elif change in ("source_pointer", "image_sha256"):
        source[change] = "/other" if change == "source_pointer" else "b" * 64
    elif change == "duplicate_id":
        plan["teaching_aids"][1]["id"] = plan["teaching_aids"][0]["id"]
    else:
        plan["bindings"] = plan["bindings"][:-1]
    assert build(value, text, presentation_plan=plan, source_identity=source)["status"] == "pending"


def test_teaching_aid_defaults_and_absence_preserve_legacy_proof_bytes():
    from katrain.web.admin.routers.tutorial_media import MediaTaskWrite

    value, text, plan, source = teaching_aid_fixture()
    del plan["teaching_aids"][0]["channel"]
    proof = build(value, text, presentation_plan=plan, source_identity=source)
    assert proof["status"] == "complete", proof
    first = proof["objects"][0]["aid"]
    assert first["channel"] == first["tone"] == "focus" and first["label"] == ""
    legacy = {
        "schema_version": 1,
        "bindings": [{"span": [i * 3, i * 3 + 2], "object_ids": [f"labels:{i},1"]} for i in range(5)],
    }
    baseline = build(diagram(), "白1，黑2，白3，黑4，白5。", presentation_plan=legacy)
    assert baseline["presentation_sha256"] == "01ffb03202fa6e59123a644453a46fe20f90e7b2f6297c75d2a39e284f54a1ef"
    for candidate in (legacy, {**legacy, "teaching_aids": []}):
        parsed = MediaTaskWrite.model_validate(
            {"kind": "audio", "expected_updated_at": None, "presentation_plan": candidate}
        ).model_dump(mode="json")
        assert "teaching_aids" not in parsed["presentation_plan"]
        assert build(diagram(), "白1，黑2，白3，黑4，白5。", presentation_plan=candidate) == baseline
    assert all("presentation_teaching_aids" not in frame["payload"] for frame in baseline["frames"])


def test_source_replay_teaching_aids_validate_event_rule_position_before_capture():
    value, plan, source = historical_capture_source()
    text = "白1，最后一气，目标白子，黑2。"
    plan["bindings"] = [
        {"span": [0, 2], "object_ids": ["labels:0,0"]},
        {"span": [13, 15], "object_ids": ["labels:0,1"]},
    ]
    plan["teaching_aids"] = []
    for object_id, kind, points, phrase, channel in [
        ("aid:last", "liberties", [[0, 1]], "最后一气", "focus"),
        ("aid:white", "group", [[0, 0]], "目标白子", "target"),
    ]:
        start = text.index(phrase)
        plan["bindings"].append({"span": [start, start + len(phrase)], "object_ids": [object_id]})
        plan["teaching_aids"].append(
            {"id": object_id, "kind": kind, "points": points, "channel": channel, "purpose": phrase, **source}
        )
    before = copy.deepcopy(value)
    proof = build(value, text, presentation_plan=plan, source_identity=source)
    assert proof["status"] == "complete", proof
    assert [0, 1] in value["stones"]["B"]  # Printed final point is occupied, but the earlier rule frame is empty.
    assert proof["frames"][2]["payload"]["presentation_teaching_aids"][0]["points"] == [[0, 1]]
    assert proof["frames"][-1]["captured"] == [[0, 0]] and value == before
    for index in (-2, -1):
        after_capture = copy.deepcopy(plan)
        after_capture["bindings"][index]["span"] = [13, 15]
        assert build(value, text, presentation_plan=after_capture, source_identity=source)["status"] == "pending"


def test_teaching_aids_resolve_current_registered_source_identity(monkeypatch):
    from katrain.web.tutorials import manual_review

    figure, database = SimpleNamespace(), object()
    source = {"source_pointer": "/current", "image_sha256": "a" * 64}
    calls = []

    def registered(current_figure, current_database):
        calls.append((current_figure, current_database))
        return source, 1

    monkeypatch.setattr(manual_review, "_registered_source_identity", registered)
    assert (
        manual_review.presentation_source_identity(figure, {"teaching_aids": [{"id": "aid:target"}]}, db=database)
        == source
    )
    assert calls == [(figure, database)]


def test_same_event_same_channel_keeps_whole_group_until_later_event_replaces_it():
    value, _, _, source = teaching_aid_fixture()
    aids = [
        {"id": "aid:line-a", "kind": "line", "points": [[0, 0], [1, 0]], "purpose": "第一条线", **source},
        {"id": "aid:line-b", "kind": "line", "points": [[1, 0], [1, 1]], "purpose": "第二条线", **source},
        {"id": "aid:arrow", "kind": "arrow", "points": [[0, 0], [2, 2]], "purpose": "改成箭头", **source},
    ]
    plan = {
        "schema_version": 1,
        "teaching_aids": aids,
        "bindings": [
            {"span": [0, 3], "object_ids": ["aid:line-a", "aid:line-b"]},
            {"span": [4, 7], "object_ids": ["aid:arrow"]},
        ],
    }
    proof = build(value, "两条线，改箭头。", presentation_plan=plan, source_identity=source)
    assert proof["status"] == "complete", proof
    assert [[aid["id"] for aid in frame["payload"]["presentation_teaching_aids"]] for frame in proof["frames"]] == [
        [],
        ["aid:line-a", "aid:line-b"],
        ["aid:arrow"],
    ]
