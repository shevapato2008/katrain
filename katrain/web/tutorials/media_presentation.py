"""Immutable recording cues; never infer or write rules/replay evidence from labels."""

import copy
import math
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_serializer

from katrain.web.tutorials.replay import replay_frames, validate_replay, recording_source_frames
from katrain.web.tutorials.workbench_models import ReplayInitial, ReplayMove


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


class SourceReplayMove(ReplayMove):
    printed_number: str | None = None
    source_note: str | None = Field(default=None, min_length=1, max_length=4000)


class SourceReplay(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    schema_version: Literal[1] = 1
    initial: ReplayInitial
    moves: list[SourceReplayMove] = Field(min_length=1, max_length=512)
    source_pointer: str = Field(min_length=1, max_length=2048)
    image_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    evidence_description: str = Field(min_length=1, max_length=8000)


class PresentationCallout(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    id: str = Field(pattern=r"^callout:[A-Za-z0-9_-]+$", max_length=100)
    anchor: list[int] = Field(min_length=2, max_length=2)
    side: Literal["top", "right"]
    text: str = Field(min_length=1, max_length=4)
    source_pointer: str = Field(min_length=1, max_length=2048)
    image_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")


class PresentationPlan(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    schema_version: Literal[1]
    bindings: list[PresentationBinding] = Field(max_length=512)
    arrows: list[PresentationArrow] = Field(default_factory=list, max_length=128)
    annotation_object_ids: list[str] = Field(default_factory=list, max_length=512)
    source_replay: SourceReplay | None = None
    callouts: list[PresentationCallout] = Field(default_factory=list, max_length=16)

    @model_serializer(mode="wrap")
    def serialize_plan(self, handler):
        value = handler(self)
        if not self.callouts:
            value.pop("callouts", None)  # Preserve every existing plan/task/profile proof byte-for-byte.
        return value


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
    # Initial-only teaching objects can be captured before the saved final diagram.
    # Their identity and lifetime belong to the initial rule position, not its replacement stone.
    source_replay = (plan or {}).get("source_replay")
    if source_replay or validate_replay(payload)["status"] == "complete":
        recording = source_replay or payload["replay"]
        initial = recording["initial"]
        initial_occupants = {tuple(point): color for color in ("B", "W") for point in initial["stones"].get(color, [])}
        moved_points = {tuple(move["point"]) for move in recording["moves"] if move.get("point") is not None}
        for field in ("labels", "letters", "shapes"):
            for key, value in sorted((initial.get(field) or {}).items()):
                point = _point(key, size)
                color = initial_occupants.get(tuple(point))
                if not isinstance(value, str) or not value.strip():
                    raise ValueError("Initial annotation must have nonempty text")
                if source_replay:
                    matching = [
                        obj
                        for obj in objects
                        if obj["kind"] == field
                        and obj["point"] == point
                        and obj["value"] == value
                        and obj["stone_color"] == color
                    ]
                    if matching:
                        if color is not None:
                            # Keep the saved ID for source-plan bindings, but pin a marked
                            # background stone to its initial rule lifetime, even on reuse.
                            matching[0]["scope"] = "initial"
                        continue
                if tuple(point) not in moved_points and any(
                    obj["kind"] == field
                    and obj["point"] == point
                    and obj["value"] == value
                    and obj["stone_color"] == color
                    for obj in objects
                ):
                    continue
                objects.append(
                    {
                        "id": f"initial.{field}:{key}",
                        "kind": field,
                        "point": point,
                        "value": value,
                        "stone_color": color,
                        "scope": "initial",
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
    source_replay = (plan or {}).get("source_replay")
    occupied_edges = set()
    for callout in (plan or {}).get("callouts", []):
        if not source_identity or any(callout[k] != source_identity.get(k) for k in ("source_pointer", "image_sha256")):
            raise ValueError("Margin callout does not match the server-owned figure source identity")
        col, row = callout["anchor"]
        if (
            not (0 <= col < size and 0 <= row < size)
            or (callout["side"] == "top" and row != 0)
            or (callout["side"] == "right" and col != size - 1)
        ):
            raise ValueError("Margin callout anchor must lie on its declared top or right grid edge")
        edge = (callout["side"], col, row)
        if edge in occupied_edges or not callout["text"].strip() or any(char.isspace() for char in callout["text"]):
            raise ValueError("Margin callouts require distinct edge anchors and short nonempty captions")
        occupied_edges.add(edge)
        objects.append(
            {
                "id": callout["id"],
                "kind": "callout",
                "point": None,
                "stone_color": None,
                "value": callout["text"],
                "callout": callout,
            }
        )
    if source_replay and (
        not source_identity
        or any(source_replay[k] != source_identity.get(k) for k in ("source_pointer", "image_sha256"))
    ):
        raise ValueError("Local recording sequence does not match the server-owned figure source identity")
    if len({obj["id"] for obj in objects}) != len(objects):
        raise ValueError("Presentation object IDs must be unique")
    return objects, plan


def _number(value):
    match = re.fullmatch(r"(?:[BW黑白])?\s*([0-9]+)", value or "", re.I)
    return int(match[1]) if match else None


def _source_recording_frames(payload, objects, source):
    """Validate source/printed actions before invoking the unchanged shared Go rules."""
    from katrain.web.tutorials.models import StrictBoardPayload

    moves, initial = source["moves"], source["initial"]
    if initial.get("unknown_stones") or not initial.get("known_region") or initial.get("to_play") not in ("B", "W"):
        raise ValueError("Source recording requires a known local initial position and explicit turn/extent")
    numbered = [
        obj
        for obj in objects
        if obj["kind"] == "labels" and obj.get("role") != "annotation" and any(c.isdigit() for c in obj["value"])
    ]
    numbers = [_number(move["printed_number"]) for move in moves if move.get("printed_number") is not None]
    if numbers and (
        any(number is None or number < 1 for number in numbers)
        or numbers != list(range(numbers[0], numbers[0] + len(numbers)))
    ):
        raise ValueError("Source recording printed numbers must be unique, positive and contiguous")
    for obj in numbered:
        if not re.fullmatch(r"[0-9]+", obj["value"]) or not obj["stone_color"]:
            raise ValueError("Saved historical number must identify a known occupied point")
        matches = [
            move
            for move in moves
            if move.get("printed_number") == obj["value"]
            and move.get("point") == obj["point"]
            and move["color"] == obj["stone_color"]
        ]
        if len(matches) != 1:
            raise ValueError("Source action does not match a saved historical number, color and coordinate")
    for move in moves:
        printed = any(
            move.get("printed_number") == obj["value"]
            and move.get("point") == obj["point"]
            and move["color"] == obj["stone_color"]
            for obj in numbered
        )
        if not printed and not (move.get("source_note") or "").strip():
            raise ValueError("Every source action absent from saved numbered stones requires an explicit source_note")
    for color in ("B", "W"):
        saved = {tuple(p) for p in payload["stones"].get(color, [])}
        setup = {tuple(p) for p in initial["stones"].get(color, [])}
        actions = {tuple(move["point"]) for move in moves if move["color"] == color and move.get("point") is not None}
        if not setup <= saved or not (saved - actions) <= setup:
            raise ValueError(
                "Source initial position must preserve saved background and cannot invent replacement stones"
            )
    for obj in objects:
        if obj["kind"] not in ("labels", "letters", "shapes") or not obj.get("stone_color"):
            continue
        if obj["point"] not in initial["stones"].get(obj["stone_color"], []):
            continue
        if any(
            numbered_obj["point"] == obj["point"] and numbered_obj["stone_color"] == obj["stone_color"]
            for numbered_obj in numbered
        ):
            continue
        key = ",".join(map(str, obj["point"]))
        if (initial.get(obj["kind"]) or {}).get(key) != obj["value"]:
            raise ValueError("Source initial must declare the saved marked background identity: " + obj["id"])
    for field in ("labels", "letters", "shapes"):
        for key, value in (initial.get(field) or {}).items():
            if (payload.get(field) or {}).get(key) != value:
                raise ValueError("Source initial annotations must match saved annotation identities")
    # Strict schema/coordinate validation uses a calibration draft so it cannot
    # accidentally assert that the book's historical chart is the rule final board.
    adapter = {
        "schema_version": 2,
        "size": payload["size"],
        "stones": copy.deepcopy(payload["stones"]),
        "unknown_stones": [],
        "source_region": {**initial["known_region"], "confirmed": True},
        "viewport": copy.deepcopy(payload.get("viewport")),
        "replay": {
            "status": "needs_calibration",
            "initial": initial,
            "moves": [{key: value for key, value in move.items() if key != "source_note"} for move in moves],
            "evidence": {
                "kind": "source",
                "source_pointer": source["source_pointer"],
                "description": source["evidence_description"],
            },
        },
    }
    adapter = StrictBoardPayload.model_validate(adapter).model_dump()
    adapter["replay"]["status"] = "complete"  # In-memory source adapter; never saved or returned as board authority.
    return recording_source_frames(adapter)


def _prepare_objects(payload, objects, source_replay=None):
    """Keep complete real replay as authoritative; otherwise validate printed sequence."""
    if payload.get("unknown_stones"):
        raise ValueError("Unknown stones require calibration before recording")
    if source_replay or validate_replay(payload)["status"] == "complete":
        frames = _source_recording_frames(payload, objects, source_replay) if source_replay else replay_frames(payload)
        moves = source_replay["moves"] if source_replay else payload["replay"]["moves"]
        ordered = []
        for step, move in enumerate(moves, 1):
            matching = [
                obj
                for obj in objects
                if obj["kind"] == "labels"
                and obj.get("role") != "annotation"
                and obj.get("scope") != "initial"
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
        return ("source_replay" if source_replay else "replay"), ordered, frames
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
        aliases = [str(number)]
        if 1 <= number <= 99:
            digits = "零一二三四五六七八九"
            tens, units = divmod(number, 10)
            aliases.append(
                (digits[tens] if tens > 1 else "") + "十" + (digits[units] if units else "") if tens else digits[units]
            )
        token = "|".join(aliases)
        return list(re.finditer(rf"(?:{color})\s*(?:{token})(?![0-9零〇一二两三四五六七八九十百千万])", text, re.I))
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
                and obj.get("scope") != "initial"
                and obj["point"] == numbered["point"]
                and obj.get("stone_color") == numbered.get("stone_color")
            ):
                owners = [
                    candidate
                    for candidate in ordered
                    if candidate["kind"] == "labels"
                    and candidate["point"] == obj["point"]
                    and candidate["stone_color"] == obj["stone_color"]
                ]
                if owners and owners[0]["id"] != numbered["id"]:
                    continue
                if by_id[obj["id"]]["at_ms"] < by_id[numbered["id"]]["at_ms"]:
                    raise ValueError("Annotation would reveal a numbered stone before its numbered/replay cue")


def _frames(payload, objects, events, real_frames):
    by_id = {obj["id"]: obj for obj in objects}
    visible = set()
    stone_labels = {
        (tuple(obj["point"]), obj["stone_color"]): obj
        for obj in objects
        if obj["kind"] == "labels" and obj.get("replay_step") and obj["point"] is not None
    }
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
            base[field] = {}
        arrows = [by_id[key]["arrow"] for key in sorted(visible) if by_id[key]["kind"] == "arrow"]
        if arrows or any(obj["kind"] == "arrow" for obj in objects):
            base["presentation_arrows"] = arrows
        if any(obj["kind"] == "callout" for obj in objects):
            base["presentation_callouts"] = [
                by_id[key]["callout"] for key in sorted(visible) if by_id[key]["kind"] == "callout"
            ]
        shown_now = set()
        for object_id in sorted(visible):
            obj = by_id[object_id]
            kind = obj["kind"]
            # Captured numbered moves have synthetic IDs but retain their real printed labels.
            field = "labels" if kind == "replay" and obj.get("number") is not None else kind
            if field not in ("labels", "letters", "shapes") or obj["point"] is None:
                continue
            key = ",".join(map(str, obj["point"]))
            if obj["stone_color"] and obj["point"] not in base["stones"][obj["stone_color"]]:
                continue
            if real_frames and obj["kind"] in ("letters", "shapes") and obj.get("scope") != "initial":
                owner = stone_labels.get((tuple(obj["point"]), obj["stone_color"]))
                if owner and (real_frames[current_rule_step]["payload"].get("labels") or {}).get(key) != owner["value"]:
                    continue  # A source marker belongs to this printed stone, not a later replacement.
            if real_frames and (obj.get("scope") == "initial" or obj.get("replay_step")):
                rule_mapping = real_frames[current_rule_step]["payload"].get(field) or {}
                if rule_mapping.get(key) != obj["value"]:
                    continue  # The source annotation was captured, replaced, or has not been placed.
            base[field][key] = obj["value"]
            shown_now.add(object_id)
        if event:
            for object_id in event["object_ids"]:
                obj = by_id[object_id]
                needs_marker = obj["kind"] in ("labels", "letters", "shapes") or (
                    obj["kind"] == "replay" and obj.get("number") is not None and obj["point"] is not None
                )
                if needs_marker and object_id not in shown_now:
                    raise ValueError("Presentation cue is outside the source annotation's valid lifetime: " + object_id)
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
        elif (
            not real_frames
            and len(appeared) == 1
            and event
            and any(
                by_id[object_id].get("number") is not None and by_id[object_id].get("role") != "annotation"
                for object_id in event["object_ids"]
            )
        ):
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
        mode, ordered, real_frames = _prepare_objects(payload, objects, (plan or {}).get("source_replay"))
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
