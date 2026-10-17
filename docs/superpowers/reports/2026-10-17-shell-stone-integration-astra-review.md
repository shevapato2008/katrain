# Shell stone integration — independent Astra Max review

Date: 2026-10-17  
Scope: approved shell/slate material in tutorial static diagrams and overhead 2D recording; only replacement TEST samples 1030/1031.

## Decision

**SPEC / actual visual: PASS. CODEQUALITY: PASS. Deployed TEST samples: PASS. No reproducible P1/P2 findings.**

The deployment gate and final narrow acceptance are complete: provider `6ac678ee1419`, console `5daf407b461e`. The deployed static board and both newly generated TEST 2D MP4s were checked. **Figure 1030 replays seven moves; figure 1031 remains static because its cues are pending. Human approval of both new videos remains pending.**

Reviewed working changes over APP `6f11076354d67949057cb3a1a655314a9a2d310a` and UI `d1db3ea4eecc4aa01133529fa49bb3db4afffd1a`. No deployment, live generation, review approval, DB write or commit was performed by this reviewer.

## 1. SPEC and actual visual review

| Requirement | Result and evidence |
| --- | --- |
| Keep the approved original model and studio | PASS. Promoted `stoneModel.ts` is byte-identical to the approved source at APP HEAD. Black and white-00 PNG hashes match the approved preview exports. All 33 PNG and model/studio source hashes match the manifest. |
| Varied white grain with fixed light | PASS. 32 white images have 32 distinct hashes. The actual contact sheet shows the near-parallel grain changing direction while the broad highlight stays in the same direction. Export rotates model Y under the fixed camera/environment/lights; consumers do not rotate the image. |
| Same material and stable point mapping in static/video | PASS. APP/UI images, manifest and selector source are byte-identical. Static uses figure ID and full-board top-left coordinates; recorder stores the figure ID in its snapshot and converts game Y to top-left row exactly once. Actual 1030 static white variants are 20/05/21/14 at points 15,14 / 16,13 / 15,12 / 16,8. |
| Physical ratio, upright overlays, diagram semantics | PASS. Black diameter is scaled once by 22.2/21.9; white is the reference diameter. Actual main-board and recorder images retain upright numbers and inverse last-move rings, correct stones, full-board grid and fine range boundaries without gray fill. Unknown-color rendering and click targets are preserved in the SVG path. |
| Recorder readiness and deterministic playback | PASS locally. Recording readiness waits for all 33 textures. The actual browser proof has no page errors; final → placement → backward seek → final produces identical final PNG bytes. Placement remains deterministic, with unchanged captions and 360 ms timing. |
| Only new 2D generation, historical 3D readable | PASS. Generation/retry always sends 2D even while viewing an old 3D video. Enqueue rejects new non-2D video requests before mutation. Old media/task records remain readable; the UI labels 3D as historical/read-only and offers no 3D approval control. |
| Preserve existing data/audio/review authority | PASS for the diff. Only the presentation seed is added to task snapshots/render input; existing board/narration digests, review gates, CAS, immutable audio, cue derivation and sound mixing are unchanged. No schema migration or bulk work is added. |

Personally inspected these actual image artifacts under `output/`:

- `tutorial-shell-integration-20261017/local-ui-1030.png` and `local-ui-1031.png`.
- `shell-stones-20261017/integration-sprite-contact-sheet.png`.
- `tutorial-shell-integration-20261017/local-recorder-1030-final.png` and `local-recorder-1030-placing.png`.
- `tutorial-shell-integration-20261017/static-recorder-material-comparison.png` and `material-board-overlay.png`.

The comparison uses complete 19×19 boards normalized to 600 px inside a 1280×800 image. Stone positions, upright markings and material orientation agree. Existing static/video board backgrounds, outline styles and on-screen sizes differ; this change preserves those layouts. The static board is smaller in the actual workbench and therefore has less visible fine grain than the recorder.

Also inspected `static-browser-proof.json` and `recorder-browser-proof.json`: 33 recorder PNG requests, zero page errors, and identical repeated final-frame SHA `48ed672b3f09d849a838652af2a5b15f7c2fab708b04f764466df7e77032c734` after the 9400 → 5148 → 4988 → 9400 ms sequence.

## 2. Code quality and focused verification

Reviewed the exporter and mirrored helper/assets, promoted studio/model, SVG consumer and workbench call sites, recorder/Board3D opt-in path, texture loading, task seed/2D guard, and changed focused tests. The ordinary Board3D material path is preserved. Static SVG has no Three.js dependency; recording uses shared sRGB textures with `MeshBasicMaterial`, `toneMapped: false`, and `fog: false` to avoid relighting baked sprites.

Fresh checks run by this reviewer:

- APP: `StoneGroup.test.tsx`, `tutorialStoneSprites.test.ts`, `TutorialMediaRecorder.test.tsx` — **5 passed**. Covers top-left conversion, replay order stability, normal-board opt-out and readiness before capture.
- UI: `SGFBoard.test.tsx` plus two targeted workbench cases — **4 passed** (28 unrelated cases filtered). Covers viewport/order stability, ratio/overlays/unknowns/click targets, 2D retry while viewing 3D and read-only historical 3D.
- Independent file checks: approved model promotion byte-equal, APP/UI sprite/manifest/helper equality, all manifest file/source SHA-256 values valid, 33 PNGs and 32 unique white hashes; total PNG size 2,080,295 bytes.

Implementation agents separately reported the affected backend/frontend tests, builds and a real local MP4 render passing. Those broader runs were not repeated by this reviewer. No additional test framework or audit infrastructure was introduced.

## 3. TEST sample closure — PASS

Final acceptance was limited to the deployed static UI and the two replacement **2D** samples. No code review or broad test suite was repeated.

| Figure | New task | Actual file | Playback and state |
| --- | --- | --- | --- |
| 1030 | `ed4d6b2b6c9340ab853bdbee5a7048da` | 902,091 bytes; 42.266667 s | Seven-move replay; actual browser playback and forward/backward seek completed, including return to 9.4 s; readyState 4, no media error. |
| 1031 | `ca8fbd0832b1402c96e38ffab8d17c4b` | 548,874 bytes; 25.466667 s | Honest static explanation, with permanent “静态讲解·落子时间待校准” label. Independent single-player playback advanced 0 → 0.860843 s; seek 12 → 4 s completed; readyState 4, seeking false, error null. |

Both actual encoded files are 1280×800, 15 fps, H.264/AAC. Independently calculated download SHA-256 values agree with the task metadata:

- 1030: `acb62f8476e3c02f6062fd4a3d35d381b219c08bc4cd863d8169cbed7296965e`.
- 1031: `aaeeb80d83022bf136cfc148f74b0455e625d37fc22c047ff865bdedca153d62`.

Personally viewed `actual-1030-2d.png`, `actual-1031-2d.png` extracted from those MP4s, plus `deployed-ui-1030.png` under `output/tutorial-shell-integration-20261017/`. The approved black/white material, fixed studio highlights, point-specific white orientations, upright labels, inverse ring, crosses, full-board grid and fine boundaries survive encoding; gray fill has not returned. Deployed browser evidence records the same four 1030 variants (20/05/21/14), stable after reload, with no new 3D generation option.

Independent playback used a separate `shell-integration-review-max` browser session on the sample gallery, pointing at the actual new TEST asset URLs. The first two-player attempt produced one 1031 `FFmpegDemuxer: data source error` during backward seek. A single-player reload and forward/backward seek completed successfully without a media error; the deployment owner's actual admin single-player proof also passed both assets. This transient read failure was not reproducible in the representative single-player flow and is recorded as non-blocking. The gallery's missing favicon is unrelated to playback. Browser playback was muted for this material-focused check; the previously accepted audio mix was not re-audited.

Independent before/after JSON comparison confirmed, for both figures:

- `board_payload`, narration and `board_review` are exactly preserved; authoritative board approval remains true.
- Audio metadata and speech timing are exactly preserved; cue content is unchanged (the newly published cue asset path changes as expected).
- Historical 3D metadata is preserved.
- Both jobs succeeded with `generated_audio: false`; `video_2d_review` remains null.

Evidence: `actual-sample-metadata.json`, `deployed-browser-proof.json`, `actual-browser-playback-proof.json`; private `before-{1030,1031}.json`, `after-{1030,1031}.json` and downloaded MP4s under `~/.local/share/smartbox-admin/tutorial-shell-integration-20261017/`. No TTS, new 3D sample, bulk approval or full-book generation was part of this acceptance. The reviewer made no live mutations and did not approve either video.
