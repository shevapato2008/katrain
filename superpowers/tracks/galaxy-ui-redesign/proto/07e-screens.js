/* ───────────────────────────── 死活题 · 解题 ───────────────────────────── */
const TSU_STONES = [[14, 16, 'B'], [15, 16, 'B'], [16, 16, 'B'], [17, 15, 'B'], [17, 14, 'B'],
  [15, 17, 'W'], [16, 17, 'W'], [17, 17, 'W'], [16, 15, 'W'], [14, 15, 'B'], [18, 16, 'B']];

SCREENS.push({
  id: 'tsumego-problem', group: '死活题', label: '死活题 · 解题', route: '/galaxy/tsumego/problem/:problemId',
  nav: 'tsumego', kind: 'content',
  branches: [
    { id: 'default', label: '未解出' }, { id: 'solved', label: '已解出' },
    { id: 'failed', label: '答错' }, { id: 'try', label: '试下模式' }, { id: 'hint', label: '显示提示' },
  ],
  render(b, vp) {
    const solved = b === 'solved', failed = b === 'failed', tryMode = b === 'try', hint = b === 'hint';
    const boardCanvas = `<canvas class="boardcv" data-floor="400" data-board='${esc(JSON.stringify({
      stones: TSU_STONES, coords: false, numbers: tryMode, last: [18, 16, 'B'],
      ai: hint ? [[18, 17, '', '']] : null,
    }))}'></canvas>`;

    /* ── mobile layout: MobileHeader + board + MobileToolbar ── */
    if (vp.id === '430x880') {
      const mtool = (ic, label, act, tint) => `<button class="iconbtn" aria-label="${label}" data-act="${act}" data-src="MobileControls.tsx"
        style="width:52px;height:52px;${tint ? `background:${tint}` : ''}">${icon(ic)}</button>`;
      return {
        raw: `<div style="display:flex;flex-direction:column;height:var(--vp-h);overflow:hidden;background:var(--bg)" data-zone="body">
          <div class="rowbetween" style="padding:8px 12px;background:rgba(0,0,0,.4);border-bottom:1px solid rgba(255,255,255,.1);flex:none" data-zone="mobile-toolbar">
            <div class="inline" style="gap:8px">
              ${ibtn({ icon: 'ArrowBack', label: '返回', size: 'sm', act: '导航 /galaxy/tsumego/3d/life-death', src: 'MobileControls.tsx' })}
              <span class="chip" style="height:24px;color:var(--jade-l);border-color:rgba(93,130,112,.5)">3D</span>
              <span class="muted mono" style="font-size:.85rem">#3/20</span>
            </div>
            <div class="inline" style="gap:6px">
              <span style="width:14px;height:14px;border-radius:50%;background:#1a1a1a;border:1px solid #333"></span>
              <span class="muted" style="font-size:.8rem">${solved ? '正确！' : failed ? '错误' : '黑先'}</span>
            </div>
          </div>
          <div class="lboard" style="position:relative;padding:4px">
            ${boardCanvas}
            ${solved ? `<div style="position:absolute;inset:0;display:grid;place-items:center;background:rgba(48,160,110,.14);pointer-events:none">
              <div class="chip ok filled" style="height:44px;font-size:1.1rem;padding:0 22px">正确！</div></div>` : ''}
          </div>
          <div style="display:flex;justify-content:space-around;padding:10px 8px;background:var(--surface);border-top:1px solid var(--line);flex:none;margin-bottom:var(--bottomnav)" data-zone="bottom-nav">
            ${mtool('NavigateBefore', '上一题', 'handlePrevious() → navigate 上一题')}
            ${mtool('Undo', '撤销', 'undo()')}
            ${mtool('Refresh', '重置', 'reset()')}
            ${mtool('TouchApp', '试下', tryMode ? 'exitTryMode()' : 'enterTryMode()', tryMode ? 'rgba(93,130,112,.3)' : '')}
            ${mtool('TipsAndUpdates', '提示', 'toggleHint()', hint ? 'rgba(232,150,57,.25)' : '')}
            ${mtool('NavigateNext', '下一题', 'handleNext() → navigate 下一题', solved ? 'rgba(76,175,80,.25)' : '')}
          </div>
          ${failed ? `<div class="snack error bottom" style="bottom:150px">此手不成立 ${ibtn({ icon: 'Close', label: 'Close — MUI Alert 关闭键', size: 'sm', act: 'setSnackbar(open:false)', src: 'TsumegoProblemPage.tsx:341' })}</div>` : ''}
          ${VH}</div>`,
      };
    }

    /* ── desktop layout: breadcrumb strip + board | 320 rail ── */
    return {
      raw: `<div class="lrow vh100" data-zone="body">
        <div class="lmain">
          <div class="lhead" style="justify-content:flex-start;gap:8px" data-zone="above-board">
            ${ibtn({ icon: 'ArrowBack', label: '返回', size: 'sm', act: '导航 /galaxy/tsumego/3d/life-death', src: 'TsumegoProblemPage.tsx:363' })}
            ${CRUMB([['死活题', '/galaxy/tsumego'], ['3D', '/galaxy/tsumego/3d'], ['死活', '/galaxy/tsumego/3d/life-death'], ['第3题', null]], 'TsumegoProblemPage.tsx:366-397')}
          </div>
          <div class="lboard" style="position:relative">
            ${boardCanvas}
            ${solved ? `<div style="position:absolute;inset:0;display:grid;place-items:center;background:rgba(48,160,110,.14);pointer-events:none">
              <div class="chip ok filled" style="height:52px;font-size:1.35rem;padding:0 28px">正确！</div></div>` : ''}
          </div>
        </div>
        <div class="lrail w320">
          <div class="lrail-scroll">
            <div style="padding:16px" data-zone="right-rail-top">
              <div class="inline" style="gap:6px;margin-bottom:14px">
                <span class="chip" style="color:var(--jade-l);border-color:rgba(93,130,112,.5)">3D</span>
                <span class="chip">死活</span>
              </div>
              <hr class="hr">
              <div class="inline" style="gap:10px;margin:14px 0">
                <span style="width:20px;height:20px;border-radius:50%;background:#1a1a1a;border:1px solid #333"></span>
                <span style="font-size:1rem">${solved ? '正确！' : failed ? '错误' : '黑先'}</span>
              </div>
              <div class="rowbetween muted" style="font-size:.85rem">
                <span class="inline" style="gap:6px">${icon('Timer', 'sm')}<span class="mono">0:07</span></span>
                <span>尝试次数: ${failed ? 2 : solved ? 1 : 0}</span>
              </div>
            </div>
            <hr class="hr">
            <div style="padding:16px" data-zone="right-rail-middle">
              ${btn({ label: hint ? '隐藏提示' : '显示提示', variant: 'outlined', full: true, icon: 'TipsAndUpdates', act: 'toggleHint() → 棋盘正解点画绿色半透明圆', src: 'TsumegoProblemControls.tsx' })}
              ${hint ? `<div style="margin-top:12px;padding:12px;background:rgba(232,150,57,.1);border-left:3px solid var(--warn);border-radius:4px;font-size:.85rem">黑先</div>
                <p class="dim" style="font-size:.72rem;margin:8px 0 0">后端 hint 字段是 String(16)，只存了「黑先」；真正的提示是棋盘上那个绿点。</p>` : ''}
            </div>
          </div>
          <div style="padding:16px;border-top:1px solid var(--line)" data-zone="right-rail-actions">
            <div class="inline" style="gap:8px;justify-content:center;margin-bottom:12px">
              ${ibtn({ icon: 'TouchApp', label: '自由探索，不判断对错', act: tryMode ? 'exitTryMode()' : 'enterTryMode()', src: 'TsumegoProblemControls.tsx' })}
              ${ibtn({ icon: 'Undo', label: '撤销 (U)', act: 'undo() — 快捷键 U / Ctrl+Z', src: 'TsumegoProblemControls.tsx' })}
              ${ibtn({ icon: 'Refresh', label: '重置 (R)', act: 'reset() — 快捷键 R', src: 'TsumegoProblemControls.tsx' })}
            </div>
            <div class="inline" style="gap:8px">
              ${btn({ label: '上一题', variant: 'outlined', full: true, icon: 'NavigateBefore', act: 'navigate 上一题', src: 'TsumegoProblemControls.tsx' })}
              ${btn({ label: '下一题', variant: solved ? 'contained' : 'outlined', full: true, act: 'navigate 下一题', src: 'TsumegoProblemControls.tsx' })}
            </div>
          </div>
        </div>
        ${failed ? `<div class="snack error bottom">此手不成立 ${ibtn({ icon: 'Close', label: 'Close — MUI Alert 关闭键', size: 'sm', act: 'setSnackbar(open:false)', src: 'TsumegoProblemPage.tsx:440' })}</div>` : ''}
        ${VH}</div>`,
    };
  },
  note: `<h3>唯一一个自己写了两套布局的棋盘页</h3>
    <p><code>TsumegoProblemPage</code> 用 <code>useMediaQuery</code> 分出 <b>桌面</b> 和 <b>移动</b> 两套完整 JSX
    （<code>:305</code> 与 <code>:360</code>），移动那套还有自己的 <code>MobileHeader</code> / <code>MobileToolbar</code>。
    <code>BoardPageShell</code> 自带响应式换层，迁移后这两套应当合成一套 —— 移动端的六个工具键并进右栏动作区。</p>
    <p>把视口切到 430×880 看看今天的样子：本页自己的底部工具条会和 galaxy 的
    <code>GalaxyBottomNav</code> 撞在一起，页面又取了 100vh。</p>
    <p>还有一处会咬人的：<code>TsumegoBoard.tsx:90</code> 把棋盘尺寸钳在
    <code>min(容器宽, 容器高, window.innerHeight - 100)</code> 再取 <code>max(400, …)</code>。
    那个 <code>innerHeight - 100</code> 是脱离布局的魔法数，1024×768 下会把棋盘压到 660 左右，
    比模板的 684 小 —— 迁移时必须换成容器测量。</p>`,
});

/* ───────────────────────────── 教程 ───────────────────────────── */
SCREENS.push({
  id: 'tutorial-landing', group: '教程', label: '教程 · 分类首页', route: '/galaxy/tutorials',
  nav: 'tutorials', kind: 'content',
  branches: [{ id: 'ok', label: '正常' }, { id: 'error', label: '加载失败' }],
  render(b) {
    if (b === 'error') {
      return { html: `<div data-zone="body"><div class="alert error">加载教程分类失败 ${btn({ label: '重试', size: 'sm', act: 'load()', src: 'TutorialLandingPage.tsx:32' })}</div></div>` };
    }
    const cats = [['入门', '从规则到第一盘棋', 6], ['布局', '开局定式与大场', 4], ['中盘', '战斗、攻防与形状', 5], ['官子', '收官计算与目数', 3]];
    return {
      html: `<div data-zone="body">
        <h1 style="font-size:1.5rem;font-weight:600;margin:0 0 4px">教程</h1>
        <p class="muted" style="margin:0 0 24px;font-size:.875rem">选择一个学习阶段开始学习</p>
        <div class="gridcards" style="grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:16px">
          ${cats.map(([n, d, bks]) => card(
            `<div style="padding:20px">
               <div class="inline" style="gap:10px;margin-bottom:10px"><span style="color:var(--jade-l)">${icon('MenuBook')}</span>
               <span style="font-size:1.15rem;font-weight:600">${n}</span></div>
               <div class="muted" style="font-size:.85rem;margin-bottom:8px">${d}</div>
               <span class="chip">${bks} 本书</span></div>`,
            { act: `导航 /galaxy/tutorials/${n}`, src: 'TutorialLandingPage.tsx:40-50' })).join('')}
        </div>
      </div>`,
    };
  },
  note: `<h3>标题是硬编码字面量，没走 i18n</h3>
    <p><code>TutorialLandingPage.tsx:36</code> 直接写了 <code>&lt;Typography variant="h5"&gt;教程&lt;/Typography&gt;</code>，
    整个文件没有 <code>useTranslation</code>。字号也比其他内容页小一档（h5 vs h4）。
    换 <code>ContentPageHeader</code> 顺带把字号统一到 h1/2.125rem。</p>`,
});

SCREENS.push({
  id: 'tutorial-books', group: '教程', label: '教程 · 书籍列表', route: '/galaxy/tutorials/:category',
  nav: 'tutorials', kind: 'content',
  branches: [{ id: 'ok', label: '正常' }, { id: 'empty', label: '空态' }, { id: 'error', label: '加载失败' }],
  render(b) {
    if (b === 'error') return { html: `<div data-zone="body"><div class="alert error">加载书籍失败 ${btn({ label: '重试', size: 'sm', act: 'load()', src: 'TutorialBooksPage.tsx' })}</div></div>` };
    const books = [['围棋入门一本通', '王元', 132], ['从零开始学围棋', '李昌镐', 96], ['围棋基本手筋', '石田芳夫', 148]];
    return {
      html: `<div data-zone="body">
        <div style="margin-bottom:8px">${btn({ label: '← 返回', size: 'sm', color: 'inherit', act: '导航 /galaxy/tutorials', src: 'TutorialBooksPage.tsx:38' })}</div>
        <h1 style="font-size:1.5rem;font-weight:600;margin:0 0 24px">入门</h1>
        ${b === 'empty' ? `<p class="muted">该分类暂无书籍</p>` : `
        <div class="gridcards" style="grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:16px">
          ${books.map(([t, a, secs]) => card(
            `<div style="padding:20px">
               <div style="font-size:1.15rem;font-weight:600;margin-bottom:6px">${t}</div>
               <div class="muted" style="font-size:.85rem;margin-bottom:10px">${a}</div>
               <span class="chip">${secs} 小节</span></div>`,
            { act: '导航 /galaxy/tutorials/book/{id}', src: 'TutorialBooksPage.tsx:44-56' })).join('')}
        </div>`}
      </div>`,
    };
  },
  note: `<h3>返回按钮纵向叠在标题上方 —— spec 明令禁止</h3>
    <p><code>TutorialBooksPage.tsx:38-39</code>：一个写死文案「← 返回」的小按钮，
    单独占一行，标题在它下面。spec §2.4 第 4 句：<b>不得把返回按钮和标题纵向叠放</b>。
    换成 <code>ContentPageHeader</code> 后是单行左右：左「入门」右「← 教程」。</p>
    <p>标题是 URL 参数 <code>category</code>，后端的分类 slug 本身就是中文
    （<code>db_queries.py:22-27</code>：入门/布局/中盘/官子），可以直接透传。</p>`,
});

SCREENS.push({
  id: 'tutorial-book', group: '教程', label: '教程 · 书籍目录', route: '/galaxy/tutorials/book/:bookId',
  nav: 'tutorials', kind: 'content',
  branches: [{ id: 'ok', label: '正常' }, { id: 'video', label: '全屏视频' }, { id: 'error', label: '加载失败' }],
  dialogs: {
    video: `<div class="dlg" style="max-width:820px" data-zone="dialog">
      <h3>第一章 · 二 角上的空</h3>
      <div style="padding:0 22px 16px">
        <div style="aspect-ratio:16/9;border-radius:8px;background:linear-gradient(150deg,#1c1c1c,#0c0c0c);display:grid;place-items:center;border:1px solid var(--line2)">
          <button class="iconbtn" aria-label="播放" data-act="&lt;video controls&gt; 原生播放" data-src="TutorialBookDetailPage.tsx:110" style="width:64px;height:64px;background:rgba(74,107,92,.9);color:#eef4f0">${icon('PlayArrow')}</button>
        </div>
      </div>
      <div class="acts">${btn({ label: '关闭', color: 'inherit', act: 'setVideoOpen(false)', src: 'TutorialBookDetailPage.tsx:133' })}</div></div>`,
  },
  render(b) {
    if (b === 'error') return { html: `<div data-zone="body"><div class="alert error">加载书籍失败 ${btn({ label: '重试', size: 'sm', act: 'load()', src: 'TutorialBookDetailPage.tsx' })}</div></div>` };
    const chapters = [['第一章 基本规则', ['一 棋盘与棋子', '二 角上的空', '三 气与提子']],
      ['第二章 吃子与逃跑', ['一 打吃', '二 双打吃', '三 征子']],
      ['第三章 死活基础', ['一 两只眼', '二 做眼与破眼']]];
    return {
      html: `<div data-zone="body">
        <div style="margin-bottom:8px">${btn({ label: '← 返回', size: 'sm', color: 'inherit', act: '导航 /galaxy/tutorials/入门', src: 'TutorialBookDetailPage.tsx:61' })}</div>
        <h1 style="font-size:1.5rem;font-weight:600;margin:0 0 4px">围棋入门一本通</h1>
        <p class="muted" style="margin:0 0 24px;font-size:.875rem">王元</p>
        <div class="stack g12">
          ${chapters.map(([ch, secs], ci) => `
            <div class="card" style="overflow:hidden">
              <button class="rowbetween" data-act="展开/收起章节 ${ci + 1}" data-src="TutorialBookDetailPage.tsx:70" style="width:100%;padding:14px 18px;background:transparent;border:0;cursor:pointer;color:inherit;font:inherit;text-align:left">
                <span style="font-weight:600">${ch}</span>${icon(ci === 0 ? 'ExpandLess' : 'ExpandMore')}
              </button>
              ${ci === 0 ? `<div style="border-top:1px solid var(--line)">${secs.map((s, si) => `
                <div class="rowbetween" style="padding:10px 18px;border-bottom:${si < secs.length - 1 ? '1px solid var(--line)' : '0'}">
                  <button data-act="导航 /galaxy/tutorials/section/{id}" data-src="TutorialBookDetailPage.tsx:80" style="flex:1;text-align:left;background:none;border:0;color:inherit;font:inherit;cursor:pointer;padding:0">${s}</button>
                  ${dlgOpen('video', '', { size: 'sm', icon: 'PlayCircleOutline', src: 'TutorialBookDetailPage.tsx:84' })}
                </div>`).join('')}</div>` : ''}
            </div>`).join('')}
        </div>
      </div>`,
    };
  },
  note: `<h3>同样是纵向叠放的返回，外加作者名当副标题</h3>
    <p>目标：左「围棋入门一本通」右「← 入门」。作者「王元」下沉到目录上方。
    注意这页的路由是 <code>/galaxy/tutorials/book/:bookId</code>，<b>不带 category</b>，
    上一级链接得从加载回来的 <code>book.category</code> 重建。</p>`,
});
