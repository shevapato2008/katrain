import { chromium } from '../../katrain/web/ui/node_modules/playwright/index.mjs';
import { OrthographicCamera, Vector3 } from '../../katrain/web/ui/node_modules/three/build/three.module.js';
import fs from 'node:fs/promises';
import path from 'node:path';

const root = process.cwd();
const output = path.join(root, 'output/tutorial-samples-20261017');
const bundle = path.join(root, 'katrain/web/tutorial-media-static');
const browser = await chromium.launch({ headless: true,
  executablePath: '/Users/fan/Library/Caches/ms-playwright/chromium_headless_shell-1208/chrome-headless-shell-mac-arm64/chrome-headless-shell',
  args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'] });
const evidence = [];
for (const [figure, time] of [[1030, 9400], [1031, 4000]]) {
  const data = JSON.parse(await fs.readFile(path.join(output, `recording-${figure}.json`), 'utf8'));
  data.render_mode = '3d';
  const context = await browser.newContext({ viewport: { width: 1280, height: 800 }, deviceScaleFactor: 1, serviceWorkers: 'block' });
  const errors = [];
  await context.route('**/*', async route => {
    const url = new URL(route.request().url());
    const local = path.resolve(bundle, decodeURIComponent(url.pathname).replace(/^\//, ''));
    if (url.origin !== 'http://tutorial-preview.local' || !local.startsWith(bundle + path.sep)) {
      errors.push(`Blocked ${url.pathname}`); await route.abort(); return;
    }
    try { await route.fulfill({ path: local }); } catch (error) { errors.push(String(error)); await route.abort(); }
  });
  const page = await context.newPage();
  page.on('pageerror', error => errors.push(String(error)));
  await page.addInitScript(data => {
    window.__TUTORIAL_MEDIA_DATA = data;
  }, data);
  await page.goto('http://tutorial-preview.local/tutorial-media.html', { waitUntil: 'load' });
  await page.waitForFunction(() => window.__TUTORIAL_MEDIA_READY === true);
  await page.evaluate(async time => { await window.__tutorialSetFrame(time); }, time);
  const file = `solid-3d-${figure}.png`;
  await page.screenshot({ path: path.join(output, file) });
  const actual = await page.evaluate(() => {
    const rect = document.querySelector('canvas').getBoundingClientRect();
    return { canvas: { x: rect.x, y: rect.y, width: rect.width, height: rect.height },
      step: document.querySelector('main').dataset.step,
      appearance: document.querySelector('main').dataset.boardAppearance,
      regionFill: document.querySelector('[data-known-region]').getAttribute('fill'),
      annotations: [...document.querySelectorAll('[data-annotation-point]')].map(element => ({
        point: element.getAttribute('data-annotation-point'), text: element.textContent, transform: element.getAttribute('transform') })),
      lastRing: document.querySelector('[data-testid="tutorial-last-move"]')?.parentElement.getAttribute('transform'),
      caption: document.querySelector('.tm-caption').textContent };
  });
  // The recording contract supplies this centered camera. Project the model's
  // actual dimensions into the measured canvas to quantify symmetry and depth.
  const { canvas } = actual;
  const span = data.board_payload.size + 2.6;
  const angle = 35 * Math.PI / 180;
  const camera = new OrthographicCamera(-canvas.width / 2, canvas.width / 2, canvas.height / 2, -canvas.height / 2, .1, 100);
  camera.zoom = Math.min(canvas.width, canvas.height) / span;
  camera.position.set(0, 1.2 + 30 * Math.cos(angle), 30 * Math.sin(angle));
  camera.lookAt(0, 1.2, 0); camera.updateProjectionMatrix(); camera.updateMatrixWorld();
  const project = (x, y, z) => {
    const point = new Vector3(x, y, z).project(camera);
    return { x: canvas.x + (point.x + 1) * canvas.width / 2, y: canvas.y + (1 - point.y) * canvas.height / 2 };
  };
  const half = (data.board_payload.size + .6) / 2;
  const corners = { topLeft: project(-half, 1.2, -half), topRight: project(half, 1.2, -half),
    frontLeft: project(-half, 1.2, half), frontRight: project(half, 1.2, half),
    bottomFront: project(0, -1.3, half) };
  const leftRightErrorPx = Math.abs((640 - corners.frontLeft.x) - (corners.frontRight.x - 640));
  const frontFaceHeightPx = corners.bottomFront.y - corners.frontLeft.y;
  if (errors.length || leftRightErrorPx > .01 || frontFaceHeightPx < 40 || actual.regionFill !== 'none')
    throw new Error(JSON.stringify({ errors, leftRightErrorPx, frontFaceHeightPx, actual }));
  evidence.push({ file, figure, time, ...actual, corners, leftRightErrorPx, frontFaceHeightPx, errors });
  console.log(file, JSON.stringify({ step: actual.step, leftRightErrorPx, frontFaceHeightPx, annotations: actual.annotations.length }));
  await context.close();
}
await browser.close();
await fs.writeFile(path.join(output, 'solid-3d-evidence.json'), JSON.stringify(evidence, null, 2));
