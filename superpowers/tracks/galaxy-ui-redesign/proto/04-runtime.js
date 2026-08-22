/* spec-sync: 2.4 rev=2026-08-22 sha=2c267c58 —— 见 check_spec_sync.py；规范 §2.4 一改这里就红。 */
/* ═══════════════════════════════════════════════════════════════
   Board renderer — the layout maths is transcribed verbatim from
   src/components/board/boardUtils.ts (calculateBoardLayout /
   gridToCanvas), so the board in this prototype occupies exactly
   the pixels the real one would at the same stage size.
   ═══════════════════════════════════════════════════════════════ */
const WOOD = '#d7a34d';                       /* sampled from katrain/img/board.png */
const LETTERS = 'ABCDEFGHJKLMNOPQRST';        /* Go skips I */

function boardLayout(w, h, size) {
  const spaces = size - 1 + 3;                /* 1.5 margin each side */
  const gridSize = Math.floor(Math.min(w / spaces, h / spaces));
  const bw = spaces * gridSize;
  return { gridSize, ox: Math.round((w - bw) / 2), oy: Math.round((h - bw) / 2) };
}
function g2c(L, x, y, size) {
  return { x: L.ox + (1.5 + x) * L.gridSize, y: L.oy + (1.5 + (size - 1 - y)) * L.gridSize };
}
const STARS = {
  19: [3, 9, 15], 13: [3, 6, 9], 9: [2, 4, 6],
};

function drawBoard(cv, o) {
  const size = o.size || 19;
  const px = cv.width;
  const ctx = cv.getContext('2d');
  const L = boardLayout(px, px, size);
  const gs = L.gridSize;

  /* wood */
  ctx.clearRect(0, 0, px, px);
  const wood = ctx.createRadialGradient(px * .38, px * .3, px * .05, px * .5, px * .5, px * .78);
  wood.addColorStop(0, '#e0af5b'); wood.addColorStop(.55, WOOD); wood.addColorStop(1, '#bf8b3b');
  ctx.fillStyle = wood; ctx.fillRect(0, 0, px, px);
  ctx.globalAlpha = .05; ctx.strokeStyle = '#5a3a12'; ctx.lineWidth = 1;
  for (let i = 0; i < px; i += 7) { ctx.beginPath(); ctx.moveTo(0, i + (i % 3)); ctx.lineTo(px, i); ctx.stroke(); }
  ctx.globalAlpha = 1;

  /* grid */
  ctx.strokeStyle = 'rgba(30,18,4,.72)';
  ctx.lineWidth = Math.max(1, gs * .035);
  for (let i = 0; i < size; i++) {
    const a = g2c(L, i, 0, size), b = g2c(L, i, size - 1, size);
    ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y); ctx.stroke();
    const c = g2c(L, 0, i, size), d = g2c(L, size - 1, i, size);
    ctx.beginPath(); ctx.moveTo(c.x, c.y); ctx.lineTo(d.x, d.y); ctx.stroke();
  }
  ctx.lineWidth = Math.max(1.4, gs * .06);
  const tl = g2c(L, 0, size - 1, size), br = g2c(L, size - 1, 0, size);
  ctx.strokeRect(tl.x, tl.y, br.x - tl.x, br.y - tl.y);

  /* star points */
  ctx.fillStyle = 'rgba(30,18,4,.85)';
  (STARS[size] || []).forEach(sx => (STARS[size] || []).forEach(sy => {
    const p = g2c(L, sx, sy, size);
    ctx.beginPath(); ctx.arc(p.x, p.y, Math.max(1.8, gs * .1), 0, 7); ctx.fill();
  }));

  /* coordinates */
  if (o.coords !== false && gs > 9) {
    ctx.fillStyle = 'rgba(40,25,6,.72)';
    ctx.font = `${Math.max(8, Math.round(gs * .5))}px -apple-system,system-ui,sans-serif`;
    ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
    for (let i = 0; i < size; i++) {
      const t = g2c(L, i, size - 1, size), b2 = g2c(L, i, 0, size);
      ctx.fillText(LETTERS[i], t.x, t.y - gs * 0.95);
      ctx.fillText(LETTERS[i], b2.x, b2.y + gs * 0.95);
      const l = g2c(L, 0, i, size), r = g2c(L, size - 1, i, size);
      ctx.fillText(String(i + 1), l.x - gs * 0.95, l.y);
      ctx.fillText(String(i + 1), r.x + gs * 0.95, r.y);
    }
  }

  /* stones */
  const R = gs * .47;
  (o.stones || []).forEach(([x, y, c]) => {
    const p = g2c(L, x, y, size);
    ctx.beginPath(); ctx.arc(p.x + R * .12, p.y + R * .16, R, 0, 7);
    ctx.fillStyle = 'rgba(0,0,0,.28)'; ctx.fill();
    const g = ctx.createRadialGradient(p.x - R * .35, p.y - R * .4, R * .1, p.x, p.y, R);
    if (c === 'B') { g.addColorStop(0, '#5a5a5a'); g.addColorStop(.5, '#1c1c1c'); g.addColorStop(1, '#050505'); }
    else { g.addColorStop(0, '#ffffff'); g.addColorStop(.6, '#f0eee9'); g.addColorStop(1, '#cdc9c0'); }
    ctx.beginPath(); ctx.arc(p.x, p.y, R, 0, 7); ctx.fillStyle = g; ctx.fill();
  });

  /* last move ring */
  if (o.last) {
    const p = g2c(L, o.last[0], o.last[1], size);
    ctx.strokeStyle = o.last[2] === 'B' ? '#ffffff' : '#111111';
    ctx.lineWidth = Math.max(1.5, gs * .09);
    ctx.beginPath(); ctx.arc(p.x, p.y, R * .5, 0, 7); ctx.stroke();
  }

  /* move numbers */
  if (o.numbers) {
    ctx.font = `600 ${Math.round(gs * .5)}px var(--mono),monospace`;
    ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
    (o.stones || []).forEach(([x, y, c], i) => {
      const p = g2c(L, x, y, size);
      ctx.fillStyle = c === 'B' ? '#fff' : '#000';
      ctx.fillText(String(i + 1), p.x, p.y);
    });
  }

  /* AI candidate markers */
  (o.ai || []).forEach((m, i) => {
    const p = g2c(L, m[0], m[1], size);
    ctx.beginPath(); ctx.arc(p.x, p.y, R, 0, 7);
    ctx.fillStyle = i === 0 ? 'rgba(93,130,112,.92)' : 'rgba(93,130,112,.62)'; ctx.fill();
    if (i === 0) { ctx.strokeStyle = 'rgba(255,255,255,.9)'; ctx.lineWidth = Math.max(2, gs * .08); ctx.stroke(); }
    ctx.fillStyle = '#fff'; ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
    ctx.font = `700 ${Math.round(gs * .38)}px -apple-system,system-ui,sans-serif`;
    ctx.fillText(m[2], p.x, p.y - gs * .12);
    ctx.font = `${Math.round(gs * .3)}px -apple-system,system-ui,sans-serif`;
    ctx.fillText(m[3], p.x, p.y + gs * .26);
  });

  /* territory ownership overlay */
  if (o.territory) {
    (o.territory).forEach(([x, y, v]) => {
      const p = g2c(L, x, y, size);
      ctx.fillStyle = v > 0 ? `rgba(0,0,0,${Math.abs(v) * .45})` : `rgba(255,255,255,${Math.abs(v) * .45})`;
      const s = gs * .5;
      ctx.fillRect(p.x - s / 2, p.y - s / 2, s, s);
    });
  }
}

/* deterministic pseudo-game so every screen shows the same plausible position */
function demoStones(n) {
  const seq = [[3,3,'B'],[15,15,'W'],[15,3,'B'],[3,15,'W'],[16,9,'B'],[2,9,'W'],[9,16,'B'],[9,2,'W'],
    [5,2,'B'],[2,5,'W'],[13,2,'B'],[16,5,'W'],[16,13,'B'],[13,16,'W'],[5,16,'B'],[2,13,'W'],
    [9,9,'B'],[11,10,'W'],[8,10,'B'],[10,12,'W'],[7,7,'B'],[12,6,'W'],[6,11,'B'],[13,11,'W'],
    [10,4,'B'],[7,4,'W'],[4,7,'B'],[11,14,'W'],[14,7,'B'],[6,14,'W'],[8,6,'B'],[12,9,'W'],
    [5,9,'B'],[14,11,'W'],[9,13,'B'],[10,7,'W'],[7,12,'B'],[12,13,'W'],[4,11,'B'],[15,9,'W']];
  return seq.slice(0, n);
}

/* ═══════════════════════════════════════════════════════════════
   Runtime
   ═══════════════════════════════════════════════════════════════ */
const VPS = [
  { id: '1440x900', w: 1440, h: 900, label: '1440×900 标准', sidebar: 216, rail: 340, board: 828 },
  { id: '1024x768', w: 1024, h: 768, label: '1024×768 窄', sidebar: 0, rail: 320, board: 684 },
  { id: '430x880', w: 430, h: 880, label: '430×880 竖屏', sidebar: 0, rail: null, board: 410 },
  /* 承重用，不是验收档：把可用高度压到 588，右栏中段必然要滚 */
  { id: '1280x640', w: 1280, h: 640, label: '1280×640 压扁', sidebar: 216, rail: 320, board: 568, stress: true },
];

const S = {
  screen: null, branch: null, vp: '1440x900', mode: 'now', stress: false,
  dialog: null, snack: null, drawer: true,
  toggles: {}, log: [],
};

const $ = (s, r) => (r || document).querySelector(s);
const $$ = (s, r) => Array.from((r || document).querySelectorAll(s));
const esc = (s) => String(s == null ? '' : s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
/* 传图标名走 sprite；直接传一段 HTML（'<' 开头）就原样放行 ——
   真实代码里有几个图标不是 MUI 图标，是手画的 Box 或纯字形。 */
const icon = (n, cls) => (n && String(n)[0] === '<') ? n : `<svg class="ic ${cls || ''}" aria-hidden="true"><use href="#i-${n}"/></svg>`;
/* ResearchToolbar.tsx:51/66/81 与 BoardEditToolbar.tsx:18/28/38 的自定义图标 */
const STONE = {
  b: '<span class="stoneic b"></span>',
  w: '<span class="stoneic w"></span>',
  alt: '<span class="stoneic alt"><i></i><i></i></span>',
};
/* BoardEditToolbar 的 123 / A / a / △ / ✕ 是 <Typography>，不是图标 */
const glyph = (s) => `<span class="glyph">${esc(s)}</span>`;

/* control helpers — every one carries data-src so the drawer can
   pair what you see with the line it came from */
function btn(o) {
  const c = ['mbtn', o.variant || '', o.color || '', o.size || '', o.full ? 'full' : ''].filter(Boolean).join(' ');
  return `<button class="${c}" ${o.disabled ? 'disabled' : ''} data-act="${esc(o.act || '')}" data-src="${esc(o.src || '')}"${o.key ? ` data-key="${esc(o.key)}"` : ''}>${o.icon ? icon(o.icon, 'sm') : ''}${esc(o.label)}</button>`;
}
function ibtn(o) {
  return `<button class="iconbtn ${o.size || ''} ${o.cls || ''}" aria-label="${esc(o.label)}" ${o.disabled ? 'disabled' : ''} data-act="${esc(o.act || '')}" data-src="${esc(o.src || '')}">${icon(o.icon, o.size === 'sm' ? 'sm' : '')}</button>`;
}
function tbtn(o) {
  const on = S.toggles[o.id] != null ? S.toggles[o.id] : !!o.on;
  return `<button class="tbtn ${o.cls || ''}" role="button" aria-pressed="${on}" data-toggle="${esc(o.id)}" ${o.disabled ? 'disabled' : ''} data-act="${esc(o.act || ('切换 ' + o.label))}" data-src="${esc(o.src || '')}">${o.icon ? icon(o.icon, 'sm') : ''}${esc(o.label)}</button>`;
}
function swrow(o) {
  const on = S.toggles[o.id] != null ? S.toggles[o.id] : !!o.on;
  return `<div class="swrow"><span>${esc(o.label)}</span><button class="sw" role="switch" aria-checked="${on}" aria-label="${esc(o.label)}" data-toggle="${esc(o.id)}" data-act="切换 ${esc(o.label)}" data-src="${esc(o.src || '')}"></button></div>`;
}
function card(inner, o) {
  o = o || {};
  return `<button class="card click ${o.sel ? 'sel' : ''}" data-act="${esc(o.act || '')}" data-src="${esc(o.src || '')}" style="${o.style || ''}">${inner}</button>`;
}
function plate(o) {
  if (o.backLabel) {
    return `<div class="plate" data-zone="right-rail-top">
      <div class="plate-text"><p class="plate-title">${esc(o.title)}</p>${o.sub ? `<p class="plate-sub">${esc(o.sub)}</p>` : ''}</div>
      ${o.status || ''}
      ${btn({ label: o.backLabel, icon: 'ArrowBack', act: '返回 ' + o.backTo, src: o.src })}
    </div>`;
  }
  return `<div class="plate iconleft" data-zone="right-rail-top">
    ${ibtn({ icon: 'ArrowBack', label: 'Back', act: 'requestNavigation(' + o.backTo + ')　—— aria-label 是 t(\'Back\',\'Back\')，cn 目录没有这个词条，所以中文界面下它读作 "Back"', src: o.src })}
    <div class="plate-text"><p class="plate-title">${esc(o.title)}</p>${o.sub ? `<p class="plate-sub">${esc(o.sub)}</p>` : ''}</div>
    ${o.status || ''}
  </div>`;
}
function cph(o) {
  return `<div class="cph" data-zone="page-header">
    <h1>${esc(o.title)}</h1>
    ${o.parentLabel ? btn({ label: o.parentLabel, icon: 'ArrowBackRounded', variant: 'outlined', color: 'inherit', act: '返回 ' + o.parentTo, src: o.src }) : ''}
  </div>`;
}
function dlgOpen(id, label, o) {
  o = o || {};
  const c = ['mbtn', o.variant || '', o.color || '', o.size || ''].filter(Boolean).join(' ');
  return `<button class="${c}" data-dialog="${esc(id)}" data-act="打开对话框 ${esc(id)}" data-src="${esc(o.src || '')}">${o.icon ? icon(o.icon, 'sm') : ''}${esc(label)}</button>`;
}
