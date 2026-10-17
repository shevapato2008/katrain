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
            narration="保存原文。",
            board_payload={"size": 9, "stones": {"B": [], "W": []}},
            frames=[],
            speech_timing={"schema_version": 1, "audio_sha256": "0" * 64, "duration_ms": 1000, "boundaries": []},
            step_cues={"schema_version": 1, "status": "pending", "audio_sha256": "0" * 64, "cues": []},
            audio_path=audio,
            output_path=tmp_path / "video.mp4",
            render_mode="2d",
        )
    assert not (tmp_path / "video.mp4").exists()


def test_renderer_rejects_narration_that_does_not_match_the_saved_timing(tmp_path):
    from katrain.web.tutorials.media_render import render_video

    audio = tmp_path / "speech.mp3"
    audio.write_bytes(b"immutable audio")
    digest = hashlib.sha256(audio.read_bytes()).hexdigest()
    with pytest.raises(ValueError, match="narration.*hash|narration.*SHA256"):
        render_video(
            narration="黑2、4。",
            board_payload={"size": 9, "stones": {"B": [], "W": []}},
            frames=[],
            speech_timing={
                "schema_version": 1,
                "audio_sha256": digest,
                "narration_sha256": "0" * 64,
                "duration_ms": 1000,
                "boundaries": [{"text": "黑24", "start_ms": 100, "duration_ms": 800}],
            },
            step_cues={"schema_version": 1, "status": "pending", "audio_sha256": digest, "cues": []},
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
        {
            "step": 1,
            "payload": {**board, "stones": {"B": [[2, 0]], "W": []}},
            "last": [2, 0],
            "currentMove": {"kind": "move", "point": [2, 0], "color": "B"},
        },
        {"step": 2, "payload": board, "last": [1, 0], "currentMove": {"kind": "move", "point": [1, 0], "color": "W"}},
    ]
    output = tmp_path / f"{mode}.mp4"
    narration = "黑2、4 提子，之后复用原位。"
    render_video(
        narration=narration,
        board_payload=board,
        frames=frames,
        speech_timing={
            "schema_version": 1,
            "audio_sha256": digest,
            "narration_sha256": hashlib.sha256(narration.encode()).hexdigest(),
            "duration_ms": duration,
            "boundaries": [{"text": "黑24提子之后复用原位", "start_ms": 100, "duration_ms": 2000}],
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
    assert (video["width"], video["height"], video["r_frame_rate"]) == (1280, 800, "15/1")
    assert abs(float(media["format"]["duration"]) * 1000 - duration) < 250
    assert hashlib.sha256(audio.read_bytes()).hexdigest() == digest


def test_stone_click_times_follow_only_completed_actual_move_landings():
    from katrain.web.tutorials.media_render import _stone_click_times

    frames = [
        {"step": 0, "currentMove": None},
        {"step": 1, "currentMove": {"kind": "move", "point": [2, 3]}},
        {"step": 2, "currentMove": {"kind": "pass", "point": None}},
        {"step": 3, "currentMove": {"kind": "move", "point": [3, 3]}},
    ]
    cues = {
        "status": "complete",
        "cues": [
            {"step": 0, "at_ms": 0},
            {"step": 1, "at_ms": 200},
            {"step": 2, "at_ms": 900},
            {"step": 3, "at_ms": 1600},
        ],
    }
    assert _stone_click_times(frames, cues, 2400) == [560, 1960]
    assert _stone_click_times(frames, {**cues, "status": "pending"}, 2400) == []
    assert _stone_click_times(frames, cues, 1800) == [560]
    assert _stone_click_times([], cues, 2400) == []


def test_stone_track_is_quiet_and_starts_at_exact_landing_without_source_changes(tmp_path):
    from array import array
    import wave
    from katrain.web.tutorials.media_render import STONE_SAMPLE, _write_stone_track

    before = hashlib.sha256(STONE_SAMPLE.read_bytes()).hexdigest()
    output = tmp_path / "clicks.wav"
    _write_stone_track(output, [560, 1960], 2400)
    with wave.open(str(output), "rb") as recording:
        rate, channels = recording.getframerate(), recording.getnchannels()
        samples = array("h", recording.readframes(recording.getnframes()))
    first = round(rate * 0.560) * channels
    assert not any(samples[:first])
    assert any(samples[first : first + round(rate * 0.13) * channels])
    assert not any(samples[round(rate * 0.9) * channels : round(rate * 1.96) * channels])
    assert max(abs(value) for value in samples) / 32768 < 0.04
    assert hashlib.sha256(STONE_SAMPLE.read_bytes()).hexdigest() == before


@pytest.mark.parametrize("channels", [1, 2])
@pytest.mark.parametrize("rate", [24000, 44100])
def test_actual_ffmpeg_mix_keeps_narration_gain_and_adds_click_at_landing(tmp_path, channels, rate):
    from array import array
    import math
    import wave
    from katrain.web.tutorials.media_render import _audio_mix_filter, _write_stone_track

    assert shutil.which("ffmpeg")
    source = array(
        "h", (round(0.12 * 32767 * math.sin(2 * math.pi * 440 * index / rate)) for index in range(round(2.4 * rate)))
    )
    narration = tmp_path / "narration.wav"
    with wave.open(str(narration), "wb") as audio:
        audio.setnchannels(channels)
        audio.setsampwidth(2)
        audio.setframerate(rate)
        interleaved = array("h", (value for sample in source for value in [sample] * channels))
        audio.writeframes(interleaved.tobytes())
    original_hash = hashlib.sha256(narration.read_bytes()).hexdigest()
    clicks = tmp_path / "clicks.wav"
    _write_stone_track(clicks, [560], 2400, channels=channels)
    result = subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-nostdin",
            "-f",
            "lavfi",
            "-i",
            "color=size=16x16:rate=15:duration=2.4",
            "-i",
            str(narration),
            "-i",
            str(clicks),
            "-filter_complex",
            _audio_mix_filter(rate),
            "-map",
            "[mixed]",
            "-c:a",
            "pcm_f32le",
            "-ac",
            str(channels),
            "-ar",
            str(rate),
            "-f",
            "f32le",
            "-",
        ],
        check=True,
        capture_output=True,
    )
    samples = array("f", result.stdout)[::channels]
    expected = [value / 32768 for value in source]
    assert len(samples) == len(expected)
    landing = round(0.560 * rate)
    # Stable gain and no sound before contact; no normalization or ducking.
    assert max(abs(samples[index] - expected[index]) for index in range(landing - round(0.002 * rate))) < 0.00001
    assert max(abs(samples[index] - expected[index]) for index in range(round(0.9 * rate), len(expected))) < 0.00001
    effect_result = subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-i",
            str(clicks),
            "-ar",
            str(rate),
            "-ac",
            str(channels),
            "-c:a",
            "pcm_f32le",
            "-f",
            "f32le",
            "-",
        ],
        check=True,
        capture_output=True,
    )
    effect = array("f", effect_result.stdout)[::channels]
    for index in range(len(expected)):
        assert abs(samples[index] - expected[index] - effect[index]) < 0.00001
    audible = next(index for index in range(len(expected)) if abs(samples[index] - expected[index]) > 0.0001)
    assert landing <= audible < landing + round(0.01 * rate)
    assert max(abs(samples[index] - expected[index]) for index in range(landing, round(0.7 * rate))) > 0.005
    assert hashlib.sha256(narration.read_bytes()).hexdigest() == original_hash


def test_audio_mix_filter_supports_old_ffmpeg_without_latency_option():
    from katrain.web.tutorials.media_render import _audio_mix_filter

    graph = _audio_mix_filter(24000)
    assert "latency" not in graph
    assert "apad=pad_len=119" in graph and "atrim=start_sample=119" in graph


@pytest.mark.parametrize(
    "profile,width,height,crf", [("galaxy-4k-v1", 3840, 2160, 16), ("kiosk-7-v1", 1024, 600, 18), (None, 1280, 800, 20)]
)
def test_renderer_uses_profile_encoding_and_checks_native_output(tmp_path, monkeypatch, profile, width, height, crf):
    from katrain.web.tutorials import media_render

    audio, output = tmp_path / "audio.mp3", tmp_path / "video.mp4"
    audio.write_bytes(b"immutable audio")
    calls, captures = [], []
    fps = 15 if profile is None else 30
    monkeypatch.setattr(media_render, "_validate_inputs", lambda *args: 1000)

    def capture(data, directory, **kwargs):
        captures.append(data)

    def run(command, **kwargs):
        calls.append(command)
        Path(command[-1]).write_bytes(b"encoded mp4")

    def probe(path, **kwargs):
        return {
            "format": {"duration": "1.0"},
            "streams": (
                [{"codec_type": "audio", "codec_name": "mp3", "channels": 1, "sample_rate": "24000"}]
                if path == audio
                else [
                    {
                        "codec_type": "video",
                        "codec_name": "h264",
                        "width": width,
                        "height": height,
                        "r_frame_rate": f"{fps}/1",
                    },
                    {"codec_type": "audio", "codec_name": "aac"},
                ]
            ),
        }

    monkeypatch.setattr(media_render, "_capture_frames", capture)
    monkeypatch.setattr(media_render, "_run", run)
    monkeypatch.setattr(media_render, "_probe", probe)
    media_render.render_video(
        narration="text",
        board_payload={},
        frames=[],
        speech_timing={},
        step_cues={"status": "pending"},
        audio_path=audio,
        output_path=output,
        render_mode="2d",
        output_profile=profile,
    )
    assert output.read_bytes() == b"encoded mp4"
    command = calls[0]
    assert command[command.index("-framerate") + 1] == str(fps)
    assert command[command.index("-r") + 1] == str(fps)
    assert command[command.index("-crf") + 1] == str(crf)
    assert command[command.index("-preset") + 1] == ("veryfast" if profile is None else "medium")
    assert command[command.index("-threads") + 1] == "4"
    assert captures[0]["output_profile"] == profile


@pytest.mark.parametrize("profile,mode", [("unknown", "2d"), ("galaxy-4k-v1", "3d")])
def test_renderer_rejects_unknown_or_3d_profile_before_opening_audio(tmp_path, profile, mode):
    from katrain.web.tutorials.media_render import render_video

    with pytest.raises(ValueError, match="profile"):
        render_video(
            narration="text",
            board_payload={},
            frames=[],
            speech_timing={},
            step_cues={},
            audio_path=tmp_path / "missing.mp3",
            output_path=tmp_path / "video.mp4",
            render_mode=mode,
            output_profile=profile,
        )


def test_profile_capture_uses_native_viewport_dpr_one_and_30fps(tmp_path, monkeypatch):
    import sys
    import time
    from contextlib import nullcontext
    from types import SimpleNamespace
    from katrain.web.tutorials import media_render

    (tmp_path / "tutorial-media.html").write_text("recorder")
    monkeypatch.setattr(media_render, "BUNDLE_ROOT", tmp_path)
    contexts, times = [], []

    class Page:
        def on(self, *args):
            pass

        def add_init_script(self, *args):
            pass

        def goto(self, *args, **kwargs):
            pass

        def wait_for_function(self, *args, **kwargs):
            pass

        def set_default_timeout(self, *args):
            pass

        def evaluate(self, script, value):
            times.append(value)
            return "same frame"

        def screenshot(self, *, path, **kwargs):
            Path(path).write_bytes(b"frame")

    class Browser:
        def new_context(self, **kwargs):
            contexts.append(kwargs)
            return SimpleNamespace(route=lambda *args: None, new_page=lambda: Page())

        def close(self):
            pass

    playwright = SimpleNamespace(chromium=SimpleNamespace(launch=lambda **kwargs: Browser()))
    monkeypatch.setitem(
        sys.modules, "playwright.sync_api", SimpleNamespace(sync_playwright=lambda: nullcontext(playwright))
    )
    media_render._capture_frames(
        {"output_profile": "kiosk-7-v1", "speech_timing": {"duration_ms": 100}},
        tmp_path,
        deadline=time.monotonic() + 60,
    )
    assert contexts[0]["viewport"] == {"width": 1024, "height": 600}
    assert contexts[0]["device_scale_factor"] == 1
    assert times == [0, 1000 / 30, 2000 / 30]
