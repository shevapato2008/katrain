// ---------- Icons, board drawing and small helpers shared by every page ----------
const P = {
  book: '<path d="M12 5c-3-2-6-2-9-1v15c3-1 6-1 9 1m0-15c3-2 6-2 9-1v15c-3-1-6-1-9 1m0-15v15"/>',
  clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
  pulse: '<path d="M2 12h4l3-7 5 14 3-7h5"/>',
  camera: '<path d="M3 7h4l2-2h6l2 2h4v12H3z"/><circle cx="12" cy="13" r="3"/>',
  chev: '<path d="m9 6 6 6-6 6"/>',
  help: '<circle cx="12" cy="12" r="9"/><path d="M9 9a3 3 0 0 1 6 0c0 2-3 2-3 4m0 3h.01"/>',
  check: '<circle cx="12" cy="12" r="9"/><path d="m8 12 3 3 5-6"/>',
  fail: '<circle cx="12" cy="12" r="9"/><path d="m9 9 6 6m0-6-6 6"/>',
  warn: '<path d="m12 3 10 18H2L12 3Z"/><path d="M12 9v5m0 3h.01"/>',
  wait: '<circle cx="12" cy="12" r="9" stroke-dasharray="3 3"/><path d="M12 7v5l3 2"/>',
  wifi: '<path d="M2 8.8a15 15 0 0 1 20 0M5 12.5a10 10 0 0 1 14 0M8.5 16a5 5 0 0 1 7 0M12 20h.01M3 3l18 18"/>',
  info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v5m0-8h.01"/>',
  lock: '<rect x="5" y="11" width="14" height="9" rx="1.5"/><path d="M8 11V8a4 4 0 0 1 8 0v3"/>',
  search: '<circle cx="11" cy="11" r="7"/><path d="m20 20-4-4"/>',
  led: '<circle cx="12" cy="12" r="4"/><path d="M12 2v3m0 14v3M2 12h3m14 0h3M5 5l2 2m10 10 2 2M19 5l-2 2M7 17l-2 2"/>',
  upload: '<path d="M12 16V4m-5 5 5-5 5 5M4 16v4h16v-4"/>',
  refresh: '<path d="M20 11a8 8 0 0 0-14-5l-2 2m0-4v4h4m-4 5a8 8 0 0 0 14 5l2-2m0 4v-4h-4"/>',
  play: '<path d="M7 5v14l11-7z"/>',
  stop: '<rect x="6" y="6" width="12" height="12" rx="1"/>',
  zoom: '<path d="M14 4h6v6M10 20H4v-6M20 4l-7 7M4 20l7-7"/>',
  layers: '<path d="m12 3 9 5-9 5-9-5 9-5Zm-9 9 9 5 9-5M3 16l9 5 9-5"/>',
  undo: '<path d="M9 14 4 9l5-5"/><path d="M4 9h11a5 5 0 0 1 0 10h-3"/>',
  box: '<rect x="4" y="4" width="16" height="16" rx="2"/><path d="M4 9h16"/>',
  file: '<path d="M6 3h8l4 4v14H6z"/><path d="M14 3v4h4"/>',
};
const ic = (name, cls = 'i') => `<svg class="${cls}" viewBox="0 0 24 24" aria-hidden="true">${P[name] || P.help}</svg>`;
const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' })[c]);
const COLS = 'ABCDEFGHJKLMNOPQRST';
const coord = ([x, y]) => COLS[x] + (19 - y);
const pad2 = (n) => String(n).padStart(2, '0');
const nowTime = () => { const d = new Date(); return `${pad2(d.getHours())}:${pad2(d.getMinutes())}:${pad2(d.getSeconds())}`; };

// A deterministic illustrative game: 60 moves spread across the board, used by every lab page.
const GAME = (() => {
  const seq = [[15,3],[3,15],[16,15],[3,3],[13,16],[15,10],[2,5],[5,2],[9,3],[16,6],[14,5],[13,14],[16,12],[11,16],[5,16],[2,13],[9,15],[15,16],[16,16],[14,15],[16,17],[3,9],[6,3],[12,3],[5,5],[9,9],[10,12],[7,13],[12,9],[8,6],[4,11],[11,6],[13,7],[6,9],[14,12],[12,12],[10,10],[8,11],[7,16],[6,14],[17,9],[17,4],[2,16],[4,17],[1,3],[2,2],[17,2],[10,4],[4,7],[14,9],[11,14],[8,17],[16,8],[5,12],[9,7],[3,6],[15,13],[12,5],[7,4],[6,7]];
  return seq.map((p, i) => ({ n: i + 1, color: i % 2 ? 'W' : 'B', p }));
})();
function stonesAt(moveCount, extra = []) {
  const map = new Map();
  GAME.slice(0, moveCount).forEach((m) => map.set(m.p.join(','), m.color));
  extra.forEach(([x, y, c]) => c ? map.set(x + ',' + y, c) : map.delete(x + ',' + y));
  return [...map].map(([k, c]) => { const [x, y] = k.split(',').map(Number); return { x, y, c }; });
}

// Top-down board: returns SVG markup in a 0..20 coordinate space.
function boardSVG({ stones = [], marks = [], boxes = [], leds = [], grid = true, bg = '#e4d4b6', lastMove = null, numbers = false, clickable = false, label = '19 路棋盘' } = {}) {
  let s = `<svg viewBox="0 0 20 20" role="img" aria-label="${esc(label)}" ${clickable ? 'data-board="1"' : ''}><rect x="0.3" y="0.3" width="19.4" height="19.4" fill="${bg}" rx="0.15"/>`;
  if (grid) {
    s += '<g stroke="#5e5646" stroke-width="0.045">';
    for (let k = 1; k <= 19; k++) s += `<line x1="${k}" y1="1" x2="${k}" y2="19"/><line x1="1" y1="${k}" x2="19" y2="${k}"/>`;
    s += '</g><g fill="#5e5646">';
    for (const a of [4, 10, 16]) for (const b of [4, 10, 16]) s += `<circle cx="${a}" cy="${b}" r="0.1"/>`;
    s += '</g>';
  }
  const LC = { red: '#e0473f', green: '#46c46a', blue: '#4f7fe0' };
  for (const l of leds) s += `<circle cx="${l.x + 1}" cy="${l.y + 1}" r="0.36" fill="${LC[l.color]}" opacity="0.9"/><circle cx="${l.x + 1}" cy="${l.y + 1}" r="0.62" fill="none" stroke="${LC[l.color]}" stroke-width="0.08" opacity="0.7"/>`;
  for (const st of stones) s += `<circle data-stone="${st.c}" cx="${st.x + 1}" cy="${st.y + 1}" r="0.46" fill="${st.c === 'W' ? '#f8f5ed' : '#202124'}" stroke="${st.c === 'W' ? '#938d7e' : '#0c0d0e'}" stroke-width="0.05"${st.ghost ? ' opacity="0.45" stroke-dasharray="0.15 0.1"' : ''}/>`;
  if (lastMove) s += `<circle cx="${lastMove.x + 1}" cy="${lastMove.y + 1}" r="0.18" fill="none" stroke="${lastMove.c === 'B' ? '#fff' : '#202124'}" stroke-width="0.07"/>`;
  for (const m of marks) s += `<rect x="${m.x + 0.4}" y="${m.y + 0.4}" width="1.2" height="1.2" fill="none" stroke="${m.color || '#d14b3f'}" stroke-width="0.1" rx="0.12"/>`;
  for (const b of boxes) s += `<rect data-box="${b.tier || 'raw'}" x="${b.x + 0.42 + (b.dx || 0)}" y="${b.y + 0.42}" width="1.16" height="1.16" fill="none" stroke="${b.tier === 'sustain' ? '#e39a3a' : b.c === 'W' ? '#4f86c6' : '#2f9c86'}" stroke-width="0.085"/>`;
  if (clickable) for (let y = 0; y < 19; y++) for (let x = 0; x < 19; x++) s += `<rect data-act="tut-place" data-x="${x}" data-y="${y}" x="${x + 0.5}" y="${y + 0.5}" width="1" height="1" fill="transparent" style="cursor:crosshair"/>`;
  return s + '</svg>';
}

// Camera-like raw frame: the board seen in perspective on a table.
function rawSVG({ stones = [], corners = true, leds = [], label = '原始相机画面（合成示意）' } = {}) {
  const tl = [470, 118], tr = [1130, 126], br = [1238, 648], bl = [360, 640];
  const lerp = (a, b, t) => [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t];
  const at = (u, v) => lerp(lerp(tl, tr, u), lerp(bl, br, u), v);
  const g = (i) => (i + 1) / 20;
  let s = `<svg viewBox="300 70 1000 640" role="img" aria-label="${esc(label)}"><rect width="1600" height="760" fill="#2d3033"/><rect y="560" width="1600" height="200" fill="#26282a"/>`;
  const edge = [at(0, 0), at(1, 0), at(1, 1), at(0, 1)].map((p) => p.join(',')).join(' ');
  s += `<polygon points="${edge}" fill="#c9b184"/><g stroke="#5a5040" stroke-width="1.2">`;
  for (let k = 0; k < 19; k++) { const a = at(g(k), g(0)), b = at(g(k), g(18)), c = at(g(0), g(k)), d = at(g(18), g(k)); s += `<line x1="${a[0]}" y1="${a[1]}" x2="${b[0]}" y2="${b[1]}"/><line x1="${c[0]}" y1="${c[1]}" x2="${d[0]}" y2="${d[1]}"/>`; }
  s += '</g>';
  const RC = { red: '#ff5a4d', green: '#5cf07e', blue: '#6f9bff' };
  for (const l of leds) { const p = at(g(l.x), g(l.y)); s += `<ellipse cx="${p[0]}" cy="${p[1]}" rx="11" ry="8" fill="${RC[l.color]}"/><ellipse cx="${p[0]}" cy="${p[1]}" rx="22" ry="15" fill="${RC[l.color]}" opacity="0.25"/>`; }
  for (const st of stones) { const p = at(g(st.x), g(st.y)); const r = 13 + (p[1] - 118) / 530 * 5; s += `<ellipse cx="${p[0]}" cy="${p[1] - 2}" rx="${r}" ry="${r * 0.82}" fill="${st.c === 'W' ? '#efeae0' : '#1b1c1e'}" stroke="${st.c === 'W' ? '#a39c8d' : '#000'}" stroke-width="1"/>`; }
  if (corners) { s += `<polygon points="${edge}" fill="none" stroke="#8cc1d0" stroke-width="3" stroke-dasharray="10 6"/>`; for (const p of [at(0, 0), at(1, 0), at(1, 1), at(0, 1)]) s += `<circle cx="${p[0]}" cy="${p[1]}" r="9" fill="none" stroke="#8cc1d0" stroke-width="3"/>`; }
  return s + '</svg>';
}

// ---------- State ----------
const S = {
  theme: (() => { const t = document.documentElement.dataset.theme; return t === 'light' || t === 'dark' ? t : (matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark'); })(),
  signedIn: true, page: 'capture', labOpen: true, proto: false, modal: null, toast: '',
};
const pages = {};   // page id -> { render(), title }
const actions = {}; // data-act name -> handler(el, event)
const timers = new Set();
function every(ms, fn) { const t = setInterval(fn, ms); timers.add(t); return t; }
function later(ms, fn) { const t = setTimeout(() => { timers.delete(t); fn(); }, ms); timers.add(t); return t; }

function confirmModal({ title, body, check, accept, onAccept, wide = false }) {
  S.modal = { title, body, check, accept, onAccept, wide, checked: !check };
  render();
}
actions['modal-check'] = (el) => { S.modal.checked = el.checked; const b = document.getElementById('modal-accept'); if (b) b.disabled = !S.modal.checked; };
actions['modal-cancel'] = () => { S.modal = null; render(); };
actions['modal-accept'] = () => { const m = S.modal; if (!m || !m.checked) return; S.modal = null; m.onAccept?.(); render(); };
function modalHTML() {
  const m = S.modal; if (!m) return '';
  return `<div class="p-backdrop" data-act="modal-backdrop"><div class="p-modal${m.wide ? ' wide' : ''}" role="dialog" aria-modal="true" aria-labelledby="modal-title"><h2 id="modal-title">${m.title}</h2>${m.body}${m.check ? `<label class="check"><input type="checkbox" data-change="modal-check" ${m.checked ? 'checked' : ''}><span>${m.check}</span></label>` : ''}<div class="actions"><button class="btn" data-act="modal-cancel">${m.accept ? '返回' : '关闭'}</button>${m.accept ? `<button class="btn primary" id="modal-accept" data-act="modal-accept" ${m.checked ? '' : 'disabled'}>${m.accept}</button>` : ''}</div></div></div>`;
}
actions['modal-backdrop'] = (el, e) => { if (e.target === el) { S.modal = null; render(); } };
