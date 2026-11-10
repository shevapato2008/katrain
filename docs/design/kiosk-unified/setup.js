/* Kiosk setup family. The board is the original 516 px device image; only the
   x=548, 460 px setup rail is redrawn. The proposal uses the maximum available
   time choice: untimed for free/local; 60 min + 3 x 30 s for ranked, where
   untimed is excluded. Source ranked default is byo-only (AiSetupPage). */
(() => {
  const family = window.KioskDesignFamilies = window.KioskDesignFamilies || {};

  const help = (detail) => `<button class="u-setup-info" type="button" aria-label="说明" data-help="${detail}"><svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="M12 11v6m0-10h.01"/></svg></button>`;
  const head = (label, detail) => `<div class="u-setup-section-head"><span>${label}</span>${help(detail)}</div>`;
  const optionSets = {
    '路数': ['19 路', '13 路', '9 路'],
    '规则': ['中国规则', '日本规则', 'AGA 规则', 'AI 赛规则'],
    '让子': ['倒贴', '分先', '让先', '自定贴目', ...Array.from({length: 8}, (_, i) => `让 ${i + 2} 子`)],
    '棋力': [...Array.from({length: 20}, (_, i) => `对手 ${20 - i} 级`), ...Array.from({length: 9}, (_, i) => `对手 ${i + 1} 段`)],
    '落子': ['实体盘', '屏幕'],
    '我执': ['执黑', '执白', '猜先'],
    '用时': ['不限时', '仅读秒30秒×3', ...[5, 10, 20, 30, 60].map(n => `${n}分+3×30秒`)],
    '落子音': ['开', '关']
  };
  const field = (label, value, state = '') => {
    const kind = state === 'input' ? 'input' : state === 'fixed' || state === 'stake' ? 'fixed' : 'select';
    const selected = label === '用时' && value.includes('u-setup-time-line') ? '60分+3×30秒' : value;
    const options = optionSets[label] || [selected];
    const control = kind === 'select' ? `<select class="u-setup-hit" aria-label="${label}">${options.map(item => `<option value="${item}"${item === selected ? ' selected' : ''}>${item}</option>`).join('')}</select><span class="u-setup-chevron" aria-hidden="true"></span>` : kind === 'input' ? `<input class="u-setup-name-input" aria-label="${label}" placeholder="输入姓名">` : '';
    return `<label class="u-setup-field ${state ? `u-setup-${state}` : ''} u-setup-${kind}"><span class="u-setup-field-label">${label}</span>${kind === 'input' ? '' : `<strong class="u-setup-field-value">${value}</strong>`}${control}</label>`;
  };
  const row = (items, extra = '') => `<div class="u-setup-row ${extra}">${items.join('')}</div>`;
  const rankedClock = '<span class="u-setup-time-line">60 分</span><span class="u-setup-time-line">+ 30 秒×3</span>';
  const gameHelp = '路数、规则、让子在开局前确定；贴目由规则和让子推导。开局后不可更改。中国规则数子，当前分先为黑贴 7.5 目。';
  const localHelp = '两人下棋前请谈妥路数、规则、让子和贴目。黑方先行，贴目由黑方给白方。开局后不可更改。';
  const seatHelp = '实体盘和屏幕都可落子；实体盘仅支持已标定的 19 路。选好落子、执子和用时后开始对局。';
  const localSeatHelp = '实体盘时双方在各自一侧确认；屏幕落子时直接点棋盘。钟在玩家卡上倒数，读秒用完判超时负；不限时就只记谱。屏上不提示形势；双方各停一手后自动数子，死活由引擎判断。只留档、不动段位；中途退出不存谱。';

  function frame(title, subtitle, backTo, backId, body, action, ctx) {
    const { I } = ctx;
    return `<div class="u-setup-cover"></div><div class="u-setup-rail">
      <div class="u-setup-page-head"><button class="u-setup-back" type="button" data-switch="${backId}">${I('back')}<span>${backTo}</span></button><div class="u-setup-page-name"><strong>${title}</strong><span>${subtitle}</span></div></div>
      <div class="u-setup-content">${body}</div>
      <button class="u-setup-start" type="button">${I('playbtn')}<span>${action}</span></button>
    </div>`;
  }

  function commonGame(detail, fixed = false) {
    return `<section class="u-setup-group">${head(fixed ? '盒子定好的' : '这局棋', detail)}
      ${row([field('路数', '19 路', fixed ? 'fixed' : ''), field('规则', '中国规则', fixed ? 'fixed' : ''), field('让子', '分先', fixed ? 'fixed' : '')])}
      ${row([field('贴目', '黑贴7.5目', 'fixed')], 'u-setup-komi-row')}
    </section>`;
  }

  function free(ctx) {
    const body = `${commonGame(gameHelp)}
      <section class="u-setup-group">${head('对手', '拟人对手目前为第 15 档、6 级；共 29 档，范围为 20k 到 9d。档位是对手的强度，不是你的段位。自由对弈不计入段位。')}
        ${row([field('棋力', '对手 6 级')], 'u-setup-opponent-row')}
      </section>
      <section class="u-setup-group">${head('怎么坐', seatHelp)}
        ${row([field('落子', '实体盘'), field('我执', '执黑'), field('用时', '不限时')], 'u-setup-seat-row')}
      </section>`;
    return frame('自由对弈', '不计入段位', '返回对弈', 'play', body, '开始对局', ctx);
  }

  function ranked(ctx) {
    const body = `<section class="u-setup-group">${head('盒子定好的', '升降级对弈固定为 19 路、中国规则、分先和黑贴 7.5 目。你是 2 级，配到第 19 档；当前对手为 2 级。此局计入段位，全程封分析；开局后不能改。')}
        ${row([field('路数', '19 路', 'fixed'), field('规则', '中国规则', 'fixed'), field('让子', '分先', 'fixed')])}
        ${row([field('贴目', '黑贴7.5目', 'fixed'), field('对手', '2 级', 'fixed'), field('当前段位', '2 级', 'fixed')], 'u-setup-rank-row')}
      </section>
      <section class="u-setup-group">${head('怎么坐', seatHelp)}
        ${row([field('落子', '实体盘'), field('我执', '执黑'), field('用时', rankedClock)], 'u-setup-seat-row')}
      </section>
      <section class="u-setup-group">${head('这一局赌多少', '赢得净胜分 +1，输为 −1；净胜分到 +3 升一档，到 −3 退一档。开局那一刻冻结，当前净胜分为 0。')}
        ${row([field('赢', '+1 分', 'stake'), field('输', '−1 分', 'stake')], 'u-setup-double-row u-setup-stake-row')}
      </section>`;
    return frame('升降级对弈', '已认证 · 服务器对弈', '返回对弈', 'play', body, '开始计分局', ctx);
  }

  function local(ctx) {
    const body = `${commonGame(localHelp)}
      <section class="u-setup-group">${head('对局双方', '黑方先行、白方后行。姓名会写进棋谱；留空时分别记作「黑方」和「白方」，不编造名字。')}
        ${row([field('黑方 · 先行', '点此输入', 'input'), field('白方 · 后行', '点此输入', 'input')], 'u-setup-double-row u-setup-players-row')}
      </section>
      <section class="u-setup-group">${head('怎么坐', localSeatHelp)}
        ${row([field('落子', '实体盘'), field('用时', '不限时'), field('落子音', '开')], 'u-setup-seat-row')}
      </section>`;
    return frame('本地对局', '两人面对面', '返回对弈', 'play', body, '开始对局', ctx);
  }

  function platform(ctx) {
    const body = `<section class="u-setup-group">${head('这局棋', '星阵围棋人机对局固定 19 路与中国规则。让子可选，贴目随让子确定。此局不计入盒内段位；开局后不可更改。')}
        ${row([field('路数', '19 路', 'fixed'), field('规则', '中国规则', 'fixed'), field('让子', '分先')])}
        ${row([field('贴目', '黑贴7.5目', 'fixed')], 'u-setup-komi-row')}
      </section>
      <section class="u-setup-group">${head('对手', '星阵下发 39 档棋力，开局前可选择。当前为星小蚊 · 18 级，第 1 / 39 档，展示 Elo −600；对标业余 18 级。')}
        <button class="u-setup-engine-plate" type="button" aria-label="选择星阵人机对手，当前星小蚊 18 级" data-help="设计预览：星阵连接后可展开 39 档棋力。实机截图只采集到当前第 1 档，完整名单由星阵提供。"><span class="u-setup-engine-mark">星</span><span class="u-setup-engine-name"><strong>星小蚊 · 18 级</strong><span>展示 Elo −600 · 第 1 / 39 档</span></span><span class="u-setup-engine-chevron" aria-hidden="true"></span></button>
      </section>
      <section class="u-setup-group">${head('怎么坐', '可选择屏幕或已标定的实体盘落子；执黑、执白或猜先。星阵人机固定 19 路、中国规则，屏幕和实体盘走同一条隧道。')}
        ${row([field('落子', '实体盘'), field('我执', '猜先')], 'u-setup-double-row u-setup-platform-seat')}
      </section>`;
    return frame('星阵围棋 · 人机', '不计入盒内段位', '返回星阵', 'golaxy-home', body, '开始对局', ctx);
  }

  family['setup-free'] = (_s, ctx) => free(ctx);
  family['setup-ranked'] = (_s, ctx) => ranked(ctx);
  family['setup-local'] = (_s, ctx) => local(ctx);
  family['platform-engine'] = (_s, ctx) => platform(ctx);
  document.addEventListener('change', (event) => {
    const select = event.target.closest?.('.u-setup-hit');
    if (!select) return;
    const display = select.closest('.u-setup-field').querySelector('.u-setup-field-value');
    display.textContent = select.value;
  });
})();
