# Kifu source standardization — independent ASTRA/MAX code review

**Decision: APPROVED, including the narrow identity-source follow-up below. Both P2 findings below are fixed and independently verified. No outstanding P1/P2 finding remains in the reviewed metadata scope.**

Reviewed the settled working tree on `feature/baipu-physical-history-20261103` against `9e83f1ad5eaf61f354b71bd6e8bb3dab28717531`, the approved source-standardization plan, its approved round-2 review, and the three independent result/rank/dedup investigations. The separately approved physical replay and account-history changes are excluded; shared kifu consumers were reviewed only for the metadata changes and their interactions.

## Closed P2 — New conflicting historical evidence could bypass a frozen rank manifest

Location: `katrain/web/kifu/source_rank_repair.py`, historical preparation and `_live_preflight`.

The original manifest froze only the chosen professional counterpart. In an isolated SQLite reproduction, preparation selected a same-operation, same-date, same ordered-player `7p` starpoint counterpart for legacy `7d`. Adding a matching starpoint `7d` counterpart before apply made a fresh preparation correctly return unspecified `7段`, but applying the earlier manifest still wrote `7p`. Rechecking only the selected record did not protect the conflict decision.

The final manifest freezes the complete relevant historical counterpart cohort, including source membership and every member's beforeimage. First apply obtains writer locks, uses a fresh PostgreSQL READ COMMITTED view, and compares the live cohort before writing any journal or snapshot. Existing applied overlays remain frozen rather than being recomputed from later profiles or new counterparts. Standalone and combined writers use the existing advisory-lock ordering.

Independently reran the exact reproduction after the fix: apply refused with `rank historical counterpart cohort preimage changed`, with zero batches and zero snapshots written. The final focused tests also cover changed nonselected peers, newly trusted source membership, changed approved identities, old incomplete manifests, and PostgreSQL source-update/new-album blocking.

## Closed P2 — Display dedup broke HTTP verification of canonical-equivalent native imports

Location: `katrain/kifu_ingest/sync.py`, `_validate_display_duplicate` and `verify_album_api`.

Native import already permits equality of the complete canonical SGF while retaining the original stored bytes and a separate `album_sgf_sha256` in the receipt. The first duplicate-proof validator compared its raw stored-SGF digest directly with the manifest's canonicalized content digest.

The independent reproduction used actual native publication and the real detail reader: a stored source retained a trailing newline; a fresh canonical-equivalent source reused its original album. HTTP verification passed before dedup, and the unchanged native receipt still replayed afterward, but HTTP verification then failed with `album display duplicate proof is invalid`.

The fix binds the journal's raw digest to the fetched original detail bytes and retains that digest in the duplicate checkpoint. The existing complete canonical-SGF/manifest check remains separate and unchanged. The public canonical card is still checked against its own retained SGF digest, while original source IDs, metadata, ranks and receipts remain authoritative. Both actual HTTP variants pass in the independently run final suite. A separate scratch workflow also passed real native **v2** publication → semantic dedup → exact unchanged receipt retry → rank-aware HTTP verification.

## Follow-up — Display-derived identities require their source reference

The subsequent live census exposed a mismatch with the approved investigation dictionary: `_identities` included `KifuPlayerName` rows marked `verified` even when `reference_url` was NULL. That could grant an otherwise missing player identity or introduce an unsupported competing identity. The resulting 195-group artifact was discarded without applying it.

Independently reviewed the narrow correction: display-name observations now require both `status == "verified"` and a non-NULL `reference_url`. Canonical names, registered aliases and existing player FKs retain their prior rules. The same restricted index serves rank historical evidence through the existing helper; no new identity inference was added.

Independent follow-up verification: **5 focused tests passed in 0.51s**, covering the new unreferenced-display refusal, source-first roundtrip, stable starpoint selection and approved exact rank aliases. An isolated scratch check additionally confirmed that the previously excluded missing-FK pair becomes eligible when its verified display name receives a reference. Approval stands for this corrected code; the replacement live manifests and their actual eligible counts remain subject to separate data review.

## Other reviewed boundaries

The final implementation retains original SGFs, raw ranks, source rows, v1 snapshots and current-profile facts. Source-normalized overlays require exact album/side/source-link/path/hash/raw binding plus an applied publication journal; invalid overlays fall back to truthful unspecified dan. Explicit amateur and kyu observations are preserved, and the reviewed Yoda exception remains bounded.

Reviewed the final specification-review corrections as well: raw SGF date/player/explicit metadata must agree with the claimed evidence; conflicting approved identities are refused; physical original source-link IDs are frozen; and canonical selection requires the original starpoint source before its stable-ID tie-break. Dedup pointer/source writes and undo retain complete precondition checks. Native imports retain the original source owner and aggregate provenance with `reviewed_same_game`. The analysis endpoints' exact-SGF restriction is unchanged.

Both library UIs, their report/replay headers, and the Kiosk library-import dialog use the shared rank presentation. Bare wins retain a known winner without inventing resignation; unsupported numeric suffixes remain raw. Generic user-strength semantics and the existing Kiosk resignation wording remain intact. The known pre-existing Galaxy selected-card request-count failure was not treated as a metadata regression.

## Independent verification

- Final catalog-standardization suite with disposable PostgreSQL enabled: **40 passed in 7.16s**, including apply/retry/undo, source/identity/date drift and both actual HTTP replay variants.
- Source normalization/repair, native rank publication, snapshot API and the final CLI artifact-repeat check: **83 passed in 8.68s**. After the last focused rank additions, reran the complete final source-rank-repair module with disposable PostgreSQL enabled: **35 passed in 2.57s**.
- Shared result/rank/list helpers, both report pages and the final import dialog: **51 passed across 6 files in 3.89s**.
- Exact stale-cohort scratch reproduction refused atomically; independent actual native v2 publish/dedup/retry/HTTP workflow passed. `git diff --check` passed.

Only this review document was added to the repository by the reviewer. Product fixes and regressions were made by their implementation owners and re-reviewed after settling. Tests used isolated SQLite databases or disposable PostgreSQL schemas; no production/developer database, device, deployment, commit, or `data/kifu-album/` filesystem access occurred.

This approves the code. Final live manifests must use the settled cohort/source-row evidence format and receive their separate data review. Production application still requires the approved plan's fresh deployed-writer/read-model compatibility check; this review does not claim a production repair or release.
