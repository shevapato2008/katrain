import { createRequire } from 'node:module';
import { mkdir, writeFile } from 'node:fs/promises';
import path from 'node:path';

const require = createRequire(path.join(process.cwd(), 'package.json'));
const { chromium } = require('@playwright/test');

const viewports = [
  [1535, 900], [1536, 900], [1537, 900], [1440, 900], [1201, 800], [1200, 800], [1199, 800],
  [1024, 768], [901, 700], [900, 700], [899, 700], [430, 880],
];
let matchId = 'yike_184016';
const livePath = () => `/galaxy/live/${matchId}`;

const captureName = process.argv[2] ?? 'reference';
const baseUrl = process.env.GALAXY_BASE_URL ?? 'http://127.0.0.1:8901';
const outputRoot = path.resolve(
  process.cwd(),
  '../../../superpowers/tracks/galaxy-ui-redesign/visual/live-template',
);

const browser = await chromium.launch({ headless: true });
const geometry = [];

try {
  for (const [width, height] of viewports) {
    const context = await browser.newContext({ viewport: { width, height }, deviceScaleFactor: 1 });
    const page = await context.newPage();
    const url = `${baseUrl}${livePath()}`;
    const browserEvents = [];
    page.on('console', (message) => browserEvents.push({ type: `console:${message.type()}`, text: message.text() }));
    page.on('pageerror', (error) => browserEvents.push({ type: 'pageerror', text: error.message }));
    page.on('requestfailed', (request) => browserEvents.push({
      type: 'requestfailed',
      text: `${request.method()} ${request.url()} ${request.failure()?.errorText ?? ''}`.trim(),
    }));
    console.log(`Capturing ${width}x${height}: ${url}`);

    const response = await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 30_000 });
    try {
      await page.waitForFunction(() => {
        const preferred = document.querySelector(
          '[data-testid="galaxy-live-board"] canvas, [data-testid="live-board"] canvas',
        );
        const canvas = preferred ?? document.querySelector('canvas');
        return canvas instanceof HTMLCanvasElement;
      }, { timeout: 30_000 });
    } catch (error) {
      const diagnostics = await page.evaluate(() => ({
        url: window.location.href,
        title: document.title,
        bodyText: document.body?.innerText.slice(0, 2_000) ?? '',
        canvasCount: document.querySelectorAll('canvas').length,
        canvases: [...document.querySelectorAll('canvas')].map((canvas) => {
          const bounds = canvas.getBoundingClientRect();
          return { width: bounds.width, height: bounds.height, x: bounds.x, y: bounds.y };
        }),
      }));
      console.error(JSON.stringify({
        failedViewport: { width, height },
        navigationHttpStatus: response?.status() ?? null,
        diagnostics,
        browserEvents,
      }, null, 2));
      throw error;
    }
    await page.waitForTimeout(1_000);

    const measured = await page.evaluate(({ width: viewportWidth, height: viewportHeight }) => {
      const rect = (element) => {
        if (!element) return null;
        const value = element.getBoundingClientRect();
        return {
          x: value.x,
          y: value.y,
          width: value.width,
          height: value.height,
          top: value.top,
          right: value.right,
          bottom: value.bottom,
          left: value.left,
        };
      };
      const preferredCanvas = document.querySelector(
        '[data-testid="galaxy-live-board"] canvas, [data-testid="live-board"] canvas',
      );
      const canvas = preferredCanvas ?? document.querySelector('canvas');
      if (!canvas) throw new Error('Live board canvas was not found');

      const explicitSidebar = document.querySelector(
        '[data-testid="galaxy-sidebar"], [data-testid="galaxy-navigation"], aside[data-galaxy-sidebar]',
      );
      const navigation = document.querySelector('nav');
      let sidebar = explicitSidebar;
      if (!sidebar && navigation) {
        let candidate = navigation;
        while (candidate.parentElement) {
          const candidateRect = candidate.getBoundingClientRect();
          if (
            candidateRect.left <= 1 &&
            candidateRect.width <= 400 &&
            candidateRect.height >= viewportHeight * 0.8
          ) {
            sidebar = candidate;
          }
          candidate = candidate.parentElement;
        }
      }

      const explicitRightRail = document.querySelector(
        '[data-testid="live-right-rail"], [data-testid="board-right-rail"], aside:not([data-galaxy-sidebar]), [role="complementary"]',
      );
      let rightRail = explicitRightRail;
      if (!rightRail) {
        let ancestor = canvas.parentElement;
        while (ancestor && !rightRail) {
          for (const sibling of ancestor.parentElement?.children ?? []) {
            if (sibling === ancestor || sibling.contains(canvas)) continue;
            const siblingRect = sibling.getBoundingClientRect();
            if (
              siblingRect.width >= 100 &&
              siblingRect.height >= viewportHeight * 0.6 &&
              siblingRect.left >= canvas.getBoundingClientRect().right - 2 &&
              siblingRect.right >= viewportWidth - 2
            ) {
              rightRail = sibling;
              break;
            }
          }
          ancestor = ancestor.parentElement;
        }
      }

      const canvasBounds = canvas.getBoundingClientRect();
      const isVisibleAboveCanvas = (element) => {
        const bounds = element.getBoundingClientRect();
        const style = getComputedStyle(element);
        return (
          bounds.width > 0 && bounds.height > 0 &&
          bounds.bottom <= canvasBounds.top + 1 &&
          bounds.bottom > 0 && bounds.top < viewportHeight &&
          style.visibility !== 'hidden' && style.display !== 'none' && Number(style.opacity) !== 0
        );
      };
      const normalize = (value) => value.replace(/\s+/g, ' ').trim();
      const unique = (values) => [...new Set(values.filter(Boolean))];
      const buttons = unique(
        [...document.querySelectorAll('button, [role="button"]')]
          .filter(isVisibleAboveCanvas)
          .map((element) => normalize(element.getAttribute('aria-label') || element.innerText || element.textContent || '')),
      );
      const texts = unique(
        [...document.querySelectorAll('h1, h2, h3, h4, h5, h6, p, span, a')]
          .filter((element) => isVisibleAboveCanvas(element) && element.children.length === 0)
          .map((element) => normalize(element.innerText || element.textContent || ''))
          .filter((value) => value.length <= 200),
      );
      const documentElement = document.documentElement;
      const body = document.body;
      const scrollWidth = Math.max(documentElement.scrollWidth, body?.scrollWidth ?? 0);
      const clientWidth = documentElement.clientWidth;

      return {
        viewport: { width: viewportWidth, height: viewportHeight },
        canvas: rect(canvas),
        sidebar: rect(sidebar),
        rightRail: rect(rightRail),
        horizontalOverflow: {
          scrollWidth,
          clientWidth,
          overflowPx: Math.max(0, scrollWidth - clientWidth),
          hasOverflow: scrollWidth > clientWidth,
        },
        visibleAboveCanvas: { texts, buttons },
      };
    }, { width, height });

    const viewportName = `${width}x${height}`;
    const viewportOutput = path.join(outputRoot, viewportName);
    await mkdir(viewportOutput, { recursive: true });
    await page.screenshot({ path: path.join(viewportOutput, `${captureName}.png`), fullPage: true });
    geometry.push({ viewportName, url, ...measured });
    await context.close();
  }
} finally {
  await browser.close();
}

await mkdir(outputRoot, { recursive: true });
await writeFile(
  path.join(outputRoot, `geometry-${captureName}.json`),
  `${JSON.stringify({ matchId, livePath: livePath(), captures: geometry }, null, 2)}\n`,
);

console.log(`Captured ${geometry.length} viewports for ${livePath()} (${captureName}).`);
