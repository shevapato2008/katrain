import { mkdir, writeFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { chromium } from '@playwright/test';
import { createServer } from 'vite';

const root = new URL('../', import.meta.url);
const output = new URL('src/components/board/assets/shell-slate/', root);
const server = await createServer({ root: fileURLToPath(root), server: { host: '127.0.0.1', port: 4183, strictPort: true } });
let browser;
try {
  await server.listen();
  browser = await chromium.launch({
    ...(process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH ? { executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH } : {}),
    args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'],
  });
  const page = await browser.newPage();
  await page.goto('http://127.0.0.1:4183/preview/production-stones/export.html');
  await page.waitForFunction(() => window.__productionStoneSprites && Object.keys(window.__productionStoneSprites).length === 9);
  const sprites = await page.evaluate(() => window.__productionStoneSprites);
  await mkdir(output, { recursive: true });
  for (const [name, dataUrl] of Object.entries(sprites)) {
    await writeFile(new URL(name, output), Buffer.from(dataUrl.split(',')[1], 'base64'));
  }
  console.log(`Rendered ${Object.keys(sprites).length} photo-free sprites from the existing stone model.`);
} finally {
  await browser?.close();
  await server.close();
}
