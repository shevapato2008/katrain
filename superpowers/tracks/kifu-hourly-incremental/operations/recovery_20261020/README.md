# One-off corrected72 recovery — 2026-10-20

Archived exact reviewed operator scripts; these are not scheduler entry points.
The normal hourly job and default scheduler are unchanged. Root owns explicit
execution, actual recovery receipts and subsequent unpause. Importing/running the
paid review script performs real calls; this archive step only parsed its AST.

## Fixed incident scope

- Original packet: 72 games / 18 decisions, publication key
  `19x19-recovery-a5425ac6c5b3d96d9bc23d3b`; canonical SHA
  `ae8fd9d9f9f4a0bde3ea72e20b74c64b0b3e041848dbb5f50d73a3b7d935e019`.
  Original packet file SHA:
  `70bd7d0936ae9bef18762f6d4fa8f1322aa93d10d3b0c3baea50e63de3de70a3`.
- Exact sorted source-ID/raw-SGF-hash/canonical-SGF-hash membership SHA:
  `0404084ef2ed16ae305bf67cd29896d2851944d96a0ac4fb1079219fb56702ef`.
- Actual native TEST undo: outer batch 880, children 881/882, all `undone`;
  actual undo receipt reports `reverted: 461`. The separate
  `../recover_frozen_event_semantics.py` preserves old TEST publication and
  verification receipts while registering the corrected package.
- Only decision indices `[1,2,7,8,9,11,12,13]` are corrected; the other ten
  decisions and all 72 games remain unchanged. The exact curated input is
  `curated-event-corrections.json`, SHA256
  `31da8dd74851959cf838c35c7d8e5a21f9d5f46227622c89e1a1479e27668efb`.

## Files and execution boundaries

- `review-eight-event-corrections.py`: final v3 bounded real Qwen producer/reviewer
  operator, using the existing daily ledger. Root reported all eight actual
  approvals and daily ledger 69549 tokens at archive time.
- `resume_cached_test.py`: requires paused B, no active run/pending command, the
  corrected durable queue and real old native undo. Uses existing `resume_batch`,
  native publication, complete five-language API verification and reconciliation.
- `native_cached_prod.py`: receipt-only by default; explicit `--publish` permits
  a single native attempt after actual TEST proof validation. Native guards stay
  intact. The pinned read-only A SGF cache SHA is
  `b3d4ae68d0994c3c6b9032e72ea19f8ea1770d0817446da57a3b3fb1cb049a8a`
  (176539 entries); cache bytes are deliberately excluded from this archive.
- `mac_bridge.py`: explicit private management-SSH relay. Reads the actual PROD
  receipt before its one possible write; never retries an uncertain write.
  Host/container/socket paths are incident-specific, not portable defaults.

## Review and archive checks

Existing independent Astra reviewed and APPROVED the actual four scripts,
including final Mac SHA `ffbae147ccd5eedabf2410504fb0d3324014d5d61d6e7229db1a8e8c2401f08e`.
Source bytes were copied unchanged and checked against `SHA256SUMS`; all four
Python files passed AST parsing only. No script was imported or executed by the
archive task. No publication or recovery success is inferred from these checks.
Actual execution evidence remains root-owned outside this source archive.
Credentials, cache bytes, private error logs and complete frozen packets are
excluded. `SHA256SUMS` records this README and the five exact archived inputs.
