# Chinese-first kifu identity catalog implementation plan

> **For agentic workers:** Use `superpowers:subagent-driven-development` for independent tasks. Keep checks proportional to the production data risk.

**Goal:** Classify every raw player and event value in the 173,025-game library, assign stable IDs and Chinese default names to confirmed people and tournament series, then translate those entities in frequency order without requiring an individual game link.

**Architecture:** Preserve the original SGF metadata on `kifu_albums`. Use the existing `kifu_raw_player_values` and `kifu_raw_event_values` tables for a complete, repeatable inventory and review decisions. `kifu_players` holds confirmed people; `kifu_events` holds competition types such as 应氏杯, and a new edition table holds a separate ID for 第1届应氏杯, 第2届应氏杯, etc. Rounds remain attributes of games, not IDs. A raw value may remain pending with its own raw ID when identity cannot be established; it must never be silently assigned to a person or competition merely because the strings look similar. Name completion and album foreign-key completion are separate metrics.

**Tech stack:** Python, SQLAlchemy, PostgreSQL, pytest; current inventory format 2 (also accept compatible 3/4 all-scope snapshots) and existing kifu identity code.

**2026-10-04 status:** The full raw-value inventory and reversible parsing in Chunk 1 are applied to TEST and PROD. The additive edition schema in Task 3a is installed, with no unverified edition assignments. The [standalone report](../../resource/kifu-preprocess-report-2026-10-04.html) lists all 7,251 player spellings and 50,223 event values from 173,025 games, plus provisional groups and current catalog IDs. Identity review, Chinese canonical names for every entity, verified merges, album links, and five-language display in Chunks 2–4 remain open. The 876 existing player IDs currently cover 3,242 of 346,050 player slots (0.94%); 22 event type IDs cover 1,057 of 173,025 games (0.61%). Raw staging coverage must not be presented as identity coverage.

**2026-10-04 review policy update:** Verify each player identity and Chinese canonical spelling against a relevant Wikipedia article or a Go association/academy roster; record the exact URL and any ambiguity before merging aliases or linking games. Event display names may be translated directly from the preserved EV string or parsed core, including sponsor names. Keep year, edition, stage, round, and original EV recoverable. Direct display translation does **not** itself prove two EV strings represent the same competition type or edition. Program labels, generic descriptions, and archive labels remain separate from competition identities. For the first batch, prioritize high-frequency names; report translated display coverage separately from verified identity coverage.

**First review batch:** [Source-backed player and direct event translation review](../../resource/kifu-name-review-first-batch-2026-10-04.md) examined 21 high-frequency people and 30 event cores. Four source-checked people without catalog rows received Chinese canonical IDs in TEST and PROD; PROD now has 880 player IDs. A pinned set of 599 raw English EV strings received Chinese `review` translation drafts, covering 20,153 games. These drafts are not approved display names and do not increase album FK coverage. The remaining player aliases, person-ID collisions, event identities, editions, and five-language promotion still require separate work.

---

## Chunk 1: Full raw-value inventory

### Task 1: Player raw values

**Files:** `katrain/web/kifu/name_parse.py`, new `katrain/web/kifu/catalog_preprocess.py`, focused `tests/web_ui/test_kifu_catalog_preprocess.py`.

- [ ] Read the pinned inventory, count all 346,050 black/white slots, and reject incomplete or duplicate inventory entries.
- [ ] Upsert all distinct non-null player spellings into `kifu_raw_player_values`, preserving original text, slot count, parsed base name, embedded rank, category, and parser version. Re-running must be idempotent.
- [ ] Do not assign a person ID for placeholders, corrupt data, ambiguous spellings, or a mere transliteration guess. Report each category and its slot count.
- [ ] Run focused parser and idempotence tests.

### Task 2: Event raw values

**Files:** `katrain/web/kifu/name_structure.py`, `katrain/web/kifu/catalog_preprocess.py`, `tests/web_ui/test_kifu_catalog_preprocess.py`.

- [ ] Upsert every distinct event value, including a recorded empty/null category, into `kifu_raw_event_values` with count, parsed series core, lossless component spans, and review status.
- [ ] Keep year, edition, season, round, and game number separate from proposed series name. Generic descriptions, program labels, and corrupt values receive a raw ID but no tournament ID.
- [ ] Group proposed series cores into a frequency-ordered review queue; do not treat all 50,223 spellings as distinct tournaments.
- [ ] Run focused structure and idempotence tests.

## Chunk 2: Confirmed Chinese entity IDs

### Task 3: Catalog decisions

**Files:** `katrain/web/kifu/catalog_preprocess.py`, a small curated decision input under `docs/resource/`, focused tests.

- [ ] Produce a dry-run decision report from existing confirmed catalog and aliases, with collision and dirty-canonical exceptions. Keep existing reliable IDs stable.
- [ ] For each newly confirmed person or competition type, create one `kifu_players` or `kifu_events` row with a Chinese canonical name and a stable ID. Store approved alternate spellings as aliases; keep ambiguous raw values pending.
- [ ] Correct existing non-Chinese or contaminated canonical names only with an explicit old-value preimage and reviewed Chinese replacement; do not bulk rewrite old IDs by heuristic.
- [ ] Record approved raw-to-entity mappings separately from album FKs. A same-name collision must remain visible in the review report.
- [ ] After all raw names and event cores are classified, rerun a whole-catalog duplicate-candidate report using Chinese canonical names, known aliases, rank-stripped player names, and event series cores. Review every candidate before merging: identical spelling alone cannot prove that two people or two tournament series are identical.
- [ ] Assign confirmed spelling variants to one existing entity ID where possible. If the review actually finds two entity IDs for the same person or tournament, handle that specific pair with a preimage-checked transaction and backup; otherwise do not build a generic merge system. Keep uncertain candidates pending. Game-record deduplication remains a separate step.
- [ ] Test one historical rank variant, one foreign-language alias, one homonym, one bad value, and repeat execution.

### Task 3a: Competition editions

**Files:** `katrain/web/core/models_db.py`, `katrain/web/core/migrations.py`, a focused migration, `tests/web_ui/test_kifu_name_schema.py`.

- [ ] Add `kifu_event_editions` with its own primary key, competition-type FK to `kifu_events`, edition number or label, and year/season when known. Keep the original raw EV text and separated round in the raw-value record.
- [ ] Add a nullable edition FK to albums. Existing `event_id` values remain competition-type IDs until each historical record is reviewed; do not invent editions from unsafe strings.
- [ ] Uniqueness is scoped to a competition type and a verified edition key. A year alone may be insufficient where multiple seasons or events share a year.
- [ ] Test two editions under one type, multiple rounds under one edition, and an unresolved edition with a NULL FK.

## Chunk 3: Five-language names and display

### Task 4: Decouple names from album links

**Files:** `katrain/web/kifu/name_candidates.py`, `katrain/web/kifu/name_batch.py`, `katrain/web/kifu/identity.py`, focused existing tests.

- [ ] Permit independently approved five-language names for a confirmed player/event ID even when its album FK count is zero. Retain the source evidence, owner preimage, collision checks, and transactional import.
- [ ] For a null album FK, resolve only an approved and unique raw-to-entity mapping for list display and search. Never write a game FK as a side effect of showing a name.
- [ ] Leave ambiguous cases on the documented fallback. For locales outside `cn/tw/jp/ko/en`, use English as already specified.
- [ ] Run focused importer, resolver, and API tests.

## Chunk 4: Deployment and progress

### Task 5: Apply safely

- [ ] Pin a fresh inventory checksum and dry-run the raw-value ingestion and catalog decisions against TEST, then apply and compare totals with 173,025 games / 346,050 player slots.
- [ ] Repeat on PROD after TEST matches. Record counts for raw classified values, confirmed player IDs, confirmed event IDs, verified five-language entities, visible game slots, and unresolved exceptions separately.
- [ ] Continue high-frequency entity research with three independent research agents; upload each five completed player names together. Event names follow the same Chinese-first catalog.
- [ ] Run one representative list/search/language-switch check. Do not report album-link coverage as name-translation coverage.

**Release rule:** Data and UI claims must distinguish classified raw values, confirmed entities, verified localized names, display coverage, and verified game associations.
