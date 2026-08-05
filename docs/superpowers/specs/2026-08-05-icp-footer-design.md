# ICP footer design

Date: 2026-08-05

## Goal
Display 京ICP备2026047949号 at the bottom center of the ModelStella website and link it to https://beian.miit.gov.cn/.

## Scope
Change only katrain/web/ui/src/galaxy/components/layout/MainLayout.tsx. Do not change game logic, APIs, login, kiosk routes, or Nginx response content.

## Layout
Use a 100vh vertical root. Keep the existing sidebar and main content in a flex:1, min-height:0 horizontal row. Add a 28px non-overlay footer after that row. The footer uses the current dark theme, centered low-contrast text, and no wrapping. The anchor opens a new tab with rel="noopener noreferrer".

## Acceptance
- Filing number is visible on the home page and Galaxy routes.
- The link targets the MIIT filing system.
- The footer does not cover the board, controls, or sidebar.
- Existing routes render and the production frontend build passes.
- The updated Docker service returns HTTP 200 and browser verification shows the footer.
- Roll back MainLayout.tsx and rebuild the prior image if tests or visual checks fail.

The public-security filing number is out of scope until it is issued.
