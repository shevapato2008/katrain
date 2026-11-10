(function () {
  const iconPaths = {
    info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v6M12 7h.01"/>',
    search: '<circle cx="10.8" cy="10.8" r="6.8"/><path d="m16 16 5 5"/>',
    next: '<path d="m9 5 7 7-7 7"/>',
    book: '<path d="M12 6c-3-3-6-3-10-2v15c4-1 7-1 10 2 3-3 6-3 10-2V4c-4-1-7-1-10 2ZM12 6v15"/>',
    video: '<rect x="3" y="5" width="18" height="14" rx="2"/><path d="m10 9 5 3-5 3z"/>',
    reset: '<path d="M3 12a9 9 0 1 0 3-6.7M3 4v5h5"/>',
    check: '<path d="m4 12 5 5L20 6"/>',
    pause: '<path d="M8 5v14M16 5v14"/>',
    sliders: '<path d="M4 7h16M4 17h16M8 4v6m8 4v6"/>',
    first: '<path d="M5 5v14m11-14-7 7 7 7"/>',
    prev: '<path d="m15 5-7 7 7 7"/>',
    last: '<path d="M19 5v14M8 5l7 7-7 7"/>',
    expand: '<path d="M4 9V4h5m6 0h5v5m0 6v5h-5m-6 0H4v-5"/>',
    minus: '<path d="M5 12h14"/>',
    plus: '<path d="M5 12h14M12 5v14"/>',
    physical: '<path d="M3 8h18v10H3zM7 18l-2 3m12-3 2 3M7 11h10M7 15h10M10 8v10m4-10v10"/><circle cx="19" cy="4" r="2"/>',
  };
  const icon = name => `<svg class="u-lib-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${iconPaths[name] || iconPaths.book}</svg>`;
  const attr = s => String(s).replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;');
  const help = copy => `<button type="button" class="u-lib-info" data-help="${attr(copy)}" aria-label="说明">${icon('info')}</button>`;
  const button = (label, image, switchTo, extra = '', disabled = false, pressed = false, extraAttrs = '') => `<button type="button" class="u-lib-button ${extra}" ${switchTo ? `data-switch="${switchTo}"` : ''} ${disabled ? 'disabled aria-disabled="true"' : ''} ${pressed ? 'aria-pressed="true"' : ''} ${extraAttrs}>${image || ''}<span>${label}</span></button>`;
  const back = (label, id, I) => button(`返回${label}`, I('back'), id, 'u-lib-back');
  const shot = (ctx, id) => ctx.root + ctx.byId[id].current;
  const board = (ctx, id) => `<div class="u-lib-board" aria-label="实机棋盘"><img src="${shot(ctx, id)}" alt="实机棋盘位置与尺寸"></div>`;
  const status = (a, b, tone) => `<div class="u-lib-status"><span>${a}</span><strong class="${tone}">${b}</strong></div>`;
  const mirror = (ctx, id, caption) => `<aside class="u-lib-mirror"><div class="u-lib-mirror-title">实体棋盘${help('左侧保留实机的实体盘预览。当前摄像头未连接，标定尚未完成，棋盘识别不可用。')}</div><div class="u-lib-preview"><img src="${shot(ctx, id)}" alt="实机实体盘空盘预览"></div><div class="u-lib-mirror-line"><span>${caption}</span><strong>暂不可用</strong></div><div class="u-lib-mirror-status">${status('摄像头', '未连接', 'bad')}${status('标定', '需校准', 'warn')}${status('LED', '未连接', 'warn')}</div></aside>`;
  const tabs = (name, labels, panes, current = 0) => `<div class="u-lib-switch">${labels.map((_, i) => `<input class="u-lib-radio" type="radio" name="u-lib-${name}" id="u-lib-${name}-${i}" ${i === current ? 'checked' : ''}>`).join('')}<div class="u-lib-tabs" role="tablist">${labels.map((label, i) => `<label for="u-lib-${name}-${i}" role="tab">${label}</label>`).join('')}</div><div class="u-lib-panes">${panes.map(p => `<div class="u-lib-pane">${p}</div>`).join('')}</div></div>`;

  let showBookChaptersOnNextRender = false;
  const uncapturedKifuPage = attr('本次只采集到棋谱库前两页。后续页内容未采集，不能在此提案中展示。');
  const uncapturedReportMove = attr('当前只采集到报告第 0 手盘面。逐手变化尚未采集。');
  const uncapturedSectionMove = attr('当前只采集到这张棋图的第 2 手盘面。退一手后的盘面未采集。');
  const kifuFixture = window.KioskKifuFixture;
  let kifuPage = 1;
  let selectedKifuId = kifuFixture.page1[0].id;
  let detailMove = kifuFixture.unanalysed.moves;
  const kifuResult = result => result === 'B+R' ? '黑胜中盘' : result === 'W+R' ? '白胜中盘' : result === 'B+T' ? '黑胜超时' : result === 'W+T' ? '白胜超时' : result === 'B+F' ? '黑胜弃权' : result === 'W+F' ? '白胜弃权' : result || '结果待核验';
  const sgfMoves = [...kifuFixture.unanalysed.sgf.matchAll(/;([BW])\[([a-s]{2})\]/g)].map(([, color, point]) => ({ color, x: point.charCodeAt(0) - 97, y: point.charCodeAt(1) - 97 }));
  function kifuBoardAt(moveNumber) {
    const cells = Array(361).fill(null);
    const neighbors = n => [n % 19 ? n - 1 : -1, n % 19 < 18 ? n + 1 : -1, n >= 19 ? n - 19 : -1, n < 342 ? n + 19 : -1].filter(x => x >= 0);
    const group = start => {
      const seen = new Set([start]), stack = [start]; let liberty = false;
      while (stack.length) for (const n of neighbors(stack.pop())) {
        if (!cells[n]) liberty = true;
        else if (cells[n] === cells[start] && !seen.has(n)) { seen.add(n); stack.push(n); }
      }
      return { seen, liberty };
    };
    for (const m of sgfMoves.slice(0, moveNumber)) {
      const n = m.y * 19 + m.x;
      if (cells[n]) continue;
      cells[n] = m.color;
      for (const adjacent of neighbors(n)) if (cells[adjacent] && cells[adjacent] !== m.color) {
        const captured = group(adjacent);
        if (!captured.liberty) for (const stone of captured.seen) cells[stone] = null;
      }
    }
    return cells;
  }
  function kifuPositionSvg(moveNumber) {
    const cells = kifuBoardAt(moveNumber), o = 34, step = 25;
    const grid = Array.from({ length: 19 }, (_, i) => `<path d="M${o} ${o+i*step}H${o+18*step} M${o+i*step} ${o}V${o+18*step}"/>`).join('');
    const stars = [3,9,15].flatMap(x => [3,9,15].map(y => `<circle cx="${o+x*step}" cy="${o+y*step}" r="2.9" fill="#4e351b"/>`)).join('');
    const stones = cells.map((c, n) => c ? `<circle cx="${o+n%19*step}" cy="${o+Math.floor(n/19)*step}" r="11.6" fill="url(#kifu-${c})" stroke="${c==='B'?'#17201a':'#d8ddd6'}" stroke-width="1.3"/>` : '').join('');
    const letters = 'ABCDEFGHJKLMNOPQRST';
    const labels = Array.from({ length: 19 }, (_, i) => `<text x="${o+i*step}" y="18" text-anchor="middle">${letters[i]}</text><text x="${o+i*step}" y="505" text-anchor="middle">${letters[i]}</text><text x="15" y="${o+i*step+5}" text-anchor="middle">${19-i}</text><text x="501" y="${o+i*step+5}" text-anchor="middle">${19-i}</text>`).join('');
    return `<svg class="u-lib-sgf-board" viewBox="0 0 516 516" role="img" aria-label="谢依旻对柳原咲辉，第 ${moveNumber} 手棋盘"><defs><linearGradient id="kifu-wood" x2=".8" y2="1"><stop stop-color="#d9a962"/><stop offset=".5" stop-color="#e6ba70"/><stop offset="1" stop-color="#c58d48"/></linearGradient><radialGradient id="kifu-B" cx=".34" cy=".25" r=".78"><stop stop-color="#52565a"/><stop offset=".65" stop-color="#191b1b"/><stop offset="1" stop-color="#080a0a"/></radialGradient><radialGradient id="kifu-W" cx=".34" cy=".25" r=".8"><stop stop-color="#fff"/><stop offset=".72" stop-color="#f0f1eb"/><stop offset="1" stop-color="#b4b9b4"/></radialGradient></defs><rect width="516" height="516" rx="9" fill="#79502b"/><rect x="22" y="22" width="472" height="472" fill="url(#kifu-wood)"/><g stroke="#674923" stroke-width="1">${grid}</g>${stars}${stones}<g fill="#e9c997" font-family="Kiosk Plex Mono,monospace" font-size="14">${labels}</g></svg>`;
  }
  const paginationButton = (name, iconName, target, disabled = false) => `<button type="button" class="u-lib-page-icon" aria-label="${name}" ${disabled ? 'disabled' : `data-lib-page="${target}"`}>${icon(iconName)}</button>`;
  function kifuPagination() {
    return `<div class="u-lib-page" aria-label="棋谱库分页"><span class="u-lib-page-total">每页 20 局</span>${paginationButton('第一页','first',1,kifuPage===1)}${paginationButton('上一页','prev',kifuPage-1,kifuPage===1)}<span class="u-lib-page-current">${kifuPage} / 8551 页</span><label class="u-lib-page-go">页码<input type="number" min="1" max="8551" value="${kifuPage}" inputmode="numeric" aria-label="跳转到棋谱库页码" data-lib-page-input></label><button type="button" class="u-lib-page-number" data-lib-jump>跳转</button>${paginationButton('下一页','next',kifuPage+1)}${paginationButton('最后一页','last',8551)}</div>`;
  }
  function kifu(ctx) {
    const records = kifuPage === 2 ? kifuFixture.page2 : kifuFixture.page1;
    const selected = records.find(r => r.id === selectedKifuId) || records[0];
    selectedKifuId = selected.id;
    const stones = window.KioskKifuPositions?.[selected.id];
    const preview = `<aside class="u-lib-kifu-selection"><div class="u-lib-mirror-title">选中这一局${help('点按右侧棋谱卡片，在这里预览该局的终局。')}</div>${Array.isArray(stones) ? window.KioskFinalBoard({...selected, stones}) : '<div class="u-lib-preview-unavailable">这局的终局棋盘暂未采集</div>'}<div class="u-lib-kifu-selected-name">${selected.black} vs ${selected.white}<span>${selected.moves} 手</span></div><div class="u-lib-kifu-selected-result">${selected.date} · ${kifuResult(selected.result)}</div><div class="u-lib-selection-actions"><button type="button" class="u-lib-button" data-lib-open="detail">查看棋谱</button><button type="button" class="u-lib-button" data-lib-open="report" ${selected.hasAnalysis ? '' : 'disabled aria-disabled="true"'}>查看分析</button></div></aside>`;
    const list = `<label class="u-lib-search">${icon('search')}<input type="search" aria-label="搜索棋谱" placeholder="棋手、赛事、年份都能搜" readonly data-help="${attr('搜索结果未采集；此提案只展示实机采集到的前两页。')}"></label><div class="u-lib-records" aria-label="第 ${kifuPage} 页，每页 20 局">${records.map(r => `<button type="button" class="u-lib-record u-game-card ${r.id===selected.id?'is-selected':''}" data-lib-select="${r.id}" aria-pressed="${r.id===selected.id}"><span class="u-lib-record-kind">${ctx.I(r.hasAnalysis ? 'chart' : 'kifu')}</span><span class="u-lib-record-title">${r.event}</span><span class="u-lib-record-meta">${r.date} · ${r.moves} 手</span><span class="u-lib-record-players"><span><i class="u-lib-stone black"></i>${r.black}</span><em>${kifuResult(r.result)}</em><span class="u-lib-white-player">${r.white}<i class="u-lib-stone white"></i></span></span></button>`).join('')}</div>${kifuPagination()}`;
    const recent = `<div class="u-lib-empty"><strong>最近摆过 · 当前未采集</strong><span>此标签按盒子上的实际摆谱记录显示。</span></div>`;
    return `<div class="u-lib-l1">${preview}<main class="u-lib-l1-main"><div class="u-lib-l1-heading"><h2>职业棋谱</h2>${help('已收录的职业棋局。当前提案展示前两页真实快照，每页 20 局。')}</div><div class="u-lib-count">名局棋谱　<span>共 171,013 局</span></div>${tabs('kifu', ['名局棋谱', '最近摆过'], [list, recent])}</main></div>`;
  }

  function detail(ctx) {
    const d = kifuFixture.unanalysed;
    const recent = sgfMoves.slice(-6).reverse().map((m, index) => `<span><b>${d.moves-index}</b><i class="u-lib-stone ${m.color==='B'?'black':'white'}"></i>${'ABCDEFGHJKLMNOPQRST'[m.x]}${19-m.y}</span>`).join('');
    return `<div class="u-lib-l2 u-lib-unanalysed"><div class="u-lib-static-board" data-kifu-board>${kifuPositionSvg(detailMove)}</div><main class="u-lib-rail"><div class="u-lib-detail-head">${back('棋谱', 'kifu', ctx.I)}<h2>职业棋谱</h2>${help('真实未分析棋局：第2届日本女子围棋联赛第1轮，谢依旻对柳原咲辉，2026-01-10，185手，黑胜中盘。')}</div><div class="u-lib-kifu-match"><strong>${d.event}</strong><div><span><i class="u-lib-stone black"></i>${d.black}</span><em>对</em><span>${d.white}<i class="u-lib-stone white"></i></span></div><small>${d.date} · ${d.moves} 手 · ${kifuResult(d.result)}</small></div><div class="u-lib-kifu-pending"><strong>尚未分析</strong><span>这局的棋谱已经收录，可以逐手查看。胜率、推荐和失误需要分析后才会显示。</span></div><div class="u-lib-kifu-moves"><div><strong>最近落子</strong><span>第 <output data-kifu-move-output>${detailMove}</output> / ${d.moves} 手</span></div><div class="u-lib-kifu-move-grid">${recent}</div></div><div class="u-lib-kifu-action">${button('实体盘', icon('physical'), 'baipu', '', false, false, `data-help="${attr('摆到实体盘前需连接摄像头并完成标定。')}"`)}</div><div class="u-lib-kifu-playback"><button type="button" aria-label="回到开局" data-kifu-move="first">${icon('first')}</button><button type="button" aria-label="上一手" data-kifu-move="prev">${icon('prev')}</button><input type="range" min="0" max="${d.moves}" value="${detailMove}" aria-label="棋谱手数" data-kifu-range><button type="button" aria-label="下一手" data-kifu-move="next">${icon('next')}</button><button type="button" aria-label="跳到终局" data-kifu-move="last">${icon('last')}</button></div></main></div>`;
  }
  function baipu(ctx) {
    return `<div class="u-lib-baipu"><input class="u-lib-view-radio" id="u-lib-view-raw" type="radio" name="u-lib-baipu-view" checked><input class="u-lib-view-radio" id="u-lib-view-warped" type="radio" name="u-lib-baipu-view"><div class="u-lib-baipu-head">${back('棋谱', 'kifu', ctx.I)}<h2>先标定棋盘</h2><div class="u-lib-view-toggle" role="group" aria-label="画面"><label for="u-lib-view-raw">原始画面</label><label for="u-lib-view-warped">俯视矫正</label></div>${help('摆谱需要先让摄像头看清棋盘。标定完成后才能进入摆谱主界面。当前实机只采集到标定门槛。')}</div><div class="u-lib-baipu-body"><div class="u-lib-calib-preview"><strong class="u-lib-raw-message">画面重建中…</strong><strong class="u-lib-warped-message">完成 LED 标定后生成俯视画面</strong><span>共 5 个定位点 · 四角和天元</span></div><div class="u-lib-calib-rail"><div class="u-lib-calib-status">${status('摄像头', '未连接', 'bad')}${status('标定', '未标定', 'warn')}${status('LED', '未连接', 'warn')}</div><div class="u-lib-steps">${[['1', '等待棋盘稳定', '进行中'], ['2', '确认并锁定曝光', '未开始'], ['3', '定位棋盘', '未开始'], ['4', '生成空盘基线', '未开始']].map(x => `<div class="u-lib-step ${x[0] === '1' ? 'is-current' : ''}"><b>${x[0]}</b><span>${x[1]}</span><em>${x[2]}</em></div>`).join('')}</div><div class="u-lib-calib-help"><strong>LED 只在你按下之后才亮，不会自动点亮 LED</strong><span>摄像头未连接 · 标定暂不能开始</span>${help('摄像头未连接且 LED 未连接，当前不能重新开始标定。失败时查看诊断；不要自行闪灯。')}</div>${button('重新开始标定', icon('reset'), '', 'u-lib-restart', true)}</div></div></div>`;
  }

  function replay(ctx) {
    return `<div class="u-lib-l2">${board(ctx, 'kifu-replay')}<main class="u-lib-rail"><div class="u-lib-replay-head">${back('棋谱', 'kifu', ctx.I)}<h2>棋谱回放</h2></div><div class="u-lib-loading" role="status"><strong>正在读这一局</strong><span>棋谱和逐手记录都要从服务器取。</span></div></main></div>`;
  }

  function courses(ctx) {
    const cats = [['入门', '围棋基础知识、规则与基本技巧 · 0 本'], ['布局', '开局阶段的战略与要点 · 5 本'], ['中盘', '中盘战斗、攻防与形势判断 · 1 本'], ['官子', '收官技巧与目数计算 · 3 本']];
    const category = `<div class="u-lib-cats">${cats.map((x, i) => `<button type="button" class="u-lib-cat" ${i === 1 ? 'data-switch="books"' : 'disabled aria-disabled="true"'}><span class="u-lib-ring">—</span><span><strong>${x[0]}</strong><em>${x[1]}</em></span>${i === 1 ? icon('next') : ''}</button>`).join('')}</div>`;
    const anatomy = `<div class="u-lib-anatomy">${[['书', '一本书', '分若干章'], ['章', '一章讲一块', '比如“吃子”'], ['节', '节才是“一课”', '翻完这一节的图就算看完'], ['图', '每张图带讲解', '可摆到实体盘上']].map(x => `<div><b>${x[0]}</b><strong>${x[1]}</strong><span>${x[2]}</span></div>`).join('')}</div>`;
    return `<div class="u-lib-l1">${mirror(ctx, 'courses', '课上的图会摆到盘上')}<main class="u-lib-l1-main"><div class="u-lib-l1-heading"><h2>课程</h2>${help('课程按分类、书、章、节、图五层组织；内容从云端读取。当前仅采集到布局书单，其他分类详情未采集；进度没有可信数据时显示“—”。')}</div><div class="u-lib-count"><div class="u-lib-count-text">4 类 · 共 9 本</div></div>${tabs('courses', ['分类', '一课长什么样'], [category, anatomy])}</main></div>`;
  }

  function books(ctx, open) {
    const items = [['曹薰铉布局技巧（上）', '2 章'], ['曹薰铉布局技巧（下）', '2 章'], ['曹薰铉布局技巧（中）', '1 章'], ['曹薰铉布局技巧（五）', '2 章'], ['曹薰铉布局技巧（四）', '2 章']];
    const bookCards = `<div class="u-lib-book-grid">${items.map((x, i) => `<button type="button" class="u-lib-book-card ${i === 0 ? 'is-selected' : ''}" ${i === 0 ? 'data-lib-book-chapters="true"' : 'disabled aria-disabled="true"'}>${icon('book')}<span><strong>${x[0]}</strong><em>曹薰铉 · ${x[1]}</em></span></button>`).join('')}</div>`;
    const chapters = `<div class="u-lib-chapter-list"><div class="u-lib-chapter-title">曹薰铉布局技巧（上）　<span>2 章 · 46 节</span></div><button type="button" class="u-lib-chapter" data-switch="books-chapter-open"><strong>第一章　布局入门</strong><span>5 节 · 100 图</span>${icon('next')}</button><button type="button" class="u-lib-chapter" disabled aria-disabled="true"><strong>第二章　基本问题</strong><span>41 节 · 251 图</span></button></div>`;
    const sections = `<div class="u-lib-chapter-list"><div class="u-lib-chapter-title">第一章　布局入门　<span>5 节 · 100 图</span>${button('收起章节', icon('prev'), 'books', 'u-lib-collapse')}</div>${[['外势和实地', '10 图', true], ['角的周围', '22 图', true], ['拆', '30 图', true], ['提高布局', '18 图', false], ['布局补充', '20 图', false]].map((x, i) => `<button type="button" class="u-lib-section-row" ${i === 0 ? 'data-switch="section"' : 'disabled aria-disabled="true"'}><b>${i+1}</b><strong>${x[0]}</strong><span>${x[1]}</span>${x[2] ? '<em>有视频</em>' : ''}${i === 0 ? icon('next') : ''}</button>`).join('')}</div>`;
    const initialTab = open || showBookChaptersOnNextRender ? 1 : 0;
    if (!open) showBookChaptersOnNextRender = false;
    return `<div class="u-lib-books"><div class="u-lib-books-head">${back('课程', 'courses', ctx.I)}<h2>${open ? '曹薰铉布局技巧（上）' : '布局'}</h2><span>${open ? '第一章 · 布局入门' : '5 本 · 内容随云端同步'}</span>${open ? button('返回章节目录', icon('prev'), 'books', 'u-lib-return-chapters') : ''}${help('本次只采集到《曹薰铉布局技巧（上）》第一章、第一节的内容；其他书、章、节详情未采集。课程进度没有可靠数据。')}</div>${tabs(open ? 'booksopen' : 'books', ['选一本', '章节目录'], [bookCards, open ? sections : chapters], initialTab)}</div>`;
  }

  function section(ctx) {
    const explain = '在图里，黑棋下在 1 位的这手棋叫做三三点，就是第三条线和第三条线相交的地方。这两条线都是我们说的实地线。三三点的好处是比较容易做出眼形来活棋，不过它的不足之处在于朝着边上和中央发展的力量相对较弱。白棋的 2 位落在第四条线和第四条线的交点上，我们把这个位置叫做“星位”。';
    const figures = `<div class="u-lib-figures"><div class="u-lib-figure-grid">${Array.from({ length: 10 }, (_, i) => `<button type="button" class="${i === 0 ? 'is-selected' : ''}" data-help="${attr(i === 0 ? '图 1：2 手，43 秒，视频讲解。' : i === 1 ? '图 2：12 手，29 秒，视频讲解。此提案未采集第 2 图盘面。' : `图 ${i + 1} 的入口。此提案未采集该图盘面。`)}">图 ${i + 1}</button>`).join('')}</div><div class="u-lib-figure-current"><strong>图 1</strong><span>2 手 · 43 秒</span><em>视频讲解</em></div></div>`;
    return `<div class="u-lib-l2 u-lib-section"><input class="u-lib-board-view-radio" id="u-lib-board-part" type="radio" name="u-lib-board-view" checked><input class="u-lib-board-view-radio" id="u-lib-board-full" type="radio" name="u-lib-board-view">${board(ctx, 'section')}<main class="u-lib-rail"><div class="u-lib-section-head">${back('目录', 'books-chapter-open', ctx.I)}<h2>外势和实地</h2>${help(explain)}</div><div class="u-lib-section-meta"><span>第一章 · 第 1 节</span><strong>第 1 / 10 图</strong><div class="u-lib-section-view" role="group" aria-label="棋图范围"><label for="u-lib-board-part">局部</label><label for="u-lib-board-full">全盘</label></div></div>${tabs('section', ['这一节的图', '讲解'], [figures, `<div class="u-lib-explain">${explain}</div>`])}<div class="u-lib-moves"><div><strong>手数</strong><span>这张图共 2 手</span></div><div class="u-lib-step-control"><button type="button" aria-label="退一手" data-help="${uncapturedSectionMove}">${icon('minus')}</button><input type="range" min="0" max="2" value="2" aria-label="手数" data-lib-captured-value="2" data-help="${uncapturedSectionMove}"><button type="button" aria-label="进一手" disabled>${icon('plus')}</button></div><span>走到第 2 手</span></div><div class="u-lib-section-actions">${button('上一图', ctx.I('back'), '', 'is-muted', true)}${button('看视频讲解', icon('video'), '', '', false, false, `data-help="${attr('本节有视频讲解入口，但播放画面未采集。')}"`)}${button('下一图', icon('next'), '', '', false, false, `data-help="${attr('第 2 图盘面未采集；本页只展示第 1 图。')}"`)}</div></main></div>`;
  }

  window.KioskDesignFamilies = window.KioskDesignFamilies || {};
  Object.assign(window.KioskDesignFamilies, {
    kifu: (_, ctx) => kifu(ctx),
    'kifu-detail': (_, ctx) => detail(ctx),
    baipu: (_, ctx) => baipu(ctx),
    'kifu-replay': (_, ctx) => replay(ctx),
    courses: (_, ctx) => courses(ctx),
    books: (_, ctx) => books(ctx, false),
    'books-chapter-open': (_, ctx) => books(ctx, true),
    section: (_, ctx) => section(ctx),
  });
  document.addEventListener('click', event => {
    if (event.target.closest('.u-lib-return-chapters, .u-lib-collapse')) showBookChaptersOnNextRender = true;
  }, true);
  document.addEventListener('click', event => {
    const selection = event.target.closest('#stage [data-lib-select]');
    if (selection) {
      const scroll = document.querySelector('#stage .u-lib-records')?.scrollTop || 0;
      selectedKifuId = Number(selection.dataset.libSelect);
      document.querySelector('.chooser button[data-id="kifu"]')?.click();
      const records = document.querySelector('#stage .u-lib-records');
      if (records) records.scrollTop = scroll;
      return;
    }
    const open = event.target.closest('#stage [data-lib-open]');
    if (open) {
      const target = open.dataset.libOpen;
      if (target === 'report' && selectedKifuId === kifuFixture.analysed.id) {
        document.querySelector('.chooser button[data-id="kifu-report"]')?.click();
      } else if (target === 'detail' && selectedKifuId === kifuFixture.unanalysed.id) {
        document.querySelector('.chooser button[data-id="kifu-detail"]')?.click();
      } else {
        document.getElementById('modal-root').innerHTML = `<div class="modal"><div class="u-lib-expanded"><div class="u-lib-expanded-head"><strong>${target === 'report' ? '查看分析' : '查看棋谱'}</strong><button type="button" class="u-lib-button" data-close-help="true">关闭</button></div><p>所选棋局的详情页面尚未采集。正式页面将按当前选中的棋局打开。</p></div></div>`;
      }
      return;
    }
    const jump = event.target.closest('#stage [data-lib-jump]');
    if (jump) {
      const input = document.querySelector('#stage [data-lib-page-input]');
      const page = Number(input?.value);
      if (!Number.isInteger(page) || page < 1 || page > 8551) { input?.reportValidity(); return; }
      if (page <= 2) { kifuPage = page; selectedKifuId = (page === 1 ? kifuFixture.page1 : kifuFixture.page2)[0].id; document.querySelector('.chooser button[data-id="kifu"]')?.click(); }
      else document.getElementById('modal-root').innerHTML = `<div class="modal"><div class="u-lib-expanded"><div class="u-lib-expanded-head"><strong>第 ${page} 页</strong><button type="button" class="u-lib-button" data-close-help="true">关闭</button></div><p>页码跳转的入口已保留。当前设计预览只采集到前两页，正式页面会按页码加载棋谱。</p></div></div>`;
      return;
    }
    const pageButton = event.target.closest('#stage [data-lib-page]');
    if (pageButton) {
      const page = Number(pageButton.dataset.libPage);
      if (page === 1 || page === 2) {
        kifuPage = page;
        selectedKifuId = (page === 1 ? kifuFixture.page1 : kifuFixture.page2)[0].id;
        document.querySelector('.chooser button[data-id="kifu"]')?.click();
      } else document.getElementById('modal-root').innerHTML = `<div class="modal"><div class="u-lib-expanded"><div class="u-lib-expanded-head"><strong>第 ${page} 页</strong><button type="button" class="u-lib-button" data-close-help="true">关闭</button></div><p>当前设计预览只采集到前两页。正式页面会从棋谱库加载这一页。</p></div></div>`;
      return;
    }
    const moveButton = event.target.closest('#stage [data-kifu-move]');
    if (moveButton) {
      const last = kifuFixture.unanalysed.moves;
      detailMove = Math.max(0, Math.min(last, moveButton.dataset.kifuMove === 'first' ? 0 : moveButton.dataset.kifuMove === 'last' ? last : detailMove + (moveButton.dataset.kifuMove === 'next' ? 1 : -1)));
      const board = document.querySelector('#stage [data-kifu-board]');
      if (board) board.innerHTML = kifuPositionSvg(detailMove);
      const slider = document.querySelector('#stage [data-kifu-range]');
      if (slider) slider.value = String(detailMove);
      const output = document.querySelector('#stage [data-kifu-move-output]');
      if (output) output.textContent = String(detailMove);
      return;
    }
    if (event.target.closest('[data-lib-book-chapters]')) {
      const chapterTab = document.getElementById('u-lib-books-1') || document.getElementById('u-lib-booksopen-1');
      if (chapterTab) chapterTab.checked = true;
    }
  });
  document.addEventListener('input', event => {
    const kifuRange = event.target.closest('#stage [data-kifu-range]');
    if (kifuRange) {
      detailMove = Number(kifuRange.value);
      document.querySelector('#stage [data-kifu-board]').innerHTML = kifuPositionSvg(detailMove);
      document.querySelector('#stage [data-kifu-move-output]').textContent = String(detailMove);
      return;
    }
    const slider = event.target.closest('[data-lib-captured-value]');
    if (slider) slider.value = slider.dataset.libCapturedValue;
  });
  document.addEventListener('click', event => {
    if (!event.target.closest('[data-lib-expand]')) return;
    document.getElementById('modal-root').innerHTML = `<div class="modal"><div class="u-lib-expanded"><div class="u-lib-expanded-head"><strong>分析详情</strong><button type="button" class="u-lib-button" data-close-help="true">关闭</button></div><div class="u-lib-expanded-wait" role="status"><strong>正在读取分析</strong><span>当前局面暂无分析数据</span></div></div></div>`;
  });
})();
