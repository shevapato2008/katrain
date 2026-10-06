/* Isolated design prototype. Business records are read-only snapshots of 24171.
 * This file is embedded into the HTML; it is not imported by either product build.
 * Statistics retain moveGrade.ts phase boundaries, denominators and per-side limits.
 */
(() => {
  const data = JSON.parse(document.getElementById('preview-data').textContent);
  const album = data.album, rows = data.analysis.moves;
  const byMove = Object.fromEntries(rows.map(r => [r.move_number, r]));
  const query = new URLSearchParams(location.search);
  const kiosk = () => matchMedia('(max-width:1100px)').matches;
  const $ = s => document.querySelector(s), $$ = s => [...document.querySelectorAll(s)];
  const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const icon = id => `<svg class="icon" aria-hidden="true"><use href="#i-${id}"/></svg>`;
  const letters = 'ABCDEFGHJKLMNOPQRST';
  const total = data.analysis.total_moves;
  const state = { cursor: Math.min(total, Math.max(0, Number(query.get('move') ?? 133))), tab:query.get('tab') || 'trend', phase:'all', player:'both', view:'stats', mode:query.get('mode') || 'professional', coordinates:true, numbers:false, advice:true, territory:false, try:false, view3d:false, pv:null, tryMoves:[], playing:false, selected:null };
  const tabs = [['trend','走势'],['brilliant','妙手'],['mistake','失误'],['grade','发挥水准'],['match','AI吻合度']];
  const tiers = [['brilliant','妙手','#3FA2E8'],['best','最佳','#2E8B57'],['very_good','很好','#4DBE46'],['playable','尚可','#A4B436'],['inaccuracy','小亏','#D6A318'],['mistake','失误','#CF6B09'],['blunder','恶手','#BB2121']];
  const tierMap = Object.fromEntries(tiers.map(t => [t[0],t]));
  const phaseOf = n => n < 60 ? 'opening' : n < 150 ? 'midgame' : 'endgame';
  const rated = () => rows.filter(r => r.move_number > 0 && (state.phase==='all' || phaseOf(r.move_number)===state.phase));
  const pct = n => n==null ? '—' : `${(100*n).toFixed(1)}%`;
  const signed = n => n==null ? '—' : `${n>=0?'+':''}${n.toFixed(1)}`;
  const side = () => state.cursor%2===0?'B':'W';
  const current = () => byMove[state.cursor];
  const candidates = () => current()?.top_moves?.slice(0,5) ?? [];
  const played = () => byMove[state.cursor+1]?.actual_move;
  const setText = (selector,text) => $$(selector).forEach(e=>e.textContent=text);
  const button = (label,action,ic,active,disabled=false) => `<button type="button" class="tool-btn" data-action="${action}" ${active==null?'':`aria-pressed="${active}"`} ${disabled?'disabled':''}>${icon(ic)}<span>${label}</span></button>`;
  const boardImage = new Image(), blackImage = new Image(), whiteImage = new Image();
  boardImage.src='../../katrain/img/board.png'; blackImage.src='../../katrain/img/B_stone.png'; whiteImage.src='../../katrain/img/W_stone.png';
  [boardImage,blackImage,whiteImage].forEach(im=>im.onload=()=>drawBoard());
  const coord = move => !move || move==='pass' ? null : [letters.indexOf(move[0]),19-Number(move.slice(1))];
  // Replay real SGF stones with captures. No decorative or invented board position.
  function position() {
    const board = Array(361).fill(null);
    const neighbors = n => [n%19? n-1:-1,n%19<18?n+1:-1,n>=19?n-19:-1,n<342?n+19:-1].filter(n=>n>=0);
    function group(start) { const seen=new Set([start]),stack=[start]; let liberty=false; while(stack.length) {const n=stack.pop(); for(const a of neighbors(n)) {if(board[a]==null)liberty=true;else if(board[a]===board[start]&&!seen.has(a)){seen.add(a);stack.push(a);}}} return {seen,liberty}; }
    const moves=rows.filter(r=>r.move_number>0&&r.move_number<=state.cursor).map(r=>({move:r.actual_move,color:r.actual_player,number:r.move_number}));
    if(state.pv!==null) for(const [i,move] of (candidates()[state.pv]?.pv ?? []).slice(0,6).entries()) moves.push({move,color:(state.cursor+i)%2===0?'B':'W',number:i+1,pv:true});
    for(const [i,move] of state.tryMoves.entries()) moves.push({move,color:(state.cursor+i)%2===0?'B':'W',number:i+1,pv:true});
    const records = new Map();
    for(const r of moves){const p=coord(r.move); if(!p||p.some(n=>n<0||n>18))continue;const n=p[1]*19+p[0];board[n]=r.color;records.set(n,r);for(const a of neighbors(n)){if(board[a]&&board[a]!==r.color){const g=group(a);if(!g.liberty)g.seen.forEach(k=>{board[k]=null;records.delete(k);});}}}
    return {board,records};
  }
  function drawBoard() {
    const canvas=$('#board'), rect=canvas.getBoundingClientRect(); if(!rect.width)return;
    const size=rect.width,dpr=devicePixelRatio||1;canvas.width=size*dpr;canvas.height=size*dpr;
    const c=canvas.getContext('2d');c.scale(dpr,dpr);
    const step=kiosk()?size/19:Math.floor(size/21), offset=(size-step*18)/2;
    if(boardImage.complete&&boardImage.naturalWidth)c.drawImage(boardImage,0,0,size,size);else{c.fillStyle='#dcb35c';c.fillRect(0,0,size,size);}
    c.strokeStyle='#382c19';c.lineWidth=1;for(let i=0;i<19;i++){const p=offset+i*step;c.beginPath();c.moveTo(offset,p);c.lineTo(offset+18*step,p);c.moveTo(p,offset);c.lineTo(p,offset+18*step);c.stroke();}
    c.fillStyle='#332a1d';for(const x of [3,9,15])for(const y of [3,9,15]){c.beginPath();c.arc(offset+x*step,offset+y*step,step*.10,0,Math.PI*2);c.fill();}
    if(!kiosk()&&state.coordinates){c.fillStyle='#594527';c.font=`600 ${Math.floor(step*.45)}px "IBM Plex Mono",monospace`;c.textAlign='center';c.textBaseline='middle';for(let i=0;i<19;i++){const p=offset+i*step;c.fillText(letters[i],p,offset-step*.67);c.fillText(letters[i],p,offset+18.67*step);c.fillText(19-i,offset-step*.67,p);c.fillText(19-i,offset+18.67*step,p);}}
    const pos=position();pos.board.forEach((color,n)=>{if(!color)return;const r=pos.records.get(n),x=offset+n%19*step,y=offset+Math.floor(n/19)*step,im=color==='B'?blackImage:whiteImage,rad=step*.505;c.globalAlpha=r.pv?.72:1;if(im.complete&&im.naturalWidth)c.drawImage(im,x-rad,y-rad,rad*2,rad*2);else{c.fillStyle=color==='B'?'#090909':'#f2efea';c.beginPath();c.arc(x,y,rad,0,7);c.fill();}c.globalAlpha=1;if(state.numbers||r.pv){c.fillStyle=color==='B'?'#fff':'#111';c.font=`600 ${step*.43}px sans-serif`;c.textAlign='center';c.textBaseline='middle';c.fillText(r.number,x,y);}});
    const last=coord(current()?.actual_move);if(last){c.beginPath();c.arc(offset+last[0]*step,offset+last[1]*step,step*.35,0,7);c.strokeStyle=side()==='W'?'#f3f3f3':'#171717';c.lineWidth=3;c.stroke();}
    if(state.advice&&state.pv===null)candidates().forEach((m,i)=>{const p=coord(m.move);if(!p)return;const x=offset+p[0]*step,y=offset+p[1]*step;c.fillStyle='rgba(67,132,87,.77)';c.beginPath();c.arc(x,y,step*.44,0,7);c.fill();if(i===0){c.strokeStyle='#edf6eb';c.lineWidth=2;c.stroke();}c.fillStyle='#fff';c.textAlign='center';c.textBaseline='middle';c.font=`600 ${Math.max(10,step*.28)}px sans-serif`;c.fillText(((side()==='B'?m.winrate:1-m.winrate)*100).toFixed(1),x,y-step*.12);c.font=`600 ${Math.max(9,step*.24)}px sans-serif`;c.fillText(m.visits>=1000?`${(m.visits/1000).toFixed(1)}k`:m.visits,x,y+step*.18);});
  }
  function candidateHtml(isKiosk) {
    const all=current()?.top_moves??[],sum=all.reduce((s,m)=>s+(m.psv||0),0), visits=all.reduce((s,m)=>s+(m.visits||0),0), actual=played();
    const list=candidates().map(m=>({...m,isActual:m.move===actual}));
    if(actual&&!list.some(m=>m.move===actual)) list.push({...all.find(m=>m.move===actual),move:actual,isActual:true,extra:true});
    return list.map((m,i)=>{
      const lead=m.score_lead==null?null:(side()==='B'?m.score_lead:-m.score_lead),win=m.winrate==null?null:(side()==='B'?m.winrate:1-m.winrate);
      const share=m.psv==null?null:sum?(m.psv/sum*100):visits?(m.visits/visits*100):null;
      const name=`${m.extra?'<small class="actual-tag">实战</small>':''}${esc(m.move)}${m.isActual&&!m.extra?'<span class="actual-mark" title="实战着点">✓</span>':''}`;
      if(isKiosk) return `<button class="k-row ${m.extra?'extra-actual':''}" data-candidate="${i}" ${m.extra?'data-actual':''} aria-label="${m.extra?'实战着点':'推荐着点'} ${esc(m.move)}"><span>${name}</span><b>${share==null?'—':`${share.toFixed(0)}%`}</b><b>${signed(lead)}</b><b>${pct(win)}</b></button>`;
      return `<button class="rec-grid rec-row ${m.extra?'extra-actual':''}" data-candidate="${i}" ${m.extra?'data-actual':''} aria-label="${m.extra?'实战着点':'推荐着点'} ${esc(m.move)}"><span class="rec-move"><i class="stone-key ${side()==='W'?'white':''}"></i>${name}</span><span>${share==null?'—':`<b class="chip">${share.toFixed(0)}%</b>`}</span><span>${lead==null?'—':`<b class="score-chip ${side()==='W'?'white-score':''}">${signed(lead)}</b>`}</span><span class="win-chips">${win==null?'—':`<b class="${side()==='W'?'other':''}">${(win*100).toFixed(1)}</b><b class="${side()==='B'?'other':''}">${((1-win)*100).toFixed(1)}</b>`}</span></button>`;
    }).join('');
  }
  function renderCandidates() { for(const [id,k] of [['desktopCandidates',false],['kioskCandidates',true]]){const list=$('#'+id),scroll=list.scrollTop;list.innerHTML=candidateHtml(k);list.scrollTop=scroll;} $('#actualComparison').classList.remove('visible'); }
  function renderMeta() {
    const r=current(),title=album.display_event||album.event,black=album.display_player_black||album.player_black,white=album.display_player_white||album.player_white;
    const lead=r?Math.abs(r.score_lead)<.05?'形势均衡':`${r.score_lead>0?'黑':'白'}领先 ${Math.abs(r.score_lead).toFixed(1)} 目`:'—';
    setText('[data-title],[data-k-title]',state.mode==='personal'?'导入的棋谱':title);
    setText('[data-date]',album.date_played);setText('[data-k-date]',`${state.cursor} / ${total} 手`);
    setText('[data-black-name]',black);setText('[data-white-name]',white);setText('[data-k-black]',`○ ${black}`);setText('[data-k-white]',`${white} ●`);
    setText('[data-lead],[data-k-lead]',lead);setText('[data-black-rate],[data-k-black-rate]',`黑 ${pct(r?.winrate)}`);setText('[data-white-rate],[data-k-white-rate]',`白 ${pct(r?1-r.winrate:null)}`);
    $$('[data-win-fill],[data-k-win-fill]').forEach(e=>e.style.width=`${(r?.winrate??.5)*100}%`);
    setText('[data-result]','黑胜中盘');setText('[data-rule]',album.rules?`${album.rules} · 贴目 ${album.komi}`:'规则待核验 · SGF贴目 6.5');
    setText('[data-k-result]','黑胜中盘');setText('[data-k-rule]','规则待核验 · 贴目 6.5');
    setText('[data-rec-title]',`AI推荐 · ${side()==='B'?'黑':'白'}方待落子`);setText('[data-rec-after]',`第 ${state.cursor} 手后`);setText('[data-k-rec-color]',`${side()==='B'?'黑':'白'} · 着点`);
    $('#kBack').textContent=state.mode==='professional'?'← 棋谱':'← 复盘';
    $$('[data-professional-nav]').forEach(e=>e.classList.toggle('active',state.mode==='professional'));$$('[data-personal-nav]').forEach(e=>e.classList.toggle('active',state.mode==='personal'));
    const details=[['日期',album.date_played],['赛事／标题',title],['黑方',black],['白方',white],['结果','黑胜中盘'],['SGF规则','未注明（缺少RU）'],['SGF贴目',`${album.komi} 目`],['分析参数','中国规则（默认值）／6.5 目'],['核验状态','比赛实际规则及贴目待核验'],['来源',state.mode==='professional'?'职业棋谱':'导入的棋谱'],['报告类型','深度报告'],['每局面 visits',2000]];
    $('#detailsRows').innerHTML=details.map(([k,v])=>`<div><dt>${esc(k)}</dt><dd>${esc(v)}</dd></div>`).join('');
  }
  function renderControls() {
    $('#desktopEntry').innerHTML='';
    $('#desktopControlsA').innerHTML=button('试下','try','hand',state.try)+button('领地','territory','territory',state.territory)+button('支招','advice','advice',state.advice)+button('清空','clear','close',null,!state.tryMoves.length&&!state.pv);
    $('#desktopControlsB').className='control-row four display-group';
    $('#desktopControlsB').innerHTML=button('手数','numbers','numbers',state.numbers)+button('坐标','coordinates','coord',state.coordinates)+button('3D','3d','3d',state.view3d);
    $('#kioskActions').innerHTML=button('试下','try','hand',state.try)+button('领地','territory','territory',state.territory)+button('支招','advice','advice',state.advice)+button('分析','openAnalysis','review',null);
    $('#kioskToggles').innerHTML=button('手数','numbers','numbers',state.numbers)+button('坐标','coordinates','coord',state.coordinates)+button('清空','clear','close',null,!state.tryMoves.length)+button('详情','details','review',null);
  }
  function renderPlayback() {
    const nav=[['first','first','到第一手'],['prev','prev','上一手'],[state.playing?'pause':'play','play',state.playing?'暂停':'播放'],['next','next','下一手'],['last','last','到最后一手']].map(([ic,a,l])=>`<button data-action="${a}" class="${a==='play'?'play':''}" aria-label="${l}" ${(['first','prev'].includes(a)&&!state.cursor)||(['next','last'].includes(a)&&state.cursor===total)?'disabled':''}>${icon(ic)}</button>`).join('');
    const range=`<input type="range" min="0" max="${total}" value="${state.cursor}" data-slider aria-label="手数进度"><output>${state.cursor} / ${total} 手</output>`;
    $('#desktopPlayback').innerHTML=`<div class="nav">${nav}</div>${range}`;$('#kioskPlayback').innerHTML=nav+range;
  }
  function segment(options,selected,kind){return `<div class="seg">${options.map(([v,l])=>`<button data-${kind}="${v}" aria-pressed="${selected===v}">${l}</button>`).join('')}</div>`;}
  function filters() {
    if(state.tab==='trend')return '';
    const phases=segment([['all','全盘'],['opening','布局'],['midgame','中盘'],['endgame','官子']],state.phase,'phase');
    const players=['brilliant','mistake'].includes(state.tab)&&!kiosk()?segment([['both','双方'],['B','黑方'],['W','白方']],state.player,'player'):'';
    const views=state.tab==='match'?segment([['stats','统计'],['dist','分布']],state.view,'view'):'';
    return `<nav class="chart-filters" aria-label="图表筛选">${phases}${players}${views}</nav>`;
  }
  function chartMetrics(place) {
    const body=$(`#${place}AnalysisBody`), w=Math.floor(body.clientWidth-24-(state.tab==='trend'?0:(kiosk()?76:innerWidth<=1535?72:88))),h=Math.floor(body.clientHeight-16-(state.tab==='trend'?28:0));
    return {w:Math.max(230,w),h:Math.max(150,h)};
  }
  const svgText=(x,y,text,fill='#c8c5bf',anchor='start',size=13)=>`<text x="${x}" y="${y}" fill="${fill}" text-anchor="${anchor}" font-size="${size}">${esc(text)}</text>`;
  function svg(w,h,content,label,extra='') { return `<svg viewBox="0 0 ${w} ${h}" class="chart-svg" role="img" aria-label="${esc(label)}" ${extra}>${content}</svg>`; }
  function trend(w,h) {
    const left=42,right=w-38,top=22,bottom=h-26,x=n=>left+n/total*(right-left),y=n=>bottom-n*(bottom-top)/100;
    const limit=Math.max(10,Math.ceil(Math.max(...rows.map(r=>Math.abs(r.score_lead)))/10)*10),ys=n=>(top+bottom)/2-n/limit*(bottom-top)/2;
    let s='';for(const n of [0,50,100]){s+=`<path d="M${left} ${y(n)}H${right}" stroke="#464642" stroke-dasharray="${n===50?'3 4':'0'}"/>`+svgText(left-8,y(n)+4,`${n}%`,'#8cd789','end')+svgText(right+8,ys((n-50)/50*limit)+4,n===50?'0':`${n===100?'+':'−'}${limit}`,'#f7b14b');}
    s+=`<polyline points="${rows.map(r=>`${x(r.move_number)},${y(r.winrate*100)}`).join(' ')}" fill="none" stroke="#77cb78" stroke-width="1.8"/><polyline points="${rows.map(r=>`${x(r.move_number)},${ys(r.score_lead)}`).join(' ')}" fill="none" stroke="#edab47" stroke-width="1.8"/><line x1="${x(state.cursor)}" x2="${x(state.cursor)}" y1="${top}" y2="${bottom}" stroke="#e4e3da" opacity=".55"/>`;
    for(const n of [0,50,100,150,total])s+=svgText(x(n),h-6,n,'#b8b5b0','middle',12);
    return svg(w,h,s,'黑棋胜率与黑棋领先目，点击曲线跳转手数','data-trend-chart');
  }
  function selectedMoves() {
    let eligible=rated().filter(r=>(state.tab==='brilliant'?r.grade==='brilliant':['inaccuracy','mistake','blunder'].includes(r.grade))&&(state.player==='both'||r.actual_player===state.player));
    const rank=r=>state.tab==='brilliant'?(r.brilliance??1)*1000+(1-(r.top_prior??1))*100:(r.points_lost??-r.delta_score);
    const shown=['B','W'].flatMap(c=>eligible.filter(r=>r.actual_player===c).sort((a,b)=>rank(b)-rank(a)).slice(0,5)).sort((a,b)=>a.move_number-b.move_number);
    return {shown,total:eligible.length,truncated:eligible.length-shown.length};
  }
  function lollipop(w,h) {
    const points=selectedMoves().shown,br=state.tab==='brilliant',max=br?5:Math.max(3,Math.ceil(Math.max(...points.map(p=>p.points_lost??0),0)/3)*3),left=42,right=w-18,top=32,bottom=h-28,mid=(top+bottom)/2,arm=(bottom-top)/2;
    let s=`<path d="M${left} ${mid}H${right}" stroke="#85827b"/>`;
    for(const n of br?[1,3,5]:[max/3,max*2/3,max])for(const sign of [-1,1]){const y=mid+sign*n/max*arm;s+=`<path d="M${left} ${y}H${right}" stroke="#282b27"/>`+svgText(left-8,y+4,n,'#b8b5b0','end',12);}
    s+=svgText(left,17,'○ 黑','#dedbd4','start',13)+svgText(right,17,br?'妙度 1–5':'目损（目）','#c6c3bd','end',13)+svgText(left,bottom-2,'● 白','#dedbd4','start',13);
    const labelLocations=[];
    for(const r of points){const value=br?r.brilliance??1:r.points_lost??0,x=left+r.move_number/total*(right-left),y=mid+(r.actual_player==='B'?-1:1)*value/max*arm;
      let lx=x,ly=Math.max(28,Math.min(h-32,y+(r.actual_player==='B'?-11:18)));
      const placements=[0,-14,14,-28,28,-42,42].map(d=>({x,y:ly+d}));
      const free=placements.find(p=>p.y>=28&&p.y<=h-32&&(p.y<=y-9||p.y>=y+16)&&!labelLocations.some(q=>Math.abs(q.x-p.x)<24&&Math.abs(q.y-p.y)<14));
      if(free){lx=free.x;ly=free.y;}else{lx=Math.max(left+12,Math.min(right-12,x+18));}
      labelLocations.push({x:lx,y:ly});
      s+=`<g data-move="${r.move_number}" style="cursor:pointer"><circle cx="${x}" cy="${y}" r="16" fill="transparent"/><path d="M${x} ${mid}V${y}" stroke="${tierMap[r.grade]?.[2]??'#777'}" stroke-width="2"/><circle cx="${x}" cy="${y}" r="5" fill="${r.actual_player==='B'?'#0d0d0d':'#f2efea'}" stroke="#dad8ce" stroke-width="1.5"/>${svgText(lx,ly,r.move_number,'#e7e4de','middle',12)}<title>第 ${r.move_number} 手 ${r.actual_move} · ${br?'妙度':'目损'} ${value}</title></g>`;
    }
    const cx=left+state.cursor/total*(right-left);s+=`<path d="M${cx} ${top}V${bottom}" stroke="#99958e" stroke-dasharray="3 4" opacity=".5"/>`+(w<320?'':svgText(cx,17,`第 ${state.cursor} 手`,'#ccc8bf','middle',12));
    for(const n of [0,50,100,150,total])s+=svgText(left+n/total*(right-left),h-6,n,'#b8b5b0','middle',12);
    if(!points.length)s+=svgText((left+right)/2,mid-12,br?'本阶段暂无妙手':'本阶段暂无失误','#c8c5bf','middle',14);
    return svg(w,h,s,'黑方在横轴上方，白方在横轴下方；点击着手跳转');
  }
  function histogram(w,h) {
    const rr=rated().filter(r=>r.grade&&r.grade!=='unrated'),b=rr.filter(r=>r.actual_player==='B').length,wh=rr.filter(r=>r.actual_player==='W').length;
    const compact=w<320;
    const left=32,right=w-10,top=36,bottom=h-(compact?60:50),space=(right-left)/7,bar=Math.min(24,space*.25),counts=tiers.map(t=>[rr.filter(r=>r.grade===t[0]&&r.actual_player==='B').length,rr.filter(r=>r.grade===t[0]&&r.actual_player==='W').length]);
    const max=Math.max(.6,Math.ceil(Math.max(...counts.map(a=>Math.max(b?a[0]/b:0,wh?a[1]/wh:0)))*5)/5),y=v=>bottom-v/max*(bottom-top);
    let s=compact?'':svgText(w-12,18,`黑 ${b} 手／白 ${wh} 手`,'#c8c5bf','end',12);
    for(let i=0;i<4;i++){const n=max*i/3;s+=`<path d="M${left} ${y(n)}H${right}" stroke="#30312d"/>`+svgText(left-7,y(n)+4,`${Math.round(n*100)}%`,'#b8b5b0','end',12);}
    tiers.forEach((t,i)=>{const center=left+(i+.5)*space,a=counts[i],br=b?a[0]/b:0,wr=wh?a[1]/wh:0;
      for(const [j,v] of [br,wr].entries()){const x=center+(j===0?-bar-2:2);s+=`<rect x="${x}" y="${y(v)}" width="${bar}" height="${bottom-y(v)}" rx="2" fill="${j?'#f2efea':'#0d0d0d'}" stroke="#d3d0c8" stroke-width="${j?0:1.3}"/>`+svgText(x+bar/2,Math.max(top-8,y(v)-7),a[j]||'', '#e4e1da','middle',12);}
      s+=svgText(center,bottom+18,t[1],'#e1ded7','middle',compact?11:13)+`<path d="M${center-space*.28} ${bottom+26}h${space*.56}" stroke="${t[2]}" stroke-width="2.5"/>`+(compact?svgText(center,bottom+39,`${Math.round(br*100)}%`,'#c8c5bf','middle',10)+svgText(center,bottom+52,`${Math.round(wr*100)}%`,'#e4e1da','middle',10):svgText(center,bottom+41,`${Math.round(br*100)}/${Math.round(wr*100)}%`,'#b8b5b0','middle',11));
    });
    s+=svgText(left+5,18,'○ 黑　● 白','#e4e1da','start',12);
    return svg(w,h,s,'七档着手评级，黑白各自归一化；柱顶为手数');
  }
  function matchStats(w,h) {
    const rr=rated(),labels=['走中 AI 一选','走进 AI 前三','不在 AI 前十选'],colors=['#7acd9c','#8bdb7c','#edab47'];
    const stats=labels.map(()=>({B:[0,0],W:[0,0]}));
    for(const r of rr){const cs=byMove[r.move_number-1]?.top_moves??[],rank=cs.findIndex(m=>m.move===r.actual_move),top1=r.is_top_move??(cs.length?rank===0:null),c=r.actual_player;if(!stats[0][c]||top1==null)continue;stats[0][c][1]++;if(top1)stats[0][c][0]++;if(cs.length){stats[1][c][1]++;stats[2][c][1]++;if(rank>=0&&rank<3)stats[1][c][0]++;if(rank<0)stats[2][c][0]++;}}
    let s='';const left=kiosk()?105:132,right=w-65,barH=10,rowH=(h-25)/3;
    for(const [i,label] of labels.entries()){const y=28+i*rowH;s+=svgText(6,y,label,'#e7e4dc','start',13);for(const [j,c] of ['B','W'].entries()){const yy=y+12+j*24,[hit,den]=stats[i][c],rate=den?hit/den:0;s+=svgText(left-8,yy+4,c==='B'?'黑':'白','#d9d5cc','end',12)+`<rect x="${left}" y="${yy-5}" width="${right-left}" height="${barH}" rx="4" fill="#363a34"/><rect x="${left}" y="${yy-5}" width="${(right-left)*rate}" height="${barH}" rx="4" fill="${colors[i]}"/>`+svgText(right+8,yy+4,`${Math.round(rate*100)}%`,'#f2efea','start',13);}}
    return svg(w,h,s,'AI一选、前三、前十选吻合度，黑白分开统计');
  }
  function matchDistribution(w,h) {
    const rr=rated(),from=rr[0]?.move_number??0,last=rr.at(-1)?.move_number??total,left=36,right=w-12,top=44,bandH=Math.min(60,(h-100)/3),ys=[top,top+bandH+40],x=n=>left+(n-from)/(last-from+1)*(right-left),dw=(right-left)/(last-from+1);
    let s='';for(const [i,c] of ['B','W'].entries()){s+=svgText(5,ys[i]+bandH/2,c==='B'?'黑':'白','#e3dfd6','start',13)+`<rect x="${left}" y="${ys[i]}" width="${right-left}" height="${bandH}" fill="#282f28" rx="5"/>`;for(const r of rr.filter(r=>r.actual_player===c)){const cs=byMove[r.move_number-1]?.top_moves??[],rank=cs.findIndex(m=>m.move===r.actual_move),top=r.is_top_move??(cs.length?rank===0:null),level=top?1:rank>=0&&rank<3?.55:.18,col=top?'#77c991':rank>=0&&rank<3?'#a6ce9b':!cs.length?'#5d645e':'#b68b5a';s+=`<rect data-move="${r.move_number}" x="${x(r.move_number)}" y="${ys[i]+bandH*(1-level)}" width="${Math.max(1,dw)}" height="${bandH*level}" fill="${col}" style="cursor:pointer"><title>第 ${r.move_number} 手 ${r.actual_move}</title></rect>`;}}
    s+=svgText(left,ys[1]+bandH+24,from,'#c8c5bf','start',12)+svgText(right,ys[1]+bandH+24,last,'#c8c5bf','end',12);
    return svg(w,h,s,'逐手AI吻合分布，实色满高是一选，半高是前三；点击跳转');
  }
  function helpContent(tab) {
    const note=selectedMoves();
    const texts={trend:'绿线为黑棋胜率，橙线为黑棋领先目。目差以黑方为基准，负数表示白方领先。点击图表跳到对应手数。',brilliant:'入选同时满足：走出引擎首选、该首选的 policy 先验低于10%、局面仍未定。妙度1：5%≤prior<10%；妙度2：3%≤prior<5%；妙度3：2%≤prior<3%；妙度4：1%≤prior<2%；妙度5：prior<1%。官子入选门槛为6%，分档仍使用绝对先验。',mistake:'小亏：目损不足3目；失误：目损不足6目；恶手：目损至少6目。黑方在横轴上方，白方在横轴下方。优先展示每方目损最高的5手，点击标记查看对应局面。',grade:'柱顶数字为手数，柱高为该方已评级着手中的比例；黑白各自归一化。黑为空心柱、白为实心浅色柱。妙手：引擎首选且先验低于10%；最佳：引擎首选；很好：目损<0.5目；尚可：目损<1.5目；小亏：目损<3目；失误：目损<6目；恶手：目损≥6目。未评级着手不进入比例分母。',match:'一选按引擎playSelectionValue排序，并优先采用服务端is_top_move判定；前三、前十选根据上一局面的候选表比对，各行分别计算可判定手数作为分母。分布图满高表示一选、半高表示前三；缺失数据不当作未命中。一致率取决于局面难度，不能单独作为棋力或作弊证据。'};
    return `<p>${texts[tab]}</p>${['brilliant','mistake'].includes(tab)?`<p class="help-count">当前筛选共 ${note.total} 处${note.truncated?`，另有 ${note.truncated} 处未画出`:'，已全部画出'}；图上每方最多展示5手。</p>`:''}`;
  }
  function renderAnalysis() {
    for(const place of ['desktop','kiosk']){const holder=$(`#${place}Tabs`);holder.innerHTML=tabs.map(([id,label])=>`<div class="tab-group ${id===state.tab?'active':''}"><button type="button" data-tab="${id}" role="tab" aria-selected="${id===state.tab}">${label}</button><button type="button" class="tab-help" data-help="${id}" aria-label="${label}说明" aria-expanded="false">${icon('help')}</button></div>`).join('');
      const body=$(`#${place}AnalysisBody`),{w,h}=chartMetrics(place);body.innerHTML=`<div class="chart-workspace ${state.tab==='trend'?'no-filters':''}">${filters()}<div class="chart-main">${state.tab==='trend'?`<div class="chart-readout"><span class="wr">黑棋胜率：${pct(current()?.winrate)}</span><span class="pts">黑棋领先：${signed(current()?.score_lead)} 目</span></div>`:''}<div class="chart-box">${state.tab==='trend'?trend(w,h):state.tab==='brilliant'||state.tab==='mistake'?lollipop(w,h):state.tab==='grade'?histogram(w,h):state.view==='stats'?matchStats(w,h):matchDistribution(w,h)}</div></div></div>`;
    }
  }
  let helpTimer,hideTimer,helpAnchor=null,helpPinned=false;
  function closeHelp(){clearTimeout(helpTimer);clearTimeout(hideTimer);$('#helpPopover').hidden=true;if(helpAnchor)helpAnchor.setAttribute('aria-expanded','false');helpAnchor=null;helpPinned=false;}
  function openHelp(anchor,pin=false){clearTimeout(hideTimer);if(!anchor)return;helpAnchor=anchor;helpPinned=pin;const pop=$('#helpPopover'),tab=anchor.dataset.help;pop.innerHTML=`<div class="help-title"><strong>${tabs.find(t=>t[0]===tab)[1]}说明</strong><button data-close-help aria-label="关闭说明">${icon('close')}</button></div>${helpContent(tab)}`;pop.hidden=false;anchor.setAttribute('aria-expanded','true');const r=anchor.getBoundingClientRect(),pr=pop.getBoundingClientRect(),left=Math.max(kiosk()?564:12,Math.min(r.right-pr.width,innerWidth-pr.width-12));pop.style.left=`${left}px`;pop.style.top=`${Math.max(12,Math.min(r.bottom+8,innerHeight-pr.height-12))}px`;}
  function openDialog(which){closeHelp();$('#dialogBackdrop').classList.add('open');$('#detailsDialog').style.display=which==='details'?'flex':'none';$('#analysisDialog').style.display=which==='analysis'?'flex':'none';renderAnalysis();}
  function closeDialog(){$('#dialogBackdrop').classList.remove('open');closeHelp();}
  function render(){document.body.dataset.mode=state.mode;renderMeta();renderCandidates();renderControls();renderPlayback();renderAnalysis();drawBoard();$$('.ruler span').forEach(e=>e.style.visibility=state.coordinates?'visible':'hidden');}
  let playbackTimer;
  function setCursor(n){closeHelp();state.cursor=Math.max(0,Math.min(total,n));state.pv=null;state.tryMoves=[];if(state.cursor===total&&state.playing){clearInterval(playbackTimer);state.playing=false;}render();}
  document.addEventListener('click',e=>{
    const help=e.target.closest('[data-help]');if(help){if(helpAnchor===help&&helpPinned)closeHelp();else openHelp(help,true);return;}
    if(e.target.closest('[data-close-help]')){closeHelp();return;}if(!e.target.closest('#helpPopover'))closeHelp();
    const tab=e.target.closest('[data-tab]');if(tab){state.tab=tab.dataset.tab;state.selected=null;renderAnalysis();return;}
    for(const key of ['phase','player','view']){const pick=e.target.closest(`[data-${key}]`);if(pick){state[key]=pick.dataset[key];renderAnalysis();return;}}
    const cand=e.target.closest('[data-candidate]');if(cand){const i=Number(cand.dataset.candidate);if(cand.hasAttribute('data-actual')){setCursor(state.cursor+1);return;}state.pv=state.pv===i?null:i;drawBoard();return;}
    const m=e.target.closest('[data-move]');if(m){setCursor(Number(m.dataset.move));return;}
    const mode=e.target.closest('button[data-mode]');if(mode){state.mode=mode.dataset.mode;render();return;}
    if(e.target.closest('[data-close-dialog]')||e.target===$('#dialogBackdrop')){closeDialog();return;}
    const expand=e.target.closest('#expandAnalysis');if(expand||e.target===$('#analysisBackdrop')){const on=$('#desktopAnalysis').classList.toggle('analysis-expanded');$('#analysisBackdrop').classList.toggle('visible',on);$('#expandAnalysis').innerHTML=icon(on?'collapse':'expand');requestAnimationFrame(renderAnalysis);return;}
    const action=e.target.closest('[data-action]');if(!action)return;
    switch(action.dataset.action){case 'first':setCursor(0);break;case 'prev':setCursor(state.cursor-1);break;case 'next':setCursor(state.cursor+1);break;case 'last':setCursor(total);break;case 'play':if(state.playing){clearInterval(playbackTimer);state.playing=false;renderPlayback();}else{if(state.cursor===total)state.cursor=0;state.playing=true;playbackTimer=setInterval(()=>setCursor(state.cursor+1),750);render();}break;case 'openAnalysis':openDialog('analysis');break;case 'details':openDialog('details');break;case 'clear':state.tryMoves=[];state.pv=null;render();break;case '3d':state.view3d=!state.view3d;renderControls();$('#board').classList.toggle('depth-preview',state.view3d);break;default:if(action.dataset.action in state){state[action.dataset.action]=!state[action.dataset.action];render();}}
  });
  document.addEventListener('input',e=>{if(e.target.matches('[data-slider]'))setCursor(Number(e.target.value));});
  document.addEventListener('pointerover',e=>{const help=e.target.closest('[data-help]');if(help&&e.pointerType!=='touch'){clearTimeout(helpTimer);helpTimer=setTimeout(()=>openHelp(help),550);}if(e.target.closest('#helpPopover'))clearTimeout(hideTimer);});
  document.addEventListener('pointerout',e=>{if(e.target.closest('[data-help]')){clearTimeout(helpTimer);if(!helpPinned)hideTimer=setTimeout(closeHelp,220);}if(e.target.closest('#helpPopover')&&!e.relatedTarget?.closest('#helpPopover')&&!helpPinned)hideTimer=setTimeout(closeHelp,220);});
  document.addEventListener('click',e=>{const chart=e.target.closest('[data-trend-chart]');if(chart){const r=chart.getBoundingClientRect();setCursor(Math.round(Math.max(0,Math.min(1,(e.clientX-r.left-42)/(r.width-80)))*total));}});
  document.addEventListener('keydown',e=>{if(e.key==='Escape'){closeDialog();$('#desktopAnalysis').classList.remove('analysis-expanded');$('#analysisBackdrop').classList.remove('visible');}if(e.key==='ArrowLeft')setCursor(state.cursor-1);if(e.key==='ArrowRight')setCursor(state.cursor+1);});
  $('#board').addEventListener('click',e=>{if(state.pv!==null){state.pv=null;drawBoard();return;}if(!state.try)return;const r=e.currentTarget.getBoundingClientRect(),step=kiosk()?r.width/19:Math.floor(r.width/21),off=(r.width-step*18)/2,x=Math.round((e.clientX-r.left-off)/step),y=Math.round((e.clientY-r.top-off)/step);if(x>=0&&x<19&&y>=0&&y<19&&!position().board[y*19+x]){state.tryMoves.push(`${letters[x]}${19-y}`);render();}});
  for(const name of ['top','bottom','left','right'])$(`.ruler.${name}`).innerHTML=(name==='top'||name==='bottom'?[...letters]:Array.from({length:19},(_,i)=>19-i)).map(n=>`<span>${n}</span>`).join('');
  if(query.get('controls')==='1')document.body.dataset.preview='true';
  render();new ResizeObserver(()=>{drawBoard();requestAnimationFrame(renderAnalysis);}).observe($('#desktopAnalysisBody'));new ResizeObserver(()=>requestAnimationFrame(renderAnalysis)).observe($('#kioskAnalysisBody'));window.addEventListener('resize',render);
  window.previewState=state;
})();
