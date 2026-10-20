import { createHash } from 'node:crypto';
import { existsSync } from 'node:fs';
import { copyFile, mkdir, readFile, writeFile } from 'node:fs/promises';
import { homedir } from 'node:os';
import { fileURLToPath } from 'node:url';

const uiRoot = new URL('../', import.meta.url);
const archive = new URL('../../assets/board-equipment/go/stones/clamshell-slate/v1/', uiRoot);
const output = new URL('src/assets/tutorial-stones/', uiRoot);
const [mode, ...extra] = process.argv.slice(2);
if (extra.length || (mode && !['--check', '--render-check', '--export-models'].includes(mode))) {
  throw new Error('Usage: node scripts/export-tutorial-stones.mjs [--check | --render-check | --export-models]');
}
const sha256 = bytes => createHash('sha256').update(bytes).digest('hex');

async function withPreview(action) {
  const executablePath = process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH
    || `${homedir()}/Library/Caches/ms-playwright/chromium_headless_shell-1208/chrome-headless-shell-mac-arm64/chrome-headless-shell`;
  if (!existsSync(executablePath)) throw new Error('Set PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH to an existing Chromium executable.');
  const [{ chromium }, { createServer }] = await Promise.all([import('@playwright/test'), import('vite')]);
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
    await action(page);
    if (errors.length) throw new Error(errors.join('; '));
  } finally {
    await browser?.close();
    await server.close();
  }
}

if (mode === '--export-models') {
  await withPreview(async page => {
    const models = await page.evaluate(async () => {
      const preview = window.__photoStonePreview;
      const data = {};
      for (const [name, buffer] of [
        ['white.glb', await preview.exportModel('photo')],
        ['black.glb', await preview.exportBlackModel()],
      ]) {
        if (!(buffer instanceof ArrayBuffer)) throw new Error(`Expected binary GLB: ${name}`);
        data[name] = await new Promise(resolve => {
          const reader = new FileReader();
          reader.onload = () => resolve(reader.result);
          reader.readAsDataURL(new Blob([buffer]));
        });
      }
      return data;
    });
    await mkdir(new URL('models/', archive), { recursive: true });
    for (const [file, dataUrl] of Object.entries(models)) {
      const bytes = Buffer.from(dataUrl.slice(dataUrl.indexOf(',') + 1), 'base64');
      const destination = new URL(`models/${file}`, archive);
      if (existsSync(destination)) {
        if (!(await readFile(destination)).equals(bytes)) throw new Error(`Approved model differs: ${file}; use a new asset version for intentional changes.`);
      } else {
        await writeFile(destination, bytes);
      }
      console.log(`Verified model ${file}: ${sha256(bytes)}`);
    }
  });
} else {
  const manifest = JSON.parse(await readFile(new URL('manifest.json', archive), 'utf8'));
  for (const { file, sha256: expected } of manifest.artifacts) {
    if (sha256(await readFile(new URL(file, archive))) !== expected) throw new Error(`Archive checksum differs: ${file}`);
  }
  const sprites = JSON.parse(await readFile(new URL('rendered/manifest.json', archive), 'utf8'));
  if (mode === '--render-check') {
    await withPreview(async page => {
      const rendered = await page.evaluate(() => window.__exportTutorialStoneSprites());
      const expected = sprites.files.filter(({ file }) => file.startsWith('white-'));
      if (Object.keys(rendered).length !== expected.length) throw new Error(`Expected ${expected.length} white sprites.`);
      for (const { file, sha256: expectedHash } of expected) {
        const dataUrl = rendered[file];
        if (!dataUrl) throw new Error(`Missing rendered sprite: ${file}`);
        const bytes = Buffer.from(dataUrl.slice(dataUrl.indexOf(',') + 1), 'base64');
        if (sha256(bytes) !== expectedHash) throw new Error(`Approved render differs: ${file}`);
      }
    });
    console.log(`Verified ${sprites.whiteVariantCount} byte-identical photo renders; approved black.png preserved.`);
  } else {
    await mkdir(output, { recursive: true });
    for (const file of ['manifest.json', ...sprites.files.map(({ file }) => file)]) {
      const from = new URL(`rendered/${file}`, archive), to = new URL(file, output);
      if (mode === '--check') {
        if (!(await readFile(from)).equals(await readFile(to))) throw new Error(`Consumer mirror differs: ${file}`);
      } else {
        await copyFile(from, to);
      }
    }
    console.log(`${mode === '--check' ? 'Verified' : 'Copied'} ${sprites.files.length} approved sprites and manifest from ${manifest.assetId}@v${manifest.version}.`);
  }
}
