"""Review verified capture assets and atomically freeze a local YOLO dataset.

No hardware, router, transport, or training lifecycle lives here. The capture
coordinator's lock keeps the source manifest stable throughout review/freeze.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import tempfile
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

import cv2
import numpy as np
import yaml

from katrain.vision.classes import CLASS_NAMES
from katrain.vision.config import DEFAULT_MARGIN_CELLS, LedAnchorConfig
from katrain.vision.geometry_lock import load_geometry_lock
from katrain.vision.tools import baipu_autolabel
from katrain.vision.warp import adjust_M_for_resolution, margin_px_for, warp_with_margin
from katrain.web.admin.vision_capture_txn import VisionCaptureCoordinator, VisionCaptureError
from katrain.web.admin.vision_sgf import prepare_vision_sgf

SCHEMA_VERSION = 1
GENERATOR_VERSION = "admin-vision-dataset-1"
CLASS_ORDERS = {"stones2": ("black", "white"), "led4": tuple(CLASS_NAMES)}
MAX_FRAMES = 2048
MAX_SOURCE_BYTES = 512 * 1024 * 1024


class VisionDatasetError(RuntimeError):
    def __init__(self, status_code: int, message: str):
        super().__init__(message)
        self.status_code = status_code


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _json(data) -> bytes:
    return json.dumps(data, sort_keys=True, ensure_ascii=False, indent=2, allow_nan=False).encode("utf-8")


def _parameters(val_fraction, stone_frac, led_frac, margin_cells) -> dict:
    bounds = [(val_fraction, 0, 1), (stone_frac, 0, 2), (led_frac, 0, 2), (margin_cells, -1, 2)]
    if (
        any(
            type(value) not in (int, float) or not math.isfinite(value) or not low < value <= high
            for value, low, high in bounds
        )
        or val_fraction == 1
        or margin_cells < 0
    ):
        raise VisionDatasetError(422, "Invalid labeling or temporal split parameters")
    return {
        "val_fraction": float(val_fraction),
        "split_strategy": "sgf_temporal",
        "split_rounding": "floor_val_clamped_nonempty",
        "stone_frac": float(stone_frac),
        "led_frac": float(led_frac),
        "margin_cells": float(margin_cells),
        "shift": [0.0, 0.0],
        "refine": False,
        "led_evidence": {"detector": "baipu_autolabel.detect_led_centroid", "config": asdict(LedAnchorConfig())},
    }


def _generator() -> dict:
    # Hash the actual code used, including replay and CV configuration. No git or
    # remote dependency is needed, and a code change creates a new version ID.
    import katrain.core.baipu as baipu
    import katrain.vision.classes as classes
    import katrain.vision.config as config
    import katrain.vision.geometry_lock as geometry_lock
    import katrain.vision.warp as warp
    import katrain.web.admin.vision_sgf as vision_sgf

    modules = [baipu, classes, config, geometry_lock, warp, vision_sgf, baipu_autolabel]
    hashes = {module.__name__: _sha(Path(module.__file__).read_bytes()) for module in modules}
    hashes[__name__] = _sha(Path(__file__).read_bytes())
    return {
        "version": GENERATOR_VERSION,
        "code_sha256": hashes,
        "dependencies": {"opencv": cv2.__version__, "numpy": np.__version__, "pyyaml": yaml.__version__},
    }


def _normalized_boxes(boxes, width: int, height: int, class_count: int) -> list[dict]:
    normalized = []
    for box in boxes:
        values = [box.cx / width, box.cy / height, box.w / width, box.h / height]
        if (
            type(box.class_id) is not int
            or not 0 <= box.class_id < class_count
            or not all(math.isfinite(value) and 0 <= value <= 1 for value in values)
            or values[2] <= 0
            or values[3] <= 0
            or values[0] - values[2] / 2 < -1e-6
            or values[0] + values[2] / 2 > 1 + 1e-6
            or values[1] - values[3] / 2 < -1e-6
            or values[1] + values[3] / 2 > 1 + 1e-6
        ):
            raise VisionDatasetError(422, "Generated label has invalid class or normalized box")
        normalized.append(dict(class_id=box.class_id, cx=values[0], cy=values[1], w=values[2], h=values[3]))
    return normalized


def _write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    if path.read_bytes() != data:
        raise OSError("Dataset asset write verification failed")


class VisionDatasetBuilder:
    def __init__(self, coordinator: VisionCaptureCoordinator, *, output_root: Path | str | None = None):
        self.coordinator = coordinator
        self.output_root = Path(output_root if output_root is not None else coordinator.root / "datasets").resolve()

    def _source(self, game_id):
        try:
            manifest = self.coordinator.load_session(game_id)
            directory = self.coordinator.root / manifest["game_id"]
            source_bytes = (directory / "manifest.json").read_bytes()
            if json.loads(source_bytes) != manifest:
                raise ValueError("Source manifest changed")
            if not 1 <= len(manifest["frames"]) <= MAX_FRAMES:
                raise VisionDatasetError(422, "Dataset requires 1 to 2048 captured frames")
            assets = {
                manifest[path_key]: manifest[hash_key]
                for path_key, hash_key in (
                    ("sgf_path", "sgf_sha256"),
                    ("geometry_path", "geometry_sha256"),
                    ("geometry_sidecar_path", "geometry_sidecar_sha256"),
                )
            }
            assets.update({frame["file"]: frame["sha256"] for frame in manifest["frames"]})
            if sum((directory / name).stat().st_size for name in assets) + len(source_bytes) > MAX_SOURCE_BYTES:
                raise VisionDatasetError(413, "Capture assets exceed the 512 MiB dataset limit")
            sgf = prepare_vision_sgf((directory / manifest["sgf_path"]).read_bytes().decode("utf-8"))
            geometry = load_geometry_lock(directory / manifest["geometry_path"])
            sidecar = json.loads((directory / manifest["geometry_sidecar_path"]).read_bytes())
            if not isinstance(sidecar, dict) or not math.isfinite(sidecar["confidence"]):
                raise ValueError("Invalid geometry provenance")
            if any(
                value is not None and (type(value) is not int or value <= 0)
                for value in (geometry.source_width, geometry.source_height)
            ):
                raise ValueError("Invalid geometry source resolution")
            if (
                not np.all(np.diff(geometry.xs) > 0)
                or not np.all(np.diff(geometry.ys) > 0)
                or min(geometry.xs[0], geometry.ys[0]) < 0
                or max(geometry.xs[-1], geometry.ys[-1]) >= geometry.out_size
                or abs(np.linalg.det(geometry.M)) < 1e-12
            ):
                raise ValueError("Degenerate geometry")
            return directory, manifest, source_bytes, assets, geometry, [asdict(step) for step in sgf.steps]
        except VisionDatasetError:
            raise
        except VisionCaptureError as exc:
            raise VisionDatasetError(exc.status_code, str(exc)) from exc
        except (OSError, ValueError, TypeError, KeyError) as exc:
            raise VisionDatasetError(503, "Capture source integrity or geometry failed") from exc

    def _sample(self, directory, manifest, geometry, steps, frame, parameters):
        raw_bytes = (directory / frame["file"]).read_bytes()
        if _sha(raw_bytes) != frame["sha256"]:
            raise VisionDatasetError(503, "Source image hash changed")
        raw = cv2.imdecode(np.frombuffer(raw_bytes, np.uint8), cv2.IMREAD_COLOR)
        if raw is None:
            raise VisionDatasetError(503, "Source image is unreadable")
        height, width = raw.shape[:2]
        matrix = adjust_M_for_resolution(geometry.M, (geometry.source_width, geometry.source_height), (width, height))
        warped = warp_with_margin(raw, matrix, geometry.out_size, parameters["margin_cells"])
        pad = margin_px_for(geometry.out_size, parameters["margin_cells"])
        xs, ys = geometry.xs + pad, geometry.ys + pad
        spacing = baipu_autolabel.mean_grid_spacing(xs, ys)
        board = baipu_autolabel.reconstruct_board(steps, frame["applied_move_index"])
        led_point = frame["led_point"] if manifest["mode"] == "led4" else None
        evidence = None
        if led_point is not None:
            gx, gy = baipu_autolabel.grid_point(led_point["row"], led_point["col"], xs, ys)
            centroid = baipu_autolabel.detect_led_centroid(
                warped, gx, gy, max(1, int(0.7 * spacing)), led_point["color"]
            )
            if centroid is None:
                raise VisionDatasetError(422, "Expected LED has no visible pixel evidence; review or retake the frame")
            evidence = {"centroid": list(centroid), "color": led_point["color"], "source_sha256": frame["sha256"]}
        h, w = warped.shape[:2]
        boxes = baipu_autolabel.frame_boxes(
            board,
            led_point,
            xs,
            ys,
            (0.0, 0.0),
            spacing,
            stone_frac=parameters["stone_frac"],
            led_frac=parameters["led_frac"],
            img_w=w,
            img_h=h,
        )
        normalized = _normalized_boxes(boxes, w, h, len(CLASS_ORDERS[manifest["mode"]]))
        return warped, boxes, normalized, evidence

    def review_sample(self, game_id: str, frame_id: str) -> dict:
        with self.coordinator.lock:
            directory, manifest, _, _, geometry, steps = self._source(game_id)
            frame = next((frame for frame in manifest["frames"] if frame["frame_id"] == frame_id), None)
            if frame is None:
                raise VisionDatasetError(404, "Capture frame does not exist")
            parameters = _parameters(0.2, 1.05, 0.45, DEFAULT_MARGIN_CELLS)
            warped, boxes, normalized, evidence = self._sample(directory, manifest, geometry, steps, frame, parameters)
            ok, encoded = cv2.imencode(".png", baipu_autolabel.draw_overlay(warped, boxes))
            if not ok:
                raise VisionDatasetError(503, "Sample overlay encoding failed")
            return {
                "frame_id": frame["frame_id"],
                "source_sha256": frame["sha256"],
                "geometry_revision": manifest["geometry_revision"],
                "geometry_source": manifest["geometry_source"],
                "mode": manifest["mode"],
                "class_names": list(CLASS_ORDERS[manifest["mode"]]),
                "boxes": normalized,
                "led_evidence": evidence,
                "overlay_png": encoded.tobytes(),
            }

    def _validate(self, directory: Path, manifest: dict) -> None:
        """Validate persisted output, including both splits and exact image/label pairing."""
        class_names = list(CLASS_ORDERS[manifest["mode"]])
        if manifest["class_names"] != class_names or manifest["schema_version"] != SCHEMA_VERSION:
            raise VisionDatasetError(503, "Frozen dataset class/schema mismatch")
        actual = {path.relative_to(directory).as_posix() for path in directory.rglob("*") if path.is_file()}
        if any(path.is_symlink() for path in directory.rglob("*")) or actual != set(manifest["assets"]) | {
            "manifest.json"
        }:
            raise VisionDatasetError(503, "Frozen dataset has missing or unexpected assets")
        for name, digest in manifest["assets"].items():
            if _sha((directory / name).read_bytes()) != digest:
                raise VisionDatasetError(503, "Frozen dataset asset hash mismatch")
        config = yaml.safe_load((directory / "data.yaml").read_bytes())
        if config != {
            "train": "images/train",
            "val": "images/val",
            "nc": len(class_names),
            "names": class_names,
        }:
            raise VisionDatasetError(503, "Frozen dataset YAML differs from its mode")
        samples = manifest["samples"]
        if not samples or {sample["split"] for sample in samples} != {"train", "val"}:
            raise VisionDatasetError(422, "Both dataset splits must be nonempty")
        if [sample["applied_move_index"] for sample in samples] != sorted(
            {sample["applied_move_index"] for sample in samples}
        ):
            raise VisionDatasetError(422, "Dataset samples must follow SGF temporal order")
        seen_val = False
        pairs = set()
        for sample in samples:
            seen_val = seen_val or sample["split"] == "val"
            if seen_val and sample["split"] != "val":
                raise VisionDatasetError(422, "Dataset split violates SGF temporal order")
            stem = Path(sample["image"]).stem
            if (
                sample["image"] != f"images/{sample['split']}/{stem}.png"
                or sample["label"] != f"labels/{sample['split']}/{stem}.txt"
            ):
                raise VisionDatasetError(503, "Dataset image/label pairing is invalid")
            pairs.update((sample["image"], sample["label"]))
            if cv2.imread(str(directory / sample["image"])) is None:
                raise VisionDatasetError(503, "Frozen dataset image is unreadable")
            for line in (directory / sample["label"]).read_text().splitlines():
                parts = line.split()
                if len(parts) != 5:
                    raise VisionDatasetError(422, "Frozen label must have five fields")
                try:
                    cid = int(parts[0])
                    cx, cy, w, h = map(float, parts[1:])
                    box = baipu_autolabel.Box(cid, cx, cy, w, h)
                    _normalized_boxes([box], 1, 1, len(class_names))
                except ValueError as exc:
                    raise VisionDatasetError(422, "Frozen label has invalid numeric values") from exc
        output_pairs = {name for name in actual if name.startswith(("images/", "labels/"))}
        if output_pairs != pairs or len(pairs) != 2 * len(samples):
            raise VisionDatasetError(503, "Frozen dataset has orphan or duplicate image/label files")

    def freeze(
        self,
        game_id: str,
        *,
        val_fraction=0.2,
        stone_frac=1.05,
        led_frac=0.45,
        margin_cells=DEFAULT_MARGIN_CELLS,
        cancel_event=None,
    ) -> dict:
        parameters = _parameters(val_fraction, stone_frac, led_frac, margin_cells)
        with self.coordinator.lock:
            directory, source, source_bytes, source_assets, geometry, steps = self._source(game_id)
            if len(source["frames"]) < 2:
                raise VisionDatasetError(422, "Both dataset splits require captured frames")
            if cancel_event is not None and cancel_event.is_set():
                raise VisionDatasetError(409, "Dataset freeze cancelled")
            generator = _generator()
            identity = {"source_manifest_sha256": _sha(source_bytes), "parameters": parameters, "generator": generator}
            version_id = "dataset-" + _sha(_json(identity))
            final = self.output_root / version_id
            try:
                if final.exists() or final.is_symlink():
                    if final.is_symlink() or not final.is_dir():
                        raise VisionDatasetError(503, "Frozen dataset directory is invalid")
                    manifest_bytes = (final / "manifest.json").read_bytes()
                    manifest = json.loads(manifest_bytes)
                    if manifest["id"] != version_id or manifest["identity"] != identity:
                        raise VisionDatasetError(503, "Frozen dataset identity mismatch")
                    self._validate(final, manifest)
                    return {**manifest, "path": str(final), "manifest_sha256": _sha(manifest_bytes), "idempotent": True}
                self.output_root.mkdir(parents=True, exist_ok=True)
                with tempfile.TemporaryDirectory(prefix=".dataset-", dir=self.output_root) as temporary:
                    # Keep the stage and final directory under the same parent:
                    # macOS can rename a read-only directory here without having
                    # to modify the moved directory's parent entry.
                    stage = Path(temporary)
                    _write(stage / "source" / "capture-manifest.json", source_bytes)
                    for name in (source["sgf_path"], source["geometry_path"], source["geometry_sidecar_path"]):
                        data = (directory / name).read_bytes()
                        if _sha(data) != source_assets[name]:
                            raise VisionDatasetError(503, "Source provenance asset hash changed")
                        _write(stage / "source" / name, data)
                    val_count = max(1, min(len(source["frames"]) - 1, int(len(source["frames"]) * val_fraction)))
                    boundary = len(source["frames"]) - val_count
                    samples = []
                    for index, frame in enumerate(source["frames"]):
                        if cancel_event is not None and cancel_event.is_set():
                            raise VisionDatasetError(409, "Dataset freeze cancelled")
                        warped, _, normalized, evidence = self._sample(
                            directory, source, geometry, steps, frame, parameters
                        )
                        split = "train" if index < boundary else "val"
                        stem = f"sample-{index:05d}"
                        image, label = f"images/{split}/{stem}.png", f"labels/{split}/{stem}.txt"
                        ok, encoded = cv2.imencode(".png", warped)
                        if not ok:
                            raise OSError("Dataset image encoding failed")
                        _write(stage / image, encoded.tobytes())
                        lines = [
                            f"{box['class_id']} {box['cx']:.8f} {box['cy']:.8f} {box['w']:.8f} {box['h']:.8f}"
                            for box in normalized
                        ]
                        _write(stage / label, (("\n".join(lines) + "\n") if lines else "").encode("ascii"))
                        samples.append(
                            {
                                "frame_id": frame["frame_id"],
                                "applied_move_index": frame["applied_move_index"],
                                "source_sha256": frame["sha256"],
                                "board_hash": frame["board_hash"],
                                "split": split,
                                "image": image,
                                "label": label,
                                "led_evidence": evidence,
                            }
                        )
                    class_names = list(CLASS_ORDERS[source["mode"]])
                    # Omitting path lets Ultralytics use the YAML parent as the
                    # root, so transferring this frozen version changes no bytes.
                    config = {
                        "train": "images/train",
                        "val": "images/val",
                        "nc": len(class_names),
                        "names": class_names,
                    }
                    _write(stage / "data.yaml", yaml.safe_dump(config, sort_keys=False).encode("utf-8"))
                    manifest = {
                        "schema_version": SCHEMA_VERSION,
                        "id": version_id,
                        "generated_at": datetime.now(timezone.utc).isoformat(),
                        "mode": source["mode"],
                        "class_names": class_names,
                        "parameters": parameters,
                        "generator": generator,
                        "identity": identity,
                        "source": {
                            key: source[key]
                            for key in (
                                "game_id",
                                "sgf_sha256",
                                "geometry_revision",
                                "geometry_source",
                                "geometry_sha256",
                                "geometry_sidecar_sha256",
                            )
                        },
                        "source_assets": source_assets,
                        "samples": samples,
                        "assets": {
                            path.relative_to(stage).as_posix(): _sha(path.read_bytes())
                            for path in sorted(stage.rglob("*"))
                            if path.is_file()
                        },
                    }
                    manifest_bytes = _json(manifest)
                    _write(stage / "manifest.json", manifest_bytes)
                    self._validate(stage, manifest)
                    for path in stage.rglob("*"):
                        path.chmod(0o555 if path.is_dir() else 0o444)
                    stage.chmod(0o555)
                    if cancel_event is not None and cancel_event.is_set():
                        raise VisionDatasetError(409, "Dataset freeze cancelled")
                    # The stage shares the destination volume. A failed rename
                    # leaves both the source and every previous version intact.
                    os.rename(stage, final)
                    return {
                        **manifest,
                        "path": str(final),
                        "manifest_sha256": _sha(manifest_bytes),
                        "idempotent": False,
                    }
            except VisionDatasetError:
                raise
            except (OSError, ValueError, TypeError, KeyError, cv2.error) as exc:
                raise VisionDatasetError(
                    507 if isinstance(exc, OSError) else 503, "Dataset validation or atomic publication failed"
                ) from exc
