/* Isolated personal-review design fixture. No API calls, private SGF, or task submission. */
(() => {
  const families = window.KioskDesignFamilies;
  const publicGame = window.KioskKifuFixture.unanalysed;
  // Public-library main line is used only as board geometry for anonymous design examples.
  // It is never sent to a personal-game or album endpoint by this HTML artifact.
  const moves = [...publicGame.sgf.matchAll(/;([BW])\[([a-s]{2})?\]/g)].map(([, color, point]) => ({color, point:point ? [point.charCodeAt(0)-97,point.charCodeAt(1)-97] : null}));
  const totalMoves = moves.length;
  const examples = [
    {id:'example-a', title:'人机自由对弈', black:'我', white:'对手 3 级', moves:totalMoves, date:'10-24', result:'黑胜中盘'},
    {id:'example-b', title:'本地双人对局', black:'黑方', white:'白方', moves:144, date:'10-23', result:'白胜中盘'},
    {id:'example-c', title:'人机自由对弈', black:'我', white:'对手 5 级', moves:96, date:'10-22', result:'黑胜中盘'},
    {id:'example-d', title:'本地双人对局', black:'黑方', white:'白方', moves:44, date:'10-21', result:'白胜中盘'},
  ];
  const state = {selected:examples[0].id, scenario:'mixed', overrides:{}, replayMove:totalMoves, reportMove:totalMoves, reportTier:'normal', reportPrevious:false, reportTab:'trend', coordinates:true, numbers:false, importOpen:false, importPage:1, query:'', draft:'', album:null, message:null};
  const escape = v => String(v ?? '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/"/g,'&quot;');
  const paths = {
    back:'<path d="m15 4-8 8 8 8M7 12h15"/>',
    first:'<path d="M5 4v16m14-16-8 8 8 8"/>', prev:'<path d="m15 4-8 8 8 8"/>', next:'<path d="m9 4 8 8-8 8"/>', last:'<path d="M19 4v16M5 4l8 8-8 8"/>',
    info:'<circle cx="12" cy="12" r="9"/><path d="M12 11v6m0-10h.01"/>', close:'<path d="m5 5 14 14M19 5 5 19"/>',
    search:'<circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 5 5"/>', check:'<path d="m4 12 5 5L20 6"/>',
    import:'<path d="M12 3v12m-4-4 4 4 4-4M4 15v6h16v-6"/>', chart:'<path d="M3 18h18M4 14l5-5 4 3 6-7"/>',
    board:'<rect x="3" y="3" width="18" height="18" rx="1"/><path d="M3 9h18M3 15h18M9 3v18m6-18v18"/>', retry:'<path d="M3 11a9 9 0 1 1 2 7M3 4v7h7"/>', book:'<path d="M4 3h7v18H4zM13 3h7v18h-7zM5 7h5m4 0h5"/>'
  };
  const icon = name => `<svg class="pr-icon" viewBox="0 0 24 24" aria-hidden="true">${paths[name] || paths.board}</svg>`;
  const selected = () => examples.find(g => g.id === state.selected) || examples[0];
  const go = id => document.querySelector(`.chooser button[data-id="${id}"]`)?.click();
  const refresh = () => { const id=location.hash.slice(1); go(['review','review-import','review-replay','review-report'].includes(id)?id:'review'); };
  const stone = white => `<i class="pr-stone${white?' white':''}"></i>`;
  const button = (label, attrs='', kind='', image='') => `<button ${attrs.includes('type=')?'':'type="button"'} class="${kind}" ${attrs}>${image?icon(image):''}${label}</button>`;
  const task = (status, n, total, extra={}) => ({status, analyzed_moves:n, total_moves:total, ...extra});
  function tasks(game) {
    const total=game.moves, n=Math.round(total*.41);
    const scenarios = {
      mixed:{normal:task('completed',total,total),deep:task('running',n,total)},
      completed:{normal:task('completed',total,total),deep:task('completed',total,total)},
      failed:{normal:task('completed',total,total),deep:task('failed',n,total)},
      waiting:{normal:task('authorizing',0,total),deep:task('pending',0,total)},
      rerun:{normal:task('running',Math.round(total*.29),total,{previous:true}),deep:task('completed',total,total)},
      missing:{normal:task('missing',0,total),deep:task('missing',0,total)},
      unknown:{normal:task('completed',total,total),deep:task('running',0,0)},
    };
    return {...scenarios[state.scenario],...state.overrides[game.id]};
  }
  function tierRow(kind, t) {
    const name=kind==='normal'?'普通':'深度', visits=kind==='normal'?500:2000;
    const labels={missing:'尚未生成',authorizing:'提交处理中',pending:t.analyzed_moves?'排队中 · 待续算':'排队中',running:t.previous?'本次分析中':'分析中',failed:'分析中断',completed:'已完成'};
    const hasTotal=t.total_moves>0;
    const percent=hasTotal?Math.min(100,Math.round(t.analyzed_moves/t.total_moves*100)):null;
    const caption=t.status==='missing'?'生成后在这里查看进度':t.status==='authorizing'?'等待服务端确认任务':!hasTotal?'等待总手数 · 暂不显示百分比':t.status==='pending'&&!t.analyzed_moves?'尚未开始分析':`${t.status==='failed'||t.status==='pending'?'已保留':'已分析'} ${t.analyzed_moves} / ${t.total_moves} 手${t.status==='failed'?' · 可续算':''}`;
    let action;
    if(t.status==='completed')action=button('查看报告',`data-pr-open-report="${kind}"`,'pr-primary');
    else if(t.previous)action=button('上次报告',`data-pr-open-report="${kind}" data-pr-previous="true"`);
    else if(t.status==='failed')action=button('继续分析',`data-pr-retry="${kind}"`,'','retry');
    else if(t.status==='missing')action=button('生成报告',`data-pr-generate="${kind}"`);
    else action=button(t.status==='running'?'分析中':t.status==='pending'?'排队中':'提交中','disabled aria-disabled="true"');
    return `<article class="pr-tier" data-status="${t.status}" data-pr-tier="${kind}" aria-label="${name}报告 ${visits} 次，${labels[t.status]}"><div class="pr-tier-label"><strong>${name}报告</strong><small>每手 ${visits} 次</small></div><div><div class="pr-tier-status"><strong>${labels[t.status]}</strong><output>${percent!==null&&!['missing','authorizing','pending'].includes(t.status)?percent+'%':''}</output></div><div class="pr-progress" ${!['missing','authorizing'].includes(t.status)&&hasTotal?`role="progressbar" aria-label="${name}报告已分析手数" aria-valuemin="0" aria-valuemax="${t.total_moves}" aria-valuenow="${t.analyzed_moves}"`:''}><i style="width:${percent||0}%"></i></div><div class="pr-progress-caption">${caption}</div></div>${action}</article>`;
  }
  function positionAt(n) {
    const cells=Array(361).fill(null);
    const neighbors=p=>[p%19?p-1:-1,p%19<18?p+1:-1,p>=19?p-19:-1,p<342?p+19:-1].filter(v=>v>=0);
    function group(start) {const seen=new Set([start]), queue=[start];let liberty=false;while(queue.length)for(const p of neighbors(queue.pop())){if(!cells[p])liberty=true;else if(cells[p].color===cells[start].color&&!seen.has(p)){seen.add(p);queue.push(p);}}return {seen,liberty};}
    moves.slice(0,n).forEach((m,i)=>{if(!m.point)return;const p=m.point[1]*19+m.point[0];cells[p]={color:m.color,n:i+1};for(const a of neighbors(p))if(cells[a]&&cells[a].color!==m.color){const g=group(a);if(!g.liberty)for(const c of g.seen)cells[c]=null;}const own=group(p);if(!own.liberty)for(const c of own.seen)cells[c]=null;});
    return cells;
  }
  function board(n, large=false) {
    const o=34, d=25, cells=positionAt(n), letters='ABCDEFGHJKLMNOPQRST';
    const grid=Array.from({length:19},(_,i)=>`<path d="M${o} ${o+i*d}H484 M${o+i*d} ${o}V484"/>`).join('');
    const stars=[3,9,15].flatMap(x=>[3,9,15].map(y=>`<circle cx="${o+x*d}" cy="${o+y*d}" r="2.9" fill="#4e351b"/>`)).join('');
    const stones=cells.map((c,i)=>c?`<circle cx="${o+i%19*d}" cy="${o+Math.floor(i/19)*d}" r="11.6" fill="url(#pr-${large?'large':'small'}-${c.color})" stroke="${c.color==='B'?'#111b17':'#d9ded7'}" stroke-width="1.2"/>${large&&state.numbers&&c.n>n-10?`<text x="${o+i%19*d}" y="${o+Math.floor(i/19)*d+6}" text-anchor="middle" fill="${c.color==='B'?'#f6f6ef':'#102117'}" font-size="18">${c.n}</text>`:''}`:'').join('');
    const labels=large&&state.coordinates?Array.from({length:19},(_,i)=>`<text x="${o+i*d}" y="18" text-anchor="middle">${letters[i]}</text><text x="${o+i*d}" y="510" text-anchor="middle">${letters[i]}</text><text x="14" y="${o+i*d+6}" text-anchor="middle">${19-i}</text><text x="503" y="${o+i*d+6}" text-anchor="middle">${19-i}</text>`).join(''):'';
    return `<svg viewBox="0 0 516 516" role="img" aria-label="匿名设计示意棋局，第 ${n} 手，只读棋盘"><defs><linearGradient id="pr-${large?'large':'small'}-wood" x2=".8" y2="1"><stop stop-color="#dbad69"/><stop offset=".5" stop-color="#e2b777"/><stop offset="1" stop-color="#c69350"/></linearGradient><radialGradient id="pr-${large?'large':'small'}-B" cx=".34" cy=".25" r=".78"><stop stop-color="#52565a"/><stop offset=".65" stop-color="#191b1b"/><stop offset="1" stop-color="#080a0a"/></radialGradient><radialGradient id="pr-${large?'large':'small'}-W" cx=".34" cy=".25" r=".8"><stop stop-color="#fff"/><stop offset=".72" stop-color="#f0f1eb"/><stop offset="1" stop-color="#b4b9b4"/></radialGradient></defs><rect width="516" height="516" rx="9" fill="#79502b"/><rect x="22" y="22" width="472" height="472" fill="url(#pr-${large?'large':'small'}-wood)"/><g stroke="#674923" stroke-width="1">${grid}</g>${stars}<g font-family="Kiosk Plex Mono,monospace">${stones}</g><g fill="#efd4a6" font-family="Kiosk Plex Mono,monospace" font-size="18">${labels}</g></svg>`;
  }
  function home() {
    const game=selected(), ts=tasks(game);
    return `<section class="pr-selected"><div class="pr-selected-head"><strong>选中这一局</strong>${button(icon('info'),'data-pr-info="fixture" aria-label="棋局示意说明"','pr-info')}</div><div class="pr-small-board">${board(game.moves)}</div><div class="pr-selected-players"><span>${game.black} 对 ${game.white}</span><span>${game.moves} 手</span></div><div class="pr-selected-meta"><span>${game.title}</span><span>${game.result}</span></div>${button('查看棋谱','data-pr-replay','', 'book')}</section><section class="pr-right"><div><div class="pr-task-heading"><strong>这一局的分析报告</strong><span>完成后可查看</span></div>${tierRow('normal',ts.normal)}${tierRow('deep',ts.deep)}</div><div class="pr-history-heading"><strong>历史对局</strong><span>${examples.length} 局示意</span>${button('导入棋谱复盘','data-pr-import','','import')}</div><div class="pr-history" aria-label="历史对局列表">${examples.map(g=>`<button type="button" class="pr-game u-game-card" data-pr-select="${g.id}" aria-pressed="${g.id===game.id}"><strong>${g.title}</strong><span>${g.date} · ${g.moves} 手</span><span class="pr-game-players">${stone(false)}${g.black}<span>对</span>${g.white}${stone(true)}</span><span class="pr-game-result">${g.result}</span></button>`).join('')}</div><div class="pr-pages"><span>每页 20 局</span>${button(icon('first'),'disabled aria-label="第一页"','pr-icon-button')}${button(icon('prev'),'disabled aria-label="上一页"','pr-icon-button')}<output>1 / 1 页</output>${button(icon('next'),'disabled aria-label="下一页"','pr-icon-button')}${button(icon('last'),'disabled aria-label="最后一页"','pr-icon-button')}</div></section>`;
  }
  function playback(report=false) {
    const n=report?state.reportMove:state.replayMove, max=selected().moves;
    return `<div class="pr-playback" aria-label="逐手回放">${button(icon('first'),`data-pr-move="first" ${n===0?'disabled':''} aria-label="回到开局"`)}${button(icon('prev'),`data-pr-move="prev" ${n===0?'disabled':''} aria-label="上一手"`)}<input type="range" min="0" max="${max}" value="${n}" data-pr-move-range aria-label="跳到指定手数">${button(icon('next'),`data-pr-move="next" ${n===max?'disabled':''} aria-label="下一手"`)}${button(icon('last'),`data-pr-move="last" ${n===max?'disabled':''} aria-label="跳到终局"`)}</div>`;
  }
  function replay() {
    const game=selected();
    return `<div class="pr-large-board" data-pr-board>${board(state.replayMove,true)}</div><section class="pr-rail"><header class="pr-detail-heading">${button('返回复盘','data-pr-back','','back')}<strong>我的棋谱</strong>${button(icon('info'),'data-pr-info="replay" aria-label="个人棋谱回放说明"','pr-info')}</header><div class="pr-match"><strong>${game.title}</strong><div class="pr-match-players"><span>${stone(false)}${game.black}</span><span>${game.white}${stone(true)}</span></div><span>${game.date} · ${game.moves} 手 · ${game.result}</span></div><div class="pr-readonly"><strong>原谱回放 · 只读</strong><p>无需生成分析报告，随时逐手查看。<br>胜率、候选与失误请到已完成报告中查看。</p></div><div class="pr-coordinate-toggle">${button('坐标',`data-pr-toggle="coordinates" aria-pressed="${state.coordinates}"`,'','board')}${button('手数',`data-pr-toggle="numbers" aria-pressed="${state.numbers}"`,'','book')}</div><div class="pr-move-info"><strong>当前手数</strong><output data-pr-move-output>第 ${state.replayMove} / ${game.moves} 手</output></div>${playback()}</section>`;
  }
  function reportWork() {
    const n=state.reportMove, total=selected().moves;
    if(state.reportTab==='trend') {
      const points=Array.from({length:38},(_,i)=>{const v=50+Math.sin(i*.45)*22+i*.38;return `${46+i*9.25},${132-v*1.05}`;}).join(' ');
      return `<header>黑方胜率<span>第 ${n} / ${total} 手</span></header><svg class="pr-report-chart" viewBox="0 0 420 145" role="img" aria-label="设计示意胜率曲线"><g stroke="#385141" stroke-dasharray="4 4"><path d="M46 25H395M46 77H395M46 130H395"/></g><text x="0" y="30">100%</text><text x="10" y="82">50%</text><text x="20" y="135">0%</text><polyline points="${points}" fill="none" stroke="#7bd59a" stroke-width="3"/><line x1="${46+n/total*342}" y1="20" x2="${46+n/total*342}" y2="130" stroke="#e4c087" stroke-width="2"/></svg><div class="pr-report-xaxis"><span>开局</span><span>中盘</span><span>${total} 手</span></div>`;
    }
    if(state.reportTab==='mistake') return `<header>关键失误<span>点按跳到该手</span></header>${[[37,'小亏','2.1 目'],[71,'失误','4.2 目'],[89,'恶手','8.6 目']].filter(r=>r[0]<=selected().moves).map(([m,label,value])=>`<div class="pr-report-row">${button(`第 ${m} 手`,`data-pr-jump="${m}"`)}<span>${label}</span><strong>${value}</strong></div>`).join('')}`;
    return `<header>AI 推荐<span>第 ${n} 手之后</span></header><div class="pr-report-row"><span>着点</span><span>推荐度</span><span>目差</span><span>胜率</span></div>${[['Q16','64%','+2.3','62%'],['D4','23%','+1.5','57%'],['C14','13%','+0.8','54%']].map(r=>`<div class="pr-report-row">${r.map(v=>`<strong>${v}</strong>`).join('')}</div>`).join('')}`;
  }
  function personalReport() {
    const game=selected(), name=state.reportTier==='normal'?'普通':'深度', visits=state.reportTier==='normal'?500:2000;
    const t=tasks(game)[state.reportTier];
    if(t.status!=='completed'&&!(t.previous&&state.reportPrevious))return `<div class="pr-large-board">${board(game.moves,true)}</div><section class="pr-rail"><header class="pr-detail-heading">${button('返回复盘','data-pr-back','','back')}<strong>${name}报告</strong></header><div class="pr-readonly"><strong>报告尚未完成</strong><p>返回复盘查看这一档的任务进度。完成后，再从“查看报告”进入。</p></div></section>`;
    return `<div class="pr-large-board" data-pr-board>${board(state.reportMove,true)}</div><section class="pr-rail pr-report"><header class="pr-detail-heading">${button('返回复盘','data-pr-back','','back')}<strong>${state.reportPrevious?'上次':''}${name}报告</strong>${button(icon('info'),'data-pr-info="report" aria-label="报告信息"','pr-info')}</header><div class="pr-report-summary"><div><span>${game.black} 对 ${game.white}</span><strong>${state.reportPrevious?'上次完成':'已完成'} · ${visits} 次</strong></div><span>${game.moves} / ${game.moves} 手已分析 · ${game.title}</span></div><div class="pr-report-tabs" role="group" aria-label="个人报告视图">${[['trend','走势'],['mistake','失误'],['recommend','AI 推荐']].map(([id,t])=>button(t,`data-pr-report-tab="${id}" aria-pressed="${state.reportTab===id}"`)).join('')}</div><div class="pr-report-work">${reportWork()}</div><div class="pr-report-footnote">第 ${state.reportMove} / ${game.moves} 手 · 分析图表为设计示意</div>${playback(true)}</section>`;
  }
  const albumItems=[...window.KioskKifuFixture.page1,...window.KioskKifuFixture.page2];
  function filteredAlbums(){const q=state.query.toLowerCase();return albumItems.filter(a=>!q||`${a.event} ${a.black} ${a.white} ${a.date}`.toLowerCase().includes(q));}
  function importDialog() {
    const all=filteredAlbums(), pageTotal=Math.max(1,Math.ceil(all.length/10));
    state.importPage=Math.min(state.importPage,pageTotal);
    const rows=all.slice((state.importPage-1)*10,state.importPage*10);
    if(!rows.some(a=>a.id===state.album))state.album=rows[0]?.id??null;
    return `<div class="pr-import-scrim"><section class="pr-import" role="dialog" aria-modal="true" aria-labelledby="pr-import-title"><header class="pr-import-head"><div><h2 id="pr-import-title">导入棋谱复盘</h2><p>公共职业棋谱库 · 选中棋谱后选择导入方式</p></div><div>${button(icon('info'),'data-pr-info="import" aria-label="棋谱来源与分析费用说明"','pr-info')}${button(icon('close'),'data-pr-close-import aria-label="关闭导入棋谱"','pr-icon-button')}</div></header><form class="pr-import-search" data-pr-search-form><label>${icon('search')}<input type="search" placeholder="搜索棋手、赛事或年份" aria-label="搜索公共棋谱库" value="${escape(state.draft)}" data-pr-query></label>${button('搜索','type="submit" data-pr-search')}${button('清空','data-pr-clear')}</form><div class="pr-import-list" aria-label="公共棋谱列表">${rows.length?rows.map(a=>`<button type="button" class="pr-album u-game-card" data-pr-album="${a.id}" aria-pressed="${a.id===state.album}"><strong><i class="pr-check">${a.id===state.album?icon('check'):icon('book')}</i><span>${escape(a.event)}</span></strong><span>${a.date} · ${a.moves} 手</span><div class="pr-album-players">${stone(false)}<span>${escape(a.black)}</span><em>对</em><span>${escape(a.white)}</span>${stone(true)}</div><span>${escape(a.result==='B+R'?'黑胜中盘':a.result==='W+R'?'白胜中盘':a.result||'结果未记录')}</span></button>`).join(''):`<div class="pr-import-empty"><strong>没有找到相关棋谱</strong><span>换一个棋手名或赛事试试</span>${button('清空搜索','data-pr-clear')}</div>`}</div><nav class="pr-pages" aria-label="导入棋谱分页"><span>${all.length} 局示意 · 每页 10 局</span>${button(icon('first'),`data-pr-import-page="1" ${state.importPage===1?'disabled':''} aria-label="导入棋谱第一页"`,'pr-icon-button')}${button('上一页',`data-pr-import-page="${state.importPage-1}" ${state.importPage===1?'disabled':''}`)}<output>${state.importPage} / ${pageTotal} 页</output>${button('下一页',`data-pr-import-page="${state.importPage+1}" ${state.importPage===pageTotal?'disabled':''}`)}${button(icon('last'),`data-pr-import-page="${pageTotal}" ${state.importPage===pageTotal?'disabled':''} aria-label="导入棋谱最后一页"`,'pr-icon-button')}</nav><footer class="pr-import-actions">${button('取消','data-pr-close-import')}${button('仅导入<small>不生成报告</small>',`data-pr-import-action="only" ${!rows.length?'disabled':''}`)}${button('<span>普通 500</span><small>导入并分析</small>',`data-pr-import-action="normal" ${!rows.length?'disabled':''}`,'pr-primary')}${button('<span>深度 2000</span><small>导入并分析</small>',`data-pr-import-action="deep" ${!rows.length?'disabled':''}`)}</footer></section></div>`;
  }
  const infoCopy={
    fixture:['设计示意棋局','匿名棋局与两档进度都是隔离设计示意，非当前设备任务。盘面借用已收录的公开棋谱几何，不含用户私有 SGF 或账号标识。'],
    replay:['个人原谱 · 只读回放','正式实现从选中的个人棋局读取主线，支持逐手、跳手与终局。原谱回放不需要生成付费报告，也不会使用职业棋谱的 album 接口。'],
    report:['已完成的个人报告','本页展示对应选中棋局与档位的报告设计。走势、失误与推荐数值为设计示意。正式实现仅在任务 completed 时进入报告。'],
    import:['公共棋谱库与分析费用','来源沿用 KifuAPI 公共棋谱库，不是个人历史。仅导入不创建报告；普通 500／深度 2000 会在导入后创建对应档位，费用需在实际确认时说明。此处所有按钮只演示，不导入、不分析、不扣费。'],
  };
  function message() {
    if(!state.message)return '';
    const m=state.message;
    return `<div class="pr-preview-message"><div role="dialog" aria-modal="true" aria-label="${escape(m.title)}"><h3>${m.title}</h3><p>${m.copy}</p><small>设计示意 · 不调用 API、不写入设备</small><footer>${m.confirm?button('取消','data-pr-close-message'):''}${button(m.confirm?'确认示意':'知道了',m.confirm?`data-pr-confirm-generate="${m.confirm}"`:'data-pr-close-message','pr-primary')}</footer></div></div>`;
  }
  function render(s,ctx) {
    const isReplay=s.id==='review-replay',isReport=s.id==='review-report';
    state.importOpen=s.id==='review-import';
    return `<div class="pr-root ${isReplay||isReport?'pr-detail':'pr-home'} ${state.importOpen||state.message?'pr-has-dialog':''}">${isReplay?replay():isReport?personalReport():home()}${state.importOpen&&!isReplay&&!isReport?importDialog():''}${message()}</div>`;
  }
  for(const id of ['review','review-import','review-replay','review-report'])families[id]=render;
  window.KioskPersonalReviewInit = id => {
    const controls=document.getElementById('personal-review-demo-controls');
    if(controls)controls.hidden=!['review','review-import','review-replay','review-report'].includes(id);
    const select=document.getElementById('personal-review-scenario');
    if(select)select.value=state.scenario;
  };
  document.addEventListener('change',e=>{if(e.target.id==='personal-review-scenario'){state.scenario=e.target.value;state.overrides={};state.message=null;state.importOpen=false;go('review');}});
  document.addEventListener('input',e=>{if(e.target.matches('[data-pr-query]'))state.draft=e.target.value;if(e.target.matches('[data-pr-move-range]')){if(location.hash==='#review-report')state.reportMove=Number(e.target.value);else state.replayMove=Number(e.target.value);updateBoard();}});
  function updateBoard(){const report=location.hash==='#review-report',n=report?state.reportMove:state.replayMove;document.querySelector('[data-pr-board]').innerHTML=board(n,true);const out=document.querySelector('[data-pr-move-output]');if(out)out.textContent=`第 ${n} / ${selected().moves} 手`;const range=document.querySelector('[data-pr-move-range]');if(range)range.value=n;const first=n===0,last=n===selected().moves;for(const name of ['first','prev','next','last']){const b=document.querySelector(`[data-pr-move="${name}"]`);if(b)b.disabled=['first','prev'].includes(name)?first:last;}if(report){document.querySelector('.pr-report-work').innerHTML=reportWork();document.querySelector('.pr-report-footnote').textContent=`第 ${n} / ${selected().moves} 手 · 分析图表为设计示意`;}window.KioskDesignTypography?.apply();}
  document.addEventListener('keydown',e=>{if(e.key==='Escape'&&(state.message||state.importOpen)){if(state.message){state.message=null;refresh();}else{state.importOpen=false;go('review');}}});
  document.addEventListener('submit',e=>{if(e.target.matches('[data-pr-search-form]')){e.preventDefault();search();}});
  function search(){state.query=state.draft.trim();state.importPage=1;state.album=null;refresh();}
  document.addEventListener('click',e=>{
    const b=e.target.closest('[data-pr-select],[data-pr-replay],[data-pr-open-report],[data-pr-back],[data-pr-retry],[data-pr-generate],[data-pr-move],[data-pr-toggle],[data-pr-import],[data-pr-close-import],[data-pr-album],[data-pr-import-page],[data-pr-search],[data-pr-clear],[data-pr-import-action],[data-pr-info],[data-pr-close-message],[data-pr-confirm-generate],[data-pr-report-tab],[data-pr-jump]');
    if(!b||b.disabled)return;
    if(b.hasAttribute('data-pr-select')){state.selected=b.dataset.prSelect;state.replayMove=selected().moves;state.reportMove=selected().moves;const scroll=document.querySelector('.pr-history')?.scrollTop;refresh();document.querySelector('.pr-history').scrollTop=scroll;}
    else if(b.hasAttribute('data-pr-replay')){state.replayMove=selected().moves;state.importOpen=false;go('review-replay');}
    else if(b.hasAttribute('data-pr-open-report')){const kind=b.dataset.prOpenReport,t=tasks(selected())[kind];if(t.status!=='completed'&&!(t.previous&&b.dataset.prPrevious))return;state.reportTier=kind;state.reportPrevious=Boolean(b.dataset.prPrevious);state.reportMove=selected().moves;state.reportTab='trend';state.importOpen=false;go('review-report');}
    else if(b.hasAttribute('data-pr-back')){state.importOpen=false;state.message=null;go('review');}
    else if(b.hasAttribute('data-pr-retry')){const kind=b.dataset.prRetry,t=tasks(selected())[kind];state.overrides[state.selected]={...state.overrides[state.selected],[kind]:{...t,status:'pending'}};refresh();}
    else if(b.hasAttribute('data-pr-generate')){state.message={title:'生成分析报告',copy:`为选中棋局生成${b.dataset.prGenerate==='normal'?'普通 500':'深度 2000'}报告。此确认只演示提交中状态；实际分析的费用由正式确认流程说明。`,confirm:b.dataset.prGenerate};refresh();}
    else if(b.hasAttribute('data-pr-confirm-generate')){const kind=b.dataset.prConfirmGenerate;state.overrides[state.selected]={...state.overrides[state.selected],[kind]:task('authorizing',0,selected().moves)};state.message=null;refresh();}
    else if(b.hasAttribute('data-pr-move')){const report=location.hash==='#review-report',key=report?'reportMove':'replayMove',n=state[key];state[key]=Math.max(0,Math.min(selected().moves,b.dataset.prMove==='first'?0:b.dataset.prMove==='last'?selected().moves:n+(b.dataset.prMove==='next'?1:-1)));updateBoard();}
    else if(b.hasAttribute('data-pr-toggle')){state[b.dataset.prToggle]=!state[b.dataset.prToggle];b.setAttribute('aria-pressed',state[b.dataset.prToggle]);updateBoard();}
    else if(b.hasAttribute('data-pr-import')){state.importOpen=true;go('review-import');}
    else if(b.hasAttribute('data-pr-close-import')){state.importOpen=false;go('review');}
    else if(b.hasAttribute('data-pr-album')){const old=document.querySelector('.pr-import-list').scrollTop;state.album=Number(b.dataset.prAlbum);refresh();document.querySelector('.pr-import-list').scrollTop=old;}
    else if(b.hasAttribute('data-pr-import-page')){state.importPage=Number(b.dataset.prImportPage);state.album=null;refresh();}
    else if(b.hasAttribute('data-pr-search')){e.preventDefault();search();}
    else if(b.hasAttribute('data-pr-clear')){state.draft='';state.query='';state.importPage=1;state.album=null;refresh();}
    else if(b.hasAttribute('data-pr-import-action')){const kind=b.dataset.prImportAction;state.message={title:'导入方式已选择 · 设计示意',copy:kind==='only'?'仅导入这局棋谱，不生成分析报告。当前预览没有实际导入。':`已选择导入并生成${kind==='normal'?'普通 500':'深度 2000'}报告。正式流程需确认分析费用；当前预览没有导入或生成任务。`};refresh();}
    else if(b.hasAttribute('data-pr-info')){const copy=infoCopy[b.dataset.prInfo];state.message={title:copy[0],copy:copy[1]};refresh();}
    else if(b.hasAttribute('data-pr-close-message')){state.message=null;refresh();}
    else if(b.hasAttribute('data-pr-report-tab')){state.reportTab=b.dataset.prReportTab;refresh();}
    else if(b.hasAttribute('data-pr-jump')){state.reportMove=Number(b.dataset.prJump);refresh();}
  });
})();
