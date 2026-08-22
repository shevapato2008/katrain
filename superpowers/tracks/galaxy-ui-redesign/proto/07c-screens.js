/* ───────────────────────────── 人人对弈 ───────────────────────────── */
SCREENS.push({
  id: 'hvh-lobby', group: '对局', label: '人人对弈 · 大厅', route: '/galaxy/play/human',
  nav: 'play', kind: 'content',
  branches: [{ id: 'ok', label: '已加载' }, { id: 'loading', label: '首次加载中' }, { id: 'empty', label: '全空态' }, { id: 'error', label: '在线玩家失败' }],
  dialogs: {
    finding: `<div class="dlg" data-zone="dialog"><h3>正在寻找对手...</h3>
      <div style="padding:8px 22px 20px;text-align:center">
        <div class="spin" style="width:60px;height:60px;border-width:3px;margin:0 auto 14px"></div>
        <div class="mono" style="font-size:1.25rem;font-weight:600">0:42</div>
        <p class="muted" style="margin:6px 0 0;font-size:.85rem;padding:0">正在为您寻找合适的对手。</p>
      </div>
      <div class="acts">${btn({ label: '取消', variant: 'outlined', color: 'err', act: "WS {type:'stop_matchmaking'}", src: 'HvHLobbyPage.tsx:204' })}</div></div>`,
    invite: `<div class="dlg" data-zone="dialog"><h3>对局邀请</h3>
      <p>alice 邀请你进行对局。</p>
      <div class="acts">
        ${btn({ label: '拒绝', color: 'inherit', act: 'setInvitation(null)（不通知对方）', src: 'HvHLobbyPage.tsx' })}
        ${btn({ label: '接受', variant: 'contained', act: "WS {type:'accept_invite'}", src: 'HvHLobbyPage.tsx' })}
      </div></div>`,
  },
  render(b) {
    const players = [['alice', '5k'], ['bob', '无段位'], ['fan', '3d']];
    const games = [['bob', 'cat', 42, 1], ['dan', 'eve', 118, 3]];
    const col = (icon2, title, inner, color) => `<div class="card" style="padding:20px;display:flex;flex-direction:column;min-height:0">
      <div class="inline" style="gap:10px;margin-bottom:14px"><span style="color:${color}">${icon(icon2)}</span>
      <h2 style="font-size:1.15rem;font-weight:600;margin:0">${title}</h2></div>${inner}</div>`;
    return {
      html: `<div data-zone="body">
        <div class="rowbetween" style="align-items:flex-start;flex-wrap:wrap;gap:16px;margin-bottom:28px" data-zone="page-header">
          <div>
            <h1 style="font-size:2.125rem;font-weight:700;margin:0 0 6px">多人游戏大厅</h1>
            <p class="muted" style="margin:0">与其他玩家对弈或观看直播对局。</p>
          </div>
          <div class="inline" style="gap:12px">
            ${dlgOpen('finding', '快速匹配（排位）', { variant: 'contained', size: 'lg', icon: 'SportsEsports', src: 'HvHLobbyPage.tsx:195' })}
            ${dlgOpen('finding', '自定义对局', { variant: 'outlined', size: 'lg', src: 'HvHLobbyPage.tsx:198' })}
          </div>
        </div>
        ${b === 'error' ? `<div class="alert error" style="margin-bottom:16px">加载在线玩家失败 ${btn({ label: '重试', size: 'sm', act: 'GET /api/v1/users/online', src: 'HvHLobbyPage.tsx:59' })}</div>` : ''}
        <div class="gridcards" style="grid-template-columns:1fr 1.4fr .9fr;gap:20px;align-items:start">
          ${col('People', b === 'empty' ? '在线玩家 (0)' : '在线玩家 (3)',
            b === 'loading' ? `<div class="stack g8">${'<div class="skel" style="height:48px"></div>'.repeat(3)}</div>`
            : b === 'empty' ? `<p class="muted" style="margin:0;font-size:.875rem">没有其他在线玩家。</p>`
            : `<div class="stack g8">${players.map(([n, r], i) => `
              <div class="rowbetween" style="padding:12px;border-radius:10px;background:rgba(255,255,255,.02)">
                <div class="inline" style="gap:10px;min-width:0">
                  <span class="avatar" style="background:${i === 2 ? 'var(--jade-d)' : 'var(--jade)'}">${n[0].toUpperCase()}</span>
                  <div style="min-width:0">
                    <div style="font-size:.9rem;font-weight:600">${n}${i === 2 ? ' <span class="dim" style="font-weight:400;font-size:.75rem">(你)</span>' : ''}</div>
                    <span class="chip" style="height:20px">${r}</span>
                  </div>
                </div>
                ${i === 2 ? '' : btn({ label: '邀请', size: 'sm', act: `WS {type:'invite',target_id:${i}}（无本地反馈）`, src: 'HvHLobbyPage.tsx:240' })}
              </div>`).join('')}</div>`, 'var(--jade)')}
          ${col('SportsEsports', '进行中的对局',
            b === 'loading' ? `<div class="stack g8">${'<div class="skel" style="height:72px"></div>'.repeat(2)}</div>`
            : b === 'empty' ? `<p class="muted" style="margin:0;font-size:.875rem">当前没有进行中的对局。<br><span class="dim">匹配功能启用后，对局将显示在这里。</span></p>`
            : `<div class="stack g8">${games.map(([bl, wh, mv, sp]) => `
              <div class="rowbetween card" style="padding:14px 16px;border-radius:10px">
                <div>
                  <div style="font-size:.9rem;font-weight:600">${bl} (B) vs ${wh} (W)</div>
                  <div class="dim mono" style="font-size:.75rem;margin-top:2px">手数: ${mv} | 观众: ${sp}</div>
                </div>
                ${btn({ label: '观战', variant: 'contained', size: 'sm', icon: 'Visibility', act: `导航 /galaxy/play/human/room/{sessionId}`, src: 'HvHLobbyPage.tsx:280' })}
              </div>`).join('')}</div>`, 'var(--jade-l)')}
          ${col('PersonAdd', '好友与关注',
            b === 'empty' || b === 'loading' ? `<p class="muted" style="margin:0;font-size:.875rem">你还没有关注任何人。</p>`
            : `<div class="stack g8">
                <div class="rowbetween" style="padding:10px 12px;border-radius:10px;background:rgba(255,255,255,.02)">
                  <div class="inline" style="gap:10px"><span class="avatar">D</span>
                    <div><div style="font-size:.9rem;font-weight:600">dan</div><span class="chip" style="height:20px">2d</span></div></div>
                  ${ibtn({ icon: 'PersonRemove', label: '取消关注', size: 'sm', act: 'DELETE /api/v1/users/follow/dan', src: 'FriendsPanel.tsx' })}
                </div></div>`, 'var(--info)')}
        </div>
        <div class="inline" style="margin-top:20px;gap:8px">
          ${dlgOpen('invite', '（演示）收到一条对局邀请', { variant: 'outlined', color: 'inherit', size: 'sm', src: 'HvHLobbyPage.tsx' })}
        </div>
        <div class="alert warning" style="margin-top:14px;align-items:center">
          先在「升降级对弈」打完 5 局定级赛，才能进行人人排位。
          ${ibtn({ icon: 'Close', label: 'Close', size: 'sm', act: 'setSnackbar(null)（6000ms 后也会自动关闭）', src: 'HvHLobbyPage.tsx' })}
        </div>
      </div>`,
    };
  },
  note: `<h3>页头已是单行左右，但右边是两个页面动作</h3>
    <p>「快速匹配（排位）」「自定义对局」是本页的主行动，不是返回上一级。
    按 spec §2.4，页头右侧只放「← 对局」，这两个按钮要下沉到正文首屏。
    副标题「与其他玩家对弈或观看直播对局。」同样下沉。</p>
    <p>标题选哪个要定：<code>lobby:title</code> 的中文是「多人游戏大厅」，
    但 <code>PlayMenu</code> 的入口卡片写的是「人人对弈」（<code>play:hvh</code>）。
    入口与页面标题现在对不上。</p>`,
});

const roomRail = (mode) => {
  const tool = (id, label, ic, dis) => tbtn({ id: 'gr-' + id, label, icon: ic, disabled: dis, src: 'RightSidebarPanel.tsx' });
  const spectator = mode === 'spectator';
  return `<div style="padding:16px" data-zone="right-rail-top">
      <div class="rowbetween" style="gap:12px">
        <div class="card" style="flex:1;padding:12px;border-radius:10px">
          <div class="inline" style="gap:8px;margin-bottom:6px"><i class="kstone b"></i>
            <span style="font-weight:600;font-size:.9rem">${spectator ? 'bob' : 'fan'}</span>
            ${ibtn({ icon: 'PersonAdd', label: 'Follow', size: 'sm', act: 'handleToggleFollow(name) → API.followUser / unfollowUser', src: 'PlayerCard.tsx' })}
            ${ibtn({ icon: 'Pause', label: '暂停/继续计时', size: 'sm', act: 'onPauseTimer()（本页不可达，仅人机对局页可见）', src: 'PlayerCard.tsx' })}</div>
          <div class="mono" style="font-size:1.35rem;font-weight:600">08:24</div>
          <div class="dim" style="font-size:.7rem">5k · 提子 3</div>
        </div>
        <div class="card" style="flex:1;padding:12px;border-radius:10px">
          <div class="inline" style="gap:8px;margin-bottom:6px"><i class="kstone w"></i>
            <span style="font-weight:600;font-size:.9rem">cat</span>
            ${ibtn({ icon: 'PersonAdd', label: '关注', size: 'sm', act: 'API.followUser(name)', src: 'PlayerCard.tsx' })}</div>
          <div class="mono" style="font-size:1.35rem;font-weight:600">06:51</div>
          <div class="dim" style="font-size:.7rem">4k · 提子 5</div>
        </div>
      </div>
      <p class="muted" style="margin:12px 0 0;font-size:.8rem">中国规则 · 贴 7.5 目 · 19 路</p>
    </div>
    <hr class="hr">
    <div style="padding:16px" data-zone="right-rail-middle">
      <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:6px">
        ${tool('terr', '领地', 'Map', true)}${tool('hint', '建议', 'TipsAndUpdates', true)}
        ${tool('chart', '图表', 'Timeline', true)}${tool('undo', '悔棋', 'Undo', spectator)}
        ${tool('pass', '停一手', 'PanToolAlt', spectator)}${tool('resign', '认输', 'Flag', spectator)}
        ${tool('count', '数子', 'Calculate', spectator)}${tool('3d', '3D', 'ViewInAr')}
      </div>
      ${mode === 'ended' ? `<div class="alert success" style="margin-top:14px">数子结束：黑胜 2.5 目</div>` : ''}
      <hr class="hr" style="margin:16px 0">
      ${swrow({ id: 'gr-coords', label: '坐标', on: true, src: 'RightSidebarPanel.tsx' })}
      ${swrow({ id: 'gr-numbers', label: '手数', src: 'RightSidebarPanel.tsx' })}
      ${swrow({ id: 'gr-drop', label: '落子特效', src: 'RightSidebarPanel.tsx' })}
    </div>`;
};

SCREENS.push({
  id: 'game-room', group: '对局', label: '人人对弈 · 对局室', route: '/galaxy/play/human/room/:sessionId',
  nav: 'play', kind: 'content',
  branches: [
    { id: 'player', label: '棋手 2D' }, { id: 'spectator', label: '观战者' },
    { id: '3d', label: '3D 视图' }, { id: 'ended', label: '对局已结束' },
    { id: 'loading', label: '加载中' }, { id: 'error', label: '加载失败' },
  ],
  dialogs: {
    leave: `<div class="dlg" data-zone="dialog"><h3>离开对局？</h3><p>离开将导致弃权。确定吗？</p>
      <div class="acts">${btn({ label: '取消', color: 'inherit', act: 'setShowLeaveConfirm(false)', src: 'GameRoomPage.tsx:198' })}
      ${btn({ label: '离开并弃权', variant: 'contained', color: 'err', act: 'API.leaveMultiplayerGame → 导航 /galaxy/play/human', src: 'GameRoomPage.tsx:206' })}</div></div>`,
    resign: `<div class="dlg" data-zone="dialog"><h3>认输？</h3><p>确定要认输吗？</p>
      <div class="acts">${btn({ label: '取消', color: 'inherit', act: 'setShowResignConfirm(false)', src: 'GameRoomPage.tsx:212' })}
      ${btn({ label: '认输', variant: 'contained', color: 'err', act: 'API.resign(sessionId)', src: 'GameRoomPage.tsx:220' })}</div></div>`,
    count: `<div class="dlg" data-zone="dialog"><h3>数子结束对局？</h3><p>计算最终得分以结束对局。</p>
      <div class="acts">${btn({ label: '取消', color: 'inherit', act: 'setShowCountConfirm(false)', src: 'GameRoomPage.tsx:238' })}
      ${btn({ label: '数子', variant: 'contained', act: 'API.requestCount(sessionId)', src: 'GameRoomPage.tsx:246' })}</div></div>`,
    countreq: `<div class="dlg" data-zone="dialog"><h3>数子请求</h3><p>cat 想要通过数子结束对局。你同意吗？</p>
      <div class="acts">${btn({ label: '拒绝', color: 'err', act: 'API.respondCount(false)', src: 'GameRoomPage.tsx:254' })}
      ${btn({ label: '接受', variant: 'contained', act: 'API.respondCount(true)', src: 'GameRoomPage.tsx:262' })}</div></div>`,
    end: `<div class="dlg" data-zone="dialog"><h3>对局结束</h3><p>你赢了！对手认输。</p>
      <div class="acts">${btn({ label: '返回大厅', variant: 'contained', act: '导航 /galaxy/play/human', src: 'GameRoomPage.tsx:230' })}</div></div>`,
  },
  render(b) {
    if (b === 'loading') return { raw: `<div style="height:100%;display:grid;place-items:center" data-zone="body"><div class="spin"></div></div>` };
    if (b === 'error') {
      return {
        raw: `<div style="padding:32px" data-zone="body"><div class="alert error" style="margin-bottom:16px">对局会话不存在或已结束</div>
          ${btn({ label: '返回大厅', variant: 'outlined', act: '导航 /galaxy/play/human', src: 'GameRoomPage.tsx:165' })}</div>`,
      };
    }
    const spectator = b === 'spectator';
    const ended = b === 'ended';
    const is3d = b === '3d';
    return {
      raw: `<div class="lrow vh100" data-zone="body">
        <div class="lmain">
          <div class="lhead" data-zone="above-board">
            <span style="font-size:.875rem;font-weight:600;color:${spectator ? 'var(--tx2)' : 'var(--jade-l)'}">
              ${spectator ? '观战中' : ended ? '对局已结束' : '轮到你了'}</span>
            <div class="inline" style="gap:16px">
              <span class="inline dim" style="gap:6px;font-size:.75rem">${icon('Visibility', 'sm')}3 观众</span>
              ${spectator
                ? btn({ label: '退出', variant: 'outlined', size: 'sm', color: 'inherit', icon: 'ExitToApp', act: '导航 /galaxy/play/human', src: 'GameRoomPage.tsx:280' })
                : ended ? '' : dlgOpen('leave', '离开对局', { variant: 'outlined', color: 'err', size: 'sm', icon: 'ExitToApp', src: 'GameRoomPage.tsx:290' })}
            </div>
          </div>
          <div class="lboard" style="padding:16px">
            ${is3d
              ? `<div style="width:100%;height:100%;border-radius:12px;background:radial-gradient(700px 400px at 50% 20%,#3a3226,#171310);display:grid;place-items:center;position:relative">
                   <canvas class="boardcv" data-floor="200" data-board='${esc(JSON.stringify({ stones: demoStones(26), coords: true }))}' style="transform:perspective(900px) rotateX(46deg) scale(.86);box-shadow:0 40px 70px -20px rgba(0,0,0,.85)"></canvas>
                   <span class="chip info" style="position:absolute;top:14px;left:14px">Board3D · three.js 懒加载</span>
                   <div style="position:absolute;right:14px;bottom:14px;display:flex;flex-direction:column;gap:6px;align-items:center;background:rgba(0,0,0,.5);padding:8px;border-radius:10px">
                <button class="iconbtn sm" aria-label="Zoom in" title="Zoom in" data-act="handleZoom('in') — 相机拉近一档（title 未本地化，无 aria-label）" data-src="Board3D/index.tsx:215">+</button>
                <button class="iconbtn sm" aria-label="Zoom out" title="Zoom out" data-act="handleZoom('out') — 相机拉远一档" data-src="Board3D/index.tsx:232">−</button>
                <input class="slider" type="range" min="0" max="100" value="55" aria-label="Tilt angle 俯仰角" title="Tilt angle" data-act="handleTiltChange — OrbitControls 极角 π*0.05…π*0.38" data-src="Board3D/index.tsx:241" style="width:70px">
              </div>
              <div style="position:absolute;left:50%;bottom:12px;transform:translateX(-50%);background:rgba(0,0,0,.5);padding:6px 12px;border-radius:20px">
                <input class="slider" type="range" min="0" max="100" value="50" aria-label="左右" title="Yaw angle" data-act="handleYaw — OrbitControls 方位角" data-src="Board3D/index.tsx:271" style="width:150px">
              </div>
                 </div>`
              : `<canvas class="boardcv" data-floor="200" data-board='${esc(JSON.stringify({ stones: demoStones(ended ? 40 : 26), coords: true, last: ended ? [15, 9, 'W'] : [12, 9, 'W'], territory: ended ? [[2, 2, 1], [3, 2, 1], [2, 3, 1], [16, 16, -1], [15, 16, -1], [16, 15, -1]] : null }))}'></canvas>`}
          </div>
        </div>
        <div class="lrail w500">
          <div class="lrail-scroll">${roomRail(b)}</div>
          <div style="padding:12px;background:var(--surface);border-top:1px solid var(--line);display:flex;justify-content:center;gap:4px" data-zone="right-rail-actions">
            ${ibtn({ icon: 'SkipPrevious', label: '跳到开局', act: 'API.undo(sessionId, 9999)', src: 'RightSidebarPanel.tsx' })}
            ${ibtn({ icon: 'FastRewind', label: '后退 10 手', act: 'API.undo(sessionId, 10)', src: 'RightSidebarPanel.tsx' })}
            ${ibtn({ icon: 'ArrowBack', label: '后退一手', act: 'API.undo(sessionId, 1)', src: 'RightSidebarPanel.tsx' })}
            ${ibtn({ icon: 'ArrowForward', label: '前进一手', act: 'API.redo(sessionId, 1)', src: 'RightSidebarPanel.tsx' })}
            ${ibtn({ icon: 'FastForward', label: '前进 10 手', act: 'API.redo(sessionId, 10)', src: 'RightSidebarPanel.tsx' })}
            ${ibtn({ icon: 'SkipNext', label: '跳到最后', act: 'API.redo(sessionId, 9999)', src: 'RightSidebarPanel.tsx' })}
          </div>
        </div>
        <div style="position:absolute;left:50%;bottom:14px;transform:translateX(-50%);display:flex;gap:8px;z-index:20">
          ${dlgOpen('resign', '认输弹窗', { variant: 'outlined', size: 'sm', color: 'inherit' })}
          ${dlgOpen('count', '数子弹窗', { variant: 'outlined', size: 'sm', color: 'inherit' })}
          ${dlgOpen('countreq', '数子请求', { variant: 'outlined', size: 'sm', color: 'inherit' })}
          ${dlgOpen('end', '终局弹窗', { variant: 'outlined', size: 'sm', color: 'inherit' })}
        </div>
        ${VH}</div>`,
    };
  },
  note: `<h3>六个棋盘页里第二难的一个</h3>
    <p>棋盘上方有一条状态/观众/离开条（<code>GameRoomPage.tsx:266-300</code>），spec §2.2 明令棋盘正上方不得有工具条。
    右栏是 500px 的 <code>RightSidebarPanel</code>，模板是 340px。</p>
    <p>好消息：<code>GamePage</code> 的 <code>isRated</code> 分支已经把同一个
    <code>RightSidebarPanel</code> 用 <code>embedded</code> 模式塞进 <code>railBody</code> 了
    （<code>GamePage.tsx:411-425</code>），这条路走过一遍。「离开对局」也可以直接换成
    <code>ModulePlate</code> 的返回 + <code>registerActiveGame</code> 的确认框，
    页面自己那个 <code>Dialog</code> 就能删。</p>
    <p>⚠️ 这页有 5 个 <code>Dialog</code> 和 1 个浏览器原生 <code>alert()</code>（数子被拒时），
    加上实时 WebSocket 状态。取图需要真开一局两人对弈。</p>`,
});
