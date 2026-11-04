# Kifu boundary pagination plan review

Round 1: **CHANGES REQUESTED** — one narrow-layout correction to the plan.

- The proposed component option, title/aria-label reuse, 22 catalog entries, same-query navigation assertions, and focused two-file test scope are appropriate. Kiosk already enables the boundary buttons. No backend or additional abstraction is needed.
- **P2: allow a minimal Galaxy-only narrow-layout adjustment.** `RAIL_TIERS` in `src/components/railStyles.ts` includes a 320px right rail. With edge buttons enabled, `compactPagination.css` requires at least 220px for five 44px buttons, 40px for five gaps, and 60px plus the total-page text for the position control: more than 320px even before rail padding. The form does not wrap and `BoardPageShell.tsx` clips horizontal overflow. The plan currently fixes the existing spacing and limits its final diff to exclude CSS, while its 1440×900 preview can miss this narrower regression.

Minimal plan correction: permit a localized, necessary fit/wrap adjustment in Galaxy's existing pagination wrapper while retaining 44px hit targets, icons, order, and handlers; keep shared/Kiosk styling unchanged unless evidence requires it. Add one quick overflow check with the Galaxy rail at its existing 320px minimum, without another screenshot suite or new permanent test harness. The existing 1440×900 screenshot and 1024×600 Kiosk check remain sufficient otherwise.

Reviewed only the plan and relevant existing UI/test/translation sources. No product code edited, tests rerun, protected data traversed, or server operations performed.

## Round 2

**APPROVED.** The revised plan closes the only finding with a direct-child `sx` wrapping rule on Galaxy's existing pager wrapper (`flexWrap: 'wrap'`, `minWidth: 0`, `maxWidth: '100%'`). It preserves the shared 44px buttons, gaps, DOM order, and Kiosk layout. The added measurement-only 320px-rail check covers the identified clipping risk without expanding the screenshot/test scope. No remaining material plan blocker.
