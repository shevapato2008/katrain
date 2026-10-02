# Honinbo v2 evidence-producer provenance addendum (2026-10-02)

This addendum records who produced the 34-group evidence proposal and what was checked. It is not an identity approval or candidate signature.

- Producer task: `/root/honinbo_v2_bundle_prep_luna`
- Configured model/reasoning: `gpt-6-luna` / `high` (parent task configuration)
- Actual `produced_at`: `2026-10-02T15:07:47.700496Z`
- Protected addendum: `/Users/fan/.local/share/kifu-name-audit/2026-10-02/honinbo-v2-evidence-producer-addendum/honinbo-v2-evidence-producer-addendum.json` (mode `0600`), SHA-256 `35072ea5407b6ac81d02b94601d8adf36efa4bc937f635b12ac48130fbd49257`
- Source-evidence manifest SHA-256: `c789ed607941d0a3a7631c22d04ed7badb555c58869c8e3ad8db79f0812227cf`
- Exact pending link-prep file SHA-256: `ce1aded31526c047abc9ac44bff2a43921d0dd3b6c286082801d20ea1168a584`; declared link-set SHA-256 `d77b853f0394880dd5be20d512610540ba79d88792b701f21f9461f97a6a35d2`

The proposal covers 34 exact raw event values and 1,617 album links. I checked all 1,617 mapped CWI archive members against the retained HTTPS archive response: member SHA-256, SGF root `EV`, and root `RO` matched with zero mismatches. The pinned inventory contains 268 raw event values matching the case-insensitive `honinbo` substring, totaling 3,321 rows. Of these, the 34 proposed values cover 1,617 rows; the other 234 raw values / 1,704 rows are excluded from this proposal without an identity conclusion.

The link membership/path mapping and series adjudication originate in prior pending artifacts/reviews; I did not re-query production or independently approve individual game identities. The source responses were fetched after the draft's `2026-10-02T14:22:12Z` freeze. Sol must attach this producer provenance, freeze again later than `produced_at`, recompute all 34 scope hashes, and record a separate real reviewer signature. No database, SGF, previous bundle, signed candidate, or research artifact was modified.
