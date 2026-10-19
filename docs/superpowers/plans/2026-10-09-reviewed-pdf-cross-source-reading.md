# Reviewed PDF and cross-source Mandarin inputs Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Accept the two reviewed thesis-page Mandarin readings and the reviewed CWA/CWI same-person link through Chinese positive evidence version 2.

**Architecture:** Extend only the Chinese identity/reading dispatcher in `name_evidence.py`. PDF captures distinguish immutable HTTP bytes from extracted page text; default producer/native validation hashes the actual PDF file, while an already bound applied-ledger reader validates retained proof without filesystem access. Existing qualified source anchors, generated review, registry, empty target and NIKL gates remain authoritative.

**Tech Stack:** Python, existing JSON evidence contracts and pytest/SQLite fixtures.

## Decision and exact scope

The source-route decision is `/tmp/kifu-next5-mandarin-after615-root-20261009/source-route-decision-astra.md`, SHA `cbf0dd16bd96176fc67ef7af86c4262bad949a74cb6110ea997f647784f0e8f5`.

- PDF: 王學傳 / Wang Xuechuan, page 63, `왕쉐촨`; 趙之雲 / Zhao Zhiyun, page 56, `자오즈윈`. Original PDF SHA `fbd2a6d635607946a313d7b3e0707947549ac339645ea67682cb67a67efe996a`, 6,876,614 bytes. English document and `zh-Hant` name span are separate fields. Each name binds its already qualified TW owner preimage.
- Cross-source: 华伟荣 / Hua Weirong, `화웨이룽`, actual CWA CWA001091/Z07 row and CWI exchange table. An explicit link binds both complete captures, URLs, locators, owner and reading; independent `generated_review` signs its complete positive hash.
- Version 1, old30/NIKL, contrary/rule/shared-Japanese captures, null target and source-live/ledger checks retain their existing behavior. 4331 remains HOLD; 6552 uses its existing route. EN correction is separate.
- No source research, generalized PDF pipeline, new table, deployment, Git or remote data mutation is part of this implementation.

## Chunk 1: one bounded evidence extension

### Task 1: contracts and representative red tests

**Files:** Modify `katrain/web/kifu/name_evidence.py`, `tests/web_ui/test_kifu_name_candidates.py`, `tests/web_ui/test_kifu_name_batch.py`, and `docs/resource/kifu-name-source-registry.json`.

- [x] Add explicitly synthetic reusable unit fixtures for the PDF/file verifier and the two captured-source link; retain exact observed page/name/output expectations. Verify the actual supplied PDF and page hashes separately in the offline implementation receipt.
- [x] Add the two PDF positive tuples and one cross-source positive, with necessary wrong raw/text/page/excerpt/owner/capture-link and independent-review negatives.
- [x] Run the new focused selection to establish a meaningful red failure.

### Task 2: minimal implementation

- [x] Add a `pdf_text_extract` capture only for Chinese version 2: exact document URL/final URL/status/time, raw PDF path/SHA/size, tool/version/options/extraction time, 1-based page/text/UTF-8 SHA, original excerpt/locator, document language and named-span language. Pin this reviewed PDF and its two observed page/name tuples; reject mixed/unknown capture flags.
- [x] Read/hash the actual PDF by default. Introduce only an internal validation keyword for the immutable reader, after all existing bundle/research/candidate/creation-ledger checks. JSON cannot disable verification.
- [x] Permit a qualified TW `verified_chinese_display` source anchor only from this PDF version-2 path using the existing anchor shape and existing exact live source checker. The shared/default anchor validator and version-1 path remain unchanged.
- [x] Add `reviewed_cross_source` on reading, mutually exclusive with `profile_pair`, binding exact owner/Han/Latin, canonical hashes/URLs/locators of the actual CWA/CWI captures, concrete identity basis and empty unresolved conflicts. Retain truthful official/published-Go-archive roles and registered source checks.
- [x] Add only the exact Chicago thesis as a scoped reference in the next immutable registry version. Do not expand its meaning to official player authority.

### Task 3: native write and immutable read verification

- [x] Reuse the existing native bundle/apply fixture for one case per new route, including a qualified TW source before the PDF KO write.
- [x] Confirm missing/tampered actual PDF bytes reject before write, applied reader qualifies without an external capture file, and changed proof/research/source preimage rejects.
- [x] Run only the new selection plus representative existing v1, old30 and nonempty-target gates; expand only for an actual related failure.
- [x] Save actual input-byte/page/cross-source SHA checks, source diff and focused test result under `/tmp/kifu-reviewed-pdf-cross-source-impl-root-20261009`, then send frozen bytes to root for one independent finite review. Root owns subsequent real pending candidates and operational delivery.

This is the implementation slice delegated by root's parallel workflow; no further implementer or repeated plan/source review is created for this tightly coupled small change. No commits are performed in this task.

## Completed verification

- Initial new-input run failed all three cases at the old Chinese evidence version gate.
- Final focused candidates: **33 passed**, including the three v2 outputs, source/link negatives, explicit v1 rejection of v2 inputs, unchanged old30 objects and legacy/current rule-source pairs.
- Final focused native batches: **7 passed**, including both new routes, tampered PDF rejection before writes, applied immutable proof qualification after removing the external PDF, exact live TW source invalidation, existing v1 ledger/importer and nonempty-target gates.
- Offline validation used the supplied actual PDF bytes and actual CWA/CWI captures without new source searches. A fresh extraction matched both saved page hashes; exact output expectations were `왕쉐촨`, `자오즈윈`, and `화웨이룽`.
- Frozen implementation/test/source-schema receipts are under `/tmp/kifu-reviewed-pdf-cross-source-impl-root-20261009`. This source/schema check is not an actual candidate approval. Root owns the real TW source ledger capture, pending candidates, independent candidate approvals and native validate/dry-run.
