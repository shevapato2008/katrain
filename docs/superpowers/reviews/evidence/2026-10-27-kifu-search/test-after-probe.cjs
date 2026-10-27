// One-off read-only TEST probe. Run only after release + indexes are confirmed ready.
// Run from the TEST ui directory with NODE_PATH=$PWD/node_modules and pass baseline/source paths.
// stdout is public JSONL only; no cookies, auth headers, request headers or private configuration.
const fs = require('fs');
const http = require('http');
const crypto = require('crypto');
const { performance } = require('perf_hooks');
const { chromium } = require('playwright');
const ts = require('typescript');
const [baselinePath, serializerPath, screenshotPath] = process.argv.slice(2);
if (!baselinePath || !serializerPath) throw Error('baseline and actual sgfSerializer.ts paths required');
const BASE = 'http://127.0.0.1:8001';
const emit = (row) => console.log(JSON.stringify({ captured_utc: new Date().toISOString(), environment: 'TEST', ...row }));
const sha = (s) => crypto.createHash('sha256').update(s).digest('hex');
const norm = (d) => ({ total: d.total, page: d.page, page_size: d.page_size, items: d.items,
  preview: d.preview ? Object.fromEntries(Object.entries(d.preview).filter(([k]) => k !== 'sgf_content')) : null,
  preview_sgf_sha256: d.preview?.sgf_content ? sha(d.preview.sgf_content) : null });
const canonical = (x) => JSON.stringify(x, (_, v) => v && typeof v === 'object' && !Array.isArray(v)
  ? Object.fromEntries(Object.keys(v).sort().map(k => [k, v[k]])) : v);
const agent = new http.Agent({ keepAlive: true, maxSockets: 1 });
async function request(params) {
  const start = performance.now();
  return new Promise((resolve, reject) => {
    const req = http.get(`${BASE}/api/v1/kifu/albums?${new URLSearchParams(params)}`, { agent }, res => {
      const ttfb = performance.now() - start; let body = '';
      res.setEncoding('utf8'); res.on('data', chunk => body += chunk);
      res.on('end', () => { try { resolve({ status: res.statusCode, http_ms: performance.now() - start,
        ttfb_ms: ttfb, server_timing: res.headers['server-timing'] ?? null, bytes: Buffer.byteLength(body), data: JSON.parse(body) }); }
      catch (e) { reject(e); } });
    });
    req.setTimeout(30000, () => req.destroy(Error('HTTP timeout'))); req.on('error', reject);
  });
}
async function contracts() {
  const before = fs.readFileSync(baselinePath, 'utf8').trim().split('\n').map(JSON.parse);
  for (const old of before) {
    const { data, ...timing } = await request({ q: old.q, page: old.page, page_size: 20, lang: old.lang });
    const actual = norm(data), expected = Object.fromEntries(Object.keys(actual).map(k => [k, old[k]]));
    const equivalent = timing.status === 200 && canonical(actual) === canonical(expected);
    emit({ kind: 'contract', case: old.case, q: old.q, lang: old.lang, ...timing, equivalent, ...actual });
    if (!equivalent) throw Error(`Public contract mismatch: ${old.case}`);
  }
  for (const [label, params, expectedStatus, expectedTotal] of [
    ['explicit_player_id', { player_id: 25 }, 200, 504],
    ['unknown_player_id', { player_id: 2147483647 }, 200, 0],
    ['conflicting_filters', { player_id: 25, q: '王星昊' }, 422, null],
    ['event_slow_separate', { q: '围甲' }, 200, null],
    ['fuzzy_slow_separate', { q: '王' }, 200, null],
  ]) {
    const { data, ...timing } = await request({ ...params, page: 1, page_size: 20, lang: 'cn' });
    const correct = timing.status === expectedStatus && (expectedTotal === null || data.total === expectedTotal);
    emit({ kind: 'extra_contract', case: label, ...timing, correct, ...(timing.status === 200 ? norm(data) : {}) });
    if (!correct) throw Error(`Extra contract mismatch: ${label}`);
  }
  agent.destroy();
}
function instrument() {
  window.__probe = { current: null };
  document.addEventListener('keydown', e => {
    if (e.key !== 'Enter' || !(e.target instanceof HTMLInputElement)) return;
    window.__probe.current = { t0: performance.now(), input: e.target.value, done: false };
  }, true);
  const nativeFetch = window.fetch;
  window.fetch = async function(...args) {
    const path = new URL(typeof args[0] === 'string' ? args[0] : args[0].url, location.href);
    const p = path.pathname === '/api/v1/kifu/albums' ? window.__probe.current : null;
    if (p) { p.fetchStart = performance.now(); p.query = path.searchParams.get('q'); p.lang = path.searchParams.get('lang'); p.page = Number(path.searchParams.get('page') || 1); }
    const res = await nativeFetch.apply(this, args);
    if (p) {
      p.headersAt = performance.now(); p.status = res.status; p.serverTiming = res.headers.get('server-timing');
      const nativeJson = res.json.bind(res);
      res.json = async () => {
        const data = await nativeJson(); p.responseAt = performance.now();
        p.total = data.total; p.ids = data.items?.map(x => x.id); p.first = data.items?.[0];
        p.previewId = data.preview?.id;
        p.expected = data.preview?.sgf_content ? window.__parseSGF(data.preview.sgf_content) : null;
        return data;
      };
    }
    return res;
  };
  const propsUp = (el, match) => {
    const key = Object.keys(el).find(k => k.startsWith('__reactFiber$'));
    for (let f = el[key], n = 0; f && n < 50; f = f.return, n++) {
      if (f.memoizedProps && match(f.memoizedProps)) return f.memoizedProps;
    }
    return null;
  };
  const clear = CanvasRenderingContext2D.prototype.clearRect;
  CanvasRenderingContext2D.prototype.clearRect = function(...args) {
    const ret = clear.apply(this, args), p = window.__probe.current;
    if (!p || p.done || !p.responseAt || !p.expected || p.status !== 200) return ret;
    const canvas = this.canvas, drawAt = performance.now();
    requestAnimationFrame(() => requestAnimationFrame(() => {
      if (window.__probe.current !== p || p.done || !canvas.isConnected) return;
      const actual = propsUp(canvas, x => Array.isArray(x.moves) && Array.isArray(x.stoneColors) && 'currentMove' in x);
      const firstCard = document.querySelector('.MuiCardActionArea-root');
      const card = firstCard ? propsUp(firstCard, x => x.album && 'selected' in x) : null;
      const title = document.querySelector('[data-testid="module-plate"]')?.innerText ?? '';
      const input = document.querySelector('input[placeholder]');
      const count = input?.closest('.MuiTextField-root')?.nextElementSibling?.textContent ?? '';
      const movesMatch = actual && JSON.stringify(actual.moves) === JSON.stringify(p.expected.moves)
        && JSON.stringify(actual.stoneColors) === JSON.stringify(p.expected.stoneColors)
        && actual.currentMove === p.expected.moves.length && actual.boardSize === (p.expected.metadata.boardSize || 19);
      const firstMatch = card?.album?.id === p.ids?.[0] && card?.selected === true && p.previewId === p.ids?.[0];
      const titleMatch = p.first && title.includes(`${p.first.display_player_black} vs ${p.first.display_player_white}`)
        && title.includes(String(p.first.move_count));
      const totalMatch = count.startsWith(p.total.toLocaleString());
      if (!movesMatch || !firstMatch || !titleMatch || !totalMatch) {
        p.lastCheck = { movesMatch: !!movesMatch, firstMatch, titleMatch, totalMatch, title, count, actualFirstId: card?.album?.id };
        return;
      }
      const pixels = canvas.getContext('2d').getImageData(0, 0, canvas.width, canvas.height).data;
      let nontransparent = 0; for (let i = 3; i < pixels.length; i += 400) if (pixels[i] > 0) nontransparent++;
      if (!nontransparent) return;
      Object.assign(p, { done: true, paintAt: performance.now(), drawAt, movesMatch: true, firstMatch,
        titleMatch, totalMatch, title, count, nontransparentSamples: nontransparent, moveCount: actual.moves.length });
    }));
    return ret;
  };
}
async function browsers() {
  const parser = ts.transpileModule(fs.readFileSync(serializerPath, 'utf8'), { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 } }).outputText;
  const browser = await chromium.launch({ headless: true, executablePath: '/home/fan/.cache/ms-playwright/chromium-1208/chrome-linux64/chrome', args: ['--no-sandbox'] });
  const queries = ['王星昊', '柯洁', '申真谞', '朴廷桓', '辜梓豪', '丁浩', '井山裕太', '一力辽'];
  const seen = new Set(['王星昊', '柯洁']); let screenshotDone = false;
  try {
    for (const latency of [0, 40]) for (const clients of [1, 4]) {
      const ready = [];
      for (let client = 0; client < clients; client++) {
        const lang = ['cn', 'en', 'jp', 'ko'][client];
        const context = await browser.newContext({ viewport: { width: 1280, height: 720 }, locale: 'zh-CN' });
        await context.addInitScript({ content: `localStorage.setItem('katrain_language',${JSON.stringify(lang)});(()=>{const exports={};${parser};window.__parseSGF=exports.sgfToMoves;})();(${instrument.toString()})();` });
        const page = await context.newPage(); const errors = [];
        page.on('pageerror', e => errors.push(String(e)));
        const cdp = await context.newCDPSession(page);
        await cdp.send('Network.enable');
        await cdp.send('Network.emulateNetworkConditions', { offline: false, latency, downloadThroughput: -1, uploadThroughput: -1, packetLoss: 0 });
        await page.goto(`${BASE}/galaxy/kifu?q=zz_kifu_no_such_player_20261027`, { waitUntil: 'networkidle' });
        await page.locator('input[placeholder]').waitFor();
        ready.push({ context, page, client, lang, errors });
      }
      await Promise.all(ready.map(async ({ page, client, lang, errors }) => {
        for (let i = 0; i < 32 / clients; i++) {
          const last = 32 / clients - 1, pageTwo = i === last;
          const q = i >= last - 1 ? '王星昊' : queries[(i + client * 2) % queries.length];
          const firstServiceQuery = !seen.has(q); seen.add(q);
          const input = page.locator(pageTwo ? 'input[name="page"]' : 'input[placeholder]');
          await input.fill(pageTwo ? '2' : q); await input.press('Enter');
          let p;
          try { await page.waitForFunction(() => window.__probe.current?.done, null, { timeout: 30000 });
            p = await page.evaluate(() => { const p=window.__probe.current; return Object.fromEntries(Object.entries(p).filter(([k]) => !['expected','first'].includes(k))); });
          } catch (e) { const failure = await page.evaluate(() => { const p=window.__probe.current; return p ? Object.fromEntries(Object.entries(p).filter(([k]) => !['expected','first'].includes(k))) : null; });
            emit({ kind: 'browser_failure', latency_emulation_ms: latency, clients, client, q, failure, errors }); throw e; }
          emit({ kind: 'browser_search', condition: latency ? 'loopback + CDP latency=40ms, unlimited throughput, no packet loss' : 'server loopback, no network emulation',
            clients, client, lang, sample: i, first_service_query: firstServiceQuery, q,
            ...p, submit_to_paint_ms: p.paintAt-p.t0, fetch_to_json_ms: p.responseAt-p.fetchStart,
            fetch_ttfb_ms: p.headersAt-p.fetchStart, response_to_paint_ms: p.paintAt-p.responseAt, errors });
          if (!screenshotDone && screenshotPath) { await page.screenshot({ path: screenshotPath }); screenshotDone = true; }
          // At most one submitted search per second per client, measured from browser keydown.
          await page.waitForTimeout(Math.max(0, 1000-(p.paintAt-p.t0)));
        }
      }));
      for (const { context } of ready) await context.close();
    }
  } finally { await browser.close(); }
}
(async () => { await contracts(); await browsers(); })().catch(e => { emit({ kind: 'probe_error', error: String(e) }); process.exitCode = 1; });
