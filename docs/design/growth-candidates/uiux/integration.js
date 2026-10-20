/* Copy this inside the existing growth.js IIFE, before const calendar.
 * Then replace only calendar(root, byId) with () => growthCalendarCandidate(1).
 * The existing info() helper is reused. UIUX 1 or 2 needs no extra handlers. */
const growthCapturedActiveCells = [[25, 6, 1], [34, 5, 2], [36, 2, 1], [36, 4, 1], [38, 1, 1], [38, 2, 2], [45, 1, 1], [48, 0, 1], [50, 0, 2], [50, 1, 1], [50, 2, 1], [50, 3, 1], [51, 2, 1], [51, 4, 4], [51, 5, 2], [52, 0, 1], [52, 1, 2]];
const growthCalendarCandidate = (n = 1) => {
  const cells = Array.from({length:53*7}, (_, i) => {
    const c=Math.floor(i/7), r=i%7;
    const voidCell=(c===0 && r<2)||(c===52 && r>2);
    return [c,r,voidCell ? -1 : growthCapturedActiveCells.find(v=>v[0]===c && v[1]===r)?.[2] ?? 0];
  });
  const infoHTML = info('每格一天，统计当天下完的对局与新解出的题。绿色越亮，完成越多。固定五档：0、1–2、3–5、6–9、10+；白框为实机采集当天。', '近一年练棋说明');
      const pitch = n===3 ? 17 : 11.4;
      const yp = n===2 ? 16.5 : pitch;
      const months = [['11月',2],['12月',7],['1月',11],['2月',15],['3月',19],['4月',24],['5月',28],['6月',33],['7月',37],['8月',41],['9月',46],['10月',50]];
      const dayLabels = n===1 ? [[0,'一'],[2,'三'],[4,'五']] : n===2 ? [[0,'一'],[2,'三'],[4,'五'],[6,'日']] : [[0,'一'],[2,'三'],[4,'五'],[6,'日']];
      const days = `<div class="cx-days" aria-hidden="true">${dayLabels.map(([r,t])=>`<span style="top:${r*yp-4}px">${t}</span>`).join('')}</div>`;
      const pan = n===3 ? `<div class="cx-pan"><button type="button" data-pan="-1" aria-label="查看较早月份"><svg viewBox="0 0 24 24"><path d="m14 5-7 7 7 7"/></svg></button><button type="button" data-pan="1" aria-label="查看较近月份"><svg viewBox="0 0 24 24"><path d="m10 5 7 7-7 7"/></svg></button></div>` : '';
      return `<section class="u-growth-calendar cx-${n}" aria-label="近一年练棋日历">` + `<div class="cx-head"><strong>近一年练棋</strong><span><span class="plex-num">17</span> 天</span>${pan}${infoHTML}</div><div class="cx-plot"><div class="cx-months" aria-hidden="true">${months.map(([m,c],i)=>`<span style="left:${(c + (months[i+1]?.[1] ?? 53) - 1) * pitch / 2}px;transform:translateX(-50%)">${m}</span>`).join('')}</div>${n!==3?days:''}<div class="cx-grid" role="img" aria-label="近一年17天有练棋记录，每列一周，从周一至周日；实机采集于2026年10月14日">${cells.filter(x=>x[2]>=0).map(([c,r,l])=>`<i class="cx-cell l${l} ${c===52&&r===2?'today':''}" style="left:${c*pitch}px;top:${r*yp}px"></i>`).join('')}</div></div>${n===3?days:''}<div class="cx-foot"><span>${n===3?'左右滑动查看全年':n===2?'每列一周 · 周一至周日':'每格一天'}</span><div class="cx-legend" aria-label="练棋次数由少至多">${['0','1–2','3–5','6–9','10+'].map(t=>`<span class="cx-key"><i></i><span>${t}</span></span>`).join('')}</div></div>` + `</section>`;

};
