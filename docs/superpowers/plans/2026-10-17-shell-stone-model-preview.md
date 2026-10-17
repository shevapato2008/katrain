# 黑白碁石模型预览 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development. Follow the proportional review scope below.

**Goal:** Give the user a real, inspectable paired black/white stone model, then wait for visual confirmation before applying it to tutorial static boards and overhead 2D videos.

**Architecture:** Isolated Three.js preview using existing dependencies; reusable deterministic geometry/material module. No production entry imports it yet. White shell uses original procedural fine growth stripes, black models paired Nachiguro slate. Keep video camera overhead; oblique/side views only inspect model geometry.

**Tech Stack:** Installed Three.js 0.183, Vite, local browser screenshots, existing KaiTi admin theme.

## Chunk 1: Research and paired model preview

- [x] Inspect user screenshot and primary manufacturer photos: Kurokigoishiten about_go_stone and premium snow grade pages. Reference images are research only, never shipped as material textures.
- [x] Confirm physical reference: white diameter 21.9 mm, black 22.2 mm; black 0.3 mm thicker. Choose practical 32-size white 8.8 mm and corresponding black 9.1 mm, explicitly artistic approximations to shape/material rather than a measured replica.
- [x] Independent Astra Max plan decision: verify bounded model preview, approval boundary, realism and small-screen legibility criteria.
- [x] Create `katrain/web/ui/preview/shell-stones/stoneModel.ts`: closed smooth symmetric double-convex geometry, gently rounded equator, stable planar shell texture coordinates, deterministic material variants; nonmetallic stone material, soft directional highlight, restrained contact shadow. No concentric rings, exaggerated yellow marble or mirror-black plastic.
- [x] Create isolated preview entry/HTML/config under the same directory. Show top, oblique and side presets, both stones, actual 24/32/48 px board-size comparison, labels/symbols/inverse last-move rings, old/plain-white reference, light/dark contexts, gentle 360 ms placement example. Reuse palette and KaiTi; no giant redesigned application.
- [x] Build to `output/shell-stones-20261017/site/`, serve with stable local URL. Export a clean screenshot and reusable model/sprites if straightforward. Do not add a new rendering infrastructure or backend.

## Chunk 2: Proportional verification and delivery

- [x] One real browser pass at 1280×800: controls, geometry silhouettes, no WebGL errors, labels at actual sizes, screenshot capture. Reference/model same-size comparison and material notes.
- [x] Astra Max independent visual/spec review, then code-quality review of isolated files. Fix actual blocking issues and recheck those items only. Closed cross-context PMREM sharing by exporting sprites using the main renderer; final bundle `index-122UBzpN.js`.
- [x] Deliver paired model preview and sources. Clearly state not applied to TEST static boards/videos yet. User confirmation is the next dependency; no generation/deployment or DB writes during this preview.

Preview: http://127.0.0.1:9035/site/ . Reference/implementation/50% overlays: http://127.0.0.1:9035/materials-comparison.html . Independent review: `docs/superpowers/reports/2026-10-17-shell-stone-model-astra-review.md`.

## After visual confirmation (separate slice)

Reuse same approved model in overhead recorder, render transparent 2D sprites from same material for lightweight static boards (no RK3562 local WebGL requirement), preserve figure labels/replay coordinates/gentle placement/audio. Keep existing 3D assets as history while removing 3D generation from the current workflow. Build/regenerate only approved page samples and TEST deploy with bounded visual and code review.

## Research sources

- https://kurokigoishiten.com/en/pages/about_go_stone — shell vs Nachiguro material, stripe grading, actual diameters.
- https://kurokigoishiten.com/en/products/clamshell-go-stones-premium-snow-grade — macro surface and double convex thickness reference.
- User screenshot: `codex-clipboard-NzEVOH.png` — diagonal pearl-white fine stripes, soft gloss and board-size visual target.

## Acceptance

White retains visible curvature at 24–48 px without whitening out grain; black remains black with broad subtle highlights, no metal/mirror look. Both are centered circular under overhead projection and symmetric double convex from side. Stable variants do not shimmer between frames. Numbers, letters, triangle/cross/square and inverse last rings remain readable. All preview dependencies are local; preview has no privileged requests and changes no saved data.

## User decision during preview

2026-10-17: user asked why dimensions differ, then confirmed “好的，那就按照厂家说明走吧”. Preserve the manufacturer's physical black/white diameter and thickness proportions. The equal 24/32/48 px inspection strips compare legibility at a specified screen size; they are not a change to those model dimensions.
