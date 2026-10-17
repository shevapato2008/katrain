# Approved photo-shell integration plan

> **For agentic workers:** Use superpowers:subagent-driven-development for the bounded asset integration; the owner handles TEST delivery. Keep review and verification proportional to this visual replacement.

**Goal:** Use the user-approved original-photo clamshell material in tutorial static boards and overhead 2D videos, then update TEST and the two existing samples.

**Architecture:** Export 32 fixed-light white orientations directly from the approved `preview/photo-shell-stones` renderer. Keep the existing black PNG byte-identical. Mirror the resulting PNGs and provenance manifest into the console through the existing sync script; existing SVG/recorder consumers, deterministic seed mapping, labels, replay, audio, task/review/CAS contracts remain unchanged.

**Tech stack:** Existing Three.js preview/exporter, React SVG/recording consumers, Vite, TEST Docker services and existing media tasks.

## Approved source and scope

- User approved `http://127.0.0.1:9035/photo-model/site/` in default **original photograph crop** mode. Source JPEG is unchanged; 2339×2356 image, UV crop x700..1650/y450..1400. No AI-derived texture or procedural stripe texture may enter the exported white PNGs.
- Preserve source material values, closed geometry, 21.9×8.8 mm white dimensions and fixed studio. Do not brighten, alter grain or re-design the UI during integration. Black and its 22.2/21.9 diameter ratio remain unchanged.
- Store source/provenance notes with the preview. The manufacturer has not explicitly granted commercial redistribution; current authorization/scope remains TEST. Do not label the image openly licensed or claim a 3D scan.
- No production, RK3562, develop/main/submodule release, schema changes, OCR, TTS, bulk media, figure edits or automatic media approval.

## Task 1 — Export and integrate the approved material

- [ ] Capture approved `photo-0` 256px sprite bytes as a baseline in ignored output before changes.
- [ ] Extend only the approved preview's export hook to produce 32 white `sprite('photo', angle)` renders regardless of selected preview mode. The AI comparison remains explicitly separate.
- [ ] Point `katrain/web/ui/scripts/export-tutorial-stones.mjs` at that preview; retain existing black PNG and add exact original-photo/crop/source hashes to the manifest.
- [ ] Run `npm run export:tutorial-stones`; prove white-00 equals the captured approved sprite, all white variants are distinct, black unchanged, and original source JPEG unchanged. Mirror to the console with the existing `sync-tutorial-stones.mjs`.
- [ ] Run focused sprite-selection tests in both UIs, `npm run build:tutorial-media`, and console `npm run build`. Do not add a new test layer for this asset change. Check one representative actual static board and recorder frame at real sizes.
- [ ] Astra Max first checks specification/visual compliance, then code/provenance; resolve concrete findings before TEST deployment. Commit only owned files, preserving unrelated untracked console work.

## Task 2 — TEST deployment and two samples

- [ ] Recheck TEST environment markers, database identifier 7596941912817897507, bucket tutorial-assets and TEST media base before mutation. Package only the recording bundle and console dist atop current TEST images. Finish and verify transfer before remote builds/deployment; preserve env/ports/mounts/networks and figure fingerprints.
- [ ] Deploy only `katrain-admin` and `smartbox-admin-admin-console-1`; verify health and exact published asset versions.
- [ ] Regenerate only figures 1030/1031 as 2D via existing tasks with current expected_updated_at, approved board versions, and existing audio. Preserve figures/narration/static approvals/historical 3D. New videos stay human-review-pending. Figure 1031 remains honest static if step cues are still pending.
- [ ] Inspect one actual encoded frame and one real browser play/seek. Bound any gallery/network auxiliary issue to one retry. Astra Max checks the actual sample material as a narrow closure; no repeated full code review.
- [ ] Update full-width sample gallery, final report and TEST links; clearly report scope and pending human video review.

## Workspaces and existing delivery helpers

- APP: `/Users/fan/.config/superpowers/worktrees/katrain-tutorial-module/tutorial-workbench-2026-10-14`.
- Console: `/Users/fan/.config/superpowers/worktrees/smartbox-software/tutorial-workbench-2026-10-14`.
- Private deploy/task helpers: `~/.local/share/smartbox-admin/tutorial-shell-grain-20261017/`; use fresh artifact/output directories and preserve secrets outside the repositories.
