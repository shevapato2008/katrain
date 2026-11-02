# 星阵标准下的棋谱结果、段位和同局去重实施计划

> **For agentic workers:** REQUIRED: superpowers:subagent-driven-development. User requires separate investigations, writing-plans, independent ASTRA/MAX plan review (at most two rounds), parallel owned-file implementation, then independent ASTRA/MAX code review and fixes until approved.

**Goal:** 在整个棋谱库采用星阵的统一元数据约定，修正错误职业/业余标注和结果显示，合并有充分证据的重复展示，并让 Kiosk/Galaxy 同时受益。

**Architecture:** 共享结果/段位格式化器负责显示。数据库保留原 SGF、原字段与来源，以可验证的、逐棋局冻结的标准化段位覆盖表达来源方言转换；不把今天的段位倒填历史。复用现有可撤销去重批次维护展示主记录，星阵优先，分析继续绑定精确 SGF。全库扫描产生有界、可审查、带前像的写入包，默认 dry-run；审核和本地验证通过后再应用用户已授权的数据修复。

**Tech Stack:** Existing Python SGF parser/SQLAlchemy/PostgreSQL, existing catalog provenance/rank snapshot/audit tables, React/TypeScript shared utilities and both existing kifu pages. No new service, fuzzy-name engine or SGF rewrite.

## Chunk 1: Independent evidence and acceptance contract

Independent investigations (read before implementation):

- `docs/superpowers/reviews/2026-11-03-kifu-result-investigation.md`
- `docs/superpowers/reviews/2026-11-03-kifu-rank-investigation.md`
- `docs/superpowers/reviews/2026-11-03-kifu-metadata-dedupe-investigation.md`

176,949 albums / 176,690 public; all SGFs scanned. Source links identify 154,231 19x19 albums and 22,718 CWI albums. Directories alone and SGF SO alone are not source authority. Existing 9 duplicate pointers and 250 other hidden records must be preserved.

### Result contract

1. Bare B+/W+ means known winner, unknown winning method/margin; render existing localized black_win/white_win keys. It is not resignation. 144 raw-SGF observations / 141 public; no database result rewrite is necessary to display these correctly.
2. Reuse shared `translateResult` in both UIs. Kiosk list winner detection must recognize bare wins; retain its established Chinese resignation wording.
3. Fix only observed adjacent parsing defects: numeric details must match the whole value; preserve uncertainty such as W+11.5? rather than silently claiming 11.5. Properly handle observed Chinese denominator form 四分之一/4分之1 and escaped fractional slash after SGF decoding. No broad result grammar rewrite or invented units/rules. Malformed/unrecognized values stay honest raw text.

### Rank/source contract

1. Canonical representation follows starpoint: typed professional `Np`, explicit amateur `Nd`, kyu `Nk`; professional ranks render Chinese numerals in simplified/traditional Chinese (职业九段/職業九段), and standard localized digits elsewhere. Bare dan remains system-unspecified when no evidence proves type. Do not globally label every SGF `d` as amateur: FF4 BR is SimpleText and recommends d/dan for dan generally.
2. Preserve original SGF bytes, raw BR/WR metadata and source links. Do not overwrite original grades, classify all players professional, or use current profile rank as a historical grade. Existing explicit amateur and insei kyu records remain amateur/kyu.
3. Whole-corpus source normalization: all recognized old-source unqualified d/dan values must stop falsely implying amateur. Use trusted source-link family to distinguish historical CWI generic dan from starpoint's typed convention; normalize these to system-unspecified unless stronger same-game historical evidence proves professional. Whole scan found 5,571 legacy d slots and 9,586 starpoint d slots; census, not automatic pro counts.
4. A historical professional refinement requires exact full operation identity, matching ordered player identity, same grade and explicit p/职业 on the starpoint counterpart. Incompatible/conflicting counterpart grades are refused. Precise compatible dates are required for automatic repair; other cohorts remain explicit review candidates. User-reported pair gets a separately recorded reviewed Yoda Norimoto ↔ 依田纪基 identity plus official historical seven-dan evidence, not a generic transliteration rule. Do not use current-professional status alone for pre-career games.
5. Known source proof must come from `KifuAlbumSource` + `KifuSource`; pin exact source link/path, original SGF SHA, side and original raw rank. Unknown/ambiguous source cannot silently receive starpoint semantics.
6. Add a small backward-compatible source-normalized snapshot policy/version in the existing `KifuAlbumRankSnapshot.snapshot` JSON. Existing v1 snapshots/facts remain unchanged and readable. A normalized-source observation need not become a global current-rank fact (`rank_fact_id` may remain NULL); avoid adding thousands of misleading current-profile observations. Valid v2 snapshot wins over raw display only after exact record/source/hash/raw binding; invalid normalization falls back to truthful source-aware unspecified rank, never a fabricated pro/amateur claim. Support legacy uppercase/nested/date source paths by pinning exact path, not weakening numeric v1 publication validation.
7. Reuse existing audit batch/change tables where semantically suitable; keep original and new snapshot images and immutable evidence. Do not introduce a generic sync/migration framework. New snapshots must carry an unambiguous audit publication key and valid originating batch identity, not arbitrary sentinel IDs. Applying a second time is idempotent; unrelated existing snapshots are never overwritten.
8. One shared kifu presentation path must serve both lists/details. Remove Kiosk's independent d→业余 inference on raw legacy fallback. Generic user strength formatting outside kifu must retain its established numeric/amateur meaning. The canonical rank in API is language-neutral; localized strings are not stored in DB.
9. Subsequent starpoint ingestion uses the same known-source normalization contract. Preserve existing native manifest v1/v2 validation and exact retry semantics; add focused fixtures showing future starpoint p/d/explicit-amateur records remain correct.

### Dedup contract

1. Exact-source-byte duplicates already hidden: zero visible exact duplicates. 1,885 full-operation candidate groups are not a deletion list. The full identity includes board size, expanded ordered AB/AW/AE, PL, colored moves/passes, and setup context; preserve original SGF/variations. Existing moves-only signature is candidate-only.
2. Automatically eligible cohort requires compatible precise full date, both ordered players resolved to same approved IDs, complete operation equality, and nonconflicting explicit komi/handicap/result/rules. There are 186 two-row groups in the frozen census; add explicitly reviewed target 25055/140858 after verifying its identity evidence. A group with unresolved/conflicting IDs or dates, setup differences, or metadata conflict remains report-only. Whole library is scanned and uncertainty counts reported; do not pretend all 1,885 candidates are proved duplicates.
3. Canonical preference: existing visible starpoint record first; stable ID tie-break among equally qualified records. Missing/low-quality setup cannot be preferred merely because source is starpoint. Same-game proof precedes canonical selection. Retain source rows and direct old-ID detail, only hide reviewed duplicates by pointer and aggregate provenance onto master with `reviewed_same_game`, not `exact_sgf`.
4. Reuse `KifuDedupBatch/Change` for before/after pointer/source images. No hard deletes, FK migration, SGF changes, analysis-job reassignment, or loss of original provenance. No self/chain/cyclic pointer and no changes to another batch's pointers.
5. Upgrade importer/backfill pointer validation for explicitly journaled reviewed same-game pointers. Do not weaken all pointers into arbitrary non-identical SGF acceptance. Exact-content reimport of a duplicate must continue to succeed and attach provenance correctly. This includes the actual native incremental path in `katrain/kifu_ingest/catalog.py`, its exact-source-owner selection, publication/retry/replay receipt validation, and old original IDs that are now hidden. Of the 186 eligible groups, 98 are starpoint-to-starpoint, so the native path is mandatory scope. Prefer the exact original SGF/source slot when multiple aggregated source owners exist; accept its hidden status only through verified journaled same-game ancestry. Keep original publication receipts/SGF/IDs immutable and return source-specific identities, not another source’s engine payload. Native replay verification must recognize intentionally hidden, proved duplicate cards while validating all original publication invariants. Do not globally relax public-card or SGF equality requirements. The analysis endpoints/library retain their exact SGF equality rule; display dedup must not grant analysis interchangeability.

## Chunk 2: Owned implementation tasks

### M1 — shared result and professional-rank display

**Own:** `ui/src/utils/resultTranslation.ts` and tests; `ui/src/utils/rank.ts` and tests; `ui/src/kiosk/utils/listRecordPresentation.ts` and tests; narrow BOTH Kiosk/Galaxy kifu consumers/tests only if required for shared presentation. Do not edit account-history/physical files or PO catalogs concurrently.

- [ ] Write focused RED tests for bare B+/W+/lowercase, unknown margin/method, uncertain numeric suffix and observed fractional forms; winner style and both UI paths. Implement minimum shared fix and run related existing tests.
- [ ] Write Chinese pro-number RED tests including 9p, professional Chinese text, cn/tw/en, ordinary user rank unchanged, legacy normalized bare dan and true amateur retained. Delegate to shared helper; remove conflicting list-only inference. Reuse locale keys; no newly missing i18n keys.
- [ ] Validate both real card consumers with same API fixture; preserve SGF navigation and board behavior. Record unrelated baseline failures separately, fix only new regressions.

### M2 — whole-corpus source-aware rank normalization and frozen overlays

**Own:** new focused `web/kifu/source_rank_normalization.py`; small existing `player_ranks.py`/`kifu_ingest/ranks.py` seams; `api/v1/endpoints/kifu.py` rank display and source binding only; source rank normalization tests; rank part of preparation/apply CLI through a helper owned exclusively by M2. Do not edit M3 dedup/importer/backfill or M1 UI files.

- [ ] RED tests for trusted CWI d→unspecified vs starpoint d→amateur, exact counterpart d→p only with matching historical evidence, missing/ambiguous/conflicting proof, nested paths, source-link spoofing, foreign album/side/hash/raw, old v1 unchanged, old source parseable suffixes, explicit amateur/kyu and historical insei preserved.
- [ ] Implement small canonical source policy and a bounded v2 snapshot builder/validator. Store raw unchanged and language-neutral display. Prefer validated normalization in API, one bounded query for a list; no N+1 corpus/profile discovery at request time.
- [ ] Prepare whole-corpus rank changes from live source-linked metadata and reviewed exact counterpart evidence, including explicit target pair. Generate exact per-slot preimages/afterimages/evidence and unresolved/conflict counts. No runtime fetching official profiles for every card.
- [ ] Implement transaction-owned apply/undo helpers reusing existing audit infrastructure, exact preconditions/idempotency/no stale overwrite. Validate durable beforeimages and rank publication identities. Cover one existing unrelated snapshot and concurrent changed source/preimage causing full refusal.
- [ ] Add future-ingest focused fixture proving known-source p/d/k semantics remain stable without weakening old native publication evidence validation.

### M3 — reviewed semantic dedup and guarded catalog repair tool

**Own:** new focused `web/kifu/catalog_standardization.py`; new `scripts/standardize_kifu_catalog.py` orchestration (M2 helper imported); narrow `web/kifu/catalog_backfill.py`, `scripts/import_kifu.py`, and actual native `kifu_ingest/catalog.py` pointer/source/publication/replay validation; focused standardization/import/dedup tests. Do not edit analysis safety guards, rank policy/API or M1 UI.

- [ ] RED tests for target pair canonical140858, 186 eligible cohort rules, source-first stable preference, differences in setup/PL/pass/size, raw/fuzzy identities/date-only/metadata disagreements excluded. Preserve variations/content and exact analysis safety.
- [ ] Implement full operation fingerprint and deterministic reviewed manifest generation; include both members' exact SGF SHA, source/identity/date/metadata/source-link preimages and canonical decision. A manifest must record exact preconditions and excluded reasons, not an unbounded flag to merge all similar moves.
- [ ] Apply/undo using existing DedupBatch/Change, transaction locks, preimage revalidation, original source links and source hashes; no arbitrary pointers accepted. Default CLI is dry-run; explicit frozen manifest+hash required for apply. Repeat same manifest is no-op; drift/refused group must not partially update a batch. Reuse existing maintain_after_write search maintenance rather than add a new index system.
- [ ] Change importer/backfill only to recognize verified journaled semantic pointers; byte-identical behavior unchanged. Verify legacy exact reimport, native starpoint source import, exact native retry, replay verification and raw-ID detail remain functional and analyses stay byte-bound. Add a real native publication fixture that is then deduplicated, retried/replayed, and imported again from its original source; no arbitrary hidden record or unjournaled cross-SGF pointer may pass. Include both starpoint-to-starpoint and CWI-to-starpoint cases.
- [ ] Integrate M2 prepared rank repair within the same reviewed tool without shared concurrent file edits. Export and verify rollback artifact before any environment writes. Tests prove independent later changes cause guarded undo refusal, not silent destruction.

### Controller — review, data repair and actual UI acceptance

- [ ] Independent ASTRA/MAX plan review round1; fix findings; round2 maximum. No M1/M2/M3 product implementation until plan approved.
- [ ] Dispatch M1/M2/M3 with frozen owned files, run focused tests and independent spec check, then independent ASTRA/MAX code review; fix until approved. User already authorized implementation and database dedup/standardization; no invented extra permission gate.
- [ ] Inspect full live dry-run manifests for BOTH home-ubuntu and ucloud-v100 (IDs may differ). Verify total/eligible/excluded counts, exact target pair and rank conversions; do not reuse IDs from one DB blindly.
- [ ] Before any production data apply, require a deployed-writer/read-model compatibility preflight for the actual native ingest, legacy import/backfill and v2 normalized rank readers. A local candidate binary is not proof that the live writer is compatible. Current deployed code predates these contracts; no data apply may proceed against it. This development request ends at reviewed code and reviewed repair manifests unless a compatible release has been authorized/performed. Prepare durable beforeimage/rollback artifacts now; apply only after compatible runtime release and fresh live precondition checks. Never make partial production repair or ad-hoc SQL changes to bypass this order. No SGF deletion.
- [ ] Verify committed DB state, API outputs under the candidate code in an isolated runtime, search preparation and old-ID access. Because current production binary may not understand new v2 rank overlays, distinguish DB repair verified from frontend fix deployed; do not claim currently deployed UI fixed without deploying authorized integrated code. No release/merge was requested.
- [ ] Both Kiosk/Galaxy representative actual previews: bare win translated, target professional ranks Chinese numerals, same-game list one starpoint card, original preview still works. Target viewport parity; existing geometry; no new visual system. Physical/account development is separate and must not be overwritten by metadata work.
- [ ] Report changed record/slot counts, unproved candidates preserved, audit/undo locations, test/review evidence and deployment status candidly. No all-candidate deletion claim.

## Verification commands and expected outcomes

- Python focused new standardization/rank/pointer/import tests plus existing catalog/rank/api tests: pass, disposable SQLite/PostgreSQL only until reviewed application phase.
- `cd katrain/web/ui && npx vitest run src/utils/resultTranslation.test.ts src/utils/rank.test.ts src/kiosk/utils/listRecordPresentation.test.ts` plus both affected Kifu page suites: pass; cn/tw professional output contains no Arabic grade.
- `npx tsc -b --pretty false`; `npm run build:kiosk-2d`: pass with import guard. Existing unrelated missing i18n baseline must not increase.
- Apply/undo roundtrip on disposable PG: data and source links restored; concurrent drift refused. Production writes only from reviewed frozen manifests after code review AND deployed-writer compatibility preflight. Without a compatible release, production application remains explicitly pending; the development artifact is ready, not claimed applied.

## Implementation record — 2026-11-03

M1/M2/M3 implemented; final independent ASTRA/MAX code review APPROVED, including the post-census referenced-name authority correction. Whole-live read-only manifests regenerated and uncached-validated for both environments:187eligible duplicate pointers and5571rank overlays per environment (5550unspecified +21historical professional refinements). Existing184rank snapshots and259hidden rows preserved. Root verified both manifest hashes and current preparation-module hashes. Actual both-surface runtime evidence and final check limitations are in the linked review records.

Production data application is explicitly pending compatible runtime release. Both live deployments are7f2ff0c65381250e41a9dc959d8cac9201c3a86b and fail native-original-receipt/HTTP-duplicate-proof/source-v2-reader compatibility. No production writes, release or deletion occurred; approved code and frozen repair/rollback artifacts are the development deliverables.
