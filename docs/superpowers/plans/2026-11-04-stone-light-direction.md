# Consistent Go stone lighting implementation plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development to implement this plan. Keep checks focused on stone rendering and deployment.

**Goal:** Keep the shell grain varied per stone while every stone on a board shares a fixed highlight and shadow direction in Galaxy and Kiosk.

**Architecture:** Production 2D sprites are rendered from the existing stone geometry at varied model angles under one fixed studio light. Canvas and SVG select a stable sprite per intersection and draw it without rotating the lit image. Real Galaxy 3D meshes continue rotating only their geometry/material under shared scene lights; recording sprites also stay unrotated at display time because their export already contains varied model angles. Board wood, grid, coordinates, hit targets, and overlays stay as they are.

**Tech Stack:** React, TypeScript, Canvas, SVG, Three.js, Vite, Vitest, Playwright.

---

## Chunk 1: Fix source and consumers

### Task 1: Fixed-light 2D sprite export

**Files:** `katrain/web/ui/preview/production-stones/export.ts`, `katrain/web/ui/scripts/export-production-stones.mjs`, `katrain/web/ui/src/components/board/assets/shell-slate/white-00.png` through `white-31.png`, `katrain/web/ui/src/components/board/assets/shell-slate/README.md`, `katrain/web/ui/src/components/board/stoneAppearance.ts`, `katrain/web/ui/src/components/board/stoneAppearance.test.ts`.

- [ ] In the exporter, keep the scene, camera, and studio lights fixed. Render 32 white sprites: white index `i` uses the existing shell material seed `i % 8`, and rotate only the mesh by `i * 2π / 32` before rendering. Black remains one unrotated sprite because its rotationally symmetric material has no grain. Update the export script's completion condition from 9 to 33 sprites.
- [ ] Export images using `node scripts/export-production-stones.mjs` from `katrain/web/ui` and register all 32 URL literals so the Vite build includes them. Preserve the original material recipe and lighting intensity.
- [ ] Add a focused test that the appearance exposes 32 stable white orientations, with coordinate selection stable across replay and resize.

### Task 2: Do not rotate lit 2D/recording images

**Files:** `katrain/web/ui/src/components/board/boardUtils.ts`, `katrain/web/ui/src/components/board/boardUtils.test.ts`, `katrain/web/ui/src/kiosk/shell/GoBoardSvg.tsx`, `katrain/web/ui/src/components/MiniBoard.tsx`, `katrain/web/ui/src/components/tutorials/SGFBoard.tsx`, `katrain/web/ui/src/kiosk/tutorial/OgsCourseBoard.tsx`, `katrain/web/ui/src/components/Board3D/StoneMesh.tsx`, focused existing tests beside these components.

- [ ] Remove runtime rotation from shared Canvas stone drawing and SVG `<image>` elements; leave labels and overlays untouched. Black always uses the same fixed-light sprite. White variation comes from the selected pre-rendered image.
- [ ] Remove runtime angle from `StoneMesh`'s `spriteTexture` plane only. Keep the 3D mesh's Y rotation, since it rotates actual material under shared lights. Keep the real 3D shell material's existing eight seeds (`variant % 8`) independent of the expanded 2D sprite count. Preserve scale, position, and opacity.
- [ ] Test Canvas/SVG/recording paths for image selection and absence of image-plane rotation. Verify 3D geometry still receives stable coordinate angle.

## Chunk 2: Review, release, deploy

### Task 3: Visual and build verification

- [ ] Run focused Vitest checks, `npm run build`, and `npm run build:smartbox-kiosk-2d` in `katrain/web/ui`.
- [ ] Check a dense Galaxy board and 1024×600 Kiosk board at the same viewport before/after. Verify black highlight direction is fixed, shell grain varies, white highlights align, and board geometry did not change. Check a Galaxy 3D board and a recording sprite path. Review resulting PNGs with image inspection. Each board must have internally consistent lighting; 2D and 3D view modes already use different studio/key-light placement and need not share identical compass direction.
- [ ] Independent Astra Max code/visual review; fix findings and repeat until accepted.

### Task 4: Integrate and deploy

- [ ] Fetch `origin/develop`, merge it into the feature branch, resolve conflicts, rerun affected checks, commit, push feature.
- [ ] Merge feature into `develop` and push. Update `smartbox-software/vendor/katrain` to the published develop commit; preserve unrelated smartbox changes; commit and push `main`.
- [ ] Deploy and verify TEST (`home-ubuntu`) and PROD (`ucloud-v100`) cloud services per `server-deploy` skill, then update only KaTrain on RK3562 from the published smartbox gitlink. Check service health, actual Galaxy/Kiosk asset URLs, and the published commit on each target. Do not interrupt an active device game.
