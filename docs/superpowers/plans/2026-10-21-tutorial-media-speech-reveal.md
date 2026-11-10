# Tutorial Speech-Triggered Teaching Objects Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development. Follow the checkboxes in order; keep the old batch paused and preserve its evidence.

**Goal:** Regenerate the frozen batch figures that already have valid audio into Galaxy4K and kiosk7 videos, revealing numbered/marked stones and annotations only after their spoken references.

**Architecture:** Add a recording-only presentation plan, separate from authoritative board/replay data. Derive teaching objects from saved labels/letters/shapes, and permit explicitly sourced supplemental arrows. Bind objects to exact narration character spans, compute event times from the ends of the real TTS boundaries, and build immutable recording frames. Keep real rule replay/captures distinct and preserve existing versioned media-task safety.

**Tech Stack:** Existing Python media worker, Pydantic/FastAPI task contract, React/TypeScript Three.js recorder, ffmpeg and current standalone recording build. No new database tables, rendering service, model provider or app navigation.

## Accepted requirements and bounded scope

User explicitly approved the visibility rules and asked to regenerate videos for figures whose audio has already completed. The new source manifest is in the main workspace `data/tutorial_media_batches/core23-first50-20261021/regeneration-scope.json`: 6 books /114 PDF pages /229 figures /458 profile videos;108 previously approved static pages plus6 partial pages. Exclude the five figures with no completed audio, all later pages and all other books not represented in the manifest. Existing audio may be reused when it fully supports the required teaching-object references; if a manifest figure needs corrected narration, regenerate audio only for that figure. Read the new three tutorial skills as acceptance criteria.

- Opening: board grid/starpoints/coordinates and static stones with no teaching annotations only.
- Every numbered stone, symbol/letter-marked stone and independent symbol/letter/arrow remains hidden until its explicit spoken reference finishes. Empty-point annotations do not create stones or stone sounds. A revealed stone is not dropped twice when another annotation on it is mentioned later.
- Numbered moves preserve source order, arbitrary start/white-first allowed. Non-numbered annotations are not subject to alternating colors or numeric ordering. Repeated references do not replay placement. Ambiguous/missing references fail with actionable reasons, never static fallback.
- Presentation does not edit board_payload, source_region, replay completeness or human reviews. Actual local rule replay still handles evidenced captures/pass and never needs whole-game history.
- Both output profiles consume the same immutable audio, exact text and event plan. Keep stone textures/materials, existing layouts, quiet contact sounds and gentle placement. No status badge/range frame/gray mask.
- Multi-mark points need independent marker visibility: revealing one annotation may expose its stone, but must not prematurely expose other annotations at the same point. Numeric stone order must not be bypassed via an earlier symbol reference; revise a conflicting script/plan.

## Chunk 1: Recording presentation foundation

### Task 1 — Backend object plan, real audio timing, immutable task snapshots

Files: create `katrain/web/tutorials/media_presentation.py`; modify `media_timing.py`, `media_tasks.py`, `media_render.py`, `katrain/web/admin/routers/tutorial_media.py`; tests in `tests/web_ui/test_tutorial_media_presentation.py` and focused existing media tests.

- [x] Write failing behavioral tests first. A clean static saved 1–5 diagram with needs_calibration replay must produce background-only opening, then correct cumulative steps at spoken reference END times. Preserve original payload byte-equivalently.
- [x] Cover a symbol-marked stone and independent letter/arrow; annotation-only event never adds a stone/click. Include a same-point multi-mark case, repeated references, out-of-order/missing number anchors, ambiguous/unmapped objects, stale hashes, and the no-annotation static case. Preserve existing real replay capture behavior.
- [x] Implement a small optional `presentation_plan` request/snapshot value. Schema: version1, `bindings` of exact narration span `[start,end)` to one or more discovered object IDs; optional source-backed arrows with stable ID/from/to/source pointer+image SHA. Derive all saved label/letter/shape objects from current board, not caller-supplied replacement stones. Validate coordinates, marker identity, narration span bounds/nonempty text, exact coverage, and no unknown object IDs. Supplemental arrows require source identity matching the figure source; do not invent markers from metaphorical words such as “愚形三角”.
- [x] Provide conservative automatic matching for unambiguous numeric/color references and unique saved annotations. Ambiguous bindings need an explicit source-grounded plan rather than positional guessing. End times come solely from aligned actual WordBoundary records, not client timestamps, uniform interpolation or video duration.
- [x] Return explicit presentation timing mode/status separate from board replay validity. A complete presentation cue plan must not assert complete real replay. Preserve compatibility for existing valid replay/static assets; do not allow newly generated annotated diagrams to succeed through pending/static fallback.
- [x] Snapshot/hash presentation inputs and immutable output frames/events with narration/audio dependencies. Use existing task CAS/queue/publication protection, preserve the sibling output profile, retain audio reuse and reject video publication when required events are incomplete. Video generation must require a valid already-completed audio artifact; disable implicit TTS fallback for video tasks so both profiles cannot quietly synthesize different audio. Existing human video approval fields must not be written by machine review.
- [x] Run focused pytest with root interpreter: `/Users/fan/Repositories/katrain-admin-console/.venv/bin/python -m pytest tests/web_ui/test_tutorial_media_presentation.py tests/web_ui/test_tutorial_media.py tests/web_ui/test_tutorial_media_render.py -q`. Inspect failures against intended updated contract, not merely update assertions to pass.
- [x] Independent spec review then code-quality review, fix concrete blockers before next task. Commit only owned changes in this isolated branch.

### Task 2 — Recorder consumes presentation frames and draws delayed arrows

Files: `katrain/web/ui/src/pages/tutorialMediaTimeline.ts`, `TutorialMediaRecorder.tsx`; focused timeline/recorder tests. Use Task1's settled contract; do not change app routes or source board editor.

- [x] Add failing tests for seeking before/after each exact speech-end cue, background-only opening, delayed symbols/letters, no duplicate placement on repeat references, independent annotations causing no drop, and retained real replay capture behavior.
- [x] Consume explicit recording presentation mode and frame/event data; never call complete real replay a prerequisite for numbered/symbol reveal. Reuse deterministic existing frame selection and soft landing where possible. State keys must include annotation-only changes, not cache stale overlays.
- [x] Render supplemental arrows using current projection overlay so board coordinates/layout match both output profiles. Keep unknown regions/source state honest; no new diagnostic label in final videos.
- [x] Reuse source stone assets, current profiles and renderer. Run `npm test -- src/pages/tutorialMediaTimeline.test.ts src/pages/TutorialMediaRecorder.test.tsx` and `npm run build:tutorial-media` in `katrain/web/ui`.
- [x] Spec review then code-quality review and a representative original-size local render in both profiles. Check each teaching event's before/after frames against the source. User already approved these behavior/layout rules; avoid redesigning UI or opening an unrelated visual mockup workflow.
- [x] Commit owned changes only.

## Chunk 2: Corrected regeneration, review and test-backend association

### Task 3 — Pilot, safe TEST application, and six book workers

Scope: only TEST `home-ubuntu/katrain-admin`, env=test, DB identity7596941912817897507, s3 tutorial-assets. Read server-deploy skill before applying code. No production service update, develop merge or smartbox submodule change is requested.

- [x] Final independent Astra Max implementation review against the new skill/user rules, including conditional audio reuse and annotation visibility. Fix blockers before publishing regenerated videos.
- [x] Apply only the reviewed test media backend/recording bundle using existing deployment mechanics; layer on the exact running TEST image (baseline smartbox-admin-go:develop-course-e36c9f7e12e9 with unrelated overlays; current reviewed TEST overlay6d8533d0), retaining all other code/configuration rather than replacing it from an older checkout; check TEST identity and representative health. Preserve other services/changes. Publish relevant commit/version and do not confuse branch deployment with merging develop.
- [x] Keep old PAUSE/controllers and old media proofs untouched. Build a separate `regeneration-v2` runner/evidence directory and a scoped helper for the frozen229 figure manifest. GET/PUT narration/POST audio only where needed; POST video two explicit profiles with current CAS. Scope each page review to its manifest figures; partial pages remain explicitly partial, never pretend the ungenerated figures are complete.
- [x] Prepare source-grounded presentation plans from original images/payload and saved text/audio. Reuse audio when all references exist; otherwise minimally rewrite teaching text and regenerate audio before either video. Four known structural numbering cases (joseki22067/41889/22077/22078) require original-note resolution by independent Astra; uncertain pages are skipped per user policy, not guessed or marked complete.
- [x] Pilot the user's example shape PDF10/figure6931 (1–5), then one symbol/letter case; verify both actual profiles, sound, cue binding and every event frame. Fresh independent Astra Max must approve actual content/visual sync; do not use the old static approval as acceptance.
- [x] Then dispatch six book agents (one book each) using the manifest, sequential pages. Every page's selected figures and both videos must pass a fresh independent Astra Max review before next page. No old controller may be SIGCONT'd; no expansion into new-audio figures.
- [ ] Main updates `superpowers/tracks/tutorial-database/go-curriculum.html` and the campaign report; show new-rule regenerated counts separately from prior static approvals. Report each book every10 complete target pages and scope completion; label partial pages and skipped unresolved cases.
- [ ] Finish only when all frozen eligible existing-audio figures are regenerated/approved or explicitly source-uncertain and skipped. Preserve audio, prior rejects, source/cue/file hashes, and honest audio/device review limitations.

## Baseline and validation budget

The real failed batch is the behavior regression: existing renderer returns full static board for needs_calibration although source1–5 is reliable, and old acceptance explicitly accepted that. Targeted baseline media replay/timing tests run in the isolated worktree before implementation. Validate only changed timing, annotations, rendering integration, versioned dependency publication and representative actual dual-profile output; do not expand into unrelated application regression or concurrency architecture.

Independent plan review: GPT-6-Astra / max APPROVE. Per-page media reviewers run as fresh Codex CLI sessions, so six native book agents plus root fit the seven available native slots. Targeted baseline replay/timing tests:2 passed.
# Actual-page correction: source margin callouts (2026-10-21)

Fresh page review rejected intro-up PDF11: its16 route-name arrows are teaching objects even outside the grid. Add only the missing recording contract: source-bound edge callouts (grid-edge anchor, top/right side, text, source pointer/image hash), delayed by explicit spoken-end bindings, without altering saved board data. Render vertical top captions and horizontal right captions in reserved margins in both native profiles. Keep existing presentations byte-stable when no callouts are supplied, so previously reviewed unrelated pages remain valid. Focused backend/frame and recorder checks plus original-size visual evidence are sufficient; fresh independent Astra reviews the change, and the actual page still needs its ordinary full review. Revised narration covers4 explicit route groups of4 objects, then new audio precedes both videos. Preserve the rejected revision and all existing receipts. Deploy TEST only after active tasks drain; resume other books from their exact own task chains.

The next actual source case, opening PDF18, also requires9 in-board regional words (four隅, four边, 中央). Extend the same source-bound callout contract with `side: board`, text only, no margin expansion or arrows. Existing audio already has the3 correct group anchors, so reuse it. Preserve byte-stable prior edge-callout/no-callout proofs; native source comparison and independent Astra gate remain required. Other five books continue while this book-specific capability is repaired.

## Actual-page corrections: first references, captions and render budget

Independent Astra accepted literal descriptive numbered references while preserving qualifiers across commas/colons; full-sentence timing remains exact. Caption grouping now preserves complete punctuation sentences/semicolon clauses, fixing actual dropped negative conditions without changing narration or audio. Native4K/kiosk fixtures pass independent visual review; only rejected outputs are redone and whole pages independently reviewed again.

A valid65.808s/23stone4K page exhausted600s (largest completed7stonecomparison257.4s). Astra recommended and reviewed a shared1800s4K/600sotherprofile budget, parentwatchdog+20s, with existing peroperation limits/processgroup cleanup, quality/FPS/frames unchanged. Targeted worker/render62passed2skipped; independent10focusedpassed. TEST3d6b7d4c overlay437filehashes/identity/health/config preserved; actualfailed15471rerun still required before pageacceptance.

## Actual-page correction: source-backed forbidden ko hypothesis

intro-down PDF11/4826 fresh review rejected missing white pre-state/capture. Independent fresh Astra content-design consultation viewed PDF10+11 and chose A (recovery/intro-down-p011-content-design/astra-design-judgment.json): originalpage10white1(4,16) must first be revealed after narration, then only after prior explicit prohibition/hypothesis declaration the sourcepage11black1(3,16) appears/removeswhite1. Page11background3B5W stays; no page10trianglesimported. The teaching example is an illegal immediate ko recapture, not legal actual replay. Source evidence sufficient; skip is not justified.

Implement the smallest typed recording-only forbidden-ko hypothesis contract, with both current and referenced figure/page source identities verified server-side in the same book; referenced stone/label and exact one-stone capture/result must match authoritative saved boards. Keep saved board/replay/manual approvals untouched. Separate initial-object reveal from hypothetical capture; preserve marked objects hiddenuntilspoken, silent initialreveal/no phantom move, explicit audio/text prohibition BEFORE event, and unchanged background. Only this source-backed scenario gets hypothetical semantics; do not relax normal replay rules/initialownership/conditional-reference guards. Snapshot/hash bothsources; taskpublication invalidates ifeither changes. Existing plans/proofs remainbyteidentical withoutthenewoptionalplanfield.

Use existing presentationframes/recorderbothprofiles; minimally support new explicit hypotheticalmode/actionkind rather than claiming legalreplay complete. Fresh realTTS for newindependentlecture, then bothvideos fromsameaudio. Focused source/identity/immutability/timing/capturetests, nativebefore/aftervisualfixtures, independentAstraSPECQUALITYVISUAL gate; TESTonlyoverlay afteractivejobsdrain. Then actualpagefreshwholemediaAstra review before nextintro-downpage. Otherfivebookscontinue duringimplementation. No genericillegalmoveengine, UIredesign, productiondeploy or unrelatedconcurrencywork.


Forbidden-ko implementation6d8533d0b6403a29b18fb3125acd22b2f62c8af1 passed independent Astra SPEC, QUALITY and native VISUAL review. Backend source/review pins validated; public snapshot/proof carries only `board_review_sha256`, never administrator review details. Focused191backendtests and27independentreviewchecks pass. TEST438overlayfilehashes verified, environment/ports/mounts preserved, scopedsourceGETs and admin18012 healthy. Actualp011 freshTTS completed with new3563ms initialwhite and17287ms forbiddenrecapture anchors; two realMP4 and ordinary freshwholepageAstra still pending. Oldrejectedmedia preserved. Allsixbookworkers resumed exact own chains; no production/develop integration.


## User amendment: token cost pause and proportional media review

User explicitly paused active reviews on2026-10-21 and approved automation-first per-page checks, representative/complex Astra reviews and ordinary-page sampling. This replaces the earlier full-page-every-page model requirement; existing genuine approvals remain valid, unreviewed pages are not retroactively approved. Both voice/video skills updated and structurally validated with focused checks; no new model review launched to review this documentation. Allsixbookcontrollers/CLIreviews and rootmonitor stopped, already-submitted non-model render tasks retained. Current fresh actual approvals25pages43fig86videos. Batchpaused, notcomplete. Existingrunner stillimplements oldperpagegate; onlydocumentationchanged inthisupdate, so alignrunner/statebeforeanyexplicituserresume. Do not resume automatically.


## Latest user decision: cancel parallel campaign, separate generation and review
当前并行批次已由用户取消。已有成片、回执与历史审核结论保留；不恢复旧控制器。现阶段生成与审核分离：生成 skill 只生成音视频并交付用户人工检查，机器审核／抽样仅在以后单独明确派发时启用。
Allsixnativebookagentscompleted/noactivecontroller orcampaignreview; rootmonitorstopped. Video/voice SKILL.md generation-only, noqualityaudit/framesampling/Astra gate; tutorial-media-review is a separate explicitlyrequested opt-in skill, notautomaticallyenabled. Existingfullreviewruntimearchived/retired; noresumeworkornewgenerationrequested. Historical25pages43fig86outputs remain genuine approvals; noadditionalapprovalassigned. CANCELLED.json+PAUSEretained.
