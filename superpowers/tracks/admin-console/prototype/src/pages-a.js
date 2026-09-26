// ---------- 教程管理 ----------
const TUT = {
  books: [{ name: '围棋入门教程（示意）', chapters: [
    { name: '第一章 基础概念', sections: [{ name: '1. 外势和实地', page: 3, figures: [{ caption: '图1中的黑1称为三三，是三线与三线的交叉点。', moves: [[3, 3, 'B'], [15, 15, 'W']], text: '在图 1 里，黑棋下在 1 位的这手棋叫做三三点。三三点的好处是比较容易做出眼形来活棋，不过它的不足之处在于朝着边上和中央发展的力量相对较弱。' }, { caption: '图2中白2是星位。', moves: [[3, 3, 'B'], [15, 3, 'W'], [15, 15, 'B']], text: '白 2 是四线与四线的交叉点，称之为“星”，也是外势线与外势线的交叉点。' }] },
      { name: '2. 棋子的气', page: 5, figures: [{ caption: '中腹一子有四口气。', moves: [[9, 9, 'B']], text: '一颗棋子在棋盘中间时，上下左右四个相邻交叉点都是它的气。' }] }] },
    { name: '第二章 吃子', sections: [{ name: '1. 打吃', page: 12, figures: [{ caption: '白1打吃，黑子只剩一口气。', moves: [[9, 9, 'B'], [9, 8, 'W'], [8, 9, 'W'], [10, 9, 'W']], text: '白 1 之后，黑子只剩下方一口气，这就是打吃。' }] }] },
  ] }],
  book: 0, chapter: 0, section: 0, figure: 0, move: 2, mode: 'detail', draft: null, textDraft: null,
  voice: {}, checked: {}, reviewed: {}, dirtyVideo: {}, notice: '', source: true,
};
const tutFig = () => { const b = TUT.books[TUT.book], c = b.chapters[TUT.chapter], s = c.sections[TUT.section]; return { b, c, s, f: s.figures[TUT.figure], key: [TUT.book, TUT.chapter, TUT.section, TUT.figure].join('-') }; };
pages.tutorial = {
  render() {
    const { b, c, s, f, key } = tutFig();
    const editingBoard = TUT.mode === 'board', editingText = TUT.mode === 'text';
    const moves = editingBoard ? TUT.draft : f.moves;
    const shown = editingBoard ? moves.length : Math.min(TUT.move, moves.length);
    const stones = moves.slice(0, shown).map(([x, y, cc]) => ({ x, y, c: cc }));
    const last = stones[stones.length - 1];
    const voice = TUT.voice[key] || 'none', reviewed = TUT.reviewed[key], checked = TUT.checked[key];
    const opt = (list, cur) => list.map((x, i) => `<option value="${i}" ${i === cur ? 'selected' : ''}>${esc(x.name)}</option>`).join('');
    return `<main class="admin-main"><div class="admin-heading"><div><div class="admin-title">教程管理</div><div class="admin-crumb">${esc(b.name)} / ${esc(c.name)} / ${esc(s.name)} / 图 ${TUT.figure + 1}</div></div><div class="admin-headcontrols"><select aria-label="选择教材" data-change="tut-book">${opt(TUT.books, TUT.book)}</select><select aria-label="选择章节" data-change="tut-chapter">${opt(b.chapters, TUT.chapter)}</select><select aria-label="选择小节" data-change="tut-section">${opt(c.sections, TUT.section)}</select></div></div>
      <div class="admin-workspace" style="${TUT.source ? '' : 'grid-template-columns:0 minmax(360px,1fr) 440px'}">
        <section class="admin-source" ${TUT.source ? '' : 'style="visibility:hidden"'}><div class="admin-panehead"><strong>原书页对照</strong><span>第 ${s.page} 页</span></div><div class="admin-book"><div class="admin-source-missing">此图没有原书页图片（示意）</div><div class="admin-sourcecaption">${esc(f.caption)}</div></div></section>
        <section class="admin-center"><div class="admin-boardbar"><strong>${esc(s.name)} · 棋图${editingBoard ? '编辑' : '预览'}</strong><span>当前第 ${shown} / ${moves.length} 手 · 棋图局部</span></div>
          <div class="admin-boardstage"><div style="width:min(100%,540px);aspect-ratio:1">${boardSVG({ stones, lastMove: last, clickable: editingBoard, bg: '#dfb66b', label: '棋图' })}</div></div>
          ${editingBoard ? `<div class="admin-editbar"><button class="admin-tool on">落子</button><button class="admin-tool" data-act="tut-undo" ${TUT.draft.length ? '' : 'disabled'}>撤销</button><span class="admin-edit-hint">草稿 ${TUT.draft.length} 手 · 点棋盘落子 · 未保存</span></div>` : ''}</section>
        <section class="admin-right"><div class="admin-rightscroll"><div class="admin-figuretitle"><button class="admin-back" aria-label="返回图列表" data-act="tut-fig" data-d="-1">←</button><div><h1>${esc(s.name)}</h1><div class="admin-sub">图 ${TUT.figure + 1} · 本节共 ${s.figures.length} 图</div></div><span class="admin-viewtag">编辑工作台</span></div>
          <div class="admin-pager"><button data-act="tut-fig" data-d="-1" ${TUT.figure ? '' : 'disabled'}>‹</button><span>图 ${TUT.figure + 1} / ${s.figures.length}</span><button data-act="tut-fig" data-d="1" ${TUT.figure < s.figures.length - 1 ? '' : 'disabled'}>›</button></div>
          <button class="admin-sourcebtn" data-act="tut-source">${TUT.source ? '▣ 收起原书页' : '▣ 对照原书页'}</button>
          ${TUT.notice ? `<div class="admin-feedback" style="margin-top:12px">${TUT.notice}</div>` : ''}
          <div class="admin-section"><div class="admin-label">手数</div><div class="admin-moves"><span>当前 ${shown} / ${moves.length}</span><span>逐手查看棋图</span></div><input class="admin-range" type="range" min="0" max="${moves.length}" value="${shown}" aria-label="棋图手数" data-input="tut-move" ${editingBoard ? 'disabled' : ''}></div>
          <div class="admin-section"><div class="admin-label"><span>语音讲解</span><span>文字与语音分开保存</span></div>${editingText ? `<textarea class="admin-editcopy" id="tut-text" aria-label="编辑语音讲解" data-input="tut-text">${esc(TUT.textDraft)}</textarea>` : `<p class="admin-copy">${esc(f.text)}</p>`}
            ${TUT.mode !== 'detail' ? '<div class="admin-draft-note" style="margin-top:12px">● 未保存的棋图和讲解不会影响公开页面</div>' : ''}
            <div class="admin-mini">讲解音频</div><div class="admin-media">${voice === 'generating' ? '语音生成中…（示意）' : voice === 'ready' ? '▶ 讲解音频 · 0:18（示意）' : '尚未生成讲解音频'}</div>
            <div class="admin-mini">配语音视频</div><div class="admin-media" style="height:64px">${TUT.dirtyVideo[key] ? '内容已修改 · 旧视频失效，需重新生成' : '配语音的视频尚未生成'}</div></div>
          <div class="admin-section"><div class="admin-label">审核状态</div><div class="admin-mini">${reviewed ? '✓ 已审核（示意）' : checked ? '已人工核对，可确认审核。' : '未审核。请核对原书页、棋图和讲解后确认。'}</div></div></div>
          ${TUT.mode === 'detail' ? `<div class="admin-actions"><button class="admin-action" data-act="tut-edit-board">编辑棋图</button><button class="admin-action" data-act="tut-edit-text">编辑讲解</button><button class="admin-action" data-act="tut-voice" ${voice === 'generating' ? 'disabled' : ''}>${voice === 'ready' ? '重新生成语音' : '生成语音'}</button><button class="admin-action" data-act="tut-check" ${checked || reviewed ? 'disabled' : ''}>人工核对完成</button><button class="admin-action wide" data-act="tut-review" ${checked && !reviewed ? '' : 'disabled'}>✓ ${reviewed ? '已审核' : '确认审核'}</button></div>`
            : `<div class="admin-actions"><button class="admin-action primary" data-act="tut-save">保存更改</button><button class="admin-action" data-act="tut-cancel">取消</button><button class="admin-action" disabled>生成语音</button><button class="admin-action" disabled>人工核对完成</button><button class="admin-action wide" disabled>✓ 确认审核</button></div>`}
        </section></div></main>`;
  },
};
const tutReset = () => { TUT.figure = 0; TUT.mode = 'detail'; TUT.notice = ''; TUT.move = tutFig().f.moves.length; };
actions['tut-book'] = (el) => { TUT.book = +el.value; TUT.chapter = 0; TUT.section = 0; tutReset(); render(); };
actions['tut-chapter'] = (el) => { TUT.chapter = +el.value; TUT.section = 0; tutReset(); render(); };
actions['tut-section'] = (el) => { TUT.section = +el.value; tutReset(); render(); };
actions['tut-fig'] = (el) => { const n = TUT.figure + +el.dataset.d; if (n < 0 || n >= tutFig().s.figures.length || TUT.mode !== 'detail') return; TUT.figure = n; TUT.move = tutFig().f.moves.length; TUT.notice = ''; render(); };
actions['tut-source'] = () => { TUT.source = !TUT.source; render(); };
actions['tut-move'] = (el) => { TUT.move = +el.value; render(); };
actions['tut-edit-board'] = () => { TUT.mode = 'board'; TUT.draft = tutFig().f.moves.slice(); TUT.notice = ''; render(); };
actions['tut-edit-text'] = () => { TUT.mode = 'text'; TUT.textDraft = tutFig().f.text; TUT.notice = ''; render(); };
actions['tut-place'] = (el) => { const x = +el.dataset.x, y = +el.dataset.y; if (TUT.draft.some(([a, b]) => a === x && b === y)) return; TUT.draft.push([x, y, TUT.draft.length % 2 ? 'W' : 'B']); render(); };
actions['tut-undo'] = () => { TUT.draft.pop(); render(); };
actions['tut-text'] = (el) => { TUT.textDraft = el.value; };
actions['tut-cancel'] = () => { TUT.mode = 'detail'; TUT.notice = '已放弃草稿，服务器版本未改动。'; render(); };
actions['tut-save'] = () => {
  const { f, key } = tutFig();
  if (TUT.mode === 'board') { f.moves = TUT.draft.slice(); TUT.move = f.moves.length; } else f.text = TUT.textDraft;
  TUT.mode = 'detail'; TUT.dirtyVideo[key] = true; TUT.checked[key] = false; TUT.reviewed[key] = false;
  TUT.notice = '已保存（原型）。内容变更后旧视频失效，审核状态重置。'; render();
};
actions['tut-voice'] = () => confirmModal({ title: '生成讲解语音', body: '<p>用当前讲解文字调用 TTS 生成音频，完成后替换旧音频。原型只模拟生成过程，不调用外部服务。</p>', accept: '开始生成', onAccept: () => { const { key } = tutFig(); TUT.voice[key] = 'generating'; later(1600, () => { TUT.voice[key] = 'ready'; if (S.page === 'tutorial') render(); }); } });
actions['tut-check'] = () => { TUT.checked[tutFig().key] = true; render(); };
actions['tut-review'] = () => confirmModal({ title: '确认审核', body: '<p>确认原书页、棋图与讲解一致。审核会同时导出训练样本（示意）。</p>', check: '我已逐手核对棋图并听过讲解音频。', accept: '确认审核', onAccept: () => { TUT.reviewed[tutFig().key] = true; TUT.notice = '审核已保存（原型）。'; } });

// ---------- 定时任务 ----------
const JOBS = [
  { id: 'cleanup', name: '系统 - 数据清理', purpose: '定期清理过期对局、孤立分析结果、已过期赛事预告和旧 cron 运行记录。', kind: '间隔 · 1 天', cadence: '每 1 天执行', state: 'failed', last: '11:52:41', dur: '1 ms', fails: 1, err: 'RuntimeError: 数据库连接超时（示意）', reason: '连续 1 次不成功，最近一次抛出了异常。', success: '暂无记录' },
  { id: 'fetch_list', name: '直播 - 赛事列表', purpose: '从已启用的对局来源同步直播列表，并更新对局的完赛状态。', kind: '间隔 · 30 分', cadence: '每 30 分执行', state: 'errors', last: '11:52:41', dur: '1 ms', fails: 1, err: '[fetch_list] 上游超时（示意）', reason: '最近一次运行记录了 1 条 ERROR。', success: '09/25 11:22:40' },
  { id: 'fetch_upcoming', name: '直播 - 赛事预告', purpose: '从已接入的赛事来源抓取预告，去重后更新即将开始的对局。', kind: '间隔 · 15 分', cadence: '每 15 分执行', state: 'overdue', last: '11:52:41', dur: '1 ms', fails: 0, err: '', reason: '已超过预期间隔 2 倍仍未运行。', success: '09/25 11:52:41' },
  { id: 'poll_moves', name: '直播 - 落子轮询', purpose: '检查直播对局的新落子，并为新增落子提交分析任务。', kind: '间隔 · 3 秒', cadence: '每 3 秒执行', state: 'overdue', last: '11:52:41', dur: '1 ms', fails: 0, err: '', reason: '已超过预期间隔 2 倍仍未运行。', success: '09/25 11:52:41' },
  { id: 'analyze', name: '直播 - 分析', purpose: '持续领取直播分析任务，用 KataGo 计算并写回分析结果。', kind: '常驻循环', cadence: '常驻循环', state: 'ok', last: '—', dur: '循环中', fails: 0, err: '', reason: '循环正常，最近心跳在预期内。', success: '—' },
  { id: 'poll_pandanet', name: '直播 - Pandanet 对局', purpose: '扫描 Pandanet-IGS 职业对局，获取新落子并提交分析任务。', kind: '间隔 · 5 分', cadence: '每 5 分执行', state: 'pending', last: '—', dur: '—', fails: 0, err: '', reason: '进程启动后尚未到第一次运行时间。', success: '暂无记录' },
  { id: 'report_analyze', name: '复盘 - 分析', purpose: '持续领取用户复盘任务，用 cron 侧 KataGo 逐手分析棋局。', kind: '常驻循环', cadence: '常驻循环', state: 'ok', last: '—', dur: '循环中', fails: 0, err: '', reason: '循环正常，最近心跳在预期内。', success: '—' },
  { id: 'translate', name: '直播 - 棋手译名', purpose: '为直播和赛事预告中缺少译名的棋手、赛事补齐译名。', kind: '间隔 · 1 小时', cadence: '每 1 小时执行', state: 'pending', last: '—', dur: '—', fails: 0, err: '', reason: '进程启动后尚未到第一次运行时间。', success: '暂无记录' },
  { id: 'tutorial_backup', name: '教程 - 备份', purpose: '定期导出教程相关数据表的压缩 JSON 快照，并清理过期快照。', kind: '间隔 · 1 天', cadence: '每 1 天执行', state: 'pending', last: '—', dur: '—', fails: 0, err: '', reason: '进程启动后尚未到第一次运行时间。', success: '暂无记录' },
];
const CRON = { scenario: 'mixed', open: null, sampled: '15:35:50', feedback: '' };
const CL = { ok: '正常', errors: '有报错', failed: '失败', offline: '失联', overdue: '该跑没跑', pending: '等待首次运行' };
const CS = { ok: '正常', errors: '报错', failed: '失败', offline: '失联', overdue: '逾期', pending: '待首跑' };
const CI = { ok: 'check', errors: 'warn', failed: 'fail', offline: 'wifi', overdue: 'clock', pending: 'wait' };
PROTO.push({ id: 'cron', page: 'cron', title: '定时任务场景', options: [['mixed', '有异常'], ['healthy', '全部正常'], ['offline', '进程失联'], ['api-error', '接口读取失败']], get: () => CRON.scenario, set: (v) => { CRON.scenario = v; CRON.feedback = ''; } });
pages.cron = {
  render() {
    const sc = CRON.scenario;
    const jobs = JOBS.map((j) => ({ ...j, state: sc === 'healthy' ? (j.state === 'pending' ? 'pending' : 'ok') : sc === 'offline' ? 'offline' : j.state }));
    const counts = {}; jobs.forEach((j) => counts[j.state] = (counts[j.state] || 0) + 1);
    const order = ['failed', 'offline', 'errors', 'overdue', 'pending', 'ok'];
    const ex = new Set(['failed', 'errors', 'offline', 'overdue']);
    const shown = [...jobs.filter((j) => ex.has(j.state)), ...jobs.filter((j) => !ex.has(j.state))];
    const open = jobs.find((j) => j.id === CRON.open);
    const st = (s) => sc === 'api-error' ? 'pending' : s;
    return `<main class="cron-page"><div class="cron-heading"><div><h1>定时任务</h1><div class="cron-sub">观察 cron 进程、任务和分析队列</div></div><div class="cron-heading-actions"><span>${sc === 'api-error' ? `数据停在 ${CRON.sampled} · 正在重试` : `采样于 ${CRON.sampled} · 每 15 秒刷新`}</span><button class="cron-refresh" data-act="cron-refresh">刷新状态</button></div></div>
      <div class="cron-content">${CRON.feedback ? `<div class="cron-feedback" role="status">${CRON.feedback}</div>` : ''}
        ${sc === 'offline' || sc === 'api-error' ? `<div class="cron-notice" role="alert"><strong>${sc === 'offline' ? 'cron 进程失联' : '任务状态读取失败'}</strong><span>${sc === 'offline' ? '最后心跳已超过 120 秒，正在保留最后采样的运行时间供排查。' : `上次成功读取于 ${CRON.sampled} · 当前显示的是旧数据`}</span></div>` : ''}
        <div class="cron-process"><div class="cron-overview-card"><div class="cron-eyebrow">CRON 进程</div><div class="cron-process-strong ${sc === 'api-error' ? 'uncertain' : sc === 'offline' ? 'offline' : 'online'}">${ic(sc === 'api-error' ? 'warn' : sc === 'offline' ? 'wifi' : 'pulse', 'cron-icon')}${sc === 'api-error' ? '状态待确认' : sc === 'offline' ? '进程失联' : '进程在线'}</div><div class="cron-process-small">${sc === 'offline' ? '最后心跳 3 分 12 秒前' : '心跳 5 秒前 · 11:52 启动'}</div></div>
          <div class="cron-overview-card"><div class="cron-eyebrow">任务概况 · 9 项</div><div class="cron-summary-chips">${order.filter((s) => counts[s]).map((s) => `<span class="cron-summary-chip ${st(s)}">${ic(CI[s], 'cron-icon')}${counts[s]} ${CS[s]}</span>`).join('')}</div></div>
          <div class="cron-overview-card"><div class="cron-eyebrow">最近采样</div><div class="cron-sample-time">${CRON.sampled}</div><div class="cron-sample-hint">${ic('clock', 'cron-icon')}15 秒自动刷新</div></div></div>
        <div class="cron-queues"><div class="cron-queue"><div><strong>直播分析队列</strong><span>待处理 0 · 暂无等待</span></div><b>0</b></div><div class="cron-queue"><div><strong>复盘队列</strong><span>${sc === 'mixed' ? '待处理 3 · 最早等待 4 分 10 秒' : '待处理 0 · 暂无等待'}</span></div><b>${sc === 'mixed' ? 3 : 0}</b></div></div>
        <section class="cron-table-panel"><div class="cron-table-heading"><h2>任务状态</h2><small>共 9 项 · 按异常优先显示 · 点任意行看详情</small></div><div class="cron-table-scroll"><div class="cron-columns"><span>任务</span><span>状态</span><span>上次运行</span><span>耗时</span><span>连续失败</span><span>类型</span><span>最近错误</span><span></span></div>
          ${shown.map((j) => `<button class="cron-job" data-act="cron-open" data-id="${j.id}"><span><span class="cron-job-name">${j.name}</span><span class="cron-job-code">${j.id}</span></span><span class="cron-status ${st(j.state)}">${sc === 'api-error' ? '待确认' : CL[j.state]}</span><span>${j.last}</span><span>${j.dur}</span><span>${j.fails}</span><span>${j.kind}</span><span class="cron-error-summary ${j.err ? '' : 'muted'}">${j.err || '—'}</span><span class="cron-arrow">›</span></button>`).join('')}
        </div></section></div>
      ${open ? `<div class="cron-backdrop" data-act="cron-close"></div><aside class="cron-history" aria-label="任务运行历史"><div class="cron-history-head"><div><div class="cron-detail-kicker">任务详情 <span class="cron-summary-chip ${st(open.state)}">${ic(CI[open.state], 'cron-icon')}${sc === 'api-error' ? '待确认' : CL[open.state]}</span></div><h2>${open.name}</h2><code>${open.id}</code></div><button aria-label="关闭运行历史" data-act="cron-close">×</button></div>
        <div class="cron-history-scroll"><p class="cron-detail-purpose">${open.purpose}</p><div class="cron-detail-label">当前状态</div><div class="cron-detail-reason ${st(open.state)}">${ic(CI[open.state], 'cron-icon')}<span>${sc === 'offline' ? 'cron 进程失联，任务状态无法更新。' : open.reason}</span></div>
          <div class="cron-detail-facts"><div><small>运行方式</small><strong>${open.cadence}</strong></div><div><small>上次运行</small><strong>${open.last === '—' ? '暂无记录' : '09/25 ' + open.last}</strong></div><div><small>上次成功</small><strong>${open.success}</strong></div><div><small>${open.kind === '常驻循环' ? '正在处理' : '本次耗时'}</small><strong>${open.kind === '常驻循环' ? '1 / 4' : open.dur}</strong></div></div>
          ${open.err ? `<div class="cron-detail-label">最近错误</div><div class="cron-detail-error">${open.err}</div>` : ''}
          <section class="cron-detail-runs"><h3>运行历史</h3><p class="cron-detail-runs-caption">${open.last === '—' ? '暂无运行记录。' : '最近 2 条 · 单次最多显示 200 条'}</p>${open.last === '—' ? '' : `<div class="cron-run"><div class="cron-run-head"><time>09/25 11:52:41</time><span class="cron-status ${open.state === 'failed' ? 'failed' : open.state === 'errors' ? 'errors' : 'ok'}">${open.state === 'failed' ? '失败' : open.state === 'errors' ? '有报错' : '成功'}</span></div><div class="cron-run-info">${open.dur}${open.err ? ' · 1 条 ERROR' : ''}</div>${open.err ? `<div class="cron-run-error">${open.err}</div>` : ''}</div><div class="cron-run"><div class="cron-run-head"><time>09/25 11:22:40</time><span class="cron-status ok">成功</span></div><div class="cron-run-info">2 ms</div></div>`}</section></div>
        <div class="cron-history-foot">仅显示最近记录 · 状态和错误均来自 cron 记录器</div></aside>` : ''}</main>`;
  },
};
actions['cron-open'] = (el) => { CRON.open = el.dataset.id; render(); };
actions['cron-close'] = () => { CRON.open = null; render(); };
actions['cron-refresh'] = () => { CRON.feedback = '正在重新检查；当前数据仍为上次采样。'; render(); later(900, () => { CRON.sampled = nowTime(); CRON.feedback = CRON.scenario === 'api-error' ? '重试仍失败，继续显示旧数据。' : ''; if (S.page === 'cron') render(); }); };

// ---------- 性能监控 ----------
const PERF = { scenario: 'unconnected', dash: '主机概览' };
PROTO.push({ id: 'perf', page: 'performance', title: '性能监控场景', options: [['unconnected', '尚未接入'], ['connected', '已接入（嵌入示意）']], get: () => PERF.scenario, set: (v) => { PERF.scenario = v; } });
pages.performance = {
  render() {
    const on = PERF.scenario === 'connected';
    return `<main class="lab-page"><div class="lab-heading"><div><h1>性能监控</h1><p>在后台内查看主机与容器运行状态</p></div><span class="lab-status">${ic('info')}Grafana 嵌入看板</span></div>
      <div class="lab-content"><section class="panel pf-status"><div style="display:flex;gap:16px;align-items:center"><div class="mark">${ic('pulse')}</div><div><div class="note">Grafana 看板</div><h2>${on ? '嵌入布局预览' : '尚未接入'}</h2><p>${on ? '原型示意 · 不是实时画面，也不代表服务在线' : '尚未验证当前环境是否部署 Grafana 服务'}</p></div></div><span class="chip info">${ic(on ? 'layers' : 'info')}${on ? '仅设计示意' : '状态未知'}</span></section>
        <div class="pf-grid"><section class="panel"><div class="panel-head"><h2>内嵌监控看板</h2><small>主机 · 容器 · 存储</small></div><div class="pf-board">${on ? `<div class="pf-embed"><div class="pf-embed-top"><span>${ic('pulse')} Grafana ／ <select aria-label="选择看板" data-change="perf-dash">${['主机概览', '容器', 'KataGo GPU'].map((d) => `<option ${d === PERF.dash ? 'selected' : ''}>${d}</option>`).join('')}</select></span><span class="note">时间范围与刷新控件由 Grafana 提供</span></div><div class="pf-canvas">${(PERF.dash === '容器' ? ['katrain-web', 'katrain-cron', 'katago', 'postgres'] : PERF.dash === 'KataGo GPU' ? ['GPU 0 利用率', 'GPU 1 利用率', '显存', '队列'] : ['CPU', '内存', '磁盘', '网络']).map((t) => `<div><strong>${t}</strong><span>暂无实时数据 · 设计占位</span></div>`).join('')}</div><div class="note" style="text-align:center;padding:6px">本图仅展示 Grafana 在后台内的位置，不是实际 Grafana 页面</div></div>` : `<div class="pf-empty">${ic('info')}<h3>暂无性能数据</h3><p>目前没有可确认的 Grafana 端点。完成服务与访问控制核实后，实时看板会直接显示在此处。</p></div>`}</div></section>
          <aside class="panel"><div class="panel-head"><h2>接入信息</h2></div><dl class="pf-facts"><div><dt>当前环境</dt><dd>测试环境</dd></div><div><dt>监控服务</dt><dd>${on ? 'Grafana（设计示意）' : '尚未核实'}</dd></div><div><dt>嵌入地址</dt><dd>${on ? '待服务核实后配置' : '待确认'}</dd></div><div><dt>最近验证</dt><dd>${on ? '尚未实际验证' : '尚无验证记录'}</dd></div></dl><p class="note" style="padding:0 18px 16px">实际嵌入需先核实 Grafana 鉴权与浏览器策略；后台令牌不会传给 Grafana。</p></aside></div></div></main>`;
  },
};
actions['perf-dash'] = (el) => { PERF.dash = el.value; render(); };
