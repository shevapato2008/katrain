# Recognition uncertainty markers

> Use superpowers:subagent-driven-development and a bounded Astra Max review.

**Goal:** Make existing recognition uncertainties visible at current page, figure and reliable full-board point level, including evidence-based suspected false positive/negative stones.

**Architecture:** Frontend only; derive a small display model from immutable candidate raw_result and existing figure metadata. Retain existing theme, navigation, APIs, manual review and media permissions. Reuse SGFBoard with optional attention markers, plus a focused evidence list.

- [x] Prefer explicitly applied candidate; if current origin is ambiguous, label evidence as original candidate reference and render markers in original-candidate comparison rather than falsely identifying edited current points.
- [x] Parse known inferences/uncertainties/issues/unknowns. Only valid explicit full-board cell locates a raw item; at-local-only/null/invalid coordinates stay figure-level. Use unknown_stones.point when already in the strict global payload.
- [x] Distinguish color, number inference, annotation uncertainty, explicit stone-presence false-positive/negative, and unclassified/unlocated evidence. No forced FP/FN for black/white or no-mark/triangle ambiguity.
- [x] Current-page/figure badges, thin ring plus ! without hiding printed move numbers; evidence list and board markers select each other. Keep original-region frames absent. Existing filters support book navigation; do not claim all-page aggregate coverage without data.
- [x] Human review state remains server-owned and separate from historical recognition uncertainty. No automatic review, save, modification, new schema or OCR/model call.
- [x] Focused tests: global cell vs local at, unlocated issue preservation, FP/FN evidence conditions, source mismatch/edited coordinates fallback, duplicate-point grouping, real p014-f06 unknown color and p013-f05 number inference.
- [x] Independent Astra Max SPEC/CODE and one representative same-size actual TEST visual; deploy TEST console, preserve current diagram/reviews/media, provide real examples.
