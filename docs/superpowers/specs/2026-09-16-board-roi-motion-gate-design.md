# Board-ROI Motion Gate Design

## Goal

Make the existing frame-difference motion gate react to hands moving on or immediately around the physical Go board without pausing recognition for unrelated motion elsewhere in the camera frame.

This remains a motion gate, not a semantic hand detector. A completely stationary hand is explicitly out of scope.

## Current behavior

`MotionFilter` compares each raw camera frame with the previous raw frame. A pixel counts as changed when its grayscale difference exceeds 30; a frame is rejected when changed pixels occupy at least 5% of the full image. Both workers call this gate before board warping and stone inference.

Consequences:

- motion outside the board can unnecessarily pause recognition;
- a hand over the board can occupy less than 5% of the full camera image and evade the gate;
- the early gate is cheap and avoids running inference on moving frames, which must be preserved.

## Chosen design

Use a hybrid gate:

1. The primary changed-pixel ratio is measured inside the calibrated board quadrilateral expanded outward by one grid spacing. The expansion catches a hand just before it crosses the outer grid line.
2. A separate, substantially higher full-frame ratio remains as a guard for camera shake, major exposure transitions, or movement of the whole scene.
3. A frame is stable only when both the expanded-board ratio and the coarse full-frame ratio are below their thresholds.
4. When no usable board geometry exists, retain the current full-frame 5% behavior.

Start with the existing 5% threshold for the expanded board region and a 30% coarse full-frame threshold. These are defaults, not new UI settings. The board test described below is the acceptance authority; adjust only if its evidence shows a threshold is wrong.

## Components and data flow

### MotionFilter

Extend the filter so one frame comparison computes:

- the changed ratio within an optional boolean ROI mask;
- the changed ratio across the full frame.

The filter continues updating its previous-frame reference on every call, including rejected frames. Its existing no-mask behavior remains unchanged for callers that do not supply geometry.

If frame dimensions or channel layout change, the filter must discard its previous frame, accept the new frame only as a fresh baseline, and report zero ratios. It must never call `cv2.absdiff` across incompatible shapes.

The API returns the stable decision and diagnostic ratios without performing board geometry work itself. This keeps frame differencing independently testable.

### ROI construction

Create a small vision helper with one strict contract: it accepts finite `(4,2)` corners expressed in the exact pixel coordinate space of the frame passed to `MotionFilter`, the corner source dimensions when known, and the current frame dimensions; it returns a boolean mask or `None`.

- Scale stored corners when calibration resolution differs from capture resolution.
- For an old geometry lock without `source_width`/`source_height`, preserve the existing geometry-lock convention and assume its corners already match the current frame. Invalid or implausible coordinates still return `None`.
- Fill the convex board polygon.
- Calculate `radius = max(1, round(mean(four edge lengths) / 18))` pixels, then expand the filled polygon with one elliptical dilation kernel of size `(2 * radius + 1, 2 * radius + 1)`. This is the deterministic one-grid-spacing margin used by implementation and tests.
- Clip naturally at image boundaries.
- Cache by corners, corner source dimensions, and frame dimensions; rebuild when any of them change.

The in-process worker uses the active geometry-lock corners, which are in raw camera coordinates.

The subprocess worker may use `BoardFinder` corners only while its transform is locked and only when those corners are in raw-frame coordinates. When camera calibration makes `BoardFinder` detect corners in an undistorted image, the subprocess worker must use full-frame fallback rather than mixing that coordinate space with the raw frame. Before lock, after unlock, or while reacquiring corners, it also uses full-frame fallback. This deliberately keeps the secondary worker safe and small; the RK3562 runtime uses the in-process path.

### Worker behavior

Both `worker_inprocess.py` and `worker.py` must apply the same policy:

1. read frame;
2. obtain or reuse the expanded-board mask;
3. run the hybrid motion gate;
4. on rejection, reset the temporal averager and skip warp, inference, voting, and move-confirmation work;
5. on stability, continue through the existing pipeline unchanged.

`SET_GEOMETRY`, including removal of geometry, invalidates the cached mask and resets motion history. `UNBIND` resets motion history at the session boundary. A frame shape/channel change rebuilds the mask and establishes a fresh history baseline. In the subprocess worker, board lock/unlock transitions do the same. `RESET_SYNC` leaves the in-process geometry lock in place and therefore preserves its mask and motion history; the subprocess worker's existing `RESET_SYNC` handler unlocks `BoardFinder`, so that path invalidates the ROI and resets motion history as part of the lock transition.

## Safety and failure behavior

- Missing, malformed, degenerate, or out-of-frame corners must not crash recognition; they cause full-frame fallback.
- A zero-area ROI must never be used as a denominator.
- The first frame after motion-history invalidation establishes a new baseline and performs no cross-coordinate comparison.
- The change must not alter stone confidence thresholds, two-frame cell voting, adaptive 3/5-frame move confirmation, ambiguous-stone behavior, or synchronization state.
- Movement outside the ROI remains ignored unless it crosses the coarse full-frame guard.
- Stationary-hand detection is not claimed or implemented.

## Verification

### Automated tests

- Existing no-mask `MotionFilter` behavior remains compatible.
- Motion inside the ROI rejects a frame even when it is less than 5% of the full image.
- Motion outside the ROI does not reject a frame below the coarse full-frame threshold.
- Large full-frame motion still rejects a frame.
- Missing and degenerate geometry fall back safely.
- ROI scaling and one-grid-spacing expansion work at a second capture resolution.
- Both worker paths pass the generated mask when their coordinate-space contract is satisfied.
- `SET_GEOMETRY` replacement/removal, `UNBIND`, frame-shape changes, and subprocess board lock/unlock transitions reset motion history and invalidate/rebuild the mask as specified.
- `RESET_SYNC` preserves motion history and the cached mask in the in-process worker, but invalidates both in the subprocess worker because that handler unlocks `BoardFinder`.

### RK3562 acceptance

Both workers log the first rejected frame immediately and then rate-limit further rejection diagnostics to at most once every five seconds. Their existing periodic vision log on stable frames includes the current mode (`roi` or `full`), ROI ratio (`N/A` in full-frame fallback), and full-frame ratio. This is diagnostic logging only; no new API or persistent telemetry is added.

At the physical 1024×600 kiosk, capture those logs and verify one representative run of each case:

1. a hand moves outside the board: the sampled frames remain stable unless full-frame change reaches 30%;
2. a hand approaches through the one-grid margin and crosses onto the board: at least one moving frame is rejected before or at the grid boundary;
3. a stone is placed and the hand withdraws: recognition resumes and emits exactly one move after the existing 3/5-frame confirmation, with no false extra or ambiguous event;
4. the camera or whole scene is shaken: at least one frame is rejected by the full-frame guard;
5. over a warmed 20-second early-board sample of the same scene, median processed-frame interval is no more than 5% above the current 342.8 ms baseline (at most 360 ms).

No new UI, model, service, or persistent configuration is introduced.
