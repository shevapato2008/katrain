// ---------- 视觉实验室 · 训练与模型 ----------
const TR = {
  scenario: 'ready', dataset: 'ds-0925-03', weights: 'yolo11m', aug: 'stones-standard', gpu: '0',
  params: { epochs: 60, batch: 8, imgsz: 960, seed: 0 }, run: null, history: [], models: [{ id: 'model-0924-01', run: 'run-0924-a1', classes: 'black · white · led_red · led_green', map: '0.91', sha: '9f2c…a1' }],
};
const TR_DS = [
  { id: 'ds-0925-03', label: 'ds-0925-03 · 指示灯四类 · 412 / 98', classes: 'black 0 · white 1 · led_red 2 · led_green 3', sha: '3b7e…c4' },
  { id: 'ds-0924-02', label: 'ds-0924-02 · 无灯双类 · 230 / 56', classes: 'black 0 · white 1', sha: 'a90d…17' },
];
PROTO.push({ id: 'tr', page: 'training', title: '训练服务场景', options: [['ready', '服务已核实（示意）'], ['disabled', '训练能力未启用'], ['fail', '让当前运行失败']], get: () => TR.scenario, set: (v) => { if (v === 'fail') { if (TR.run && TR.run.state === 'running') { TR.run.state = 'failed'; TR.run.error = 'CUDA out of memory'; TR.run.log.push('[epoch ' + TR.run.epoch + '] CUDA out of memory; run failed'); } return; } TR.scenario = v; } });
const TRS = { starting: '启动中', running: '运行中', cancelling: '正在取消', cancelled: '已取消', failed: '失败', completed: '完成' };
pages.training = {
  render() {
    const enabled = TR.scenario !== 'disabled';
    const r = TR.run; const busy = r && ['starting', 'running', 'cancelling'].includes(r.state);
    const ds = TR_DS.find((d) => d.id === TR.dataset);
    const locked = !enabled || busy;
    const opt = (list, cur) => list.map(([v, t]) => `<option value="${v}" ${v === cur ? 'selected' : ''}>${t}</option>`).join('');
    const icon = !r ? 'help' : r.state === 'failed' ? 'fail' : r.state === 'completed' ? 'check' : r.state === 'cancelled' ? 'stop' : 'pulse';
    const metric = (v) => v == null ? '—' : v.toFixed(2);
    return `<main class="lab-page"><div class="lab-heading"><div><h1>训练与模型</h1><p>测试机 home-ubuntu · 单卡训练运行与模型版本</p></div><span class="lab-status ${enabled ? 'ok' : ''}">${ic(enabled ? 'check' : 'help')}${enabled ? '训练服务 · 已核实（示意）' : '训练能力未启用'}</span></div>
      <div class="lab-content">
        ${!enabled ? `<div class="banner info">${ic('info')}<span>仅测试机 test 环境、显式启用并核实 GPU 预留后可训练；Mac 本机始终禁用，本页不会暗中连接远端。</span></div>` : ''}
        <div class="tr-grid">
          <section class="panel"><div class="panel-head"><h2>创建训练运行</h2><small>固定参数 · 单卡</small></div><form class="tr-form" data-submit="tr-create">
            <label class="field">冻结数据集<select data-change="tr-ds" ${locked ? 'disabled' : ''}>${enabled ? opt(TR_DS.map((d) => [d.id, d.label]), TR.dataset) : '<option>尚无已核实的测试机数据集</option>'}</select></label>
            <div class="tr-schema">${enabled ? `${ds.classes}<br>清单 SHA-256 ${ds.sha}（示意）` : '类目与清单哈希：尚未读取'}</div>
            <div class="tr-row"><label class="field">预训练权重<select data-change="tr-w" ${locked ? 'disabled' : ''}>${enabled ? opt([['yolo11m', 'YOLO11m · 已校验'], ['yolo11s', 'YOLO11s · 已校验']], TR.weights) : '<option>待校验权重</option>'}</select></label><label class="field">增强方案<select data-change="tr-aug" ${locked ? 'disabled' : ''}>${enabled ? opt([['stones-standard', '棋子标准'], ['led-safe-blur', 'LED 安全模糊']], TR.aug) : '<option>待核实类目</option>'}</select></label></div>
            <label class="field">训练 GPU<select data-change="tr-gpu" ${locked ? 'disabled' : ''}>${enabled ? opt([['0', 'GPU 0 · 已登记预留单卡'], ['1', 'GPU 1 · 已登记预留单卡']], TR.gpu) : '<option>尚未核实可预留 GPU</option>'}</select></label>
            <details class="tr-adv" data-key="tr-adv"><summary>训练参数 · ${TR.params.epochs} epoch · ${TR.params.imgsz} px · batch ${TR.params.batch} · seed ${TR.params.seed}</summary><div class="tr-row"><label class="field">Epoch<input type="number" min="1" max="300" value="${TR.params.epochs}" data-change="tr-p" data-k="epochs" ${locked ? 'disabled' : ''}></label><label class="field">Batch<select data-change="tr-p" data-k="batch" ${locked ? 'disabled' : ''}>${opt([['8', '8'], ['4', '4']], String(TR.params.batch))}</select></label></div><div class="tr-row" style="margin-top:10px"><label class="field">图像尺寸<select data-change="tr-p" data-k="imgsz" ${locked ? 'disabled' : ''}>${opt([['960', '960'], ['640', '640']], String(TR.params.imgsz))}</select></label><label class="field">Seed<input type="number" value="${TR.params.seed}" data-change="tr-p" data-k="seed" ${locked ? 'disabled' : ''}></label></div></details>
            <p class="note">${!enabled ? '训练能力未启用；远程访问与真实训练均需单独授权。' : busy ? '已有运行，参数锁定；取消须确认本运行进程组退出后才释放单卡。' : '仅使用已冻结校验的数据集、登记本地权重与预留单卡；不允许隐式下载。'}</p>
            <button class="btn primary full" type="submit" ${enabled && !busy ? '' : 'disabled'}>${!enabled ? '创建运行 · 未启用' : busy ? '已有运行 · 不并行启动' : '创建新运行'}</button></form></section>
          <div style="display:grid;gap:12px">
            <section class="panel"><div class="panel-head"><h2>当前运行</h2>${TR.history.length ? `<label class="field" style="flex-direction:row;display:flex;align-items:center;gap:8px">运行历史<select data-change="tr-hist" style="width:170px">${TR.history.map((h) => `<option value="${h.id}" ${r && r.id === h.id ? 'selected' : ''}>${h.id} · ${TRS[h.state]}</option>`).join('')}</select></label>` : ''}<span class="lab-status ${r && r.state === 'failed' ? 'warn' : 'ok'}">${ic(icon)}${r ? TRS[r.state] : '尚无运行'}</span></div>
              ${!r ? `<div class="tr-empty"><strong>${enabled ? '尚无训练运行' : '尚未读取训练服务'}</strong><p>没有核实结果时，不展示在线设备、日志或指标。创建与取消都需要明确确认。</p></div>` : `<div class="tr-run">
                <div class="tr-runid">${r.id} · 上次观察 ${r.observed}</div>
                <div class="tr-progress-row"><strong>${r.state === 'completed' ? '训练结束' : r.state === 'failed' ? `在 Epoch ${r.epoch} 失败` : r.state === 'cancelled' ? '已取消运行' : r.state === 'cancelling' ? '正在取消 · 等待本运行进程组退出' : r.state === 'starting' ? '正在启动独立运行' : `Epoch ${r.epoch} / ${r.total}`}</strong><span>${r.state === 'completed' ? `${r.total} / ${r.total}` : r.state === 'failed' ? '未发布新模型' : r.state === 'cancelled' ? '进程已退出' : Math.round(r.epoch / r.total * 100) + '%'}</span></div>
                <div class="progress"><i style="width:${Math.round(r.epoch / r.total * 100)}%"></i></div>
                <dl class="tr-metrics"><div><dt>mAP50</dt><dd>${metric(r.map)}</dd></div><div><dt>Precision</dt><dd>${metric(r.p)}</dd></div><div><dt>Recall</dt><dd>${metric(r.rc)}</dd></div></dl>
                <p class="note">${r.map == null ? '尚无验证指标；不填 0，不从其他运行复制。' : '指标来自本运行的验证观察（示意）；模型只在产物校验后发布。'}</p>
                <div class="tr-meta"><span>GPU ${r.gpu} · 单卡</span><span>imgsz ${r.imgsz} · batch ${r.batch} · seed ${r.seed}</span><span>数据集 ${r.ds}</span></div>
                ${r.state === 'failed' ? `<div class="banner bad">${ic('fail')}<span><strong>${r.error}</strong><br>本运行已退出；未发布新模型，旧版本保留。调整配置后可显式新建，不会自动重启。</span></div>` : ''}
                <pre class="tr-log" aria-label="运行日志">${esc(r.log.slice(-8).join('\n'))}</pre>
                <div class="row" style="justify-content:flex-end">${r.state === 'running' ? '<button class="btn" data-act="tr-cancel">取消此运行</button>' : ''}${r.state === 'failed' || r.state === 'cancelled' ? '<button class="btn" data-act="tr-create">按当前配置新建</button>' : ''}</div></div>`}</section>
            <section class="panel tr-models"><div class="panel-head"><h2>模型版本</h2><small>校验通过后只读保存</small></div>${enabled && TR.models.length ? `<table aria-label="模型版本"><thead><tr><th>版本 / 来源</th><th>类目 / 验证</th><th>Mac 获取</th></tr></thead><tbody>${TR.models.map((m) => `<tr><td>${m.id}<small>${m.run}</small></td><td>${m.classes}<small>mAP50 ${m.map} · best.pt SHA-256 ${m.sha}</small></td><td><button class="btn small" disabled>下载到本机 · 待授权</button></td></tr>`).join('')}</tbody></table>` : `<div class="empty">${enabled ? '尚无已校验发布的模型。' : '尚未读取真实模型版本。'}</div>`}</section>
          </div></div>
        <p class="dg-foot">只允许已冻结且清单校验一致的数据集。首版一次一运行、单 GPU；双卡 DDP 尚未验证。数据与指标均为原型示意。</p>
      </div></main>`;
  },
};
actions['tr-ds'] = (el) => { TR.dataset = el.value; render(); };
actions['tr-w'] = (el) => { TR.weights = el.value; };
actions['tr-aug'] = (el) => { TR.aug = el.value; };
actions['tr-gpu'] = (el) => { TR.gpu = el.value; };
actions['tr-p'] = (el) => { TR.params[el.dataset.k] = Math.max(1, +el.value || 0) || 0; if (el.dataset.k === 'seed') TR.params.seed = +el.value || 0; render(); };
actions['tr-hist'] = (el) => { TR.run = TR.history.find((h) => h.id === el.value); render(); };
actions['tr-create'] = () => {
  const p = TR.params;
  confirmModal({ title: '创建单卡训练运行', body: `<p>数据集 ${TR.dataset} · ${TR.weights} · ${TR.aug} · GPU ${TR.gpu}<br>${p.epochs} epoch · imgsz ${p.imgsz} · batch ${p.batch} · seed ${p.seed}</p><p class="note">只启动一个独立进程组；不抢占 KataGo，不下载任何权重。原型只模拟进度。</p>`, accept: '创建运行', onAccept: () => {
    const id = 'run-0926-' + Math.random().toString(16).slice(2, 6);
    TR.run = { id, state: 'starting', epoch: 0, total: p.epochs, map: null, p: null, rc: null, gpu: TR.gpu, imgsz: p.imgsz, batch: p.batch, seed: p.seed, ds: TR.dataset, observed: nowTime(), log: ['[runner] dataset manifest verified', '[runner] local weights verified; no download'] };
    TR.history.unshift(TR.run);
    later(900, () => { if (TR.run.id === id && TR.run.state === 'starting') { TR.run.state = 'running'; TR.run.log.push(`[runner] GPU ${TR.gpu} reserved; process group started`); if (S.page === 'training') render(); } });
  } });
};
actions['tr-cancel'] = () => confirmModal({ title: '取消当前运行', body: `<p>只停止 ${TR.run.id} 的进程组，确认退出后才标为取消并释放单卡；不影响 KataGo 或其他 GPU 进程。</p>`, accept: '取消运行', onAccept: () => { const r = TR.run; r.state = 'cancelling'; later(1200, () => { r.state = 'cancelled'; r.log.push('[runner] process group exited after cancel'); if (S.page === 'training') render(); }); } });
every(400, () => {
  const r = TR.run; if (!r || r.state !== 'running') return;
  r.epoch = Math.min(r.total, r.epoch + 2); r.observed = nowTime();
  if (r.epoch >= 10) { const t = r.epoch / r.total; r.map = 0.62 + 0.3 * t; r.p = 0.66 + 0.28 * t; r.rc = 0.6 + 0.3 * t; }
  r.log.push(`[epoch ${r.epoch}/${r.total}] box_loss ${(1.4 - r.epoch / r.total).toFixed(3)}${r.map ? ' mAP50 ' + r.map.toFixed(3) : ''}`);
  if (r.epoch >= r.total) { r.state = 'completed'; r.log.push('[runner] best.pt + schema + manifest verified; published'); TR.models.unshift({ id: 'model-0926-' + pad2(TR.models.length + 1), run: r.id, classes: TR_DS.find((d) => d.id === r.ds).classes.replace(/ \d/g, '').replace(/ ·/g, ' ·'), map: r.map.toFixed(2), sha: Math.random().toString(16).slice(2, 6) + '…' + Math.random().toString(16).slice(2, 4) }); }
  if (S.page === 'training' && !S.modal) render();
});

// ---------- 视觉实验室 · 本机部署与诊断 ----------
const STAGES = [
  { title: '原图 / 标定叠图', short: '原图', tag: '本轮锚点', what: '本轮处理批次的锚点原帧，叠加锁定几何的四角与边框。不另取一张“最新图”。', note: '只用于核对标定是否贴合；模型不直接看这张图。' },
  { title: '纯 warped', short: '纯 warped', tag: '平均前', what: '本轮原帧按锁定几何做透视校正，保留生产 margin。', note: '这是平均和增强之前的单帧，不是 YOLO 的实际输入。' },
  { title: '模型 NMS 后框', short: 'NMS 后框', tag: '去重前', what: '底图是实际输入：最多 8 帧平均 + CLAHE。框是模型 NMS 之后、业务去重之前的全部检测。', note: '重复框与阴影误检会在下一阶段剔除。' },
  { title: '业务筛选后框', short: '筛选后框', tag: '去重后', what: '业务去重 + 阴影剔除后的框，分 keep / sustain 两档。', note: 'sustain 档只维持已有棋子，不单独产生新子；画出的框不等于全部参与赋值。' },
  { title: '原始定位投影 · 诊断派生', short: '原始投影', tag: '诊断派生', what: '把筛选后框的原始连续网格坐标按最近点落格；越界丢弃，同格取最高置信度。', note: '不是生产中间结果：不做视差、历史、掩码修正，也不回灌状态。' },
  { title: '纠偏后棋盘', short: '纠偏后', tag: '实际赋值', what: '本轮唯一一次 detections_to_board() 的返回值，含视差修正和占位冲突处理。', note: '与上一阶段的差异就是纠偏逻辑的效果。' },
  { title: '最终发布棋盘', short: '最终发布', tag: '两帧稳定', what: '逐格两帧投票 → 否认掩码 → 参考检查之后实际发布的棋盘。', note: 'viewer 不绑定对局：参考检查与落子确认未参与，不产生第八张盘。' },
];
const DG = { state: 'auto', stage: 0, current: 'local-0926-02', previous: 'local-0924-01', selected: 'local-0926-02', loadFailed: false, batch: 24, observed: '14:32:08', staleFor: 8 };
const DG_MODELS = { 'local-0926-02': { label: 'local-0926-02 · 四类 · mAP50 0.93', sha: 'e41b…7d' }, 'local-0924-01': { label: 'local-0924-01 · 四类 · mAP50 0.91', sha: '9f2c…a1' } };
PROTO.push({ id: 'dg', page: 'diagnostics', title: '诊断场景', options: [['auto', '跟随采集页设备状态'], ['ready', '设备就绪'], ['running', '诊断中'], ['stale', '快照陈旧'], ['loadfail', '模型加载失败']], get: () => DG.loadFailed ? 'loadfail' : DG.state, set: (v) => { if (v === 'loadfail') { DG.loadFailed = true; DG.state = 'ready'; } else { DG.loadFailed = false; DG.state = v; } } });
const dgState = () => DG.state !== 'auto' ? DG.state : CAP.device === 'connected' && CAP.calib === 'done' && !CAP.stale ? 'ready' : 'unconnected';
function dgStones() { const base = boardAfter(21); return base; }
function stageVisual(i, big = true) {
  const stones = dgStones(); const moved = stones[9], missing = stones[14];
  const bg = '#d8c49b';
  if (i === 0) return rawSVG({ stones, corners: true, label: '原图与标定叠图（合成示意）' });
  const wrap = (svg) => `<div style="height:100%;aspect-ratio:1">${svg}</div>`;
  if (i === 1) return wrap(boardSVG({ stones, bg: '#cdb88e', label: '纯 warped（合成示意）' }));
  if (i === 2) return wrap(boardSVG({ stones, bg: '#e2cc9c', boxes: stones.map((s) => ({ x: s.x, y: s.y, c: s.c })).concat([{ x: moved.x, y: moved.y, c: 'W', dx: 0.32 }, { x: 4, y: 10, c: 'B' }]), label: 'NMS 后框（合成示意）' }));
  if (i === 3) return wrap(boardSVG({ stones, bg: '#e2cc9c', boxes: stones.map((s, k) => ({ x: s.x, y: s.y, c: s.c, tier: k === 14 ? 'sustain' : 'keep' })), label: '业务筛选后框（合成示意）' }));
  if (i === 4) return wrap(boardSVG({ stones: stones.map((s) => s === moved ? { ...s, x: s.x + 1 } : s), marks: [{ x: moved.x + 1, y: moved.y, color: '#d14b3f' }], bg, label: '原始定位投影（合成示意）' }));
  if (i === 5) return wrap(boardSVG({ stones, marks: [{ x: moved.x, y: moved.y, color: '#2f9c86' }], bg, label: '纠偏后棋盘（合成示意）' }));
  return wrap(boardSVG({ stones: stones.filter((s) => s !== missing), marks: [{ x: missing.x, y: missing.y, color: '#e39a3a' }], bg, label: '最终发布棋盘（合成示意）' }));
}
function stageFacts(i) {
  const stones = dgStones(); const moved = stones[9], missing = stones[14];
  const b = stones.filter((s) => s.c === 'B').length, w = stones.length - b;
  return [
    [['原帧', `design-frame-0${DG.batch} · 1600×760`], ['几何', 'grid-04 · 四角已锁定'], ['与上一阶段', '—（批次锚点）']],
    [['尺寸', '960×960 · 含 margin'], ['来源', '同一原帧，未平均'], ['与上一阶段', '仅做透视校正']],
    [['检测框', `${stones.length + 2} 个 · black ${b + 1} · white ${w + 1}`], ['贡献帧', `8 帧 · frame-0${DG.batch - 7} … 0${DG.batch}`], ['与上一阶段', '换成平均 + CLAHE 底图']],
    [['保留框', `${stones.length} 个 · keep ${stones.length - 1} · sustain 1`], ['剔除', `2 个 · 重复框 ${coord([moved.x, moved.y])} · 阴影 E9`], ['与上一阶段', '去重 −1、阴影 −1']],
    [['落格棋子', `${stones.length} 子`], ['异常', `${coord([moved.x, moved.y])} 的框落到了 ${coord([moved.x + 1, moved.y])}（红框）`], ['与上一阶段', '只读投影，不修正']],
    [['棋子', `${stones.length} 子`], ['纠偏', `视差修正把 ${coord([moved.x + 1, moved.y])} 拉回 ${coord([moved.x, moved.y])}（绿框）`], ['与原始投影', '1 格差异']],
    [['发布棋子', `${stones.length - 1} 子`], ['未稳定', `${coord([missing.x, missing.y])} 只出现 1 帧，投票未通过（橙框）`], ['参考检查', 'viewer 未参与']],
  ][i];
}
pages.diagnostics = {
  render() {
    const st = dgState(); const unknown = st === 'unconnected'; const active = st === 'running' || st === 'stale'; const stale = st === 'stale';
    const status = DG.loadFailed ? ['加载失败 · 诊断已停', 'warn', 'warn'] : ({ unconnected: ['未连接 · 未核实', 'help', ''], ready: ['已就绪', 'check', 'ok'], running: ['诊断中 · 2 Hz', 'pulse', 'ok'], stale: ['快照陈旧', 'warn', 'warn'] })[st];
    const cur = DG_MODELS[DG.current];
    const i = DG.stage; const s = STAGES[i];
    return `<main class="lab-page"><div class="lab-heading"><div><h1>本机部署与诊断</h1><p>Mac 本机 · 可信模型与识别链七阶段观察</p></div><span class="lab-status ${status[2]}">${ic(status[1])}${status[0]}</span></div>
      <div class="lab-content">
        <section class="panel dg-controls" aria-label="本机模型与诊断控制"><div class="dg-model-row">
          <div class="dg-version"><small>当前本机版本</small><strong>${unknown ? '尚未读取' : DG.current}</strong></div><div class="dg-version"><small>前一版本 · 保留</small><strong>${unknown ? '尚未读取' : DG.previous}</strong></div>
          <label class="dg-registered">登记模型<select data-change="dg-sel" ${unknown || active ? 'disabled' : ''} aria-describedby="dg-lock">${unknown ? '<option>尚无已核实的本机模型</option>' : Object.entries(DG_MODELS).map(([id, m]) => `<option value="${id}" ${id === DG.selected ? 'selected' : ''}>${m.label}</option>`).join('')}</select></label>
          <button class="btn" data-act="dg-activate" ${unknown || active ? 'disabled' : ''} aria-describedby="dg-lock">激活</button><button class="btn" data-act="dg-rollback" ${unknown || active ? 'disabled' : ''} aria-describedby="dg-lock">回滚</button><button class="btn" disabled>从测试机拉取 · 待授权</button></div>
          <div class="dg-run-row"><div class="dg-meta">${unknown ? '模型 manifest / 实际 imgsz / 类目：<strong>尚未核实</strong>' : `<span>manifest <strong>${cur.sha}</strong></span><span>实际 imgsz <strong>960</strong></span><span>类目 <strong>black 0 · white 1 · led_red 2 · led_green 3</strong></span><span>viewer · 不绑定对局</span>${active ? `<span class="dg-lock" id="dg-lock">${ic('lock')}诊断未停止 · 换模前请先停止</span>` : ''}`}</div>
            <button class="btn primary" data-act="dg-start" ${unknown || active ? 'disabled' : ''}>${ic('play')}${unknown ? '开始诊断 · 未就绪' : '开始诊断'}</button><button class="btn" data-act="dg-stop" ${active ? '' : 'disabled'}>${ic('stop')}停止诊断</button></div></section>
        ${DG.loadFailed ? `<div class="banner" role="alert">${ic('warn')}<span><strong>模型加载失败 · 诊断已停</strong> YOLO.names 与登记类目不一致（示意）。当前 ${DG.current} 与前一版仍保留；核实登记模型后重试。</span></div>` : ''}
        ${stale ? `<div class="banner" role="alert">${ic('warn')}<span><strong>运动跳过 · 整份旧快照</strong> 当前画面不是新观察；七个阶段仍来自同一旧批次，不拼接新原图与旧棋盘。停止后重新核实设备与标定。</span></div>` : ''}
        ${unknown ? `<div class="banner info">${ic('info')}<span>相机与标定由「采集与数据集」显式准备；这里不会自动打开设备。</span><button class="btn small" data-act="go" data-page="capture">去连接与标定</button></div>` : ''}
        <section class="panel" aria-label="七个处理阶段"><div class="tabs" role="tablist">${STAGES.map((x, k) => `<button class="tab" role="tab" data-act="dg-stage" data-i="${k}" aria-selected="${k === i}"><b>0${k + 1}</b>${x.short}</button>`).join('')}</div>
          <div class="dg-stage"><div class="viewer">${active ? `${stageVisual(i)}<span class="tag">0${i + 1} · ${s.title}</span><span class="stamp">${stale ? '整份旧快照 · ' : ''}合成示意，非相机实图</span>${i === 3 ? '<span class="legend"><span style="color:#5cc3ad"><i></i>keep</span><span style="color:#f1c07c"><i></i>sustain</span></span>' : ''}` : `<div class="empty-view">${ic(unknown ? 'help' : 'camera')}<span>${unknown ? '尚无已核实快照' : '等待显式开始诊断'}</span><small>${s.title}</small></div>`}</div>
            <aside class="dg-side"><div class="dg-batch ${stale ? 'stale' : ''}" aria-label="共享处理批次">${active ? `<div><strong>同一处理批次 · design-batch-0${DG.batch}</strong><p>原帧 design-frame-0${DG.batch} · 几何 grid-04 · 模型 ${DG.current} · 观察 ${DG.observed}${stale ? ` · ${DG.staleFor} 秒未更新` : ''}（示意）</p></div>` : `<div><strong>${unknown ? '没有可核实的处理批次' : '尚无诊断批次'}</strong><p>${unknown ? '设备、几何与模型未核实；不展示假画面。' : '确认后显式开始；七个阶段来自同一次真实识别。'}</p></div>`}
          <details data-key="dg-batch"><summary>批次来源与边界</summary><div class="pop">实际平均输入的贡献帧最多 8 帧，再 CLAHE。原图与纯 warp 锚定当前帧，第 3、4 阶段用平均 + CLAHE 底图。模型、几何与帧身份同轮保存，不再次推理。<br><strong>资源上限</strong>：底图 ≤3、长边 ≤960、每张 JPEG ≤1 MiB、每阶段 ≤4096 框、总响应 ≤8 MiB；超限报不可用，不裁剪冒充完整。</div></details></div><div><div class="kicker">阶段 ${i + 1} / 7 · ${s.tag}</div><h3>${s.title}</h3></div><dl><div><dt>这是什么</dt><dd>${s.what}</dd></div>${active ? stageFacts(i).map(([k, v]) => `<div><dt>${k}</dt><dd>${v}</dd></div>`).join('') : ''}<div><dt>注意</dt><dd>${s.note}</dd></div></dl><div class="row"><button class="btn small" data-act="dg-step" data-d="-1" ${i ? '' : 'disabled'}>← 上一阶段</button><button class="btn small" data-act="dg-step" data-d="1" ${i < 6 ? '' : 'disabled'}>下一阶段 →</button></div><div class="keys">键盘 1–7 直接切换，←/→ 前后切换</div></aside></div></section>
        <p class="dg-foot">viewer 只读观察 · 一次真实推理链、最多 2 Hz 展示 · 不绑定对局，不启 monitor，不提交棋步或驱动指示灯。切换设备、标定或模型前先停止并确认旧线程退出。</p>
      </div></main>`;
  },
  key(e) { if (/^[1-7]$/.test(e.key)) { DG.stage = +e.key - 1; render(); } else if (e.key === 'ArrowRight' && DG.stage < 6) { DG.stage++; render(); } else if (e.key === 'ArrowLeft' && DG.stage > 0) { DG.stage--; render(); } },
};
actions['dg-stage'] = (el) => { DG.stage = +el.dataset.i; render(); };
actions['dg-step'] = (el) => { DG.stage = Math.max(0, Math.min(6, DG.stage + +el.dataset.d)); render(); };
actions['dg-sel'] = (el) => { DG.selected = el.value; };
actions['dg-start'] = () => confirmModal({ title: '开始只读诊断', body: `<p>使用当前设备、锁定几何 grid-04 与本机模型 ${DG.current}，只开 viewer。</p>`, check: '我已理解 viewer 不参与对局、参考检查与落子确认。', accept: '确认开始', onAccept: () => { DG.loadFailed = false; DG.state = 'running'; } });
actions['dg-stop'] = () => { DG.state = 'ready'; DG.loadFailed = false; render(); };
const dgSwap = (next) => { if (next !== DG.current) { DG.previous = DG.current; DG.current = next; DG.selected = next; } };
actions['dg-activate'] = () => confirmModal({ title: '激活登记模型', body: `<p>激活 ${DG.selected}：先停止诊断并确认旧线程退出，再核对 hash / schema / imgsz。加载成功才替换当前版；失败保留旧版，诊断仍停止。</p>`, check: '我已确认停止旧诊断；理解加载失败不能替换当前版。', accept: '确认激活', onAccept: () => { DG.loadFailed = false; dgSwap(DG.selected); } });
actions['dg-rollback'] = () => confirmModal({ title: '回滚本机模型', body: `<p>回滚到 ${DG.previous}：同样先停止诊断、核对产物后加载；失败保留当前版。</p>`, check: '我已确认停止旧诊断；理解加载失败不能替换当前版。', accept: '确认回滚', onAccept: () => { DG.loadFailed = false; dgSwap(DG.previous); } });
every(500, () => { if (dgState() === 'running') { DG.batch += 1; DG.observed = nowTime(); if (S.page === 'diagnostics' && !S.modal) { const b = document.querySelector('.dg-batch'); if (b) b.querySelector('div').innerHTML = `<strong>同一处理批次 · design-batch-0${DG.batch}</strong><p>原帧 design-frame-0${DG.batch} · 几何 grid-04 · 模型 ${DG.current} · 观察 ${DG.observed}（示意）</p>`; } } });
