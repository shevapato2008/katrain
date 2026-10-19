# OGS interactive preview implementation plan

> Scope approved in this session on 2026-10-19. Frontend preview only; user reviews the running result before any new backend or full course import. Apply writing-plans and subagent-driven-development proportionately to this isolated slice.

**Goal:** Review four real OGS exercises inside the existing TEST tutorial admin, with original screenshots/text, playable boards, and empty narration/media.

**Architecture:** Existing authenticated AdminApp and SGFBoard, copper/graphite theme and Kaiti. A TEST-build-only `?preview=ogs` entry lazy-loads isolated local fixture data. Source-derived examples: capture_stone/0, bl4-opening-4/0, count-liberties/0, ending-the-game/1. Chinese, English and Japanese preview variants share the same board and answers. This preview is separate from the future 32-language full import.

**Workspace:** `/Users/fan/.config/superpowers/worktrees/smartbox-software/ogs-learning-preview-2026-10-19`, from console `7518b4b2`; app/backend remain unchanged.

## Task 1 — source fixtures and reference

- [x] Capture source screenshots and actual config/text in 3 languages for 4 examples; freeze upstream revision and locale version.
- [x] Add isolated `admin-console/ui/src/admin/tutorials/ogs-preview/fixtures.ts`, `fixtures.json`, `assets/` and source/license notes.
- [x] Contract: each fixture has `id`, `kind` (`move`, `choice`, `remove`), `sourceUrl`, `courseCode`, `step`, `totalSteps`, `size`, `initialPlayer`, `stones` (zero-based top-left B/W points), `letters`, `shapes`, optional `viewport`, `correctPoints`, optional `choices`/`correctChoice`, optional `removeTargets`, and `locales` keyed `zh-cn`/`en`/`ja` (`title`, `instruction`). Image URLs are exported by fixtures.ts.

## Task 2 — interactive frontend

- [x] Reuse AdminApp shell + SGFBoard, Kaiti, navigation and existing stone sprites. Add only the TEST-build preview entry and a return-to-library link; preserve existing login and API behavior.
- [x] Build source screenshot zoom/full view, extracted reference text, 4-example navigation, language selector, answer controls, success/failure, retry, local progress, collapsible side panes; narration/audio/video empty.
- [x] Capture and ABC placement run existing tutorial replay rules to show real captures and reject occupied/suicide moves. This is ephemeral answer simulation, not verified database replay.
- [x] Count-liberties accepts source options 3/4/6 with 3 correct. Removal selects groups and succeeds only at the source target set; wrong removal is reported. Source range must not shift coordinates.
- [x] Keyboard access through native choice controls and coordinate entry for board operations. Clearly label preview/local progress; no database writes, review approval or media generation.
- [x] Correct reused board star points for 9/13 if necessary, with one focused check.

## Task 3 — review and delivery

- [x] Focused behavior checks: real capture, white first ABC, incorrect/correct choice, exact dead-group selection, retry/navigation/language state, existing route and TEST-build gate.
- [x] Targeted spec/code review. Build once with preview flag and once normally; ensure normal build cannot expose fixture route.
- [x] Representative 1920×1080 reference/implementation/side-by-side/overlay comparison; inspect actual preview and one compact viewport. Record functional and visual limits.
- [x] Publish only the console frontend preview to verified TEST using reversible asset packaging, preserving backend build, environment and sessions. Do not merge/release to production.
- [x] Deliver existing TEST URL, direct example links and short review instructions. Remove fixtures/gate and replace them with real data only in the later approved integration slice.

## Delivery status

Frontend preview published to existing TEST admin, source commit `99bb6e064795f86bf49c6429095b20079445893b`. 24 focused tests, typecheck/build, normal-build fixture exclusion, real-browser4-exercise checks and16deployed asset hashes verified. Astra Max APPROVE after final navigation cleanup. Backend container/image/environment/ports unchanged. No database import or new backend. User frontend acceptance pending.

See [visual review and examples](ogs-preview-2026-10-19/visual-review.md). Temporary asset overlay survives restart but a container recreation restores its original image; rollback index is retained onTEST server.
