/* ───────────────── 对局中（AI）· 已迁移 / 未迁移 各一半 ───────────────── */
const gameRail = (rated, ended) => {
  const tool = (id, label, ic, dis) => tbtn({ id: 'g-' + id, label, icon: ic, disabled: dis, src: 'RightSidebarPanel.tsx' });
  return `<div class="pad" data-zone="right-rail-middle">
      <div class="rowbetween" style="gap:10px;margin-bottom:14px">
        <div class="card" style="flex:1;padding:10px;border-radius:10px">
          <div class="inline" style="gap:6px;margin-bottom:4px"><i class="kstone b"></i><span style="font-weight:600;font-size:.85rem">fan</span>
            ${ibtn({ icon: 'PersonAdd', label: '关注 fan', size: 'sm', act: 'API.followUser(name)', src: 'PlayerCard.tsx' })}</div>
          <div class="mono" style="font-size:1.25rem;font-weight:600">09:12</div>
          <div class="dim" style="font-size:.68rem">3K · 提子 2</div>
        </div>
        <div class="card" style="flex:1;padding:10px;border-radius:10px">
          <div class="inline" style="gap:6px;margin-bottom:4px"><i class="kstone w"></i><span style="font-weight:600;font-size:.85rem">智星棋手</span>
            ${ibtn({ icon: 'PersonAdd', label: '关注 智星棋手', size: 'sm', act: 'API.followUser(name)', src: 'PlayerCard.tsx' })}</div>
          <div class="mono" style="font-size:1.25rem;font-weight:600">07:48</div>
          <div class="dim" style="font-size:.68rem">3K · 提子 4</div>
        </div>
      </div>
      <div class="toolgrid" style="display:grid;grid-template-columns:repeat(4,1fr);gap:6px">
        ${tool('terr', '领地', 'Map', rated)}${tool('hint', '建议', 'TipsAndUpdates', rated)}
        ${tool('chart', '图表', 'Timeline', rated)}${tool('undo', '悔棋', 'Undo', rated)}
        ${tool('pass', '停一手', 'PanToolAlt')}${tool('resign', '认输', 'Flag')}
        ${tool('count', '数子', 'Calculate')}${tool('3d', '3D', 'ViewInAr')}
      </div>
      ${rated ? `<p class="dim" style="font-size:.72rem;margin:10px 0 0">升降级对局中不开放 AI 分析、改规则、改贴目、改让子或改强度。</p>` : ''}
      <hr class="hr" style="margin:14px 0">
      ${swrow({ id: 'g-coords', label: '坐标', on: true, src: 'RightSidebarPanel.tsx' })}
      ${swrow({ id: 'g-numbers', label: '手数', src: 'RightSidebarPanel.tsx' })}
      ${swrow({ id: 'g-drop', label: '落子特效', src: 'RightSidebarPanel.tsx' })}
    </div>`;
};

SCREENS.push({
  id: 'game-rated', group: '对局', label: '升降级对局中（已在模板上）', route: '/galaxy/play/game/:sessionId?mode=rated',
  nav: 'play', kind: 'board',
  branches: [{ id: 'playing', label: '对局中' }, { id: '3d', label: '3D 视图' }, { id: 'settled', label: '已结算' }, { id: 'stalled', label: '引擎不可用' }, { id: 'pending', label: '结算未送达' }],
  dialogs: {
    leave: `<div class="dlg" data-zone="dialog"><h3>离开对局？</h3><p>对局仍在进行中。离开将认输本局。确定吗？</p>
      <div class="acts">${btn({ label: '取消', color: 'inherit', act: 'setShowLeaveConfirm(false)', src: 'GamePage.tsx:459' })}
      ${btn({ label: '认输并退出', variant: 'contained', color: 'err', act: "handleAction('resign') 后离开", src: 'GamePage.tsx:468' })}</div></div>`,
    resign: `<div class="dlg" data-zone="dialog"><h3>认输？</h3><p>确定要认输吗？</p>
      <div class="acts">${btn({ label: '取消', color: 'inherit', act: 'setShowResignConfirm(false)', src: 'GamePage.tsx:474' })}
      ${btn({ label: '认输', variant: 'contained', color: 'err', act: 'checkRankedStillActive → API.resign', src: 'GamePage.tsx:482' })}</div></div>`,
    count: `<div class="dlg" data-zone="dialog"><h3>通过数子结束对局？</h3><p>计算最终得分以结束对局。</p>
      <div class="acts">${btn({ label: '取消', color: 'inherit', act: 'setShowCountConfirm(false)', src: 'GamePage.tsx:489' })}
      ${btn({ label: '数子', variant: 'contained', act: 'API.requestCount(sessionId)', src: 'GamePage.tsx:497' })}</div></div>`,
    result: `<div class="dlg" data-zone="dialog"><h3>对局结束</h3><p>数子结束：黑胜 2.5 目</p>
      <div class="acts">${btn({ label: '确定', variant: 'contained', act: 'setCountResult(null)', src: 'GamePage.tsx:512' })}</div></div>`,
  },
  render(b) {
    const settled = b === 'settled';
    const banner = b === 'stalled'
      ? `<div class="alert warning" style="margin:0 auto;max-width:420px">阶梯引擎不可用，AI 无法落子 · 本局不计入升降级，请退出本局</div>`
      : b === 'pending'
        ? `<div class="alert warning" style="margin:0 auto;max-width:420px">暂时无法确认本局状态，请重试
             ${btn({ label: '重试', size: 'sm', color: 'inherit', act: 'setLifecycleRetry(v=>v+1) → 重启 5s 轮询', src: 'GamePage.tsx:449' })}
             ${ibtn({ icon: 'Close', label: '关闭', size: 'sm', act: 'setResignError(null)', src: 'GamePage.tsx:447' })}</div>`
        : '';
    if (b === '3d') {
      return {
        raw: `<div class="shell" data-zone="board-shell">
          <div class="stage-box" data-zone="board">
            <div style="width:100%;height:100%;border-radius:12px;background:radial-gradient(700px 400px at 50% 20%,#3a3226,#171310);display:grid;place-items:center;position:relative;overflow:hidden">
              <canvas class="boardcv" data-floor="200" data-board='${esc(JSON.stringify({ stones: demoStones(28), coords: true }))}' style="transform:perspective(900px) rotateX(46deg) scale(.84);box-shadow:0 40px 70px -20px rgba(0,0,0,.85)"></canvas>
              <div style="position:absolute;right:14px;bottom:14px;display:flex;flex-direction:column;gap:6px;align-items:center;background:rgba(0,0,0,.5);padding:8px;border-radius:10px">
                <button class="iconbtn sm" aria-label="Zoom in" title="Zoom in" data-act="handleZoom('in') — 相机拉近一档（title 未本地化，无 aria-label）" data-src="Board3D/index.tsx:215">+</button>
                <button class="iconbtn sm" aria-label="Zoom out" title="Zoom out" data-act="handleZoom('out') — 相机拉远一档" data-src="Board3D/index.tsx:232">−</button>
                <input class="slider" type="range" min="0" max="100" value="55" aria-label="Tilt angle 俯仰角" title="Tilt angle" data-act="handleTiltChange — OrbitControls 极角 π*0.05…π*0.38" data-src="Board3D/index.tsx:241" style="width:70px">
              </div>
              <div style="position:absolute;left:50%;bottom:12px;transform:translateX(-50%);background:rgba(0,0,0,.5);padding:6px 12px;border-radius:20px">
                <input class="slider" type="range" min="0" max="100" value="50" aria-label="左右" title="Yaw angle" data-act="handleYaw — OrbitControls 方位角" data-src="Board3D/index.tsx:271" style="width:150px">
              </div>
            </div>
          </div>
          <aside class="rail">
            <div class="rail-module">${plate({ title: '升降级对弈', backLabel: '升降级', backTo: '/galaxy/play/ai?mode=rated', src: 'GamePage.tsx:518' })}</div>
            <div class="rail-scroll" data-zone="right-rail-middle">${gameRail(true, false)}</div>
            <div class="rail-actions" data-zone="right-rail-actions">
              <div style="padding:12px;background:var(--surface);display:flex;justify-content:center;gap:2px">
                ${ibtn({ icon: 'SkipPrevious', label: '跳到开局', act: 'API.undo(sessionId, 9999)', src: 'RightSidebarPanel.tsx' })}
                ${ibtn({ icon: 'FastRewind', label: '后退 10 手', act: 'API.undo(sessionId, 10)', src: 'RightSidebarPanel.tsx' })}
                ${ibtn({ icon: 'ArrowBack', label: '后退一手', act: 'API.undo(sessionId, 1)', src: 'RightSidebarPanel.tsx' })}
                ${ibtn({ icon: 'ArrowForward', label: '前进一手', act: 'API.redo(sessionId, 1)', src: 'RightSidebarPanel.tsx' })}
                ${ibtn({ icon: 'FastForward', label: '前进 10 手', act: 'API.redo(sessionId, 10)', src: 'RightSidebarPanel.tsx' })}
                ${ibtn({ icon: 'SkipNext', label: '跳到最后', act: 'API.redo(sessionId, 9999)', src: 'RightSidebarPanel.tsx' })}
              </div>
            </div>
          </aside>
        </div>`,
      };
    }
    return {
      board: { floor: 200, stones: demoStones(settled ? 40 : 28), coords: true, last: [12, 9, 'W'], territory: settled ? [[2, 2, 1], [3, 2, 1], [2, 3, 1], [16, 16, -1], [15, 16, -1], [16, 15, -1]] : null },
      plate: plate({
        title: '升降级对弈', backLabel: '升降级',
        backTo: '/galaxy/play/ai?mode=rated', src: 'GamePage.tsx:518',
      }),
      railBody: `${banner ? `<div class="pad" style="padding-bottom:0">${banner}</div>` : ''}
        ${settled ? `<div class="pad" style="border-bottom:1px solid var(--line)" data-zone="right-rail-top">
          <div class="inline" style="gap:10px;margin-bottom:8px"><span style="color:var(--ok)">${icon('CheckCircle')}</span>
            <span style="font-weight:600">晋级 2K</span></div>
          <p class="muted" style="margin:0 0 14px;font-size:.85rem">本局已计入升降级 · 净胜 +3，升一档，计数归零。</p>
          <div class="inline" style="gap:8px">
            ${btn({ label: '再来一局', variant: 'contained', act: '导航 /galaxy/play/ai?mode=rated', src: 'AiLadderSettlementPanel.tsx' })}
            ${btn({ label: '返回对局', variant: 'outlined', act: '导航 /galaxy/play', src: 'AiLadderSettlementPanel.tsx' })}
            ${btn({ label: '重试', color: 'inherit', act: 'feedback.retry() → 重新轮询结算', src: 'AiLadderSettlementPanel.tsx' })}
          </div></div>` : ''}
        ${gameRail(true, settled)}`,
      actions: `<div style="padding:12px;background:var(--surface);display:flex;justify-content:center;gap:2px">
          ${ibtn({ icon: 'SkipPrevious', label: '跳到开局', act: 'API.undo(sessionId, 9999)', src: 'RightSidebarPanel.tsx' })}
          ${ibtn({ icon: 'FastRewind', label: '后退 10 手', act: 'API.undo(sessionId, 10)', src: 'RightSidebarPanel.tsx' })}
          ${ibtn({ icon: 'ArrowBack', label: '后退一手', act: 'API.undo(sessionId, 1)', src: 'RightSidebarPanel.tsx' })}
          ${ibtn({ icon: 'ArrowForward', label: '前进一手', act: 'API.redo(sessionId, 1)', src: 'RightSidebarPanel.tsx' })}
          ${ibtn({ icon: 'FastForward', label: '前进 10 手', act: 'API.redo(sessionId, 10)', src: 'RightSidebarPanel.tsx' })}
          ${ibtn({ icon: 'SkipNext', label: '跳到最后', act: 'API.redo(sessionId, 9999)', src: 'RightSidebarPanel.tsx' })}
        </div>
        <div style="padding:0 12px 10px;display:flex;justify-content:center;gap:6px;background:var(--surface)">
          ${dlgOpen('resign', '认输', { size: 'sm', color: 'inherit' })}
          ${dlgOpen('count', '数子', { size: 'sm', color: 'inherit' })}
          ${dlgOpen('leave', '离开', { size: 'sm', color: 'inherit' })}
          ${dlgOpen('result', '终局', { size: 'sm', color: 'inherit' })}
        </div>`,
    };
  },
  note: `<h3>模块牌的另一种形式 —— 而且和直播样板不一样</h3>
    <p>这一页用的是 <code>ModulePlate</code> 的 <b>backLabel</b> 形式：左「升降级对弈」，右「← 升降级」
    （<code>GamePage.tsx:517-521</code>），正是 spec §2.4 写的「右侧显示『左箭头 + 上一级页面简称』」。</p>
    <p>可是已批准的 <code>LiveMatchPage</code> 样板用的是<b>另一种</b>：返回图标在最左，标题居中，状态徽章在右。
    两个都被 scope 列为「已迁到模板、别改」的照抄对象，形式却不一致。
    切到「直播 · 对局页」对比一下模块牌那一行 —— 剩下 6 个棋盘页照抄哪一个，需要你定。</p>`,
});

SCREENS.push({
  id: 'game-free', group: '对局', label: '自由对局中（未迁移）', route: '/galaxy/play/game/:sessionId?mode=free',
  nav: 'play', kind: 'content',
  branches: [{ id: 'playing', label: '对局中' }, { id: '3d', label: '3D 视图' }],
  dialogs: {
    result: `<div class="dlg" data-zone="dialog"><h3>对局结束</h3><p>数子结束：黑胜 2.5 目</p>
      <div class="acts">${btn({ label: '确定', variant: 'contained', act: 'setCountResult(null)', src: 'GamePage.tsx:512' })}</div></div>`,
    leave: `<div class="dlg" data-zone="dialog"><h3>离开对局？</h3><p>对局仍在进行中。离开将认输本局。确定吗？</p>
      <div class="acts">${btn({ label: '取消', color: 'inherit', act: 'setShowLeaveConfirm(false)', src: 'GamePage.tsx:459' })}
      ${btn({ label: '认输并退出', variant: 'contained', color: 'err', act: "handleAction('resign') 后离开", src: 'GamePage.tsx:468' })}</div></div>`,
  },
  render(b) {
    const is3d = b === '3d';
    return {
      raw: `<div class="lrow" style="position:relative" data-zone="body">
        <div style="position:absolute;top:12px;left:50%;transform:translateX(-50%);z-index:20;min-width:320px">
          <div class="alert warning" style="align-items:center">
            暂时无法确认本局状态，请重试
            ${btn({ label: '重试', size: 'sm', color: 'inherit', act: 'setLifecycleRetry(v => v + 1) → 重启轮询', src: 'GamePage.tsx:449' })}
            ${ibtn({ icon: 'Close', label: 'Close', size: 'sm', act: 'setResignError(null) —— MUI Alert 内置关闭键', src: 'GamePage.tsx:447' })}
          </div>
        </div>
        <div class="lmain">
          <div class="lhead" data-zone="above-board">
            <span style="font-size:.875rem;font-weight:600;color:var(--jade-l)">自由对弈 (free)</span>
            <div class="inline" style="gap:6px">
              ${dlgOpen('result', '终局弹窗', { size: 'sm', color: 'inherit' })}
              ${dlgOpen('leave', '退出', { variant: 'outlined', color: 'err', size: 'sm', icon: 'ExitToApp', src: 'GamePage.tsx:557' })}
            </div>
          </div>
          <div class="lboard" style="padding:4px">
            ${is3d
              ? `<div style="width:100%;height:100%;border-radius:12px;background:radial-gradient(700px 400px at 50% 20%,#3a3226,#171310);display:grid;place-items:center;position:relative">
                   <canvas class="boardcv" data-floor="200" data-board='${esc(JSON.stringify({ stones: demoStones(28), coords: true }))}' style="transform:perspective(900px) rotateX(46deg) scale(.86);box-shadow:0 40px 70px -20px rgba(0,0,0,.85)"></canvas>
                   <div style="position:absolute;right:14px;bottom:14px;display:flex;flex-direction:column;gap:6px;align-items:center;background:rgba(0,0,0,.5);padding:8px;border-radius:10px">
                <button class="iconbtn sm" aria-label="Zoom in" title="Zoom in" data-act="handleZoom('in') — 相机拉近一档（title 未本地化，无 aria-label）" data-src="Board3D/index.tsx:215">+</button>
                <button class="iconbtn sm" aria-label="Zoom out" title="Zoom out" data-act="handleZoom('out') — 相机拉远一档" data-src="Board3D/index.tsx:232">−</button>
                <input class="slider" type="range" min="0" max="100" value="55" aria-label="Tilt angle 俯仰角" title="Tilt angle" data-act="handleTiltChange — OrbitControls 极角 π*0.05…π*0.38" data-src="Board3D/index.tsx:241" style="width:70px">
              </div>
              <div style="position:absolute;left:50%;bottom:12px;transform:translateX(-50%);background:rgba(0,0,0,.5);padding:6px 12px;border-radius:20px">
                <input class="slider" type="range" min="0" max="100" value="50" aria-label="左右" title="Yaw angle" data-act="handleYaw — OrbitControls 方位角" data-src="Board3D/index.tsx:271" style="width:150px">
              </div>
                 </div>`
              : `<canvas class="boardcv" data-floor="200" data-board='${esc(JSON.stringify({ stones: demoStones(28), coords: true, last: [12, 9, 'W'] }))}'></canvas>`}
          </div>
        </div>
        <div class="lrail w500">
          <div class="lrail-scroll">${gameRail(false, false)}
            <div class="pad" style="border-top:1px solid var(--line)">
              <p class="sec-label">胜率走势</p>
              ${trendChart(452, 140, 'gf')}
            </div>
          </div>
          <div style="padding:12px;background:var(--surface);border-top:1px solid var(--line);display:flex;justify-content:center;gap:2px" data-zone="right-rail-actions">
            ${ibtn({ icon: 'SkipPrevious', label: '跳到开局', act: 'API.undo(sessionId, 9999)', src: 'RightSidebarPanel.tsx' })}
            ${ibtn({ icon: 'FastRewind', label: '后退 10 手', act: 'API.undo(sessionId, 10)', src: 'RightSidebarPanel.tsx' })}
            ${ibtn({ icon: 'ArrowBack', label: '后退一手', act: 'API.undo(sessionId, 1)', src: 'RightSidebarPanel.tsx' })}
            ${ibtn({ icon: 'ArrowForward', label: '前进一手', act: 'API.redo(sessionId, 1)', src: 'RightSidebarPanel.tsx' })}
            ${ibtn({ icon: 'FastForward', label: '前进 10 手', act: 'API.redo(sessionId, 10)', src: 'RightSidebarPanel.tsx' })}
            ${ibtn({ icon: 'SkipNext', label: '跳到最后', act: 'API.redo(sessionId, 9999)', src: 'RightSidebarPanel.tsx' })}
          </div>
        </div>
      </div>`,
    };
  },
  note: `<h3>同一个文件里，一半迁了一半没迁</h3>
    <p><code>GamePage.tsx</code> 的 <code>isRated</code> 分支走 <code>BoardPageShell</code>（上一屏），
    <code>free</code> 分支还是老的「棋盘 + 500px 右栏 + 棋盘上方一条标题/退出条」。
    scope 把 <code>GamePage.tsx</code> 列进「已迁移、别改」，所以本轮它会保持这个一半一半的状态。</p>
    <p>这和 <code>AiSetupPage</code> 是同一个形状的问题：<b>两个照抄对象各自只迁了一半</b>。
    要不要在本轮把这两个文件的另一半也收掉，需要你裁定。</p>`,
});
