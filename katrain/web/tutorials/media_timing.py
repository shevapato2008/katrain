"""One audio stream, immutable timing, and conservative replay reference alignment."""

import hashlib
import json
import re
import subprocess
from pathlib import Path

from katrain.web.tutorials.replay import validate_replay

VOICE = "zh-CN-XiaoxiaoNeural"


def digest(value) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def narration_hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


async def synthesize_audio(text: str, voice: str, path: Path) -> list[dict]:
    import edge_tts

    boundaries = []
    with path.open("wb") as output:
        async for chunk in edge_tts.Communicate(text, voice, boundary="WordBoundary").stream():
            if chunk["type"] == "audio":
                output.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                boundaries.append(
                    {
                        "text": chunk["text"],
                        "start_ms": round(chunk["offset"] / 10000),
                        "duration_ms": round(chunk["duration"] / 10000),
                    }
                )
    if not path.stat().st_size or not boundaries:
        raise RuntimeError("TTS returned no audio or word boundaries")
    return boundaries


def probe_duration(path: Path) -> int:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", str(path)],
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    )
    duration = round(float(json.loads(result.stdout)["format"]["duration"]) * 1000)
    if duration <= 0:
        raise RuntimeError("Media duration must be positive")
    return duration


def align_boundaries(narration: str, boundaries: list[dict]) -> list[tuple[int, int, int]]:
    """Align actual words to source positions, ignoring only punctuation/space."""
    positions = [i for i, char in enumerate(narration) if char.isalnum()]
    expected = "".join(narration[i] for i in positions)
    actual = "".join(char for boundary in boundaries for char in boundary["text"] if char.isalnum())
    if not expected or expected != actual:
        raise ValueError("Speech boundary text does not match the exact saved narration")
    result, cursor, previous = [], 0, -1
    for boundary in boundaries:
        count = sum(char.isalnum() for char in boundary["text"])
        start = boundary["start_ms"]
        if start < previous or boundary["duration_ms"] < 0:
            raise ValueError("Speech boundary timing is not chronological")
        previous = start
        if count:
            result.append((positions[cursor], positions[cursor + count - 1] + 1, start))
            cursor += count
    return result


def build_step_cues(payload: dict, narration: str, timing: dict) -> dict:
    result = {
        "schema_version": 1,
        "audio_sha256": timing["audio_sha256"],
        "replay_sha256": digest(payload.get("replay")),
        "status": "pending",
        "reason": None,
        "cues": [],
    }

    def pending(reason):
        result["reason"] = reason
        return result

    proof = validate_replay(payload)
    if proof["status"] != "complete":
        return pending("Replay needs calibration: " + "; ".join(proof["issues"]))
    moves = payload["replay"]["moves"]
    lookup = {}
    for step, move in enumerate(moves, 1):
        number = re.fullmatch(r"(?:[BW黑白])?\s*(\d+)", move.get("printed_number") or "", re.I)
        if number:
            lookup.setdefault((move["color"], int(number[1])), []).append(step)
    boundary_positions = align_boundaries(narration, timing.get("boundaries", []))

    def time_at(position):
        return next((time for start, end, time in boundary_positions if start <= position < end), None)

    anchors = {}
    for match in re.finditer(r"(?P<color>黑|白|B|W)\s*(?P<numbers>\d+(?:\s*[、,，和及]\s*\d+)*)", narration, re.I):
        color = "B" if match["color"].upper() in ("黑", "B") else "W"
        for number in re.finditer(r"\d+", match["numbers"]):
            steps = lookup.get((color, int(number[0])), [])
            if len(steps) != 1:
                return pending("Narrated color/printed number does not identify one replay step")
            position = match.start() if number.start() == 0 else match.start("numbers") + number.start()
            at_ms = time_at(position)
            if at_ms is None:
                return pending("Narrated move has no word boundary")
            if steps[0] in anchors:
                return pending("Repeated narrated move reference is ambiguous")
            anchors[steps[0]] = at_ms
    if not anchors or 1 not in anchors or len(moves) not in anchors:
        return pending("First and last replay steps need explicit narrated color/printed references")
    ordered = sorted(anchors.items())
    if any(right[1] <= left[1] for left, right in zip(ordered, ordered[1:])):
        return pending("Narrated move anchors are not in chronological replay order")
    cues = {0: 0, **anchors}
    for (start_step, start_time), (end_step, end_time) in zip(ordered, ordered[1:]):
        for step in range(start_step + 1, end_step):
            cues[step] = round(start_time + (end_time - start_time) * (step - start_step) / (end_step - start_step))
    if any(time < 0 or time >= timing["duration_ms"] for time in cues.values()):
        return pending("Move timing falls outside the audio duration")
    result.update(
        status="complete",
        reason=None,
        cues=[
            {"step": step, "at_ms": time, "source": "anchor" if step in anchors or step == 0 else "interpolated"}
            for step, time in sorted(cues.items())
        ],
    )
    return result
