# Tutorial Module Design

Date: 2026-03-14
Status: Draft for review

## Summary

Add a new Galaxy tutorial module to KaTrain Web, parallel to existing modules such as Play, Live, and Tsumego.

The module serves structured voice-guided Go lessons built from externally parsed book data, but the public product must not expose book titles, authors, translators, or near-verbatim source text. Public lessons are organized as:

`Tutorial -> Category -> Topic -> Example -> Step`

Phase 1 uses existing page screenshots as the visual layer. A later phase may replace screenshot-based steps with SGF-backed interactive board views without changing the public hierarchy.

## Goals

1. Ship a first-class Web tutorial module inside Galaxy, with both backend and frontend support.
2. Build a safe content pipeline from parsed `book.json` inputs to public lesson artifacts.
3. Generate narrated audio lessons offline using CosyVoice as the TTS subsystem.
4. Keep the online product read-only with respect to lesson generation: all public lesson content is prebuilt, reviewed, and published offline.
5. Preserve a migration path from screenshot steps to SGF-driven board visualization.

## Non-Goals

1. No desktop/Kivy tutorial UI in phase 1.
2. No online lesson authoring CMS in phase 1.
3. No real-time TTS generation in the public app.
4. No source-book attribution in the public UI or public APIs.
5. No fully automated publish path without human review.

## Product Requirements

### User-visible structure

The public module is structured as:

- `Tutorial`: the top-level Galaxy module entry.
- `Category`: broad learning stages such as `beginner`, `opening`, `middle-game`, `endgame`.
- `Topic`: a public knowledge unit, not a raw book chapter.
- `Example`: one teaching sequence under a topic.
- `Step`: the smallest playback unit, containing narration, image/board payload, and audio.

### Content policy

Public content must:

1. Avoid book names, author names, translator names, raw chapter headings, and source-specific provenance.
2. Rewrite source text into concise spoken instruction suitable for audio playback.
3. Avoid near-verbatim reproduction of source passages.
4. Remove OCR noise, redundant phrasing, special symbols, and page furniture.
5. Be auditable before publication.

### First release scope

Phase 1 includes:

1. Category browsing
2. Topic browsing within a category
3. Example playback page with step navigation
4. Screenshot-based visuals
5. Offline-generated audio
6. User progress tracking

## Source Input and Editorial Boundary

The initial content source is parsed book output such as:

- `output/book.json`
- `output/review.json`
- extracted page screenshots

Example source path used during design:

- `/Users/fan/Repositories/go-topic-collections/books/布局/曹薰铉布局技巧_上册_曹薰铉_1997/output/book.json`

That source shows a useful internal hierarchy:

- `chapters`
- `sections`
- `pages`
- `elements`

This hierarchy is sufficient for an offline builder to derive lesson fragments, but it must remain private. It is not the public product model.

## Recommended Architecture

Use a three-layer architecture:

### 1. Private source layer

Contains raw parsed materials and source metadata:

- `book.json`
- `review.json`
- page screenshots
- source file paths
- raw text fragments
- figure labels
- page references

This layer is never exposed to public APIs or the public UI.

### 2. Editorial build layer

Offline pipeline that transforms source content into public tutorial artifacts:

1. Ingest parsed source files.
2. Extract source fragments.
3. Map fragments into public lesson categories.
4. Merge similar source sections into public `topic` units.
5. Split each topic into one or more `example` sequences.
6. Split each example into short `step` units suitable for narration.
7. Rewrite narration into spoken teaching copy.
8. Call CosyVoice to generate step-level audio.
9. Write draft outputs for manual review.
10. Publish reviewed content into a public lesson package.

### 3. Public app layer

KaTrain Web reads published lesson packages and exposes:

- tutorial browsing APIs
- example detail APIs
- progress APIs
- Galaxy tutorial pages

This layer must not contain raw source metadata.

## Data Model

### Private editorial objects

These exist only in the offline review workflow.

#### `SourceFragment`

- `source_id`
- `source_path`
- `page`
- `image_ref`
- `raw_text`
- `figure_label`
- `bbox`

#### `DraftTopic`

- `topic_slug`
- `category`
- `working_title`
- `teaching_goal`
- `source_refs[]`

#### `DraftExample`

- `example_id`
- `topic_slug`
- `draft_title`
- `source_refs[]`
- `steps[]`

#### `DraftStep`

- `step_id`
- `narration_draft`
- `narration_final`
- `image_ref`
- `board_mode`
- `board_payload`
- `audio_ref`

`board_mode` is expected to be `image` in phase 1 and may later become `sgf`.

#### `ReviewRecord`

- `status`
- `reviewer`
- `reviewed_at`
- `notes`
- `rejection_reason`

Recommended minimum workflow:

- `draft`
- `approved`
- `published`

### Public lesson objects

These are safe to expose through the public app.

#### `Category`

- `id`
- `slug`
- `title`
- `summary`
- `order`
- `topic_count`
- `cover_asset`

#### `Topic`

- `id`
- `category_id`
- `slug`
- `title`
- `summary`
- `tags[]`
- `difficulty`
- `estimated_minutes`

#### `Example`

- `id`
- `topic_id`
- `title`
- `summary`
- `order`
- `total_duration_sec`
- `step_count`

#### `Step`

- `id`
- `example_id`
- `order`
- `narration`
- `image_asset`
- `audio_asset`
- `board_mode`
- `board_payload`

#### `UserProgress`

- `user_id`
- `topic_id`
- `example_id`
- `last_step_id`
- `completed`
- `last_played_at`

`UserProgress` is dynamic online data and is not part of the published content package.

## Published Package Format

Recommended published package layout:

```text
data/tutorials_published/
  manifest.json
  categories/
    opening.json
    middle-game.json
  topics/
    opening/
      balance-corner-and-influence.json
  examples/
    ex_opening_001.json
    ex_opening_002.json
  assets/
    images/
      ex_opening_001_step_01.png
    audio/
      ex_opening_001_step_01.mp3
```

Rules for published packages:

1. Do not include source identity fields such as book title, author, translator, or source path.
2. Do not include raw extracted source text.
3. Include only final rewritten narration.
4. Include only `published` content.
5. Keep `board_mode` explicit so the app can support both screenshot and SGF steps.

## Code Placement

### Offline builder

Recommended package:

```text
katrain/tutorial_builder/
  ingest/
  normalize/
  dedupe/
  rewrite/
  tts/
  review/
  publish/
```

Reasoning:

- The builder belongs with the product because the publish format and app behavior will evolve together.
- It should not live inside the online runtime package.
- It should not depend on the source-book repository for long-term maintainability.

### Online backend

Recommended placement:

```text
katrain/web/tutorials/
  loader.py
  service.py
  progress.py
katrain/web/api/v1/endpoints/tutorials.py
```

This follows the existing `api/v1` endpoint pattern already used by modules such as Tsumego, Kifu, and Live.

### Online frontend

Recommended placement:

```text
katrain/web/ui/src/galaxy/api/tutorials.ts
katrain/web/ui/src/galaxy/types/tutorials.ts
katrain/web/ui/src/galaxy/pages/tutorials/
katrain/web/ui/src/galaxy/components/tutorials/
```

Also update:

- `katrain/web/ui/src/GalaxyApp.tsx`
- `katrain/web/ui/src/galaxy/components/layout/GalaxySidebar.tsx`
- dashboard module cards if the tutorial module should appear there as well

## Backend API Shape

Recommended phase-1 endpoints:

- `GET /api/v1/tutorials/categories`
- `GET /api/v1/tutorials/categories/{slug}/topics`
- `GET /api/v1/tutorials/topics/{topic_id}`
- `GET /api/v1/tutorials/examples/{example_id}`
- `GET /api/v1/tutorials/examples/{example_id}/assets/{asset_id}` if asset indirection is needed
- `GET /api/v1/tutorials/progress`
- `POST /api/v1/tutorials/progress/{example_id}`

Notes:

1. Content endpoints should read from the published package index.
2. Progress endpoints may store per-user state in the existing database stack.
3. Public content payloads should stay stable even if the source pipeline changes.

## Frontend UX Shape

Recommended phase-1 page flow:

1. Tutorial landing page: category cards
2. Topic listing page: topics under the selected category
3. Topic detail page: topic summary plus ordered examples
4. Example playback page:
   - screenshot or board panel
   - narration text
   - audio playback
   - step navigation
   - completion/progress state

The example playback page is the core learning surface and should treat `Step` as the primary playback unit.

## TTS Integration

Use CosyVoice as a replaceable offline TTS subsystem.

Why this is acceptable:

- The official repository publicly documents service deployment under `runtime/python/fastapi` and `grpc`, plus text normalization and streaming support.
- Those capabilities are sufficient for batch or service-based lesson audio generation.

Why this is not enough by itself:

- CosyVoice does not solve topic deduplication.
- CosyVoice does not solve copyright-safe rewriting.
- CosyVoice does not solve editorial review or publish rules.

Therefore:

1. The builder owns rewrite and publishing policy.
2. CosyVoice only converts approved or draft narration text into audio assets.

Source:

- https://github.com/FunAudioLLM/CosyVoice

## Editorial Review Workflow

Phase 1 review remains file-based, not CMS-based.

Recommended directories:

```text
data/tutorial_drafts/
data/tutorials_published/
```

Workflow:

1. Builder generates draft JSON plus audio assets.
2. Reviewer reads draft files and listens to audio locally.
3. Reviewer checks copyright safety, spoken quality, and lesson clarity.
4. Approved items are published into the public package.

Required review checklist:

1. No source-book identity leakage
2. No near-verbatim reproduction
3. Spoken narration sounds natural
4. Step sequence teaches a coherent concept
5. Audio assets are present and playable

## Error Handling

### Offline builder

1. If rewrite fails for a step, keep the example in `draft` and block publish.
2. If TTS fails, keep the draft but block publication for that example.
3. If a screenshot is missing, mark the step as blocked rather than silently dropping it.
4. If similar source sections conflict, keep them as separate examples under one topic rather than over-merging.

### Publish

Publish should be atomic:

1. Build the next package version in a staging directory.
2. Validate the full package.
3. Swap the active manifest or directory pointer only after validation succeeds.

### Online app

1. Missing topic or example returns 404, not silent empty success.
2. Missing user progress falls back to empty progress state.
3. Unsupported `board_mode` should fail explicitly rather than render incorrectly.

## Testing Strategy

### Builder tests

1. `book.json -> source fragments` extraction behaves deterministically.
2. Topic dedupe rules produce stable IDs and grouping.
3. Published packages exclude forbidden fields.
4. Step payloads preserve image/audio/board consistency.
5. Publish validation rejects incomplete examples.

### Backend tests

1. Tutorial endpoints return the expected schema.
2. Not-found behavior is explicit.
3. Index refresh logic handles package updates safely.
4. Progress persistence behaves correctly for partial and completed examples.

### Frontend tests

1. Sidebar and route wiring expose the tutorial module.
2. Category -> topic -> example navigation works.
3. Example playback advances between steps correctly.
4. Audio and progress state stay in sync.
5. `board_mode=image` renders screenshots correctly.

## Acceptance Criteria

Phase 1 is acceptable when:

1. One category, one topic, and at least one multi-step example can be published end to end.
2. The lesson can be browsed inside Galaxy as a dedicated module.
3. The example page supports picture plus narrated audio playback.
4. The public app and public APIs do not expose book identity or raw source text.
5. The publish process requires explicit human approval.
6. The public `Step` model remains compatible with a future SGF-backed renderer.

## Key Decisions Captured

1. The tutorial module is a new Galaxy module, not an extension of Play, Live, or Tsumego.
2. Phase 1 is Web-only.
3. Content generation is offline, not online.
4. Manual review is required before publication.
5. Public lessons are topic-centric, not book-centric.
6. Screenshots are acceptable in phase 1; SGF is a later upgrade.
7. CosyVoice is a TTS dependency, not an editorial engine.

## Open Follow-up

These are implementation details, not blockers for the design:

1. Exact topic dedupe heuristics
2. Exact narration rewrite policy and prompt/template design
3. Whether tutorial progress should require authentication or support anonymous local progress
4. Whether assets are served directly from disk or indexed through an asset manifest
5. Whether the first release should show estimated lesson duration on topic and example cards
