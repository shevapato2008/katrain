/* 死活题阶梯页（TsumegoLevelsPage）承重实测 —— 真浏览器。
 *
 * 这一页**不上 `BoardPageShell`**（它是无棋盘内容页，稿子也是 `cph()`），
 * 所以判据不是右栏三段那一套 —— 按自己这条链重写：
 * 页面在自然流里滚，行是 CSS grid，**新引入的裁切边界只有一处**：分布条的
 * `overflow:hidden`。反查「把改动撤回去，谁的高度来源或裁切边界会变」得到的就是它，
 * 外加行内那个 `minWidth: 0` 的伸缩列。
 *
 * 跑法：
 *   B=~/.claude/skills/gstack/browse/dist/browse
 *   $B viewport 1440x900 && $B goto http://127.0.0.1:8001/galaxy/tsumego
 *   $B wait '[data-testid="tsumego-rung"]' && $B wait --networkidle
 *   $B eval superpowers/tracks/galaxy-ui-redesign/loadbearing_tsumego_ladder.js
 *
 * 取数前置：真实接口回 22 档（15k…1k + 1d…7d）。少于 12 行说明没连上真库，本轮作废。
 *
 * 2026-08-23 实测（真库 22 档）：三档视口 T1–T7 全过。关键几个数：
 *   行宽 896（1440/1024，页根 maxWidth 960 − p:4 两边）/ 366（430）
 *   内容高 1702 vs 可视 848 —— 22 行本来就装不下一屏，滚是设计内的
 *   T5a `galaxy-main overflow-y=auto`；T6 级位 15 档、第一个段位在第 15 行
 *   430 档分布条数 0（那一列按设计不渲染，改放题数）
 *
 * **两条红分支都在真实树上跑过**，不是变异：
 *   T5a/T5b —— 把 `MainLayout.tsx` 换回 12a3d3fe：
 *              `galaxy-main overflow-y=visible sh=1702 ch=848` → 红。
 *   T7      —— 去掉页根的 `width:'100%'`：`行宽=489 可用=960` → 红。
 *              这一条尤其值得记：**别的判据全是绿的** —— 不溢出、不裁切、滚得动，
 *              全对，就是没铺开。判据不落在「行宽 vs 可用宽」上就永远看不见。
 */
(() => {
  const rows = Array.from(document.querySelectorAll('[data-testid="tsumego-rung"]'));
  if (!rows.length) return { fatal: 'rung not found —— 先 wait 那个 testid，别当布局错' };

  const box = (el) => { const r = el.getBoundingClientRect(); return {
    x: Math.round(r.left), y: Math.round(r.top), w: Math.round(r.width), h: Math.round(r.height),
    right: Math.round(r.right), bottom: Math.round(r.bottom) }; };

  const vw = innerWidth, vh = innerHeight;
  const narrow = vw < 600;                 // 分布条那一列在 xs 档不渲染（sx 里 sm 起才 flex）
  const scroller = document.scrollingElement;
  const R = [];
  const rel = (id, desc, pass, got) => R.push({ id, desc, pass, got });

  rel('T1', '整页不横向滚: scrollingElement.scrollWidth <= innerWidth+1',
      scroller.scrollWidth <= vw + 1, `${scroller.scrollWidth} vs ${vw}`);

  rel('T2', '所有档都渲染出来且高度非零', rows.every((r) => box(r).h > 0),
      `${rows.length} 行，最矮 ${Math.min(...rows.map((r) => box(r).h))}px`);

  /* T3：行是 grid，中间那一列 `minmax(0,1fr)`。列没写 min-width:0 时 grid 子项的
     min-content 会把整行撑破 —— 这一条就是量它有没有被撑破。 */
  const overflowingRows = rows.filter((row) => {
    const rb = box(row);
    return Array.from(row.querySelectorAll('*')).some((el) => {
      const b = el.getBoundingClientRect();
      return b.width > 0 && (b.right > rb.right + 1 || b.left < rb.x - 1);
    });
  });
  rel('T3', '行内没有任何元素被挤出行盒', overflowingRows.length === 0,
      overflowingRows.length ? `${overflowingRows.length} 行溢出，首个 ${overflowingRows[0].textContent.trim().slice(0, 20)}` : '0 行溢出');

  /* T4：分布条的分段是百分比宽，父盒 `overflow:hidden`。分段合计要正好铺满条宽 ——
     差得多就说明有类目被静默切掉了（这是这一页唯一的新裁切边界）。 */
  const bars = rows.map((r) => r.querySelector('[role="img"]')).filter((b) => b && b.getBoundingClientRect().width > 0);
  const barMismatch = bars.map((bar) => {
    const bw = bar.getBoundingClientRect().width;
    const sum = Array.from(bar.children).reduce((a, c) => a + c.getBoundingClientRect().width, 0);
    return { bw: Math.round(bw), sum: Math.round(sum), diff: Math.abs(bw - sum) };
  }).filter((m) => m.diff > 1.5);
  rel('T4', narrow ? '窄档按设计不画分布条（那一列改放题数）' : '分布条分段合计铺满条宽（没有类目被 hidden 切掉）',
      narrow ? bars.length === 0 : (bars.length === rows.length && barMismatch.length === 0),
      narrow ? `条数=${bars.length}（期望 0）`
             : `条数=${bars.length}/${rows.length}，超差 ${barMismatch.length} 条` +
               (barMismatch.length ? ` 首个 ${JSON.stringify(barMismatch[0])}` : ''));

  /* T5 —— 「能不能滚」。22 行在 1440x900 下装不完（稿子说「八行正好一屏装下」是按它
     虚构的 8 档说的），所以这一页必须真的滚得动。

     判别位是**最近那个溢出的祖先的 `overflow-y`**，不是「scrollTop 推得动吗」：
     `overflow:hidden` 的元素**程序能设 scrollTop、用户滚不动** —— 两者在
     「设了 scrollTop 之后内容动没动」这个观察里是同一个结果，拿它当判据会放行。
     2026-08-23 就是这么发现缺陷的：`galaxy-root` 是 `height:100dvh; overflow:hidden`
     而 `galaxy-main` 当时没有 overflow ⇒ 唯一溢出的祖先是那个 hidden 的外壳，
     真滚轮推三次纹丝不动。修法在 `MainLayout.tsx`（给 main 补 `overflowY:auto`）。 */
  const scrollableAncestor = (() => {
    let el = rows[0].parentElement;
    while (el && el !== document.documentElement) {
      if (el.scrollHeight > el.clientHeight + 1) return el;
      el = el.parentElement;
    }
    return document.scrollingElement;
  })();
  const ancestorOverflowY = getComputedStyle(scrollableAncestor).overflowY;
  const userScrollable = ['auto', 'scroll'].includes(ancestorOverflowY)
    || scrollableAncestor === document.scrollingElement;
  rel('T5a', '最近那个溢出的祖先是**用户滚得动**的（overflow-y auto/scroll，不是 hidden）',
      userScrollable,
      `${(scrollableAncestor.dataset && scrollableAncestor.dataset.testid) || scrollableAncestor.tagName}`
      + ` overflow-y=${ancestorOverflowY} sh=${scrollableAncestor.scrollHeight} ch=${scrollableAncestor.clientHeight}`);

  const before = scrollableAncestor.scrollTop;
  scrollableAncestor.scrollTop = scrollableAncestor.scrollHeight;
  const lastRow = box(rows[rows.length - 1]);
  rel('T5b', '滚到底后最后一档完整可见', lastRow.bottom <= vh + 1 && lastRow.h > 0,
      `lastRow.bottom=${lastRow.bottom} vh=${vh}`);
  scrollableAncestor.scrollTop = before;

  /* T6：级位在上、段位在下，且两节各自内部从弱到强。这条量的是**浏览器渲染出来的顺序**，
     不是数组顺序 —— 稿子的核心论证就是「顺序被 22 个等价方块抹掉了」。 */
  /* 档位名取**徽章那个盒子**的文本，不是整行 textContent 的第一段 ——
     徽章和题数之间没有空白节点，`textContent.split(/\s+/)[0]` 会拿到 `15K1000`，
     于是 `/K$/` 永远不匹配、T6 一路报「级位 0 档」还照样绿。又一次量错操作数。 */
  const order = rows.map((r) => ((r.firstElementChild && r.firstElementChild.textContent) || '').trim());
  const kyuCount = order.filter((s) => /K$/i.test(s)).length;
  const firstDan = order.findIndex((s) => /D$/i.test(s));
  rel('T6', '级位整段在段位之前（那道坎只出现一次）',
      firstDan === -1 || firstDan === kyuCount, `级位 ${kyuCount} 档，第一个段位在第 ${firstDan} 行`);

  /* T7 —— 行有没有真的铺开。`galaxy-main` 是 flex 列，页根那个 `mx:'auto'` 在 flex 里
     是 cross 轴的 auto margin：它会把这一项**压成内容宽**，而不是先铺满再居中。
     实测撞过一次：可用 896，行只有 489，右边 400 多像素空着 —— 而所有别的判据都是绿的
     （不溢出、不裁切、滚得动，全对，就是没铺开）。旧版是 Grid、卡片按百分比撑开，
     所以看不出来；换成按内容定宽的行以后才露。判据落在「行宽 vs 可用宽」上。 */
  const pageRoot = rows[0].parentElement.parentElement;
  const avail = Math.min(960, pageRoot.parentElement.clientWidth);   // 页根的 maxWidth 是 960
  const rowW = box(rows[0]).w;
  rel('T7', '行铺满可用宽度（不被 flex 里的 auto margin 压成内容宽）',
      rowW >= avail - 64 - 1,   // 减掉页根左右各 p:4 = 32px
      `行宽=${rowW} 可用=${avail} 期望>=${avail - 64}`);

  const failed = R.filter((r) => !r.pass).map((r) => r.id);
  const dataEnough = rows.length >= 12;
  return { vw, vh, narrow, rowCount: rows.length, dataEnough,
           verdict: !dataEnough ? '作废：档数 <12，多半没连上真库' : failed.length ? '红' : '绿',
           order, relations: R, failed };
})()
