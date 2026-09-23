"""Run the deployed detector on saved warped frames; dump raw (pre-dedup) and deduped boxes.

Mirrors worker_inprocess: enhance_for_inference(clahe) -> backend.detect(conf=sustain 0.20, iou default)
-> dedup_detections. Read-only: loads its own RKNN context, touches no service state.
Usage (on the board, cwd = vendor/katrain): python board_detect_dump.py <frames_dir> <out.json>
"""
import glob
import json
import os
import sys

import cv2

from katrain.vision.enhance import enhance_for_inference
from katrain.vision.stone_detector import StoneDetector, dedup_detections

MODEL = "/opt/smartbox/share/katrain-vision/go4_s.rknn"
frames_dir, out_path = sys.argv[1], sys.argv[2]
det = StoneDetector(MODEL, backend="rknn", confidence_threshold=0.20)
out = {}
for path in sorted(glob.glob(os.path.join(frames_dir, "*.jpg"))):
    img = cv2.imread(path)
    enh = enhance_for_inference(img, "clahe")
    raw = det.backend_impl.detect(enh, det.confidence_threshold, det.iou_threshold)
    kept = dedup_detections(raw)
    pack = lambda ds: [
        {"x": d.x_center, "y": d.y_center, "cls": d.class_id, "conf": round(d.confidence, 4), "bbox": list(d.bbox)}
        for d in ds
    ]
    out[os.path.basename(path)] = {"shape": list(img.shape), "raw": pack(raw), "dedup": pack(kept)}
    print(os.path.basename(path), len(raw), len(kept), flush=True)
json.dump(out, open(out_path, "w"))
