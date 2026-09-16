# Board-ROI Motion Gate Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Gate vision inference on motion inside an expanded physical-board region while retaining a coarse full-frame camera-shake guard.

**Architecture:** A focused ROI-mask cache converts validated camera-space board corners into a deterministic, one-grid-spacing-expanded boolean mask. `MotionFilter` remains responsible only for frame differencing and returns ROI/full-frame diagnostic ratios. Each worker supplies geometry only when it can prove that the corners and differenced frame share a coordinate space; otherwise it preserves the current full-frame behavior.

**Tech Stack:** Python 3, NumPy, OpenCV, pytest, systemd/SSH acceptance on RK3562.

**Spec:** `docs/superpowers/specs/2026-09-16-board-roi-motion-gate-design.md`

---

## Chunk 1: Motion primitives, worker integration, and device verification

### File map

- Create `katrain/vision/motion_roi.py`: validate/scale corners and cache the deterministic expanded-board mask.
- Modify `katrain/vision/motion_filter.py`: compare frames once, return ROI and full-frame ratios, handle shape changes, and expose `reset()`.
- Modify `katrain/vision/worker_inprocess.py`: use geometry-lock corners, lifecycle invalidation, hybrid gate, and rate-limited diagnostics.
- Modify `katrain/vision/worker.py`: use only locked raw-space `BoardFinder` corners, lifecycle invalidation, hybrid gate, and matching diagnostics.
- Modify `tests/test_vision/test_motion_filter.py`: unit coverage for ROI/full-frame decisions and history reset.
- Create `tests/test_vision/test_motion_roi.py`: mask validation, scaling, expansion, caching, and safe fallback.
- Modify `tests/test_vision/test_worker_commands.py`: lifecycle parity and coordinate-space fallback tests without loading camera/model hardware.

### Task 1: Deterministic board ROI mask

**Files:**
- Create: `katrain/vision/motion_roi.py`
- Create: `tests/test_vision/test_motion_roi.py`

- [ ] **Step 1: Write failing ROI tests**

Cover these exact cases:

```python
def test_mask_fills_board_and_expands_one_mean_grid_spacing(): ...
def test_mask_scales_corners_from_calibration_resolution(): ...
def test_old_lock_without_source_size_uses_current_pixel_space(): ...
@pytest.mark.parametrize("corners", [MALFORMED, NONFINITE, DEGENERATE, WHOLLY_OFFSCREEN])
def test_invalid_corners_return_none(corners): ...
def test_partially_clipped_board_remains_valid(): ...
def test_cache_reuses_mask_and_source_dimensions_are_part_of_key(): ...
def test_invalidate_forces_mask_rebuild(): ...
```

Use a 200×300 frame and rectangle `[(60, 40), (240, 40), (240, 160), (60, 160)]`. The mean edge length is 150, so the deterministic radius is `round(150 / 18) == 8`. Assert a point seven pixels outside an edge is included and a point ten pixels outside is excluded; avoid ellipse-corner assertions where morphology shape is intentionally rounded. Define `source_size` everywhere as `(source_width, source_height)`. For scaling, use source size `(600, 400)`, current frame `(200, 300, 3)`, and source corners `[(120, 80), (480, 80), (480, 320), (120, 320)]`; expect the rectangle and radius above after 0.5× scaling. A polygon crossing an image edge is valid if its clipped fill has nonzero area; only a wholly off-frame polygon is rejected.

- [ ] **Step 2: Run the tests and confirm RED**

Run:

```bash
.venv/bin/python -m pytest tests/test_vision/test_motion_roi.py -q
```

Expected: collection/import failure because `katrain.vision.motion_roi` does not exist.

- [ ] **Step 3: Implement the minimal helper and cache**

Implement this public boundary:

```python
def build_motion_roi_mask(
    frame_shape: tuple[int, ...],
    corners,
    source_size: tuple[int | None, int | None] = (None, None),
) -> np.ndarray | None:
    """Return an expanded boolean board mask in frame coordinates, or None."""


class MotionRoiMaskCache:
    def get(self, frame_shape, corners, source_size=(None, None)) -> np.ndarray | None: ...
    def invalidate(self) -> None: ...
```

Validation and construction order:

1. require image height/width >0 and finite `(4,2)` float corners;
2. interpret `source_size` as `(source_width, source_height)`; when both positive dimensions exist, scale x/y into current dimensions; when both are absent, assume current coordinates; one-sided/invalid dimensions return `None`;
3. reject a zero-area polygon or a polygon whose filled intersection with the image is empty;
4. fill with `cv2.fillConvexPoly`;
5. derive radius from the scaled polygon using `max(1, round(mean(edge_lengths) / 18))`;
6. dilate once using `cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2*r+1, 2*r+1))`;
7. return `mask.astype(bool)`.

The cache key contains frame shape, normalized float32 corner bytes, and normalized source dimensions. `None` results may be cached for the same key.

- [ ] **Step 4: Run ROI tests and confirm GREEN**

Run the Task 1 pytest command. Expected: all tests pass.

- [ ] **Step 5: Commit Task 1**

```bash
git add katrain/vision/motion_roi.py tests/test_vision/test_motion_roi.py
git commit -m "add board motion ROI mask"
```

### Task 2: Hybrid motion-filter decision

**Files:**
- Modify: `katrain/vision/motion_filter.py`
- Modify: `tests/test_vision/test_motion_filter.py`

- [ ] **Step 1: Add failing filter tests**

Add tests for:

```python
def test_roi_motion_rejects_when_full_frame_change_is_below_five_percent(): ...
def test_motion_outside_roi_is_stable_below_global_guard(): ...
def test_large_full_frame_change_rejects_even_when_roi_is_quiet(): ...
def test_missing_or_empty_mask_falls_back_to_full_frame(): ...
@pytest.mark.parametrize("next_frame", [DIFFERENT_HEIGHT_WIDTH, GRAYSCALE_AFTER_BGR, BGR_AFTER_GRAYSCALE])
def test_dimension_or_channel_layout_change_establishes_a_fresh_baseline(next_frame): ...
def test_reset_establishes_a_fresh_baseline(): ...
def test_rejected_frame_becomes_the_next_comparison_baseline(): ...
```

Use synthetic constant frames and rectangular masks. Assert both the boolean decision and returned `(roi_ratio, full_ratio)`; fallback returns `roi_ratio is None`.

- [ ] **Step 2: Run the focused test and confirm RED**

```bash
.venv/bin/python -m pytest tests/test_vision/test_motion_filter.py -q
```

Expected: failures because the regional API and `reset()` do not exist.

- [ ] **Step 3: Implement regional comparison without breaking old callers**

Add:

```python
def reset(self) -> None:
    self.prev_frame = None

def is_stable_with_regions(
    self,
    frame: np.ndarray,
    roi_mask: np.ndarray | None = None,
    global_change_ratio_threshold: float = 0.30,
) -> tuple[bool, float | None, float]:
    ...
```

Before `cv2.absdiff`, compare the complete raw array shape (including channel layout). If it differs, copy the new frame as a baseline and return without attempting conversion or subtraction. Otherwise compute `changed = gray_diff > pixel_diff_threshold` once. If history is absent, copy the frame and return `(True, 0.0 if a valid nonempty mask exists else None, 0.0)`. A valid mask must match `gray_diff.shape` and contain at least one pixel; otherwise use full-frame fallback. In ROI mode return stability as:

```python
roi_ratio < self.change_ratio_threshold and full_ratio < global_change_ratio_threshold
```

Assign `self.prev_frame = frame.copy()` on every compatible-shape comparison before returning, including rejected frames. Keep `is_stable()` returning exactly one boolean and keep `is_stable_with_ratio()` returning exactly the legacy two-tuple `(stable, full_ratio)` by delegating without a mask and discarding the new ROI field.

- [ ] **Step 4: Run motion-filter tests and confirm GREEN**

Run the Task 2 command. Expected: all tests pass.

- [ ] **Step 5: Commit Task 2**

```bash
git add katrain/vision/motion_filter.py tests/test_vision/test_motion_filter.py
git commit -m "gate motion inside board region"
```

### Task 3: Integrate the RK3562 in-process worker

**Files:**
- Modify: `katrain/vision/worker_inprocess.py`
- Modify: `tests/test_vision/test_worker_commands.py`

- [ ] **Step 1: Add failing lifecycle and geometry tests**

Construct `InProcessAdapter` with `StoneDetector` patched, as existing tests do. Test:

- a geometry lock produces an ROI mask using its corners and source dimensions;
- `set_geometry(new_or_none)` invalidates the cache and calls `MotionFilter.reset()`;
- `UNBIND` resets motion history;
- `RESET_SYNC` does not reset motion history or invalidate the mask;
- a frame-size change is handled by the cache/filter and becomes a fresh baseline.
- the worker's motion-gate helper passes the generated mask to `is_stable_with_regions()`;
- a rejected result resets the averager and returns `False`, which is the loop's guard before warp/inference;
- a one-iteration `_loop` test uses a fake camera that stops the loop after returning one frame, forces `_motion_is_stable()` to `False`, and asserts `_warp_frame`, detector inference, board voting, and `detect_new_move` are never called;
- with `time.monotonic()` patched, the first rejection logs immediately, another within five seconds does not, and one after five seconds does;
- the stable diagnostic formatter emits `roi:<ratio>/full:<ratio>` and emits `full:N/A/full:<ratio>` during fallback.

- [ ] **Step 2: Run focused tests and confirm RED**

```bash
.venv/bin/python -m pytest tests/test_vision/test_worker_commands.py tests/test_vision/test_motion_filter.py tests/test_vision/test_motion_roi.py -q
```

Expected: new worker assertions fail before integration.

- [ ] **Step 3: Implement the in-process integration**

Add `MotionRoiMaskCache`, `_last_motion_log`, `_motion_mask(frame)`, and `_motion_is_stable(frame)` helpers. `set_geometry()` invalidates the cache and resets the filter after every replacement/removal. `UNBIND` resets the filter; do not touch it in `RESET_SYNC`.

`_motion_is_stable(frame)` calls `is_stable_with_regions(frame, self._motion_mask(frame))`, stores the two ratios for the periodic line, resets the averager on rejection, applies the first/immediate then five-second logging policy, and returns only the stable boolean. Replace the raw filter call in `_loop` with `if frame is not None and self._motion_is_stable(frame):`; because warp and inference remain wholly inside that branch, `False` skips all downstream work. Extend the existing every-30-processed-frame line with `motion=roi:<ratio>/full:<ratio>` or `motion=full:N/A/full:<ratio>`.

- [ ] **Step 4: Run focused tests and confirm GREEN**

Run the Task 3 command. Expected: all tests pass.

- [ ] **Step 5: Commit Task 3**

```bash
git add katrain/vision/worker_inprocess.py tests/test_vision/test_worker_commands.py
git commit -m "use board ROI for in-process motion gating"
```

### Task 4: Keep the subprocess worker behaviorally aligned

**Files:**
- Modify: `katrain/vision/worker.py`
- Modify: `tests/test_vision/test_worker_commands.py`

- [ ] **Step 1: Add failing subprocess policy tests**

Using `_VisionWorkerLoop.__new__` and mocks, test:

- unlocked worker returns no ROI;
- locked worker with uncalibrated `BoardFinder` uses `pre_corner_point`;
- locked worker with calibrated/undistorted `BoardFinder` returns no ROI;
- `CONFIRM_POSE_LOCK`, `RESET_SYNC`, auto-unlock, and `UNBIND` reset the filter and invalidate the cache;
- full-frame fallback continues to call the hybrid filter with `roi_mask=None`.
- the worker's motion-gate helper passes a generated mask to `is_stable_with_regions()`, and a rejection resets the averager and returns `False` before board finding/inference;
- a one-iteration `_processing_loop` test uses a fake camera that stops the loop after returning one frame, forces `_motion_is_stable()` to `False`, and asserts `BoardFinder.find_focus`, detector inference, board voting, and `detect_new_move` are never called;
- the immediate/five-second rejection logs and stable diagnostic formatting match the in-process worker.

- [ ] **Step 2: Run the worker test and confirm RED**

```bash
.venv/bin/python -m pytest tests/test_vision/test_worker_commands.py -q
```

Expected: new subprocess assertions fail before integration.

- [ ] **Step 3: Implement matching subprocess policy**

Add the same cache, diagnostic state, and loop call. `_motion_mask(frame)` returns a mask only when `_board_locked` is true, four corners exist, and `BoardFinder.camera_config` is absent or uncalibrated. Otherwise it returns `None`.

Centralize lock-transition cleanup in a tiny `_reset_motion_region()` method that invalidates the cache and resets `MotionFilter`; call it from `CONFIRM_POSE_LOCK`, `RESET_SYNC`, `UNBIND`, and the existing auto-unlock branch. Preserve all existing board/move/sync semantics.

- [ ] **Step 4: Run focused tests and confirm GREEN**

Run the Task 4 command. Expected: all tests pass.

- [ ] **Step 5: Commit Task 4**

```bash
git add katrain/vision/worker.py tests/test_vision/test_worker_commands.py
git commit -m "align subprocess board motion gating"
```

### Task 5: Regression verification and RK3562 acceptance

**Files:**
- No production file changes expected.

- [ ] **Step 1: Run vision regression tests**

```bash
.venv/bin/python -m pytest tests/test_vision -q
```

Expected: all vision tests pass.

- [ ] **Step 2: Review exactly this implementation's scope**

```bash
MOTION_GATE_BASE_SHA=$(git log -1 --format=%H --grep='^document board ROI motion gate$')
git diff --name-status "$MOTION_GATE_BASE_SHA"..HEAD
git diff "$MOTION_GATE_BASE_SHA"..HEAD -- katrain/vision/motion_roi.py katrain/vision/motion_filter.py katrain/vision/worker.py katrain/vision/worker_inprocess.py tests/test_vision
```

Expected changed production paths are only the four vision files listed above, plus their focused tests. The unfiltered `--name-status` output must contain no frontend, web backend, i18n, or unrelated files. Confirm both workers implement the specified lifecycle distinctions.

- [ ] **Step 3: Run the real board-link preflight**

```bash
/Users/fan/Repositories/smartbox-software/scripts/deploy-main-to-rk3562.sh check
```

Expected: `en10`, route, ARP, and SSH each print `[OK]`. Stop on any failure.

- [ ] **Step 4: Back up the deployed vision package and sync only runtime files**

```bash
(
  set -euo pipefail
  files=(katrain/vision/motion_roi.py katrain/vision/motion_filter.py katrain/vision/worker.py katrain/vision/worker_inprocess.py)
  ssh rk3562-direct "test ! -e /root/smartbox-software/.deploy-backups/motion-roi-pre.tgz && mkdir -p /root/smartbox-software/.deploy-backups && tar -czf /root/smartbox-software/.deploy-backups/motion-roi-pre.tgz -C /root/smartbox-software/vendor/katrain katrain/vision"
  rsync -azc "${files[@]}" rk3562-direct:/root/smartbox-software/vendor/katrain/katrain/vision/
  for file in "${files[@]}"; do
    local_hash=$(shasum -a 256 "$file"); local_hash=${local_hash%% *}
    remote_line=$(ssh rk3562-direct "sha256sum /root/smartbox-software/vendor/katrain/katrain/vision/${file##*/}")
    remote_hash=${remote_line%% *}
    test "$local_hash" = "$remote_hash"
    printf '%s  %s\n' "$local_hash" "$file"
  done
)
```

Expected: backup command exits 0, rsync exits 0, and all four local/remote SHA-256 pairs match. If sync or hash validation fails, restore with:

```bash
ssh rk3562-direct "tar -xzf /root/smartbox-software/.deploy-backups/motion-roi-pre.tgz -C /root/smartbox-software/vendor/katrain && rm -f /root/smartbox-software/vendor/katrain/katrain/vision/motion_roi.py && systemctl restart smartbox-katrain.service"
```

The rollback removal is correct for this first deployment because `motion_roi.py` does not exist in the pre-deployment tree.

- [ ] **Step 5: Restart and prove service health**

```bash
ssh rk3562-direct 'set -eu; systemctl restart smartbox-katrain.service; code=000; for i in $(seq 1 40); do sleep 1; code=$(curl -s -o /dev/null -w "%{http_code}" --max-time 3 http://127.0.0.1:8081/kiosk 2>/dev/null || true); test "$code" = 200 && break; done; test "$code" = 200; systemctl is-active smartbox-katago-api.service smartbox-katrain.service smartbox-kiosk.service; curl -fsS -o /dev/null http://127.0.0.1:8000/health'
```

Expected: kiosk reaches 200 within 40 seconds, all three services print `active`, and KataGo health exits 0. On failure, run the rollback command from Step 4 and re-check health before stopping.

- [ ] **Step 6: Run the five physical acceptance cases with timestamped evidence**

Immediately before each physical case, record the board clock and label it with that case:

```bash
ssh rk3562-direct "date '+%Y-%m-%d %H:%M:%S'"
```

Save each exact timestamp. Perform the corresponding case, then retrieve evidence using that case's literal `--since` value:

```bash
ssh rk3562-direct "journalctl -u smartbox-katrain.service --since 'RECORDED BOARD TIMESTAMP' --no-pager | grep -E 'motion rejected|motion=(roi|full)|move confirmed|ambiguous'"
```

Pass criteria:

- outside-board hand: stable below 30% full-frame change;
- hand enters margin/board: rejection occurs by the grid boundary;
- place/withdraw: exactly one move event after 3/5-frame confirmation;
- camera shake: full-frame guard rejects;
- same-scene warmed 20-second median processed-frame interval is at most 360 ms.

For the throughput case, leave the same early-game scene untouched, record a warmed sample, and calculate the interval from the every-30-processed-frame `vision:` log markers:

```bash
PERF_START=$(ssh rk3562-direct "date '+%Y-%m-%d %H:%M:%S'")
sleep 25
ssh rk3562-direct "journalctl -u smartbox-katrain.service --since '$PERF_START' -o short-unix --no-pager" | .venv/bin/python -c 'import statistics,sys; ts=[float(line.split()[0]) for line in sys.stdin if "worker_inprocess:vision:" in line]; samples=[(b-a)/30 for a,b in zip(ts,ts[1:])]; assert samples, "need at least two vision log markers"; med=statistics.median(samples); print(f"processed_frame_interval_median={med*1000:.1f}ms samples={len(samples)}"); assert med <= 0.360, f"median {med*1000:.1f}ms exceeds 360ms"'
```

Expected: at least two periodic markers, a printed median at or below `360.0ms`, and exit code 0.

- [ ] **Step 7: Capture and inspect the kiosk screen and Chromium geometry**

```bash
ssh rk3562-direct "DISPLAY=:0 scrot /tmp/kiosk-motion-roi.png; DISPLAY=:0 xdotool search --onlyvisible --class Chromium getwindowgeometry %@; curl -fsS http://127.0.0.1:9222/json/list"
scp rk3562-direct:/tmp/kiosk-motion-roi.png /private/tmp/kiosk-motion-roi.png
```

Expected: exactly one visible Chromium window at `0,0`, geometry `1024x600`, exactly one page target at `http://127.0.0.1:8081/kiosk/...`, and the screenshot shows the normal fullscreen kiosk without browser chrome.

- [ ] **Step 8: Handle any evidence-backed threshold adjustment**

If no threshold adjustment is needed, keep the prior task commits. If acceptance requires an adjustment, change only the relevant default and run:

```bash
(
  set -euo pipefail
  files=(katrain/vision/motion_roi.py katrain/vision/motion_filter.py katrain/vision/worker.py katrain/vision/worker_inprocess.py)
  .venv/bin/python -m pytest tests/test_vision/test_motion_filter.py tests/test_vision/test_motion_roi.py tests/test_vision/test_worker_commands.py -q
  .venv/bin/python -m pytest tests/test_vision -q
  git add katrain/vision/motion_filter.py katrain/vision/motion_roi.py tests/test_vision/test_motion_filter.py tests/test_vision/test_motion_roi.py tests/test_vision/test_worker_commands.py
  git commit -m "tune board motion thresholds"
  rsync -azc "${files[@]}" rk3562-direct:/root/smartbox-software/vendor/katrain/katrain/vision/
  for file in "${files[@]}"; do
    local_hash=$(shasum -a 256 "$file"); local_hash=${local_hash%% *}
    remote_line=$(ssh rk3562-direct "sha256sum /root/smartbox-software/vendor/katrain/katrain/vision/${file##*/}")
    remote_hash=${remote_line%% *}
    test "$local_hash" = "$remote_hash"
  done
  ssh rk3562-direct 'set -eu; systemctl restart smartbox-katrain.service; code=000; for i in $(seq 1 40); do sleep 1; code=$(curl -s -o /dev/null -w "%{http_code}" --max-time 3 http://127.0.0.1:8081/kiosk 2>/dev/null || true); test "$code" = 200 && break; done; test "$code" = 200'
)
```

Then repeat each physical case affected by the adjusted threshold, record a fresh per-case timestamp, and re-run the Step 6 journal query and throughput calculation. Do not proceed to publication unless the adjusted board evidence passes.

- [ ] **Step 9: Publish KaTrain and advance the smartbox submodule**

```bash
(
  set -euo pipefail
  git status --short --branch
  test "$(git branch --show-current)" = fix/kiosk-ui-debug
  test "$(git -C /Users/fan/Repositories/katrain branch --show-current)" = develop
  test "$(git -C /Users/fan/Repositories/smartbox-software branch --show-current)" = main
  git diff --cached --quiet
  git diff --quiet -- katrain/vision/motion_roi.py katrain/vision/motion_filter.py katrain/vision/worker.py katrain/vision/worker_inprocess.py tests/test_vision
  git -C /Users/fan/Repositories/katrain diff --cached --quiet
  git -C /Users/fan/Repositories/smartbox-software diff --cached --quiet
  git fetch origin
  git merge origin/develop
  .venv/bin/python -m pytest tests/test_vision -q
  git push origin fix/kiosk-ui-debug
  git -C /Users/fan/Repositories/katrain merge --ff-only fix/kiosk-ui-debug
  git -C /Users/fan/Repositories/katrain push origin develop
  KATRAIN_PUBLISHED_SHA=$(git rev-parse HEAD)
  test "$(git -C /Users/fan/Repositories/katrain rev-parse HEAD)" = "$KATRAIN_PUBLISHED_SHA"
  git -C /Users/fan/Repositories/smartbox-software/vendor/katrain checkout "$KATRAIN_PUBLISHED_SHA"
  test "$(git -C /Users/fan/Repositories/smartbox-software/vendor/katrain rev-parse HEAD)" = "$KATRAIN_PUBLISHED_SHA"
  git -C /Users/fan/Repositories/smartbox-software add vendor/katrain
  test "$(git -C /Users/fan/Repositories/smartbox-software diff --cached --name-only)" = vendor/katrain
  git -C /Users/fan/Repositories/smartbox-software commit -m "update katrain board motion gating"
  git -C /Users/fan/Repositories/smartbox-software push origin main
)
```

Expected: the current worktree shows no unexpected uncommitted implementation files; branch guards and all three staged-change guards exit 0; vision tests pass after merging current `origin/develop`; feature and `develop` point to the same published KaTrain SHA; smartbox stages only `vendor/katrain`, whose checked-out SHA exactly matches it. Preserve the pre-existing untracked `/Users/fan/Repositories/katrain/m.html` and modified `vendor/hermes-agent` without staging either.
