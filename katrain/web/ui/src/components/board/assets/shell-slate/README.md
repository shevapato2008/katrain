# Shell / slate production stone sprites

These 33 PNGs are rendered from the repository's authored model geometry and
photo-free procedural material in `src/components/tutorials/stoneModel.ts` using
`scripts/export-production-stones.mjs`. The corresponding geometry and dimensions
come from `katrain/assets/board-equipment/go/stones/clamshell-slate/v1/source/recipe.json`.

Run `node scripts/export-production-stones.mjs` from `katrain/web/ui` to regenerate
them. Set `PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH` if Playwright's default browser
revision is not installed.

The white material uses broad, irregular warm shell growth ribbons so the grain
remains visible at normal board sizes. The model's manufacturer photograph,
`white.glb` with embedded photo material, and the TEST-only tutorial sprites are
not used by these production images. The black and white models share the same
lighting and fixed top-down camera. The black stone is unrotated; the 32 white
stones use eight repeating procedural seeds and model rotations in 11.25° steps.
The rendered images should be displayed without rotation so their highlights
remain aligned under the fixed studio lighting.
