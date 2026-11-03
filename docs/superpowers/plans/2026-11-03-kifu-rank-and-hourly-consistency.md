# Kifu rank and hourly consistency Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`) syntax. The user requires independent gpt-6-astra/max plan review (at most two rounds), parallel implementation where ownership permits, and a fresh independent Astra max final code review with fixes until approved.

**Goal:** Persist one honest canonical rank decision for old and newly collected games, fill verifiable historical gaps, and include semantic deduplication plus timely finite Elasticsearch synchronization in the existing hourly publication lifecycle.

**Architecture:** Preserve original SGFs/raw columns and all old facts/receipts. Add a small versioned historical rank resolver and reuse the existing album snapshot table, native journal/CAS/undo and TEST-to-PROD publication. Resolve once before publication; neither page performs live player lookups. Hourly work is bounded to the batch and relevant indexed candidates, rather than calling full-library repair preparation.

**Tech Stack:** Existing Python, SQLAlchemy/PostgreSQL, native incremental manifest V2, Elasticsearch sync gate, pytest and shared TypeScript rank formatter. No new service, table, external profile crawler or model.

---

## Evidence, scope and decisions

Baseline: origin/develop `bc248574d9b49ffecf641d08945938ca1c1e79aa`; isolated worktree `/Users/fan/.config/superpowers/worktrees/katrain-kiosk-debug/kifu-rank-hourly-20261103`. Focused baseline: 80 passed.

Read-only investigation on 2026-11-03 found:

- Both pages use `formatKifuRank`; `9p` becomes 职业九段, `9段` becomes 九段. Old native snapshots can contain `professional_dan` alongside a bare Chinese display string. The prior 5,571-row repair had 21 proved professional refinements and 5,550 unspecified results; it did not classify all bare ranks.
- PROD has 136 player facts, 5,755 album snapshots and 3,689 players. Go Seigen has no current/history fact. His 230 raw-empty slots include 208 names with embedded source ranks; only 22 genuinely lack a displayed source rank (20 public).
- Verified missing cases: 65690 black and 65736 white, 1968-08-01, can use the same exact player in 136916 white, 1968-05-23, explicit 9p. 152129 white, 1934-06-03, can use 140822 black, 1934-04-25, explicit 5p. The latter is historical evidence, not an identical-game match.
- Go Seigen's scalar pilot has 175 potentially refinable bare-rank slots, including 113 bare nines, after excluding a 7-versus-earlier-8 contradiction. This is candidate scope, not an approved write count. Seventy-five more slots have a nearer explicit 19x19 `9d` boundary and remain blocked.
- Date 2002-11-30 contains inconsistent historical grades and upload-like records (e.g. 本因坊秀哉/第二局成名作). Matching DB and SGF dates alone does not prove historical reliability.
- Both live cron collectors are disabled; heartbeat is fresh, interval is 3600 seconds, LLM is disabled with zero budget, publication transport and ES writer configuration are absent. Home has five unfinished old batches; old failures included preparation memory budget exceeded. Do not silently reset/recreate their state or enable paid calls.
- Historical successful whole rounds took 36–43 minutes for 1–3 inserted receipt items; recent failed rounds took 24–25 minutes. These are old total-run measurements, not current ES timing. Existing ES code does not retain separable projection/bulk/refresh times.

Canonical database decisions use `rank_value`, `rank_system` and a matching neutral code: `Np`, `Nd`, `Nk`, or `N段` for an unspecified system. Chinese professional display stays 职业一段…职业九段. Raw fields remain provenance, not the canonical layer.

Decision priority:

1. Preserve the source-aware matrix: `p/pro` is professional; 19x19 `d/dan` is amateur; non-19x19 unqualified `d/dan` is unspecified; explicit amateur syntax is amateur; k/kyu is kyu. Apply the same matrix to embedded source-name ranks. Never replace a known source numeric grade with a profile. An unreliable date blocks inference, not preservation of an explicit source rank. Conflicting root/name ranks refuse inference.
2. Bare source dan keeps its numeric grade. It may become professional only using the same uniquely bound player and verifiable evidence no later than the game, with no intervening contradictory typed observation or professional grade decrease.
3. Missing source rank may use the latest qualified original observation no later than the target game. Retain the evidence date and origin `historical_prior` (latest known as of then), not a fabricated promotion date.
4. Unknown identity, imprecise/placeholder/untrusted dates, tied contradictory grades/systems, incompatible observations, or unavailable exact evidence produce an explicit unknown/refusal. Do not infer from later games, current profiles or another inferred snapshot.
5. Same-game evidence requires the existing complete operation fingerprint, ordered unique identities, compatible metadata and exact source bindings. Same players/day alone is never enough.

Date safety: use `_precise_date`/calendar checks, and build per-owner same-day rank conflict summaries from source scalar observations. Reject ambiguous day/cohort decisions; the shared versioned policy (including native receiver validation, not only the CLI) excludes the known upload-like 2002-11-30 inference date. No player-name hardcode. Other source dates remain observations, never inferred promotion dates. Month/year-only games stay unresolved in this slice.

No filesystem access, traversal or listing under `data/kifu-album/`; all source content comes from bounded SQL reads or existing stage/manifest bodies. No hard deletion. No arbitrary all-professional assumption, UI-only disguise, broad new research pipeline or periodic full-index rebuild.

## Chunk 1: Shared historical rank foundation

### Task 1: Resolver, portable evidence and versioned snapshot

**Files:**
- Create `katrain/web/kifu/historical_ranks.py`.
- Create `tests/web_ui/test_kifu_historical_ranks.py`.
- Reuse parsers/source binding from `source_rank_normalization.py`, `source_rank_repair.py`, `player_ranks.py`; do not change their existing v1/v2 hash rules.

- [ ] Write failing cases for the three verified missing games, bare nine with prior p, explicit amateur, embedded rank, future-only evidence, same-day conflict, intervening typed d, grade decrease, partial date, upload-like conflicting date, and same-day different game.
- [ ] Implement pure decisions plus indexed owner/date candidate lookup. Inputs are source observations keyed by exact owner/canonical identity/date; no current-profile fallback for historical games. Fetch SGFs only for chosen bounded evidence and validate root DT/PB/PW/BR/WR, exact SGF SHA, trusted source link and owner identity. Native batch limit remains 100 games / 200 owners; large historical audits stream in bounded chunks.
- [ ] Define one new snapshot version `kifu-rank-snapshot-v3`, policy `historical-rank-as-of-v1`, with these fields (exact field allowlist and canonical SHA):

```text
version, policy_version, source_ref, player_ref, raw_rank, raw_name,
display_rank, rank_value, rank_system, origin, target_date,
basis, qualification, refusal_reason, matched_at, content_sha256

source_ref = {source_key, origin_path, sgf_sha256, slot}
player_ref = {canonical_name} | null
origin = source | historical_type | historical_prior | unknown
basis = finite exact original source refs, raw root rank/name/date,
        normalized grade/system, canonical owner and evidence hashes
```

Portable snapshot bytes contain no local DB IDs. Album/side/FK/source-link bindings live in the local snapshot row and journal. Each chosen basis must be found by exact path/source/SHA in the receiving DB or the same frozen incoming batch; reject absent/mutated evidence rather than reselecting a newer fact. Evidence tie-break is source key/path/SHA/slot, never local album ID. Use one supplied `matched_at` for paired historical prepares when claiming full snapshot SHA parity. Inferred snapshots never become original evidence for further inference.

**Initial qualification vs replay (R1 B1):** the frozen v3 decision includes material `qualification` evidence: owner/target day, exclusion policy, latest qualifying original observation/day, same-day normalized grade/system set, intervening typed boundaries and professional maximum/grade-decrease guard. On first repair apply and first native/PROD receipt, acquire the existing writer/advisory lock, relevant target/evidence row locks and the existing READ COMMITTED/table-lock cohort-recheck pattern from `source_rank_repair._live_preflight`; then freshly recompute this material qualification from the complete bounded scalar cohort before any write. Newly nearer, tied or disqualifying data causes rejection, never replacement of the chosen basis. A conflict beyond a body shortlist still blocks. TEST/PROD need equal material qualification, not equal local IDs/irrelevant observation inventory. Future observations after the target day do not enter it. Already-applied replay validates original journal/receipt and does not perform this initial resolution again.

**Frozen interfaces before parallel work:**

```python
# historical_ranks.py (pure decision + bounded DB adapter)
prepare_rank_decisions(conn, targets, *, matched_at)  # portable decisions + refusals
validate_rank_decision(decision)                    # shape/hash/policy
verify_initial_rank_decisions(conn, targets, decisions)  # locks held; live qualification
bind_rank_decision(conn, target, decision)           # exact local basis bindings
assert_retained_rank_basis(conn, removed_bindings, *, excluding_batch_ids=())

# historical_rank_repair.py
prepare_manifest(conn, *, matched_at, album_ids=None)
apply_in_transaction(conn, manifest, *, expected_sha256)
undo_in_transaction(conn, manifest, *, expected_sha256)
```

`qualification` is a required allowlisted v3 field included in the snapshot hash. Local `basis_bindings` are stored in applied native/repair artifacts: exact basis album/source-link/owner IDs + portable refs and target snapshot binding, with a deterministic binding hash. They are not portable snapshot fields.

**Shared resource ceilings (R1 B3):** fix constants before workers split: 100 incoming games / 200 owners; scalar rank cohort at most 50,000 rows and 32 MiB per batch; semantic/noncanonical body cohort at most 500 rows; per SGF 256 KiB, cumulative fetched evidence/candidate SGFs 8 MiB per batch; each bounded candidate query 5s (PostgreSQL SET LOCAL, restore parent setting afterwards). Read counts/lengths/scalars before bodies. Whole-cohort overflow produces an explicit resource-deferred outcome, with zero inference/dedup from a truncated cohort; an original-source ownership integrity check that cannot finish rejects publication. Same-day scalar conflict aggregates cover the entire relevant set independently of selected bodies. These are refusal ceilings, not claims that all batches fit. Historical full-corpus audit streams chunks but applies the same per-owner/cohort safety policy.

- [ ] Canonical display derives from grade/system and is validated for v3; a professional system with bare display cannot be constructed. Unknown carries a refusal code and no invented grade/system. Freeze time does not become rank validity time.
- [ ] Run `PYTHONPATH=$PWD CI=true /Users/fan/Repositories/katrain-kiosk-debug/.venv/bin/python -m pytest -q tests/web_ui/test_kifu_historical_ranks.py tests/web_ui/test_kifu_source_rank_normalization.py` (pass), then commit foundation.

### Task 2: Freeze/publish/read the same decision across both databases and pages

**Files:**
- Modify `katrain/kifu_ingest/ranks.py`, `orchestration.py`, `catalog.py` rank dispatch points only.
- Modify `katrain/web/kifu/player_ranks.py` snapshot batch loader only as required.
- Modify `katrain/web/api/v1/endpoints/kifu.py` shared rank reader.
- Extend `tests/test_kifu_rank_freeze.py`, `tests/web_ui/test_kifu_rank_snapshots_api.py`, `tests/web_ui/test_kifu_incremental_catalog.py`.
- Existing frontend formatter/tests: `katrain/web/ui/src/utils/rank.ts`, `rank.test.ts`; no layout work.

- [ ] Write failing integration tests: new source bare rank -> canonical decision; empty historic rank -> earlier fact; same frozen package TEST/PROD local IDs differ but snapshot hash agrees; prepare→apply nearer typed conflict, receiver-only conflict and conflict beyond shortlist reject; future evidence does not affect an earlier target; later evidence does not drift applied replay; wrong owner/raw/source/date/SHA rejected.
- [ ] Introduce explicit version dispatch while preserving v1/v2 validators and their original outputs/receipts. V2 manifest envelopes may carry v3 snapshots; old receivers must reject unknown snapshot version. Preserve old source observation/history behavior and never rewrite legacy facts.
- [ ] New prepare freezes historical decisions before paid name calls; retries load the existing staged decision. Preserve the old checkpoint lookup namespace or try its exact old key before selecting a new v3 request key (`rank_decision_request` includes policy). Test a mixed batch with an old frozen item and a new v3 item: only the new item resolves. Dispatch version handling in validation, fact reference collection, reporting, API verification, publish and replay. `rank_facts/rank_observations` remain original observations; historical inference never becomes an original fact. The receiver verifies exact basis **and initial material qualification** under the writer/table locks, not today's current profile.
- [ ] Native publication stores v3 in the existing snapshot table with native batch journal. Validate canonical identity, precise target source/body/raw and finite basis. Keep original source ownership, receipt album ID, original SGF and old snapshot replay contracts.
- [ ] **Reverse dependencies (R1 B2):** before the first compensation write, native undo calls `assert_retained_rank_basis` for every album/link/identity binding it would delete/invalidate. Inspect all currently applied v3 snapshots and their validated native **or standalone historical-repair** artifact bindings, not only V2 receipts/rank_fact_id. Retained basis dependency rejects the whole undo. Test evidence publication A → native target B and separately historical-repair B using A → undo A atomically refuses → undo B → undo A succeeds. No new dependency table; existing snapshot/artifact JSON is sufficient.
- [ ] Shared API list/preview/detail accepts v3 only with exact target bindings, applied batch and matching journal afterimage; invalid overlays fall back honestly. Page requests batch-load snapshots and never query other games/player profiles per card. Return canonical code + origin/as-of provenance.
- [ ] For legacy typed/display mismatch, do not blindly trust a current professional identity for an old game. Correct eligible rows through the reviewed CAS repair below; leave immutable legacy bytes intact.
- [ ] Run the above focused integration suites plus `tests/test_kifu_api_verification.py`; verify cn/tw professional numerals and explicit amateur/unknown using existing formatter tests. Commit after passing.

## Chunk 2: Historical repair and hourly publication (parallel after Chunk 1 contracts stabilize)

### Task 3: Database canonical repair with reviewed beforeimages

**Ownership:** Worker A owns new historical repair module/CLI/tests; does not edit catalog/search files owned by Worker B.

**Files:**
- Create `katrain/web/kifu/historical_rank_repair.py`.
- Create `scripts/repair_historical_kifu_ranks.py`.
- Create `tests/web_ui/test_kifu_historical_rank_repair.py`.
- Reuse `name_batch.py` insert/update/change journal, existing locks and `search_sync` coordinator.

- [ ] First test default dry-run, exact beforeimage drift refusal, idempotent apply, safe undo, existing snapshot correction, and no raw SGF/rank/source/visibility changes.
- [ ] `prepare` reports a census of **all** album/source slots, including hidden/excluded scope, but materializes eligible changes only for public targets. Count unchanged source, missing/qualified, refinable/qualified and each refusal reason separately. Include target raw/name/FK/date/source SHA plus complete snapshot before/after and material qualification. Bind manifest to database identity, policy, code and canonical SHA.
- [ ] Create canonical v3 rows where absent. Existing legacy/source snapshots may be corrected only by an explicit new CAS journal with full beforeimage; preserve original batch/receipt evidence, never mutate an old manifest. Existing v3/other-party corrections are not silently replaced. Current afterimage mismatch rejects the entire reviewed batch.
- [ ] Expose `apply_in_transaction(conn, manifest)` / `undo_in_transaction` for existing native transaction use, and a CLI coordinator that owns locks, real commit and existing ES pending/ready protocol when visibility/search fields are involved. Pure rank-only changes need no full ES rebuild because API reads rank snapshots from PG. Do not claim raw columns are canonicalized.
- [ ] Apply locks targets/evidence and cohort-recheck tables in the existing deterministic order; validates chosen original evidence, **fresh material qualification** and exact complete beforeimages before first write. Persist validated local basis bindings in its artifact so native undo sees repair dependencies. Repeated apply returns original decision; old publication replay never reruns historical resolution or overwrites a later correction. If an old contract must refuse a superseded snapshot, fail closed without data changes and test it explicitly.
- [ ] Freeze independent TEST/PROD manifests because local IDs can differ; compare logical decision/hash parity. Save private full beforeimages and sanitized summaries. Dry-run reviewed counts are the actual scope; the 175 pilot candidates are not a promised repair count.
- [ ] Run focused new repair/API tests and existing `test_kifu_source_rank_repair.py`, then commit.

### Task 4: Hourly finite semantic dedup and index consistency

**Ownership:** Worker B owns catalog/dedup/search/cron tests after rank dispatch changes from Chunk 1 are stable; does not edit Worker A files.

**Files:**
- Modify `katrain/kifu_ingest/catalog.py` publication/replay/undo and source lookup.
- Modify `katrain/web/kifu/catalog_standardization.py` finite prepare mode.
- Modify `katrain/web/kifu/search_sync.py` child journal validation/scope and timing logs.
- Modify `katrain/cron/jobs/kifu_ingest.py` only if configuration preflight/result propagation requires it.
- Extend existing catalog/dedup/search publication/cron tests.

- [ ] Failing tests: incoming different metadata/same full game, same player/day but different game stays distinct, retry returns original receipt, later new evidence does not silently refreeze old batches, undo restores child changes first, ES failure retains pending and original replay recovers ready.
- [ ] Query original source receipts/links by the incoming source keys/paths, rather than building all-source Python maps. Preserve `_select_source_owner`, exact original source checks and native/manual original retry behavior.
- [ ] Remove full-library Python canonical SGF warm/parse from the ordinary new publication path. Preserve exact SGF compatibility using a SQL exact canonical-content branch followed by full equality checks; for existing noncanonical content, use bounded metadata cohorts plus parser comparison and document the conservative fallback. Do not claim an unindexed content equality predicate is an indexed DB lookup or add a new global hash-index project.
- [ ] Add optional candidate-ID/cohort inputs to the existing semantic dedup prepare, keeping its default CLI semantics unchanged. Hourly cohorts come from incoming exact dates and ordered uniquely bound identities. Fetch only these originals and relevant source links; retain full operation/setup/pass/variation/metadata checks, ambiguity exclusions and existing canonical preference. Hardcode no Go-specific rule in this path.
- [ ] Apply incoming shared rank decisions and semantic dedup under the *same* `catalog_publish/_locked_write` transaction, before final artifact/undo_guard. Do not change public original receipt album IDs/actions or SGF ownership. Freeze the child-artifact contract before worker edits: `catalog_repairs={version, dedup:{manifest,manifest_sha256,batch_id,journal_sha256}, affected_album_ids}`. Validate child exact hash/membership/current afterimages on replay and before any compensation; compensate the dedup child before parent intermediate afterimage checks. Rank bindings stay in the parent, including v3 basis dependencies.
- [ ] Scope reduction from R1: hourly writes v3 for incoming original slots only. Existing frozen snapshots are never upgraded by retry or a new incoming batch. Report existing-record correction candidates as deferred for the independently reviewed historical CAS tool. No rank child lifecycle or hourly full-corpus prepare.
- [ ] Include child changed/original/canonical IDs in the existing ES scope. Preserve pending-before-SQL, real PG commit, finite bulk, refresh, ready, and recover original pending operation on retry. Never clear a gate on an unverified failure or introduce another writer/cron.
- [ ] Add bounded structured stage timing around existing projection, bulk batches and refresh/ready, with operation-reference hash and action count. Do not put variable timing into immutable receipt hashes or log source bodies, tokens or DSNs. Persist via existing logs/cron evidence, not a new metrics platform. Report real measured current timings when an authorized run is available; otherwise explicitly label unavailable.
- [ ] Run new cases plus `tests/web_ui/test_kifu_incremental_catalog.py`, `test_kifu_catalog_standardization.py`, `test_kifu_search_publication.py`, `tests/cron/test_kifu_ingest.py`; inspect exact query/candidate bounds. Commit.
- [ ] Include one existing-pipeline regression preserving FF4 operation sequence, original `B+` and source attribution through incoming preparation/publication/API. Shared presentation handles them; do not rewrite SGF results or create another replay parser.

## Chunk 3: Review, production data and authorized scheduling

### Task 5: Integration and measured release

**Files:**
- Create `docs/operations/kifu-rank-hourly-consistency.md`.
- Create review and release evidence under `docs/superpowers/reviews/` / ignored `output/` as appropriate.
- Use existing Docker/RK3562 deployment workflow; preserve unrelated worktrees/changes.

- [ ] Fresh independent Astra max final code/data-integrity review after all targeted checks pass; fix findings and re-review until approved. Spec check may share the written plan but reviewer starts without controller history.
- [ ] Focused PostgreSQL transaction/lock/CAS/rollback test for the new repair and native parent/child publication before live data writes. Keep existing v1/v2/native/HTTP semantic-reimport regressions passing; no GPU or unrelated UI regression campaign.
- [ ] Run historical read-only prepare against both databases and inspect actual counts/Go sample beforeimages/refusals. Deploy compatible readers/receivers first. Apply only frozen reviewed manifests, verify all changed slots/canonical API/unchanged raw data and counts, retain guarded undo. No automatic hard deletion or data fabrication.
- [ ] Fetch/merge latest develop into feature, resolve, verify, commit/push feature; merge/push develop; update/push smartbox-software gitlink; deploy both servers and RK3562 exact artifacts. Retain original flags, memberships, identities, stage/state/old receipts, GPU/DB/MinIO and camera honesty.
- [ ] At actual 1024x600 RK Kiosk and representative Galaxy viewport, verify Go's previously missing historical samples, canonical professional display, an explicit amateur and a blocked/unknown case; source SGF/replay/B+ behavior remains intact. Use existing signed-in flow, no fake user history writes.
- [ ] Scheduling preference is pending an asynchronous user answer. If continuing pause, keep collectors/paid processing/transport unchanged and deliver tested code plus exact activation requirements. If restoring, enable exactly one TEST collector only after restoring approved restricted native transport and valid ES writer configuration in TEST publisher and PROD receiver. PROD does not collect independently. Do not spend paid model tokens or invent a budget merely to make the job run.
- [ ] Before resuming old five unfinished batches, inspect their frozen state and repair/retry the original operation; never reset publication keys/checkpoints or retranslate already frozen decisions. Run one authorized representative new/resumed batch, verify TEST→PROD same frozen package/API/search visibility and replay, and report whole-run vs ES-stage timings separately. If source/evidence/model/transport prevents success, report exact reason rather than “hourly working”.
- [ ] Final report states published/deployed commits, reviewed/applied counts, remaining unknown/conflict reasons, actual collector status, next-run schedule, measured timing or lack thereof, and retained backups. Do not equate a configured one-hour interval with a running collector.

## Review checkpoints and proportionality

Plan review max two Astra rounds per user instruction. Shared foundation first; parallel workers only after contract stability and disjoint ownership. Tests target semantic/data/concurrency/publication boundaries, not implementation mirrors. Reuse existing two DB tables, audit journals, CLI and search protocol; stop adding machinery once the three requested outcomes are evidenced.
