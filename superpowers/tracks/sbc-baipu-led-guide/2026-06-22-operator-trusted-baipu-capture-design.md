# Operator-Trusted Baipu Capture Design

**Date:** 2026-06-22  
**Status:** Approved direction; implementation pending  
**Track:** `sbc-baipu-led-guide`

## 1. Goal

The current phase exists to bootstrap a YOLOv11 black/white stone dataset. The operator follows the LED and explicitly confirms each placement. That confirmation is the ground truth; image recognition must not accept, reject, or delay a capture.

The system must therefore do only this for every move:

1. Trust the operator's confirmation.
2. Advance the SGF-authoritative move index.
3. Light the next guided move, if one exists.
4. Wait for the LED/camera synchronization barrier.
5. Save the image and metadata in the directory for that SGF.

Stone-recognition QA will be reintroduced only after an initial YOLOv11 model exists and is separately validated.

## 2. Decisions

### 2.1 No recognition in collection mode

`/api/v1/baipu/capture` will not call the classical HSV classifier, compare against an empty-board baseline, or return a placement mismatch. The endpoint will not depend on `model_ready` or `recognition_ready`.

The existing classical classifier remains available to other code and offline diagnostics, but it is removed from the baipu capture decision path. No threshold adjustment is part of this change.

### 2.2 Operator confirmation is authoritative

The frontend's **Confirm placement** action is the only placement acceptance event. The backend uses the loaded SGF to derive applied move, next move, board hash, color, and canonical coordinates. It does not infer any of those values from the image.

The mismatch correction UI is removed from the active collection flow. Existing manifests with `qa_status=ok` or `operator_override` remain readable.

### 2.3 One directory per SGF identifier

Every loaded source keeps its existing stable SGF identifier, such as `kifu_24171`. Captures are stored under:

```text
<capture_dir>/<sgf_id>/
  game.sgf
  geometry.npz
  geometry.json
  manifest.json
  frame_000.jpg
  frame_001.jpg
  ...
```

Different SGF identifiers must never share a manifest or frame sequence. Reopening the same SGF identifier resumes from its manifest rather than creating an unrelated directory. Existing slug/path-containment validation remains mandatory.

## 3. Capture Data Flow

### 3.1 Initial frame

After loading an SGF and entering a calibrated baipu session, the system lights the first playable move and saves `frame_000.jpg`. Its manifest entry keeps `frame_kind=initial_led`, `applied_move_index=-1`, and `next_guided_move_index=0` (or the first non-pass placement).

### 3.2 Confirmed move

For a confirmed move index `N`:

1. Validate the index and SGF session contract.
2. Compute the SGF-authoritative board through `N` and its board hash.
3. Find the next playable placement after `N`.
4. If present, send the next LED color/point and wait for strict `SHOW` acknowledgement.
5. Capture only a frame newer than the LED acknowledgement plus settle time.
6. Atomically save the frame and manifest entry.
7. Return the saved frame and next-guidance metadata to the frontend.

If no next placement exists, clear the LED and capture the final board without a guidance light according to the existing end/pass behavior.

### 3.3 Manifest semantics

New collection entries use:

```json
{
  "qa_status": "operator_confirmed"
}
```

This field means that the image was accepted from an explicit operator action and was not machine-verified. Other fields remain authoritative and unchanged: `frame_kind`, `applied_move_index`, `next_guided_move_index`, `led_point`, `board_through_index`, `board_hash`, `seq`, and `file`.

## 4. Frontend Behavior

The baipu page remains a sequential workflow:

1. Show the SGF move and LED guidance.
2. Operator places the stone.
3. Operator selects **Confirm placement**.
4. Disable the action while capture is in progress.
5. On success, increment the captured-frame count and display the next move/LED.

The frontend must not render mismatch details, **Correct and retry**, or **Confirm correct and continue** during operator-trusted collection. Hardware, storage, invalid-index, and LED/camera synchronization failures remain blocking errors because they mean a valid training image was not saved.

## 5. Error Handling

- Camera unavailable or no fresh frame: fail the capture and keep the current move pending.
- LED unavailable when a next placement requires guidance: fail the capture and keep the current move pending.
- Invalid SGF identifier or path escape: reject the request.
- Duplicate capture of the same move and identical payload: preserve existing idempotent response behavior.
- Conflicting duplicate payload: preserve the existing conflict response.
- Manifest or image write failure: do not advance the frontend move.
- Recognition service absent, disabled, inaccurate, or unloaded: irrelevant to baipu collection and never an error.

## 6. Compatibility

- Existing capture directories and manifests remain valid.
- Existing `qa_status` values are not rewritten.
- New entries use `operator_confirmed` so downstream tooling can distinguish bootstrapped, human-confirmed data from future model-verified data.
- Future YOLOv11 QA must be introduced behind an explicit capture-policy/version field rather than silently changing the meaning of operator-trusted sessions.

## 7. Verification

Backend tests must prove:

1. Capture succeeds when the classifier would report a mismatch.
2. The classifier is not invoked in operator-trusted mode.
3. New manifest entries use `qa_status=operator_confirmed`.
4. Confirmation lights the next move before the saved-frame synchronization barrier.
5. Two SGF identifiers create independent directories and manifests.
6. Reopening one SGF resumes only that SGF's sequence.

Frontend tests must prove:

1. A capture success advances immediately to the next move.
2. HTTP placement-mismatch UI and override controls are absent.
3. Hardware/storage failures remain visible and do not advance.

Manual hardware verification uses a short SGF: place and confirm at least three moves, then verify sequential images and manifest entries in that SGF's directory. The saved images must show the board after the confirmed move and the LED for the next guided move.

