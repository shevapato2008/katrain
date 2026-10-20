"""One audio stream, immutable timing, and conservative replay reference alignment."""

import hashlib
import json
import math
import subprocess
from pathlib import Path


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


def align_boundary_spans(narration: str, boundaries: list[dict]) -> list[tuple[int, int, int, int]]:
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
        length = boundary["duration_ms"]
        if (
            type(start) not in (int, float)
            or type(length) not in (int, float)
            or not math.isfinite(start)
            or not math.isfinite(length)
            or start < 0
            or start < previous
            or length <= 0
        ):
            raise ValueError("Speech boundary timing is not chronological")
        previous = start
        if count:
            result.append((positions[cursor], positions[cursor + count - 1] + 1, start, start + length))
            cursor += count
    return result


def align_boundaries(narration: str, boundaries: list[dict]) -> list[tuple[int, int, int]]:
    return [(start, end, at) for start, end, at, _ in align_boundary_spans(narration, boundaries)]


def build_step_cues(
    payload: dict, narration: str, timing: dict, *, presentation_plan=None, source_identity=None
) -> dict:
    from katrain.web.tutorials.media_presentation import build_presentation

    return build_presentation(payload, narration, timing, presentation_plan, source_identity)
