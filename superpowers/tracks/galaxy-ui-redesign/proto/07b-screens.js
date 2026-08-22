/* ───────────────────────────── 死活题 ───────────────────────────── */
const CRUMB = (items, src) => `<div class="crumbs" data-zone="page-header">${items.map((it, i) =>
  (i ? '<span class="sep">/</span>' : '') + (it[1]
    ? `<button data-act="导航 ${it[1]}" data-src="${src}">${esc(it[0])}</button>`
    : `<span style="color:var(--tx)">${esc(it[0])}</span>`)).join('')}</div>`;

SCREENS.push({
  id: 'tsumego-levels', group: '死活题', label: '死活题 · 难度列表', route: '/galaxy/tsumego',
  nav: 'tsumego', kind: 'content',
  branches: [{ id: 'ok', label: '主界面' }, { id: 'loading', label: '加载中' }, { id: 'error', label: '加载失败' }, { id: 'empty', label: '空态' }],
  render(b) {
    if (b === 'loading') return { html: `<div data-zone="body" style="height:50vh;display:grid;place-items:center"><div class="spin"></div></div>` };
    if (b === 'error') return { html: `<div data-zone="body" style="padding-top:20px"><div class="alert error">死活题库加载失败，请稍后重试。</div></div>` };
    if (b === 'empty') return { html: `<div data-zone="body"><h1 style="font-size:2.125rem;font-weight:700;margin:0 0 8px">死活题</h1><p class="muted" style="margin:0 0 32px">选择难度级别</p><p class="dim">暂无死活题。</p></div>` };
    const levels = [['15K', 240, [['死活', 160], ['手筋', 60], ['官子', 20]]], ['10K', 312, [['死活', 200], ['手筋', 92], ['官子', 20]]],
      ['5K', 288, [['死活', 180], ['手筋', 88], ['官子', 20]]], ['1K', 196, [['死活', 120], ['手筋', 56], ['官子', 20]]],
      ['1D', 164, [['死活', 100], ['手筋', 48], ['官子', 16]]], ['3D', 132, [['死活', 80], ['手筋', 40], ['官子', 12]]],
      ['5D', 96, [['死活', 60], ['手筋', 26], ['官子', 10]]], ['7D', 64, [['死活', 40], ['手筋', 18], ['官子', 6]]]];
    return {
      html: `<div data-zone="body" style="max-width:1200px;margin:0 auto">
        <h1 style="font-size:2.125rem;font-weight:700;margin:0 0 8px">死活题</h1>
        <p class="muted" style="margin:0 0 32px">选择难度级别</p>
        <div class="gridcards" style="grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:24px">
          ${levels.map(([lv, total, cats]) => card(
            `<div style="padding:32px 16px;text-align:center">
               <div class="mono" style="font-size:3rem;font-weight:700;color:var(--jade);margin-bottom:8px">${lv}</div>
               <div style="font-size:1.25rem;color:var(--tx2);margin-bottom:12px">${total} 题</div>
               <div class="inline" style="justify-content:center;gap:6px">
                 ${cats.map(([c, n]) => `<span style="font-size:.72rem;padding:2px 8px;background:rgba(255,255,255,.06);border-radius:4px;color:var(--tx2)">${c}: ${n}</span>`).join('')}
               </div></div>`,
            { act: `导航 /galaxy/tsumego/${lv.toLowerCase()}`, src: 'TsumegoLevelsPage.tsx:80-110', style: 'border-radius:12px' })).join('')}
        </div>
      </div>`,
    };
  },
  note: `<h3>根级内容页 · 无面包屑</h3>
    <p>标题 <code>t('Tsumego')</code> <b>没传 fallback</b>（<code>TsumegoLevelsPage.tsx:70</code>），
    翻译没加载完时会直接显示英文 key「Tsumego」。迁到 <code>ContentPageHeader</code> 时要补成
    <code>t('Tsumego','死活题')</code>，且两个 return 分支（<code>:59</code> 和 <code>:69</code>）都要改。</p>
    <p>副标题「选择难度级别」下沉；卡片里那些看着像 chip 的分类计数其实是 <code>Typography</code>，没有点击行为，属于正文，不动。</p>`,
});

SCREENS.push({
  id: 'tsumego-categories', group: '死活题', label: '死活题 · 题型列表', route: '/galaxy/tsumego/:level',
  nav: 'tsumego', kind: 'content',
  branches: [{ id: 'ok', label: '主界面' }, { id: 'loading', label: '加载中' }],
  render(b) {
    if (b === 'loading') return { html: `<div data-zone="body" style="height:50vh;display:grid;place-items:center"><div class="spin"></div></div>` };
    const cats = [['死活', 160, 'Extension'], ['手筋', 60, 'TipsAndUpdates'], ['官子', 20, 'Calculate']];
    return {
      html: `<div data-zone="body" style="padding-left:16px">
        <div class="inline" style="margin-bottom:24px">
          ${ibtn({ icon: 'ArrowBack', label: '返回', act: '导航 /galaxy/tsumego', src: 'TsumegoCategoriesPage.tsx:53' })}
          ${CRUMB([['死活题', '/galaxy/tsumego'], ['15K', null]], 'TsumegoCategoriesPage.tsx:56-66')}
        </div>
        <h1 style="font-size:2.125rem;font-weight:700;margin:0 0 8px">15K - 选择题型</h1>
        <p class="muted" style="margin:0 0 32px">选择你想要练习的题型</p>
        <div class="stack g16" style="max-width:480px">
          ${cats.map(([c, n, i]) => card(
            `<div style="height:72px;display:flex;align-items:center;padding:0 16px;gap:16px">
               <div style="width:48px;display:grid;place-items:center;color:var(--jade-l)">${icon(i)}</div>
               <div style="flex:1;min-width:0;font-size:1.05rem;font-weight:600">${c}</div>
               <div class="mono muted">${n} 题</div></div>`,
            { act: `导航 /galaxy/tsumego/15k/${c}`, src: 'TsumegoCategoriesPage.tsx:80-120', style: 'border-radius:12px' })).join('')}
        </div>
      </div>`,
    };
  },
  note: `<h3>面包屑 + 左置返回，两者都要拆</h3>
    <p>今天是「返回图标 + 两级面包屑」一行，标题在下一行（<code>TsumegoCategoriesPage.tsx:51-74</code>）。
    spec §2.4 明确：面包屑不进页头，返回按钮不与标题纵向叠放。目标是单行
    <b>左「15K 选择题型」 右「← 死活题」</b>。</p>
    <p>标题里的 <code>level</code> 是 URL 参数（15K…7D），是动态的。
    kiosk 那边已经有一份同款：<code>src/kiosk/pages/TsumegoCategoriesPage.tsx:117</code>，
    构成一样，只有 fallback 文案不同，可以对齐。</p>`,
});

SCREENS.push({
  id: 'tsumego-units', group: '死活题', label: '死活题 · 单元列表', route: '/galaxy/tsumego/:level/:category',
  nav: 'tsumego', kind: 'content',
  branches: [{ id: 'ok', label: '主界面' }, { id: 'loading', label: '加载中' }],
  render(b) {
    if (b === 'loading') return { html: `<div data-zone="body" style="height:50vh;display:grid;place-items:center"><div class="spin"></div></div>` };
    return {
      html: `<div data-zone="body" style="padding-left:16px">
        <div class="inline" style="margin-bottom:24px">
          ${ibtn({ icon: 'ArrowBack', label: '返回', act: '导航 /galaxy/tsumego/15k', src: 'TsumegoUnitsPage.tsx:151' })}
          ${CRUMB([['死活题', '/galaxy/tsumego'], ['15K', '/galaxy/tsumego/15k'], ['死活', null]], 'TsumegoUnitsPage.tsx:154-172')}
        </div>
        <h1 style="font-size:2.125rem;font-weight:700;margin:0 0 8px">15K 死活 - 选择单元</h1>
        <p class="muted" style="margin:0 0 32px">共 160 题，分为 8 个单元</p>
        <div class="gridcards" style="grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:12px">
          ${Array.from({ length: 8 }, (_, i) => card(
            `<div style="display:flex;align-items:center;padding:14px 16px;gap:12px">
               <div class="mono" style="font-size:1.4rem;font-weight:700;color:var(--jade-l);min-width:32px">${i + 1}</div>
               <div style="flex:1;min-width:0">
                 <div style="font-weight:600">单元 ${i + 1}</div>
                 <div class="dim mono" style="font-size:.75rem">第 ${i * 20 + 1}-${i * 20 + 20} 题</div>
               </div>
               <span class="chip ${i < 2 ? 'ok' : ''}">${i < 2 ? '20/20' : i === 2 ? '7/20' : '0/20'}</span>
             </div>`,
            { act: `导航 /galaxy/tsumego/15k/死活/${i + 1}`, src: 'TsumegoUnitsPage.tsx:185-240', style: 'border-radius:10px' })).join('')}
        </div>
      </div>`,
    };
  },
  note: `<h3>副标题同时是状态说明</h3>
    <p>「共 160 题，分为 8 个单元」既是长副标题又是计数状态，spec §2.4 双重禁止进页头。
    它要下沉到卡片网格上方作为正文首行。三级面包屑同样出局，换成右侧「← 15K 题型」。</p>`,
});

SCREENS.push({
  id: 'tsumego-list', group: '死活题', label: '死活题 · 题目九宫格', route: '/galaxy/tsumego/:level/:category/:unit',
  nav: 'tsumego', kind: 'content',
  branches: [{ id: 'ok', label: '主界面' }, { id: 'loading', label: '加载中' }],
  render(b) {
    if (b === 'loading') return { html: `<div data-zone="body" style="height:50vh;display:grid;place-items:center"><div class="spin"></div></div>` };
    return {
      html: `<div data-zone="body" style="max-width:1400px;margin:0 auto">
        <div class="inline" style="margin-bottom:24px">
          ${ibtn({ icon: 'ArrowBack', label: '返回', act: '导航 /galaxy/tsumego/15k/死活', src: 'TsumegoListPage.tsx:116' })}
          ${CRUMB([['死活题', '/galaxy/tsumego'], ['15K', '/galaxy/tsumego/15k'], ['死活', '/galaxy/tsumego/15k/死活'], ['单元 3', null]], 'TsumegoListPage.tsx:119-145')}
        </div>
        <div class="rowbetween" style="margin-bottom:32px">
          <div>
            <h1 style="font-size:2.125rem;font-weight:700;margin:0 0 4px">单元 3</h1>
            <p class="muted mono" style="margin:0">第 41-60 题</p>
          </div>
          <span class="chip" style="height:30px;font-size:1rem;padding:0 12px">7/20</span>
        </div>
        <div class="gridcards" style="grid-template-columns:repeat(auto-fill,minmax(160px,1fr));gap:16px">
          ${Array.from({ length: 20 }, (_, i) => card(
            `<div style="padding:10px">
               <div style="aspect-ratio:1/1;border-radius:8px;background:linear-gradient(160deg,#e0af5b,#bf8b3b);position:relative;margin-bottom:8px">
                 ${i < 7 ? `<span style="position:absolute;top:6px;right:6px;color:#0d3a25;background:var(--ok);border-radius:50%;width:20px;height:20px;display:grid;place-items:center"><svg class="ic xs" style="fill:#04150d"><use href="#i-CheckCircle"/></svg></span>` : ''}
               </div>
               <div style="text-align:center;font-size:.85rem">第${i + 41}题</div>
             </div>`,
            { act: `导航 /galaxy/tsumego/problem/${22592 + i}`, src: 'TsumegoListPage.tsx:160-200;ProblemCard.tsx', style: 'border-radius:12px' })).join('')}
        </div>
      </div>`,
    };
  },
  note: `<h3>唯一一个页头里带真 Chip 的页面</h3>
    <p>右上角那个 <code>7/20</code> 是 MUI <code>&lt;Chip&gt;</code>（<code>TsumegoListPage.tsx:157</code>），
    spec §2.4 明令 chip 不进页头。它要跟着「第 41-60 题」一起下沉到九宫格上方的一行进度区。</p>`,
});

/* ───────────────────────────── 棋谱库 ───────────────────────────── */
const KIFU = [
  ['韩一洲', '张强', '2026-03-21', '第 3 届衢州·烂柯杯', 250, '黑中盘胜'],
  ['黄云嵩', '范廷钰', '2026-03-19', '2026 中国围甲联赛', 244, '白胜 1.5 目'],
  ['洪性志', '安成浚', '2026-03-18', 'KB 国民银行联赛', 238, '黑胜 2.5 目'],
  ['张梦瑶', '吴其右', '2026-03-15', '第 8 届吴清源杯', 231, '黑中盘胜'],
  ['李元荣', '金彩瑛', '2026-03-14', '女子最强战', 226, '白中盘胜'],
  ['柯洁', '朴廷桓', '2026-03-11', '春兰杯八强战', 219, '黑胜 0.5 目'],
];
const kifuCard = (r, i, sel) => `<button class="kcard ${sel ? 'sel' : ''}" data-act="handleCardClick(album) → 换选中棋谱、重取 SGF" data-src="KifuLibraryPage.tsx:355">
  <div class="kmeta"><span>${r[2]} · ${r[3]}</span><span>${r[4]} 手</span></div>
  <div class="kplayers">
    <span class="side"><i class="kstone b"></i>${r[0]}</span>
    <span class="dim" style="font-size:.7rem">${r[5]}</span>
    <span class="side w">${r[1]}<i class="kstone w"></i></span>
  </div></button>`;

SCREENS.push({
  id: 'kifu', group: '棋谱库', label: '棋谱库 · 列表 + 预览', route: '/galaxy/kifu',
  nav: 'kifu', kind: 'content',
  branches: [{ id: 'preview', label: '已选棋谱' }, { id: 'ready', label: '未选中' }, { id: 'loading', label: '列表加载中' }, { id: 'empty', label: '空结果' }],
  render(b) {
    const search = `<div style="padding:24px 24px 12px" data-zone="page-header">
        <div class="inline" style="align-items:baseline;gap:12px;margin-bottom:16px">
          <h1 style="font-size:2.125rem;font-weight:700;margin:0">棋谱库</h1>
          ${b === 'loading' ? '' : `<span class="muted mono" style="font-size:.85rem;opacity:.6">25,062 条记录</span>`}
        </div>
        <div class="fieldwrap">${icon('Search', 'sm')}
          <input class="field" placeholder="按棋手、赛事、日期搜索…" aria-label="按棋手、赛事、日期搜索" data-act="Enter → setSearchParams({q}) 重查列表" data-src="KifuLibraryPage.tsx:302">
        </div>
      </div>`;
    const list = b === 'loading'
      ? `<div class="lleft-scroll stack g8">${Array.from({ length: 8 }, () => `<div class="skel" style="height:64px"></div>`).join('')}</div>`
      : b === 'empty'
        ? `<div class="lleft-scroll" style="display:grid;place-items:center;text-align:center">
             <div><div style="font-size:1.15rem;font-weight:500;color:var(--tx2)">未找到棋谱</div>
             <div class="dim" style="margin-top:6px">"柯洁 2019"</div></div></div>`
        : `<div class="lleft-scroll stack g8">${KIFU.map((r, i) => kifuCard(r, i, b === 'preview' && i === 0)).join('')}</div>`;
    const pager = b === 'loading' || b === 'empty' ? '' : `<div style="padding:8px 0;border-top:1px solid var(--line);flex:none">
        <div class="pager">
          ${ibtn({ icon: 'ChevronLeft', label: '上一页', size: 'sm', act: 'handlePageChange(page-1)', src: 'KifuLibraryPage.tsx:386' })}
          ${[1, 2, 3, 4, 5].map(p => `<button aria-current="${p === 1}" data-act="handlePageChange(${p}) → 改 URL 重查" data-src="KifuLibraryPage.tsx:386">${p}</button>`).join('')}
          <span class="dim">…</span>
          <button data-act="handlePageChange(1044)" data-src="KifuLibraryPage.tsx:386">1044</button>
          ${ibtn({ icon: 'ChevronRight', label: '下一页', size: 'sm', act: 'handlePageChange(page+1)', src: 'KifuLibraryPage.tsx:386' })}
        </div></div>`;

    let right;
    if (b === 'preview') {
      right = `<div class="lboard"><canvas class="boardcv" data-floor="400" data-board='${esc(JSON.stringify({ stones: demoStones(38), coords: true, last: [15, 9, 'W'] }))}'></canvas></div>
        <div class="lbottom" style="justify-content:space-between">
          <div style="flex:1"></div>
          <div class="inline" style="gap:8px">
            ${btn({ label: '⏮', size: 'sm', color: 'inherit', act: 'setPreviewCurrentMove(0)', src: 'KifuLibraryPage.tsx:435' })}
            ${btn({ label: '◀', size: 'sm', color: 'inherit', act: 'setPreviewCurrentMove(m-1)', src: 'KifuLibraryPage.tsx:443' })}
            <span class="mono muted" style="min-width:80px;text-align:center;margin:0 16px">250 / 250 手</span>
            ${btn({ label: '▶', size: 'sm', color: 'inherit', act: 'setPreviewCurrentMove(m+1)', src: 'KifuLibraryPage.tsx:463' })}
            ${btn({ label: '⏭', size: 'sm', color: 'inherit', act: 'setPreviewCurrentMove(moves.length)', src: 'KifuLibraryPage.tsx:471' })}
          </div>
          <div style="flex:1;display:flex;justify-content:flex-end">
            ${btn({ label: '在研究中打开', variant: 'contained', size: 'sm', act: '导航 /galaxy/research?kifu_id=8502', src: 'KifuLibraryPage.tsx:480' })}
          </div>
        </div>`;
    } else if (b === 'loading') {
      right = `<div class="lboard"><div class="skel" style="width:360px;height:360px;border-radius:8px"></div></div>`;
    } else {
      right = `<div class="lboard"><p class="dim">选择一局棋谱预览</p></div>`;
    }
    return {
      raw: `<div class="lrow" data-zone="body">
        <div class="lleft">${search}${list}${pager}</div>
        <div class="lmain" style="border-left:1px solid var(--line)">${right}</div>
      </div>`,
    };
  },
  note: `<h3>构图与模板左右相反</h3>
    <p>今天是<b>左 520px 列表 / 右 棋盘</b>（<code>KifuLibraryPage.tsx:279-281</code>）。
    模板是<b>左 棋盘 / 右 340px 信息栏</b>。迁移不是换皮，是左右对调，
    并把 520px 宽的搜索 + 卡片列表压进 340px。</p>
    <p>另外它给 <code>LiveBoard</code> 没传 <code>minimumCanvasSize</code>，
    所以棋盘有一个 400px 的硬下限（<code>LiveBoard.tsx:326</code>）；
    <code>LiveMatchPage</code> 传的是 0。窄视口下这条会直接把棋盘顶出容器。</p>`,
});
