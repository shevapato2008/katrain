/* ═══════════════════════════════════════════════════════════════
   Chrome renderers — GalaxyTopBar / GalaxySidebar / GalaxyBottomNav
   ═══════════════════════════════════════════════════════════════ */
const NAV = [
  { key: 'home', label: '首页', path: '/galaxy', icon: 'Home' },
  { key: 'play', label: '对局', path: '/galaxy/play', icon: 'SportsEsports' },
  { key: 'research', label: '研究', path: '/galaxy/research', icon: 'Science' },
  { key: 'tsumego', label: '死活题', path: '/galaxy/tsumego', icon: 'Extension' },
  { key: 'review', label: '复盘', path: '/galaxy/report', icon: 'Assessment' },
  { key: 'live', label: '直播', path: '/galaxy/live', icon: 'LiveTv' },
  { key: 'kifu', label: '棋谱库', path: '/galaxy/kifu', icon: 'LibraryBooks' },
  { key: 'tutorials', label: '教程', path: '/galaxy/tutorials', icon: 'MenuBook' },
];

function topbar(vp) {
  /* 改版：左栏折叠钮不再悬在棋盘上。左栏已经停靠时根本不需要折叠
     （1440 下棋盘是高度受限，收起左栏一个像素都不多），只有左栏
     收起了的档位才需要一个入口，放在顶栏左侧。 */
  const needMenu = S.mode === 'new' && vp && vp.sidebar === 0 && vp.id !== '430x880';
  return `<header class="topbar" data-zone="top-bar">
    ${needMenu ? ibtn({ icon: 'Menu', label: '展开导航', act: '展开左侧导航（覆盖式）', src: 'GalaxyTopBar.tsx' }) : ''}
    <button class="brand" aria-label="回到首页" data-act="导航 /galaxy" data-src="GalaxyTopBar.tsx:30">
      <img src="${LOGO}" alt="智星盒 StellaBox">
      <span class="brand-cn">智星盒</span><span class="brand-latin">StellaBox</span>
    </button>
  </header>`;
}

function sidebar(active) {
  return `<nav class="sidebar" data-zone="sidebar" aria-label="主导航">
    <ul class="sidenav">
      ${NAV.map(n => `<li><button class="navitem" ${n.key === active ? 'aria-current="page"' : ''}
        data-act="导航 ${n.path}" data-src="GalaxySidebar.tsx:73">${icon(n.icon)}<span>${n.label}</span></button></li>`).join('')}
    </ul>
    <div class="side-foot">
      <button class="navitem" data-act="打开设置菜单（语言）" data-src="GalaxySidebar.tsx:90">${icon('Settings')}<span>设置</span></button>
      <div class="usercard">
        <div class="avatar">5k</div>
        <div style="flex:1;min-width:0">
          <div style="font-size:.85rem;font-weight:600;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">fan</div>
          <div style="font-size:.72rem;color:var(--jade-l);font-weight:600">5k</div>
        </div>
        ${ibtn({ icon: 'Logout', label: '退出登录', size: 'sm', act: '退出登录', src: 'GalaxySidebar.tsx:119' })}
      </div>
    </div>
  </nav>`;
}

function bottomnav(active) {
  const direct = NAV.slice(0, 5);
  return `<nav class="bottomnav" data-zone="bottom-nav" aria-label="主导航">
    ${direct.map(n => `<button ${n.key === active ? 'aria-current="page"' : ''} aria-label="${n.label}"
      data-act="导航 ${n.path}" data-src="GalaxyBottomNav.tsx:46">${icon(n.icon)}<span>${n.label}</span></button>`).join('')}
    <button aria-label="更多" data-act="打开更多菜单（棋谱库 / 教程）" data-src="GalaxyBottomNav.tsx:54">${icon('MoreHoriz')}<span>更多</span></button>
  </nav>`;
}

/* ═══════════════════════════════════════════════════════════════
   Frame assembly
   ═══════════════════════════════════════════════════════════════ */
function currentScreen() { return SCREENS.find(s => s.id === S.screen) || SCREENS[0]; }
function branchesOf(sc) {
  return (S.mode === 'new' && sc.branches2) ? sc.branches2 : (sc.branches || [{ id: 'default', label: '默认' }]);
}
function currentBranch(sc) {
  const bs = branchesOf(sc);
  return bs.find(b => b.id === S.branch) || bs[0];
}

function renderFrame() {
  const sc = currentScreen();
  const br = currentBranch(sc);
  const vp = VPS.find(v => v.id === S.vp);
  const mobile = vp.id === '430x880';
  /* 改版模式：有 V2 实现就用 V2，并强制走 BoardPageShell 那条路 */
  const useV2 = S.mode === 'new' && typeof V2 !== 'undefined' && V2[sc.id];
  const out = (useV2 ? V2[sc.id](br.id, vp) : sc.render(br.id, vp)) || {};
  const asBoard = useV2 ? (out.html == null) : sc.kind === 'board';

  let body;
  if (asBoard && !out.raw) {
    const stageInner = out.stage != null
      ? out.stage
      : (out.board == null
        ? ''
        : `<canvas class="boardcv" data-floor="${(out.board && out.board.floor) || 0}" data-board='${esc(JSON.stringify(out.board || {}))}'></canvas>`);
    body = `<div class="shell" data-zone="board-shell">
      <div class="stage-box${out.stage != null ? ' custom' : ''}" data-zone="board" style="position:relative">${stageInner}${out.stageOverlay || ''}</div>
      <aside class="rail">
        <div class="rail-module">${out.plate || ''}</div>
        <div class="rail-scroll" data-zone="right-rail-middle">${out.railBody || ''}${out.controls || ''}</div>
        <div class="rail-actions" data-zone="right-rail-actions">${out.actions || ''}</div>
      </aside>
    </div>`;
  } else {
    body = out.raw != null ? out.raw : `<div class="content"><div class="content-inner">${out.html || ''}</div></div>`;
  }

  const dialogs = ((sc.dialogs && S.dialog) ? (sc.dialogs[S.dialog] || '') : '') || out.scrim || '';
  const app = $('#app');
  app.dataset.vp = vp.id;
  app.dataset.mode = S.mode;
  app.style.width = vp.w + 'px';
  app.style.height = vp.h + 'px';
  app.innerHTML = topbar(vp) + `<div class="row">
      ${mobile ? '' : sidebar(sc.nav)}
      ${mobile || vp.sidebar === 0 && false ? '' : ''}
      <main class="main">${body}</main>
      ${mobile || S.mode === 'new' ? '' : `<button class="sidebar-toggle" aria-label="${vp.sidebar ? '收起导航' : '展开导航'}" aria-expanded="${vp.sidebar > 0}" data-act="${vp.sidebar ? '收起左侧导航' : '展开左侧导航（覆盖式）'}" data-src="GalaxySidebar.tsx:158">${icon(vp.sidebar ? 'ChevronLeft' : 'Menu')}</button>`}
    </div>` + (mobile ? bottomnav(sc.nav) : '') +
    (out.snack || '') +
    (S.snack ? `<div class="snack ${S.snack.kind} ${S.snack.pos || 'bottom'}">${esc(S.snack.text)}</div>` : '') +
    (dialogs ? `<div class="scrim" data-scrim="1">${dialogs}</div>` : '');

  scaleFrame(vp);
  paintBoards();
  readout(vp);
  buildDrawer(sc, br);
}

function scaleFrame(vp) {
  const wrap = $('#frameWrap');
  const avail = $('.stagecol').clientWidth - 44;
  const availH = window.innerHeight - 52 - 92;
  const k = Math.min(1, avail / vp.w, availH / vp.h);
  const app = $('#app');
  app.style.transform = `scale(${k})`;
  wrap.style.width = (vp.w * k) + 'px';
  wrap.style.height = (vp.h * k) + 'px';
  $('#scaleNote').textContent =
    (vp.stress ? '压扁档 · 不是验收视口，用来把右栏中段压到必须滚　' : '') +
    (k < .995 ? `显示缩放 ${(k * 100).toFixed(0)}%（几何按 ${vp.w}×${vp.h} 计算）` : '1:1');
}

function paintBoards() {
  $$('.boardcv').forEach(cv => {
    /* clientWidth/Height are layout px (a CSS transform does not change them)
       and include padding. Stage padding is 6px a side (BoardPageShell.tsx:82),
       then the board component subtracts its own 4px a side — the `-8` in
       LiveBoard.tsx:366. Same arithmetic, same result. */
    const st = cv.parentElement;
    const cw = st.clientWidth - 12, ch = st.clientHeight - 12;
    const edge = Math.floor(Math.min(cw, ch)) - 8;
    /* Each board component hard-codes its own floor and cap:
         LiveBoard        Math.max(minimumCanvasSize=400, min(1200, size))   LiveBoard.tsx:367
         Board (legacy)   Math.max(200, min(1200, size))                     Board.tsx:100
         TsumegoBoard     Math.max(400, min(1200, size))                     TsumegoBoard.tsx:93
       LiveMatchPage is the only caller that passes minimumCanvasSize={0}.
       Below the floor the board overflows its column instead of shrinking. */
    const floor = Number(cv.dataset.floor || 0);
    const px = Math.min(1200, Math.max(floor, Math.max(8, edge)));
    cv.width = px; cv.height = px;
    cv.style.width = px + 'px'; cv.style.height = px + 'px';
    cv.style.borderRadius = '2px';
    cv.dataset.edge = px;
    drawBoard(cv, JSON.parse(cv.dataset.board || '{}'));
  });
}

/* The readout the acceptance gate actually measures. Targets are the
   numbers the approved live template hit at each viewport, recorded in
   visual/live-template/geometry-implementation.json. A legacy page is
   compared against the same targets on purpose — the gap IS the finding. */
function readout(vp) {
  const cv = $('.boardcv');
  const rail = $('.rail') || $('.lrail');
  const sb = $('.sidebar');
  const tb = $('.topbar');
  const k = getScale();
  const set = (id, val, want) => {
    const el = $('#' + id); if (!el) return;
    const dd = el.querySelector('dd');
    if (val == null) { dd.textContent = '—'; dd.classList.remove('miss'); return; }
    const off = want != null && Math.abs(val - want) > 1;
    dd.textContent = off ? `${val} (${val > want ? '+' : ''}${val - want})` : String(val);
    dd.classList.toggle('miss', off);
  };
  set('roTop', tb ? Math.round(tb.getBoundingClientRect().height / k) : null, 52);
  set('roSide', sb ? Math.round(sb.getBoundingClientRect().width / k) : 0, vp.sidebar);
  const railWant = S.mode === 'new' ? (vp.id === '430x880' ? null : RAIL2) : vp.rail;
  set('roRail', rail ? Math.round(rail.getBoundingClientRect().width / k) : null, railWant);
  set('roBoard', cv ? Number(cv.dataset.edge) : null, currentScreen().noBoardTarget ? null : vp.board);
}
function getScale() {
  const m = /scale\(([\d.]+)\)/.exec($('#app').style.transform || '');
  return m ? parseFloat(m[1]) : 1;
}

/* ═══════════════════════════════════════════════════════════════
   Control drawer — generated FROM the rendered frame, so the count
   is evidence, not a claim.
   ═══════════════════════════════════════════════════════════════ */
const ZONE_CN = {
  'top-bar': '顶栏', 'sidebar': '左侧导航', 'bottom-nav': '底部导航',
  'page-header': '页头', 'board': '棋盘', 'board-shell': '棋盘壳',
  'right-rail-top': '右栏 · 模块牌', 'right-rail-middle': '右栏 · 中段',
  'right-rail-actions': '右栏 · 动作区', 'body': '正文', 'dialog': '对话框',
  'above-board': '棋盘上方（spec 禁止）', 'mobile-toolbar': '移动工具条',
};

function buildDrawer(sc, br) {
  const nodes = $$('#app [data-act], #app [data-toggle], #app [data-dialog], #app input, #app select');
  const rows = nodes.map(n => {
    const zoneEl = n.closest('[data-zone]');
    const zone = zoneEl ? zoneEl.dataset.zone : 'body';
    const label = (n.getAttribute('aria-label') || n.textContent || n.placeholder || n.getAttribute('data-act') || '').trim() || '（无标签）';
    const kind = n.classList.contains('sw') ? 'switch'
      : n.hasAttribute('aria-pressed') ? 'toggle'
      : n.classList.contains('iconbtn') ? 'icon-button'
      : n.classList.contains('card') ? 'card'
      : n.tagName === 'INPUT' ? (n.type === 'range' ? 'slider' : 'text-field')
      : n.tagName === 'SELECT' ? 'select' : 'button';
    return { label, zone, kind, src: n.dataset.src || '', act: n.dataset.act || '', el: n };
  });
  const byZone = {};
  rows.forEach((r, i) => { r.i = i; (byZone[r.zone] = byZone[r.zone] || []).push(r); });
  window.__rows = rows;

  $('#ctlCount').textContent = rows.length;
  $('#ctlScreen').textContent = sc.label + (sc.branches && sc.branches.length > 1 ? ' · ' + br.label : '');
  $('#ctlRoute').textContent = sc.route;
  $('#drawerBody').innerHTML = Object.keys(byZone).map(z => `
    <div class="zblock">
      <p class="zname">${ZONE_CN[z] || z}<em>${byZone[z].length}</em></p>
      ${byZone[z].map(r => `<button class="crow" data-i="${r.i}">
        <span class="ck">${esc(r.kind)}</span>
        <span class="cl">${esc(r.label)}</span>
        <span class="cs">${esc(r.src)}</span>
      </button>`).join('')}
    </div>`).join('');
}
