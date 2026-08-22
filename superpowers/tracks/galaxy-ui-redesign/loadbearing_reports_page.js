/* 复盘页（ReportsPage）承重实测 —— 真浏览器，jsdom 对这里的任何一条无权作证。
 *
 * 关系式先写死，具体像素只记录不作判据。判据全部按「浏览器算出来的布局结论」写，
 * 不按源码里写了什么写。
 *
 * 跑法（需要后端 8001 + vite 8901 + 一个有棋局的登录态）：
 *   B=~/.claude/skills/gstack/browse/dist/browse
 *   $B viewport 430x880 && $B goto http://localhost:8901/galaxy/report
 *   $B wait '[data-testid="reports-list-scroll"]' && $B wait --networkidle
 *   $B eval superpowers/tracks/galaxy-ui-redesign/loadbearing_reports_page.js
 *
 * 2026-08-22 实测（用户 fan 的 12 局真实数据）：
 *   改前 430x880 → R1/R3/R4/R5/R6/R7 六条全红：
 *     左栏被压到 48px（只剩 p:3 的内边距，提示文字竖排成一列），右栏仍占 520,
 *     split.scrollWidth 568 vs clientWidth 430 —— 超出的 118px 被 overflow:hidden 切掉,
 *     没有任何地方能滚过去。
 *   改后 430 / 899 全绿（堆叠），900 / 1024 / 1440 全绿（并排）。
 *   1440 档改前改后逐数相同（704/520/1224, scroll.sh 1704 ch 599, lastCard 同一组数）——
 *   这就是「宽档零回归」的证据，不是「看起来没变」。
 *   另外单量了一条 R7 量不到的：把 split 滚到底，最后一张卡 top=669 bottom=800
 *   left=20 right=410，完全在 430x880 视口内且没被底部导航压住。
 *
 * 一处**必须提防**的取数陷阱：`reload` + `wait --networkidle` 之后 split 可能还没渲染
 * （数据还在路上，页面停在登录/加载分支），此时脚本返回 `{fatal:'pane not found'}`。
 * 那不是「布局是错的」，是「还没量到」—— 一定要先 `wait '[data-testid=...]'`。
 * 2026-08-22 实跑时 430/900/1024 三档就这样各假红过一次。
 */
(() => {
  const q = (id) => document.querySelector(`[data-testid="${id}"]`);
  const box = (el) => { const r = el.getBoundingClientRect(); return {
    x: Math.round(r.left), y: Math.round(r.top), w: Math.round(r.width), h: Math.round(r.height),
    right: Math.round(r.right), bottom: Math.round(r.bottom) }; };

  const split = q('reports-split'), left = q('reports-preview-pane'),
        right = q('reports-list-pane'), scroll = q('reports-list-scroll'),
        main = q('galaxy-main');
  if (!split || !left || !right) return { fatal: 'pane not found', split: !!split, left: !!left, right: !!right };

  const vw = innerWidth, vh = innerHeight;
  const stacked = vw < 900;
  const B = { split: box(split), left: box(left), right: box(right),
              scroll: scroll ? box(scroll) : null, main: main ? box(main) : null };

  // 造够数据了吗：列表里有几张卡
  const cards = right.querySelectorAll('[data-testid="report-game-card"], .MuiCard-root');
  const cardCount = cards.length;
  const lastCard = cardCount ? box(cards[cardCount - 1]) : null;

  const scrollerOverflows = scroll ? scroll.scrollHeight > scroll.clientHeight + 1 : false;
  const pageScroller = document.scrollingElement;

  const R = [];
  const rel = (id, desc, pass, got) => R.push({ id, desc, pass, got });

  // —— 与视口档无关的两条 ——
  rel('R1', '承重容器不横向溢出: split.scrollWidth <= split.clientWidth+1',
      split.scrollWidth <= split.clientWidth + 1,
      `${split.scrollWidth} vs ${split.clientWidth}`);
  rel('R2', '整页不横向滚: scrollingElement.scrollWidth <= innerWidth+1',
      pageScroller.scrollWidth <= vw + 1,
      `${pageScroller.scrollWidth} vs ${vw}`);

  if (stacked) {
    // —— 窄档：必须堆叠 ——
    rel('R3', '堆叠: right.top >= left.bottom-1（右栏在左栏下方，不并排）',
        B.right.y >= B.left.bottom - 1, `right.top=${B.right.y} left.bottom=${B.left.bottom}`);
    rel('R4', '左栏拿到整幅宽: |left.w - split.clientWidth| <= 1',
        Math.abs(B.left.w - split.clientWidth) <= 1, `left.w=${B.left.w} split.cw=${split.clientWidth}`);
    rel('R5', '右栏拿到整幅宽: |right.w - split.clientWidth| <= 1',
        Math.abs(B.right.w - split.clientWidth) <= 1, `right.w=${B.right.w} split.cw=${split.clientWidth}`);
    rel('R6', '两栏合计不超视口: left.w + right.w <= vw+1（并排时才有意义，堆叠下等价于各自 <= vw）',
        B.left.w <= vw + 1 && B.right.w <= vw + 1, `left.w=${B.left.w} right.w=${B.right.w} vw=${vw}`);
    rel('R7', '底部内容够得着: split 自身或其祖先能滚到 right.bottom',
        (() => {
          let el = split;
          while (el && el !== document.body) {
            if (el.scrollHeight > el.clientHeight + 1 &&
                ['auto','scroll'].includes(getComputedStyle(el).overflowY)) return true;
            el = el.parentElement;
          }
          return pageScroller.scrollHeight > vh + 1;
        })(), `split.sh=${split.scrollHeight} split.ch=${split.clientHeight}`);
  } else {
    // —— 宽档：必须并排、右栏定宽、列表内部滚 ——
    rel('R3', '并排: right.left >= left.right-1',
        B.right.x >= B.left.right - 1, `right.left=${B.right.x} left.right=${B.left.right}`);
    rel('R4', '右栏定宽 520', B.right.w === 520, `right.w=${B.right.w}`);
    rel('R5', '左栏吃掉余下宽度: |left.w - (split.clientWidth-520)| <= 1',
        Math.abs(B.left.w - (split.clientWidth - 520)) <= 1,
        `left.w=${B.left.w} 期望=${split.clientWidth - 520}`);
    rel('R6', '两栏合计 == 容器宽: |left.w+right.w - split.clientWidth| <= 1',
        Math.abs(B.left.w + B.right.w - split.clientWidth) <= 1,
        `${B.left.w}+${B.right.w} vs ${split.clientWidth}`);
    rel('R7', '列表在自己内部滚（宽档唯一可滚处）', scrollerOverflows,
        scroll ? `scroll.sh=${scroll.scrollHeight} ch=${scroll.clientHeight}` : 'no scroller');
  }

  return { vw, vh, stacked, cardCount, boxes: B, lastCard,
           dataEnough: cardCount >= 8,
           relations: R, failed: R.filter((r) => !r.pass).map((r) => r.id) };
})()
