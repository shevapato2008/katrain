/* ═══════════════════════════════════════════════════════════════
   改版 —— 统一版式 v2
   ---------------------------------------------------------------
   一条契约，所有有棋盘的页面共用：

     顶栏  52   固定（GalaxyTopBar）
     左栏  216  固定（停靠态；<900 收起为 0；<600 换 64 底栏）
     右栏  320  固定（取消现行 320/340/380 三档）
     棋盘  中间区全部剩余空间，方形居中，stage padding 6，地板 0
     棋盘上方  空
     右栏三段  模块牌（不滚）/ 中段（唯一可滚）/ 动作区（不滚）

   为什么右栏收到 320 而不是模板现在的 340：
     1440×900  棋盘 = min(1440-216-320-20, 900-52-20) = min(884, 828) = 828
     1024×768  棋盘 = min(1024-  0-320-20, 768-52-20) = min(684, 696) = 684
   两档都是「高度」在卡棋盘，右栏从 340 收到 320 一个像素都不亏，
   却把三档并成了一个数。430 竖屏右栏整幅移到棋盘下方。
   ═══════════════════════════════════════════════════════════════ */
const RAIL2 = 320;
/* 承重实测要求「先把数据造到会溢出」。列表型页面的行数在这里放大到
   后端一页真的会返回的量（棋谱库 page_size=20，复盘/直播同量级），
   而不是演示用的 4-6 行。压扁视口 + 这份数据 = 中段必然要滚。 */
const STRESS = () => !!S.stress;
const rep = (arr, n) => Array.from({ length: n }, () => arr).flat();
const V2 = {};

/* 统一模块牌：图标左置（已批准样板那一种）。根级页面没有上一级，只有标题。
   顺手修掉一处：返回键的 aria-label 在现状里是 t('Back','Back')，cn 目录
   没有词条所以真的读作 "Back"。这里读「返回」。 */
function plate2(o) {
  const back = o.backTo
    ? ibtn({ icon: 'ArrowBack', label: '返回', act: 'requestNavigation(' + o.backTo + ')', src: o.src })
    : '';
  return `<div class="plate ${o.backTo ? 'iconleft' : ''}" data-zone="right-rail-top">
    ${back}
    <div class="plate-text"><p class="plate-title">${esc(o.title)}</p>${o.sub ? `<p class="plate-sub">${esc(o.sub)}</p>` : ''}</div>
    ${o.status || ''}
  </div>`;
}
/* 右栏中段的一节 */
function sec2(label, inner, style) {
  return `<div class="pad" style="border-bottom:1px solid var(--line);${style || ''}">
    ${label ? `<p class="sec-label">${esc(label)}</p>` : ''}${inner}</div>`;
}
/* 右栏动作区里那条主按钮 */
function act2(inner) { return `<div class="pad">${inner}</div>`; }
/* 320 宽下的走势图 */
const trend2 = (id) => trendChart(RAIL2 - 24, 132, id);

/* 3D 相机浮层 —— 三个页面共用，位置不变，只是外面换成了 BoardPageShell 的 stage */
const cam3d = `
  <div style="position:absolute;right:14px;bottom:14px;display:flex;flex-direction:column;gap:6px;align-items:center;background:rgba(0,0,0,.5);padding:8px;border-radius:10px">
    <button class="iconbtn sm" aria-label="Zoom in" title="Zoom in" data-act="handleZoom('in') — 相机拉近一档" data-src="Board3D/index.tsx:215">+</button>
    <button class="iconbtn sm" aria-label="Zoom out" title="Zoom out" data-act="handleZoom('out') — 相机拉远一档" data-src="Board3D/index.tsx:232">−</button>
    <input class="slider" type="range" min="0" max="100" value="55" aria-label="Tilt angle 俯仰角" title="Tilt angle" data-act="handleTiltChange — OrbitControls 极角" data-src="Board3D/index.tsx:241" style="width:70px">
  </div>
  <div style="position:absolute;left:50%;bottom:12px;transform:translateX(-50%);background:rgba(0,0,0,.5);padding:6px 12px;border-radius:20px">
    <input class="slider" type="range" min="0" max="100" value="50" aria-label="左右" title="Yaw angle" data-act="handleYaw — OrbitControls 方位角" data-src="Board3D/index.tsx:271" style="width:150px">
  </div>`;
const stage3d = (stones) => `<div style="width:100%;height:100%;border-radius:12px;background:radial-gradient(700px 400px at 50% 20%,#3a3226,#171310);display:grid;place-items:center;position:relative;overflow:hidden">
  <canvas class="boardcv" data-floor="0" data-board='${esc(JSON.stringify({ stones, coords: true }))}' style="transform:perspective(900px) rotateX(46deg) scale(.84);box-shadow:0 40px 70px -20px rgba(0,0,0,.85)"></canvas>
  ${cam3d}</div>`;

/* 六键前后翻手 —— 对局类页面的动作区第一行 */
const navRow = (src) => `<div style="padding:10px 12px;display:flex;justify-content:center;gap:2px">
  ${ibtn({ icon: 'SkipPrevious', label: '跳到开局', act: 'API.undo(sessionId, 9999)', src })}
  ${ibtn({ icon: 'FastRewind', label: '后退 10 手', act: 'API.undo(sessionId, 10)', src })}
  ${ibtn({ icon: 'ArrowBack', label: '后退一手', act: 'API.undo(sessionId, 1)', src })}
  ${ibtn({ icon: 'ArrowForward', label: '前进一手', act: 'API.redo(sessionId, 1)', src })}
  ${ibtn({ icon: 'FastForward', label: '前进 10 手', act: 'API.redo(sessionId, 10)', src })}
  ${ibtn({ icon: 'SkipNext', label: '跳到最后', act: 'API.redo(sessionId, 9999)', src })}
</div>`;


/* ═══ 对局类页面共用的右栏 ═══════════════════════════════════════
   三条改动，来自 2026-08-20 的评审：
   ① 轮到谁下，谁的卡片高亮（描边 + 时钟变玉色 + 一个呼吸点），
      另一张压暗。之前两张卡完全一样，看不出轮次。
   ② 右下角那排「认输 / 数子 / 数子请求 / 离开」删掉：认输和数子
      本来就在上面的工具格里（现在真的接上弹窗了），数子请求是对方
      发起时弹出来的、不是我方按钮。只剩「离开对局」，按要求跟工具格
      放在一起 —— 就在格子正下方。动作区只留翻手那六个键。
   ③ 弹窗触发挪到控制台的「弹窗」一栏，框里不再有原型专用的假按钮。
   ═══════════════════════════════════════════════════════════════ */
function pcard(o) {
  const on = !!o.active;
  return `<div class="pcard${on ? ' on' : ''}" style="flex:1;min-width:0">
    <div class="inline" style="gap:6px">
      ${on ? '<i class="turn"></i>' : ''}<i class="kstone ${o.stone}"></i>
      <span style="font-weight:600;font-size:.84rem;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${esc(o.name)}</span>
    </div>
    <div class="rowbetween" style="margin-top:2px;flex-wrap:nowrap;gap:2px">
      <span class="mono clock" style="font-size:1.2rem;font-weight:600">${esc(o.clock)}</span>
      <span class="pcard-icons">
        ${ibtn({ icon: 'PersonAdd', label: '关注 ' + o.name, size: 'sm', act: 'handleToggleFollow(name) → API.followUser / unfollowUser', src: 'PlayerCard.tsx' })}${o.extra || ''}</span>
    </div>
    <div class="dim" style="font-size:.68rem">${esc(o.meta)}</div>
    ${on ? '<span class="pcard-turn">该你了</span>' : ''}
  </div>`;
}

/* ═══ 普通按钮的唯一形态 ═══════════════════════════════════════════
   对局室右栏那八个键（领地/建议/图表/悔棋/停一手/认输/数子/3D）是样板：
   有边框、图标在上、文字在下、四列等宽、彼此挨在一起成一块。
   全站的普通按钮都走这个 helper，形状和尺寸就不会各页各样。

   两类例外，不进格子：
     · 滑轨 —— 只有坐标 / 手数 / 落子特效三样，见 swrow()；
     · 整行按钮 —— 「离开对局」这种破坏性操作，和动作区那条主 CTA。 */
function tgrid(inner, cols) {
  return `<div class="toolgrid" style="display:grid;grid-template-columns:repeat(${cols || 4},1fr);gap:6px">${inner}</div>`;
}
/* 格子里的「按一下就发生一件事」的按钮：和 tbtn 同一个外观，
   但没有按下态（不是开关，所以不写 aria-pressed）。 */
function gbtn(o) {
  /* 带 aria-label：图标可能是纯字形（△ / 123），不写的话读屏和快照
     读到的是「△图形」这种把装饰和文案粘在一起的串。 */
  return `<button class="tbtn" aria-label="${esc(o.label)}" ${o.disabled ? 'disabled' : ''}${o.dialog ? ` data-dialog="${esc(o.dialog)}"` : ''} data-act="${esc(o.act || '')}" data-src="${esc(o.src || '')}">${o.icon ? icon(o.icon, 'sm') : ''}${esc(o.label)}</button>`;
}

/* 工具格 + 离开。认输 / 数子 直接接弹窗 —— 它们本来就该开弹窗。 */
function toolBlock(o) {
  const t = (id, label, ic, dis) => tbtn({ id: o.ns + id, label, icon: ic, disabled: dis, src: 'RightSidebarPanel.tsx' });
  const d = (id, label, ic, dis) => dis
    ? tbtn({ id: o.ns + id, label, icon: ic, disabled: true, src: 'RightSidebarPanel.tsx' })
    : `<button class="tbtn" data-dialog="${id}" data-act="打开${label}确认框" data-src="RightSidebarPanel.tsx">${icon(ic, 'sm')}${label}</button>`;
  return `${tgrid(`
      ${t('terr', '领地', 'Map', o.lockAnalysis)}${t('hint', '建议', 'TipsAndUpdates', o.lockAnalysis)}
      ${t('chart', '图表', 'Timeline', o.lockAnalysis)}${t('undo', '悔棋', 'Undo', o.lockAnalysis || o.spectator)}
      ${t('pass', '停一手', 'PanToolAlt', o.spectator)}${d('resign', '认输', 'Flag', o.spectator || o.over)}
      ${d('count', '数子', 'Calculate', o.spectator || o.over)}${t('3d', '3D', 'ViewInAr')}`)}
    ${o.hint ? `<p class="dim" style="font-size:.72rem;margin:10px 0 0">${o.hint}</p>` : ''}
    <div style="margin-top:10px">
      ${o.spectator
      ? btn({ label: '退出观战', variant: 'outlined', color: 'inherit', full: true, icon: 'ExitToApp', act: '导航 ' + o.backTo, src: o.src })
      : `<button class="mbtn outlined err full" data-dialog="leave" data-act="打开离开确认框（离开将判负 / 弃权）" data-src="${esc(o.src)}">${icon('ExitToApp', 'sm')}离开对局</button>`}
    </div>`;
}

/* ───────────────────────────── 研究 ───────────────────────────── */
V2['research'] = function (b, vp) {
  const l3 = b === 'l3', l2 = b === 'l2', lib = b === 'lib';
  const stones = demoStones(l3 ? 34 : 12);

  if (l2) {
    return {
      board: { floor: 0, stones, coords: true },
      plate: plate2({ title: '研究室', sub: '正在分析 · 128 / 250 步', src: 'ResearchPage.tsx' }),
      railBody: sec2('分析进度', `
        <div style="margin:2px 0 10px;height:10px;border-radius:5px;background:rgba(255,255,255,.1);overflow:hidden">
          <div style="width:51%;height:100%;background:var(--jade);border-radius:5px"></div></div>
        <div class="rowbetween"><span class="mono" style="color:var(--jade-l);font-weight:700;font-size:1.15rem">51%</span>
          <span class="mono dim" style="font-size:.8rem">剩余 2分14秒</span></div>
        <p class="muted" style="margin:12px 0 0;font-size:.82rem;line-height:1.7">
          分析在后台跑，盘面留在左边，随时可以回到编辑。</p>`),
      actions: act2(btn({ label: '取消分析', variant: 'outlined', color: 'err', size: 'lg', full: true, act: 'handleReturnToEdit() → 回到 L1', src: 'ResearchPage.tsx:561' })),
    };
  }

  const railL1 = `
    ${sec2('对局信息', `<div class="stack g8">
      <div><label class="flabel">黑方</label><input class="field" value="黑方" aria-label="黑方" data-act="board.setPlayerBlack" data-src="ResearchSetupPanel.tsx"></div>
      <div><label class="flabel">白方</label><input class="field" value="白方" aria-label="白方" data-act="board.setPlayerWhite" data-src="ResearchSetupPanel.tsx"></div>
      <div class="inline" style="gap:8px">
        <div style="flex:1"><label class="flabel">棋盘</label><div class="selwrap"><select class="sel" aria-label="棋盘大小" data-act="board.setBoardSize" data-src="ResearchSetupPanel.tsx"><option>19×19</option><option>13×13</option><option>9×9</option></select>${icon('ArrowDropDown', 'sm')}</div></div>
        <div style="flex:1"><label class="flabel">规则</label><div class="selwrap"><select class="sel" aria-label="规则" data-act="board.setRules" data-src="ResearchSetupPanel.tsx"><option>中国规则</option><option>日本规则</option><option>韩国规则</option></select>${icon('ArrowDropDown', 'sm')}</div></div>
      </div>
      <div class="inline" style="gap:8px">
        <div style="flex:1"><label class="flabel">贴目</label><input class="field" type="number" step="0.5" value="7.5" aria-label="贴目" data-act="board.setKomi" data-src="ResearchSetupPanel.tsx"></div>
        <div style="flex:1"><label class="flabel">让子</label><div class="selwrap"><select class="sel" aria-label="让子" data-act="board.setHandicap" data-src="ResearchSetupPanel.tsx"><option>无</option><option>2子</option><option>3子</option><option>4子</option><option>5子</option><option>6子</option></select>${icon('ArrowDropDown', 'sm')}</div></div>
      </div></div>`)}
    ${sec2('编辑工具', tgrid(`
        ${[['0', '手数', 'FormatListNumbered'], ['2', '移动', 'OpenWith']].map(([i, l, ic]) =>
    tbtn({ id: 'r2-' + i, label: l, icon: ic, src: 'ResearchToolbar.tsx' })).join('')}
        ${tbtn({ id: 'r2-3', label: '删除', icon: 'DeleteForever', cls: 'danger', src: 'ResearchToolbar.tsx:191' })}
        ${gbtn({ label: '停一手', icon: 'PanToolAlt', dialog: 'pass', act: '打开停一手确认框', src: 'ResearchToolbar.tsx:295' })}
        ${[['4', '摆黑', STONE.b], ['5', '摆白', STONE.w], ['6', '交替', STONE.alt], ['7', '清空', 'LayersClear'], ['8', '建议', 'TipsAndUpdates'], ['9', '领地', 'Map']].map(([i, l, ic]) =>
    tbtn({ id: 'r2-' + i, label: l, icon: ic, on: l === '交替', src: 'ResearchToolbar.tsx' })).join('')}
        ${gbtn({ label: '打开', icon: 'FolderOpen', dialog: 'openmenu', act: '打开「打开棋谱」菜单', src: 'ResearchToolbar.tsx' })}
        ${gbtn({ label: '保存', icon: 'Save', dialog: 'savemenu', act: '打开「保存」菜单', src: 'ResearchToolbar.tsx' })}`))}`;
  /* 现状这里的「停一手」出现过两次：工具栏里一个、下面又一个 ——
     和对局页那对假的认输 / 数子是同一个毛病。只留一个，就是格子里
     那一个，并且让它真的去开确认框（现状工具栏那个才是开框的）。
     打开 / 保存 也不再是另一种尺寸的小描边键，并入同一块格子。 */

  const railL3 = `
    ${sec2('局面', `<div class="inline" style="gap:14px">
        <span class="stat"><b style="color:var(--jade-l)">54.2%</b><span>黑棋胜率</span></span>
        <span class="stat"><b>+1.8</b><span>领先（目）</span></span>
        <span class="stat"><b>34</b><span>当前手</span></span>
      </div>`)}
    ${sec2('AI 推荐', `<table style="width:100%;border-collapse:collapse;font-size:.8rem">
        <thead><tr class="dim" style="text-align:left"><th style="font-weight:500;padding:3px 0">着手</th><th style="font-weight:500">胜率</th><th style="font-weight:500">目差</th><th style="font-weight:500">推荐</th></tr></thead>
        <tbody class="mono">
          ${[['Q16', '54.2%', '+1.8', '92%'], ['D4', '52.9%', '+0.9', '61%'], ['R5', '51.1%', '+0.2', '34%']].map((r, i) => `
          <tr data-act="hover → 棋盘画变化图" data-src="ResearchAnalysisPanel.tsx" role="button" tabindex="0">
            <td style="padding:3px 0;${i ? '' : 'color:var(--jade-l)'}">${r[0]}</td><td>${r[1]}</td><td>${r[2]}</td><td>${r[3]}</td></tr>`).join('')}
        </tbody></table>`)}
    <div style="flex:none">
      <div class="tabs">
        <button role="tab" aria-selected="true" data-act="切到 走势图" data-src="ResearchAnalysisPanel.tsx">走势</button>
        <button role="tab" aria-selected="false" data-act="切到 妙手 (2)" data-src="ResearchAnalysisPanel.tsx">妙手 (2)</button>
        <button role="tab" aria-selected="false" data-act="切到 问题手 (5)" data-src="ResearchAnalysisPanel.tsx">问题手 (5)</button>
      </div>
      <div style="padding:12px 12px 4px">${trend2('r3')}</div>
      <div class="stack g4" style="padding:0 12px 12px">
        ${[57, 88, 121].map(n => `<button class="rowbetween" data-act="onMoveClick(${n}) → setCurrentMove(${n})" data-src="ResearchAnalysisPanel.tsx"
          style="width:100%;background:none;border:0;border-left:3px solid var(--ok);padding:6px 10px;color:inherit;font:inherit;cursor:pointer;text-align:left">
          <span style="font-size:.8rem">第 ${n} 手 · Q16</span><span class="mono" style="font-size:.76rem;color:var(--ok)">+6.2</span></button>`).join('')}
      </div>
    </div>`;

  return {
    board: {
      floor: 0, stones, coords: true,
      last: l3 ? [4, 11, 'B'] : null,
      ai: l3 ? [[15, 15, '54%', '+1.8'], [3, 3, '53%', '+0.9']] : null,
    },
    plate: plate2({
      title: '研究室',
      sub: l3 ? '第 34 手 / 250 手' : '摆盘编辑 · 12 手',
      status: l3 ? `<span class="chip ok">分析完成</span>` : `<span class="chip">编辑中</span>`,
      src: 'ResearchPage.tsx',
    }),
    railBody: l3 ? railL3 : railL1,
    actions: l3
      ? `<div class="inline" style="justify-content:center;gap:2px;padding:8px 8px 0">
           ${ibtn({ icon: 'SkipPrevious', label: '最初', act: 'handleL2MoveChange(0)', src: 'ResearchAnalysisPanel.tsx' })}
           ${ibtn({ icon: 'NavigateBefore', label: '后退', act: 'handleL2MoveChange(n-1)', src: 'ResearchAnalysisPanel.tsx' })}
           <button class="iconbtn" aria-label="播放" data-act="自动播放" data-src="ResearchAnalysisPanel.tsx" style="background:var(--jade);color:#eef4f0">${icon('PlayArrow')}</button>
           ${ibtn({ icon: 'NavigateNext', label: '前进', act: 'handleL2MoveChange(n+1)', src: 'ResearchAnalysisPanel.tsx' })}
           ${ibtn({ icon: 'SkipNext', label: '最终', act: 'handleL2MoveChange(total)', src: 'ResearchAnalysisPanel.tsx' })}
           <span class="mono muted" style="margin-left:6px;font-size:.78rem">34/250</span>
         </div>
         <div class="pad inline" style="gap:8px;padding-top:10px">
           ${btn({ label: '返回编辑', variant: 'outlined', color: 'inherit', act: 'handleReturnToEdit() → 回到 L1（模式退出，不是路由返回）', src: 'ResearchPage.tsx:434' })}
           ${btn({ label: '继续分析', variant: 'contained', full: true, act: '继续 KataGo 分析', src: 'ResearchAnalysisPanel.tsx' })}
         </div>`
      : `<div class="inline" style="justify-content:center;gap:2px;padding:8px 8px 0">
           ${ibtn({ icon: 'SkipPrevious', label: '第一手', act: 'board.handleMoveChange(0)', src: 'ResearchPage.tsx:608' })}
           ${ibtn({ icon: 'NavigateBefore', label: '上一手', act: 'board.handleMoveChange(n-1)', src: 'ResearchPage.tsx:615' })}
           <span class="mono muted" style="min-width:74px;text-align:center;font-size:.8rem">12 / 12 手</span>
           ${ibtn({ icon: 'NavigateNext', label: '下一手', act: 'board.handleMoveChange(n+1)', src: 'ResearchPage.tsx:630' })}
           ${ibtn({ icon: 'SkipNext', label: '最后一手', act: 'board.handleMoveChange(moves.length)', src: 'ResearchPage.tsx:637' })}
         </div>
         ${act2(btn({ label: '开始研究', variant: 'contained', size: 'lg', full: true, act: 'serializeToSGF → 创建研究会话 → 进入 L2', src: 'ResearchSetupPanel.tsx' }))}`,
    scrim: lib ? `<div class="dlg" style="max-width:640px" data-zone="dialog">
      <h3>棋谱库</h3>
      <div class="tabs" style="padding:0 22px">
        <button role="tab" aria-selected="true" data-act="切到 我的棋谱" data-src="CloudSGFPanel.tsx">我的棋谱</button>
        <button role="tab" aria-selected="false" data-act="切到 我的盘面" data-src="CloudSGFPanel.tsx">我的盘面</button>
        <button role="tab" aria-selected="false" data-act="切到 大赛棋谱" data-src="CloudSGFPanel.tsx">大赛棋谱</button>
      </div>
      <div style="padding:14px 22px 0"><div class="fieldwrap">${icon('Search', 'sm')}
        <input class="field" placeholder="搜索棋手、赛事..." aria-label="搜索棋手、赛事" data-act="过滤棋谱列表" data-src="CloudSGFPanel.tsx"></div></div>
      <div style="padding:16px 22px;max-height:300px;overflow:auto" class="stack g8">
        ${[['柯洁', '朴廷桓', 250], ['申真谞', '芈昱廷', 211], ['陈泓明', '姚钧耀', 194]].map(([a, c, m]) => `
          <button class="kcard" data-act="加载该棋谱到研究盘面" data-src="CloudSGFPanel.tsx">
            <div class="kmeta"><span>2026-08-12</span><span class="chip" style="height:18px;font-size:.62rem">${m}手</span></div>
            <div class="kplayers"><span class="side"><i class="kstone b"></i>${a}</span><span class="dim">vs</span><span class="side w">${c}<i class="kstone w"></i></span></div>
          </button>`).join('')}
      </div>
      <div class="acts">${btn({ label: '关闭', color: 'inherit', act: 'setLibraryOpen(false)', src: 'ResearchPage.tsx:688' })}</div>
    </div>` : null,
  };
};

/* ───────────────────────────── 死活题 · 解题 ───────────────────────────── */
V2['tsumego-problem'] = function (b, vp) {
  const solved = b === 'solved', failed = b === 'failed';
  /* 坐标：现状 TsumegoBoard.tsx:197 无条件画，没有开关也没有 prop。
     改版按对局页的样子办 —— 默认开，右栏给一条滑轨。 */
  const coords = S.toggles['ts2-coords'] != null ? S.toggles['ts2-coords'] : true;
  /* 提示 / 试下 现在是工具格里两个有按下态的键，所以分支只当默认值用，
     点了之后棋盘要真的跟着变（提示 → 正解点，试下 → 显示手数）。 */
  const tryMode = S.toggles['ts2-try'] != null ? S.toggles['ts2-try'] : b === 'try';
  const hint = S.toggles['ts2-hint'] != null ? S.toggles['ts2-hint'] : b === 'hint';
  return {
    board: {
      floor: 0, stones: TSU_STONES, coords, numbers: tryMode, last: [18, 16, 'B'],
      ai: hint ? [[18, 17, '', '']] : null,
    },
    stageOverlay: solved
      ? `<div style="position:absolute;inset:0;display:grid;place-items:center;background:rgba(48,160,110,.14);pointer-events:none">
           <div class="chip ok filled" style="height:52px;font-size:1.35rem;padding:0 28px">正确！</div></div>`
      : '',
    plate: plate2({
      title: '第 3 题', sub: '3D · 死活 · 3 / 20',
      status: solved ? `<span class="chip ok filled">正确</span>` : failed ? `<span class="chip err filled">错误</span>` : `<span class="chip">黑先</span>`,
      backTo: '/galaxy/tsumego/3d/life-death', src: 'TsumegoProblemPage.tsx:363',
    }),
    railBody: `
      ${sec2('', CRUMB([['死活题', '/galaxy/tsumego'], ['3D', '/galaxy/tsumego/3d'], ['死活', '/galaxy/tsumego/3d/life-death'], ['第3题', null]], 'TsumegoProblemPage.tsx:366-397'), 'padding-top:12px;padding-bottom:12px')}
      ${sec2('本题', `
        <div class="inline" style="gap:10px;margin-bottom:12px">
          <span style="width:20px;height:20px;border-radius:50%;background:#1a1a1a;border:1px solid #333"></span>
          <span style="font-size:1rem">${solved ? '正确！' : failed ? '错误' : '黑先'}</span>
        </div>
        <div class="rowbetween muted" style="font-size:.85rem">
          <span class="inline" style="gap:6px">${icon('Timer', 'sm')}<span class="mono">0:07</span></span>
          <span>尝试次数: ${failed ? 2 : solved ? 1 : 0}</span>
        </div>`)}
      ${sec2('', `${tgrid(`
          ${tbtn({ id: 'ts2-hint', label: '提示', icon: 'TipsAndUpdates', on: hint, act: 'toggleHint() → 棋盘正解点画绿色半透明圆', src: 'TsumegoProblemControls.tsx' })}
          ${tbtn({ id: 'ts2-try', label: '试下', icon: 'TouchApp', on: tryMode, act: tryMode ? 'exitTryMode()' : 'enterTryMode() —— 自由摆子，不判断对错', src: 'TsumegoProblemControls.tsx' })}
          ${gbtn({ label: '撤销', icon: 'Undo', act: 'undo() — 快捷键 U / Ctrl+Z', src: 'TsumegoProblemControls.tsx' })}
          ${gbtn({ label: '重置', icon: 'Refresh', act: 'reset() — 快捷键 R', src: 'TsumegoProblemControls.tsx' })}`)}
        ${hint ? `<div style="margin-top:12px;padding:12px;background:rgba(232,150,57,.1);border-left:3px solid var(--warn);border-radius:4px;font-size:.85rem">黑先</div>
          <p class="dim" style="font-size:.72rem;margin:8px 0 0">后端 hint 字段是 String(16)，只存了「黑先」；真正的提示是棋盘上那个绿点。</p>` : ''}
        ${tryMode ? `<p class="muted" style="margin:10px 0 0;font-size:.82rem;line-height:1.7">试下中：自由摆子，不判断对错。退出试下会清掉试下的子。</p>` : ''}`)}
      ${sec2('', swrow({ id: 'ts2-coords', label: '坐标', on: true, src: 'TsumegoBoard.tsx:197' }))}`,
    actions: `<div class="pad inline" style="gap:8px;padding-top:12px">
        ${btn({ label: '上一题', variant: 'outlined', full: true, icon: 'NavigateBefore', act: 'navigate 上一题', src: 'TsumegoProblemControls.tsx' })}
        ${btn({ label: '下一题', variant: solved ? 'contained' : 'outlined', full: true, act: 'navigate 下一题', src: 'TsumegoProblemControls.tsx' })}
      </div>`,
    snack: failed ? `<div class="snack error bottom">此手不成立 ${ibtn({ icon: 'Close', label: '关闭', size: 'sm', act: 'setSnackbar(open:false)', src: 'TsumegoProblemPage.tsx:440' })}</div>` : '',
  };
};

/* ───────────────────────────── 复盘 · 报告详情 ───────────────────────────── */
V2['report-detail'] = function (b, vp) {
  if (b === 'loading') {
    return {
      board: {},
      plate: plate2({ title: '正在加载报告', sub: '　', backTo: '/galaxy/report', src: 'ReportDetailPage.tsx' }),
      railBody: `<div class="pad stack g12"><div class="skel" style="height:110px"></div><div class="skel" style="height:150px"></div><div class="skel" style="height:170px"></div></div>`,
      actions: `<div class="pad"><div class="skel" style="height:40px"></div></div>`,
    };
  }
  if (b === 'error') {
    return {
      board: {},
      plate: plate2({ title: '复盘报告', backTo: '/galaxy/report', src: 'ReportDetailPage.tsx' }),
      railBody: `<div class="pad"><div class="alert error" style="margin-bottom:14px">加载报告失败</div>
        ${btn({ label: '返回报告列表', variant: 'outlined', act: '导航 /galaxy/report', src: 'ReportDetailPage.tsx:104' })}</div>`,
      actions: `<div class="pad"><div class="skel" style="height:40px"></div></div>`,
    };
  }
  const nosgf = b === 'nosgf';
  return {
    board: nosgf ? null : { floor: 0, stones: demoStones(36), coords: true, last: [9, 13, 'B'], ai: [[15, 15, '54%', '+1.8'], [3, 15, '52%', '+0.9'], [16, 5, '51%', '+0.2']] },
    stage: nosgf ? `<div style="display:grid;place-items:center;width:100%;height:100%"><div class="alert info">没有可用于复盘展示的 SGF 数据。</div></div>` : null,
    plate: plate2({
      title: '申真谞 vs 柯洁', sub: '250 手 · 普通报告',
      status: `<span class="chip ok">已完成</span>`,
      backTo: '/galaxy/report', src: 'ReportDetailPage.tsx:113',
    }),
    railBody: `
      ${sec2('对局信息', `
        <div class="rowbetween" style="font-size:.875rem"><span class="inline" style="gap:6px"><i class="kstone b"></i>申真谞</span><span class="mono">9段</span></div>
        <div class="rowbetween" style="font-size:.875rem;margin-top:4px"><span class="inline" style="gap:6px"><i class="kstone w"></i>柯洁</span><span class="mono">9段</span></div>
        <div class="inline" style="gap:14px;margin-top:12px">
          <span class="stat"><b style="color:var(--jade-l)">54.2%</b><span>黑棋胜率</span></span>
          <span class="stat"><b>+1.8</b><span>领先（目）</span></span>
          <span class="stat"><b>250</b><span>手数</span></span>
        </div>`)}
      ${sec2('AI 推荐', `<table style="width:100%;border-collapse:collapse;font-size:.8rem">
        <thead><tr class="dim" style="text-align:left"><th style="font-weight:500;padding:3px 0">着手</th><th style="font-weight:500">胜率</th><th style="font-weight:500">目差</th><th style="font-weight:500">推荐</th></tr></thead>
        <tbody class="mono">
          <tr data-act="hover → 棋盘画变化图 pvMoves" data-src="AiAnalysis.tsx" role="button" tabindex="0"><td style="padding:3px 0;color:var(--jade-l)">Q16</td><td>54.2%</td><td>+1.8</td><td>92%</td></tr>
          <tr data-act="hover → 棋盘画变化图 pvMoves" data-src="AiAnalysis.tsx" role="button" tabindex="0"><td style="padding:3px 0">D4</td><td>52.9%</td><td>+0.9</td><td>61%</td></tr>
        </tbody></table>`)}
      <div style="flex:none">
        <div class="tabs">
          <button role="tab" aria-selected="true" data-act="setTab(0)" data-src="TrendChart.tsx">走势</button>
          <button role="tab" aria-selected="false" data-act="setTab(1)" data-src="TrendChart.tsx">妙手 (2)</button>
          <button role="tab" aria-selected="false" data-act="setTab(2)" data-src="TrendChart.tsx">失误 (5)</button>
        </div>
        <div style="padding:12px 12px 4px">${trend2('rd2')}</div>
        <div class="stack g4" style="padding:0 12px 12px">
          ${[[57, '+6.2', 'ok'], [88, '-8.1', 'err']].map(([n, v, k]) => `<button class="rowbetween"
            data-act="onMoveClick(${n}) → setCurrentMove(${n})" data-src="TrendChart.tsx"
            style="width:100%;background:none;border:0;border-left:3px solid var(--${k});padding:5px 10px;color:inherit;font:inherit;cursor:pointer;text-align:left">
            <span style="font-size:.8rem">第 ${n} 手 · ${k === 'ok' ? '妙手' : '失误'}</span>
            <span class="mono" style="font-size:.76rem;color:var(--${k})">${v} 目</span></button>`).join('')}
        </div>
      </div>
      ${sec2('', btn({ label: '进入研究室', variant: 'outlined', full: true, icon: 'Science', act: '导航 /galaxy/research?game_id={id}（现状漏了棋局参数，改版补上）', src: 'ReportDetailPage.tsx:118' }))}`,
    controls: `<div class="pad">
        ${tgrid(`
        ${tbtn({ id: 'rd2-try', label: '试下', icon: 'TouchApp', src: 'ReportDetailPage.tsx:167' })}
        ${tbtn({ id: 'rd2-terr', label: '领地', icon: 'Map', src: 'ReportDetailPage.tsx:184' })}
        ${tbtn({ id: 'rd2-num', label: '手数', icon: 'FormatListNumbered', src: 'ReportDetailPage.tsx:207' })}
        ${tbtn({ id: 'rd2-ai', label: '建议', icon: 'TipsAndUpdates', on: true, src: 'ReportDetailPage.tsx:218' })}`)}
        <div class="rowbetween" style="margin-top:8px">
          <span class="dim mono" style="font-size:.72rem">试下: Q16 → R14</span>
          ${btn({ label: '清空', variant: 'outlined', size: 'sm', act: 'setTryMoves([])（不退出试下）', src: 'ReportDetailPage.tsx:232' })}
        </div>
      </div>`,
    actions: playback(250, 250, 'PlaybackBar.tsx'),
  };
};

/* ───────────────────────────── 棋谱库 ───────────────────────────── */
V2['kifu'] = function (b, vp) {
  const preview = b === 'preview', loading = b === 'loading', empty = b === 'empty';
  return {
    board: preview ? { floor: 0, stones: demoStones(38), coords: true, last: [15, 9, 'W'] } : null,
    stage: preview ? null : `<div style="display:grid;place-items:center;width:100%;height:100%">
      ${loading ? `<div class="spin"></div>` : `<p class="dim">从右边选一局棋谱预览</p>`}</div>`,
    plate: plate2({
      title: '棋谱库',
      sub: loading ? '　' : preview ? '韩一洲 vs 张强 · 250 手' : '25,062 条记录',
      status: preview ? `<span class="chip">黑中盘胜</span>` : '',
      src: 'KifuLibraryPage.tsx',
    }),
    railBody: `
      ${sec2('', `<div class="fieldwrap">${icon('Search', 'sm')}
        <input class="field" placeholder="棋手 / 赛事 / 日期" aria-label="按棋手、赛事、日期搜索" data-act="Enter → setSearchParams({q}) 重查列表" data-src="KifuLibraryPage.tsx:302"></div>
        ${loading ? '' : `<p class="dim mono" style="margin:8px 0 0;font-size:.72rem">25,062 条记录 · 第 1 / 1044 页</p>`}`, 'padding-top:12px;padding-bottom:12px')}
      <div style="padding:10px 12px">
        ${loading ? `<div class="stack g8">${'<div class="skel" style="height:58px"></div>'.repeat(6)}</div>`
      : empty ? `<div style="text-align:center;padding:40px 0"><div style="font-size:1.05rem;color:var(--tx2)">未找到棋谱</div>
              <div class="dim" style="margin-top:6px">"柯洁 2019"</div></div>`
        : `<div class="stack g8">${rep(KIFU, STRESS() ? 4 : 1).map((r, i) => kifuCard(r, i, preview && i === 0)).join('')}</div>`}
      </div>
      ${loading || empty ? '' : `<div style="padding:4px 0 12px">
        <div class="pager">
          ${ibtn({ icon: 'ChevronLeft', label: '上一页', size: 'sm', act: 'handlePageChange(page-1)', src: 'KifuLibraryPage.tsx:386' })}
          ${[1, 2, 3, 4, 5].map(p => `<button aria-current="${p === 1}" data-act="handlePageChange(${p}) → 改 URL 重查" data-src="KifuLibraryPage.tsx:386">${p}</button>`).join('')}
          <span class="dim">…</span>
          <button data-act="handlePageChange(1044)" data-src="KifuLibraryPage.tsx:386">1044</button>
          ${ibtn({ icon: 'ChevronRight', label: '下一页', size: 'sm', act: 'handlePageChange(page+1)', src: 'KifuLibraryPage.tsx:386' })}
        </div></div>`}`,
    actions: preview
      ? `<div class="inline" style="justify-content:center;gap:2px;padding:8px 8px 0">
           ${ibtn({ icon: 'SkipPrevious', label: '第一手', act: 'setPreviewCurrentMove(0)', src: 'KifuLibraryPage.tsx:435' })}
           ${ibtn({ icon: 'NavigateBefore', label: '上一手', act: 'setPreviewCurrentMove(m-1)', src: 'KifuLibraryPage.tsx:443' })}
           <span class="mono muted" style="min-width:80px;text-align:center;font-size:.8rem">250 / 250 手</span>
           ${ibtn({ icon: 'NavigateNext', label: '下一手', act: 'setPreviewCurrentMove(m+1)', src: 'KifuLibraryPage.tsx:463' })}
           ${ibtn({ icon: 'SkipNext', label: '最后一手', act: 'setPreviewCurrentMove(moves.length)', src: 'KifuLibraryPage.tsx:471' })}
         </div>
         ${act2(btn({ label: '在研究中打开', variant: 'contained', size: 'lg', full: true, act: '导航 /galaxy/research?kifu_id=8502', src: 'KifuLibraryPage.tsx:480' }))}`
      : act2(btn({ label: '在研究中打开', variant: 'contained', size: 'lg', full: true, disabled: true, act: '未选中棋谱时禁用', src: 'KifuLibraryPage.tsx:480' })),
  };
};

/* ───────────────────────────── 人人对弈 · 对局室 ───────────────────────────── */
V2['game-room'] = function (b, vp) {
  if (b === 'loading') {
    return {
      board: {},
      plate: plate2({ title: '正在进入对局室', sub: '　', backTo: '/galaxy/play/human', src: 'GameRoomPage.tsx' }),
      railBody: `<div class="pad stack g12"><div class="skel" style="height:96px"></div><div class="skel" style="height:130px"></div></div>`,
      actions: `<div class="pad"><div class="skel" style="height:40px"></div></div>`,
    };
  }
  if (b === 'error') {
    return {
      board: {},
      plate: plate2({ title: '对局室', backTo: '/galaxy/play/human', src: 'GameRoomPage.tsx' }),
      railBody: `<div class="pad"><div class="alert error" style="margin-bottom:14px">对局会话不存在或已结束</div>
        ${btn({ label: '返回大厅', variant: 'outlined', act: '导航 /galaxy/play/human', src: 'GameRoomPage.tsx:165' })}</div>`,
      actions: `<div class="pad"><div class="skel" style="height:40px"></div></div>`,
    };
  }
  const spectator = b === 'spectator', ended = b === 'ended', is3d = b === '3d';
  const tool = (id, label, ic, dis) => tbtn({ id: 'gr2-' + id, label, icon: ic, disabled: dis, src: 'RightSidebarPanel.tsx' });
  /* 名字独占一行，关注 / 暂停下沉到时钟那一行的右侧 ——
     320 里把它们和名字挤在一行会把「fan」截成「f…」。 */
  const player = (nm, stone, clock, meta, extra) => `<div class="card" style="flex:1;padding:10px;border-radius:10px;min-width:0">
    <div class="inline" style="gap:6px;flex-wrap:nowrap"><i class="kstone ${stone}"></i>
      <span style="font-weight:600;font-size:.84rem;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${nm}</span></div>
    <div class="rowbetween" style="margin-top:2px;flex-wrap:nowrap;gap:2px">
      <span class="mono" style="font-size:1.2rem;font-weight:600">${clock}</span>
      <span class="pcard-icons">
        ${ibtn({ icon: 'PersonAdd', label: '关注 ' + nm, size: 'sm', act: 'handleToggleFollow(name) → API.followUser / unfollowUser', src: 'PlayerCard.tsx' })}${extra || ''}</span>
    </div>
    <div class="dim" style="font-size:.68rem">${meta}</div></div>`;

  return {
    board: is3d ? null : { floor: 0, stones: demoStones(ended ? 40 : 26), coords: true, last: ended ? [15, 9, 'W'] : [12, 9, 'W'], territory: ended ? [[2, 2, 1], [3, 2, 1], [2, 3, 1], [16, 16, -1], [15, 16, -1], [16, 15, -1]] : null },
    stage: is3d ? stage3d(demoStones(26)) : null,
    plate: plate2({
      title: '对局室', sub: `${spectator ? 'bob' : 'fan'} vs cat · 19 路`,
      status: spectator ? `<span class="chip">观战中</span>`
        : ended ? `<span class="chip ok">已结束</span>`
          : `<span class="chip filled pulse"><i class="dot"></i>轮到你了</span>`,
      backTo: '/galaxy/play/human', src: 'GameRoomPage.tsx',
    }),
    railBody: `
      ${sec2('', `<div class="rowbetween" style="gap:10px;align-items:stretch">
          ${pcard({ name: spectator ? 'bob' : 'fan', stone: 'b', clock: '08:24', meta: '5k · 提子 3', active: !ended, extra: ibtn({ icon: 'Pause', label: '暂停/继续计时', size: 'sm', act: 'onPauseTimer()（本页不可达，仅人机对局页可见）', src: 'PlayerCard.tsx' }) })}
          ${pcard({ name: 'cat', stone: 'w', clock: '06:51', meta: '4k · 提子 5', active: false })}
        </div>
        <div class="rowbetween muted" style="margin-top:10px;font-size:.74rem;gap:6px">
          <span style="min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">中国规则 · 贴 7.5 目</span>
          <span class="inline dim" style="gap:4px;flex:none">${icon('Visibility', 'xs')}3 观众</span>
        </div>`, 'padding-top:12px')}
      ${sec2('', `${toolBlock({ ns: 'gr2-', spectator, over: ended, lockAnalysis: true, backTo: '/galaxy/play/human', src: 'GameRoomPage.tsx:198' })}
        ${ended ? `<div class="alert success" style="margin-top:12px">数子结束：黑胜 2.5 目</div>` : ''}`)}
      ${sec2('', `${swrow({ id: 'gr2-coords', label: '坐标', on: true, src: 'RightSidebarPanel.tsx' })}
        ${swrow({ id: 'gr2-numbers', label: '手数', src: 'RightSidebarPanel.tsx' })}
        ${swrow({ id: 'gr2-drop', label: '落子特效', src: 'RightSidebarPanel.tsx' })}`)}`,
    actions: navRow('RightSidebarPanel.tsx'),
  };
};

/* ───────────────────────────── 直播 · 列表页 ───────────────────────────── */
V2['live-list'] = function (b, vp) {
  const upcoming = b === 'upcoming', loading = b === 'loading', empty = b === 'empty', ok = b === 'ok';
  const rows = () => rep(LIVEROWS, STRESS() ? 3 : 1).map(([bl, wh, ev, mv, live], i) => `
    <button class="kcard ${ok && i === 0 ? 'sel' : ''}" data-act="handleSelectMatch(id) → 换棋盘" data-src="LivePage.tsx:141">
      <div class="kmeta"><span>${ev}</span><span>${live ? '<span class="chip err filled pulse" style="height:16px;font-size:.62rem"><i class="dot"></i>直播中</span>' : `${mv} 手`}</span></div>
      <div class="kplayers"><span class="side"><i class="kstone b"></i>${bl}</span><span class="dim">vs</span><span class="side w">${wh}<i class="kstone w"></i></span></div>
    </button>`).join('');
  return {
    board: ok ? { floor: 0, stones: demoStones(34), coords: true, last: [4, 11, 'B'] } : null,
    stage: ok ? null : `<div style="display:grid;place-items:center;width:100%;height:100%">
      ${loading ? `<div class="spin"></div>` : `<p class="dim">从右边选一场对局观看</p>`}</div>`,
    plate: plate2({
      title: '直播',
      sub: ok ? `${NOW.black} vs ${NOW.white} · 194 手` : upcoming ? '赛事预告' : '选择一场对局',
      status: ok ? `<span class="chip err filled pulse"><i class="dot"></i>直播中</span>` : '',
      src: 'LivePage.tsx',
    }),
    railBody: `
      <div class="tabs">
        <button role="tab" aria-selected="${!upcoming}" data-act="setRightTab(0)" data-src="LivePage.tsx:119">精选对局</button>
        <button role="tab" aria-selected="${upcoming}" data-act="setRightTab(1)" data-src="LivePage.tsx:120">赛事预告</button>
      </div>
      <div style="padding:14px 12px">
        ${upcoming
        ? `<div class="stack g8">${[['第 9 届应氏杯', '2026-08-24 13:00', '2 天后'], ['三星火灾杯预选', '2026-08-27 10:00', '5 天后']].map(([n, t2, d]) => `
              <div class="kcard" style="cursor:default"><div class="kmeta"><span>${n}</span><span>${d}</span></div>
              <div class="rowbetween"><span class="mono muted" style="font-size:.78rem">${t2}</span>
              <span class="inline" style="gap:4px">
                ${ibtn({ icon: 'Pause', label: '暂停自动轮播', size: 'sm', act: '暂停 UpcomingList 轮播', src: 'UpcomingList.tsx' })}
                <button data-act="打开赛事官方页" data-src="UpcomingList.tsx" style="background:none;border:0;color:var(--info);cursor:pointer;font-size:.76rem;text-decoration:underline;text-underline-offset:2px">官方信息</button>
              </span></div></div>`).join('')}</div>`
        : loading ? `<div class="stack g8">${'<div class="skel" style="height:58px"></div>'.repeat(5)}</div>`
          : `<p class="sec-label">正在直播 (2)</p><div class="stack g8">${rows()}</div>
               <p class="sec-label" style="margin-top:18px">历史对局</p><div class="stack g8">${rows()}</div>`}
      </div>`,
    actions: upcoming
      ? act2(btn({ label: '进入直播', variant: 'contained', size: 'lg', full: true, disabled: true, act: '预告页没有可进入的对局', src: 'LivePage.tsx:171' }))
      : `${ok ? playback(194, 194, 'PlaybackBar.tsx', true) : ''}
         ${act2(btn({ label: ok ? '进入直播' : '查看棋谱', variant: 'contained', size: 'lg', full: true, disabled: empty || loading, act: '导航 /galaxy/live/{matchId}', src: 'LivePage.tsx:171' }))}`,
  };
};

/* ───────────────────────────── 复盘 · 列表 ───────────────────────────── */
V2['reports'] = function (b, vp) {
  if (b === 'guest') {
    return {
      board: null,
      stage: `<div style="display:grid;place-items:center;width:100%;height:100%;padding:24px"><div style="max-width:360px;text-align:center">
        <div class="alert info" style="justify-content:center">请先登录后查看和生成复盘报告。</div></div></div>`,
      plate: plate2({ title: '复盘', sub: '未登录', src: 'ReportsPage.tsx' }),
      railBody: `<div class="pad"><p class="muted" style="margin:0 0 14px;font-size:.85rem;line-height:1.7">
        登录后可以导入棋谱、生成普通/深度报告，并在这里预览每一局。</p></div>`,
      actions: act2(btn({ label: '登录', variant: 'contained', size: 'lg', full: true, icon: 'Login', act: '打开 LoginModal', src: 'ReportsPage.tsx' })),
    };
  }
  const loading = b === 'loading', empty = b === 'empty';
  const cardFor = ([title, date, moves, st]) => `<div class="kcard" role="button" tabindex="0"
    data-act="setSelectedGameId(id) → 换棋盘预览（整卡可点，Enter/Space 同效）" data-src="ReportGameCard.tsx:104">
    <div class="rowbetween" style="margin-bottom:8px">
      <div style="min-width:0"><div style="font-size:.88rem;font-weight:600;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${title}</div>
      <div class="dim mono" style="font-size:.7rem">${date} · ${moves} 手</div></div>
      ${ibtn({ icon: 'DeleteOutline', label: '删除棋局', size: 'sm', act: 'setDeleteTarget(id) → 删除确认弹窗', src: 'ReportGameCard.tsx:125' })}
    </div>
    <div class="inline" style="gap:6px">
      ${st === 'done' ? `${btn({ label: '普通报告', variant: 'outlined', size: 'sm', act: '导航 /galaxy/report/{id}', src: 'ReportGameCard.tsx:202' })}
         ${btn({ label: '深度报告', variant: 'outlined', size: 'sm', act: '导航 /galaxy/report/{id}', src: 'ReportGameCard.tsx:215' })}` : ''}
      ${st === 'running' ? `<span class="chip warn">普通报告 生成中</span>` : ''}
      ${st === 'failed' ? btn({ label: '重试普通报告', variant: 'outlined', size: 'sm', color: 'err', act: 'POST /api/v1/reports/{id}/retry', src: 'ReportGameCard.tsx:229' }) : ''}
      ${st === 'none' ? dlgOpen('imp', '生成报告', { variant: 'contained', size: 'sm', src: 'ReportGameCard.tsx:257' }) : ''}
    </div></div>`;
  return {
    board: loading || empty ? null : { floor: 0, stones: demoStones(36), coords: true, last: [9, 13, 'B'] },
    stage: loading ? `<div style="display:grid;place-items:center;width:100%;height:100%"><div class="spin"></div></div>`
      : empty ? `<div style="display:grid;place-items:center;width:100%;height:100%"><p class="dim">还没有可预览的棋局。</p></div>` : null,
    plate: plate2({
      title: '复盘',
      sub: empty ? '选择棋局' : loading ? '　' : '申真谞 vs 柯洁 · 250 手',
      status: empty || loading ? '' : `<span class="chip ok">已完成</span>`,
      src: 'ReportsPage.tsx',
    }),
    railBody: `
      ${sec2('', `<p class="muted" style="margin:0 0 12px;font-size:.8rem;line-height:1.6">
          选一局在左边预览棋盘；报告生成和跳转都在棋局卡片上完成。</p>
        <div class="inline" style="gap:6px;margin-bottom:12px">
          <span class="chip warn">1 生成中</span><span class="chip">2 排队中</span><span class="chip err">1 失败</span>
        </div>
        <div class="stack g8">
          ${dlgOpen('imp', '导入棋谱', { variant: 'outlined', icon: 'CloudDownload', src: 'ReportImportMenu.tsx:17' })}
          <div class="fieldwrap">${icon('Search', 'sm')}<input class="field" placeholder="棋手 / 标题 / 赛事" aria-label="按棋手、标题或赛事搜索" data-act="Enter → handleSearch()" data-src="ReportsPage.tsx:436"></div>
        </div>`, 'padding-top:12px')}
      <div style="padding:12px">
        ${loading ? `<div class="stack g8">${'<div class="skel" style="height:82px"></div>'.repeat(4)}</div>`
      : empty ? `<p class="dim" style="text-align:center;padding:32px 0">还没有棋局，先导入一局再生成报告。</p>`
        : `<div class="stack g8">${rep(REPORTS, STRESS() ? 5 : 1).map(cardFor).join('')}</div>
             <div class="pager" style="margin-top:12px">
               ${[1, 2, 3].map(p => `<button aria-current="${p === 1}" data-act="handlePageChange(${p})" data-src="ReportsPage.tsx">${p}</button>`).join('')}
             </div>`}
      </div>`,
    actions: loading || empty ? act2(btn({ label: '导入棋谱', variant: 'contained', size: 'lg', full: true, icon: 'CloudDownload', act: 'setLocalImportOpen(true)', src: 'ReportImportMenu.tsx:17' }))
      : playback(250, 250, 'PlaybackBar.tsx'),
  };
};

/* ───────────────────────────── 自由对局中 ───────────────────────────── */
V2['game-free'] = function (b, vp) {
  const is3d = b === '3d';
  return {
    board: is3d ? null : { floor: 0, stones: demoStones(28), coords: true, last: [12, 9, 'W'] },
    stage: is3d ? stage3d(demoStones(28)) : null,
    plate: plate2({
      title: '自由对弈', sub: '智星棋手 5K · 28 手',
      status: `<span class="chip">对局中</span>`,
      backTo: '/galaxy/play/ai?mode=free', src: 'GamePage.tsx',
    }),
    railBody: `
      ${sec2('', `<div class="alert warning" style="align-items:center;flex-wrap:wrap">
          <span style="flex:1;min-width:150px">暂时无法确认本局状态，请重试</span>
          ${btn({ label: '重试', size: 'sm', color: 'inherit', act: 'setLifecycleRetry(v => v + 1) → 重启轮询', src: 'GamePage.tsx:449' })}
          ${ibtn({ icon: 'Close', label: 'Close', size: 'sm', act: 'setResignError(null) —— MUI Alert 内置关闭键', src: 'GamePage.tsx:447' })}
        </div>`, 'padding-top:12px')}
      ${sec2('', `<div class="rowbetween" style="gap:10px;align-items:stretch">
          ${pcard({ name: 'fan', stone: 'b', clock: '09:12', meta: '5k · 提子 2', active: true })}
          ${pcard({ name: '智星棋手', stone: 'w', clock: '07:48', meta: '5K · 提子 4', active: false })}
        </div>`)}
      ${sec2('', toolBlock({ ns: 'gf2-', backTo: '/galaxy/play/ai?mode=free', src: 'GamePage.tsx:557' }))}
      ${sec2('胜率走势', trend2('gf2'))}
      ${sec2('', `${swrow({ id: 'gf2-coords', label: '坐标', on: true, src: 'RightSidebarPanel.tsx' })}
        ${swrow({ id: 'gf2-numbers', label: '手数', src: 'RightSidebarPanel.tsx' })}
        ${swrow({ id: 'gf2-drop', label: '落子特效', src: 'RightSidebarPanel.tsx' })}`)}`,
    actions: navRow('RightSidebarPanel.tsx'),
  };
};

/* ───────────────── 升降级对局中（照抄对象之一，改版按同一条契约） ───────────────── */
V2['game-rated'] = function (b, vp) {
  const settled = b === 'settled', is3d = b === '3d';
  const banner = b === 'stalled'
    ? `<div class="alert warning">阶梯引擎不可用，AI 无法落子 · 本局不计入升降级，请退出本局</div>`
    : b === 'pending'
      ? `<div class="alert warning" style="align-items:center;flex-wrap:wrap">
           <span style="flex:1;min-width:150px">暂时无法确认本局状态，请重试</span>
           ${btn({ label: '重试', size: 'sm', color: 'inherit', act: 'setLifecycleRetry(v=>v+1) → 重启 5s 轮询', src: 'GamePage.tsx:449' })}
           ${ibtn({ icon: 'Close', label: '关闭', size: 'sm', act: 'setResignError(null)', src: 'GamePage.tsx:447' })}</div>`
      : '';
  return {
    board: is3d ? null : {
      floor: 0, stones: demoStones(settled ? 40 : 28), coords: true, last: [12, 9, 'W'],
      territory: settled ? [[2, 2, 1], [3, 2, 1], [2, 3, 1], [16, 16, -1], [15, 16, -1], [16, 15, -1]] : null,
    },
    stage: is3d ? stage3d(demoStones(28)) : null,
    plate: plate2({
      title: '升降级对弈', sub: '智星棋手 3K · 28 手',
      status: settled ? `<span class="chip ok">已结算</span>` : `<span class="chip">对局中</span>`,
      backTo: '/galaxy/play/ai?mode=rated', src: 'GamePage.tsx:518',
    }),
    railBody: `
      ${banner ? sec2('', banner, 'padding-top:12px') : ''}
      ${settled ? sec2('', `<div class="inline" style="gap:10px;margin-bottom:8px"><span style="color:var(--ok)">${icon('CheckCircle')}</span>
          <span style="font-weight:600">晋级 2K</span></div>
        <p class="muted" style="margin:0 0 12px;font-size:.85rem;line-height:1.6">本局已计入升降级 · 净胜 +3，升一档，计数归零。</p>
        <div class="inline" style="gap:6px">
          ${btn({ label: '再来一局', variant: 'contained', size: 'sm', act: '导航 /galaxy/play/ai?mode=rated', src: 'AiLadderSettlementPanel.tsx' })}
          ${btn({ label: '返回对局', variant: 'outlined', size: 'sm', act: '导航 /galaxy/play', src: 'AiLadderSettlementPanel.tsx' })}
          ${btn({ label: '重试', color: 'inherit', size: 'sm', act: 'feedback.retry() → 重新轮询结算', src: 'AiLadderSettlementPanel.tsx' })}
        </div>`, banner ? '' : 'padding-top:12px') : ''}
      ${sec2('', `<div class="rowbetween" style="gap:10px;align-items:stretch">
          ${pcard({ name: 'fan', stone: 'b', clock: '09:12', meta: '3K · 提子 2', active: !settled, extra: ibtn({ icon: 'Pause', label: '暂停/继续计时', size: 'sm', act: 'onPauseTimer()', src: 'PlayerCard.tsx' }) })}
          ${pcard({ name: '智星棋手', stone: 'w', clock: '07:48', meta: '3K · 提子 4', active: false })}
        </div>`, (banner || settled) ? '' : 'padding-top:12px')}
      ${sec2('', toolBlock({
      ns: 'g2-', over: settled, lockAnalysis: true,
      hint: '升降级对局中不开放 AI 分析、改规则、改贴目、改让子或改强度。',
      backTo: '/galaxy/play/ai?mode=rated', src: 'GamePage.tsx:459',
    }))}
      ${sec2('', `${swrow({ id: 'g2-coords', label: '坐标', on: true, src: 'RightSidebarPanel.tsx' })}
        ${swrow({ id: 'g2-numbers', label: '手数', src: 'RightSidebarPanel.tsx' })}
        ${swrow({ id: 'g2-drop', label: '落子特效', src: 'RightSidebarPanel.tsx' })}`)}`,
    actions: navRow('RightSidebarPanel.tsx'),
  };
};

/* ───────────────────────────── 教程 · 变化图 ───────────────────────────── */
V2['tutorial-figure'] = function (b, vp) {
  if (b === 'error') {
    return {
      board: {},
      plate: plate2({ title: '变化图', backTo: 'navigate(-1)', src: 'TutorialFigurePage.tsx:267' }),
      railBody: `<div class="pad"><div class="alert error" style="margin-bottom:14px">加载小节失败</div>
        ${btn({ label: '重试', variant: 'outlined', act: 'load()', src: 'TutorialFigurePage.tsx:261' })}</div>`,
      actions: `<div class="pad"><div class="skel" style="height:40px"></div></div>`,
    };
  }
  const editing = b === 'edit', narration = b === 'narration', debug = b === 'debug', nodata = b === 'nodata';
  /* 竖屏放不下并排：410 的 stage 让出 34% 只剩 280 的棋盘。
     所以对照层只在桌面档出现，竖屏时原书页降到右栏第一节。 */
  const wide = vp.id !== '430x880';
  const compare = wide && (S.toggles['fig2-compare'] != null ? S.toggles['fig2-compare'] : true);

  /* 原书页图不进右栏 —— 它必须和棋盘「并排」才能核对。做成 stage 内的对照层：
     默认开，占 stage 左侧 34%，可一键收起把整块还给棋盘。 */
  const sourcePane = `<div style="position:absolute;left:0;top:0;bottom:0;width:34%;min-width:180px;
      background:var(--paper);border-right:1px solid var(--line2);display:flex;flex-direction:column;overflow:hidden;z-index:5">
    <div class="rowbetween" style="padding:8px 10px;border-bottom:1px solid var(--line);flex:none">
      <span class="sec-label" style="margin:0">原书页</span>
      ${ibtn({ icon: 'ChevronLeft', label: '收起原书页', size: 'sm', act: '收起对照层，棋盘吃满整个 stage', src: 'TutorialFigurePage.tsx' })}
    </div>
    <div style="flex:1;min-height:0;overflow-y:auto;padding:10px">
      <div style="width:100%;aspect-ratio:3/4;border-radius:4px;border:1px solid var(--line2);background:linear-gradient(170deg,#f2ede2,#ded6c6);padding:12px;color:#3a352c;font-size:.64rem;line-height:1.7;overflow:hidden">
        <div style="font-weight:700;margin-bottom:6px">二、角上的空</div>
        <div style="opacity:.75">在角上围空效率最高。图一中黑1占据角地，白2挂角后黑3小飞守角，是最常见的下法之一。角上只需要较少的子数就能围出实空……</div>
        <div style="margin-top:10px;height:84px;border:1px solid #b9ac93;border-radius:3px;background:#dcb468;opacity:.8"></div>
      </div>
      <p class="muted" style="margin:10px 0 0;font-size:.74rem;line-height:1.7">黑1占角，白2挂，黑3小飞守角。</p>
    </div></div>`;

  const boardStage = nodata
    ? `<div style="display:grid;place-items:center;width:100%;height:100%;padding:24px">
        <div style="padding:28px;text-align:center;border:1px dashed var(--line2);border-radius:8px">
          <p class="muted" style="margin:0 0 12px">暂无棋盘数据</p>
          ${btn({ label: '初始化空棋盘', variant: 'outlined', size: 'sm', act: 'handleServerSave(空 payload) → PUT figures/{id}', src: 'TutorialFigurePage.tsx:405' })}</div></div>`
    : `<div style="display:grid;place-items:center;width:100%;height:100%">
        <canvas class="boardcv" data-floor="0" data-board='${esc(JSON.stringify({ stones: FIG_STONES, coords: false, numbers: true }))}'></canvas></div>`;

  return {
    stage: `<div style="position:relative;width:100%;height:100%;overflow:hidden">
      ${compare ? sourcePane : `<button class="iconbtn" aria-label="展开原书页" data-toggle="fig2-compare"
          data-act="展开原书页对照层" data-src="TutorialFigurePage.tsx"
          style="position:absolute;left:8px;top:8px;z-index:6;background:var(--paper);border:1px solid var(--line2)">${icon('ChevronRight')}</button>`}
      <div style="position:absolute;inset:0;${compare ? 'left:34%;' : ''}display:grid;place-items:center">
        ${boardStage}
      </div>
      ${compare ? `<button class="iconbtn" aria-label="收起原书页" data-toggle="fig2-compare" data-act="收起对照层" data-src="TutorialFigurePage.tsx" style="display:none"></button>` : ''}
    </div>`,
    plate: plate2({
      title: '二. 角上的空', sub: '图一 · 1 / 42',
      status: `<span class="chip ${editing ? 'warn' : ''}">${editing ? '编辑中' : '只读'}</span>`,
      backTo: 'navigate(-1)', src: 'TutorialFigurePage.tsx:267',
    }),
    railBody: `
      ${sec2('', `<div class="rowbetween">
          ${ibtn({ icon: 'NavigateBefore', label: '上一图', disabled: true, act: 'setCurrentFigureIndex(i-1)', src: 'TutorialFigurePage.tsx:275' })}
          <span class="mono" style="font-size:.82rem">图一 (1 / 42)</span>
          ${ibtn({ icon: 'NavigateNext', label: '下一图', act: 'setCurrentFigureIndex(i+1)', src: 'TutorialFigurePage.tsx:281' })}
        </div>
        ${wide ? `<div style="margin-top:10px">${tgrid(tbtn({ id: 'fig2-compare', label: '对照原书页', icon: 'MenuBook', on: true, act: '开/关 stage 左侧的原书页对照层', src: 'TutorialFigurePage.tsx' }), 1)}</div>` : ''}`, 'padding-top:12px')}
      ${wide ? '' : sec2('原书页', `<div style="width:100%;aspect-ratio:3/4;border-radius:4px;border:1px solid var(--line2);background:linear-gradient(170deg,#f2ede2,#ded6c6);padding:12px;color:#3a352c;font-size:.68rem;line-height:1.7;overflow:hidden">
          <div style="font-weight:700;margin-bottom:6px">二、角上的空</div>
          <div style="opacity:.75">在角上围空效率最高。图一中黑1占据角地，白2挂角后黑3小飞守角，是最常见的下法之一。</div>
          <div style="margin-top:10px;height:90px;border:1px solid #b9ac93;border-radius:3px;background:#dcb468;opacity:.8"></div>
        </div>`)}
      ${nodata ? '' : editing
      ? sec2('编辑棋盘', `
${tgrid(`
            ${figToolBtn('摆黑', STONE.b, true, "onToolChange('stone') + onStoneModeChange('black')")}
            ${figToolBtn('摆白', STONE.w, false, "onStoneModeChange('white')")}
            ${figToolBtn('交替', STONE.alt, false, "onStoneModeChange('alternate')")}
            ${figToolBtn('编号', glyph('123'), true, 'onNumberingChange(!numbering)')}
            ${figToolBtn('大写', glyph('A'), false, "onToolChange('letter_upper')")}
            ${figToolBtn('小写', glyph('a'), false, "onToolChange('letter_lower')")}
            ${figToolBtn('橡皮', glyph('✕'), false, "onToolChange('eraser')")}
            ${gbtn({ label: '图形', icon: glyph('△'), dialog: 'shape', act: '打开图形菜单', src: 'BoardEditToolbar.tsx:225' })}
            ${gbtn({ label: '撤销', icon: 'Undo', act: 'editor.undo()', src: 'BoardEditToolbar.tsx' })}
            ${gbtn({ label: '一键清空', icon: 'DeleteSweep', act: 'editor.clearAll()（保留 viewport）', src: 'BoardEditToolbar.tsx' })}`)}
          <div class="inline" style="gap:8px;margin-top:10px">
            <div style="flex:1"><label class="flabel">下一手编号</label>
              <input class="field" type="number" min="1" value="13" aria-label="下一手编号" data-act="onNextMoveNumberChange" data-src="BoardEditToolbar.tsx"></div>
            <div style="flex:1"><label class="flabel">下一个字母</label>
              <input class="field" value="A" aria-label="下一个字母" data-act="onNextLetterChange" data-src="BoardEditToolbar.tsx"></div>
          </div>
`)
      : sec2('手数', `<label class="flabel">当前 <span class="mono">12</span> / 12</label>
          <input class="slider" type="range" min="0" max="12" value="12" aria-label="手数" data-act="setMoveStep(v) → SGFBoard maxMoveStep" data-src="TutorialFigurePage.tsx:354">`)}
      ${sec2('语音讲解', `${narration
        ? `<div class="stack g8">
              <textarea class="field" rows="6" aria-label="讲解文本" data-act="setEditedNarration" data-src="TutorialFigurePage.tsx:428">黑1占角，白2挂角，黑3小飞守角。角上围空的效率最高，这是入门阶段最应当先记住的一个形。</textarea>
              <div class="inline" style="gap:6px">
                ${btn({ label: '保存文字', variant: 'outlined', size: 'sm', act: 'PUT figures/{id} narration', src: 'TutorialFigurePage.tsx:438' })}
                ${btn({ label: '生成语音并保存', variant: 'contained', size: 'sm', icon: 'RecordVoiceOver', act: 'POST tutorials/tts → 写 audio_asset', src: 'TutorialFigurePage.tsx:445' })}
                ${btn({ label: '取消', color: 'inherit', size: 'sm', act: '还原 narration，收起编辑器', src: 'TutorialFigurePage.tsx:454' })}
              </div></div>`
        : `<p class="muted" style="margin:0 0 10px;font-size:.82rem;line-height:1.75">黑1占角，白2挂角，黑3小飞守角。角上围空的效率最高，这是入门阶段最应当先记住的一个形。</p>
              ${btn({ label: '编辑讲解', variant: 'outlined', size: 'sm', icon: 'Edit', act: 'setIsEditingNarration(v => !v)', src: 'TutorialFigurePage.tsx:414' })}`}
        ${narration ? btn({ label: '收起编辑', variant: 'outlined', size: 'sm', icon: 'Edit', act: 'setIsEditingNarration(false)', src: 'TutorialFigurePage.tsx:414' }) : ''}
        <div class="card" style="padding:8px 10px;border-radius:10px;margin-top:12px">
          <div class="inline" style="gap:8px">
            ${ibtn({ icon: 'PlayArrow', label: '播放语音', size: 'sm', act: 'audio.play() / audio.pause()', src: 'AudioPlayer.tsx' })}
            <div style="flex:1;height:4px;border-radius:2px;background:rgba(255,255,255,.12);position:relative">
              <div style="width:34%;height:100%;background:var(--jade-l);border-radius:2px"></div></div>
            <span class="mono dim" style="font-size:.7rem">0:12/0:35</span>
          </div></div>
        <div style="margin-top:12px">
          <div style="aspect-ratio:16/9;border-radius:8px;background:linear-gradient(150deg,#1c1c1c,#0c0c0c);border:1px solid var(--line2);display:grid;place-items:center">
            <button class="iconbtn" aria-label="播放讲解视频" data-act="&lt;video controls preload=none&gt; 原生播放" data-src="TutorialFigurePage.tsx:487" style="width:46px;height:46px;background:rgba(74,107,92,.85);color:#eef4f0">${icon('PlayArrow')}</button>
          </div>
          <div class="mono dim" style="font-size:.7rem;margin-top:4px">1:24</div>
        </div>`)}
      ${debug ? sec2('', `<div class="rowbetween" style="margin-bottom:8px"><span class="sec-label" style="margin:0">识别流程</span>
          ${ibtn({ icon: 'ExpandLess', label: '收起调试面板', size: 'sm', act: '折叠 RecognitionDebugPanel', src: 'RecognitionDebugPanel.tsx' })}</div>
        ${['S0 画框检测 · 识别页面中每张棋谱图的位置', 'S1 纠偏与网格扫描 · 纠偏 + 检测到的网格线', 'S2 落子检测 · 检测到的落子点标注', 'S3 棋盘定位 · 确定棋谱在 19×19 棋盘中的区域', 'S4 编号绑定 · 数字与棋子配对'].map((s, i) => `
          <button class="rowbetween" data-act="展开第 ${i + 1} 步中间图" data-src="RecognitionDebugPanel.tsx"
            style="width:100%;background:none;border:0;border-top:${i ? '1px solid var(--line)' : '0'};color:inherit;font:inherit;padding:7px 0;cursor:pointer;text-align:left">
            <span style="font-size:.72rem;line-height:1.4;padding-right:8px">${s}</span>${icon('ExpandMore', 'sm')}</button>`).join('')}`) : ''}`,
    actions: nodata ? act2(btn({ label: '初始化空棋盘', variant: 'contained', size: 'lg', full: true, act: 'handleServerSave(空 payload)', src: 'TutorialFigurePage.tsx:405' }))
      : editing
        ? `<div class="pad inline" style="gap:8px">
             ${btn({ label: '取消', variant: 'outlined', color: 'inherit', act: 'editor.cancelEdit() → 回滚 payload', src: 'BoardEditToolbar.tsx' })}
             ${btn({ label: '保存', variant: 'contained', full: true, act: 'PUT /api/v1/tutorials/figures/{id}', src: 'BoardEditToolbar.tsx' })}
           </div>`
        : `<div class="pad" style="display:grid;grid-template-columns:1fr 1fr;gap:6px">
             ${btn({ label: '编辑', variant: 'outlined', icon: 'Edit', act: 'editor.enterEdit()', src: 'TutorialFigurePage.tsx:367' })}
             ${btn({ label: '逻辑检查', variant: 'outlined', icon: 'Rule', act: '纯前端校验（现状走浏览器原生 alert()）', src: 'TutorialFigurePage.tsx:370' })}
             ${btn({ label: '确认审核', variant: 'contained', icon: 'CheckCircleOutline', act: 'PUT /api/v1/tutorials/figures/{id}/verify', src: 'TutorialFigurePage.tsx:374', full: true })}
           </div>`,
    noBoardTarget: false,
  };
};

/* ═══════════════════════════════════════════════════════════════
   改版模式下每屏的说明
   ═══════════════════════════════════════════════════════════════ */
const NOTES2 = {
  'research': `<h3>三套布局并成一套</h3>
    <p>L1 / L2 / L3 现在共用同一个壳：棋盘永远在中间，右栏换内容。
    L3 那条压在棋盘正上方的「研究模式 · 胜率 · 返回编辑」没有了 ——
    胜率进右栏「局面」，<b>返回编辑</b>进右栏动作区（它是模式退出，不是路由返回，
    所以不能做成模块牌的返回键）。</p>
    <p>L2 原本是一整页全屏进度、棋盘消失。现在盘面留在左边不动，进度条进右栏 ——
    分析的是哪一盘，看得见。</p>
    <p><code>height:100vh</code> 三处一起没了，框右下角那个橙色溢出标记不再出现。</p>`,

  'tsumego-problem': `<h3>桌面和移动两套 JSX 合成一套</h3>
    <p>现状里 <code>TsumegoProblemPage</code> 用 <code>useMediaQuery</code> 写了两棵完整的树
    （<code>:305</code> 桌面 / <code>:360</code> 移动），移动那套还自带
    <code>MobileHeader</code> 和 <code>MobileToolbar</code>，会和 galaxy 的底栏撞车。
    改版只有一套：把视口切到 430×880，右栏整幅落到棋盘下面，六个工具键就是动作区那一行。</p>
    <p>面包屑从棋盘上方挪进右栏中段第一节；<code>TsumegoBoard.tsx:90</code> 那个
    <code>window.innerHeight - 100</code> 的魔法钳位换成容器测量，所以 1024×768 下棋盘从约 660 回到 684。</p>`,

  'report-detail': `<h3>本轮最省事的一页</h3>
    <p>它本来就是「棋盘左 / 信息右」，右栏顺序也和模板一致。改的只有三处：
    棋盘上方那行标题条进模块牌、右栏 500 → 320、外层换 <code>BoardPageShell</code>。
    棋盘因此从 664 长到 828。</p>
    <p>顺手补了一个既有 bug：「进入研究室」原来不带棋局参数（<code>:118</code>），点了会丢掉当前这局。
    这一处涉及导航参数、不涉及后端契约，属于可以顺手带的范围 —— 但仍然请你点头。</p>`,

  'kifu': `<h3>左右对调</h3>
    <p>现状是<b>左 520 列表 / 右 棋盘</b>，模板是<b>左 棋盘 / 右 320 信息栏</b>。
    搜索框、棋谱卡片、分页整块搬到右栏；棋盘从 683 长到 828，并且拿到了
    <code>minimumCanvasSize={0}</code> —— 现状那个 400px 硬下限在窄视口下会把棋盘顶出容器。</p>
    <p>棋谱卡片在 320 宽下要压：赛事名和日期合成一行、结果字号降一档。
    切到 1024×768 看还读不读得动，这是本页唯一有信息损失风险的地方。</p>`,

  'game-room': `<h3>你举的第一个例子</h3>
    <p>棋盘上方那条「轮到你了 / 3 观众 / 离开对局」整条没了：
    <b>轮到你了</b>变成模块牌右侧那枚会呼吸的徽章，<b>3 观众</b>降到右栏对局信息那行。
    右栏 495 → 320，棋盘 704 → 828。</p>
    <h3>这一轮按你的三条意见改的</h3>
    <ul>
      <li><b>轮次高亮。</b>轮到谁下，谁的卡描边变玉色、时钟变玉色、名字前多一个呼吸点、卡底压一条「该你了」；
        另一张压到 62% 不透明度。<b>四条线索是冗余的，不只靠颜色</b> —— 色盲和强光下的 7 寸屏上，
        只改一个色相等于没改。</li>
      <li><b>右下角那排删了。</b>「认输 / 数子」本来就在上面的工具格里 —— 而且原来格子里那两个是<b>假的</b>，
        点了没反应，真正开弹窗的是下面那排。现在反过来：格子里的认输和数子<b>真的接上弹窗</b>，
        下面那排整个删掉。<b>数子请求</b>不是我方按钮，是对方发起时弹出来的，也删了。
        只剩「离开对局」，按你说的<b>和上方的按钮放在一起</b> —— 就在工具格正下方。
        动作区现在只有翻手那六个键。</li>
      <li><b>原型专用的假按钮清空了。</b>「认输弹窗」「终局弹窗」这类只有原型才需要的触发器，
        全部挪到控制台的<b>弹窗</b>那一栏。框里现在只剩真实产品控件。</li>
    </ul>`,

  'game-rated': `<h3>照抄对象之一，也按同一条契约走了一遍</h3>
    <p>scope 说 <code>GamePage.tsx</code> 已迁移、别改，但它是「已在模板上」的两页之一，
    版式统一如果不把它一起对齐，右栏就还是 340、工具格还是四列横排、右下角还是那排重复按钮。
    这一屏是它按同一条契约长出来的样子：右栏 320、轮次高亮、离开跟工具格放在一起、动作区只留翻手。</p>
    <p>模块牌也从 <code>backLabel</code>（右侧「← 升降级」）换成了和直播样板一致的图标左置。
    这就是总览页第 1 条要你裁定的那件事 —— 两个照抄对象形式不一样，得选一个。</p>
    <p>结算态（切「已结算」分支）保留原来的晋级面板，只是它现在在右栏中段最上面，
    不再是一块浮在棋盘上的卡。</p>`,

  'live-list': `<h3>你举的第二个例子</h3>
    <p>直播列表页现在和直播对局页是同一个壳：棋盘居中 828，右栏 320
    装 精选/预告 两个页签 + 对局列表 + 底部「进入直播」。
    标题「直播」从棋盘正上方挪进模块牌，当前对局名做副标题。</p>
    <p>还修掉一处：现状右栏是 <code>display:{xs:'none',md:'flex'}</code>，
    430 竖屏下整条列表直接消失、只剩一块棋盘。改版里它落到棋盘下方，一直在。</p>`,

  'reports': `<h3>顺着同一条规则一起改了</h3>
    <p>复盘列表是全站棋盘最小的一页（467，比模板小 361）。改版后棋盘 828，
    列表、导入、搜索、分页全在 320 右栏里。</p>
    <p>页头那句长副标题「选择右侧棋局预览棋盘…」按 spec §2.4 下沉到列表栏顶部，
    措辞也跟着改成「选一局在左边预览棋盘」—— 列表本来就在右边，说「右侧」是从棋盘视角写的。</p>`,

  'game-free': `<h3>范围外，但顺手做了一版给你看</h3>
    <p>scope 把 <code>GamePage.tsx</code> 列进「已迁移、别改」，可它只有 <code>rated</code> 分支在模板上，
    <code>free</code> 分支还是老样子。这一屏是它按同一条契约走会长成什么样：
    右栏 320、轮次高亮、离开跟工具格放在一起、动作区只留翻手六键、胜率走势进中段。</p>
    <p>和 rated 的差别只有两处：工具全开（不锁 AI 分析），多一块胜率走势。改动量很小。
    要不要在本轮把这半边也收掉，仍然是你的裁定。</p>`,

  'tutorial-figure': `<h3>唯一没有硬套的一页</h3>
    <p>它是内部制作工具，审图的人必须让<b>原书页图</b>和<b>识别出的棋盘</b>并排，
    塞进右栏上下滚会真的弄坏这个工作流。所以这里的做法是：
    <b>右栏仍然是统一的 320</b>（工具 / 讲解 / 音视频 / 识别调试都在里面），
    但原书页图不进右栏 —— 它做成 stage 里的<b>对照层</b>，占 stage 左侧 34%，
    点右栏「对照原书页」可以一键收起，收起后棋盘吃满整个 stage。</p>
    <p>这样外框的三个数（52 / 216 / 320）和别的页面完全一致，
    可对照的需求也没被牺牲。<b>这是我在本轮里最没把握的一处，请你重点看。</b></p>
    <p>另：<code>calc(100vh - 140px)</code> 那四处魔法数一起没了，三列各滚各的也没了 ——
    现在只有右栏中段一条滚动条。</p>`,
};

/* 改版契约本身，作为总览页顶部那张卡 */
const CONTRACT2 = [
  ['顶栏', '52', '固定', 'GalaxyTopBar，全站唯一'],
  ['左栏', '216', '固定', '停靠态；<900 收起为 0 + 圆形展开钮；<600 换 64 底栏'],
  ['右栏', '320', '固定', '取消现行 320 / 340 / 380 三档，全站一个数'],
  ['棋盘', '中间区全部剩余', '方形居中', 'stage padding 6，地板 0，1200 上限保留'],
  ['棋盘上方', '空', '—', 'spec §2.2：状态、标题、操作一律进右栏'],
  ['右栏结构', '三段', '只有中段滚', '模块牌（≥52）/ 中段 / 动作区'],
];

/* ═══════════════════════════════════════════════════════════════
   死活题 · 难度列表 —— 重新设计
   现状是 8 个 380×270 的等价方块，每块里一个 3rem 的大数字在撑场面，
   下半屏全空。丢掉的恰恰是这一页唯一真正的结构：15K→7D 是一条
   有序的阶梯，级位往下数、段位往上数，1K→1D 是围棋里唯一那道坎。
   所以改成「行」不是「格」，坎画成真的分隔线，自己的水平标在阶梯上。
   ═══════════════════════════════════════════════════════════════ */
const CATCOLOR = { 死活: '#5d8270', 手筋: '#5b9bd5', 官子: '#8a7f6d' };
const LADDER = [
  ['15K', '入门', '刚学会规则，先认识「气」和「眼」', 240, [160, 60, 20], 240],
  ['10K', '初级', '会做基本活棋，开始算简单的死活', 312, [200, 92, 20], 268],
  ['5K', '中级', '常见死活形已成套，手筋题占比上来', 288, [180, 88, 20], 96],
  ['1K', '高级', '冲段前的量，复杂形和收官一起练', 196, [120, 56, 20], 0],
  ['1D', '业余初段', '长手数死活，官子开始计算目数', 164, [100, 48, 16], 0],
  ['3D', '业余中段', '连环劫、双活等复杂判断', 132, [80, 40, 12], 0],
  ['5D', '业余高段', '实战难形，容错很小', 96, [60, 26, 10], 0],
  ['7D', '业余顶尖', '古今名局里的极难题', 64, [40, 18, 6], 0],
];
const MY_RANK = '5K';
const MAXTOTAL = Math.max(...LADDER.map(r => r[3]));

V2['tsumego-levels'] = function (b, vp) {
  const withProgress = b === 'ok';
  if (b === 'loading') {
    return { html: `<div data-zone="body">${cph({ title: '死活题' })}
      <div class="ladder" style="margin-top:22px;max-width:960px">${'<div class="skel" style="height:58px;border-radius:10px"></div>'.repeat(8)}</div></div>` };
  }
  if (b === 'error') {
    return { html: `<div data-zone="body">${cph({ title: '死活题' })}
      <div style="max-width:960px;margin-top:22px"><div class="alert error" style="margin-bottom:14px">死活题库加载失败，请稍后重试。</div>
      ${btn({ label: '重试', variant: 'outlined', act: '重新 GET /api/v1/tsumego/levels', src: 'TsumegoLevelsPage.tsx:23' })}</div></div>` };
  }
  if (b === 'empty') {
    return { html: `<div data-zone="body">${cph({ title: '死活题' })}
      <div style="max-width:960px;margin-top:22px"><div class="alert info">暂无死活题。</div></div></div>` };
  }

  const mobile = vp.id === '430x880';
  const rung = (r) => {
    const [lv, name, sub, total, cats, solved] = r;
    const dan = lv.endsWith('D');
    const me = lv === MY_RANK;
    const pct = total ? Math.round(solved / total * 100) : 0;
    const label = `${lv}${dan ? ' 段' : ' 级'}，${name}，共 ${total} 题`
      + (withProgress ? `，已解 ${solved} 题，完成 ${pct}%` : '');
    return `<button class="lrung ${dan ? 'dan' : ''} ${me ? 'me' : ''}" aria-label="${esc(label)}"
      data-act="导航 /galaxy/tsumego/${lv.toLowerCase()}" data-src="TsumegoLevelsPage.tsx:87"
      ${mobile ? 'style="grid-template-columns:52px 1fr 20px;gap:12px"' : ''}>
      <span class="rung-badge">${lv}</span>
      <span style="min-width:0">
        <span class="rung-name">${name}${me ? ` <em style="font-style:normal;font-size:.68rem;color:var(--jade-l);letter-spacing:.06em;margin-left:6px">你的水平</em>` : ''}</span>
        <span class="rung-sub" style="display:block;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${mobile ? `${total} 题${withProgress ? ` · 已解 ${solved}` : ''}` : sub}</span>
      </span>
      ${mobile ? '' : `
      <span class="rung-barwrap">
        <span class="rung-bar" style="width:${(38 + total / MAXTOTAL * 62).toFixed(1)}%"
          role="img" aria-label="死活 ${cats[0]} 题、手筋 ${cats[1]} 题、官子 ${cats[2]} 题">
          ${['死活', '手筋', '官子'].map((c, i) => `<i style="width:${(cats[i] / total * 100).toFixed(1)}%;background:${CATCOLOR[c]}"></i>`).join('')}
        </span>
      </span>
      <span class="rung-total">${total} 题</span>
      ${withProgress
        ? `<span class="rung-prog"><span class="track"><span class="fill" style="width:${pct}%"></span></span>
             <span class="num${solved ? '' : ' zero'}">${solved ? `<b>${solved}</b>` : '0'} / ${total}${pct === 100 ? ' · 全解' : ''}</span></span>`
        : `<span class="rung-prog"><span class="num zero" style="text-align:center">—</span></span>`}`}
      <span class="chev">${icon('ChevronRight', 'sm')}</span>
    </button>`;
  };

  return {
    html: `<div data-zone="body" style="max-width:960px;margin:0 auto">
      ${cph({ title: '死活题' })}

      ${withProgress ? `<div class="resume" style="margin-top:18px">
        <div style="flex:1;min-width:200px">
          <p class="sec-label" style="margin:0 0 4px">继续练习</p>
          <div style="font-size:.95rem;font-weight:600">5K · 手筋 · 第 3 单元 · 第 7 题</div>
          <div class="dim" style="font-size:.74rem;margin-top:2px">上次练习 2 天前 · 本单元已解 6 / 20</div>
        </div>
        ${btn({ label: '继续', variant: 'contained', icon: 'PlayArrow', act: '导航到 progress 里 lastAttemptAt 最新的那一题', src: 'TsumegoProgressContext.tsx' })}
        ${btn({ label: '从我的水平开始', variant: 'outlined', color: 'inherit', act: '导航 /galaxy/tsumego/5k', src: 'TsumegoLevelsPage.tsx' })}
      </div>` : `<p class="muted" style="margin:14px 0 0;font-size:.875rem">选择难度级别开始练习。</p>`}

      <div class="rowbetween" style="margin:${withProgress ? 22 : 18}px 0 12px;flex-wrap:wrap;gap:10px">
        <span class="sec-label" style="margin:0">全部难度 · 8 档</span>
        ${mobile ? '' : `<span class="legend">
          ${['死活', '手筋', '官子'].map(c => `<span><i style="background:${CATCOLOR[c]}"></i>${c}</span>`).join('')}
          ${withProgress ? `<span><i style="background:var(--jade-l);border-radius:50%"></i>已解</span>` : ''}
        </span>`}
      </div>

      <div class="ladder">
        <div class="tier-seam">级位 <em>越往下越强</em></div>
        ${LADDER.slice(0, 4).map(rung).join('')}
        <div class="tier-seam">段位 <em>越往下越强</em></div>
        ${LADDER.slice(4).map(rung).join('')}
      </div>
    </div>`,
  };
};
(SCREENS.find(s => s.id === 'tsumego-levels') || {}).branches2 = [
  { id: 'ok', label: '主界面（带进度）' },
  { id: 'noprog', label: '不接进度' },
  { id: 'loading', label: '加载中' },
  { id: 'error', label: '加载失败' },
  { id: 'empty', label: '空态' },
];

NOTES2['tsumego-levels'] = `<h3>从「八个方块」改成「一条阶梯」</h3>
  <p>现状那 8 张卡之所以显得空，不是因为留白多，是因为<b>每张卡只有一个数字在承担全部信息</b> ——
  把 <code>15K</code> 放到 3rem，剩下的位置就只能靠空白填。而这一页真正的结构被丢掉了：
  15K→7D 是<b>有序的</b>，级位往下数、段位往上数，<code>1K→1D</code> 是围棋里唯一那道坎。
  8 个等价方块把顺序和那道坎一起抹掉了。</p>
  <p>改法：用<b>行</b>不用<b>格</b>。一行一档，段位那一段单独起一节并换一档略暖的底色，
  自己的水平（5K）左侧压一条玉色边、徽章点亮、旁边写「你的水平」。
  级别数字降到 1.05rem 放进 34px 的徽章里 —— 它是<b>标识</b>不是<b>标题</b>。
  空出来的横向位置交给真信息：一句说明、三段分布条、题数、进度。八行加上那道坎，
  正好一屏装下，不用滚。</p>
  <h3>三处细节</h3>
  <ul>
    <li><b>24 枚 chip 收成 8 条分布条。</b>「死活: 160 手筋: 60 官子: 20」× 8 = 24 个小方块，
      读起来是噪声。一行一条三段条，比例一眼可比，图例只在顶部出现一次。
      第三段用的是 <code>#8a7f6d</code> —— 棋盘木色，不另起一套配色。</li>
    <li><b>颜色不是唯一线索。</b>轮次、进度、分布条都同时带文字或数字；
      分布条挂了 <code>role="img"</code> 和完整 aria-label，读屏能听到「死活 160 题、手筋 60 题、官子 20 题」。</li>
    <li><b>「继续练习」放在最上面。</b>回到这一页的人多半不是来重新挑难度的，
      是来接着上次练的。这条带子是主行动，难度阶梯是次行动。</li>
  </ul>
  <h3>⚠ 这一处需要你点头：进度数据要多一次请求</h3>
  <p>进度本身<b>已经存在</b> —— <code>TsumegoProgressContext</code> 里是一张
  <code>problem_id → {completed, attempts, lastAttemptAt}</code> 的表，单元页就是这么算
  <code>x/y</code> 的（<code>TsumegoUnitsPage.tsx:128</code>）。但 <code>/api/v1/tsumego/levels</code>
  只回 <code>{level, categories, total}</code>，<b>不带题目 id</b>，所以难度页要显示「已解 96/288」，
  必须能按难度拿到 id 列表 —— 要么加一个聚合端点，要么按难度查一次题目列表。
  这是本轮唯一会碰到后端契约的地方。</p>
  <p>所以这一屏给了两个分支：<b>主界面（带进度）</b>和<b>不接进度</b>。
  后者不需要任何后端改动，阶梯结构照样成立，只是右边那一列变成「—」。
  切过去对比一下，值不值得为那一列加个端点，你定。</p>`;
