/* ═══════════════════════════════════════════════════════════════
   Console + interaction wiring
   ═══════════════════════════════════════════════════════════════ */
function buildPicker() {
  const groups = [];
  SCREENS.forEach(s => {
    let g = groups.find(x => x.name === s.group);
    if (!g) groups.push(g = { name: s.group, items: [] });
    g.items.push(s);
  });
  $('#pick').innerHTML = groups.map(g =>
    `<optgroup label="${esc(g.name)}">${g.items.map(s =>
      `<option value="${esc(s.id)}">${esc(s.label)}</option>`).join('')}</optgroup>`).join('');
  $('#pick').value = S.screen;
}

function buildBranches() {
  const sc = currentScreen();
  const bs = branchesOf(sc);
  $('#branchWrap').style.display = bs.length > 1 ? '' : 'none';
  $('#branches').innerHTML = bs.map(b =>
    `<button data-branch="${esc(b.id)}" aria-pressed="${b.id === currentBranch(sc).id}">${esc(b.label)}</button>`).join('');
}

function buildModes() {
  $$('#modes button').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.mode === S.mode)));
  const f = $('#modeFlag');
  f.textContent = S.mode === 'new' ? '统一版式：顶栏 52 / 左栏 216 / 右栏 320 / 棋盘吃满中间' : '照搬今天的代码';
  f.classList.toggle('now', S.mode !== 'new');
}

function buildDialogs() {
  const sc = currentScreen();
  const ds = sc.dialogs ? Object.keys(sc.dialogs) : [];
  $('#dlgWrap').style.display = ds.length ? '' : 'none';
  const CN = {
    leave: '离开对局', resign: '认输', count: '数子', countreq: '数子请求', end: '对局结束',
    result: '终局结果', del: '确认删除', imp: '导入棋谱', local: '本地导入 SGF',
    openmenu: '打开菜单', savemenu: '保存菜单', pass: '停一手', shape: '图形菜单',
    displace: '顶替确认', library: '棋谱库',
  };
  $('#dlgs').innerHTML = `<button data-dlg="" aria-pressed="${!S.dialog}">无</button>` +
    ds.map(d => `<button data-dlg="${esc(d)}" aria-pressed="${S.dialog === d}">${esc(CN[d] || d)}</button>`).join('');
}

function buildVps() {
  $('#vps').innerHTML = VPS.map(v =>
    `<button data-vp="${esc(v.id)}" aria-pressed="${v.id === S.vp}">${esc(v.label)}</button>`).join('');
}

function pushLog(label, act, src) {
  const t = new Date();
  S.log.unshift({
    time: `${String(t.getHours()).padStart(2, '0')}:${String(t.getMinutes()).padStart(2, '0')}:${String(t.getSeconds()).padStart(2, '0')}`,
    label, act, src,
  });
  S.log = S.log.slice(0, 60);
  $('#logCount').textContent = S.log.length;
  $('#logList').innerHTML = S.log.map(e =>
    `<li><span class="t">${esc(e.time)}</span><span class="a">${esc(e.label)}<em>→ ${esc(e.act || '（无动作）')}${e.src ? ' · ' + esc(e.src) : ''}</em></span></li>`).join('')
    || '<li class="empty">还没有点击。</li>';
}

function go(id, branch) {
  S.screen = id;
  S.dialog = null; S.snack = null;
  const sc = currentScreen();
  S.branch = branch || (sc.branches && sc.branches[0] ? sc.branches[0].id : 'default');
  $('#pick').value = id;
  buildBranches();
  buildDialogs();
  render();
}

function render() {
  const sc = currentScreen();
  $('#capRoute').textContent = sc.route;
  const n2 = (S.mode === 'new' && typeof NOTES2 !== 'undefined') ? NOTES2[sc.id] : null;
  $('#footnote').innerHTML = n2 || sc.note || '';
  renderFrame();
}

/* ── global click delegation ─────────────────────────────────── */
document.addEventListener('click', (ev) => {
  const t = ev.target;

  const seg = t.closest('#branches button');
  if (seg) { S.branch = seg.dataset.branch; S.dialog = null; buildBranches(); buildDialogs(); render(); return; }

  const db = t.closest('#dlgs button');
  if (db) { S.dialog = db.dataset.dlg || null; buildDialogs(); render(); return; }

  const mb = t.closest('#modes button');
  if (mb) {
    S.mode = mb.dataset.mode; S.dialog = null;
    const bs = branchesOf(currentScreen());
    if (!bs.some(x => x.id === S.branch)) S.branch = bs[0].id;
    buildModes(); buildBranches(); buildDialogs(); render(); return;
  }

  const sb2 = t.closest('#stress button');
  if (sb2) { S.stress = !S.stress; sb2.setAttribute('aria-pressed', String(S.stress)); render(); return; }

  const vb = t.closest('#vps button');
  if (vb) { S.vp = vb.dataset.vp; buildVps(); render(); return; }

  const crow = t.closest('.crow');
  if (crow) {
    const r = (window.__rows || [])[Number(crow.dataset.i)];
    if (r && r.el) {
      r.el.classList.remove('flash'); void r.el.offsetWidth; r.el.classList.add('flash');
      r.el.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
    }
    return;
  }

  if (t.closest('#app')) {
    const node = t.closest('[data-act],[data-toggle],[data-dialog],[data-goto],[data-close]');
    if (!node) return;

    if (node.hasAttribute('data-close')) { S.dialog = null; render(); return; }

    const label = (node.getAttribute('aria-label') || node.textContent || '').trim() || '（无标签）';
    pushLog(label, node.dataset.act || '', node.dataset.src || '');

    if (node.dataset.toggle) {
      const k = node.dataset.toggle;
      S.toggles[k] = !(S.toggles[k] != null ? S.toggles[k] : node.getAttribute('aria-pressed') === 'true' || node.getAttribute('aria-checked') === 'true');
      render(); return;
    }
    if (node.dataset.dialog) { S.dialog = node.dataset.dialog; buildDialogs(); render(); return; }
    if (node.dataset.goto) { const [id, b] = node.dataset.goto.split('#'); go(id, b); return; }
    return;
  }
}, false);

document.addEventListener('change', (ev) => {
  const t = ev.target;
  if (t.id === 'pick') { go(t.value); return; }
  if (t.closest('#app')) {
    const label = (t.getAttribute('aria-label') || t.previousElementSibling?.textContent || t.name || '输入').trim();
    pushLog(label, (t.dataset.act || '') + ' = ' + t.value, t.dataset.src || '');
  }
});

document.addEventListener('keydown', (ev) => {
  if (ev.key === 'Escape' && S.dialog) { S.dialog = null; buildDialogs(); render(); }
});

let rz;
window.addEventListener('resize', () => { clearTimeout(rz); rz = setTimeout(render, 120); });

/* ── boot ────────────────────────────────────────────────────── */
S.screen = SCREENS[1].id;
S.branch = SCREENS[1].branches ? SCREENS[1].branches[0].id : 'default';
buildPicker(); buildVps(); buildModes();
measureAll();                       /* fills the overview table from real layout */
S.screen = SCREENS[0].id; S.branch = 'default';
$('#pick').value = S.screen;
buildBranches(); buildDialogs(); render();
$('#logCount').textContent = 0;
