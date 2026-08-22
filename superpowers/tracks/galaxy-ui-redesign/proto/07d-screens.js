/* shared: PlaybackBar —— 照抄 components/live/PlaybackBar.tsx:107-241
     · 滑杆一行，控件一行，手数就在控件那一行里（真代码 Typography 是
       同一个 flex 容器的最后一个孩子，不是另起一行）
     · 「自动跟进」是无边框 ToggleButton，选中时 success.main（绿），
       **只有 isLive 才渲染**。真代码里只有 LivePage / LiveMatchPage 传
       isLive；ReportsPage、ReportDetailPage 都没传 —— 复盘不是直播，
       没有「最新一手」可跟。
     · 图标：KeyboardDoubleArrowLeft / ChevronLeft / PlayArrow /
       ChevronRight / KeyboardDoubleArrowRight / Sync
     · 首手禁用后退两键，末手禁用前进两键（handleFirst/Prev/Next/Last 的
       disabled 条件）。
   一处刻意不照抄：真代码有个 @container board-rail (max-width:340px) 的
   断点，会把手数换到第二行 —— 320 的右栏必然命中。这里把控件收窄到
   一行装得下（小键 32、播放键 44、间距 2、手数 .78rem），因为「合并成
   一行」是这次的验收条件。 */
function playback(total, cur, src, live) {
  const atStart = cur <= 0, atEnd = cur >= total;
  const on = S.toggles['follow-' + src] != null ? S.toggles['follow-' + src] : true;
  return `<div style="padding:10px 8px 12px">
    <input class="slider" type="range" min="0" max="${total}" value="${cur}" aria-label="手数滑杆" data-act="handleSliderChange → 停自动播放 + setCurrentMove(v)" data-src="${src}" style="margin-bottom:8px">
    <div class="pbrow">
      ${ibtn({ icon: 'KeyboardDoubleArrowLeft', label: '第一手', size: 'sm', disabled: atStart, act: 'handleFirst() → setCurrentMove(0)', src })}
      ${ibtn({ icon: 'ChevronLeft', label: '上一手', size: 'sm', disabled: atStart, act: 'handlePrev() → setCurrentMove(n-1)', src })}
      <button class="iconbtn play" aria-label="播放" data-act="handlePlayPause() —— 1000ms/手；已在末手时先回到第 0 手。暂停态 aria-label 变「暂停」" data-src="${src}">${icon('PlayArrow')}</button>
      ${ibtn({ icon: 'ChevronRight', label: '下一手', size: 'sm', disabled: atEnd, act: 'handleNext() → setCurrentMove(n+1)', src })}
      ${ibtn({ icon: 'KeyboardDoubleArrowRight', label: '最新', size: 'sm', disabled: atEnd, act: 'handleLast() → setCurrentMove(total) 并重新开启自动跟进', src })}
      ${live ? `<button class="syncbtn" role="button" aria-pressed="${on}" aria-label="自动跟进：${on ? '开' : '关'}" data-toggle="follow-${esc(src)}" data-act="setFollowLatest(v => !v)；由关转开时立刻跳到最新一手" data-src="${src}">${icon('Sync', 'sm')}</button>` : ''}
      <span class="mono muted" data-testid="playback-move-counter" style="font-size:.74rem;white-space:nowrap;margin-left:3px">${cur} / ${total} 手</span>
    </div>
  </div>`;
}

/* winrate sparkline — a chart deserves the same care as the type */
function trendChart(w, h, id) {
  const pts = [50, 52, 48, 55, 61, 58, 63, 57, 54, 60, 66, 62, 59, 64, 71, 68, 65, 70, 74, 69, 66, 72, 78, 75, 71, 68, 63, 58, 54.2];
  const n = pts.length, pad = 26;
  const x = i => pad + i * (w - pad - 8) / (n - 1);
  const y = v => h - 18 - (v / 100) * (h - 30);
  const line = pts.map((v, i) => `${i ? 'L' : 'M'}${x(i).toFixed(1)},${y(v).toFixed(1)}`).join('');
  const area = `${line}L${x(n - 1).toFixed(1)},${h - 18}L${pad},${h - 18}Z`;
  return `<svg viewBox="0 0 ${w} ${h}" width="100%" height="${h}" role="img" aria-label="黑棋胜率趋势，当前 54.2%">
    <defs><linearGradient id="tg${id}" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#5d8270" stop-opacity=".38"/><stop offset="100%" stop-color="#5d8270" stop-opacity="0"/>
    </linearGradient></defs>
    ${[25, 50, 75].map(v => `<line x1="${pad}" y1="${y(v)}" x2="${w - 8}" y2="${y(v)}" stroke="rgba(255,255,255,.07)" stroke-width="1"/>`).join('')}
    <line x1="${pad}" y1="${y(50)}" x2="${w - 8}" y2="${y(50)}" stroke="rgba(255,255,255,.16)" stroke-width="1" stroke-dasharray="3 3"/>
    ${[0, 50, 100].map(v => `<text x="${pad - 6}" y="${y(v) + 3}" fill="#4a4845" font-size="9" text-anchor="end">${v}</text>`).join('')}
    <path d="${area}" fill="url(#tg${id})"/>
    <path d="${line}" fill="none" stroke="#5d8270" stroke-width="1.8" stroke-linejoin="round"/>
    <circle cx="${x(n - 1)}" cy="${y(54.2)}" r="3.4" fill="#f5f3f0" stroke="#5d8270" stroke-width="1.6"/>
    <rect x="${pad}" y="0" width="${w - pad - 8}" height="${h - 14}" fill="transparent"
      data-act="点击折线图按横坐标换算手数 → setCurrentMove" data-src="TrendChart.tsx" role="button" aria-label="点击跳转到该手"/>
  </svg>`;
}

/* ───────────────────────────── 复盘 ───────────────────────────── */
const REPORTS = [
  ['申真谞 vs 柯洁', '2026-08-14', 250, 'done'],
  ['fan vs 智星棋手 5K', '2026-08-12', 244, 'running'],
  ['fan vs 智星棋手 5K', '2026-08-10', 211, 'failed'],
  ['黄云嵩 vs 范廷钰', '2026-08-08', 198, 'none'],
];
SCREENS.push({
  id: 'reports', group: '复盘', label: '复盘 · 列表 + 预览', route: '/galaxy/report',
  nav: 'review', kind: 'content',
  branches: [{ id: 'ok', label: '有棋局' }, { id: 'loading', label: '加载中' }, { id: 'empty', label: '空列表' }, { id: 'guest', label: '未登录' }],
  dialogs: {
    del: `<div class="dlg" data-zone="dialog"><h3>确认删除</h3><p>删除后棋局及所有关联分析数据将不可恢复，确认删除？</p>
      <div class="acts">${btn({ label: '取消', color: 'inherit', act: 'setDeleteTarget(null)', src: 'ReportsPage.tsx:529' })}
      ${btn({ label: '删除', variant: 'contained', color: 'err', act: 'DELETE /api/v1/user-games/{id}', src: 'ReportsPage.tsx:537' })}</div></div>`,
    imp: `<div class="dlg" style="max-width:300px" data-zone="dialog"><h3>导入棋谱</h3>
      <div style="padding:0 8px 12px">
        <button class="navitem" data-act="setLocalImportOpen(true)" data-src="ReportImportMenu.tsx:26">${icon('UploadFile')}<span>从本地导入 SGF</span></button>
        <button class="navitem" data-act="setLibraryImportOpen(true)" data-src="ReportImportMenu.tsx:34">${icon('LibraryBooks')}<span>从棋谱库导入</span></button>
      </div><div class="acts">${btn({ label: '关闭', color: 'inherit', act: '关闭菜单' })}</div></div>`,
    local: `<div class="dlg" style="max-width:520px" data-zone="dialog"><h3>从本地导入 SGF</h3>
      <p>选择本地 SGF 文件，或直接粘贴 SGF 内容。</p>
      <div style="padding:0 22px 16px" class="stack g12">
        ${btn({ label: '选择本地文件', variant: 'outlined', icon: 'UploadFile', full: true, act: '打开文件选择器', src: 'ReportLocalImportDialog.tsx' })}
        <textarea class="field" rows="5" placeholder="(;GM[1]FF[4]SZ[19]…" aria-label="SGF 内容" data-act="setSgfText" data-src="ReportLocalImportDialog.tsx"></textarea>
      </div>
      <div class="acts">${btn({ label: '取消', color: 'inherit', act: '关闭弹窗' })}
      ${btn({ label: '仅导入', variant: 'outlined', act: 'POST /api/v1/user-games', src: 'ReportLocalImportDialog.tsx' })}
      ${btn({ label: '导入并生成普通报告', variant: 'contained', act: 'POST user-games → POST reports(normal)', src: 'ReportLocalImportDialog.tsx' })}</div></div>`,
  },
  render(b) {
    if (b === 'guest') {
      return {
        html: `<div data-zone="body" style="max-width:420px;margin:80px auto;text-align:center">
          <div class="alert info" style="justify-content:center">请先登录后查看和生成复盘报告。</div>
          <div style="margin-top:16px">${btn({ label: '登录', variant: 'contained', icon: 'Login', act: '打开 LoginModal', src: 'ReportsPage.tsx' })}</div></div>`,
      };
    }
    const cardFor = ([title, date, moves, st]) => `<div class="kcard" role="button" tabindex="0"
      data-act="setSelectedGameId(id) → 换左栏预览（整卡可点，Enter/Space 同效）" data-src="ReportGameCard.tsx:104">
      <div class="rowbetween" style="margin-bottom:8px">
        <div style="min-width:0"><div style="font-size:.92rem;font-weight:600;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${title}</div>
        <div class="dim mono" style="font-size:.72rem">${date} · ${moves} 手</div></div>
        ${ibtn({ icon: 'DeleteOutline', label: '删除棋局', size: 'sm', act: 'setDeleteTarget(id) → 删除确认弹窗', src: 'ReportGameCard.tsx:125' })}
      </div>
      <div class="inline" style="gap:6px">
        ${st === 'done' ? `${btn({ label: '普通报告', variant: 'outlined', size: 'sm', act: '导航 /galaxy/report/{id}', src: 'ReportGameCard.tsx:202' })}
           ${btn({ label: '深度报告', variant: 'outlined', size: 'sm', act: '导航 /galaxy/report/{id}', src: 'ReportGameCard.tsx:215' })}` : ''}
        ${st === 'running' ? `<span class="chip warn">普通报告 生成中</span>` : ''}
        ${st === 'failed' ? `${btn({ label: '重试普通报告', variant: 'outlined', size: 'sm', color: 'err', act: 'POST /api/v1/reports/{id}/retry', src: 'ReportGameCard.tsx:229' })}` : ''}
        ${st === 'none' ? dlgOpen('imp', '生成报告', { variant: 'contained', size: 'sm', src: 'ReportGameCard.tsx:257' }) : ''}
      </div></div>`;
    const left = `<div class="lmain" style="padding:24px;gap:16px">
      <div data-zone="page-header">
        <h1 style="font-size:2.125rem;font-weight:700;letter-spacing:-.02em;margin:0">复盘</h1>
        <p class="muted" style="margin:6px 0 0;font-size:.875rem">选择右侧棋局预览棋盘，报告生成和跳转都在棋局卡片上完成。</p>
      </div>
      <div style="flex:1;min-height:0;display:flex;flex-direction:column;border-radius:14px;background:#111;border:1px solid rgba(255,255,255,.06);overflow:hidden">
        <div style="padding:14px 24px;border-bottom:1px solid rgba(255,255,255,.06)">
          <div style="font-size:1.25rem;font-weight:700">${b === 'empty' ? '选择棋局' : '申真谞 vs 柯洁'}</div>
          <div class="muted" style="font-size:.85rem;margin-top:3px">${b === 'empty' ? '从右侧列表选择一局，或导入新的 SGF / 棋谱库对局。' : '申真谞 vs 柯洁 · 250 手'}</div>
        </div>
        <div class="lboard">${b === 'loading'
          ? `<div class="spin"></div>`
          : b === 'empty' ? `<p class="dim">还没有可预览的棋局。</p>`
            : `<canvas class="boardcv" data-floor="400" data-board='${esc(JSON.stringify({ stones: demoStones(36), coords: true, last: [9, 13, 'B'] }))}'></canvas>`}</div>
        <div style="border-top:1px solid rgba(255,255,255,.06)">${playback(250, 250, 'PlaybackBar.tsx')}</div>
      </div>
    </div>`;
    const right = `<div class="lrail w520 fixed" data-zone="right-rail-top">
      <div style="padding:24px 24px 16px">
        <div style="font-size:1.25rem;font-weight:700">棋局列表</div>
        <p class="muted" style="margin:6px 0 12px;font-size:.85rem">共 107 局，支持按棋手、标题或赛事搜索。</p>
        <div class="inline" style="gap:6px;margin-bottom:12px">
          <span class="chip warn">1 生成中</span><span class="chip">2 排队中</span><span class="chip err">1 失败</span>
        </div>
        <div class="stack g12">
          ${dlgOpen('imp', '导入棋谱', { variant: 'outlined', icon: 'CloudDownload', src: 'ReportImportMenu.tsx:17' })}
          <div class="fieldwrap">${icon('Search', 'sm')}<input class="field" placeholder="按棋手、标题或赛事搜索" aria-label="按棋手、标题或赛事搜索" data-act="Enter → handleSearch()" data-src="ReportsPage.tsx:436"></div>
        </div>
      </div>
      <div class="lrail-scroll" style="padding:0 20px 16px" data-zone="list-item">
        ${b === 'loading' ? '<div class="stack g8">' + '<div class="skel" style="height:88px"></div>'.repeat(4) + '</div>'
          : b === 'empty' ? `<p class="dim" style="text-align:center;padding:40px 0">还没有棋局，先导入一局再生成报告。</p>`
            : `<div class="stack g8">${REPORTS.map(cardFor).join('')}</div>`}
      </div>
      ${b === 'ok' ? `<div style="padding:12px 0;border-top:1px solid var(--line)" data-zone="right-rail-actions">
        <div class="pager">
          ${[1, 2, 3].map(p => `<button aria-current="${p === 1}" data-act="handlePageChange(${p})" data-src="ReportsPage.tsx">${p}</button>`).join('')}
        </div></div>` : ''}
    </div>`;
    return { raw: `<div class="lrow" data-zone="body">${left}${right}</div>` };
  },
  note: `<h3>标题下面那行是长副标题</h3>
    <p>「选择右侧棋局预览棋盘，报告生成和跳转都在棋局卡片上完成。」是操作说明，
    spec §2.4 不许进页头，要下沉到棋盘卡片上方或列表栏顶部。</p>
    <p>⚠️ <code>ReportsPage.test.tsx:150</code> 断言的是英文 fallback <code>'Review'</code>（vitest 不加载翻译），
    所以 <code>ContentPageHeader</code> 的 title 要传 <code>t('report:my_reports','Review')</code> 这个表达式，
    不能写死中文「复盘」，否则那条测试会红。</p>`,
});

SCREENS.push({
  id: 'report-detail', group: '复盘', label: '复盘 · 报告详情', route: '/galaxy/report/:taskId',
  nav: 'review', kind: 'content',
  branches: [{ id: 'ok', label: '主界面' }, { id: 'loading', label: '加载中' }, { id: 'error', label: '加载失败' }, { id: 'nosgf', label: '无 SGF' }],
  render(b) {
    if (b === 'loading') return { raw: `<div style="height:100%;display:grid;place-items:center" data-zone="body"><div class="spin"></div></div>` };
    if (b === 'error') {
      return {
        raw: `<div style="padding:32px" data-zone="body"><div class="alert error" style="margin-bottom:16px">加载报告失败</div>
          ${btn({ label: '返回报告列表', variant: 'outlined', act: '导航 /galaxy/report', src: 'ReportDetailPage.tsx:104' })}</div>`,
      };
    }
    const tab = (i, l, on) => `<button role="tab" aria-selected="${on}" data-act="setTab(${i})" data-src="TrendChart.tsx">${l}</button>`;
    return {
      raw: `<div class="lrow" data-zone="body">
        <div class="lmain" style="padding:20px">
          <div class="inline" style="gap:8px;margin-bottom:16px" data-zone="page-header">
            ${ibtn({ icon: 'ArrowBack', label: '返回', size: 'sm', act: '导航 /galaxy/report', src: 'ReportDetailPage.tsx:113' })}
            <span style="flex:1;min-width:0;font-size:1.25rem;font-weight:600;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">申真谞 vs 柯洁</span>
            ${btn({ label: '进入研究室', variant: 'outlined', size: 'sm', act: '导航 /galaxy/research（不带棋局参数）', src: 'ReportDetailPage.tsx:118' })}
          </div>
          <div style="flex:1;min-height:0;display:flex;align-items:center;justify-content:center">
            ${b === 'nosgf' ? `<div class="alert info">没有可用于复盘展示的 SGF 数据。</div>`
              : `<canvas class="boardcv" data-floor="400" data-board='${esc(JSON.stringify({ stones: demoStones(36), coords: true, last: [9, 13, 'B'], ai: [[15, 15, '54%', '+1.8'], [3, 15, '52%', '+0.9'], [16, 5, '51%', '+0.2']] }))}'></canvas>`}
          </div>
        </div>
        <div class="lrail w500">
          <div style="padding:16px;border-bottom:1px solid var(--line)" data-zone="right-rail-top">
            <div class="rowbetween" style="margin-bottom:8px"><span style="font-weight:600">申真谞</span><span class="mono">9段</span></div>
            <div class="rowbetween" style="margin-bottom:10px"><span style="font-weight:600">柯洁</span><span class="mono">9段</span></div>
            <div class="inline" style="gap:16px">
              <span class="stat"><b style="color:var(--jade-l)">54.2%</b><span>黑棋胜率</span></span>
              <span class="stat"><b>+1.8</b><span>黑棋领先（目）</span></span>
              <span class="stat"><b>250</b><span>手数</span></span>
            </div>
          </div>
          <div class="lrail-scroll" data-zone="right-rail-middle">
            <div style="padding:12px 16px;border-bottom:1px solid var(--line);background:rgba(255,255,255,.03)">
              <div class="tgroup">
                ${tbtn({ id: 'rd-try', label: '试下', icon: 'TouchApp', src: 'ReportDetailPage.tsx:167' })}
                ${tbtn({ id: 'rd-terr', label: '领地', icon: 'Map', src: 'ReportDetailPage.tsx:184' })}
                ${tbtn({ id: 'rd-num', label: '手数', icon: 'FormatListNumbered', src: 'ReportDetailPage.tsx:207' })}
                ${tbtn({ id: 'rd-ai', label: '建议', icon: 'TipsAndUpdates', on: true, src: 'ReportDetailPage.tsx:218' })}
              </div>
              <div class="rowbetween" style="margin-top:8px">
                <span class="dim mono" style="font-size:.72rem">TRY: Q16 → R14</span>
                ${btn({ label: '清空', size: 'sm', act: 'setTryMoves([])（不退出试下）', src: 'ReportDetailPage.tsx:232' })}
              </div>
            </div>
            <div style="padding:14px 16px;border-bottom:1px solid var(--line)">
              <p class="sec-label">AI 推荐</p>
              <table style="width:100%;border-collapse:collapse;font-size:.8rem">
                <thead><tr class="dim" style="text-align:left"><th style="font-weight:500;padding:3px 0">着手</th><th style="font-weight:500">胜率</th><th style="font-weight:500">目差</th><th style="font-weight:500">推荐度</th></tr></thead>
                <tbody class="mono">
                  <tr data-act="hover → 棋盘画变化图 pvMoves" data-src="AiAnalysis.tsx" role="button" tabindex="0"><td style="padding:3px 0;color:var(--jade-l)">Q16</td><td>54.2%</td><td>+1.8</td><td>92%</td></tr>
                  <tr data-act="hover → 棋盘画变化图 pvMoves" data-src="AiAnalysis.tsx" role="button" tabindex="0"><td style="padding:3px 0">D4</td><td>52.9%</td><td>+0.9</td><td>61%</td></tr>
                </tbody></table>
            </div>
            <div style="padding:0 0 14px">
              <div class="tabs">${tab(0, '走势', true)}${tab(1, '妙手 (2)', false)}${tab(2, '失误 (5)', false)}</div>
              <div style="padding:12px 16px 0">${trendChart(452, 150, 'rd')}</div>
            </div>
          </div>
          <div style="border-top:1px solid var(--line)" data-zone="right-rail-actions">${playback(250, 250, 'PlaybackBar.tsx')}</div>
        </div>
      </div>`,
    };
  },
  note: `<h3>六个棋盘页里最好迁的一个</h3>
    <p>它已经是「棋盘左 / 信息栏右」，右栏内容顺序也和模板一致（信息 → 开关 → AI → 走势 → 回放）。
    要动的只有三件：棋盘上方那行标题条搬进 <code>ModulePlate</code>（<code>ReportDetailPage.tsx:112-122</code>）、
    右栏 500 → 340、外层换 <code>BoardPageShell</code>。</p>
    <p>「进入研究室」现在不带棋局参数（<code>:118</code>），点了会丢掉当前这局 ——
    是个既有 bug，记下来，本轮不顺手改。</p>`,
});

/* ───────────────────────────── 直播 ───────────────────────────── */
const LIVEROWS = [
  ['陈泓明', '姚钧耀', '天元记谱', 194, true],
  ['申真谞', '柯洁', '春兰杯八强', 250, true],
  ['朴廷桓', '芈昱廷', 'LG 杯十六强', 231, false],
  ['黄云嵩', '范廷钰', '中国围甲', 244, false],
];
SCREENS.push({
  id: 'live-list', group: '直播', label: '直播 · 列表页', route: '/galaxy/live',
  nav: 'live', kind: 'content',
  branches: [{ id: 'ok', label: '已选中对局' }, { id: 'upcoming', label: '赛事预告' }, { id: 'loading', label: '加载中' }, { id: 'empty', label: '未选择' }],
  render(b) {
    const rows = (compact) => LIVEROWS.map(([bl, wh, ev, mv, live], i) => `
      <button class="kcard ${b === 'ok' && i === 0 ? 'sel' : ''}" data-act="handleSelectMatch(id) → 换右栏棋盘" data-src="LivePage.tsx:141">
        <div class="kmeta"><span>${ev}</span><span>${live ? '<span class="chip err filled pulse" style="height:16px;font-size:.62rem"><i class="dot"></i>直播中</span>' : `${mv} 手`}</span></div>
        <div class="kplayers"><span class="side"><i class="kstone b"></i>${bl}</span><span class="dim">vs</span><span class="side w">${wh}<i class="kstone w"></i></span></div>
      </button>`).join('');
    return {
      raw: `<div class="lrow" data-zone="body">
        <div class="lmain" style="padding:16px">
          <div class="rowbetween" style="margin-bottom:16px" data-zone="page-header">
            <h1 style="font-size:2.125rem;font-weight:700;margin:0">直播</h1>
          </div>
          <div style="flex:1;min-height:0;display:flex;flex-direction:column">
            ${b === 'loading' ? `<div style="flex:1;display:grid;place-items:center"><div class="spin"></div></div>`
              : b === 'empty' || b === 'upcoming'
                ? `<div style="flex:1;display:grid;place-items:center"><p class="dim">选择一场对局观看</p></div>`
                : `<div class="lboard"><canvas class="boardcv" data-floor="400" data-board='${esc(JSON.stringify({ stones: demoStones(34), coords: true, last: [4, 11, 'B'] }))}'></canvas></div>
                   ${playback(194, 194, 'PlaybackBar.tsx', true)}`}
          </div>
        </div>
        <div class="lrail w500 mdonly">
          <div class="tabs" style="padding:16px 16px 0" data-zone="right-rail-top">
            <button role="tab" aria-selected="${b !== 'upcoming'}" data-act="setRightTab(0)" data-src="LivePage.tsx:119">精选对局</button>
            <button role="tab" aria-selected="${b === 'upcoming'}" data-act="setRightTab(1)" data-src="LivePage.tsx:120">赛事预告</button>
          </div>
          <div class="lrail-scroll" style="padding:16px" data-zone="right-rail-middle">
            ${b === 'upcoming'
              ? `<div class="stack g8">${[['第 9 届应氏杯', '2026-08-24 13:00', '2 天后'], ['三星火灾杯预选', '2026-08-27 10:00', '5 天后']].map(([n, t2, d]) => `
                  <div class="kcard" style="cursor:default"><div class="kmeta"><span>${n}</span><span>${d}</span></div>
                  <div class="rowbetween"><span class="mono muted" style="font-size:.8rem">${t2}</span>
                  <span class="inline" style="gap:4px">
                    ${ibtn({ icon: 'Pause', label: '暂停自动轮播', size: 'sm', act: '暂停 UpcomingList 轮播', src: 'UpcomingList.tsx' })}
                    <button data-act="打开赛事官方页" data-src="UpcomingList.tsx" style="background:none;border:0;color:var(--info);cursor:pointer;font-size:.78rem;text-decoration:underline;text-underline-offset:2px">官方信息</button>
                  </span></div></div>`).join('')}</div>`
              : b === 'loading' ? '<div class="stack g8">' + '<div class="skel" style="height:64px"></div>'.repeat(4) + '</div>'
                : `<p class="sec-label">正在直播 (2)</p><div class="stack g8">${rows(true)}</div>
                   <p class="sec-label" style="margin-top:20px">历史对局</p><div class="stack g8">${rows(true)}</div>`}
          </div>
          ${b !== 'upcoming' ? `<div style="padding:16px;border-top:1px solid var(--line)" data-zone="right-rail-actions">
            ${btn({ label: b === 'ok' ? '进入直播' : '查看棋谱', variant: 'contained', size: 'lg', full: true, disabled: b === 'empty' || b === 'loading', act: '导航 /galaxy/live/{matchId}', src: 'LivePage.tsx:171' })}
          </div>` : ''}
        </div>
      </div>`,
    };
  },
  note: `<h3>被归到内容页，但它其实有棋盘</h3>
    <p>scope 把 <code>LivePage</code> 列进「12 个只换页头」的内容页，可它左栏是一块真棋盘，
    而且标题就压在棋盘正上方（<code>LivePage.tsx:64-69</code>）—— spec §2.2 明令禁止的位置。</p>
    <p>只换页头的话，这条违规会留下来。这是本轮范围里我看到的最需要你裁定的一处：
    要么承认它是第 7 个棋盘页，要么明确接受它保持现状。</p>`,
});

SCREENS.push({
  id: 'live-match', group: '直播', label: '直播 · 对局页（已批准样板）', route: '/galaxy/live/:matchId',
  nav: 'live', kind: 'board',
  branches: [{ id: 'live', label: '直播中' }, { id: 'finished', label: '已结束' }, { id: 'loading', label: '加载中' }, { id: 'error', label: '加载失败' }],
  render(b, vp) {
    if (b === 'loading') {
      return {
        board: {},
        plate: plate({ title: '正在加载直播对局', sub: '　', backTo: '/galaxy/live', src: 'LiveMatchPage.tsx:82' }),
        railBody: `<div class="pad stack g12"><div class="skel" style="height:120px"></div><div class="skel" style="height:160px"></div><div class="skel" style="height:180px"></div></div>`,
        controls: `<div class="pad" style="display:grid;grid-template-columns:1fr 1fr;gap:6px">${Array.from({ length: 5 }, (_, i) => `<button class="mbtn full" disabled aria-label="骨架按钮${i + 1}" data-act="LoadingControls 占位按钮 ${i + 1}（内含 Skeleton width 70%）" data-src="LiveMatchPage.tsx:21"><span class="skel" style="width:70%;height:14px"></span></button>`).join('')}</div>`,
        actions: `<div class="pad"><button class="mbtn full" disabled aria-label="骨架按钮 6" data-act="LoadingActions 占位按钮（内含 Skeleton width 60%）" data-src="LiveMatchPage.tsx:28"><span class="skel" style="width:60%;height:14px"></span></button></div>`,
      };
    }
    if (b === 'error') {
      return {
        board: {},
        plate: plate({ title: '直播对局', backTo: '/galaxy/live', src: 'LiveMatchPage.tsx:100' }),
        railBody: `<div class="pad"><div class="alert error" style="margin-bottom:14px">加载对局数据失败</div>
          ${btn({ label: '重试', variant: 'outlined', act: 'refresh() → 重新拉取直播详情', src: 'LiveMatchPage.tsx:106' })}</div>`,
        actions: `<div class="pad"><div class="skel" style="height:40px"></div></div>`,
      };
    }
    const live = b === 'live';
    const railW = vp.rail || 430;
    return {
      board: { floor: 0, stones: demoStones(34), coords: true, last: [4, 11, 'B'], ai: [[15, 15, '54%', '+1.8'], [3, 15, '52%', '+0.9'], [16, 5, '51%', '+0.2']] },
      plate: plate({
        title: `${NOW.black} vs ${NOW.white}`,
        sub: `${NOW.event} · 194 / 194 手`,
        status: live
          ? `<span class="chip err filled pulse"><i class="dot"></i>直播中</span>`
          : `<span class="chip">已结束</span>`,
        backTo: '/galaxy/live', src: 'LiveMatchPage.tsx:170',
      }),
      railBody: `<div class="pad" style="border-bottom:1px solid var(--line)">
          <p class="sec-label">对局信息</p>
          <div class="rowbetween" style="font-size:.875rem"><span class="inline" style="gap:6px"><i class="kstone b"></i>${NOW.black}</span><span class="mono">9段</span></div>
          <div class="rowbetween" style="font-size:.875rem;margin-top:4px"><span class="inline" style="gap:6px"><i class="kstone w"></i>${NOW.white}</span><span class="mono">9段</span></div>
          <div class="rowbetween muted" style="font-size:.8rem;margin-top:10px"><span>中国规则 · 贴 7.5 目</span><span class="mono">${live ? '黑棋胜率 54.2%' : '黑中盘胜'}</span></div>
          <div class="inline dim" style="gap:8px;font-size:.72rem;margin-top:8px"><span>2026年3月27日</span><span class="chip info">弈客</span></div>
        </div>
        <div class="pad" style="border-bottom:1px solid var(--line)">
          <p class="sec-label">AI 推荐</p>
          <table style="width:100%;border-collapse:collapse;font-size:.8rem">
            <thead><tr class="dim" style="text-align:left"><th style="font-weight:500;padding:3px 0">着手</th><th style="font-weight:500">胜率</th><th style="font-weight:500">目差</th></tr></thead>
            <tbody class="mono">
              <tr data-act="hover → 棋盘画变化图" data-src="AiAnalysis.tsx" role="button" tabindex="0"><td style="padding:3px 0;color:var(--jade-l)">Q16</td><td>54.2%</td><td>+1.8</td></tr>
              <tr data-act="hover → 棋盘画变化图" data-src="AiAnalysis.tsx" role="button" tabindex="0"><td style="padding:3px 0">D4</td><td>52.9%</td><td>+0.9</td></tr>
              <tr data-act="hover → 棋盘画变化图" data-src="AiAnalysis.tsx" role="button" tabindex="0"><td style="padding:3px 0">R5</td><td>51.1%</td><td>+0.2</td></tr>
            </tbody></table>
        </div>
        <div data-testid="live-match-trend-region" style="flex:none">
          <div class="tabs">
            <button role="tab" aria-selected="true" data-act="setTab(0) 走势" data-src="TrendChart.tsx">走势</button>
            <button role="tab" aria-selected="false" data-act="setTab(1) 妙手" data-src="TrendChart.tsx">妙手 (2)</button>
            <button role="tab" aria-selected="false" data-act="setTab(2) 失误" data-src="TrendChart.tsx">失误 (5)</button>
          </div>
          <div style="padding:12px 12px 4px">${trendChart(railW - 24, 140, 'lm')}</div>
          <div class="stack g4" style="padding:4px 12px 12px">
            ${[[57, '+6.2', 'ok'], [88, '-8.1', 'err']].map(([n, v, kind]) => `<button class="rowbetween"
              data-act="onMoveClick(${n}) → setCurrentMove(${n})，棋盘跳到该手" data-src="TrendChart.tsx"
              style="width:100%;background:none;border:0;border-left:3px solid var(--${kind});padding:5px 10px;color:inherit;font:inherit;cursor:pointer;text-align:left">
              <span style="font-size:.8rem">第 ${n} 手 · ${kind === 'ok' ? '妙手' : '失误'}</span>
              <span class="mono" style="font-size:.76rem;color:var(--${kind})">${v} 目</span></button>`).join('')}
          </div>
        </div>`,
      controls: `<div class="pad" data-testid="live-match-display-controls-grid" style="display:grid;grid-template-columns:1fr 1fr;gap:6px">
          ${tbtn({ id: 'lm-try', label: '试下', icon: 'TouchApp', src: 'LiveMatchDisplayControls.tsx' })}
          ${tbtn({ id: 'lm-terr', label: '领地', icon: 'Map', src: 'LiveMatchDisplayControls.tsx:114' })}
          ${tbtn({ id: 'lm-num', label: '手数', icon: 'FormatListNumbered', src: 'LiveMatchDisplayControls.tsx' })}
          ${tbtn({ id: 'lm-ai', label: '建议', icon: 'TipsAndUpdates', on: true, src: 'LiveMatchDisplayControls.tsx' })}
          ${tbtn({ id: 'lm-coord', label: '坐标', icon: 'GridOn', on: vp.id !== '430x880', src: 'LiveMatchDisplayControls.tsx:141' })}
          <div class="rowbetween" style="grid-column:1/-1;margin-top:4px">
            <span class="dim mono" style="font-size:.72rem">试下: Q16 → R14</span>
            ${btn({ label: '清空', size: 'sm', act: 'onClearTryMoves() → setTryMoves([])', src: 'LiveMatchDisplayControls.tsx:156' })}
          </div>
        </div>`,
      actions: playback(194, 194, 'PlaybackBar.tsx', live),
    };
  },
  note: `<h3>本轮唯一的棋盘页照抄对象</h3>
    <p>2026-08-06 经你确认的 12 视口样板。结构固定为：棋盘是唯一连续伸缩区域；
    右栏自上而下 <b>模块牌 / 业务主体 / 显示开关 / 行动区</b>，<b>只有中段可滚</b>，
    模块牌与底部动作始终可见。</p>
    <p>把上面的视口切到 1024×768 和 430×880，几何读数应当分别落在 684 / 320 和 410 ——
    这三个数就是其余 6 个棋盘页迁完后要对上的判据。</p>`,
});
