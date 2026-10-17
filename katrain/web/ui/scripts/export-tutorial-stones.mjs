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
  configFile: fileURLToPath(new URL('preview/shell-stones/vite.config.ts', uiRoot)),
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
  await page.waitForFunction(() => window.__stonePreviewReady === true);
  const sprites = await page.evaluate(() => window.__exportTutorialStoneSprites());
  if (errors.length || Object.keys(sprites).length !== 33) throw new Error(`Sprite export failed: ${errors.join('; ')}`);
  await mkdir(output, { recursive: true });
  const files = [];
  for (const [file, dataUrl] of Object.entries(sprites)) {
    const bytes = Buffer.from(dataUrl.slice(dataUrl.indexOf(',') + 1), 'base64');
    await writeFile(new URL(file, output), bytes);
    files.push({ file, sha256: createHash('sha256').update(bytes).digest('hex') });
  }
  const sources = {};
  for (const file of ['stoneModel.ts', 'stoneStudio.ts']) {
    sources[file] = createHash('sha256').update(await readFile(new URL(`src/components/tutorials/${file}`, uiRoot))).digest('hex');
  }
  const manifest = {
    modelVersion: 'approved-shell-slate-2026-10-17',
    width: 256, height: 256, transparent: true,
    whiteVariantCount: 32, whiteTextureSeed: 17, whiteRotationStepDegrees: 11.25,
    rotation: 'model Y only; camera, studio lights and environment remain fixed',
    camera: { projection: 'orthographic', position: [0, 9, 0], up: [0, 0, -1], bounds: 'per-color physical radius' },
    spriteBounds: 'tight per-color diameter; consumer applies diameterRatio once',
    dimensionsMm: { W: { diameter: 21.9, thickness: 8.8 }, B: { diameter: 22.2, thickness: 9.1 } },
    diameterRatio: { W: 1, B: 22.2 / 21.9 }, sources, files,
  };
  await writeFile(new URL('manifest.json', output), `${JSON.stringify(manifest, null, 2)}\n`);
  console.log(`Exported ${files.length} transparent 256px sprites to ${fileURLToPath(output)}`);
} finally {
  await browser?.close();
  await server.close();
}
