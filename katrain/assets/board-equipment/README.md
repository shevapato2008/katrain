# Board equipment assets

Versioned, reviewed source assets for Go board equipment live here. The first
approved set is `go.stones.clamshell-slate@v1`:

```text
go/stones/clamshell-slate/v1/
  manifest.json              identity, provenance, dimensions and SHA-256 inventory
  source/recipe.json         geometry, photo crop, material and studio parameters
  materials/source-photo.jpg unretouched manufacturer photograph
  models/white.glb           photo clamshell, glTF 2.0, metres
  models/black.glb           slate material, glTF 2.0, metres
  rendered/manifest.json     approved sprite export metadata
  rendered/white-00.png      32 white rotations, 00 through 31
  rendered/black.png         approved black sprite
```

The source photo, models, recipe and approved images are project assets. Paths
under `output/` are disposable review evidence. The APP and admin console copies
in `src/assets/tutorial-stones/` are generated consumer mirrors of `rendered/`.
They are not independently owned source sets.

## Current approved set

The white stone is 21.9 mm in diameter and 8.8 mm thick; black is 22.2 × 9.1 mm.
Both use an artistically approximated, closed symmetric lens profile. They are
not scans or measured meshes. Geometry is normalized to the white stone's
2-unit diameter; both GLBs use the same **0.01095 metre per unit** scale. Black
geometry already includes its diameter ratio, so do not apply that ratio again
to a GLB. Each model rests on the y=0 plane and uses y as its vertical axis.

White uses only the original photograph's crop x=700..1650, y=450..1400 from a
2339 × 2356 image. The photo is embedded in `white.glb`, including its UV crop
transform; no external texture is needed to load either GLB. The preserved white
model retains its original node name `clamshell-white-photo-preview`; the archive
manifest supplies its permanent identity. Black's node name is `slate-black`.

`source/recipe.json` is the parameter authority. The existing Three.js adapters
are `katrain/web/ui/src/components/tutorials/stoneModel.ts` and `stoneStudio.ts`;
the photo preview reads the same recipe and canonical photo. The procedural
`createShellMaps` white material remains a library fallback and older comparison
preview. It is not the approved default material. The AI-derived texture retained
in `preview/photo-shell-stones/photo-shell-albedo.png` is a labeled comparison
only and is excluded from this approved asset set.

The photograph comes from [Kuroki Goishiten's product page](https://kurokigoishiten.com/en/products/clamshell-go-stones-premium-snow-grade).
The original URL and file SHA-256 are recorded in `manifest.json`. The current
rights status is **manufacturer copyright; commercial redistribution permission
unconfirmed; authorized scope TEST**. Project archiving does not change that
status.

## Reproduce and verify

From `katrain/web/ui`:

```sh
# Copy the approved sprites and export manifest into the APP consumer directory.
npm run export:tutorial-stones

# Check archive hashes and the APP mirror without starting a browser.
npm run export:tutorial-stones -- --check

# Re-render the 32 white rotations and compare each PNG byte-for-byte.
npm run export:tutorial-stones -- --render-check

# Reproduce both GLBs; verify existing files or restore a missing file.
npm run export:tutorial-stones -- --export-models

# Mirror the same APP consumer files into a separate console checkout.
node scripts/sync-tutorial-stones.mjs /absolute/path/to/console/admin-console/ui
node scripts/sync-tutorial-stones.mjs /absolute/path/to/console/admin-console/ui --check
```

The browser commands use the installed Playwright Chromium headless shell; set
`PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH` if it is elsewhere. Run them using the
project's pinned dependencies and the same Chromium/SwiftShader setup used for
the approved export. A render or model mismatch stops the command; intentional
changes require a new reviewed version. The approved black PNG is preserved,
not rerendered by the photo export. No tutorial videos need regeneration to copy
or verify this archive.

For the interactive comparison preview:

```sh
npx vite --config preview/photo-shell-stones/vite.config.ts --host 127.0.0.1
```

## Galaxy, kiosk, and additional styles

Galaxy and kiosk can consume the approved 2D PNG sprites through the existing
`tutorialStoneSprites.ts` helper without adding Three.js to their runtime. A
sprite is 256 × 256 with transparency and tight bounds for its own color. Apply
the manifest's black/white diameter ratio once when sizing sprites; rotate the
white material by selecting a variant, while keeping labels upright. GLBs are
available for future 3D consumers; their scene lighting should be derived from
the recipe when reproducing the approved appearance.

Add future reviewed styles at, for example,
`go/stones/yunzi/v1/` or `go/boards/kaya/v1/`, with their own manifest, source,
models or materials, and exported images as needed. Keep a stable asset ID and
an explicit version; record units, dimensions, provenance, rights and hashes.
Create those directories when actual assets exist. There is no asset service,
registry database or runtime style selector in this archive change.
