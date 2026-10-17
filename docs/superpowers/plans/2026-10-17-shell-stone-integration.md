# 教程静态棋图与 2D 视频碁石接入 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development. Keep tests and review focused on this approved visual integration.

**Goal:** Apply the approved paired shell/slate model to tutorial static diagrams and overhead 2D videos, with varied but stable white grain directions, and deploy TEST with two replacement sample videos.

**Architecture:** Pre-render 32 white orientations and one black overhead sprite from the approved real model under fixed lighting; only stone material rotates, not lighting/labels. Reuse the identical generated assets in SVG static boards and the recorder's opt-in 2D stone plane, preserving physical black/white diameter ratio. This keeps RK3562 free of local Three.js and makes static/video appearances identical. Keep the current replay, timing, audio, human-review and CAS contracts unchanged.

**Tech Stack:** Existing Three.js/Vite/React, SVG images, existing Python persistent media worker, MinIO, TEST console/provider Docker overlay deployments.

## Scope and authority

User approved the full model preview, requested random white angles and explicitly authorized integration. Manufacturer proportions remain white 21.9×8.8 mm, black 22.2×9.1 mm. Deployment and writes remain TEST-only. No new OCR/TTS, no full-book jobs, no production/RK/develop/main/submodule updates.

## Chunk 1: Minimum shared visual foundation

- [ ] Astra Max reviews this plan and decides any material integration tradeoff (max two plan rounds).
- [ ] Promote the approved model from `katrain/web/ui/preview/shell-stones/stoneModel.ts` to `katrain/web/ui/src/components/tutorials/stoneModel.ts`, with preview importing it. Extract only the studio setup needed by preview/export so sprite output retains approved lighting. Do not alter normal Galaxy/kiosk Board3D defaults.
- [ ] Add a reproducible local export entry/script: 32 uniformly spaced white grain rotations, one black sprite, 128 or 256 px transparent PNG, fixed seed and camera. Rotate model Y before render so specular highlights remain fixed to studio lighting. Generated file manifest records dimensions/angle count/model version and physical black/white ratio. Store originals in APP source assets; copy byte-identical assets into UI source assets through a small explicit script/check, no shared-package framework.
- [ ] Add a tiny deterministic `stoneVariant(seed,col,row)` selection helper mirrored/verified across the two repos. Use stable figure ID plus full-board coordinates, never array index, current replay cursor, Date.now or Math.random. Removing/re-adding at the same point may reuse that deterministic orientation; this is intentional visual stability, no new persistence or replay schema.

## Chunk 2: User journey — read/edit diagram and play 2D video

- [ ] UI `admin-console/ui/src/components/tutorials/SGFBoard.tsx`: replace known black/white circles with approved sprite images + restrained contact shadows, correct physical diameter ratio; keep annotations and last-move ring as independent upright SVG overlays. Preserve unknown-color, click targets, coordinates, source/known boundaries. Pass figure identity seed from workbench main/thumb/candidate boards. No local WebGL.
- [ ] APP recorder: optional tutorial sprite props through Board3D/StoneGroup/StoneMesh (or equally small isolated overlay); use sprites only in overhead recording, `MeshBasicMaterial` with `toneMapped=false` / correct sRGB and resource reuse. Map top-left coordinates once so white variants match the static board, stable across frames and backward seeks. Keep 360ms placement, captures, subtitles and quiet landing sounds unchanged.
- [ ] Only 2D generation in current workbench UI. Preserve old 3D media/history read-only, no new 3D jobs. Minimal enqueue guard rejects new video requests with `render_mode=3d` with a useful error; existing historical records remain readable. No DB schema migration.
- [ ] Focused checks: orientation variety/stability across reload/step changes, correct black/white ratio, labels and inverse rings do not rotate, unknown stones unchanged, no RK WebGL import; only new 2D jobs. Build both UIs and run affected existing board/media tests, no whole-suite expansion.

## Chunk 3: TEST integration and sample acceptance

- [ ] Independent Astra Max SPEC/visual check followed by code-quality review; fix until passed. Compare current static board and 2D recorder with approved model at same viewport and actual stone size; one side-by-side/overlay, not all-state reshoots.
- [ ] Commit narrow changes in both existing feature worktrees. Verify TEST provider/console environment markers, DB system identifier `7596941912817897507`, MinIO bucket `tutorial-assets` and TEST public media base before writes. Reuse existing deployment helper with fresh artifact dirs/version SHAs; await asset transfer before Docker builds. Preserve env/ports/networks/mounts. Restart only TEST provider and console.
- [ ] Read protected current figures 1030/1031. Keep board payload, narration, raw audio hashes and human board approvals intact; submit two `video/2d` tasks with current expected_updated_at. Do not recreate approvals or mark videos human-approved. No bulk generation.
- [ ] Verify two actual MP4s (play/seek, model appearance, diverse fixed orientations, 1030 replay and soft placement/audio; 1031 honest static mode if cues still pending). Confirm static main/thumb and video markers match, source frame/unknown bounds unchanged, task freshness/reviews valid. Astra Max checks actual sample video frames and code closure, bounded to changed material.
- [ ] Deliver TEST backend direct links, two latest 2D sample links and review summary; distinguish code complete/deployed/sample-generated/human-video-review-pending.

## Repos / files

- APP: `/Users/fan/.config/superpowers/worktrees/katrain-tutorial-module/tutorial-workbench-2026-10-14`.
- Console: `/Users/fan/.config/superpowers/worktrees/smartbox-software/tutorial-workbench-2026-10-14`.
- Main existing files: `katrain/web/ui/src/pages/TutorialMediaRecorder.tsx`, `src/components/Board3D/{index,StoneGroup,StoneMesh}.tsx`, `katrain/web/tutorials/media_tasks.py`, UI `admin-console/ui/src/components/tutorials/SGFBoard.tsx`, `src/admin/tutorials/workbench/TutorialWorkbench.tsx` and affected existing tests.
- Private deploy scripts/credentials remain outside repos under `~/.local/share/smartbox-admin/`; never print them.

## Acceptance boundary

No figure/replay/narration changes just to vary texture. Stable angle is presentation state derived from identity; only white grain orientation varies, highlights and labels stay fixed. Source artwork comes solely from approved original procedural model. Previous 3D assets retained, current creation uses 2D only. New sample videos remain pending human approval.
