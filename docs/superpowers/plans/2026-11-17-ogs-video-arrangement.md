# OGS Video Arrangement Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Curate and configure video-first playlists for all 248 OGS lessons using completed TEST media, with an auditable source table and a usable TEST preview.

**Architecture:** Reuse the accepted OGS lesson/player contract and its stable IDs. Build one pinned, compact current-media index; chapter authors independently select and sequence clips; a deterministic assembler validates their decisions and produces the review document and TEST manifest. A small trusted TEST configuration permits playback of existing TEST assets and TEST exercises in an isolated preview, preserving the current PROD defaults and all Admin WIP.

**Tech Stack:** Python standard-library content tooling, read-only TEST SQLAlchemy capture through existing SSH, JSON/CSV/HTML, existing React/TypeScript/Vitest player.

---

## Chunk 1: Data, editorial decisions, and TEST preview

### Task 1: Compact context and assembly foundation

**Files**
- Create: `scripts/tutorials/ogs_arrangement.py` and `tests/test_ogs_arrangement.py` in this isolated worktree.
- Read: main-worktree `superpowers/tracks/tutorial-database/ogs-video-outline-2026-11-12.json` and the completed batch `resume-full-20261117/final-report.json`.
- Output: main-worktree `data/tutorial_media_batches/ogs-book-sources-20261113/arrangement-20261117/`.

- [x] Persist a single read-only capture before deriving indexes, to make local ETL failures recoverable without another remote capture. Pin TEST DB identity, board/source/narration/audio fingerprints and both existing profile asset keys against the completed batch. Export only whitelisted fields; never export recognition history, WordBoundary arrays, credentials, or service URL queries.
- [x] Normalize outline `source_units` as a mapping. Build `video-index.json` from current narration, source/PDF references and durations. Keep context-reference flags and PDF order.
- [x] Use the full local OGS Chinese bundle to build `lesson-goals.json`; the existing helper owns this file. Include concise actual instructions and feedback, not only repeated titles.
- [x] Implement meaningful assembly tests: exact 248-ID coverage, nonempty/duplicate-free lists, excluded or stale clip rejection, missing profile rejection, duration from actual data, existing14 baseline preservation. Run `python -m pytest tests/test_ogs_arrangement.py -q`.
- [x] Produce chapter context/candidate files from approved source units plus narration matching, with deduplicated clip text. Ranking is a retrieval aid; chapter authors make the actual editorial choices.

### Task 2: Parallel chapter curation

**Files:** `arrangement-20261117/chapters/chapter-01.json` through `chapter-07.json` (chapter6 may be authored in two disjoint parts).

- [x] Assign chapters1–3, chapter4, chapter5, two halves of chapter6, and chapter7 to separate authors, with exclusive output files and no remote writes.
- [x] For each lesson select an ordered list from current media; record `role/focus/rationale/source_unit`, `intro`, `practice_bridge`, and honest coverage notes. Do not force a clip quota or indiscriminately reuse an entire source range.
- [x] Keep the current14 playlists and order, subject only to explicit concrete source/content concerns. For same-title lessons use their actual OGS instructions to select the relevant concept/variation.
- [x] Search the current pool for the three known supplementation cases. Preserve an explicit boundary between video principle coverage and details taught by the original interactive exercise; no invented demonstration or new AV generation.
- [x] Run the assembler, resolve data errors and disputed ordering, and spot-check representative content transitions. Review the merged content decisions proportionately; do not perform frame-by-frame/model AV review.

### Task 3: Minimal trusted TEST player configuration

**Files:** `katrain/web/ui/src/types/ogsVideo.ts`, `types/ogsVideo.test.ts`, `api/tutorialApi.ts`, and existing affected player tests only as required.

- [x] Add focused failing tests for configured TEST manifest/media paths while preserving existing PROD acceptance/rejection cases.
- [x] Add trusted build-time TEST manifest/media/API-base configuration. The fetched manifest and URL parameters cannot choose arbitrary origins. Accept only the configured TEST public asset prefix; reject credentials, query strings, traversal, unsupported profiles, unknown clip references and malformed data. TEST poster may be absent.
- [x] Preserve video-first navigation and practice access. Support the direct TEST tutorial API instead of the box board-mode proxy in the isolated TEST preview. Existing PROD defaults remain unchanged.
- [x] Run the existing affected Vitest tests, using the already-installed toolchain where available. Build only the isolated preview; do not replace current Admin files or publish to PROD/RK.

### Task 4: Review artifacts and real TEST-data handoff

**Files**
- Create: main-worktree `superpowers/tracks/tutorial-database/ogs-video-arrangement-2026-11-17.{json,csv,html}`.
- Create: versioned `arrangement-20261117/test-manifest.json` and preview receipt.
- Modify: existing outline progress only to reflect actual new arrangement, keeping material readiness separate from published/runtime association.

- [x] Assemble a 248-row source table: lesson/goal, ordered clip IDs and purposes, book/PDF/figure/Admin links, duration, coverage note and actual TEST-association status. Reuse the existing document visual system and supply playable 4K/kiosk previews.
- [x] Generate a schema-compatible TEST manifest using immutable existing MP4 URLs; no MP4 regeneration, bucket ACL changes or box download. Publish only new, versioned TEST configuration/artifact objects if needed, with a dry-run and TEST identity guard.
- [x] Serve the isolated preview against real TEST course/step endpoints. Verify a beginning rule lesson, a repeated-title later lesson, one excluded-source-adjacent lesson, video→exercise and profile playback. Use one representative 1024×600 actual browser preview; no repeated full-state screenshot sweep.
- [x] Perform focused spec and implementation review of the assembled data/configuration, resolve actual issues, and record validation. Save a final receipt and report the document/preview links and any honest remaining content limitations. No unrelated merge, release, or production deployment.


## Execution outcome

- 2026-11-17: 248/248 lessons curated across seven chapters; 316 unique clips / 721 ordered uses. Fifteen excluded sources were not used; fourteen accepted baseline playlists retained.
- New review artifacts are in the main worktree's `superpowers/tracks/tutorial-database/ogs-video-arrangement-2026-11-17.{html,json,csv}`; existing outline progress updated separately from material readiness and PROD associations.
- TEST deployment discovery corrected: the running Admin image has authenticated OGS reads but no anonymous public OGS reader. This delivery uses a fingerprinted real TEST book80 read-only export (248 lessons,3551 steps), not fixture data or a PROD fallback. No server deployment was performed.
- The existing product shell correctly requires box authentication. An isolated preview-only entry mounts the unchanged four OGS pages with their real providers; production AppRouter/Guard remain untouched.
- Loopback preview runs on port18957; review HTML streams only manifest-allowlisted TEST assets to avoid browser cross-origin restrictions. Videos are not copied or regenerated. Browser verified kiosk1024x600 and4K3840x2160 playback, rules-intro video→exercise→correct point, and later same-title lesson7.4.
- Assembly tests23 passed; affected frontend tests56 passed, strict configuration31 passed; real TS parser accepted316clips/248playlists. Independent content review sampled9lessons/104steps/23narrations across7chapters and approved with explicit content limitations. This was not an AV review or comprehensive review of all248lessons.
- New PROD/RK deployment and whole-library AV generation remain outside this arrangement delivery. See the preview receipt for environment and validation details.
