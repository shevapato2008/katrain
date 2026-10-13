// ---------- 视觉实验室 · 采集与数据集 ----------
// Extend the illustrative game with a real edge capture (moves 61–63) and quiet filler moves.
(() => {
  GAME.push({ n: 61, color: 'B', p: [18, 8] }, { n: 62, color: 'W', p: [18, 9] }, { n: 63, color: 'B', p: [18, 10], removes: [[18, 9]] });
  let seed = 7; const rnd = () => (seed = (seed * 16807) % 2147483647) / 2147483647;
  const used = new Set(GAME.map((m) => m.p.join(',')));
  while (GAME.length < 240) {
    const x = 1 + Math.floor(rnd() * 17), y = 1 + Math.floor(rnd() * 17), k = x + ',' + y;
    if (used.has(k) || k === '18,9') continue;
    used.add(k); GAME.push({ n: GAME.length + 1, color: GAME.length % 2 ? 'W' : 'B', p: [x, y] });
  }
})();
function boardAfter(count) {
  const map = new Map();
  GAME.slice(0, count).forEach((m) => { map.set(m.p.join(','), m.color); (m.removes || []).forEach((r) => map.delete(r.join(','))); });
  return [...map].map(([k, c]) => { const [x, y] = k.split(',').map(Number); return { x, y, c }; });
}
const KIFU = [
  { id: 'k1', title: '示例杯 决赛 第 1 局', black: '棋手甲 九段', white: '棋手乙 九段', date: '2025-11-02', moves: 211, result: '黑中盘胜' },
  { id: 'k2', title: '示例杯 决赛 第 2 局', black: '棋手乙 九段', white: '棋手甲 九段', date: '2025-11-04', moves: 176, result: '白中盘胜' },
  { id: 'k3', title: '示例联赛 第 7 轮', black: '棋手丙 七段', white: '棋手丁 六段', date: '2025-08-19', moves: 238, result: '白胜 1.5 目' },
  { id: 'k4', title: '示例新秀赛 半决赛', black: '棋手戊 四段', white: '棋手丙 七段', date: '2024-12-10', moves: 142, result: '黑中盘胜' },
  { id: 'k5', title: '示例名人战 挑战赛 第 3 局', black: '棋手丁 六段', white: '棋手甲 九段', date: '2024-06-21', moves: 199, result: '黑胜 3.5 目' },
  { id: 'k6', title: '示例团体赛 第 2 台', black: '棋手己 五段', white: '棋手戊 四段', date: '2023-09-30', moves: 88, result: '白中盘胜' },
];
const RESUMABLE = [
  { id: 's-0925-01', kifu: 'k3', mode: 'led', done: 23, geometry: 'grid-03', at: '09-25 21:14' },
  { id: 's-0924-02', kifu: 'k6', mode: 'plain', done: 88, geometry: 'grid-02', at: '09-24 19:40' },
];
const CAP = {
  device: 'none', camera: '0', mode: 'led', calib: 'none', geometry: 'grid-04', fiducial: 'every-move', stale: false, staleChecked: false,
  view: 'raw', grid: true, ledOverlay: true, frame: 18342,
  source: 'search', query: '', searched: true, selected: null, resumeSel: null, sgfName: '',
  session: null, advance: 'manual', placed: false, busy: '', auto: false, error: '', scenario: 'normal', frozen: [], reviewing: null,
};
PROTO.push({ id: 'cap-jump', page: 'capture', title: '快速进入', options: [['start', '从头开始'], ['mid', '采集进行中（第 12 手）'], ['removal', '提子步骤（第 63 手）']], get: () => CAP.jump || 'start', set: (v) => {
  CAP.jump = v; CAP.error = ''; CAP.busy = ''; CAP.auto = false; CAP.advance = 'manual'; CAP.placed = false;
  if (v === 'start') { CAP.device = 'none'; CAP.calib = 'none'; CAP.session = null; CAP.selected = null; CAP.stale = false; return; }
  CAP.device = 'connected'; CAP.mode = 'led'; CAP.calib = 'done'; CAP.stale = false; CAP.selected = 'k1'; CAP.view = 'raw';
  const n = v === 'mid' ? 11 : 62; newSession(capKifu('k1').title, 211, n, 0);
  for (let k = 0; k <= n; k++) CAP.session.samples.push(makeSample(k));
} });
PROTO.push({ id: 'cap', page: 'capture', title: '采集场景', options: [['normal', '一切正常'], ['camera-busy', '相机被 kiosk 占用'], ['led-missing', '指示灯串口未配置'], ['kifu-offline', '棋谱库不可用']], get: () => CAP.scenario, set: (v) => { CAP.scenario = v; CAP.error = ''; } });
const capKifu = (id) => KIFU.find((k) => k.id === id);
const nextIdx = () => CAP.session ? CAP.session.placed : 0; // number of moves already on the board
function ledFor(count) {
  const s = CAP.session; if (!s || CAP.mode !== 'led') return [];
  const out = [];
  const prev = GAME[count - 1];
  if (prev && prev.removes && s.pendingRemoval) { prev.removes.forEach(([x, y]) => out.push({ x, y, color: 'blue' })); return out; }
  const m = GAME[count]; if (m && count < s.total) out.push({ x: m.p[0], y: m.p[1], color: m.color === 'B' ? 'red' : 'green' });
  return out;
}
function capStones() { return CAP.session ? boardAfter(CAP.session.placed).concat(CAP.session.pendingRemoval ? (GAME[CAP.session.placed - 1].removes || []).map(([x, y]) => ({ x, y, c: 'W' })) : []) : []; }
function labelBoxes(sample) {
  const stones = boardAfter(sample.after);
  const boxes = stones.map((s) => ({ x: s.x, y: s.y, c: s.c }));
  const leds = sample.led ? [{ x: sample.led.x, y: sample.led.y, color: sample.led.color }] : [];
  return { boxes, leds, counts: { black: stones.filter((s) => s.c === 'B').length, white: stones.filter((s) => s.c === 'W').length, led_red: leds.filter((l) => l.color === 'red').length, led_green: leds.filter((l) => l.color === 'green').length } };
}
function viewerHTML() {
  if (CAP.device !== 'connected') return `<div class="viewer" style="height:540px"><div class="empty-view">${ic('camera')}<span>尚未连接本机摄像头</span><small>在右侧第 1 步显式连接；本页不会自动打开设备</small></div></div>`;
  const stones = capStones(); const leds = CAP.ledOverlay ? ledFor(nextIdx()) : [];
  if (CAP.view === 'raw') return `<div class="viewer" style="height:540px">${rawSVG({ stones, corners: CAP.calib === 'done' && CAP.grid, leds })}<span class="tag">原始相机画面 · 相机帧 #${CAP.frame}</span><span class="stamp">合成示意</span></div>`;
  if (CAP.calib !== 'done') return `<div class="viewer" style="height:540px"><div class="empty-view">${ic('box')}<span>等待空盘标定</span><small>未标定时不生成校正画面</small></div></div>`;
  if (CAP.view === 'warp') return `<div class="viewer" style="height:540px"><div style="height:100%;aspect-ratio:1">${boardSVG({ stones, grid: CAP.grid, leds: CAP.mode === 'led' ? leds : [], bg: '#d8c49b', label: 'warped 校正画面' })}</div><span class="tag">warped 校正 · 几何 ${CAP.geometry} · 同一相机帧</span><span class="stamp">合成示意</span>${leds.some((l) => l.color === 'blue') ? '<span class="legend"><span style="color:#8fb6ff">● 蓝灯闪烁 = 需提走的子</span></span>' : ''}</div>`;
  const s = CAP.session && CAP.session.samples[CAP.session.samples.length - 1];
  if (!s) return `<div class="viewer" style="height:540px"><div class="empty-view">${ic('layers')}<span>尚无样本</span><small>拍摄第一帧后显示自动标注叠框</small></div></div>`;
  const lb = labelBoxes(s);
  return `<div class="viewer" style="height:540px"><div style="height:100%;aspect-ratio:1">${boardSVG({ stones: boardAfter(s.after), boxes: lb.boxes, marks: lb.leds.map((l) => ({ x: l.x, y: l.y, color: l.color === 'red' ? '#e0473f' : '#46c46a' })), bg: '#d8c49b', label: '自动标注叠框' })}</div><span class="tag">最新样本 · ${esc(s.name)} · 按 SGF 真值自动标注</span><span class="legend"><span style="color:#5cc3ad"><i></i>black ${lb.counts.black}</span><span style="color:#7fa9dc"><i></i>white ${lb.counts.white}</span>${CAP.mode === 'led' ? `<span style="color:#ff8a80"><i></i>led_red ${lb.counts.led_red}</span><span style="color:#7fe29a"><i></i>led_green ${lb.counts.led_green}</span>` : ''}</span><span class="stamp">合成示意</span></div>`;
}
function stepState(n) {
  const connected = CAP.device === 'connected', calibrated = CAP.calib === 'done' && !CAP.stale, hasSession = !!CAP.session;
  const done = [connected, calibrated, hasSession, hasSession && CAP.session.complete][n - 1];
  const reachable = [true, connected, connected && calibrated, hasSession][n - 1];
  return done ? 'done' : reachable ? 'current' : 'locked';
}
function stepHead(n, title, chip) { return `<div class="step-head"><b>${stepState(n) === 'done' ? '✓' : n}</b>${title}${chip || ''}</div>`; }
function sourceHTML() {
  const locked = CAP.device !== 'connected' || CAP.calib !== 'done' || CAP.stale;
  const tab = (id, text) => `<button data-act="cap-source" data-v="${id}" aria-pressed="${CAP.source === id}">${text}</button>`;
  let body = '';
  if (CAP.source === 'search') {
    const q = CAP.query.trim().toLowerCase();
    const list = KIFU.filter((k) => !q || [k.title, k.black, k.white, k.date].join(' ').toLowerCase().includes(q));
    body = CAP.scenario === 'kifu-offline' ? `<div class="banner bad">${ic('warn')}<span><strong>棋谱库暂不可用</strong><br>本机后台连不上 kifu_albums。改用「导入 SGF」，或同步棋谱库后重试。</span></div>`
      : `<form class="row" data-submit="cap-search"><label class="field" style="flex:1">搜索棋谱库<input id="cap-q" placeholder="棋手、赛事、年份" value="${esc(CAP.query)}" data-input="cap-q" ${locked ? 'disabled' : ''}></label><button class="btn" type="submit" ${locked ? 'disabled' : ''}>${ic('search')}搜索</button></form>
        <div class="kifu-list" role="listbox" aria-label="棋谱搜索结果">${list.length ? list.map((k) => `<button class="kifu" data-act="cap-pick" data-id="${k.id}" aria-pressed="${CAP.selected === k.id}" ${locked ? 'disabled' : ''}><strong>${k.title}</strong><span>黑 ${k.black} · 白 ${k.white}</span><span>${k.date} · ${k.moves} 手 · ${k.result}</span></button>`).join('') : '<p class="note">没有匹配的棋谱，换个关键词试试。</p>'}</div>
        <p class="note">共 ${list.length} 局 · 原型示意数据；实际来自棋谱库（kifu_albums）。</p>`;
  } else if (CAP.source === 'sgf') {
    body = `<label class="field">SGF 文件<input type="file" accept=".sgf" data-change="cap-file" ${locked ? 'disabled' : ''}></label><p class="note">${CAP.sgfName ? `已读取 ${esc(CAP.sgfName)} · 19×19 · 按提子规则回放校验通过（示意）` : '只接受 19×19 棋谱；导入时回放校验落子与提子。'}</p>`;
  } else {
    body = `<div class="kifu-list">${RESUMABLE.map((r) => { const k = capKifu(r.kifu); return `<button class="kifu" data-act="cap-resume-pick" data-id="${r.id}" aria-pressed="${CAP.resumeSel === r.id}" ${CAP.device !== 'connected' ? 'disabled' : ''}><strong>${k.title}</strong><span>${r.mode === 'led' ? '指示灯 · 四类' : '无灯 · 双类'} · 已采 ${r.done} / ${k.moves} 手 · 几何 ${r.geometry}</span><span>上次采集 ${r.at}</span></button>`; }).join('')}</div><p class="note">恢复后必须复核标定：重连不代表视角没变。</p>`;
  }
  const pick = CAP.source === 'search' ? capKifu(CAP.selected) : CAP.source === 'sgf' && CAP.sgfName ? { title: CAP.sgfName, moves: 68 } : null;
  const startBtn = CAP.source === 'resume'
    ? `<button class="btn primary full" data-act="cap-resume" ${CAP.resumeSel && CAP.device === 'connected' ? '' : 'disabled'}>恢复会话</button>`
    : `<button class="btn primary full" data-act="cap-start" ${pick && !locked ? '' : 'disabled'}>${pick ? `开始采集 · ${esc(pick.title)} · ${pick.moves} 手` : '先选择一局棋谱'}</button>`;
  return `<div class="seg" role="group" aria-label="棋谱来源">${tab('search', '搜索棋谱库')}${tab('sgf', '导入 SGF')}${tab('resume', '恢复会话')}</div>${body}${CAP.session ? '' : startBtn}`;
}
function guideHTML() {
  const s = CAP.session;
  if (!s) return '<p class="note">先连接、标定并选定棋谱。</p>';
  const i = s.placed, m = GAME[i];
  const pct = Math.round((s.placed / s.total) * 100);
  const removal = s.pendingRemoval ? GAME[i - 1].removes : null;
  const initial = s.samples.length === 0;
  let card;
  if (initial) card = `<div class="next-move"><span class="stone ${m.color}"></span><strong>拍摄初始帧</strong><span>空盘 + 第 1 手指示灯（${m.color === 'B' ? '红灯' : '绿灯'} ${coord(m.p)}）</span></div>`;
  else if (removal) card = `<div class="next-move"><span class="stone W" style="background:#6c8fd6;box-shadow:none"></span><strong>提走 ${removal.length} 子：${removal.map(coord).join('、')}</strong><span>第 ${i} 手提子 · 蓝灯闪烁位置取走白子后拍照</span></div>`;
  else if (s.complete) card = `<div class="next-move"><span class="stone B" style="background:var(--ok)"></span><strong>本局采集完成</strong><span>共 ${s.samples.length} 帧 · 可在下方检查并冻结</span></div>`;
  else if (i >= s.total) card = `<div class="next-move"><span class="stone B" style="background:#6b6e72"></span><strong>拍摄终局帧</strong><span>最后一手已摆好 · 熄灭指示灯后拍照</span></div>`;
  else card = `<div class="next-move"><span class="stone ${m.color}"></span><strong>第 ${i + 1} 手 · ${m.color === 'B' ? '黑' : '白'} ${coord(m.p)}</strong><span>${CAP.mode === 'led' ? `${m.color === 'B' ? '红灯' : '绿灯'}已点亮 ${coord(m.p)} · 按灯位摆放` : `按 SGF 摆放 ${coord(m.p)}`}${m.removes ? ' · 落子后需提子' : ''}</span></div>`;
  const busy = CAP.busy;
  const confirmLabel = initial ? '拍摄初始帧' : removal ? '已提子 · 拍照' : i >= s.total ? '熄灯并拍摄终局帧' : '已摆好 · 拍照并进入下一手';
  const controls = s.complete ? '' : CAP.advance === 'camera' && !initial
    ? `<div class="banner info">${ic('camera')}<span>${CAP.auto ? '摄像头识别到落子后自动拍照并推进（移植自 kiosk 摆谱）' : '自动推进已暂停'}</span><button class="btn small" data-act="cap-auto">${CAP.auto ? '暂停' : '继续'}</button></div>`
    : `<label class="check"><input type="checkbox" data-change="cap-placed" ${CAP.placed ? 'checked' : ''} ${busy ? 'disabled' : ''}><span>${initial ? '棋盘已清空，只有指示灯亮着' : removal ? '已取走蓝灯位置的棋子，棋面与 SGF 一致' : '已按灯位摆好，棋面与 SGF 一致'}</span></label><button class="btn primary full" data-act="cap-shot" ${CAP.placed && !busy ? '' : 'disabled'}>${busy || confirmLabel}</button>`;
  return `${card}
    ${CAP.mode === 'led' && !s.complete ? `<div class="led-line"><span class="led-dot ${removal ? 'red' : i >= s.total ? 'off' : m.color === 'B' ? 'red' : 'green'}" ${removal ? 'style="background:#4f7fe0"' : ''}></span>${removal ? '蓝灯闪烁：需提走的子' : i >= s.total ? '指示灯将熄灭' : m.color === 'B' ? '红灯 = 下一手黑棋' : '绿灯 = 下一手白棋'}${CAP.fiducial === 'every-move' ? ' · 每手基准点校正' : ''}</div>` : ''}
    <div class="progress" aria-label="采集进度"><i style="width:${pct}%"></i></div><div class="note">已摆 ${s.placed} / ${s.total} 手 · 已采 ${s.samples.length} 帧 · 会话 ${s.id}</div>
    ${s.complete ? '' : `<div class="row"><div class="seg" role="group" aria-label="推进方式"><button data-act="cap-advance" data-v="manual" aria-pressed="${CAP.advance === 'manual'}">手动确认</button><button data-act="cap-advance" data-v="camera" aria-pressed="${CAP.advance === 'camera'}">摄像头自动推进</button></div></div>`}
    ${controls}
    ${s.complete ? '' : `<div class="row"><button class="btn small ghost" data-act="cap-back" ${s.samples.length > 1 && !busy ? '' : 'disabled'}>${ic('undo')}撤回上一帧</button><button class="btn small ghost" data-act="cap-end" ${s.samples.length ? '' : 'disabled'}>结束本局</button></div>`}`;
}
pages.capture = {
  render() {
    const connected = CAP.device === 'connected';
    const status = !connected ? ['未连接', 'help', ''] : CAP.stale ? ['恢复的标定待复核', 'warn', 'warn'] : CAP.calib !== 'done' ? ['已连接 · 待标定', 'camera', 'ok'] : [`Camera ${CAP.camera}${CAP.mode === 'led' ? ' · 指示灯' : ''} · 标定通过`, 'check', 'ok'];
    const tab = (id, text, extra = '') => `<button class="tab" role="tab" data-act="cap-view" data-v="${id}" aria-selected="${CAP.view === id}">${text}${extra}</button>`;
    const s = CAP.session;
    return `<main class="lab-page"><div class="lab-heading"><div><h1>采集与数据集</h1><p>Mac 本机 · 指示灯摆谱，采集 YOLO 训练帧</p></div><span class="lab-status ${status[2]}">${ic(status[1])}${status[0]}</span></div>
      <div class="lab-content">
        ${CAP.error ? `<div class="banner bad" role="alert">${ic('warn')}<span>${CAP.error}</span><button class="btn small" data-act="cap-dismiss">知道了</button></div>` : ''}
        <div class="cp-grid">
          <section class="panel cp-preview" aria-label="采集预览"><div class="tabs" role="tablist">${tab('raw', '原始画面')}${tab('warp', 'warped 校正')}${tab('label', '标注预览', s && s.samples.length ? ` <span class="chip">${s.samples.length}</span>` : '')}</div>
            ${viewerHTML()}
            <div class="cp-toolbar"><label class="check"><input type="checkbox" data-change="cap-grid" ${CAP.grid ? 'checked' : ''}>显示标定网格</label>${CAP.mode === 'led' ? `<label class="check"><input type="checkbox" data-change="cap-ledov" ${CAP.ledOverlay ? 'checked' : ''}>显示指示灯位置</label>` : ''}<span class="spacer"></span><span>预览最多 2 帧/秒 · 非训练视频</span></div></section>
          <aside class="panel cp-steps" aria-label="采集步骤">
            <div class="step ${stepState(1)}">${stepHead(1, '连接设备', connected ? '<span class="chip ok">已连接</span>' : '')}<div class="step-body">${connected ? `<div class="row"><span class="note" style="flex:1">Camera ${CAP.camera} · ${CAP.mode === 'led' ? '指示灯四类 · usbmodem1101' : '无灯双类'}<br>设备已占用，断开时释放</span>${CAP.mode === 'led' ? '<button class="btn small" data-act="cap-ledtest">测试点亮</button>' : ''}<button class="btn small" data-act="cap-disconnect" ${CAP.busy || s ? 'disabled' : ''}>断开</button></div>` : `
              <div class="row"><label class="field">摄像头<select data-change="cap-camera" ${connected ? 'disabled' : ''}><option value="0" ${CAP.camera === '0' ? 'selected' : ''}>Camera 0 · FaceTime HD</option><option value="1" ${CAP.camera === '1' ? 'selected' : ''}>Camera 1 · USB 1080p</option></select></label></div>
              <div class="seg" role="group" aria-label="采集模式"><button data-act="cap-mode" data-v="led" aria-pressed="${CAP.mode === 'led'}" ${connected ? 'disabled' : ''}>指示灯 · 四类</button><button data-act="cap-mode" data-v="plain" aria-pressed="${CAP.mode === 'plain'}" ${connected ? 'disabled' : ''}>无灯 · 双类</button></div>
              <p class="note">${CAP.mode === 'led' ? '类目 black / white / led_red / led_green；串口 /dev/cu.usbmodem1101（示意）。' : '类目 black / white；不点灯，不伪造 LED 类。'}</p>
              <button class="btn" data-act="cap-connect">连接摄像头${CAP.mode === 'led' ? '与指示灯' : ''}</button>`}
            </div></div>
            <div class="step ${stepState(2)}">${stepHead(2, '空盘标定', CAP.calib === 'done' && !CAP.stale ? `<span class="chip ok">${CAP.geometry}</span>` : CAP.stale ? '<span class="chip warn">待复核</span>' : '')}<div class="step-body">
              ${!connected ? '<p class="note">连接后清空棋盘再标定。</p>' : CAP.stale ? `<p class="note">恢复的几何 ${CAP.geometry} 待复核；在原始画面上检查网格是否贴合。</p><label class="check"><input type="checkbox" data-change="cap-stalecheck" ${CAP.staleChecked ? 'checked' : ''}><span>网格与棋盘贴合，视角没有变化</span></label><div class="row"><button class="btn" data-act="cap-stale-ok" ${CAP.staleChecked ? '' : 'disabled'}>确认保存的标定</button><button class="btn ghost" data-act="cap-recal-new">视角已变 · 重新标定</button></div>`
                : CAP.calib === 'done' && s ? `<div class="row"><span class="note" style="flex:1">标定通过 · 重投影 0.6 px${CAP.mode === 'led' ? ` · ${CAP.fiducial === 'every-move' ? '每手校正' : '不校正'}` : ''}（示意）</span></div>`
                : CAP.calib === 'done' ? `<p class="note">标定通过 · 19×19 · 重投影误差 0.6 px（示意）</p>${CAP.mode === 'led' ? `<label class="field">基准点校正<select data-change="cap-fiducial" ${s ? 'disabled' : ''}><option value="every-move" ${CAP.fiducial === 'every-move' ? 'selected' : ''}>每手校正（点亮空位基准点）</option><option value="off" ${CAP.fiducial === 'off' ? 'selected' : ''}>关闭（只用开局标定）</option></select></label>` : ''}<button class="btn ghost small" data-act="cap-calibrate" ${s ? 'disabled' : ''}>重新标定</button>`
                : `<p class="note">清空棋盘后开始；${CAP.mode === 'led' ? '标定时指示灯全部熄灭。' : '需要看到完整四角。'}</p><button class="btn" data-act="cap-calibrate" ${CAP.calib === 'running' ? 'disabled' : ''}>${CAP.calib === 'running' ? '正在检测棋盘四角…' : '开始空盘标定'}</button>`}
            </div></div>
            <div class="step ${stepState(3)}">${stepHead(3, '选择棋谱', s ? `<span class="chip ok">${esc(s.title)}</span>` : '')}<div class="step-body">${s ? `<p class="note">${esc(s.title)} · 共 ${s.total} 手 · 模式与几何在本会话内固定。</p>` : sourceHTML()}</div></div>
            <div class="step ${stepState(4)}">${stepHead(4, '逐手摆谱采集')}<div class="step-body">${guideHTML()}</div></div>
          </aside>
        </div>
        ${datasetHTML()}
      </div></main>`;
  },
};
function datasetHTML() {
  const s = CAP.session;
  const flagged = s ? s.samples.filter((x) => x.flag).length : 0;
  const n = s ? s.samples.length : 0;
  const canFreeze = s && n >= 3 && !flagged && !CAP.busy;
  return `<section class="panel cp-dataset"><div class="panel-head"><h2>数据集草稿</h2><small>检查叠框 → 冻结版本 → 上传测试机</small></div><div class="panel-body">
    ${s ? `<div class="ds-meta"><span>棋谱 <strong>${esc(s.title)}</strong></span><span>模式 <strong>${CAP.mode === 'led' ? '指示灯 · 四类' : '无灯 · 双类'}</strong></span><span>几何 <strong>${CAP.geometry}</strong></span><span>已采 <strong>${n}</strong> 帧</span><span>训练 / 验证 <strong>${Math.max(0, Math.round(n * 0.8))} / ${n - Math.max(0, Math.round(n * 0.8))}</strong>（按棋谱顺序分段，不随机拆连续帧）</span>${flagged ? `<span class="chip warn">${flagged} 帧待重拍</span>` : ''}</div>
      <div class="samples">${s.samples.slice().reverse().slice(0, 14).map((x) => `<button class="sample ${x.flag ? 'flag' : ''}" data-act="cap-review" data-id="${x.id}">${boardSVG({ stones: boardAfter(x.after), leds: x.led ? [x.led] : [], grid: false, bg: '#d8c49b', label: x.name })}<strong>${esc(x.name)}</strong><span>${x.flag ? '待重拍' : x.retaken ? '已重拍 · 帧 #' + x.frame : '帧 #' + x.frame}</span></button>`).join('')}${n > 14 ? `<span class="note" style="align-self:center">另有 ${n - 14} 帧</span>` : ''}</div>`
      : '<p class="note">还没有采集样本。开始会话后，每拍一帧都会按 SGF 真值自动生成标注。</p>'}
    <div class="ds-actions"><button class="btn primary" data-act="cap-freeze" ${canFreeze ? '' : 'disabled'}>冻结数据集版本</button><button class="btn" disabled>${ic('upload')}上传测试机 · 待授权</button><span class="note">${!s ? '' : flagged ? '有待重拍的帧，重拍后才能冻结。' : n < 3 ? '至少 3 帧才能冻结。' : '冻结会校验每张图、标签、类目和文件 SHA-256，冻结后只读。'}</span></div>
    ${CAP.frozen.length ? `<div class="ds-meta" style="flex-direction:column;gap:4px">${CAP.frozen.map((f) => `<span>${ic('check')} <strong>${f.id}</strong> · ${f.frames} 帧 · 训练 ${f.train} / 验证 ${f.val} · ${f.mode} · 待上传</span>`).join('')}</div>` : ''}
  </div></section>`;
}
actions['cap-view'] = (el) => { CAP.view = el.dataset.v; render(); };
actions['cap-grid'] = (el) => { CAP.grid = el.checked; render(); };
actions['cap-ledov'] = (el) => { CAP.ledOverlay = el.checked; render(); };
actions['cap-camera'] = (el) => { CAP.camera = el.value; };
actions['cap-mode'] = (el) => { CAP.mode = el.dataset.v; render(); };
actions['cap-dismiss'] = () => { CAP.error = ''; render(); };
actions['cap-connect'] = () => {
  if (CAP.scenario === 'camera-busy') { CAP.error = 'Camera ' + CAP.camera + ' 正被本机 kiosk 进程占用（设备租约冲突）。关闭 kiosk 采集后重试；后台不会抢占。'; render(); return; }
  if (CAP.scenario === 'led-missing' && CAP.mode === 'led') { CAP.error = '未配置指示灯串口（KATRAIN_ADMIN_VISION_LED_PORT）。配置后重启后台，或改用「无灯 · 双类」。'; render(); return; }
  CAP.error = ''; CAP.device = 'connected'; CAP.view = 'raw'; render();
};
actions['cap-disconnect'] = () => { CAP.device = 'none'; CAP.auto = false; render(); };
actions['cap-ledtest'] = () => confirmModal({ title: '测试点亮指示灯', body: '<p>依次点亮四个角和天元各 1 秒，用来确认串口与灯位映射。测试期间不拍照。</p>', accept: '开始测试', onAccept: () => { CAP.error = ''; } });
actions['cap-calibrate'] = () => { CAP.calib = 'running'; CAP.stale = false; render(); later(1100, () => { CAP.calib = 'done'; CAP.geometry = 'grid-' + pad2(+CAP.geometry.slice(5) + (CAP.session ? 0 : 1)); if (S.page === 'capture') render(); }); };
actions['cap-stalecheck'] = (el) => { CAP.staleChecked = el.checked; render(); };
actions['cap-stale-ok'] = () => { CAP.stale = false; CAP.staleChecked = false; render(); };
actions['cap-fiducial'] = (el) => { CAP.fiducial = el.value; render(); };
actions['cap-source'] = (el) => { CAP.source = el.dataset.v; render(); };
actions['cap-q'] = (el) => { CAP.query = el.value; };
actions['cap-search'] = () => { render(); };
actions['cap-pick'] = (el) => { CAP.selected = el.dataset.id; render(); };
actions['cap-file'] = (el) => { CAP.sgfName = el.files?.[0]?.name || ''; render(); };
actions['cap-resume-pick'] = (el) => { CAP.resumeSel = el.dataset.id; render(); };
function newSession(title, total, placed = 0, preSamples = 0) {
  const samples = [];
  for (let k = 0; k < preSamples; k++) samples.push(makeSample(k === 0 ? 0 : k));
  CAP.session = { id: 'cap-' + Math.random().toString(16).slice(2, 8), title, total, placed, samples, pendingRemoval: false, complete: false };
}
function makeSample(after, opts = {}) {
  const m = GAME[after];
  const led = CAP.mode === 'led' && !opts.final && m ? { x: m.p[0], y: m.p[1], color: m.color === 'B' ? 'red' : 'green' } : null;
  CAP.frame += 7;
  return { id: 'f' + CAP.frame, frame: CAP.frame, after, led, name: opts.name || (after === 0 ? '初始空盘' : `第 ${after} 手${opts.suffix || ''}`), flag: false, retaken: false };
}
actions['cap-start'] = () => {
  const k = CAP.source === 'search' ? capKifu(CAP.selected) : { title: CAP.sgfName, moves: 68 };
  confirmModal({ title: '开始采集会话', body: `<p><strong>${esc(k.title)}</strong> · ${k.moves} 手 · ${CAP.mode === 'led' ? '指示灯 · 四类' : '无灯 · 双类'} · 几何 ${CAP.geometry}</p><p class="note">新建独立会话；棋谱、模式与几何在会话内固定。样本写入 ~/.katrain/admin-vision，不会覆盖已有会话。</p>`, accept: '开始会话', onAccept: () => { newSession(k.title, k.moves); CAP.placed = false; CAP.view = CAP.mode === 'led' ? 'raw' : 'warp'; } });
};
actions['cap-resume'] = () => { const r = RESUMABLE.find((x) => x.id === CAP.resumeSel); const k = capKifu(r.kifu); CAP.mode = r.mode; CAP.geometry = r.geometry; CAP.calib = 'done'; CAP.stale = true; newSession(k.title, k.moves, r.done, Math.min(r.done + 1, 30)); CAP.session.samples.forEach((x, i) => { x.after = i; x.name = i ? `第 ${i} 手` : '初始空盘'; }); render(); };
actions['cap-placed'] = (el) => { CAP.placed = el.checked; render(); };
function shoot() {
  const s = CAP.session; const initial = s.samples.length === 0;
  CAP.busy = CAP.mode === 'led' ? '等待指示灯稳定后抓帧…' : '抓取新鲜相机帧…'; render();
  later(650, () => {
    CAP.busy = ''; CAP.placed = false;
    if (initial) s.samples.push(makeSample(0));
    else if (s.pendingRemoval) { s.pendingRemoval = false; s.samples.push(makeSample(s.placed, { suffix: ' · 提子后' })); }
    else if (s.placed >= s.total) { s.samples.push(makeSample(s.placed, { name: '终局 · 熄灯', final: true })); s.complete = true; CAP.auto = false; }
    else {
      s.placed += 1; const m = GAME[s.placed - 1];
      if (m.removes) s.pendingRemoval = true; else s.samples.push(makeSample(s.placed));
    }
    if (S.page === 'capture') render();
  });
}
actions['cap-shot'] = () => { if (CAP.placed) shoot(); };
actions['cap-advance'] = (el) => { CAP.advance = el.dataset.v; CAP.auto = CAP.advance === 'camera'; render(); };
actions['cap-auto'] = () => { CAP.auto = !CAP.auto; render(); };
every(1900, () => { if (S.page === 'capture' && CAP.session && CAP.advance === 'camera' && CAP.auto && !CAP.busy && !CAP.session.complete && CAP.session.samples.length && !S.modal) shoot(); });
every(500, () => { if (S.page === 'capture' && CAP.device === 'connected' && !S.modal && !CAP.busy) { CAP.frame += 1; const t = document.querySelector('.viewer .tag'); if (t && CAP.view === 'raw') t.textContent = '原始相机画面 · 相机帧 #' + CAP.frame; } });
actions['cap-back'] = () => confirmModal({ title: '撤回上一帧', body: '<p>撤回最近一帧并回到它之前的棋面。已写入的图片留在会话目录，清单不再引用它。</p>', check: '我会把棋盘恢复到上一帧的棋面。', accept: '撤回', onAccept: () => {
  const s = CAP.session; const x = s.samples.pop(); s.complete = false; s.pendingRemoval = false;
  if (x.name.includes('提子后')) s.pendingRemoval = true; else if (!x.name.startsWith('终局')) s.placed = Math.max(0, x.after - 1);
} });
actions['cap-end'] = () => confirmModal({ title: '结束本局采集', body: `<p>已采 ${CAP.session.samples.length} 帧。结束后不能继续追加，可检查并冻结。</p>`, accept: '结束本局', onAccept: () => { CAP.session.complete = true; CAP.auto = false; } });
actions['cap-review'] = (el) => {
  const s = CAP.session; const x = s.samples.find((y) => y.id === el.dataset.id); const lb = labelBoxes(x);
  S.modal = { title: `样本检查 · ${esc(x.name)}`, wide: true, checked: true, accept: x.flag ? '已恢复棋面 · 重拍此帧' : '标记为需重拍',
    body: `<div class="viewer" style="height:440px;border-radius:8px"><div style="height:100%;aspect-ratio:1">${boardSVG({ stones: boardAfter(x.after), boxes: lb.boxes, marks: lb.leds.map((l) => ({ x: l.x, y: l.y, color: l.color === 'red' ? '#e0473f' : '#46c46a' })), bg: '#d8c49b', label: '样本叠框' })}</div><span class="stamp">合成示意 · 帧 #${x.frame}</span></div>
      <div class="ds-meta" style="margin-top:10px"><span>black <strong>${lb.counts.black}</strong></span><span>white <strong>${lb.counts.white}</strong></span>${CAP.mode === 'led' ? `<span>led_red <strong>${lb.counts.led_red}</strong></span><span>led_green <strong>${lb.counts.led_green}</strong></span>` : ''}<span>几何 <strong>${CAP.geometry}</strong></span><span>文件 SHA-256 已校验</span></div>
      <p class="note">标签来自 SGF 棋面真值。框偏、漏灯或糊图就标记重拍；重拍只替换这一帧，不删除后续样本。</p>`,
    onAccept: () => { if (x.flag) { x.flag = false; x.retaken = true; CAP.frame += 3; x.frame = CAP.frame; } else x.flag = true; } };
  render();
};
actions['cap-freeze'] = () => {
  const s = CAP.session; const n = s.samples.length; const train = Math.round(n * 0.8);
  confirmModal({ title: '冻结数据集版本', body: `<p>${n} 帧 · 训练 ${train} / 验证 ${n - train} · ${CAP.mode === 'led' ? '四类' : '双类'}。</p><ul class="note" style="margin:0 0 8px;padding-left:1.2em"><li>每张图可读、标签有限且归一化、类目 ID 合法</li><li>训练 / 验证两侧非空，按棋谱顺序分段</li><li>SGF、几何与全部文件 SHA-256 写入清单</li></ul><p class="note">冻结后只读；失败时保留现有草稿。</p>`, check: '我已检查过有代表性的样本叠框。', accept: '冻结', onAccept: () => { CAP.frozen.unshift({ id: 'ds-0926-' + pad2(CAP.frozen.length + 1), frames: n, train, val: n - train, mode: CAP.mode === 'led' ? '指示灯四类' : '无灯双类' }); } });
};

actions['cap-recal-new'] = () => confirmModal({ title: '重新标定并新建会话', body: '<p>视角变化后旧几何不再可信。重新标定会结束恢复的会话（原会话文件保持不变），之后从第 3 步重新选择棋谱。</p>', accept: '重新标定', onAccept: () => { CAP.session = null; CAP.stale = false; CAP.staleChecked = false; actions['cap-calibrate'](); } });
