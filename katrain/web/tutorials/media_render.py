"""Isolated, synchronous tutorial renderer; no DB, TTS or public application route.

The caller owns the immutable audio and validated replay snapshots. A fresh
browser sees only the standalone bundle via intercepted local asset requests.
"""

import hashlib
import json
import math
import mimetypes
import os
from pathlib import Path
import subprocess
import tempfile
import time
from urllib.parse import unquote, urlsplit

WIDTH, HEIGHT, FPS = 1280, 800, 5
MAX_DURATION_MS = 15 * 60 * 1000
RENDER_TIMEOUT_SECONDS = 600
BUNDLE_ROOT = Path(__file__).resolve().parents[1] / "tutorial-media-static"
RENDER_ORIGIN = "http://tutorial-render.invalid"


def _run(command, *, timeout):
    try:
        result = subprocess.run(command, check=True, capture_output=True, text=True, timeout=timeout)
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(f"{command[0]} failed: {(exc.stderr or str(exc))[-2000:]}") from exc
    except subprocess.TimeoutExpired as exc:
        raise TimeoutError(f"{command[0]} exceeded the tutorial render deadline") from exc
    return result.stdout


def _probe(path, *, timeout=20):
    return json.loads(
        _run(["ffprobe", "-v", "error", "-show_format", "-show_streams", "-of", "json", str(path)], timeout=timeout)
    )


def _validate_inputs(narration, board_payload, frames, speech_timing, step_cues, audio_path, render_mode):
    if render_mode not in ("2d", "3d"):
        raise ValueError("render_mode must be 2d or 3d")
    digest = hashlib.sha256(audio_path.read_bytes()).hexdigest()
    if speech_timing.get("audio_sha256") != digest or step_cues.get("audio_sha256") != digest:
        raise ValueError("The audio artifact hash does not match speech_timing/step_cues")
    if (
        not isinstance(narration, str)
        or speech_timing.get("narration_sha256") != hashlib.sha256(narration.encode()).hexdigest()
    ):
        raise ValueError("The saved narration hash does not match speech_timing")
    if speech_timing.get("schema_version") != 1 or step_cues.get("schema_version") != 1:
        raise ValueError("Unsupported tutorial media timing schema")
    duration = speech_timing.get("duration_ms")
    if not isinstance(duration, (float, int)) or not math.isfinite(duration) or not 0 < duration <= MAX_DURATION_MS:
        raise ValueError("Audio duration must be positive and no more than 15 minutes")
    previous = -1
    boundaries = speech_timing.get("boundaries") or []
    if not boundaries:
        raise ValueError("Speech timing has no real word boundaries")
    for boundary in boundaries:
        start, length = boundary.get("start_ms"), boundary.get("duration_ms")
        if (
            not isinstance(start, (int, float))
            or not isinstance(length, (int, float))
            or not math.isfinite(start)
            or not math.isfinite(length)
            or start < 0
            or start < previous
            or length < 0
            or start + length > duration + 250
            or not isinstance(boundary.get("text"), str)
            or not boundary["text"].strip()
        ):
            raise ValueError("Invalid or unordered speech boundary")
        previous = start
    from katrain.web.tutorials.media_timing import align_boundaries

    align_boundaries(narration, boundaries)
    if not isinstance(board_payload.get("size"), int) or not 2 <= board_payload["size"] <= 25:
        raise ValueError("Invalid saved board size")
    if not isinstance(board_payload.get("stones"), dict):
        raise ValueError("A saved static board is required")
    status = step_cues.get("status")
    if status == "complete":
        if len(frames) < 2 or [frame.get("step") for frame in frames] != list(range(len(frames))):
            raise ValueError("Complete replay requires every validated frame, including initial state")
        cues = step_cues.get("cues") or []
        # Every move must have an authoritative cue; never replay a legal prefix.
        steps = [cue.get("step") for cue in cues]
        if steps not in (list(range(1, len(frames))), list(range(len(frames)))):
            raise ValueError("Complete step_cues must time every validated replay step")
        if steps[0] == 0 and cues[0].get("at_ms") != 0:
            raise ValueError("The initial frame cue must start at zero")
        previous = -1
        for cue in cues:
            at = cue.get("at_ms")
            if not isinstance(at, (float, int)) or not math.isfinite(at) or not 0 <= at < duration or at < previous:
                raise ValueError("Invalid or unordered replay cue")
            previous = at
    elif status != "pending":
        raise ValueError("step_cues must explicitly be complete or pending")
    return duration


def _local_asset(bundle, url):
    """Resolve only files inside this build, never the filesystem or network."""
    parsed = urlsplit(url)
    if f"{parsed.scheme}://{parsed.netloc}" != RENDER_ORIGIN:
        return None
    relative = unquote(parsed.path).lstrip("/")
    path = (bundle / relative).resolve()
    if not path.is_relative_to(bundle) or not path.is_file():
        return None
    return path


def _capture_frames(data, directory, *, deadline):
    from playwright.sync_api import sync_playwright

    bundle = BUNDLE_ROOT.resolve()
    if not (bundle / "tutorial-media.html").is_file():
        raise RuntimeError("Standalone tutorial recorder bundle is missing; run npm run build:tutorial-media")
    failures = []
    cache = {}
    count = math.ceil(data["speech_timing"]["duration_ms"] * FPS / 1000)

    def remaining_ms():
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("Tutorial browser render exceeded 600 seconds")
        return min(30_000, max(1, int(remaining * 1000)))

    with sync_playwright() as playwright:
        launch = {
            "headless": True,
            "timeout": remaining_ms(),
            "args": [
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--use-gl=angle",
                "--use-angle=swiftshader",
                "--enable-unsafe-swiftshader",
            ],
        }
        executable = os.environ.get("TUTORIAL_MEDIA_CHROMIUM_EXECUTABLE")
        if executable:
            launch["executable_path"] = executable
        browser = playwright.chromium.launch(**launch)
        try:
            context = browser.new_context(
                viewport={"width": WIDTH, "height": HEIGHT}, device_scale_factor=1, service_workers="block"
            )

            def route_asset(route):
                path = _local_asset(bundle, route.request.url)
                if path is None:
                    failures.append(f"Blocked recorder asset: {urlsplit(route.request.url).path}")
                    route.abort()
                    return
                content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
                route.fulfill(
                    path=str(path),
                    content_type=content_type,
                    headers={
                        "Content-Security-Policy": "default-src 'none'; script-src 'self' 'unsafe-eval'; style-src 'self' 'unsafe-inline'; font-src 'self'; img-src 'self' data: blob:; connect-src 'none'; worker-src 'none'",
                    },
                )

            context.route("**/*", route_asset)
            page = context.new_page()
            page.on("pageerror", lambda error: failures.append(str(error)))
            page.add_init_script("window.__TUTORIAL_MEDIA_DATA = " + json.dumps(data, ensure_ascii=False) + ";")
            page.goto(RENDER_ORIGIN + "/tutorial-media.html", wait_until="load", timeout=remaining_ms())
            try:
                page.wait_for_function("window.__TUTORIAL_MEDIA_READY === true", timeout=remaining_ms())
            except Exception as exc:
                if failures:
                    raise RuntimeError("Tutorial recorder browser failed: " + "; ".join(failures[:3])) from exc
                raise
            for index in range(count):
                page.set_default_timeout(remaining_ms())
                key = page.evaluate(
                    """time => Promise.race([
                    window.__tutorialSetFrame(time),
                    new Promise((_, reject) => setTimeout(() => reject(new Error('Frame paint timed out')), 10000))
                ])""",
                    index * 1000 / FPS,
                )
                if failures:
                    raise RuntimeError("Tutorial recorder browser failed: " + "; ".join(failures[:3]))
                target = directory / f"frame-{index:06d}.png"
                if key in cache:
                    os.link(cache[key], target)
                else:
                    page.screenshot(path=str(target), timeout=remaining_ms())
                    cache[key] = target
        finally:
            browser.close()


def render_video(
    *,
    narration: str,
    board_payload: dict,
    frames: list[dict],
    speech_timing: dict,
    step_cues: dict,
    audio_path: Path,
    output_path: Path,
    render_mode: str,
) -> None:
    """Render snapshots at saved audio cues and atomically write a checked MP4.

    Pending cues always render the saved final static diagram with an explicit
    calibration label. Failures propagate to the job runner with their stage.
    """
    audio_path, output_path = Path(audio_path), Path(output_path)
    duration = _validate_inputs(narration, board_payload, frames, speech_timing, step_cues, audio_path, render_mode)
    audio = _probe(audio_path)
    if not any(stream.get("codec_type") == "audio" for stream in audio.get("streams", [])):
        raise ValueError("Saved speech artifact contains no audio stream")
    actual_duration = float(audio["format"]["duration"]) * 1000
    if abs(actual_duration - duration) > 250:
        raise ValueError("Saved speech duration disagrees with the actual audio artifact")
    deadline = time.monotonic() + RENDER_TIMEOUT_SECONDS
    data = {
        "narration": narration,
        "board_payload": board_payload,
        "frames": frames,
        "speech_timing": speech_timing,
        "step_cues": step_cues,
        "render_mode": render_mode,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="tutorial-render-", dir=output_path.parent) as temporary:
        directory = Path(temporary)
        _capture_frames(data, directory, deadline=deadline)
        rendered = directory / "rendered.mp4"
        _run(
            [
                "ffmpeg",
                "-v",
                "error",
                "-nostdin",
                "-y",
                "-framerate",
                str(FPS),
                "-i",
                str(directory / "frame-%06d.png"),
                "-i",
                str(audio_path),
                "-map",
                "0:v:0",
                "-map",
                "1:a:0",
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-crf",
                "20",
                "-pix_fmt",
                "yuv420p",
                "-r",
                str(FPS),
                "-c:a",
                "aac",
                "-b:a",
                "128k",
                "-t",
                f"{actual_duration / 1000:.6f}",
                "-movflags",
                "+faststart",
                str(rendered),
            ],
            timeout=max(1, deadline - time.monotonic()),
        )
        result = _probe(rendered, timeout=max(1, min(20, deadline - time.monotonic())))
        streams = result.get("streams", [])
        video = next((item for item in streams if item.get("codec_type") == "video"), {})
        sound = next((item for item in streams if item.get("codec_type") == "audio"), {})
        if (
            video.get("codec_name"),
            video.get("width"),
            video.get("height"),
            video.get("r_frame_rate"),
            sound.get("codec_name"),
        ) != ("h264", WIDTH, HEIGHT, "5/1", "aac"):
            raise RuntimeError("Rendered tutorial video has invalid codecs, dimensions or frame rate")
        if abs(float(result["format"]["duration"]) * 1000 - actual_duration) > 250:
            raise RuntimeError("Rendered tutorial duration does not match its saved speech artifact")
        rendered.replace(output_path)
