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

## Review amendments
- AppRouter routes the public home experience into GalaxyApp, whose normal routes are nested under MainLayout. Kiosk routes remain excluded. Verify this route mapping before editing.
- Use a 100vh fallback with 100dvh where supported. Keep the content row flex:1/min-height:0 and the footer flex-shrink:0.
- Footer height is min-height:28px rather than a hard height. Keep one line with safe hidden overflow and text ellipsis. Verify 320px width and 200% text zoom.
- Automated checks assert text, href, target="_blank", and rel. Visual checks cover home, a board route, expanded sidebar, long content, desktop viewport, and mobile viewport; confirm the main region still scrolls.
- Before deployment, record the current container image digest. After deployment, confirm the new image identity, HTTP status, visible filing text, and final link in a real browser.
- Rollback restores the recorded immutable image digest, then rechecks HTTP and the page.

## Narrow-screen correction
The filing number must always remain fully visible. Desktop may use one line; narrow screens and enlarged text may wrap and grow the footer height. Do not use ellipsis. The page must not gain horizontal scrolling.
