"""Server-owned manual approvals, bound to exact saved content and immutable media.

Historical recognition/calibration flags are evidence only. They never grant authority.
"""

import copy
import hashlib
from datetime import datetime, timezone

from pydantic import ValidationError

from katrain.web.tutorials.media_timing import VOICE, digest
from katrain.web.tutorials.media_profiles import GALAXY, OUTPUT_PROFILES, profile_entry
from katrain.web.tutorials.models import StrictBoardPayload


def static_payload(payload):
    return {key: value for key, value in (payload or {}).items() if key != "replay"}


def board_content_sha256(figure):
    return digest(
        {
            "board_payload": static_payload(figure.board_payload),
            "page": figure.page,
            "bbox": figure.bbox,
            "page_image_path": figure.page_image_path,
        }
    )


def board_problem(figure):
    if not isinstance(figure.board_payload, dict) or not figure.board_payload:
        return "Save a static diagram before manual approval"
    try:
        StrictBoardPayload.model_validate(static_payload(figure.board_payload))
    except (ValidationError, TypeError, ValueError):
        return "Saved static diagram needs calibration before manual approval"
    return None


def _record_valid(record):
    if not isinstance(record, dict) or not record.get("reviewed_by") or not record.get("reviewed_at"):
        return False
    try:
        reviewed_at = datetime.fromisoformat(record["reviewed_at"].replace("Z", "+00:00"))
        return reviewed_at.tzinfo is not None and len(record.get("content_sha256", "")) == 64
    except (ValueError, TypeError, AttributeError):
        return False


def board_approval(figure):
    record = figure.board_review
    if not _record_valid(record):
        return {"approved": False, "reason": "Current static diagram requires explicit manual approval"}
    problem = board_problem(figure)
    if problem:
        return {"approved": False, "reason": problem}
    if record["content_sha256"] != board_content_sha256(figure):
        return {"approved": False, "reason": "Static diagram content changed after manual approval"}
    return {"approved": True, "reason": None}


def board_authority(figure):
    return {"board_content_sha256": board_content_sha256(figure), "board_review_sha256": digest(figure.board_review)}


def make_review(admin, content_sha256, **extra):
    return {
        "reviewed_by": admin["username"],
        "reviewed_at": datetime.now(timezone.utc).isoformat(),
        "content_sha256": content_sha256,
        **extra,
    }


def media_dependencies(figure, *, voice=VOICE):
    media = (figure.recognition_debug or {}).get("workbench_media") or {}
    audio, timing = media.get("audio"), media.get("speech_timing")
    return {
        **board_authority(figure),
        "narration": figure.narration,
        "voice": voice,
        "board_payload": copy.deepcopy(figure.board_payload),
        "audio_asset": figure.audio_asset,
        "audio": copy.deepcopy(audio),
        "speech_timing": copy.deepcopy(timing),
    }


def video_artifact(figure, mode, output_profile=None):
    container = ((figure.recognition_debug or {}).get("workbench_media") or {}).get("videos", {}).get(mode)
    return profile_entry(container, output_profile)


def video_problem(figure, mode, output_profile=None):
    approval = board_approval(figure)
    if not approval["approved"]:
        return approval["reason"]
    video = video_artifact(figure, mode, output_profile)
    if not isinstance(video, dict) or not video.get("asset") or not video.get("sha256"):
        return "Generate a current immutable video with a file digest before manual approval"
    if video.get("dependencies_sha256") != digest(media_dependencies(figure)):
        return "Video dependencies changed; generate this mode again before manual approval"
    if mode == "2d" and output_profile is None and figure.video_asset != video["asset"]:
        galaxy = video_artifact(figure, mode, GALAXY)
        if not galaxy or figure.video_asset != galaxy.get("asset"):
            return "The saved 2D video does not match the current generated artifact"
    return None


def video_content_sha256(figure, mode, output_profile=None):
    content = {
        "render_mode": mode,
        "video": video_artifact(figure, mode, output_profile),
        "dependencies": media_dependencies(figure),
    }
    if output_profile is not None:
        content["output_profile"] = output_profile
    return digest(content)


def video_approval(figure, mode, output_profile=None):
    record = profile_entry(getattr(figure, f"video_{mode}_review"), output_profile)
    if not _record_valid(record):
        return {"approved": False, "reason": f"Current {mode.upper()} video requires explicit manual approval"}
    problem = video_problem(figure, mode, output_profile)
    if problem:
        return {"approved": False, "reason": problem}
    video = video_artifact(figure, mode, output_profile)
    if (
        record.get("asset") != video["asset"]
        or record.get("file_sha256") != video["sha256"]
        or record["content_sha256"] != video_content_sha256(figure, mode, output_profile)
    ):
        return {"approved": False, "reason": "Video changed after manual approval"}
    return {"approved": True, "reason": None}


def review_validity(figure):
    return {
        "board": board_approval(figure),
        "video_2d": video_approval(figure, "2d"),
        "video_3d": video_approval(figure, "3d"),
        "video_2d_profiles": {name: video_approval(figure, "2d", name) for name in OUTPUT_PROFILES},
    }


def stored_file_sha256(storage, key):
    """Hash bounded chunks, including remote assets, without buffering an entire MP4."""
    if not storage.exists(key):
        raise ValueError("Video file is missing; regenerate before manual approval")
    size = storage.size(key)
    if size <= 0:
        raise ValueError("Video file is empty; regenerate before manual approval")
    checksum = hashlib.sha256()
    for start in range(0, size, 1024 * 1024):
        block = storage.read_range(key, start, min(1024 * 1024, size - start))
        if not block:
            raise ValueError("Video file is incomplete; regenerate before manual approval")
        checksum.update(block)
    return checksum.hexdigest()
