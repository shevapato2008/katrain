(function () {
  const families = window.KioskDesignFamilies = window.KioskDesignFamilies || {};

  const paths = {
    info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v6m0-10h.01"/>',
    search: '<circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 5 5"/>',
    upload: '<path d="M12 16V3m-4 4 4-4 4 4M4 14v6h16v-6"/>',
    maximize: '<path d="M8 3H3v5m18 0V3h-5M3 16v5h5m8 0h5v-5"/>',
    first: '<path d="M5 4v16m14-16-8 8 8 8"/>',
    prev: '<path d="m15 4-8 8 8 8"/>',
    next: '<path d="m9 4 8 8-8 8"/>',
    last: '<path d="M19 4v16M5 4l8 8-8 8"/>',
    trash: '<path d="M4 6h16m-14 0 1 15h10l1-15M9 6V3h6v3m-5 4v7m4-7v7"/>',
    open: '<path d="M12 5H4v15h15v-8M10 14 21 3m-7 0h7v7"/>',
    save: '<path d="M4 3h14l3 3v15H3V3h1Zm3 0v7h10V3M7 21v-8h10v8"/>',
    clear: '<path d="m5 5 14 14M19 5 5 19"/>',
    cycle: '<path d="M20 6v5h-5M4 18v-5h5M5 9a8 8 0 0 1 14-2l1 2M4 15l1 2a8 8 0 0 0 14-2"/>',
    expand: '<path d="M4 8V4h4m12 4V4h-4M4 16v4h4m12-4v4h-4"/>',
    chevron: '<path d="m5 9 7 7 7-7"/>',
    physical: '<path d="M3 8h18v10H3zM7 18l-2 3m12-3 2 3M7 11h10M7 15h10M10 8v10m4-10v10"/><circle cx="19" cy="4" r="2"/>',
  };
  function ico(name, ctx) {
    if (!paths[name]) return ctx.I(name);
    return `<span class="u-report-icon"><svg viewBox="0 0 24 24" aria-hidden="true">${paths[name]}</svg></span>`;
  }
  function help(copy, label = '说明') {
    const safe = copy.replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;');
    return `<button type="button" class="u-report-info" aria-label="${label}" data-help="${safe}">${ico('info')}</button>`;
  }
  function reportDetailsButton() {
    return `<button type="button" class="u-report-info" aria-label="对局详情" data-report-details="true">${ico('info')}</button>`;
  }
  const demo = (name) => `这是 ${name} 的静态设计预览。实机功能与数据以当前应用为准。`;
  function action(label, icon, ctx, opts = {}) {
    const state = opts.selected ? ' is-on' : '';
    return `<button type="button" class="u-report-action${state}" ${opts.disabled ? 'disabled' : `data-help="${demo(label)}"`} aria-label="${label}">${ico(icon, ctx)}<span>${label}</span></button>`;
  }
  const reviewFixture = window.KioskReviewFixture;
  let reviewPage = 1;
  let selectedReviewId = reviewFixture.items[0]?.id;
  let openReviewMenu = null;
  const resultText = result => result === 'B+R' ? '黑胜中盘' : result === 'W+R' ? '白胜中盘' : result === 'B+F' ? '黑胜弃权' : result === 'W+F' ? '白胜弃权' : result === 'B+T' ? '黑胜超时' : result === 'W+T' ? '白胜超时' : /^B\+/.test(result||'') ? `黑胜 ${result.slice(2)} 目` : /^W\+/.test(result||'') ? `白胜 ${result.slice(2)} 目` : result || '结果未记录';
  const safe = value => String(value ?? '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/"/g,'&quot;');
  function reviewBoard(game) {
    const marks = [3,9,15].flatMap(x => [3,9,15].map(y => `<circle cx="${17+x*12.35}" cy="${17+y*12.35}" r="2.1" fill="#4a361d"/>`)).join('');
    const grid = Array.from({length:19},(_,i)=>{const p=(17+i*12.35).toFixed(2);return `<path d="M17 ${p}H239 M${p} 17V239"/>`;}).join('');
    const stones = game.stones.map(([x,y,c]) => `<circle cx="${17+x*12.35}" cy="${17+y*12.35}" r="5.8" fill="${c==='B'?'url(#review-black)':'url(#review-white)'}" stroke="${c==='B'?'#1a201c':'#d4d9d0'}" stroke-width=".65"/>`).join('');
    return `<div class="u-report-preview" role="img" aria-label="${safe(game.black)}对${safe(game.white)}的SGF终局，${game.moves}手"><svg viewBox="0 0 256 256" aria-hidden="true"><defs><radialGradient id="review-black" cx=".34" cy=".25"><stop stop-color="#626669"/><stop offset="1" stop-color="#070909"/></radialGradient><radialGradient id="review-white" cx=".34" cy=".25"><stop stop-color="#fff"/><stop offset="1" stop-color="#bbc0ba"/></radialGradient></defs><rect width="256" height="256" rx="3" fill="#b98a4b"/><rect x="8" y="8" width="240" height="240" fill="#bc9154" stroke="#7f5a2e" stroke-width="7"/><g fill="none" stroke="#674625" stroke-width=".9">${grid}</g>${marks}${stones}</svg></div>`;
  }
  window.KioskFinalBoard = reviewBoard;
  function reviewPages() {
    const total = Math.max(1, Math.ceil(reviewFixture.items.length/reviewFixture.pageSize));
    return `<div class="u-report-review-pages"><span>每页 20 局</span><button type="button" aria-label="第一页" data-review-page="1" ${reviewPage===1?'disabled':''}>${ico('first')}</button><button type="button" aria-label="上一页" data-review-page="${Math.max(1,reviewPage-1)}" ${reviewPage===1?'disabled':''}>${ico('prev')}</button><output>${reviewPage} / ${total} 页</output><label>页码<input type="number" min="1" max="${total}" value="${reviewPage}" inputmode="numeric" aria-label="跳转到我的对局页码" data-review-page-input></label><button type="button" data-review-jump>跳转</button><button type="button" aria-label="下一页" data-review-page="${Math.min(total,reviewPage+1)}" ${reviewPage===total?'disabled':''}>${ico('next')}</button><button type="button" aria-label="最后一页" data-review-page="${total}" ${reviewPage===total?'disabled':''}>${ico('last')}</button></div>`;
  }
  const reportTier = (game, kind, visits) => {
    const state = game.reports?.[kind] || 'missing';
    const verb = state === 'completed' ? '查看' : state === 'pending' || state === 'running' ? '进行中' : '生成';
    return `<button type="button" role="menuitem" data-review-tier="${visits}" data-review-id="${game.id}" ${verb==='进行中'?'disabled':''}><strong>${verb}${kind==='normal'?'普通':'深度'}报告</strong><span>每手 ${visits} 次</span></button>`;
  };
  function review(ctx) {
    const selected = reviewFixture.items.find(game => game.id === selectedReviewId) || reviewFixture.items[0];
    const games = reviewFixture.items.slice((reviewPage-1)*reviewFixture.pageSize,reviewPage*reviewFixture.pageSize);
    const cards = games.map(game => `<div class="u-report-review-row u-game-card ${game.id===selected?.id?'is-selected':''}" data-review-row="${game.id}"><button type="button" class="u-report-review-select" data-review-select="${game.id}" aria-pressed="${game.id===selected?.id}" aria-label="预览${safe(game.title)}，${safe(game.black)}对${safe(game.white)}的终局"><span class="u-lib-record-kind">${ctx.I('kifu')}</span><span class="u-lib-record-title">${safe(game.title)}</span><span class="u-lib-record-meta">${safe(game.date)} · ${game.moves} 手</span><span class="u-lib-record-players"><span><i class="u-lib-stone black"></i>${safe(game.black)}</span><em>${safe(resultText(game.result))}</em><span>${safe(game.white)}<i class="u-lib-stone white"></i></span></span></button><button type="button" class="u-report-delete" data-review-delete="${game.id}" aria-label="删除${safe(game.title)}">${ico('trash')}</button></div>`).join('');
    if (!selected) return `<div class="u-report-review u-report-review-empty-state">暂无历史对局</div>`;
    return `<div class="u-report-review">
      <section class="u-report-review-left">
        <div class="u-report-review-lefthead"><strong>选中这一局</strong>${help('左侧棋盘按所选历史对局的 SGF 主线回放到终局。', '选中对局说明')}</div>
        ${reviewBoard(selected)}
        <div class="u-report-selected"><span>${safe(selected.black)} vs ${safe(selected.white)}</span><span>${selected.moves} 手</span></div>
        <div class="u-report-selection-actions"><button type="button" data-review-open="game">查看棋谱</button><div class="u-report-review-rowactions"><button type="button" class="u-report-review-report" data-review-menu="${selected.id}" aria-expanded="${openReviewMenu===selected.id}">分析报告 ${ico('chevron')}</button>${openReviewMenu===selected.id?`<div class="u-report-review-menu" role="menu">${reportTier(selected,'normal',500)}${reportTier(selected,'deep',2000)}</div>`:''}</div></div>
      </section>
      <div class="u-report-review-right">
        <section class="u-report-review-chart"><div class="u-report-review-heading"><strong>这一局的胜率</strong>${help('未取得对应分析时，不绘制胜率曲线；可以从所选对局卡片选择报告档位。', '胜率说明')}</div><div class="u-report-review-empty">选中对局暂无胜率数据</div></section>
        <section class="u-report-review-games"><div class="u-report-review-heading"><strong>历史对局</strong><span>共 ${reviewFixture.items.length} 局</span><button type="button" data-review-search="true" aria-label="筛选和搜索历史对局">${ico('search')}</button></div><div class="u-report-review-scroll">${cards}</div>${reviewPages()}</section>
      </div>
    </div>`;
  }

  const reportHelp = {
    recommend: '推荐度是 AI 对候选着点的选择倾向。目差和胜率以待落子方为基准；点按候选着法可预览变化。',
    trend: '绿线为黑方胜率，橙线为黑方领先目数。点击图表可跳到对应局面；没有分析的手数不补值。',
    brilliant: '妙手按 AI 深入计算后的结果评定。图中黑方在上、白方在下，可按棋局阶段和棋手筛选。',
    mistake: '失误按每手目损分级。黑方在上、白方在下；未评级表示上一手缺少足够分析。当前实机图标注第 49、71、76、78、85、86、87、88、89、96 手。',
    perf: '发挥水准从妙手到恶手分七档。黑白柱分别归一；未评级的手不计入。',
    match: 'AI 吻合度只统计可与 AI 比对的手数：一选、前三、其余。它不能单独作为棋力判断依据。',
  };
  const tabs = [['recommend','推荐'],['trend','走势'],['brilliant','妙手'],['mistake','失误'],['perf','发挥水准'],['match','AI吻合度']];
  function reportToolbar(tab, ctx) {
    return `<div class="u-report-tabs">${tabs.map(([id,label])=>`<button type="button" class="${id===tab?'is-on':''}" data-switch="report-${id}" aria-current="${id===tab?'page':'false'}">${label}</button>`).join('')}</div>`;
  }
  function chartCrop(ctx, kind, x, y, w, h, scale = 1, cropClass = '') {
    // CSS resolves url() inside a custom property relative to this stylesheet,
    // one directory deeper than the HTML document.
    const src = '../../../' + ctx.byId[`report-${kind}`].current;
    return `<div class="u-report-actual-chart ${cropClass}" style="--chart-url:url('${src}');--crop-x:-${Math.round(x*scale)}px;--crop-y:-${Math.round(y*scale)}px;background-size:${Math.round(1024*scale)}px ${Math.round(600*scale)}px;width:${Math.round(w*scale)}px;height:${Math.round(h*scale)}px" role="img" aria-label="实机${tabs.find(t=>t[0]===kind)[1]}分析图"></div>`;
  }
  function phaseFilters(_ctx, sides = false, stats = false) {
    const modal = '此筛选状态未取得 RK3562 实机截图；当前提案保留全盘采集画面。';
    const phase = ['全盘','布局','中盘','官子'].map((t,i)=>`<button type="button" class="${i===0?'is-on':''}" aria-pressed="${i===0}" ${i===0?'':`data-help="${modal}"`}>${t}</button>`).join('');
    const extra = stats ? ['统计','分布'] : sides ? ['双方','黑方','白方'] : [];
    return `<div class="u-report-filters"><div class="u-report-phase" role="group" aria-label="棋局阶段">${phase}</div>${extra.length?`<div class="u-report-side" role="group" aria-label="${stats?'视图':'棋手筛选'}">${extra.map((t,i)=>`<button type="button" class="${i===0?'is-on':''}" aria-pressed="${i===0}" ${i===0?'':`data-help="${modal}"`}>${t}</button>`).join('')}</div>`:''}</div>`;
  }
  function mistakeChart() {
    // Point positions are transcribed from the captured device image in pixel
    // coordinates. No exact fractional score loss is asserted by this preview.
    // Both markers and move-axis labels use the same screenshot-to-SVG x map.
    const dots = [
      [49,830,317,1,0,-9],[71,896,317,1,0,-9],
      [76,912,393,-1,-16,22],[78,918,392,-1,-15,-10],
      [85,938,322,1,24,-1],[86,941,392,-1,-10,-10],
      [87,944,306,1,0,-9],[88,947,403,-1,8,23],
      [89,950,262,1,20,6],[96,971,419,-1,8,-9]
    ];
    const x = sourceX => 44 + (sourceX - 671) * (381 / 315);
    const y = sourceY => 78 + (sourceY - 344) * .75;
    const stem = ([m,px,py,side,dx,dy]) => { const sx=x(px), sy=y(py); return `<line x1="${sx}" y1="78" x2="${sx}" y2="${sy}" stroke="${side>0?'#d79655':'#e14b4b'}" stroke-width="2.5"/><circle cx="${sx}" cy="${sy}" r="4.5" fill="${side>0?'#181a1b':'#f6f4ec'}" stroke="#e9eee9" stroke-width="1.5"/><text x="${sx+dx}" y="${sy+dy}" text-anchor="middle">${m}</text>`; };
    const ticks=[[1,671],[25,746],[50,829],[75,912],[100,986]].map(([n,px])=>`<text x="${x(px)}" y="149" text-anchor="middle">${n}</text>`).join('');
    return `<svg class="u-report-svgchart" viewBox="0 0 440 156" role="img" aria-label="依据实机截图点位重绘的全盘失误分布：第 49、71、76、78、85 至 89、96 手；纵轴为目损"><rect width="440" height="156" fill="#111b1a"/><g stroke="#263a30"><path d="M44 18H425M44 38H425M44 58H425M44 98H425M44 118H425M44 138H425"/></g><path d="M44 78H425" stroke="#355045" stroke-dasharray="4 4"/><g class="u-report-axis"><text x="2" y="21">黑 15</text><text x="13" y="41">10</text><text x="23" y="61">5</text><text x="23" y="81">0</text><text x="23" y="101">5</text><text x="13" y="121">10</text><text x="2" y="141">白 15</text></g>${dots.map(stem).join('')}${ticks}</svg>`;
  }
  function perfChart() {
    const rows=[['妙手',0,0],['最佳',23,13],['很好',5,7],['尚可',8,5],['小亏',7,12],['失误',5,6],['恶手',2,7]];
    const bp=[0,46,10,16,14,10,4], wp=[0,26,14,10,24,12,14];
    return `<div class="u-report-perf-chart" role="img" aria-label="实机全盘发挥水准：妙手 0/0，最佳 23/13，很好 5/7，尚可 8/5，小亏 7/12，失误 5/6，恶手 2/7"><div class="u-report-perf-legend"><span><i class="u-report-disc"></i>黑</span><span><i class="u-report-white-disc"></i>白</span></div><div class="u-report-perf-grid">${rows.map(([name,b,w],i)=>`<div><div class="u-report-perf-bars"><span style="--n:${b}" data-count="${b}"></span><span style="--n:${w}" data-count="${w}"></span></div><strong>${name}</strong><small><span>${bp[i]}%</span><span>${wp[i]}%</span></small></div>`).join('')}</div></div>`;
  }
  function matchChart() {
    const rows=[['走中 AI 一选',46,26,'#397f55'],['走进 AI 前三',66,42,'#42a956'],['不在 AI 前十选',14,46,'#cf741b']];
    return `<div class="u-report-match-chart">${rows.map(([label,b,w,color])=>`<div class="u-report-match-row"><strong>${label}</strong><div><span><i class="u-report-disc"></i><em><b style="width:${b}%;background:${color}"></b></em><output>${b}%</output></span><span><i class="u-report-white-disc"></i><em><b style="width:${w}%;background:${color}"></b></em><output>${w}%</output></span></div></div>`).join('')}</div>`;
  }
  function reportBody(tab, ctx) {
    if (tab === 'recommend') return `<div class="u-report-recommend"><div class="u-report-workhead"><strong>AI 推荐 · 黑方待落子</strong><span>第 100 手后</span></div><div class="u-report-tablehead"><span>着点</span><span>推荐度</span><span>目差</span><span>胜率</span></div><div class="u-report-candidates">${[['R12','74%','+47.1','100.0%'],['R10','13%','+43.3','100.0%'],['N9','11%','+44.6','100.0%'],['S11','1%','+43.9','100.0%'],['R8','1%','+44.8','100.0%']].map(r=>`<button type="button" data-help="${demo('候选着法预览')}"><span><i></i><span class="u-report-coordinate">${r[0]}</span></span><span>${r[1]}</span><span>${r[2]}</span><span>${r[3]}</span></button>`).join('')}</div></div>`;
    if (tab === 'trend') return `<div class="u-report-trend"><div class="u-report-metrics"><span>黑胜率 <strong>100.0%</strong></span><span>黑领先 <strong>+46.1 目</strong></span></div><div class="u-report-plot"><div class="u-report-ylabels"><span>100%</span><span>50%</span><span>0%</span></div>${chartCrop(ctx,'trend',613,261,342,174,.85)}<div class="u-report-right-axis"><span>+48</span><span>0</span><span>−48</span></div></div><div class="u-report-xlabels"><span>0</span><span>25</span><span>50</span><span>75</span><span>100 手</span></div></div>`;
    if (tab === 'brilliant') return `${phaseFilters(ctx,true)}<div class="u-report-no-results">暂无妙手</div>`;
    if (tab === 'mistake') return `${phaseFilters(ctx,true)}<div class="u-report-chart-frame">${mistakeChart()}</div>`;
    if (tab === 'perf') return `${phaseFilters(ctx)}<div class="u-report-chart-frame">${perfChart()}</div>`;
    return `${phaseFilters(ctx,false,true)}<div class="u-report-chart-frame">${matchChart()}</div>`;
  }
  function report(id, ctx) {
    const tab=id==='report'?'recommend':id.slice('report-'.length);
    return `<div class="u-report-rail"><div class="u-report-summary"><div class="u-report-summary-main"><button type="button" class="u-report-back" data-switch="review" aria-label="返回复盘">${ico('back',ctx)}<span>返回复盘</span></button><strong>本地对局 · 未记名</strong><button type="button" class="u-report-expand" data-expand="true" aria-label="放大分析工作区">${ico('expand')}</button>${reportDetailsButton()}</div><div class="u-report-score"><span><i class="u-report-disc"></i>黑方</span><strong>黑领先 46.1 目</strong><span>白方<i class="u-report-white-disc"></i></span></div><div class="u-report-scoreline"><span>黑胜率 100.0%</span><span>白胜率 0.0%</span></div></div>${reportToolbar(tab,ctx)}<div class="u-report-work analysis">${reportBody(tab,ctx)}</div><div class="u-report-actions">${[['试下','hand'],['领地','board'],['支招','hint'],['实体盘','physical'],['手数','numbers'],['坐标','grid']].map(([label,name])=>action(label,name,ctx,{selected:['领地','手数','坐标'].includes(label)})).join('')}</div><div class="u-report-playback">${[['first','回到开局'],['prev','上一手'],['playbtn','播放'],['next','下一手'],['last','跳到最后']].map(([name,label])=>`<button type="button" aria-label="${label}" ${name==='next'||name==='last'?'disabled':`data-help="${demo(label)}"`} class="${name==='playbtn'?'is-play':''}">${ico(name,ctx)}</button>`).join('')}<input type="range" min="0" max="100" value="100" aria-label="手数进度；静态设计预览不可拖动" disabled title="静态设计预览不可拖动；实机回放操作以当前应用为准"><output>100/100 手</output></div></div>`;
  }

  // Screen 16, analysed variant: same board/rail system as screen 20, with
  // professional metadata and the verified analysis snapshot for game 24171.
  let professionalTab = 'recommend';
  function professionalBody(tab) {
    const rows = window.KioskKifuFixture.analysed.analysis;
    const first = rows[0];
    if (tab === 'recommend') {
      const top = first.top || [];
      const sum = top.reduce((n, candidate) => n + (candidate.psv || 0), 0);
      return `<div class="u-report-recommend"><div class="u-report-workhead"><strong>AI 推荐 · 黑方待落子</strong><span>第 0 手后</span></div><div class="u-report-tablehead"><span>着点</span><span>推荐度</span><span>目差</span><span>胜率</span></div><div class="u-report-candidates">${top.map(candidate => `<button type="button" data-help="${demo('候选着法预览')}"><span><i></i><span class="u-report-coordinate">${candidate.move}</span></span><span>${sum ? Math.round(candidate.psv/sum*100) : 0}%</span><span>${candidate.score >= 0 ? '+' : ''}${candidate.score.toFixed(1)}</span><span>${(candidate.winrate*100).toFixed(1)}%</span></button>`).join('')}</div></div>`;
    }
    if (tab === 'trend') {
      const points = rows.filter(row => Number.isFinite(row.winrate)).map(row => `${(row.n/211*284+3).toFixed(1)},${(138-row.winrate*130).toFixed(1)}`).join(' ');
      return `<div class="u-report-trend u-report-professional-trend"><div class="u-report-metrics"><span>黑棋胜率 <strong>${(first.winrate*100).toFixed(1)}%</strong></span><span>白棋领先 <strong>${Math.abs(first.score).toFixed(1)} 目</strong></span></div><svg viewBox="0 0 300 146" role="img" aria-label="真实职业棋局 211 手黑方胜率走势"><g stroke="#355341" stroke-dasharray="4 4"><path d="M3 8H287M3 73H287M3 138H287"/></g><polyline points="${points}" fill="none" stroke="#6bd293" stroke-width="2.5"/></svg><div class="u-report-professional-axis"><span>0</span><span>50</span><span>100</span><span>150</span><span>211 手</span></div></div>`;
    }
    return `<div class="u-report-no-results">该分项图表未收录在本次设计快照中</div>`;
  }
  function professionalReport(ctx) {
    const game = window.KioskKifuFixture.analysed;
    const first = game.analysis[0];
    const scoreSide = first.score < 0 ? '白' : '黑';
    const proTabs = `<div class="u-report-tabs">${tabs.map(([id,label]) => `<button type="button" class="${id===professionalTab?'is-on':''}" data-pro-report-tab="${id}" aria-current="${id===professionalTab?'page':'false'}">${label}</button>`).join('')}</div>`;
    return `<div class="u-lib-professional-board"><img src="${ctx.root+ctx.byId['kifu-report'].current}" alt="已分析职业棋局的第 0 手棋盘"></div><div class="u-report-rail u-report-professional"><div class="u-report-summary"><div class="u-report-summary-main"><button type="button" class="u-report-back" data-switch="kifu" aria-label="返回棋谱">${ico('back',ctx)}<span>返回棋谱</span></button><strong>职业棋局报告</strong>${help(`${game.event}。${game.black}执黑，${game.white}执白，${game.date}，${game.moves}手，黑胜中盘。规则待核验，贴目${game.komi}目。`, '棋局详情')}</div><div class="u-report-score"><span><i class="u-report-disc"></i>${game.black}</span><strong>${scoreSide}领先 ${Math.abs(first.score).toFixed(1)} 目</strong><span>${game.white}<i class="u-report-white-disc"></i></span></div><div class="u-report-scoreline"><span>黑胜率 ${(first.winrate*100).toFixed(1)}%</span><span>白胜率 ${((1-first.winrate)*100).toFixed(1)}%</span></div></div>${proTabs}<div class="u-report-work analysis">${professionalBody(professionalTab)}</div><div class="u-report-actions">${[['试下','hand'],['领地','board'],['支招','hint'],['实体盘','physical'],['手数','numbers'],['坐标','grid']].map(([label,name])=>action(label,name,ctx,{selected:['支招','手数','坐标'].includes(label)})).join('')}</div><div class="u-report-playback">${[['first','回到开局'],['prev','上一手'],['playbtn','播放'],['next','下一手'],['last','跳到最后']].map(([name,label])=>`<button type="button" aria-label="${label}" ${name==='first'||name==='prev'?'disabled':`data-help="${demo(label)}"`} class="${name==='playbtn'?'is-play':''}">${ico(name,ctx)}</button>`).join('')}<input type="range" min="0" max="${game.moves}" value="0" aria-label="手数进度；静态设计预览不可拖动" disabled><output>0/${game.moves} 手</output></div></div>`;
  }

  function research(ctx) {
    return `<div class="u-report-research"><div class="u-report-research-head"><button type="button" data-switch="play" aria-label="返回对弈">${ico('back',ctx)}<span>返回对弈</span></button><strong>研究 · 第 0 手</strong><button type="button" data-help="${demo('领地显示')}" aria-label="领地">${ico('board',ctx)}</button></div><div class="u-report-research-tools" role="group" aria-label="编辑工具">${[['交替','cycle'],['摆黑','board'],['摆白','board'],['删除','trash']].map(([label,name],i)=>`<button type="button" ${i===0?'':`data-help="${demo(label)}；当前仍显示实机采集的交替状态。"`} class="${i===0?'is-on':''}" aria-pressed="${i===0}">${i===1?'<i class="u-report-disc"></i>':i===2?'<i class="u-report-white-disc"></i>':ico(name,ctx)}<span>${label}</span></button>`).join('')}</div><div class="u-report-research-meta"><span>交替 · 中国规则 · 贴目 7.5</span>${help('研究棋盘可交替落子、指定摆黑或摆白、删除棋子。当前规则为中国规则，贴目 7.5；这局的 AI 推荐正在计算。', '研究规则说明')}</div><div class="u-report-research-fold"><button type="button" class="u-report-research-foldhead" data-research-fold="true" aria-expanded="true">${ico('chevron')}<strong>AI 推荐 · 第 0 手之后</strong><span class="u-report-fold-minus">−</span></button><div class="u-report-research-pending">正在算这一手</div></div><div class="u-report-research-nav">${[['first','回到开局'],['prev','上一手'],['next','下一手'],['last','跳到最后']].map(([name,label])=>`<button type="button" aria-label="${label}" disabled>${ico(name)}</button>`).join('')}</div><div class="u-report-research-actions">${[['打开','upload'],['保存','save'],['停一手','hand'],['清空','clear'],['全局分析','search']].map(([label,name])=>action(label,name,ctx)).join('')}</div></div>`;
  }
  families.review = (_s,ctx) => review(ctx);
  families['kifu-report'] = (_s,ctx) => professionalReport(ctx);
  families.research = (_s,ctx) => research(ctx);
  families.report = (s,ctx) => report(s.id,ctx);
  for (const [id] of tabs) families[`report-${id}`] = (s,ctx) => report(s.id,ctx);

  window.KioskReportInit = () => {
    const strip = document.querySelector('#stage .u-report-tabs');
    const active = strip?.querySelector('.is-on');
    if (!active) return;
    strip.scrollLeft = active.offsetLeft - strip.offsetLeft - (strip.clientWidth - active.clientWidth) / 2;
  };

  function detailsModal() {
    const tab = document.querySelector('#stage .u-report-tabs>.is-on')?.getAttribute('data-switch')?.slice(7) || 'recommend';
    return `<div class="modal u-report-modal"><div role="dialog" aria-modal="true" aria-label="对局详情"><h3>对局详情</h3><dl><div><dt>对局</dt><dd>本地对局 · 未记名</dd></div><div><dt>结果</dt><dd>黑方胜 49.3 子</dd></div><div><dt>规则</dt><dd>中国规则 · 贴目 7.5</dd></div><div><dt>报告</dt><dd>已完成 · 标准档</dd></div></dl><p>每手计算 500 次。${reportHelp[tab] || ''}</p><p>研究画面单独采集；跳转后显示第 0 手的实机状态。</p><div class="u-report-modal-actions"><button type="button" data-report-go="research">去研究</button><button type="button" data-report-retry="true">重算</button><button type="button" data-close-help="true">关闭</button></div></div></div>`;
  }
  function retryPreview() {
    return `<div class="modal u-report-modal"><div role="dialog" aria-modal="true" aria-label="重算预览"><h3>重算</h3><p>实机的重算确认状态尚未采集。这是设计预览，不会提交分析任务，也不会写入设备。</p><div class="u-report-modal-actions"><button type="button" data-close-help="true">知道了</button></div></div></div>`;
  }
  function uncapturedPreview(title, copy) {
    return `<div class="modal u-report-modal"><div role="dialog" aria-modal="true" aria-label="${title}"><h3>${title}</h3><p>${copy}</p><div class="u-report-modal-actions"><button type="button" data-close-help="true">知道了</button></div></div></div>`;
  }
  function deleteReviewPreview(game) {
    return `<div class="modal u-report-modal"><div role="dialog" aria-modal="true" aria-label="确认删除棋局"><h3>删除这局棋？</h3><p>${safe(game.black)} 对 ${safe(game.white)} · ${safe(game.date)}。确认后，棋局和关联的普通、深度分析报告都会删除。</p><div class="u-report-modal-actions"><button type="button" data-close-help="true">取消</button><button type="button" data-review-delete-confirm="${safe(game.id)}">删除棋局</button></div></div></div>`;
  }
  document.addEventListener('click', (event) => {
    if (event.target.closest('#stage [data-report-details]')) {
      document.getElementById('modal-root').innerHTML = detailsModal();
    } else if (event.target.closest('#modal-root [data-report-go]')) {
      document.getElementById('modal-root').innerHTML = '';
      document.querySelector('.chooser button[data-id="research"]')?.click();
    } else if (event.target.closest('#modal-root [data-report-retry]')) {
      document.getElementById('modal-root').innerHTML = retryPreview();
    } else if (event.target.closest('#stage [data-review-search]')) {
      document.getElementById('modal-root').innerHTML = uncapturedPreview('搜索历史对局', '实机搜索与筛选窗口尚未采集。页面保留真实的搜索入口；当前设计预览不会生成搜索结果。');
    } else if (event.target.closest('#stage [data-review-open]')) {
      document.getElementById('modal-root').innerHTML = uncapturedPreview('查看棋谱', '正式页面会打开左侧选中棋局的逐手棋谱；此设计预览只采集到终局。');
    } else if (event.target.closest('#stage [data-review-delete]')) {
      const game = reviewFixture.items.find(item => item.id === event.target.closest('[data-review-delete]').dataset.reviewDelete);
      if (game) document.getElementById('modal-root').innerHTML = deleteReviewPreview(game);
    } else if (event.target.closest('#modal-root [data-review-delete-confirm]')) {
      const id = event.target.closest('[data-review-delete-confirm]').dataset.reviewDeleteConfirm;
      const index = reviewFixture.items.findIndex(item => item.id === id);
      if (index !== -1) {
        reviewFixture.items.splice(index, 1);
        reviewFixture.total = reviewFixture.items.length;
        reviewPage = Math.min(reviewPage, Math.max(1, Math.ceil(reviewFixture.items.length/reviewFixture.pageSize)));
        selectedReviewId = reviewFixture.items[(reviewPage-1)*reviewFixture.pageSize]?.id || reviewFixture.items[0]?.id;
        openReviewMenu = null;
      }
      document.getElementById('modal-root').innerHTML = '';
      document.querySelector('.chooser button[data-id="review"]')?.click();
    } else if (event.target.closest('#stage [data-review-jump]')) {
      const input = document.querySelector('#stage [data-review-page-input]');
      const total = Math.max(1, Math.ceil(reviewFixture.items.length/reviewFixture.pageSize));
      const page = Number(input?.value);
      if (!Number.isInteger(page) || page < 1 || page > total) { input?.reportValidity(); return; }
      reviewPage = page;
      selectedReviewId = reviewFixture.items[(page-1)*reviewFixture.pageSize]?.id || selectedReviewId;
      openReviewMenu = null;
      document.querySelector('.chooser button[data-id="review"]')?.click();
    } else if (event.target.closest('#stage [data-pro-report-tab]')) {
      professionalTab = event.target.closest('[data-pro-report-tab]').dataset.proReportTab;
      document.querySelector('.chooser button[data-id="kifu-report"]')?.click();
    } else if (event.target.closest('#stage [data-review-page]')) {
      reviewPage = Number(event.target.closest('[data-review-page]').dataset.reviewPage);
      openReviewMenu = null;
      selectedReviewId = reviewFixture.items[(reviewPage-1)*reviewFixture.pageSize]?.id || selectedReviewId;
      document.querySelector('.chooser button[data-id="review"]')?.click();
    } else if (event.target.closest('#stage [data-review-tier]')) {
      const tier = Number(event.target.closest('[data-review-tier]').dataset.reviewTier);
      const game = reviewFixture.items.find(item => item.id === event.target.closest('[data-review-tier]').dataset.reviewId);
      const kind = tier === 500 ? 'normal' : 'deep';
      const completed = game?.reports?.[kind] === 'completed';
      document.getElementById('modal-root').innerHTML = uncapturedPreview(`${completed?'查看':'生成'}${tier === 500 ? '普通' : '深度'}报告 · ${tier} 次`, `${game?.black || '所选棋手'}对${game?.white || '所选棋手'}，每手最多计算 ${tier} 次。${completed?'正式页面会打开已有报告。':'这是设计预览，不会提交报告任务。'}`);
      openReviewMenu = null;
    } else if (event.target.closest('#stage [data-review-menu]')) {
      const oldScroll = document.querySelector('#stage .u-report-review-scroll')?.scrollTop || 0;
      const id = event.target.closest('[data-review-menu]').dataset.reviewMenu;
      openReviewMenu = openReviewMenu === id ? null : id;
      document.querySelector('.chooser button[data-id="review"]')?.click();
      const list = document.querySelector('#stage .u-report-review-scroll');
      if (list) list.scrollTop = oldScroll;
    } else if (event.target.closest('#stage [data-review-select]')) {
      const oldScroll = document.querySelector('#stage .u-report-review-scroll')?.scrollTop || 0;
      selectedReviewId = event.target.closest('[data-review-select]').dataset.reviewSelect;
      openReviewMenu = null;
      document.querySelector('.chooser button[data-id="review"]')?.click();
      const list = document.querySelector('#stage .u-report-review-scroll');
      if (list) list.scrollTop = oldScroll;
    } else if (event.target.closest('#stage [data-research-fold]')) {
      const button = event.target.closest('[data-research-fold]');
      const fold = button.closest('.u-report-research-fold');
      const collapsed = fold.classList.toggle('is-collapsed');
      button.setAttribute('aria-expanded', String(!collapsed));
    }
  });

}());
