(function () {
  const paths = {
    board: '<rect x="3" y="3" width="18" height="18" rx="2"/><path d="M3 9h18M3 15h18M9 3v18m6-18v18"/>',
    robot: '<rect x="5" y="7" width="14" height="13" rx="3"/><path d="M12 3v4M9 3h6M8 12h.01M16 12h.01M9 16h6"/>',
    trophy: '<path d="M7 4h10v7a5 5 0 0 1-10 0V4ZM7 6H4v3a3 3 0 0 0 3 3m10-6h3v3a3 3 0 0 1-3 3M12 16v4m-4 0h8"/>',
    users: '<circle cx="9" cy="8" r="3"/><path d="M3 20v-2a6 6 0 0 1 12 0v2H3ZM17 11a3 3 0 0 0 0-6M17 14a6 6 0 0 1 4 6h-4"/>',
    globe: '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c3 3 4 6 4 9s-1 6-4 9M12 3c-3 3-4 6-4 9s1 6 4 9"/>',
    history: '<path d="M3 12a9 9 0 1 0 3-6.7M3 4v5h5M12 7v5l4 2"/>',
    info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v6M12 7h.01"/>',
    chevron: '<path d="m9 5 7 7-7 7"/>',
    camera: '<rect x="3" y="6" width="18" height="14" rx="2"/><path d="m8 6 1-2h6l1 2"/><circle cx="12" cy="13" r="3"/>',
    calibrate: '<path d="M4 9V4h5m6 0h5v5m0 6v5h-5m-6 0H4v-5M8 12h8m-4-4v8"/>',
    led: '<path d="M9 18h6M10 21h4M8 16c-1-2-3-3-3-6a7 7 0 0 1 14 0c0 3-2 4-3 6z"/>'
  };
  const icon = (name) => `<svg class="u-play-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${paths[name]}</svg>`;
  const attr = (value) => value.replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;');
  const help = (copy) => `<button type="button" class="u-play-info" data-help="${attr(copy)}" aria-label="说明">${icon('info')}</button>`;
  const mode = (id, name, mark) => `<div class="u-play-card"><button type="button" class="u-play-card-action" data-switch="${id}">${icon(mark)}<span>${name}</span>${icon('chevron')}</button></div>`;
  const marks = {OGS: 'ogs.svg', '星阵围棋': 'golaxy.png', '野狐围棋': 'fox.png'};
  const platform = (id, name, state, disabled) => `<div class="u-play-platform${disabled ? ' u-play-platform-disabled' : ''}"><button type="button" class="u-play-platform-action" ${disabled ? 'disabled aria-disabled="true"' : `data-switch="${id}"`}><img class="u-play-platform-mark" src="../../katrain/web/ui/src/kiosk/assets/platform-marks/${marks[name]}" alt=""><span class="u-play-platform-copy"><strong>${name}</strong><em>${state}</em></span>${disabled ? '' : icon('chevron')}</button></div>`;
  const status = (label, value, tone) => `<div class="u-play-status u-play-status-${tone}"><span>${label}</span><strong>${value}</strong></div>`;

  window.KioskDesignFamilies = window.KioskDesignFamilies || {};
  window.KioskDesignFamilies.play = (s, ctx) => {
    const shot = ctx.root + ctx.byId.play.current;
    return `<div class="u-play-layer">
      <aside class="u-play-console" aria-label="实体棋盘状态">
        <div class="u-play-console-title"><strong>实体棋盘</strong>${help('镜像中的空盘尚未接入识别结果；当前实体盘暂不可用。')}</div>
        <div class="u-play-board-frame"><div class="u-play-board-crop"><img src="${shot}" alt="实机实体棋盘空盘预览"></div></div>
        <div class="u-play-sync"><span>识别盘面未接入</span><strong>暂不可用</strong></div>
        <div class="u-play-statuses">
          ${status('摄像头', '未连接', 'bad')}
          ${status('标定', '需校准', 'warn')}
          ${status('LED', '未连接', 'warn')}
        </div>
      </aside>
      <main class="u-play-rail" aria-label="对弈首页">
        <div class="u-play-heading"><h2>夜深了，<span>fan</span></h2><span class="u-play-heading-hint">选择对弈方式</span></div>
        <div class="u-play-panels">
          <div class="u-play-panel">
            <section class="u-play-group"><h3>人机对弈</h3><div class="u-play-mode-grid">
              ${mode('setup-free', '自由对弈', 'robot')}
              ${mode('setup-ranked', '升降级对弈', 'trophy')}
            </div></section>
            <section class="u-play-group"><h3>人人对弈</h3><div class="u-play-mode-grid">
              ${mode('setup-local', '本地对局', 'users')}
              ${mode('lobby', '在线大厅', 'globe')}
            </div></section>
            <section class="u-play-group"><h3>跨平台对弈</h3><div class="u-play-platform-grid">
              ${platform('platform-login-ogs', 'OGS', '未连接', false)}
              ${platform('platform-login', '星阵围棋', '未连接', false)}
              ${platform('', '野狐围棋', '暂不能对弈', true)}
            </div></section>
            <section class="u-play-group u-play-history-group"><h3>对局历史</h3><div class="u-play-card u-play-history-card"><button type="button" class="u-play-card-action" data-switch="review">${icon('history')}<span>全部对局</span>${icon('chevron')}</button></div></section>
          </div>
        </div>
      </main>
    </div>`;
  };
})();
