"""The two published 2D outputs and the original renderer's recovery identity."""

import copy
from dataclasses import dataclass
from typing import Literal

OutputProfile = Literal["galaxy-4k-v1", "kiosk-7-v1"]
GALAXY = "galaxy-4k-v1"
KIOSK = "kiosk-7-v1"
OUTPUT_PROFILES = (GALAXY, KIOSK)


@dataclass(frozen=True)
class RenderProfile:
    width: int
    height: int
    fps: int
    crf: int
    preset: str
    renderer_recipe: str


GALAXY_RENDER = RenderProfile(3840, 2160, 30, 16, "medium", "tutorial-2d-dual-v1")
KIOSK_RENDER = RenderProfile(1024, 600, 30, 18, "medium", "tutorial-2d-dual-v1")
LEGACY_RENDER = RenderProfile(1280, 800, 15, 20, "veryfast", "tutorial-legacy-v1")


def render_profile(output_profile=None):
    if output_profile is None:
        return LEGACY_RENDER
    if output_profile == GALAXY:
        return GALAXY_RENDER
    if output_profile == KIOSK:
        return KIOSK_RENDER
    raise ValueError("Unknown tutorial video output_profile")


def profile_entry(container, output_profile=None):
    """Select one artifact/review; never hash a container containing sibling outputs."""
    if not isinstance(container, dict):
        return None
    if output_profile is not None:
        profiles = container.get("profiles")
        value = profiles.get(output_profile) if isinstance(profiles, dict) else None
        return copy.deepcopy(value) if isinstance(value, dict) else None
    value = {key: copy.deepcopy(value) for key, value in container.items() if key != "profiles"}
    return value or None


def with_profile(container, output_profile, value):
    """Merge a single slot into the latest persisted container, retaining legacy fields."""
    result = copy.deepcopy(container) if isinstance(container, dict) else {}
    if output_profile is None:
        profiles = result.get("profiles")
        result = copy.deepcopy(value) if isinstance(value, dict) else {}
        if profiles is not None:
            result["profiles"] = profiles
        return result or None
    profiles = result.get("profiles")
    result["profiles"] = dict(profiles) if isinstance(profiles, dict) else {}
    result["profiles"][output_profile] = copy.deepcopy(value)
    return result


def public_video_fields(figure):
    media = (figure.recognition_debug or {}).get("workbench_media") or {}
    container = (media.get("videos") or {}).get("2d")
    fields = (
        "asset",
        "width",
        "height",
        "fps",
        "duration_ms",
        "size_bytes",
        "playback_mode",
        "timing_status",
        "timing_reason",
        "output_profile",
        "renderer_recipe",
    )
    profiles = {}
    for name in OUTPUT_PROFILES:
        artifact = profile_entry(container, name)
        profiles[name] = {key: artifact.get(key) for key in fields} if artifact and artifact.get("asset") else None
    galaxy = profiles[GALAXY]
    selected = None
    if figure.video_asset:
        selected = GALAXY if galaxy and galaxy["asset"] == figure.video_asset else "legacy"
    return {"video_profiles": profiles, "video_output_profile": selected}
