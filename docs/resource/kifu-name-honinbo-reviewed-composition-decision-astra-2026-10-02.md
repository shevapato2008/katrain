# Honinbo reviewed composition decision — 2026-10-02

**GO for a narrow `composed` decision and stored edition displays. HOLD approval/import of the 374 displays until the eleven rule records below pass independent review.** This implements the user's approved “拆解再翻译” approach and retains the full eleven-language release gate. This memo authorizes the implementation choice; it does not sign language rules or candidates.

Reviewer: `/root/oza_ua_display_decision_astra`, parent-configured `gpt-6-astra` / max, without runtime attestation. Inputs: [display preview](kifu-name-honinbo-raw-event-display-preview-2026-10-02.md), [ordinal research](kifu-name-honinbo-ordinal-source-research-2026-10-02.md), [approved bases](kifu-name-honinbo-corrected-final-candidates-independent-review-astra-2026-10-02.md), review runbook, validators, importer, database models, strict display/search and coverage code. All ten retained ordinal-response sizes/hashes match manifest SHA-256 `b62b7b82510aa070cd52443eb645a56123ca7d62d5cedd7b79c38ea8f890e337`.

## Decision and minimum implementation

Add `decision_kind: composed`, initially restricted to **raw-event edition + approved series base**. Generate and independently approve all **34 exact raw values × 11 languages = 374 stored names**. Keep the existing eleven base decisions and 1,617 identity links as dependencies. Conventional full-name claims still require observed exact names; generated base-name/transliteration claims retain their existing negative-search requirements. Composition asserts neither claim, so it needs no invented negative search for each number.

Using the existing `generated` branch would change its meaning or repeat irrelevant searches. Treating every composition as `conventional` would falsely attest publication. Request-time composition would bypass the existing exact-display coverage gate. A separate, tightly checked decision is the smallest clear path.

Use the existing raw-value/name and evidence tables: their decision columns are strings and evidence payloads are JSON; this path needs no new table or schema migration. Add a small edition renderer/validator with allowlisted operations and explicit locale parameters. No executable template expressions. Other components, unknown rules and unapproved series scopes fail closed. Future series can reuse the contract and grammar evidence, with separately approved base, series unit and finite raw scope; reuse never extends the Honinbo approval automatically.

## Eleven rule records: minimum evidence and finite gaps

Each language needs **one** rule record, not 34 independent name searches. It must contain:

1. The exact approved base-candidate/research hashes and series identity; source evidence that the raw number is a Honinbo edition. Keep `round_name` separate.
2. At least one retained target-language body showing the proposed ordinal construction. Where no applicable example exists, use an authoritative grammar/style reference covering the actual construction, plus an independent language review explaining its application. A Japanese source alone cannot establish Korean, Ukrainian or another locale's grammar.
3. Exact numeric spelling, unit, position, spaces, punctuation, agreement and capitalization transformations. Save URL, actual body language and its basis, actual capture time, body SHA-256, excerpt and any encyclopedia revision. Distinguish observed pattern, grammar inference and editorial choice. Shared source bodies may be referenced by hash.
4. A versioned rule, producer identity/time, independent reviewer identity/time, and approved rule-content hash. Review samples 1/17/34 plus every different grammatical case: English 2/3/11/12/13/21/22/23/31/32/33, French feminine first, and any case changes. Mechanically verify the complete 1–34 output table.

The supplied packet supports drafting the English prefix, Japanese `期` prefix, German dotted prefix and attested Chinese `期` usage. It contains **no approved eleven-rule artifact**. Choose compact Japanese **`第N期本因坊戦`**, resolving the research memo's spacing inconsistency. Choose `期` for this series' Chinese editions, explicitly retaining the competing `届` observation. These editorial choices do not approve the remaining grammar or the 374 outputs.

| Remaining language evidence | Finite completion requirement |
| --- | --- |
| `tw` | One Traditional Chinese body or applicable grammar source for `第N期`; Simplified Chinese evidence alone is insufficient for this rule record. |
| `ko` | One Hangul body or authoritative usage source supporting `제N기` and spacing. The captured Korean page's Japanese kanji do not establish that Hangul rendering. |
| `es`, `fr` | Evidence for the proposed ordinal's agreement with `edición/édition`, `del/du`, and French `1re`; record the exact chosen capitalization. The women's-series French example supplies only adjacent syntax. |
| `ru`, `ua` | Evidence for the numeric masculine ordinal and agreement with `турнир/турнір`; explicitly review lowercasing that leading common noun while preserving the proper name. |
| `tr` | Evidence for the numeric ordinal period and its use before the approved `Honinbo Turnuvası` base. |

These are seven language packets to complete, followed by independent approval of all eleven rules. No full-edition-name search across all 374 combinations is required. A failed fetch or absent grammar explanation leaves the affected rule pending.

## Candidate binding and tamper checks

Use a new bundle copy with a separately versioned composition section. Preserve the existing identity rule version and signed identity payloads when their inventory/catalog/context still match; do not change those fields merely to name the composition extension. Any real scope drift requires the existing refresh/review process.

| Record | Required binding |
| --- | --- |
| Finite scope | Exact 34 raw spellings; one integer edition per spelling; series owner/ref; frozen inventory/catalog; complete occurrence IDs and existing scope/context hashes; independently reviewed decomposition. No substring match or unrestricted ordinal regex grants membership. |
| Locale rule | Series owner, locale, approved base-candidate hash, evidence hashes, renderer/version/parameters and independent approval. Hash the rule content separately from its approval envelope; candidates bind the complete approved record. |
| Each candidate | Exact raw owner/value, locale, display, `decision_kind: composed`, rule version/hash, base-candidate hash, integer edition and raw-scope hash; actual producer/reviewer provenance. Keep `research_sha256` empty and validate dedicated composition evidence, rather than fabricating a conventional/negative research record. |

The validator resolves these references, checks the base's approval and language, rerenders every display byte-for-byte, and rejects missing/extra/duplicate members, altered dependencies, foreign series, unsupported components and collisions. Extend both within-bundle and live cross-bundle collision checks to `composed`. Require all eleven decisions for every declared raw owner in this cohort.

The current parser classifies these strings as **`unclassified_pending`**. Preserve that conservative category and independently approve the edition decomposition. Permit `composed` there only with the complete composition proof. Do not relabel them `formal_event_candidate`: the current strict-display branch for that category requires **Oteai** identity. No parser-wide relaxation is needed.

Review the eleven rules and 34 mappings once; an independent source reviewer can then approve a whole mechanically checked 374-row artifact. A separate binder captures the current raw owners and full name-row preimages: explicit null only when absent/new, otherwise the complete row hash. Preserve source authorship and bind source-candidate/capture hashes. An independent final reviewer verifies the bound copies after capture, signs each exact row, and recomputes member, candidate, dependency and bundle hashes. This is a bounded batch review, not 374 separate research assignments.

## Stored display, coverage and rollback

The importer must retain the approved rule/dependency payloads in existing evidence JSON, with resolved series ID and base evidence ID/revision as derived audit metadata. Apply base dependencies before composed names. Do not rewrite signed symbolic candidate objects when resolving IDs.

Strict display, search and coverage must share the same eligibility check: an approved raw owner, a verified exact locale row with matching independent evidence/revision, the bound approved series identity/base, and the album's matching series link. Recognize `composed` only for raw-event names. An absent base, changed base dependency, wrong/unlinked series, missing language or pending row remains a coverage gap; the approved core alone cannot fill it. Reuse the existing page-batched queries, adding only the needed binding fields/checks. No network access, translation, renderer execution or per-album evidence query belongs in the request path.

Retain atomic import and the existing change journal. Undo only this batch's touched rows/links, in reverse dependency order, with complete after-image comparisons; preserve later edits and report conflicts. If bases/links were installed by a separate earlier batch, this composition batch's undo must leave them intact. A dependency removal/change must fail closed in strict display. Original SGF, raw event spelling, dates, rounds and player metadata are outside this batch's write boundary.

## Next implementation slice and gates

Implement the composition contract, pending 374-row expansion, validator/importer evidence retention and shared strict-display eligibility. Complete the seven evidence gaps and obtain the eleven rule approvals before signing production candidates. Keep the current production strict-mode release gate unchanged.

Focused tests must cover: all 374 deterministic outputs and grammatical branches; rule/base/scope/hash/series tampering and missing locale; independent signatures and chronology; stale/null preimages and live collisions; parser-category preservation; approved/pending/missing/mismatched-dependency API, search and coverage agreement; bounded query count; atomic apply, repeat apply and conditional undo. Preserve the existing generated-negative and conventional-source regression checks. After adding `test_kifu_name_composition.py`, run:

```sh
pytest -q tests/web_ui/test_kifu_name_composition.py tests/web_ui/test_kifu_name_candidates.py tests/web_ui/test_kifu_name_batch.py tests/web_ui/test_kifu_name_api.py tests/web_ui/test_kifu_name_coverage.py
```

Then use one frozen, fully approved artifact for the required current-state dry-run and isolated production-copy apply/repeat/conditional-undo rehearsal. Require `ready=true`, `write_ready=true` and **17,787/17,787 approved Honinbo event slots** across eleven languages. Both player slots remain part of the separate full-coverage accounting. Production release still requires every in-scope black/white/event slot × eleven languages to pass, with zero pending or unsupported raw fallback. This memo changes no code, signed artifact or database, and approves no production release.
