/* Isolated visual candidates; original artifact and production UI are untouched. */
(async () => {
  const cells = await (await fetch('captured-cells.json')).json();
  const frame = document.querySelector('iframe');
  const start = () => {
    const doc = frame.contentDocument;
    if (!doc?.querySelector('#stage')) return;
    const s = doc.createElement('style');
    s.textContent = `
      html,body{margin:0!important;padding:0!important;width:1024px!important;height:600px!important;overflow:hidden!important;background:#0d1415!important}
      .work-head,.compare-sidebar,.intro,.panel>h2,.design-note,.footer{display:none!important}
      .compare-layout,.compare-main,.compare-content,.panel,.stage-host{position:static!important;width:1024px!important;height:600px!important;max-width:none!important;margin:0!important;padding:0!important;border:0!important;border-radius:0!important;overflow:hidden!important}
      #stage{position:absolute!important;left:0!important;top:0!important;transform:none!important;width:1024px!important;height:600px!important}
      #stage .u-growth-calendar{height:227px;padding:8px 14px 9px;position:relative}
      #stage .cx-head{display:flex;align-items:center;height:44px;gap:16px;font-size:22px}
      #stage .cx-head>span{color:#74d395;font-size:28px;white-space:nowrap}
      #stage .cx-head .u-growth-info{margin-left:auto;flex:none}
      #stage .cx-plot{position:relative;margin-left:28px;width:604px}
      #stage .cx-months{position:relative;height:30px;color:#d0dfd0;font-size:18px;line-height:24px}
      #stage .cx-months span{position:absolute;white-space:nowrap;top:0}
      #stage .cx-grid{position:relative;height:79px;width:604px}
      #stage .cx-cell{position:absolute;border-radius:2px;background:#293a30;width:9.4px;height:9.4px}
      #stage .cx-cell.l1{background:#3b6d49}#stage .cx-cell.l2{background:#51915e}#stage .cx-cell.l3{background:#66b77b}#stage .cx-cell.l4{background:#83d99a}
      #stage .cx-cell.today{outline:1px solid #edf4e8;outline-offset:1px}
      #stage .cx-days{position:absolute;left:-28px;top:30px;width:22px;font-size:18px;color:#c4d6c4;line-height:18px}
      #stage .cx-days span{position:absolute;right:0}
      #stage .cx-foot{height:43px;display:flex;align-items:center;justify-content:space-between;font-size:18px;color:#bcd0bc;padding-left:28px}
      #stage .cx-legend{display:flex;gap:10px;align-items:center;white-space:nowrap}#stage .cx-key{display:flex;gap:4px;align-items:center}
      #stage .cx-legend i{display:block;width:12px;height:12px;background:#293a30;border-radius:2px}
      #stage .cx-key:nth-child(2) i{background:#3b6d49}#stage .cx-key:nth-child(3) i{background:#51915e}#stage .cx-key:nth-child(4) i{background:#66b77b}#stage .cx-key:nth-child(5) i{background:#83d99a}
      #stage .cx-2 .cx-head{height:40px}#stage .cx-2 .cx-months{height:24px}
      #stage .cx-2 .cx-grid{height:113px}#stage .cx-2 .cx-cell{height:13px}
      #stage .cx-2 .cx-days{top:24px}#stage .cx-2 .cx-foot{height:28px}
      #stage .cx-3 .cx-head{height:42px;gap:12px}#stage .cx-3 .cx-head .u-growth-info{margin-left:0}
      #stage .cx-pan{margin-left:auto;display:flex;gap:6px}
      #stage .cx-pan button{height:44px;width:44px;padding:10px;background:#284332;color:#daeadb;border:1px solid #55775c;border-radius:12px}
      #stage .cx-pan button:disabled{opacity:.4;cursor:default}#stage .cx-pan button svg{width:22px;height:22px;fill:none;stroke:currentColor;stroke-width:2;stroke-linecap:round;stroke-linejoin:round}
      #stage .cx-3 .cx-plot{overflow-x:auto;overflow-y:hidden;scrollbar-width:thin;scrollbar-color:#577c60 #15221a;height:140px}
      #stage .cx-3 .cx-plot::-webkit-scrollbar{height:4px}#stage .cx-3 .cx-plot::-webkit-scrollbar-thumb{background:#577c60;border-radius:3px}
      #stage .cx-3 .cx-months{width:898px;height:24px}#stage .cx-3 .cx-grid{width:898px;height:116px}
      #stage .cx-3 .cx-cell{width:14px;height:14px;border-radius:3px}#stage .cx-3 .cx-days{top:74px;left:14px}
      #stage .cx-3 .cx-foot{height:26px;padding-left:28px}
      #stage button:focus-visible{outline:2px solid #a8edb8;outline-offset:2px}
    `;
    doc.head.append(s);
    const update = () => {
      const cal = doc.querySelector('.u-growth-calendar');
      if (!cal || cal.dataset.candidate) return;
      cal.dataset.candidate = window.candidate;
      const n = window.candidate;
      cal.classList.add('cx-'+n);
      const help = cal.querySelector('.u-growth-info'); help.dataset.help = '每格一天，统计当天下完的对局与新解出的题。绿色越亮，完成越多。固定五档：0、1–2、3–5、6–9、10+；白框为实机采集当天。'; const info = help.outerHTML;
      const pitch = n===3 ? 17 : 11.4;
      const yp = n===2 ? 16.5 : pitch;
      const months = [['11月',2],['12月',7],['1月',11],['2月',15],['3月',19],['4月',24],['5月',28],['6月',33],['7月',37],['8月',41],['9月',46],['10月',50]];
      const dayLabels = n===1 ? [[0,'一'],[2,'三'],[4,'五']] : n===2 ? [[0,'一'],[2,'三'],[4,'五'],[6,'日']] : [[0,'一'],[2,'三'],[4,'五'],[6,'日']];
      const days = `<div class="cx-days" aria-hidden="true">${dayLabels.map(([r,t])=>`<span style="top:${r*yp-4}px">${t}</span>`).join('')}</div>`;
      const pan = n===3 ? `<div class="cx-pan"><button type="button" data-pan="-1" aria-label="查看较早月份"><svg viewBox="0 0 24 24"><path d="m14 5-7 7 7 7"/></svg></button><button type="button" data-pan="1" aria-label="查看较近月份"><svg viewBox="0 0 24 24"><path d="m10 5 7 7-7 7"/></svg></button></div>` : '';
      cal.innerHTML = `<div class="cx-head"><strong>近一年练棋</strong><span><span class="plex-num">17</span> 天</span>${pan}${info}</div><div class="cx-plot"><div class="cx-months" aria-hidden="true">${months.map(([m,c],i)=>`<span style="left:${(c + (months[i+1]?.[1] ?? 53) - 1) * pitch / 2}px;transform:translateX(-50%)">${m}</span>`).join('')}</div>${n!==3?days:''}<div class="cx-grid" role="img" aria-label="近一年17天有练棋记录，每列一周，从周一至周日；实机采集于2026年10月14日">${cells.filter(x=>x[2]>=0).map(([c,r,l])=>`<i class="cx-cell l${l} ${c===52&&r===2?'today':''}" style="left:${c*pitch}px;top:${r*yp}px"></i>`).join('')}</div></div>${n===3?days:''}<div class="cx-foot"><span>${n===3?'左右滑动查看全年':n===2?'每列一周 · 周一至周日':'每格一天'}</span><div class="cx-legend" aria-label="练棋次数由少至多">${['0','1–2','3–5','6–9','10+'].map(t=>`<span class="cx-key"><i></i><span>${t}</span></span>`).join('')}</div></div>`;
      // Use project numeral glyphs, including the visible month labels.
      frame.contentWindow.applyPlexNumerals?.(cal);
      if(n===3){const plot=cal.querySelector('.cx-plot');const buttons=cal.querySelectorAll('[data-pan]');const sync=()=>{buttons[0].disabled=plot.scrollLeft<2;buttons[1].disabled=plot.scrollLeft>=plot.scrollWidth-plot.clientWidth-2;};plot.scrollLeft=1000;buttons.forEach(b=>b.onclick=()=>plot.scrollBy({left:Number(b.dataset.pan)*294,behavior:'smooth'}));plot.addEventListener('scroll',sync);sync();}
    };
    new MutationObserver(update).observe(doc.querySelector('#stage'), {childList:true,subtree:true});
    update();
    document.documentElement.dataset.ready='true';
  };
  frame.addEventListener('load',start);
  if(frame.contentDocument?.readyState==='complete')start();
})();
