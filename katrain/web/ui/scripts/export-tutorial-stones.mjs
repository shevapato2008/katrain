import { createHash } from 'node:crypto';
import { existsSync } from 'node:fs';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { homedir } from 'node:os';
import { fileURLToPath } from 'node:url';
import { chromium } from '@playwright/test';
import { createServer } from 'vite';

const uiRoot = new URL('../', import.meta.url);
const output = new URL('src/assets/tutorial-stones/', uiRoot);
const executablePath = process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH
  || `${homedir()}/Library/Caches/ms-playwright/chromium_headless_shell-1208/chrome-headless-shell-mac-arm64/chrome-headless-shell`;
if (!existsSync(executablePath)) throw new Error('Set PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH to an existing Chromium executable.');

const server = await createServer({
  configFile: fileURLToPath(new URL('preview/photo-shell-stones/vite.config.ts', uiRoot)),
  server: { host: '127.0.0.1', port: 4182, strictPort: true },
});
let browser;
try {
  await server.listen();
  browser = await chromium.launch({ executablePath, args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'] });
  const page = await browser.newPage({ viewport: { width: 1280, height: 800 }, deviceScaleFactor: 1 });
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.goto('http://127.0.0.1:4182/');
  await page.waitForFunction(() => window.__photoStoneReady === true);
  const sprites = await page.evaluate(() => window.__exportTutorialStoneSprites());
  const whiteFiles = Array.from({ length: 32 }, (_, variant) => `white-${String(variant).padStart(2, '0')}.png`);
  if (errors.length || Object.keys(sprites).length !== 32 || whiteFiles.some(file => !sprites[file])) {
    throw new Error(`Expected 32 photo white sprites: ${errors.join('; ')}`);
  }
  await mkdir(output, { recursive: true });
  // Black keeps its existing approved rendering; only white is exported from the photo preview.
  const black = await readFile(new URL('black.png', output));
  const files = [{ file: 'black.png', sha256: createHash('sha256').update(black).digest('hex') }];
  for (const [file, dataUrl] of Object.entries(sprites)) {
    const bytes = Buffer.from(dataUrl.slice(dataUrl.indexOf(',') + 1), 'base64');
    await writeFile(new URL(file, output), bytes);
    files.push({ file, sha256: createHash('sha256').update(bytes).digest('hex') });
  }
  const sources = {};
  for (const file of ['stoneModel.ts', 'stoneStudio.ts']) {
    sources[file] = createHash('sha256').update(await readFile(new URL(`src/components/tutorials/${file}`, uiRoot))).digest('hex');
  }
  for (const file of ['preview.ts', 'index.html', 'preview.css', 'vite.config.ts']) {
    const path = `preview/photo-shell-stones/${file}`;
    sources[path] = createHash('sha256').update(await readFile(new URL(path, uiRoot))).digest('hex');
  }
  const sourcePhotoSha256 = createHash('sha256')
    .update(await readFile(new URL('preview/photo-shell-stones/source-photo.jpg', uiRoot))).digest('hex');
  const manifest = {
    modelVersion: 'shell-slate-original-photo-2026-10-17',
    width: 256, height: 256, transparent: true,
    whiteVariantCount: 32, whiteRotationStepDegrees: 11.25,
    rotation: 'model Y only; camera, studio lights and environment remain fixed',
    camera: { projection: 'orthographic', position: [0, 9, 0], up: [0, 0, -1], bounds: 'per-color physical radius' },
    spriteBounds: 'tight per-color diameter; consumer applies diameterRatio once',
    dimensionsMm: { W: { diameter: 21.9, thickness: 8.8 }, B: { diameter: 22.2, thickness: 9.1 } },
    diameterRatio: { W: 1, B: 22.2 / 21.9 },
    provenance: {
      material: 'Unretouched original photograph UV crop on approximate closed geometry; not a 3D scan',
      source: {
        pageUrl: 'https://kurokigoishiten.com/en/products/clamshell-go-stones-premium-snow-grade',
        imageUrl: 'https://cdn.shopify.com/s/files/1/0606/1093/6995/products/snow-stripesample-01.jpg?v=1654821047',
        file: 'preview/photo-shell-stones/source-photo.jpg', sha256: sourcePhotoSha256,
        width: 2339, height: 2356, cropPixels: { left: 700, top: 450, right: 1650, bottom: 1400 },
        rights: 'Manufacturer photograph; commercial redistribution permission unconfirmed; authorized scope is TEST',
      },
      approvedPreview: {
        url: 'http://127.0.0.1:9035/photo-model/site/',
        rendererFile: 'preview/photo-shell-stones/preview.ts',
        rendererSha256BeforeExportHook: 'ca249a7ff38ea2d5a704835f2cb3dbdf866ea75cdd1b970bda338e199db18f2b',
        white00Sha256: '39e2723cf23e176e2eff396c6a1dba50b794e8f1f21a0a75845313fbc728d913',
      },
      whiteMaterial: { roughness: .3, clearcoat: .12, clearcoatRoughness: .38, envMapIntensity: .6, emissiveIntensity: .18 },
      black: 'Existing black.png preserved byte-identical; not rerendered by the photo exporter',
    },
    sources, files,
  };
  await writeFile(new URL('manifest.json', output), `${JSON.stringify(manifest, null, 2)}\n`);
  console.log(`Exported ${files.length} transparent 256px sprites to ${fileURLToPath(output)}`);
} finally {
  await browser?.close();
  await server.close();
}
