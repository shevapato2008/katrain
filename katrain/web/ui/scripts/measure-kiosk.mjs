#!/usr/bin/env node
/**
 * measure-kiosk.mjs — compare first-paint + bundle size for full vs kiosk-2d builds.
 *
 * Usage:  node scripts/measure-kiosk.mjs
 * Output: markdown table to stdout, raw JSON to ./kiosk-metrics.json
 *
 * Requires ../static-full-baseline and ../static-kiosk-2d to exist.
 */
import { chromium } from '@playwright/test';
import http from 'node:http';
import { readFile, readdir, stat, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const UI_DIR = path.resolve(__dirname, '..');

const MIME = {
  '.html': 'text/html', '.js': 'application/javascript', '.mjs': 'application/javascript',
  '.css': 'text/css', '.json': 'application/json', '.svg': 'image/svg+xml',
  '.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.woff': 'font/woff',
  '.woff2': 'font/woff2', '.ttf': 'font/ttf', '.ico': 'image/x-icon',
};

async function dirSize(dir) {
  let total = 0;
  for (const name of await readdir(dir, { withFileTypes: true })) {
    const p = path.join(dir, name.name);
    total += name.isDirectory() ? await dirSize(p) : (await stat(p)).size;
  }
  return total;
}

function makeSpaServer(root) {
  return http.createServer(async (req, res) => {
    const urlPath = decodeURIComponent((req.url || '/').split('?')[0]);
    let filePath = path.join(root, urlPath);
    let exists = false;
    try { exists = (await stat(filePath)).isFile(); } catch { /* not a file */ }
    if (!exists) filePath = path.join(root, 'index.html');
    try {
      const data = await readFile(filePath);
      const ct = MIME[path.extname(filePath)] || 'application/octet-stream';
      res.writeHead(200, { 'Content-Type': ct, 'Cache-Control': 'no-store' });
      res.end(data);
    } catch {
      res.writeHead(404).end('not found');
    }
  });
}

async function listen(server, port) {
  return new Promise((resolve, reject) => {
    server.once('error', reject);
    server.listen(port, '127.0.0.1', () => resolve());
  });
}

async function close(server) {
  return new Promise((resolve) => server.close(() => resolve()));
}

async function measure(label, staticDir, port, route = '/kiosk/login') {
  const absDir = path.resolve(UI_DIR, staticDir);
  const bytes = await dirSize(absDir);
  const server = makeSpaServer(absDir);
  await listen(server, port);
  const browser = await chromium.launch();
  try {
    const context = await browser.newContext({ viewport: { width: 1280, height: 800 } });
    const page = await context.newPage();
    await page.addInitScript(() => {
      // @ts-ignore
      window.__lcp__ = 0;
      new PerformanceObserver((list) => {
        for (const e of list.getEntries()) {
          // @ts-ignore
          if (e.startTime > window.__lcp__) window.__lcp__ = e.startTime;
        }
      }).observe({ type: 'largest-contentful-paint', buffered: true });
    });
    const url = `http://127.0.0.1:${port}${route}`;
    const t0 = Date.now();
    await page.goto(url, { waitUntil: 'networkidle', timeout: 30000 });
    const tti = Date.now() - t0;
    // Give LCP one more rAF tick.
    await page.waitForTimeout(300);
    const metrics = await page.evaluate(() => {
      const fcpEntry = performance.getEntriesByName('first-contentful-paint')[0];
      const nav = performance.getEntriesByType('navigation')[0];
      return {
        fcp: Math.round(fcpEntry ? fcpEntry.startTime : 0),
        // @ts-ignore
        lcp: Math.round(window.__lcp__ || 0),
        domComplete: Math.round(nav ? nav.domComplete : 0),
        loadEvent: Math.round(nav ? nav.loadEventEnd : 0),
      };
    });
    return { label, bytes, ...metrics, tti };
  } finally {
    await browser.close();
    await close(server);
  }
}

const pct = (kiosk, full) => full === 0 ? '—' : `${Math.round((1 - kiosk / full) * 100)}%`;
const mb = (b) => (b / 1024 / 1024).toFixed(2);

console.error('→ measuring full baseline…');
const full = await measure('full', '../static-full-baseline', 9190);
console.error('→ measuring kiosk-2d…');
const kiosk = await measure('kiosk-2d', '../static-kiosk-2d', 9191);

const rows = [
  ['dist/ 总大小', `${mb(full.bytes)} MB`, `${mb(kiosk.bytes)} MB`, pct(kiosk.bytes, full.bytes)],
  ['FCP',          `${full.fcp} ms`,       `${kiosk.fcp} ms`,       pct(kiosk.fcp, full.fcp)],
  ['LCP',          `${full.lcp} ms`,       `${kiosk.lcp} ms`,       pct(kiosk.lcp, full.lcp)],
  ['domComplete',  `${full.domComplete} ms`, `${kiosk.domComplete} ms`, pct(kiosk.domComplete, full.domComplete)],
  ['load event',   `${full.loadEvent} ms`, `${kiosk.loadEvent} ms`, pct(kiosk.loadEvent, full.loadEvent)],
  ['TTI (networkidle proxy)', `${full.tti} ms`, `${kiosk.tti} ms`, pct(kiosk.tti, full.tti)],
];

console.log('| 指标 | 完整版 (with three) | 2D-only (kiosk) | 降幅 |');
console.log('|---|---|---|---|');
for (const [k, a, b, d] of rows) {
  console.log(`| ${k} | ${a} | ${b} | ${d} |`);
}

await writeFile(path.join(UI_DIR, 'kiosk-metrics.json'),
  JSON.stringify({ full, kiosk, generatedAt: new Date().toISOString() }, null, 2) + '\n');

console.error('→ wrote kiosk-metrics.json');
