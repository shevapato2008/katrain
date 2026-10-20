# Test tutorial catalog import Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Import the 78 catalog sources into the verified test tutorial library, preserve existing authoring results, and browse their diagrams, original pages and text through the existing unified admin.

**Architecture:** A separate importer resolves only catalog paths, inventories real parsed content and matches existing identity conservatively. Three additive provenance tables link source books/pages/figures to existing tutorial IDs without changing old records. The existing MinIO stores immutable source PNG objects; a small authenticated page reader extends the deployed SmartBox admin rather than creating a second frontend.

**Tech Stack:** Python3.11, SQLAlchemy2/PostgreSQL15, boto3/MinIO, FastAPI, existing React19 admin UI, pytest/Vitest and one real browser acceptance.

## Frozen scope and read-only evidence

- Application worktree: `/Users/fan/.config/superpowers/worktrees/katrain-tutorial-module/catalog-import-2026-10-13`, base published develop `2aa81b37d` (user application checkout preserved).
- UI worktree: `/Users/fan/.config/superpowers/worktrees/smartbox-software/tutorial-source-pages-2026-10-13`, base currently deployed console `419d2c7c`. Only tutorial UI additions are packaged for test.
- Sources: `/Users/fan/Repositories/go-topic-collections/curriculum/catalog.json`; original source repo remains read-only. 78 unique canonical book JSONs, 41,605 physical figures, 20,828 PNGs (2,221,183,307 bytes). 2,471 figures are in chapter introductions; 483 nested nie-life references are metadata aliases, not new figures.
- Test: SSH `home-ubuntu`, unified admin127.0.0.1:8012/env=test, Go provider127.0.0.1:18010/env=test, DB `katrain_db` on Docker172.19.0.4 with PostgreSQL system_identifier `7596941912817897507`, MinIO172.19.0.2 `http://minio:9000` bucket`tutorial-assets`, public media`https://go.sailorvoyage.top/media`.
- Baseline: 9 books, 27 chapters, 637 sections, 3,935 figures/boards; 669 verified, 1,902 narration/audio,580 videos,958 history rows,1,759 training samples. Exact full-row fingerprints will be retained before writes.
- Explicit authorization is TEST ONLY. No production SSH/deployment, application-wide release, force, deletion/recreation, table replacement, OCR, recognition, board generation, narration/audio/video generation or unrelated service restart.
- All architectural/visual decisions delegated to gpt-6-astra max: approved additive tables, immutable-source reconciliation, source-page mode and conservative legacy matching. Ordinary local UI change is checked against existing style; no redesign.

## Chunk 1: Shared source contract and incremental importer

### Task 1: Parse and identify sources

**Files:** Create `katrain/web/tutorials/catalog_sources.py`, `tests/web_ui/test_tutorial_catalog_sources.py`.

- [ ] Resolve catalog `project_dir`/`repo_metadata.json` and declared JSON paths against an explicit source root; support relocating the original Mac root on the test host. Reject escaped/outside roots. Deduplicate real JSON paths, never glob books/compatibility links or module duplicates as additional sources. Every catalog ID gets an outcome.
- [ ] Parse actual chapter `intro` and all section `pages` independently, even when both occur in one chapter. Preserve title/author/translator/volume/year/edition/ISBN metadata and all module memberships. Keep all page text fragments with hierarchy and pointers. Retain every actual page PNG, including unreferenced and text-only pages; locate actual three- or four-digit filenames, never synthesize an absent filename.
- [ ] Physical source figure keys are book catalog ID + page + explicit original element index when present; otherwise book catalog ID + page + physical occurrence across all fragments. Store JSON pointer and original metadata. Repeated labels/bboxes remain separate. Verify key uniqueness and physical counts against independent inventory. Nested commentary_refs resolve to physical source keys; retain links in source metadata.
- [ ] Map categories to existing constraints only: module basics→入门, opening/joseki→布局, life/death/tesuji/fighting/judgment→中盘, endgame→官子. Retain source modules. Apply the audited 官子谱 override to 官子. Expected source categories4/10/58/6; document policy.
- [ ] Focused tests: both intro+sections, repeated page-local indexes/labels, commentary alias, path relocation/realpath dedupe, all text-only page preservation, module/category mapping, missing/unsupported structure is reported rather than silently omitted. Run with `/opt/miniconda3/envs/py311_katago/bin/python -m pytest tests/web_ui/test_tutorial_catalog_sources.py -q`.

### Task 2: Add provenance and import safely

**Files:** Create `katrain/web/tutorials/source_models.py`, `katrain/web/tutorials/catalog_import.py`, `scripts/import_tutorial_catalog.py`, `tests/web_ui/test_tutorial_catalog_import.py`.

- [ ] Add models to existing Base without modifying legacy columns: `TutorialSourceBook` unique(namespace,catalog_id), book_id FK, source_json_sha256/assets_manifest_sha256, source_metadata/matching_evidence JSON; `TutorialSourceFigure` unique(source_book_id,source_figure_id), source_pointer/page, nullable figure_id FK, original metadata/match_reason, one-to-one nonnull figure mapping; `TutorialSourcePage` unique(source_book_id,page), actual image key/SHA256, ordered text fragments/page text. No fourth import-jobs table.
- [ ] Default CLI is read-only dry-run; absent provenance tables mean an empty registry without DDL. No `create_all`/DDL, filesystem asset writes, uploads or application startup in dry-run. `--apply` creates ONLY these three new tables after environment=test + recorded DB system identity + expected storage/media target verification. Settings credentials stay inherited/private and never appear in reports/commands.
- [ ] Match registry first, then corroborated slug/title aliases+author+volume+available authoritative version and hierarchy/page/figure evidence. Never title alone. Known 1997 directory vs2001 publication mismatch is a warning, not an identity veto if a unique source/legacy candidate is otherwise corroborated. Conflicting authoritative metadata/multiple candidates→ambiguity, no legacy data change. Preserve existing IDs and record all reasons/candidates.
- [ ] Existing books are `existing_skipped`: do not insert/update their book/chapter/section/figure/authoring records. Add only immutable provenance/page indexing. Match their figures one-to-one by hierarchy+page+label/order evidence, never global label or bbox; leave unmatched figure_id=NULL and report reason. Source hash or asset-manifest change for the same catalog ID requires reconciliation; never remap silently.
- [ ] New book transaction creates all chapters/intro sections/ordinary sections/figures, including actual SQL NULL board_payload/recognition_debug (use sqlalchemy.null(), not JSON literal null), original figure/page text, normalized source bbox and real remote image key. Preserve full original labels/metadata; validate existing DB field constraints and report any unsupported source rather than truncate silently.
- [ ] Upload pages before committing a book, using source-owned content-addressed PNG keys beneath `tutorial_assets/catalog/<catalog_id>/...`. Conditional object creation (`IfNoneMatch=*`), ContentMD5/SHA256 metadata and checksum agreement on reuse; never overwrite existing objects. An incomplete transaction may leave unreferenced immutable objects and must report them; a rerun reuses them safely. S3 upload failure rolls back the book; continue other sources.
- [ ] PostgreSQL advisory import lock and uniqueness constraints prevent concurrent duplication; per-book transactions and clear error boundaries. Source mappings and optional import audit records commit in the same transaction. Produce readable JSON/CSV report, book/figure mappings, reference aliases and exceptions for all78 sources. No delete/update of legacy authoring data.
- [ ] Focused tests prove repeat import has zero new records/assets, existing edited bbox/board/review/narration/audio/video/history/training untouched, ambiguity skip, changed source rejection, stable identity/null mapping and raw SQL missing-board predicates, asset failure rollback, dry-run no writes and target guard failure. Review integrity with independent max before real writes.

## Chunk 2: Existing admin page reader

### Task 3: Minimal read UI and authenticated API

**App files:** Create `katrain/web/admin/routers/tutorial_sources.py`, `tests/web_ui/test_admin_tutorial_sources.py`; modify `katrain/web/admin/app.py` only to mount the protected source router.

**Actual UI files:** In the SmartBox worktree modify `admin-console/ui/src/admin/AdminApp.tsx`, `admin-console/ui/src/admin/api/client.ts`; create `admin-console/ui/src/admin/tutorials/SourcePages.tsx`, scoped CSS and focused component test.

- [ ] Freeze API contract: `GET /api/admin/tutorials/books/{book_id}/source-pages` returns `{book_id,source_catalog_id,pages:[{page,page_image_path,has_text,figure_count}]}`. Detail `/source-pages/{page}` returns `{book_id,page,page_image_path,page_context_text,text_fragments:[{kind:description|figure_ref,text,source_figure_id?,chapter_title,section_title,source_pointer}],figures:[{source_figure_id,figure_id,figure_label,bbox,match_reason}]}`. Include original figure captions even when figure_id=NULL. No Mac absolute URL, HTML rendering, full source blobs or credentials in outputs; fetch one page detail at a time.
- [ ] Add “棋图 / 原书页” mode for selected book, page selector and previous/next controls. Reuse admin typography, palette/sidebar/geometry; maintain existing figure authoring workbench. Show figure text and page text separately; board_payload=NULL shows“待识别” and no fake recognized empty board. Explicit edit-board still initializes its draft.
- [ ] Preview the new reader with real parsed page fixture supplied only through browser test interception, at the existing admin viewport; independent max visual check delegated by user. No fixture business data in production code. After that check, implement the protected read endpoint over the frozen foundation, with404/empty/unavailable/error/retry states and existing service auth.
- [ ] Run focused API auth/shape/page-not-found tests and UI mode/navigation/pending-recognition checks plus typecheck/build once. Keep old unmodified legacy AdminApp out of this UI implementation.

## Chunk 3: Test data, deployment and actual acceptance

### Task 4: Prepare target, dry-run and safeguard data

- [ ] Retain redacted test environment identity report and DB books/structure inventory outside Git at `/Users/fan/.local/share/smartbox-admin/tutorial-import-20261013/`. Verify admin login/env and current media asset browser reachability.
- [ ] Make private custom-format backup of full tutorial books/chapters/sections/figures, board_payload_history/training_samples/admin_audit_log; verify archive and restore into a new isolated test database. Confirm counts/fingerprints there, then remove only that rehearsal DB. Never restore over the live target.
- [ ] Transfer only catalog, canonical output/book.json and actual output/pages (about2.22GB) into a private test source staging directory; do not transfer PDFs, compatibility links or whole application/source repos. Preserve original-source identity in the relocated manifest.
- [ ] Run the importer read-only against the real test DB; record all78 proposed statuses and source→existing book IDs, unmatched/ambiguous figures, asset needs and warnings. Independent max final code/data review before applying.

### Task 5: Apply, rerun and deploy narrowly

- [ ] Build and smoke-check the narrow provider/console artifacts BEFORE live data apply. Apply the reviewed importer to the verified test target. Continue failures/ambiguities and retain old data. Re-run `--apply` unchanged; verify zero newly created business/provenance records and assets, stable ID mappings, and exact baseline row fingerprints unchanged.
- [ ] Test-only provider image layers copy only new tutorial modules/router and the existing app mounting change over currently deployed provider516249704 (relevant original tutorial/app/model files are unchanged versus app develop2aa81b37d). Keep provider service credentials/networks/port and existing container configuration; recreate only its provider. After import and repeat-run data checks pass, switch the provider and console; build/recreate only the unified test console UI/API image with its unchanged private env and audit volume. Keep public web/cron/Postgres/MinIO/engines/production/RK3562 intact. Retain concrete rollback image IDs and container configuration privately.
- [ ] Use the real test admin browser login: select a newly imported book; browse chapter introduction and section figures, inspect original page+both text types, text-only original page, pending recognition. Verify remote PNG actually decodes after existing asset redirects/CSP, and one existing verified book/media remains accessible. Verify API source mapping count matches planned physical records and all78 statuses accounted for.
- [ ] Publish only test import report/book mapping/figure mapping/exception list and actual access instructions. Source code commits stay on task branches; no production release/merge-to-develop is inferred from test authorization. Final report states actual outcomes, counts, repeat-run deltas, preservation evidence, deployed test revisions and any explicit exceptions.

## Review record

Independent gpt-6-astra max architecture and plan round1 approved. Incorporated absent-registry readonly behavior, complete page-caption contract and build-before-apply/switch-after-data-check sequencing. New missing-board values use actual SQL NULL; no legacy JSON column change.
