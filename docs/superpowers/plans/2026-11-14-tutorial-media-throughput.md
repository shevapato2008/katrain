# Tutorial pronunciation and parallel generation implementation plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development. Keep this change proportional; no media review or Astra jobs.

**Goal:** Correct numbered-stone 一 pronunciation, deploy a safe parallel TEST generator, then resume ten exclusively owned book lanes with periodic progress reports.

**Architecture:** Keep the versioned tutorial API and current source/approval guards. Add scoped pronunciation rules and a configurable worker pool with exclusive database leadership, atomic task claims, and same-figure serialization. Existing production services and unconfirmed diagrams are outside scope.

**Tech Stack:** Python, PostgreSQL/SQLAlchemy, Chromium, FFmpeg/libx264, Docker, existing TEST Admin API.

---

## Shared preparation

- [x] Preserve the batch PAUSE until pronunciation and concurrency changes are ready; let book owners prepare sources and reconcile accepted tasks read-only.
- [x] Assign ten workers: intro-up; intro-down; shape; life-1; opening; life-2; sakata-1; sakata-2; joseki then endgame; ko then simple-judgement. Retire conflicting old cross-book supervisors.
- [x] Reconcile exact current approved/clear IDs and interrupted tasks into `data/tutorial_media_batches/ogs-book-sources-20261113/resume-20261114/`. Do not extend static approval.

## Pronunciation

**Files:** `katrain/web/tutorials/go_pronunciations.json`, `media_pronunciation.py`, `tests/web_ui/test_tutorial_pronunciation.py`, voice/video skill pronunciation guidance.

- [x] Add precise complete-identifier rules for 黑一/白一/黑1/白1 using the existing TTS-only homophone/remapping mechanism; retain original narration, subtitles and real WordBoundary mapping.
- [x] Keep longer numbers and unrelated quantity phrases outside those rules; preserve unaffected pronunciation identities.
- [x] Run focused pronunciation tests, including the existing 提子 correction and partial-number exclusions. Identify exactly which current assets require regeneration.

## TEST worker concurrency

**Files:** `katrain/web/tutorials/media_tasks.py`, `media_render.py`, focused concurrency tests, TEST runtime configuration.

- [x] Implement configurable pool size (default 1; TEST target 10), bounded queue (TEST 40) and encoder threads (default/TEST 4).
- [x] Preserve single pool leadership across processes, atomic claims, same-figure publication serialization and correct interrupted-task recovery. Verify shutdown handles every lane.
- [x] Run focused concurrency and existing affected media tests. Obtain one focused independent code review before deployment; fix material findings.
- [ ] Capture actual TEST container configuration privately and deploy from its exact image with only intended source/config deltas. Preserve mounts, networks, secrets and unrelated settings. Do not restart production, DB or GPU services.
- [ ] Verify effective pool/queue/thread settings, representative real concurrent tasks and service health without a media audit.

## Resume and reporting

- [ ] Deploy pronunciation together with the worker change; confirm current rule identities before releasing PAUSE.
- [ ] Start one ordinary persistent controller per lane. Reuse only current unaffected assets; regenerate affected audio first, then both native video profiles using its real timestamps.
- [ ] Reconcile results before retrying uncertain writes. Keep source ambiguities and unconfirmed diagrams blocked; do not fill review fields.
- [ ] Update main session and the OGS HTML/JSON/CSV at every ten whole-page milestone, book clear-scope completion or blocker, plus a thirty-minute heartbeat. Clearly label any decrease caused by new pronunciation validity rules.
- [ ] Keep a single low-cost child-to-parent notification relay; no model polling or automated media review.

No commit, push or production rollout is included in this request.
