# Next16 execution helper review

2026-10-09 — **PASS: no important blockers remain in the revised helper scope.** This is a code review result, not execution approval.

Reviewed exact bytes:

- `next16-inner.py`: `222c33ea87bf03ea732584fc72fb4d89b5a6cb6b034b4d57487b4cb10565e534`
- `next16-run.py`: `0581772bfaa085f2ff60a00099d95fe50ac8b04f8a32968c1a8383063f5eb6be`

The apply path calls the existing CLI and native `apply_bundle`. Its wrapper enters the original `_locked_write` before checking captured preimages and yields that same connection; the native transaction, table/advisory locks, validation, complete target-name CAS, writes and undo ledger remain in force.

The revised helper restores the prior narrow legacy-ORM adapter before native reads: a read-only connection inspects the physical schema, verifies `list_hidden_reason` is `String(64)`, and adds that column to the in-memory mapping only when absent. It issues no schema change and does not map `event_edition_id`. This preserves the batch-594 format-4 inventory reader context: `_selection_supplement` delegates to ORM-based `verified_selection_rows`, whose historical proof checks compare complete mapped album images and column sets. The native `ALBUM_COLUMNS` tuple is already imported before the adapter runs.

Before the first write, the guard compares every captured owner, all 64 complete name rows, all 64 owner evidence rows, aliases, and the source registry. It also compares the entire physical `SELECT *` album scope, with SGF content represented by SHA-256, checks columns, and requires exactly 158 albums / 160 owner slots. Native catalog and inventory checks still run afterward under the same locks.

Both saved read-only captures identify applied batch 594, contain 16 owners with four qualified languages each, and have absent target rows. Baseline and verification use the qualified reader: 64 old qualified names must remain, all 16 exact candidate names must qualify, total qualification must reach 80, and all 16 owners must have five languages. Existing name hashes and full scoped album hashes are compared with baseline.

Packaged artifact hashes and each capture's immutable image ID were checked. Assembly retains reviewed source/CAS fields and native bundle validation. The actual bundles contain 16 approved conventional decisions, existing owners, and no album-link writes. The runner and inner helper require root's approval bound to the manifest and bundle hashes; the runner inspects the immutable image ID, and the inner helper rejects disabled assertions. Captured Docker output is not echoed wholesale; emitted failure diagnostics redact URL credentials.

Validation performed: syntax parsing of all four helpers, including the revised inner helper; local capture and package integrity checks; source inspection of native locking, CAS, format-4 adapter, and qualified-read paths. No database, Docker, cloud, Git, signing, or apply action was performed. Root must regenerate the manifest/transport with the revised hash above before creating execution approval; the previous helper pin is obsolete. Native TEST dry-run/apply/verify and then PROD remain execution steps for root.
