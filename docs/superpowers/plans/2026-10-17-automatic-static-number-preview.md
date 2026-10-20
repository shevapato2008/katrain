# Automatic static diagram number preview

> Use superpowers:subagent-driven-development; focused independent Astra Max review.

**Goal:** Apply the user's latest rule: numbering validation runs automatically; valid static diagram numbers immediately enable step navigation without a manual build/confirmation prerequisite.

**Architecture:** Reuse the pure numbering validator and existing controls. Keep a static numbered preview separate from a genuine validated replay, server data and media timing. Preview shows only known source stones and marks, never fabricating missing moves or off-page stones; a genuine replay retains the existing capture-aware rules.

**Scope:** Frontend only in existing console worktree. No new backend endpoints or schema, no book rewrites or automatic manual approvals.

- [x] Extend pure playback view to return a separate static-number preview when there is no complete replay and numbering passes. Unnumbered stones/unknown points/letters/shapes remain visible from the start; numbered stones are revealed in consecutive numeric order with actual step count, arbitrary starting number and either first color.
- [x] Automatically recompute from current figure/draft on load, edit, undo/redo and figure switch. Missing/duplicate/nonpositive/unsafe numbers, same-color adjacency, numeric marks on empty/unknown points disable static navigation and show the reason. No numeric labels is zero playback steps, not a numbering error.
- [x] Enable initial/previous/next/final/progress for valid static numbered previews; use distinct honest label `按原书编号预览` and never claim a verified full replay, synthesize unrecorded captures, persist preview moves, approve content or unlock media timing.
- [x] Retain explicit complete replay behavior including capture/pass/reuse/reverse snapshots, independently of missing printed labels on captured stones. Keep existing save/CAS/manual approval behavior.
- [x] Focused tests: initial real example1032 1–10 automatic navigation, arbitrary number/white first, static invalid disabling and edit fixes, switch/reset, zero-number initial-only, true capture replay unchanged, preview excluded from media sync.
- [x] Astra Max checks latest semantics and code; resolve blocking findings. Build/deploy only TEST console, preserve existing DB/review/media; check actual 18012 controls without writes and provide same direct link.
