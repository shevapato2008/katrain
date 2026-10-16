"""Focused real-browser checks; opt in after building the isolated recorder bundle."""

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

import pytest


def test_renderer_rejects_an_audio_artifact_mismatch(tmp_path):
    from katrain.web.tutorials.media_render import render_video

    audio = tmp_path / "speech.mp3"
    audio.write_bytes(b"a different immutable artifact")
    with pytest.raises(ValueError, match="audio.*hash|audio.*SHA256"):
        render_video(
            board_payload={"size": 9, "stones": {"B": [], "W": []}},
            frames=[],
            speech_timing={"schema_version": 1, "audio_sha256": "0" * 64, "duration_ms": 1000, "boundaries": []},
            step_cues={"schema_version": 1, "status": "pending", "audio_sha256": "0" * 64, "cues": []},
            audio_path=audio,
            output_path=tmp_path / "video.mp4",
            render_mode="2d",
        )
    assert not (tmp_path / "video.mp4").exists()


@pytest.mark.skipif(os.environ.get("TUTORIAL_MEDIA_RENDER_TEST") != "1", reason="requires built recorder and Chromium")
@pytest.mark.parametrize("mode", ["2d", "3d"])
def test_real_renderer_muxes_exact_audio_and_full_snapshots(tmp_path, mode):
    from katrain.web.tutorials.media_render import render_video

    assert shutil.which("ffmpeg") and shutil.which("ffprobe")
    audio = tmp_path / "speech.mp3"
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:duration=2.4",
            "-c:a",
            "libmp3lame",
            str(audio),
        ],
        check=True,
    )
    digest = hashlib.sha256(audio.read_bytes()).hexdigest()
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_format", "-of", "json", str(audio)],
        check=True,
        capture_output=True,
        text=True,
    )
    duration = round(float(json.loads(probe.stdout)["format"]["duration"]) * 1000)
    board = {
        "size": 9,
        "stones": {"B": [[2, 0]], "W": [[1, 0]]},
        "labels": {"1,0": "3"},
        "letters": {"3,1": "A"},
        "shapes": {"4,1": "triangle"},
        "source_region": {"col": 1, "row": 0, "cols": 8, "rows": 9, "confirmed": True},
        "replay": {"initial": {"known_region": {"col": 1, "row": 0, "cols": 8, "rows": 9}}},
    }
    frames = [
        {"step": 0, "payload": {**board, "stones": {"B": [], "W": [[1, 0]]}}, "last": None},
        {"step": 1, "payload": {**board, "stones": {"B": [[2, 0]], "W": []}}, "last": [2, 0]},
        {"step": 2, "payload": board, "last": [1, 0]},
    ]
    output = tmp_path / f"{mode}.mp4"
    render_video(
        board_payload=board,
        frames=frames,
        speech_timing={
            "schema_version": 1,
            "audio_sha256": digest,
            "duration_ms": duration,
            "boundaries": [{"text": "提子后复用原位。", "start_ms": 100, "duration_ms": 2000}],
        },
        step_cues={
            "schema_version": 1,
            "status": "complete",
            "audio_sha256": digest,
            "cues": [{"step": 0, "at_ms": 0}, {"step": 1, "at_ms": 800}, {"step": 2, "at_ms": 1600}],
        },
        audio_path=audio,
        output_path=output,
        render_mode=mode,
    )
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(output)],
        check=True,
        capture_output=True,
        text=True,
    )
    media = json.loads(result.stdout)
    assert {stream["codec_name"] for stream in media["streams"]} == {"h264", "aac"}
    video = next(stream for stream in media["streams"] if stream["codec_type"] == "video")
    assert (video["width"], video["height"], video["r_frame_rate"]) == (1280, 800, "5/1")
    assert abs(float(media["format"]["duration"]) * 1000 - duration) < 250
    assert hashlib.sha256(audio.read_bytes()).hexdigest() == digest
