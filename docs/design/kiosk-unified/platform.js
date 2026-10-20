(function () {
  const F = window.KioskDesignFamilies = window.KioskDesignFamilies || {};
  let phoneAreas = [
    ['中国', '86'], ['中国台湾', '886'], ['中国香港', '852'], ['中国澳门', '853'],
    ['美国', '1'], ['韩国', '82'], ['日本', '81'], ['英国', '44'],
    ['澳大利亚', '61'], ['新加坡', '65']
  ];
  const areaOptions = () => phoneAreas.map(([name, dial]) => `<option value="${name}">${name} +${dial}</option>`).join('');
  // Reuse the complete country list shipped with the actual login page.
  fetch('../../katrain/web/ui/src/kiosk/constants/golaxyPhoneAreas.json')
    .then((response) => response.ok ? response.json() : [])
    .then((areas) => {
      if (!Array.isArray(areas) || !areas.length) return;
      phoneAreas = areas.map(({ name, dial }) => [name, dial]);
      document.querySelectorAll('.u-p-phone-area').forEach((select) => {
        const selected = select.value;
        select.innerHTML = areaOptions();
        select.value = selected;
      });
    }).catch(() => {});
  const icon = (name) => {
    const paths = {
      info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v6m0-10h.01"/>',
      users: '<circle cx="9" cy="8" r="3"/><path d="M3 20v-2a6 6 0 0 1 12 0v2H3ZM17 11a3 3 0 0 0 0-6M17 14a6 6 0 0 1 4 6h-4"/>',
      invite: '<circle cx="8" cy="8" r="3"/><path d="M2 20a6 6 0 0 1 12 0m5-11v10m-5-5h10"/>',
      search: '<circle cx="10.5" cy="10.5" r="6.5"/><path d="m15.5 15.5 6 6"/>',
      board: '<rect x="3" y="3" width="18" height="18" rx="2"/><path d="M3 9h18M3 15h18M9 3v18m6-18v18"/>',
      list: '<path d="M10 6h11M10 12h11M10 18h11M3 5h2v3M3 12h3l-3 3h3M3 18h3"/>',
      refresh: '<path d="M20 7a9 9 0 0 0-15-1L3 9m0-5v5h5M4 17a9 9 0 0 0 15 1l2-3m0 5v-5h-5"/>',
      clock: '<circle cx="12" cy="12" r="9"/><path d="M12 6v6l4 2"/>',
      play: '<path d="m8 5 11 7-11 7z"/>',
      arrow: '<path d="M5 12h14m-6-6 6 6-6 6"/>',
      robot: '<rect x="5" y="7" width="14" height="13" rx="3"/><path d="M12 3v4M9 3h6M8 12h.01M16 12h.01M9 16h6"/>',
      close: '<path d="M5 5l14 14M19 5 5 19"/>'
    };
    return `<svg class="u-p-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${paths[name]}</svg>`;
  };
  const escape = (x) => x.replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;');
  const help = (copy) => `<button type="button" class="u-p-help" aria-label="说明" data-help="${escape(copy)}">${icon('info')}</button>`;
  const bar = (ctx, back, title, status = '') => `<header class="u-p-bar"><button type="button" class="u-p-back" data-switch="${back === '返回星阵围棋' ? 'golaxy-home' : 'play'}">${ctx.I('back')}${back}</button><h1>${title}</h1>${status ? `<span class="u-p-bar-status">${status}</span>` : ''}</header>`;
  const section = (title, copy = '') => `<div class="u-p-section-title"><strong>${title}</strong>${copy ? help(copy) : ''}</div>`;
  const card = (name, symbol, state, target, copy, disabled = false, showHelp = true) => `<div class="u-p-mode"><button type="button" class="u-p-mode-action" ${disabled ? 'disabled aria-disabled="true"' : target?.startsWith('@') ? `data-u-p-tab="${target.slice(1)}"` : target ? `data-switch="${target}"` : `data-help="${escape(copy)}"`}>${icon(symbol)}<span>${name}</span>${state ? `<em>${state}</em>` : ''}</button>${showHelp ? help(copy) : ''}</div>`;
  document.addEventListener('click', (event) => {
    const tab = event.target.closest?.('[data-u-p-tab]');
    if (tab?.closest('.u-p-lobby')) {
      const input = document.getElementById(`u-p-lobby-${tab.getAttribute('data-u-p-tab')}`);
      if (input) input.checked = true;
    }
  });
  document.addEventListener('change', (event) => {
    const box = event.target.closest?.('.u-p-time input[type="checkbox"]');
    if (box && !box.checked && !box.closest('.u-p-time-grid').querySelector('input:checked')) box.checked = true;
  });
  const board = (ctx) => `<div class="u-p-board" aria-label="19 路空盘预览"><div class="u-p-board-crop"><img src="${ctx.root + ctx.byId['platform-room'].current}" alt="实机 19 路空盘预览"></div><div class="u-p-board-label">19 路 · 空盘预览</div></div>`;
  const mark = (ctx, id) => `<img class="u-p-mark" src="${ctx.root}katrain/web/ui/src/kiosk/assets/platform-marks/${id === 'ogs' ? 'ogs.svg' : 'golaxy.png'}" alt="">`;
  const inputRows = () => `<div class="u-p-input"><span>落子</span><div class="u-p-segment"><input id="u-p-screen" name="u-p-input" type="radio"><label for="u-p-screen">屏幕</label><input id="u-p-board" name="u-p-input" type="radio" checked><label for="u-p-board">实体盘</label></div></div>`;
  const notes = (quick) => help(quick ? '可多选用时，至少选择一种。星阵完成匹配后才进入对局。AI 对手暂不可用，当前只匹配棋友。星阵开局功能暂不可用，请稍后再试。' : '加入房间后仍需确认对局身份和开局状态。星阵开局功能暂不可用，请稍后再试。');

  F.lobby = (_s, ctx) => `<div class="u-p-body u-p-lobby">${bar(ctx, '返回对弈', '在线大厅', '<span class="u-p-online"><i class="u-p-live-dot"></i>已连接</span><span>我的段位 2 级</span>')}
    <div class="u-p-lobby-main">${section('开一局', '快速匹配按当前段位找棋友，不计升降段位。邀请棋友可直接邀请任意段位的空闲棋友。')}
      <div class="u-p-lobby-actions">${card('快速匹配', 'users', '', '', '按当前段位找棋友，不计升降段位。', false, false)}${card('邀请棋友', 'invite', '', '@players', '直接邀请任意段位的空闲棋友。', false, false)}</div>
      ${section('对战大厅', '点选棋局可观战；大厅对局不计升降段位。黑棋在左，白棋在右；自己的对局可返回棋盘。')}
      <div class="u-p-lobby-panel"><input type="radio" name="u-p-lobby-tab" id="u-p-lobby-games" checked><input type="radio" name="u-p-lobby-tab" id="u-p-lobby-players"><div class="u-p-lobby-tabs"><div class="u-p-lobby-tab-capsule"><label for="u-p-lobby-games">进行中对局 3</label><label for="u-p-lobby-players">在线棋友 117</label></div></div><div class="u-p-lobby-games-panel"><div class="u-p-game-grid">
        ${[['2f40','石桥小羊','西窗如秋','153 手','执黑 · 准9段','准9段 · 执白'],['6468','星河海棠','圆圆清和','127 手','执黑 · 9段','9段 · 执白'],['a59a','轻轻初晴','木木寻山','41 手','执黑 · 职业水平','职业水平 · 执白']].map(r=>`<button type="button" class="u-p-game" data-help="设计预览：正式页面可打开 ${r[0]} 房观战。"><span class="u-p-game-head"><b>${r[0]} 房</b><span>分先 · 19 路</span><span>0 人观战</span></span><span class="u-p-game-players"><span><strong><i class="u-p-stone u-p-stone-black"></i>${r[1]}</strong><small>${r[4]}</small></span><b>${r[3]}</b><span><strong><i class="u-p-stone u-p-stone-white"></i>${r[2]}</strong><small>${r[5]}</small></span></span></button>`).join('')}
      </div></div><div class="u-p-lobby-players-panel"><div class="u-p-filter"><input type="radio" name="u-p-peer-filter" id="u-p-peer-all" checked><label for="u-p-peer-all">全部棋友</label><input type="radio" name="u-p-peer-filter" id="u-p-peer-rank"><label for="u-p-peer-rank">同段位</label></div><p>名单未采集 · 当前仅知 117 人</p>${help('当前截图没有展示棋友名单的具体条目；在线棋友数量来自实机。')}</div></div>
    </div></div>`;

  const loginFacts = {
    golaxy: '用星阵自己的账号登录，不是智星盒账号；没有账号请在手机星阵 APP 注册，盒上无法注册。扫码、验证码、密码三种方式都可用。只保存星阵发的登录令牌，不保存密码；可在设置里断开。',
    ogs: '使用 online-go.com 账号；注册需在浏览器完成。盒上暂不支持 Google 或 Apple 登录；这类账号需先在 OGS 网页设置密码。只保存登录后的会话，不保存密码；可去设置断开。'
  };
  const login = (ctx, mode) => {
    const ogs = mode === 'ogs', scan = mode === 'scan', sms = mode === 'sms';
    const name = ogs ? 'OGS' : '星阵围棋';
    const sub = ogs ? '未连接 · 用 online-go.com 的账号' : scan ? '未连接 · 用手机上的星阵 APP 扫一扫' : sms ? '未连接 · 用手机验证码登录' : '未连接 · 用星阵的账号密码登录';
    const title = `登录${name}`;
    return `<div class="u-p-body u-p-login">${bar(ctx, '返回对弈', name, sub)}<div class="u-p-login-card"><aside class="u-p-login-aside"><div class="u-p-login-brand">${mark(ctx, ogs ? 'ogs' : 'golaxy')}<div><strong>${name}</strong><span>${ogs ? 'online-go.com' : '19x19.com'}</span></div></div><p>使用${name}账号连接</p>${help(loginFacts[ogs ? 'ogs' : 'golaxy'])}<span class="u-p-disconnected">尚未连接</span></aside>
      <div class="u-p-login-main"><div class="u-p-form-title">${title}${ogs ? '<span>段位也从这个账号来</span>' : ''}${help(loginFacts[ogs ? 'ogs' : 'golaxy'])}</div>${ogs ? '' : `<div class="u-p-login-tabs"><button type="button" class="${scan ? 'is-active' : ''}" data-switch="platform-login">扫码</button><button type="button" class="${sms ? 'is-active' : ''}" data-switch="platform-login-sms">验证码</button><button type="button" class="${mode === 'pw' ? 'is-active' : ''}" data-switch="platform-login-pw">密码</button></div>`}
      ${scan ? `<div class="u-p-qr"><img src="${ctx.root + ctx.byId['platform-login'].current}" alt="实机星阵扫码登录二维码"></div><div class="u-p-qr-side"><b>打开星阵 APP 扫一扫</b><p>扫码后在手机上点确认</p><div class="u-p-await">等待扫描</div><button type="button" class="u-p-btn u-p-secondary" data-help="设计预览：正式页面会重新获取星阵登录二维码。">换一张</button></div>` : `<div class="u-p-login-fields"><label><span class="u-p-field-caption">${ogs ? '用户名' : '手机号'}</span><span class="u-p-field">${ogs ? '' : `<select class="u-p-phone-area" aria-label="国家或地区区号">${areaOptions()}</select>`}<input aria-label="${ogs ? '用户名' : '手机号'}" placeholder="点此输入"></span></label><label><span class="u-p-field-caption">${sms ? '验证码' : '密码'}</span><span class="u-p-field"><input type="${sms ? 'text' : 'password'}" aria-label="${sms ? '验证码' : '密码'}" placeholder="点此输入"></span></label>${sms ? '<button type="button" class="u-p-btn u-p-secondary u-p-send-code" data-help="设计预览：正式页面会向手机号发送验证码。">获取验证码</button>' : ''}<button type="button" class="u-p-btn u-p-primary u-p-login-submit" data-help="设计预览：正式页面会验证账号并连接平台。">${title}</button></div>`}</div></div></div>`;
  };
  F['platform-login'] = (_s, ctx) => login(ctx, 'scan');
  F['platform-login-sms'] = (_s, ctx) => login(ctx, 'sms');
  F['platform-login-pw'] = (_s, ctx) => login(ctx, 'pw');
  F['platform-login-ogs'] = (_s, ctx) => login(ctx, 'ogs');

  const room = (ctx, kind) => {
    const isMatch = kind === 'match';
    const title = isMatch ? '快速匹配' : '房间';
    const active = kind === 'mine' ? 'mine' : kind === 'join' ? 'join' : 'create';
    const content = isMatch ? `<div class="u-p-match-head">匹配用时 · 可多选${help('至少选择一种用时；星阵完成匹配后才进入对局。')}</div><div class="u-p-time-grid">${[['快棋','1 分','15 秒 × 3'],['普通','10 分','30 秒 × 3'],['慢棋','30 分','40 秒 × 3']].map(x=>`<label class="u-p-time"><input type="checkbox" checked><strong>${x[0]}</strong><span>${x[1]}<br>${x[2]}</span></label>`).join('')}</div><div class="u-p-ai"><span>允许匹配 AI 对手</span><strong>暂不可用</strong>${help('AI 对手暂不可用，当前只匹配棋友。')}</div>` : `<div class="u-p-room-tabs"><button class="${active === 'create' ? 'is-active' : ''}" data-switch="golaxy-room-setup">创建房间</button><button class="${active === 'mine' ? 'is-active' : ''}" data-switch="golaxy-room-mine">我的房间</button><button class="${active === 'join' ? 'is-active' : ''}" data-switch="golaxy-room-join">加入房间</button></div><div class="u-p-room-content">${active === 'create' ? `<strong>创建星阵房间</strong><p>创建后在房间内设置对局</p><p class="u-p-room-risk">创建后与棋友确认对局规则</p>${help('创建后需等待另一位棋手加入，进入房间后双方确认对局规则。')}` : active === 'mine' ? `<strong>我的房间</strong><div class="u-p-room-empty">尚未接通我的房间</div>${help('此处显示星阵返回的当前账号所建房间，目前接口尚未接通。')}` : `<strong>加入星阵房间</strong><label>房间号<input aria-label="房间号" placeholder="请输入星阵房间号" inputmode="numeric"></label><p class="u-p-room-risk">按房号进入可能是观战身份，仍需确认可对弈席位</p>${help('加入房间后仍需确认对局身份和开局状态。')}`}</div>`;
    return `<div class="u-p-body u-p-setup">${bar(ctx, '返回星阵围棋', `${mark(ctx, 'golaxy')}${title}`)}<div class="u-p-setup-title"><strong>${title}</strong><span>${isMatch ? '落子位置与匹配用时在开局前设置' : '创建、找回或按房号进入星阵房间'}</span></div>${board(ctx)}<div class="u-p-setup-panel">${inputRows()}${content}<div class="u-p-setup-warning">星阵开局功能暂不可用${notes(isMatch)}</div><button class="u-p-btn u-p-disabled u-p-submit" type="button" disabled>${isMatch ? '开始匹配' : active === 'create' ? '创建房间' : active === 'mine' ? '打开我的房间' : '加入房间'} · 暂不可用</button></div></div>`;
  };
  F['platform-match'] = (_s, ctx) => room(ctx, 'match');
  F['platform-room'] = (_s, ctx) => room(ctx, 'create');
  F['golaxy-room-setup'] = (_s, ctx) => room(ctx, 'create');
  F['golaxy-room-mine'] = (_s, ctx) => room(ctx, 'mine');
  F['golaxy-room-join'] = (_s, ctx) => room(ctx, 'join');

  F['golaxy-home'] = (_s, ctx) => `<div class="u-p-body u-p-golaxy">${bar(ctx, '返回对弈', `${mark(ctx, 'golaxy')}星阵围棋`)}<div class="u-p-golaxy-state"><strong>星阵账号未连接</strong><p>连接后可使用星阵对弈与大厅</p><button type="button" class="u-p-btn u-p-primary" data-switch="platform-login">连接星阵</button></div></div>`;

  F['platform-lobby'] = (_s, ctx) => `<div class="u-p-body u-p-ogs">${bar(ctx, '返回对弈', `${mark(ctx, 'ogs')}OGS`, '尚未连接')}<div class="u-p-ogs-notice">OGS 尚未连接。请先连接账号。</div><div class="u-p-ogs-input">${inputRows()}<span>19 路</span>${help('实机截图显示实体盘落子；实体盘只下 19 路。')}</div>${section('开一局', '胜负记在 OGS 账上。快速匹配与发起挑战在盒上尚未接通；找人下可按用户名直接约战。')}<div class="u-p-ogs-cards">${card('快速匹配','users','暂未接通','','盒上尚未接通快速匹配。',true)}${card('发起挑战','list','暂未接通','','盒上尚未接通发起挑战。',true)}${card('找人下','search','按用户名约战','','按用户名直接约战；需先连接 OGS。')}</div>${section('公开挑战', '段位来自 OGS；连接 OGS 后可查看公开挑战。')}<div class="u-p-ogs-filter"><div class="u-p-ogs-filter-tabs"><input type="radio" name="u-p-ogs-filter" id="u-p-ogs-all" checked><label for="u-p-ogs-all">全部实时局</label><input type="radio" name="u-p-ogs-filter" id="u-p-ogs-19"><label for="u-p-ogs-19">19 路</label></div><input class="u-p-ogs-search" type="search" aria-label="搜索用户名" placeholder="搜索用户名"><button type="button" class="u-p-btn u-p-secondary" aria-label="刷新公开挑战" disabled>${icon('refresh')}</button></div><div class="u-p-ogs-empty">连接 OGS 后可查看公开挑战</div></div>`;
})();
