"""Immutable recording cues; never infer or write rules/replay evidence from labels."""

import copy
import math
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from katrain.web.tutorials.replay import replay_frames, validate_replay


class PresentationBinding(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    span: list[int] = Field(min_length=2, max_length=2)
    object_ids: list[str] = Field(min_length=1, max_length=512)


class PresentationArrow(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, populate_by_name=True)
    id: str = Field(pattern=r"^arrow:[A-Za-z0-9_-]+$", max_length=100)
    from_point: list[int] = Field(alias="from", min_length=2, max_length=2)
    to: list[int] = Field(min_length=2, max_length=2)
    source_pointer: str = Field(min_length=1, max_length=2048)
    image_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")


class PresentationPlan(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    schema_version: Literal[1]
    bindings: list[PresentationBinding] = Field(max_length=512)
    arrows: list[PresentationArrow] = Field(default_factory=list, max_length=128)
    annotation_object_ids: list[str] = Field(default_factory=list, max_length=512)


SHAPE_WORDS = {
    "triangle": ["三角", "△", "▲", "triangle"],
    "circle": ["圆圈", "圆形", "○", "●", "circle"],
    "cross": ["叉号", "叉", "×", "cross"],
    "square": ["方块", "方框", "正方形", "□", "■", "square"],
}


def _point(key, size):
    if not isinstance(key, str) or not re.fullmatch(r"\d+,\d+", key):
        raise ValueError("Annotation coordinate is invalid")
    point = list(map(int, key.split(",")))
    if any(not 0 <= value < size for value in point):
        raise ValueError("Annotation coordinate is outside the saved board")
    return point


def discover_objects(payload, presentation_plan=None, source_identity=None):
    """Stable marker IDs derive only from the saved board; arrows require server provenance."""
    plan = PresentationPlan.model_validate(presentation_plan).model_dump(by_alias=True) if presentation_plan else None
    size = payload.get("size")
    if type(size) is not int or not 2 <= size <= 25:
        raise ValueError("Invalid saved board size")
    occupants = {}
    for color in ("B", "W"):
        for point in (payload.get("stones") or {}).get(color, []):
            if len(point) != 2 or any(type(v) is not int or not 0 <= v < size for v in point):
                raise ValueError("Saved stone coordinate is invalid")
            key = ",".join(map(str, point))
            if key in occupants:
                raise ValueError("Saved stones overlap")
            occupants[key] = color
    objects = []
    for field in ("labels", "letters", "shapes"):
        for key, value in sorted((payload.get(field) or {}).items()):
            point = _point(key, size)
            if not isinstance(value, str) or not value.strip():
                raise ValueError("Saved annotation must have nonempty text")
            objects.append(
                {
                    "id": f"{field}:{key}",
                    "kind": field,
                    "point": point,
                    "value": value,
                    "stone_color": occupants.get(key),
                }
            )
    annotations = (plan or {}).get("annotation_object_ids", [])
    if annotations:
        if (
            not source_identity
            or not source_identity.get("source_pointer")
            or not re.fullmatch(r"[a-f0-9]{64}", source_identity.get("image_sha256", ""))
        ):
            raise ValueError("Numeric annotation roles require a server-owned source identity")
        eligible = {obj["id"] for obj in objects if obj["kind"] == "labels" and any(c.isdigit() for c in obj["value"])}
        if len(set(annotations)) != len(annotations) or not set(annotations) <= eligible:
            raise ValueError("Numeric annotation roles must identify saved numeric labels exactly once")
        for obj in objects:
            if obj["id"] in annotations:
                obj["role"] = "annotation"
    for arrow in (plan or {}).get("arrows", []):
        if not source_identity or any(arrow[k] != source_identity.get(k) for k in ("source_pointer", "image_sha256")):
            raise ValueError("Supplemental arrow does not match the server-owned figure source identity")
        for point in (arrow["from"], arrow["to"]):
            if any(not 0 <= value < size for value in point):
                raise ValueError("Supplemental arrow coordinate is outside the saved board")
        if arrow["from"] == arrow["to"]:
            raise ValueError("Supplemental arrow must have different endpoints")
        objects.append({"id": arrow["id"], "kind": "arrow", "arrow": arrow, "stone_color": None, "point": None})
    if len({obj["id"] for obj in objects}) != len(objects):
        raise ValueError("Presentation object IDs must be unique")
    return objects, plan


def _number(value):
    match = re.fullmatch(r"(?:[BW黑白])?\s*([0-9]+)", value or "", re.I)
    return int(match[1]) if match else None


def _prepare_objects(payload, objects):
    """Keep complete real replay as authoritative; otherwise validate printed sequence."""
    if payload.get("unknown_stones"):
        raise ValueError("Unknown stones require calibration before recording")
    if validate_replay(payload)["status"] == "complete":
        frames = replay_frames(payload)
        moves = payload["replay"]["moves"]
        ordered = []
        for step, move in enumerate(moves, 1):
            matching = [
                obj
                for obj in objects
                if obj["kind"] == "labels"
                and obj.get("role") != "annotation"
                and obj["point"] == move.get("point")
                and _number(obj["value"]) == _number(move.get("printed_number"))
                and _number(obj["value"]) is not None
            ]
            obj = matching[0] if matching else None
            # A point can be reused in real replay. A saved final label identifies only its matching move.
            if obj and obj.get("replay_step"):
                raise ValueError("Repeated replay printed number/point is ambiguous")
            if obj is None:
                obj = {
                    "id": f"replay:{step}",
                    "kind": "replay",
                    "point": move.get("point"),
                    "value": move.get("printed_number"),
                    "stone_color": move["color"],
                }
                objects.append(obj)
            obj.update(replay_step=step, number=_number(move.get("printed_number")))
            ordered.append(obj)
        return "replay", ordered, frames
    numbered = []
    for obj in objects:
        if (
            obj["kind"] != "labels"
            or obj.get("role") == "annotation"
            or not any(char.isdigit() for char in obj["value"])
        ):
            continue
        if not re.fullmatch(r"[0-9]+", obj["value"]) or not obj["stone_color"] or int(obj["value"]) < 1:
            raise ValueError("Printed number must identify one known stone with a positive plain number")
        obj["number"] = int(obj["value"])
        numbered.append(obj)
    numbered.sort(key=lambda obj: obj["number"])
    if numbered:
        numbers = [obj["number"] for obj in numbered]
        if numbers != list(range(numbers[0], numbers[0] + len(numbers))):
            raise ValueError("Printed numbers must be unique and contiguous; calibrate missing/duplicate numbers")
        if any(a["stone_color"] == b["stone_color"] for a, b in zip(numbered, numbered[1:])):
            raise ValueError("Printed numbered stone colors must alternate")
    return ("presentation" if objects else "static"), numbered, None


def _matches(obj, text):
    """Only explicit color+number or actual saved annotation tokens qualify automatically."""
    number = obj.get("number")
    if number is not None:
        color = "黑|B" if obj["stone_color"] == "B" else "白|W"
        return list(re.finditer(rf"(?:{color})\s*{number}(?![0-9])", text, re.I))
    if obj["kind"] == "replay":
        return []  # Unnumbered moves/passes need an explicit human binding.
    words = SHAPE_WORDS.get(obj.get("value"), [obj.get("value")]) if obj["kind"] == "shapes" else [obj.get("value")]
    if obj["kind"] == "arrow":
        words = ["箭头", "arrow"]
    patterns = []
    for word in words:
        if not word:
            continue
        escaped = re.escape(word)
        patterns.append(rf"(?<![A-Za-z0-9]){escaped}(?![A-Za-z0-9])" if word.isascii() and word.isalnum() else escaped)
    return list(re.finditer("|".join(patterns), text, re.I)) if patterns else []


def _auto_bindings(objects, narration):
    candidates = {}
    for obj in objects:
        for match in _matches(obj, narration):
            start = match.start()
            # Include a directly preceding color to disambiguate equal symbols on black/white stones.
            prefix = narration[max(0, start - 1) : start]
            if obj.get("number") is None and prefix in ("黑", "白"):
                if obj["stone_color"] != ("B" if prefix == "黑" else "W"):
                    continue
                start -= 1
            candidates.setdefault((start, match.end()), []).append(obj["id"])
    first = {}
    for span, ids in sorted(candidates.items()):
        if len(ids) != 1:
            raise ValueError("Narrated annotation is ambiguous; provide explicit presentation bindings")
        first.setdefault(ids[0], {"span": list(span), "object_ids": ids})
    missing = {obj["id"] for obj in objects} - first.keys()
    if missing:
        raise ValueError("Missing explicit narrated reference for: " + ", ".join(sorted(missing)))
    return list(first.values())


def _events(objects, plan, narration, timing):
    from katrain.web.tutorials.media_timing import align_boundary_spans, narration_hash

    if timing.get("narration_sha256") != narration_hash(narration):
        raise ValueError("Saved narration hash does not match speech timing")
    boundaries = align_boundary_spans(narration, timing.get("boundaries") or [])
    duration = timing.get("duration_ms")
    if type(duration) not in (int, float) or not math.isfinite(duration) or duration <= 0:
        raise ValueError("Invalid audio duration")
    if any(end_ms > duration or start_ms < 0 for _, _, start_ms, end_ms in boundaries):
        raise ValueError("Real speech boundary end falls outside the audio duration")
    bindings = plan["bindings"] if plan is not None else _auto_bindings(objects, narration)
    by_id = {obj["id"]: obj for obj in objects}
    used, events = set(), []
    for binding in bindings:
        start, end = binding["span"]
        ids = binding["object_ids"]
        if not 0 <= start < end <= len(narration) or not any(c.isalnum() for c in narration[start:end]):
            raise ValueError("Presentation binding needs a nonempty exact narration character span")
        if len(set(ids)) != len(ids) or used.intersection(ids) or not set(ids) <= by_id.keys():
            raise ValueError("Every known presentation object must be bound exactly once")
        # Numeric references must name their exact color+number even in manual plans.
        for object_id in ids:
            obj = by_id[object_id]
            if obj.get("number") is not None and not _matches(obj, narration[start:end]):
                raise ValueError("Numbered binding must explicitly mention its saved color and printed number")
        spoken_positions = [i for i in range(start, end) if narration[i].isalnum()]
        covered = [boundary for boundary in boundaries if boundary[0] <= spoken_positions[-1] < boundary[1]]
        if len(covered) != 1:
            raise ValueError("Presentation span has no aligned real speech end")
        at_ms = covered[0][3]
        if not 0 < at_ms < duration:
            raise ValueError("Presentation cue falls outside the audio duration")
        used.update(ids)
        events.append({"at_ms": at_ms, "object_ids": ids, "span": [start, end]})
    if used != by_id.keys():
        raise ValueError("Every required presentation object needs exactly one binding")
    events.sort(key=lambda event: (event["at_ms"], event["span"][0]))
    for step, event in enumerate(events, 1):
        event["step"] = step
    return events


def _validate_order(ordered, objects, events):
    by_id = {object_id: event for event in events for object_id in event["object_ids"]}
    for left, right in zip(ordered, ordered[1:]):
        if (
            by_id[left["id"]]["at_ms"] >= by_id[right["id"]]["at_ms"]
            or by_id[left["id"]]["span"][1] > by_id[right["id"]]["span"][0]
        ):
            raise ValueError("Numbered/replay references must follow source order with distinct real speech ends")
    for numbered in ordered:
        if numbered["point"] is None:
            continue
        for obj in objects:
            if (
                obj["id"] != numbered["id"]
                and not obj.get("replay_step")
                and obj["point"] == numbered["point"]
                and obj.get("stone_color")
            ):
                if by_id[obj["id"]]["at_ms"] < by_id[numbered["id"]]["at_ms"]:
                    raise ValueError("Annotation would reveal a numbered stone before its numbered/replay cue")


def _frames(payload, objects, events, real_frames):
    by_id = {obj["id"]: obj for obj in objects}
    visible = set()
    all_marked = {
        (obj["stone_color"], tuple(obj["point"]))
        for obj in objects
        if obj["point"] is not None and obj.get("stone_color") and not (real_frames and obj.get("replay_step"))
    }
    current_rule_step = 0
    frames = []
    for step, event in enumerate([None, *events]):
        prior = frames[-1]["payload"]["stones"] if frames else {"B": [], "W": []}
        if event:
            visible.update(event["object_ids"])
            moves = [by_id[key].get("replay_step") for key in event["object_ids"] if by_id[key].get("replay_step")]
            if moves:
                if len(moves) != 1 or moves[0] != current_rule_step + 1:
                    raise ValueError("Real replay must advance exactly one evidenced step per cue")
                current_rule_step = moves[0]
        base = copy.deepcopy(real_frames[current_rule_step]["payload"] if real_frames else payload)
        revealed = {
            (by_id[key]["stone_color"], tuple(by_id[key]["point"]))
            for key in visible
            if by_id[key]["point"] is not None and by_id[key].get("stone_color")
        }
        base["stones"] = {
            color: [
                p
                for p in base["stones"].get(color, [])
                if (color, tuple(p)) not in all_marked or (color, tuple(p)) in revealed
            ]
            for color in ("B", "W")
        }
        for field in ("labels", "letters", "shapes"):
            # Replay's rule snapshots remove annotations on captures. Preserve that authority.
            mapping = base.get(field) or {}
            base[field] = {key: val for key, val in mapping.items() if f"{field}:{key}" in visible}
        arrows = [by_id[key]["arrow"] for key in sorted(visible) if by_id[key]["kind"] == "arrow"]
        if arrows or any(obj["kind"] == "arrow" for obj in objects):
            base["presentation_arrows"] = arrows
        if real_frames:
            # Saved independent annotations are presentation objects, even if absent from replay.initial.
            occupied = {tuple(p) for points in base["stones"].values() for p in points}
            for key in visible:
                obj = by_id[key]
                if obj["kind"] in ("labels", "letters", "shapes") and (
                    not obj["stone_color"] or tuple(obj["point"]) in occupied
                ):
                    rule_mapping = real_frames[current_rule_step]["payload"].get(obj["kind"]) or {}
                    # Never resurrect a captured numbered label.
                    if (
                        obj.get("replay_step")
                        and obj["point"] is not None
                        and ",".join(map(str, obj["point"])) not in rule_mapping
                    ):
                        continue
                    base[obj["kind"]][",".join(map(str, obj["point"]))] = obj["value"]
        appeared = (
            [
                {"color": color, "point": point}
                for color in ("B", "W")
                for point in base["stones"][color]
                if point not in prior.get(color, [])
            ]
            if event
            else []
        )
        move = None
        captured = []
        if (
            real_frames
            and event
            and current_rule_step
            and any(by_id[key].get("replay_step") for key in event["object_ids"])
        ):
            move = copy.deepcopy(real_frames[current_rule_step]["currentMove"])
            captured = copy.deepcopy(real_frames[current_rule_step]["captured"])
        elif len(appeared) == 1:
            move = {"kind": "move", **appeared[0]}
        frames.append(
            {
                "step": step,
                "payload": base,
                "captured": captured,
                "last": move.get("point") if move else None,
                "currentMove": move,
                "nextColor": None,
                "appeared_stones": appeared,
            }
        )
    return frames


def build_presentation(payload, narration, timing, presentation_plan=None, source_identity=None):
    """Build a fail-closed, hash-bound recording proof, including exact visible snapshots."""
    from katrain.web.tutorials.media_timing import digest, narration_hash

    result = {
        "schema_version": 1,
        "mode": "presentation",
        "audio_sha256": timing.get("audio_sha256"),
        "narration_sha256": narration_hash(narration),
        "board_sha256": digest(payload),
        "replay_sha256": digest(payload.get("replay")),
        "status": "pending",
        "reason": None,
        "objects": [],
        "events": [],
        "cues": [],
        "frames": [],
        "presentation_plan": presentation_plan,
        "source_identity": source_identity,
    }
    try:
        objects, plan = discover_objects(payload, presentation_plan, source_identity)
        result["presentation_plan"] = plan
        mode, ordered, real_frames = _prepare_objects(payload, objects)
        result.update(mode=mode, objects=objects)
        events = _events(objects, plan, narration, timing)
        _validate_order(ordered, objects, events)
        frames = _frames(payload, objects, events, real_frames)
        result.update(
            status="complete",
            events=events,
            frames=frames,
            cues=[
                {"step": 0, "at_ms": 0, "source": "initial"},
                *[{"step": event["step"], "at_ms": event["at_ms"], "source": "speech_end"} for event in events],
            ],
        )
    except (ValueError, TypeError, KeyError, IndexError) as exc:
        result["reason"] = str(exc)
    result["presentation_sha256"] = digest(
        {key: value for key, value in result.items() if key not in ("presentation_sha256", "asset")}
    )
    return result
