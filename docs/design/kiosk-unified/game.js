(function () {
  const families = window.KioskDesignFamilies = window.KioskDesignFamilies || {};

  function icon(ctx, name) { return ctx.I(name); }
  function help(copy, label = '说明') {
    return `<button type="button" class="u-game-help" aria-label="${label}" data-help="${copy}"><svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="M12 11v6m0-10h.01"/></svg></button>`;
  }
  function stone(color) { return `<span class="u-game-stone u-game-stone--${color}" aria-hidden="true"></span>`; }
  function duelSurface(side, turn) {
    const id = `u-game-duel-${side}-${turn ? 'turn' : 'rest'}`;
    const path = side === 'left'
      ? 'M14 1 H218 Q233 1 230 15 L214 111 Q211 125 197 125 H14 Q1 125 1 112 V14 Q1 1 14 1 Z'
      : 'M36 1 H220 Q233 1 233 14 V112 Q233 125 220 125 H17 Q1 125 4 111 L20 15 Q22 1 36 1 Z';
    const start = turn ? '#2b6244' : '#26362c';
    const end = turn ? '#1c432f' : '#15231b';
    const stroke = turn ? '#69c98a' : '#405948';
    return `<svg class="u-game-player-surface" viewBox="0 0 234 126" preserveAspectRatio="none" aria-hidden="true"><defs><linearGradient id="${id}" x2="0.8" y2="1"><stop stop-color="${start}"/><stop offset="1" stop-color="${end}"/></linearGradient></defs><path d="${path}" fill="url(#${id})" stroke="${stroke}" stroke-width="1.5"/></svg>`;
  }
  function action(ctx, name, label, options = '') {
    return `<button type="button" class="u-game-action${options.includes('danger') ? ' u-game-action--danger' : ''}" ${options.includes('disabled') ? 'disabled' : ''}>${icon(ctx, name)}<span>${label}</span></button>`;
  }

  function game(ctx) {
    const graph = `<svg viewBox="0 0 432 102" role="img" aria-label="实机当前只有一手评估点，黑方胜率 47.5%"><path class="u-game-graph-grid" d="M4 18H428M4 51H428M4 84H428"/><circle class="u-game-graph-point" cx="20" cy="54" r="5"/></svg>`;
    return `<div class="u-game-rail-mask"></div><div class="u-game-rail">
      <div class="u-game-game-head"><button type="button" class="u-game-back" data-switch="play">${icon(ctx, 'back')}<span>退出对局</span></button><strong>自由对弈</strong><span>19 路 · 中国规则 · 贴目 7.5 · 不让子</span></div>
      <div class="u-game-players">
        <section class="u-game-player">${duelSurface('left', false)}<div class="u-game-player-name">${stone('white')}<strong>白方 · 6 级</strong></div><div class="u-game-player-clock">不限时</div><div class="u-game-player-foot"><span class="u-game-player-status">已落子</span><span class="u-game-player-detail">提子 0</span></div></section>
        <section class="u-game-player u-game-player--turn">${duelSurface('right', true)}<div class="u-game-player-name">${stone('black')}<strong>黑 · fan（你）</strong></div><div class="u-game-player-clock">不限时</div><div class="u-game-player-foot"><span class="u-game-player-status">轮到你 · 第 1 手</span><span class="u-game-player-detail">提子 0</span></div></section>
      </div>
      <section class="u-game-chart"><div class="u-game-chart-head"><strong>胜率 · KataGo</strong><span>黑 47.5% · 黑 +0.2 目</span></div><div class="u-game-graph">${graph}</div></section>
      <div class="u-game-toggles"><button type="button" class="u-game-toggle u-game-toggle--on" data-game-toggle="coordinates" aria-label="坐标" aria-pressed="true">${icon(ctx, 'grid')}坐标</button><button type="button" class="u-game-toggle" data-game-toggle="move-numbers" aria-label="手数" aria-pressed="false">${icon(ctx, 'numbers')}手数</button>${help('本局满 100 手后可数子。领地、支招、图表需要登录；本实机的支招和数子当前不可用。', '对局操作说明')}</div>
      <div class="u-game-actions">${[
        ['board', '领地', ''], ['hint', '支招', 'disabled'], ['chart', '图表', ''], ['count', '数子', 'disabled'],
        ['undo', '悔棋', ''], ['hand', '停一手', ''], ['stop', '认输', 'danger']
      ].map(([name, label, options]) => action(ctx, name, label, options)).join('')}</div>
    </div>`;
  }

  function localSeat(ctx, color) {
    const black = color === 'black';
    const label = black ? '黑方' : '白方';
    const state = black ? '走棋中' : '等待中';
    const guidance = black ? '轮到你落子' : '等待黑方';
    const confirm = black ? '确认落子' : '等待黑方';
    return `<section class="u-game-local-seat u-game-local-seat--${color}${black ? ' u-game-local-seat--turn' : ''}" aria-label="${label}玩家面板">
      <div class="u-game-local-person">${stone(color)}<div><div class="u-game-local-side"><strong>${label}</strong><span>${state}</span></div><div class="u-game-local-name">${label}</div></div></div>
      <div class="u-game-local-clock"><div class="u-game-local-clock-meta"><span>剩余主时间</span><span>已暂停</span></div><strong>不限时</strong></div>
      <div class="u-game-local-guidance">${guidance}</div>
      <div class="u-game-local-keys"><button type="button" class="u-game-local-toggle u-game-local-toggle--on" data-game-toggle="coordinates" aria-label="坐标" aria-pressed="true">${icon(ctx, 'grid')}<span class="u-game-local-toggle-label">坐标</span></button><button type="button" class="u-game-local-toggle" data-game-toggle="move-numbers" aria-label="手数" aria-pressed="false">${icon(ctx, 'numbers')}<span class="u-game-local-toggle-label">手数</span></button>${action(ctx, 'hand', '停一手', black ? '' : 'disabled')}${action(ctx, 'count', '数子', 'disabled')}${action(ctx, 'stop', '认输', 'danger')}</div>
      <button type="button" class="u-game-local-confirm" disabled>${black ? '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m4 12 5 5L20 6"/></svg>' : ''}<span>${confirm}</span><em>${black ? '先在棋盘选点' : '对方确认后再落子'}</em></button>
    </section>`;
  }
  function local(ctx) {
    return `<div class="u-game-local-mask u-game-local-mask--left"></div><div class="u-game-local-mask u-game-local-mask--right"></div>${localSeat(ctx, 'black')}${localSeat(ctx, 'white')}`;
  }
  function localDialogs(ctx) {
    const cleanGame = ctx.root + ctx.byId['game-local'].current;
    return `<img class="u-game-local-base" src="${cleanGame}" alt="" aria-hidden="true">${local(ctx)}<div class="u-game-dialog-scrim"></div><section class="u-game-dialog" role="dialog" aria-modal="true" aria-label="退出这局？"><h2 class="u-game-dialog-title">退出这局？</h2><p>这局还没下完，退出后不会保存。</p><div class="u-game-dialog-actions"><button type="button" data-switch="game-local">继续下</button><button type="button" class="u-game-dialog-danger" data-switch="play">退出不保存</button></div></section>`;
  }

  function spectate(ctx) {
    return `<div class="u-game-spectate-head-mask"></div><div class="u-game-spectate-head"><button type="button" class="u-game-back" data-switch="lobby">${icon(ctx, 'back')}<span>返回大厅</span></button><strong>大厅对局观战</strong><span class="u-game-spectate-live">实时快照</span></div>
      <div class="u-game-spectate-mask"></div><section class="u-game-spectate-panel"><div class="u-game-spectate-title"><strong>在线大厅</strong><span>只读观战</span><b>对局中</b></div>
        <div class="u-game-spectate-players"><div class="u-game-spectate-player">${duelSurface('left', false)}<div>${stone('black')}<strong>轻轻初晴</strong><span>执黑</span></div><b>职业水平</b><span>对局棋手</span></div><div class="u-game-spectate-player u-game-spectate-player--turn">${duelSurface('right', true)}<div>${stone('white')}<strong>木木寻山</strong><span>执白</span></div><b>职业水平</b><span>轮到落子</span></div></div>
        <div class="u-game-spectate-latest"><strong>第 279 手 · 最新落子 K16</strong><span>实时盘面 · 每 2 秒同步</span></div>
        <div class="u-game-spectate-footer"><span>1 人观战</span>${help('观看实时盘面，不参与对局。此画面每 2 秒从大厅同步一次。', '观战说明')}</div>
      </section>`;
  }

  families.game = (_s, ctx) => game(ctx);
  families['game-local'] = (_s, ctx) => local(ctx);
  families['game-local-dialogs'] = (_s, ctx) => localDialogs(ctx);
  families['pvp-spectate'] = (_s, ctx) => spectate(ctx);
  document.addEventListener('click', (event) => {
    const button = event.target.closest('#stage #proposal-layer [data-game-toggle]');
    if (!button) return;
    const enabled = button.getAttribute('aria-pressed') !== 'true';
    const peers = button.classList.contains('u-game-local-toggle')
      ? document.querySelectorAll(`#stage #proposal-layer .u-game-local-toggle[data-game-toggle="${button.dataset.gameToggle}"]`)
      : [button];
    peers.forEach(peer => {
      peer.setAttribute('aria-pressed', String(enabled));
      peer.classList.toggle(peer.classList.contains('u-game-local-toggle') ? 'u-game-local-toggle--on' : 'u-game-toggle--on', enabled);
    });
  });
}());
