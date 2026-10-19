#!/usr/bin/env node
/** Capture real public OGS initial exercise views. Never reconstruct a webpage. */
import { createHash } from 'node:crypto';
import { createRequire } from 'node:module';
import fs from 'node:fs';
import path from 'node:path';
import { pathToFileURL } from 'node:url';

const args = Object.fromEntries(process.argv.slice(2).reduce((items, value, index, all) => {
  if (value.startsWith('--')) items.push([value.slice(2), all[index + 1]?.startsWith('--') ? true : all[index + 1] ?? true]);
  return items;
}, []));
if (!args.bundle || !args.output) throw new Error('Required: --bundle course.json --output capture-dir [--playwright-module module-dir] [--workers 3] [--limit N]');
const require = createRequire(import.meta.url);
const playwright = args['playwright-module']
  ? await import(pathToFileURL(path.join(path.resolve(args['playwright-module']), 'index.mjs')).href)
  : require('playwright');
const bundle = JSON.parse(fs.readFileSync(args.bundle, 'utf8'));
if (bundle.schema_version !== 1 || !Array.isArray(bundle.steps)) throw new Error('Unsupported source bundle');
const output = path.resolve(args.output);
fs.mkdirSync(path.join(output, 'pages'), { recursive: true });
const journal = path.join(output, 'captures.jsonl');
const previous = new Map();
if (fs.existsSync(journal)) for (const line of fs.readFileSync(journal, 'utf8').split('\n').filter(Boolean)) {
  const row = JSON.parse(line); previous.set(row.source_id, row);
}
const sha = bytes => createHash('sha256').update(bytes).digest('hex');
const canonical = value => Array.isArray(value) ? value.map(canonical) : value && typeof value === 'object'
  ? Object.fromEntries(Object.keys(value).sort().map(key => [key, canonical(value[key])])) : value;
const digest = value => sha(JSON.stringify(canonical(value)));
const textKey = text => String(text ?? '').replace(/\s/gu, '');
const expectedIdentity = step => {
  const text = step.translations['zh-cn'];
  let instruction = text.instruction;
  for (const choice of step.exercise.choices ?? []) instruction += text.choices?.[choice.value] ?? choice.value;
  if (step.exercise.kind === 'pass' || step.exercise.kind === 'finish') instruction += bundle.source.ui_translations['zh-cn'][step.exercise.kind];
  return { config: step.raw_source.config, title: textKey(text.title), instruction: textKey(instruction) };
};
const sortPoints = points => points.map(point => point.join(',')).sort().join(';');
const cacheOkay = step => {
  const row = previous.get(step.source_id);
  if (row?.status !== 'captured' || row.language !== 'zh-cn' || row.source_commit !== bundle.source.commit
    || row.identity_version !== 2 || row.expected_identity_sha256 !== digest(expectedIdentity(step))
    || row.observed_identity_sha256 !== row.expected_identity_sha256) return false;
  const image = path.join(output, row.path);
  return fs.existsSync(image) && sha(fs.readFileSync(image)) === row.sha256;
};
const limit = args.limit ? Number(args.limit) : Infinity;
const chosen = bundle.steps.filter(step => !cacheOkay(step)).slice(0, limit);
const lessonGroups = new Map();
for (const step of chosen) {
  const group = lessonGroups.get(step.lesson_id) ?? [];
  group.push(step); lessonGroups.set(step.lesson_id, group);
}
const queue = [...lessonGroups.values()];
const total = chosen.length;
let captured = 0, failed = 0, mismatched = 0;
const workers = Math.max(1, Math.min(4, Number(args.workers ?? 3)));
const browser = await playwright.chromium.launch({ channel: 'chrome', headless: !args.headed });
const context = await browser.newContext({ viewport: { width: 1920, height: 1080 }, locale: 'zh-CN', deviceScaleFactor: 1 });
const start = Date.now();
const record = row => { fs.appendFileSync(journal, JSON.stringify(row) + '\n'); previous.set(row.source_id, row); };
const observed = async (page, configKeys) => page.evaluate(keys => {
  const goban = window.global_goban, engine = goban?.engine;
  const stones = { B: [], W: [] };
  if (engine) for (let row = 0; row < engine.height; row++) for (let col = 0; col < engine.width; col++) {
    if (engine.board[row][col] === 1) stones.B.push([col, row]);
    if (engine.board[row][col] === 2) stones.W.push([col, row]);
  }
  return { language: window.ogs_current_language, url: location.href,
    active_step: Number(document.querySelector('.LearningPage-pages .pages .page.active')?.textContent),
    total_steps: document.querySelectorAll('.LearningPage-pages .pages .page').length,
    title: document.querySelector('.LearningPage-pages h1')?.textContent ?? '',
    instruction: document.querySelector('.LearningPage-pages .text')?.textContent ?? '',
    width: engine?.width, height: engine?.height, initial_player: engine?.player === 1 ? 'B' : 'W',
    move_number: engine?.cur_move?.move_number, stones,
    config: Object.fromEntries(keys.map(key => [key, goban?.config?.[key]])),
  };
}, configKeys);
try {
  if (!chosen.length) { console.log(JSON.stringify({ total: bundle.steps.length, cached: bundle.steps.length, captured: 0 })); }
  else {
    const bootstrap = await context.newPage();
    await bootstrap.goto(chosen[0].source_url, { waitUntil: 'domcontentloaded', timeout: 45000 });
    await bootstrap.locator('.LearningPage').waitFor({ state: 'visible', timeout: 45000 });
    if (await bootstrap.evaluate(() => window.ogs_current_language) !== 'zh-cn') {
      await bootstrap.locator('.LanguagePicker').click();
      await bootstrap.getByText('简体中文', { exact: true }).click();
      await bootstrap.waitForFunction(() => window.ogs_current_language === 'zh-cn', { timeout: 30000 });
    }
    await bootstrap.close();
    await Promise.all(Array.from({ length: workers }, async (_, worker) => {
      const page = await context.newPage();
      while (queue.length) {
        const steps = queue.shift();
        let loadedLesson = false;
        for (const step of steps) {
          const base = { source_id: step.source_id, page: step.page, step: step.step, source_url: step.source_url,
            source_step_index: step.step - 1, source_commit: bundle.source.commit, language: 'zh-cn', captured_at: new Date().toISOString() };
          try {
            if (!loadedLesson) {
              await page.goto(step.source_url, { waitUntil: 'domcontentloaded', timeout: 45000 });
              loadedLesson = true;
            } else {
              const target = page.locator('.LearningPage-pages .pages .page').nth(step.step - 1);
              await target.click({ timeout: 10000 });
            }
            await page.waitForFunction(expected => Number(document.querySelector('.LearningPage-pages .pages .page.active')?.textContent) === expected && !!window.global_goban?.engine, step.step, { timeout: 20000 });
            await page.evaluate(async () => { await document.fonts.ready; await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))); });
            await page.waitForTimeout(120);
            const expected = expectedIdentity(step);
            const actual = await observed(page, Object.keys(expected.config));
            const expectedSignature = digest(expected);
            const observedSignature = digest({ config: actual.config, title: textKey(actual.title), instruction: textKey(actual.instruction) });
            const expectedPath = decodeURIComponent(new URL(step.source_url).pathname).replace(/\/$/, '');
            const actualPath = decodeURIComponent(new URL(actual.url).pathname).replace(/\/$/, '');
            const same = actual.language === 'zh-cn' && actual.active_step === step.step && actual.move_number === 0
              && actual.width === step.size && actual.height === step.size && actual.initial_player === step.initial_player
              && sortPoints(actual.stones.B) === sortPoints(step.stones.B) && sortPoints(actual.stones.W) === sortPoints(step.stones.W)
              && expectedSignature === observedSignature
              && actualPath.replace(/\/0$/, '') === expectedPath.replace(/\/0$/, '');
            if (!same) { mismatched++; record({ ...base, status: 'mismatched', expected_identity_sha256: expectedSignature, observed_identity_sha256: observedSignature, observed: actual }); continue; }
            const clip = await page.evaluate(() => {
              const elements = ['.InstructionalGoban', '.LearningPage-pages'].map(selector => document.querySelector(selector)?.getBoundingClientRect());
              if (elements.some(rect => !rect || rect.width <= 0 || rect.height <= 0)) throw new Error('Original exercise layout is missing');
              const x = Math.max(0, Math.floor(Math.min(...elements.map(rect => rect.left)) + scrollX) - 8);
              const y = Math.max(0, Math.floor(Math.min(...elements.map(rect => rect.top)) + scrollY) - 8);
              return { x, y, width: Math.ceil(Math.max(...elements.map(rect => rect.right)) + scrollX) + 8 - x,
                height: Math.ceil(Math.max(...elements.map(rect => rect.bottom)) + scrollY) + 8 - y };
            });
            const imagePath = `pages/step_${String(step.page).padStart(4, '0')}_zh-cn.png`;
            const image = await page.screenshot({ path: path.join(output, imagePath), clip, animations: 'disabled' });
            record({ ...base, status: 'captured', identity_version: 2, expected_identity_sha256: expectedSignature, observed_identity_sha256: observedSignature,
              path: imagePath, sha256: sha(image), width: clip.width, height: clip.height,
              clip, observed: { title: actual.title, instruction: actual.instruction, url: actual.url, active_step: actual.active_step, total_steps: actual.total_steps } });
            captured++;
          } catch (error) { failed++; loadedLesson = false; record({ ...base, status: 'failed', error: String(error.message ?? error).slice(0, 500) }); }
          if ((captured + failed + mismatched) % 25 === 0) console.log(JSON.stringify({ captured, failed, mismatched, total, worker, elapsed_seconds: Math.round((Date.now() - start) / 1000) }));
          await page.waitForTimeout(100);
        }
        console.log(JSON.stringify({ lesson: steps[0].lesson_id, captured, failed, mismatched, total }));
      }
      await page.close();
    }));
  }
} finally { await context.close(); await browser.close(); }
const final = { source_commit: bundle.source.commit, total: bundle.steps.length,
  captured: bundle.steps.filter(cacheOkay).length, failed: bundle.steps.filter(step => previous.get(step.source_id)?.status === 'failed').length,
  mismatched: bundle.steps.filter(step => previous.get(step.source_id)?.status === 'mismatched').length,
  elapsed_seconds: Math.round((Date.now() - start) / 1000) };
fs.writeFileSync(path.join(output, 'summary.json'), JSON.stringify(final, null, 2) + '\n');
console.log(JSON.stringify(final));
if (final.failed || final.mismatched) process.exitCode = 1;
