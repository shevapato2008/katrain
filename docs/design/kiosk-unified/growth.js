/* Growth design: one captured RK3562 state, with the same two-column geometry. */
(() => {
  const info = (copy, label = '查看说明') => `<button type="button" class="u-growth-info" aria-label="${label}" data-help="${copy}"><svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="M12 11v6m0-10h.01"/></svg></button>`;
  const stats = [
    ['21', '近 30 天对局'],
    ['24%', '胜率 · 近 30 天'],
    ['18', '累计已解题'],
    ['5', '升降级局 · 累计'],
  ];
  const pageState = () => typeof growthTab === 'string' && ['overview', 'practice', 'opponents'].includes(growthTab) ? growthTab : 'overview';
  // The 17 highlighted days and their color levels come from the captured device calendar.
  const capturedActiveDays = [[25, 6, 1], [34, 5, 2], [36, 2, 1], [36, 4, 1], [38, 1, 1], [38, 2, 2], [45, 1, 1], [48, 0, 1], [50, 0, 2], [50, 1, 1], [50, 2, 1], [50, 3, 1], [51, 2, 1], [51, 4, 4], [51, 5, 2], [52, 0, 1], [52, 1, 2]];
  const activeLevels = new Map(capturedActiveDays.map(([column, row, level]) => [`${column}:${row}`, level]));
  const months = [['11月', 2], ['12月', 7], ['1月', 11], ['2月', 15], ['3月', 19], ['4月', 24], ['5月', 28], ['6月', 33], ['7月', 37], ['8月', 41], ['9月', 46], ['10月', 50]];
  const calendar = () => `
    <section class="u-growth-calendar" aria-label="近一年练棋日历">
      <div class="u-growth-calendar-head"><strong>近一年练棋</strong><span><span class="kiosk-plex-num">17</span> 天</span>${info('每格一天，统计当天下完的对局与新解出的题。绿色越亮，完成越多。白框为实机采集当天。', '近一年练棋说明')}</div>
      <div class="u-growth-calendar-plot">
        <div class="u-growth-calendar-months" aria-hidden="true">${months.map(([label, column], index) => `<span style="left:${(column + (months[index + 1]?.[1] ?? 53) - 1) * 11.4 / 2}px">${label}</span>`).join('')}</div>
        <div class="u-growth-calendar-days" aria-hidden="true">${[[0, '一'], [2, '三'], [4, '五'], [6, '日']].map(([row, label]) => `<span style="top:${row * 16.5 - 4}px">${label}</span>`).join('')}</div>
        <div class="u-growth-calendar-grid" role="img" aria-label="近一年有17天练棋记录，每列一周，从周一至周日；白框表示2026年10月14日采集当天">${Array.from({length:53*7}, (_, index) => {
          const column = Math.floor(index / 7), row = index % 7;
          if ((column === 0 && row < 2) || (column === 52 && row > 2)) return '';
          const level = activeLevels.get(`${column}:${row}`) ?? 0;
          return `<i class="u-growth-calendar-cell level-${level}${column === 52 && row === 2 ? ' today' : ''}" style="left:${column * 11.4}px;top:${row * 16.5}px"></i>`;
        }).join('')}</div>
      </div>
      <div class="u-growth-calendar-footer"><span>每列一周 · 周一至周日</span><div class="u-growth-calendar-legend" aria-label="练棋次数由少至多">${['0', '1–2', '3–5', '6–9', '10+'].map((label, index) => `<span class="u-growth-calendar-key level-${index}"><i></i><span>${label}</span></span>`).join('')}</div></div>
    </section>`;
  const overview = (root, byId) => `
    <div class="u-growth-stats">${stats.map(([value, label]) => `<div class="u-growth-stat"><strong>${value}</strong><span>${label}</span></div>`).join('')}</div>
    <div class="u-growth-note">4 局未计入胜率 ${info('面对面的对局，以及当时没记下你执黑还是执白的对局，没有计入近 30 天胜率。', '胜率口径说明')}</div>
    ${calendar(root, byId)}`;
  const diagnosis = () => `
    <div class="u-growth-section-title"><strong>能力诊断</strong>${info('诊断只统计最近 3 份已完成报告中你执的那一方：共 278 手。问题手包括小亏、失误、恶手。样本还少时，结论会变化。', '能力诊断说明')}</div>
    <div class="u-growth-phase-list">
      ${[['布局', '24', '90', 27, false], ['中盘', '61', '135', 45, false], ['官子', '30', '53', 57, true]].map(([name, bad, total, width, weakest]) => `<div class="u-growth-phase"><div><strong>${name}${weakest ? ' · 最弱' : ''}</strong><span>问题手 ${bad} / ${total}</span></div><div class="u-growth-track"><i style="width:${width}%"></i></div></div>`).join('')}
    </div>
    <div class="u-growth-diagnosis-note">最近 3 份报告 · 你下的 278 手<br>另有 2 份没记执色，未计入诊断</div>`;
  const opponents = () => `
    <div class="u-growth-section-title"><strong>按对手强度</strong>${info('这里列出已计入的升降级对局，按对手当时的段位分组。开局设置里的强度调的是对手，不是你的段位。', '按对手强度说明')}</div>
    <div class="u-growth-opponents">
      ${[['2段', '0 胜', '1 负'], ['1级', '0 胜', '1 负'], ['2级', '0 胜', '1 负'], ['3级', '1 胜', '0 负'], ['6级', '1 胜', '0 负']].map(([rank, win, lose]) => `<div class="u-growth-opponent"><strong>${rank}</strong><span>${win}<i>·</i>${lose}</span></div>`).join('')}
    </div>`;
  const left = () => `
    <section class="u-growth-rank" aria-label="盒内段位">
      <div class="u-growth-rank-head"><strong>盒内段位</strong>${info('盒内段位由升降级对弈决定。当前为 2 级；净胜分达到正 3 升一档，达到负 3 降一档。', '盒内段位说明')}</div>
      <div class="u-growth-rank-value">2级</div>
      <div class="u-growth-net"><span>净胜分</span><strong>0 / 3</strong></div>
      <div class="u-growth-net-track"><i></i></div>
      <div class="u-growth-trend"><strong>近 30 天走势</strong><span>升降级对局不足两天，暂不连线</span></div>
      <div class="u-growth-rules-heading">升降的规矩</div>
      <div class="u-growth-rules">
        <div><span>1</span><strong>净胜 3 盘升一档</strong></div>
        <div><span>2</span><strong>净负 3 盘降一档</strong></div>
        <div><span>3</span><strong>下封 20 级 · 上封 超越人类</strong></div>
      </div>
      <div class="u-growth-rank-footer"><div><span>定级局</span><strong>已完成</strong></div><div><span>已解题</span><strong>18</strong></div></div>
    </section>`;
  window.KioskDesignFamilies = window.KioskDesignFamilies || {};
  window.KioskDesignFamilies.growth = (_s, { root, byId }) => {
    const tab = pageState();
    const tabs = [['overview', '概览'], ['practice', '能力诊断'], ['opponents', '对手']];
    return `<div class="u-growth-root">${left()}<section class="u-growth-right" aria-label="成长记录"><div class="u-growth-tabs" role="tablist">${tabs.map(([id, label]) => `<button type="button" role="tab" aria-selected="${tab === id}" class="${tab === id ? 'is-active' : ''}" data-growth="${id}">${label}</button>`).join('')}</div><div class="u-growth-tab-content" role="tabpanel">${tab === 'practice' ? diagnosis() : tab === 'opponents' ? opponents() : overview(root, byId)}</div></section></div>`;
  };
})();
