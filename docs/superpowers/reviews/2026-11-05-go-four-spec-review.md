# Go four fixes — independent spec compliance review

Reviewer scope: SDD spec compliance only. Read-only product review; no code-quality expansion, build, backend start, deployment, or additional state capture.

## Item 4 — 复盘首页「历史对局」字号

**Status: spec approved**

- Approved plan: `docs/superpowers/plans/2026-11-05-kiosk-home-section-heading-size.md`.
- Reviewed product range: `fb916f12516dd510080fb736a48a825dc206bc37..01ad13f662ca42f8f8bedfde391fedad39c9e925` in `/private/tmp/katrain-home-section-heading-plan-20261105`.
- Fresh commit diff and `git diff --name-only` confirm the only changed product file is `katrain/web/ui/src/kiosk/pages/personalGamesReviewed.css`. All additions remain under `.personal-games-reviewed`; the pre-existing local pagination container changes from 52 px to 46 px. No global or other-page style, data contract, component, production fixture, or user-data asset is added.
- The history heading is explicitly 22 px with `letter-spacing:0`, matching the existing 22 px archive heading reference. The existing section-height token is overridden locally to 30 px and the heading row uses centered alignment. The pagination adjustment is the necessary local geometry correction allowed by the plan and accepted by ROOT after the representative preview found a 6 px card crop; it does not reduce the 44 px controls.
- Reviewed the provided before/after computed-style artifacts at the same 1024 × 600 viewport, `large` type size, with search expanded. The after artifact reports 22 px type, 27.5 px line height, zero normalized letter spacing (`letterSpacingPx:0`; raw computed value `normal`), a 30 px label row, and the title fully within its row. No title/subtitle/count/action overlap is recorded. All three 74 px cards fit fully within the scroll viewport; pagination buttons retain 44 px height and the import entry remains visible.
- Independently viewed `/private/tmp/katrain-home-heading-side-by-side-20261105.png`. The two 1024 × 600 panels show the intended heading increase, a clear English subtitle and count, a usable search control, three complete history cards, pagination, and import entry. Different game content and the local fixture's engine notice are outside the CSS change.
- Focused source checks confirm the other first-level homepage title treatments recorded by the plan: archive 22 px; play section titles 20 px under its existing layout; training home 28 px; growth and settings group titles 22 px; course home headings 28 px with 22 px course names. Preserving these existing roles is consistent with the requested focused homepage check and avoids a site-wide heading redesign.
- Fresh `git diff --check` for the reviewed product range/file exits 0 with no output. Existing representative runtime evidence is sufficient for this local CSS change; no redundant build, test layer, or full-state regression was run.

No spec changes required for item 4. This approval covers the reviewed CSS item only; integration, independent final code review, and release remain ROOT's workflow.

No filesystem access, traversal, stat, or git-status pathspec was used for `data/kifu-album/`.
