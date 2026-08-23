/* 直播列表页（LivePage）承重实测 —— 真浏览器，jsdom 对这里的任何一条无权作证。
 *
 * 关系式先写死，具体像素只记录不作判据。判据按「浏览器算出来的布局结论」写。
 * 这一页的盒子链**不照抄**棋盘页的通用式：它的中段装的是对局列表，
 * 而棋盘 stage 本来就不该滚 —— 「能不能滚」只问中段（≥900）或整页（<900）。
 *
 * 跑法（需要后端 8001 + 已 build 的 static；两个页签各跑一次）：
 *   B=~/.claude/skills/gstack/browse/dist/browse
 *   $B viewport 1440x900 && $B goto http://127.0.0.1:8001/galaxy/live
 *   $B wait '[data-testid="board-rail-scroll"]' && $B wait --networkidle
 *   $B eval superpowers/tracks/galaxy-ui-redesign/loadbearing_live_list.js
 *   $B click 'button[role=tab]:nth-of-type(2)'   # 赛事预告，再 eval 一次
 *
 * 取数前置：`dataEnough` 必须为 true。装得下的数据量下量出来的数字一概不算 ——
 * 本机 live_upcoming 的 42 条全是 2026-04 的陈数据、端点按 `scheduled_time > now()`
 * 过滤后恒空，所以预告页签必须先造 fixture（scratchpad/livefix.sh make）才量得到。
 * 迁移前那轮把「本机没有直播数据」写进待议、430 档整条没测 —— 那个前提当时就是错的。
 *
 * 2026-08-23 实测（真数据：3 场直播 + 120 场已结束；预告页签 20 条 fixture）：
 *   四档视口 × 两个页签 = 8 轮，R1–R11 全过。关键几个数：
 *     1536 右栏 380 / 1440 右栏 340 / 1024 右栏 320（spec §2.3 三档各跑到一次）
 *     R5 三段严丝合缝：59+606+182 == 848（1440 档），一个像素都没被 hidden 吞掉
 *     R6 中段确实溢出：精选 sh=1741 / 预告 sh=2755，可视 606 —— 数据造够了
 *     棋盘 828（1440/1536）/ 684（1024）/ 410（430）
 *
 *   **改动前的树上直接量过一次**（不是变异，是真实树 12a3d3fe）：430x880 下
 *   右栏 `display: none`、高 0 宽 0，13 张 MatchCard 全在 DOM 里但一张都不可见。
 *   这条闸在旧树上返回的是 `fatal: shell not found`（它是照新壳写的），
 *   所以那个缺陷的证据来自直接探针，不来自这条闸 —— 两者都记下来，别混为一谈。
 */
(() => {
  const q = (id) => document.querySelector(`[data-testid="${id}"]`);
  const box = (el) => { const r = el.getBoundingClientRect(); return {
    x: Math.round(r.left), y: Math.round(r.top), w: Math.round(r.width), h: Math.round(r.height),
    right: Math.round(r.right), bottom: Math.round(r.bottom) }; };

  const shell = q('board-page-shell'), stage = q('board-stage'), rail = q('board-right-rail'),
        module_ = q('board-rail-module'), scroll = q('board-rail-scroll'), actions = q('board-rail-actions');
  if (!shell || !stage || !rail || !scroll || !actions) {
    return { fatal: 'shell not found —— 多半是还没渲染到，先 wait 那个 testid，别当布局错',
             shell: !!shell, stage: !!stage, rail: !!rail, scroll: !!scroll, actions: !!actions };
  }

  const vw = innerWidth, vh = innerHeight;
  const stacked = vw < 900;
  const B = { shell: box(shell), stage: box(stage), rail: box(rail),
              module: box(module_), scroll: box(scroll), actions: box(actions) };
  const canvas = stage.querySelector('canvas');
  const Bc = canvas ? box(canvas) : null;

  /* 造够数据了吗 —— 中段里的卡片。精选页签是 MatchCard，预告页签是 UpcomingList 的卡，
     两者都是 MuiCard；页签本身不是卡，用 scroll 作根就不会数进来。 */
  const cards = scroll.querySelectorAll('.MuiCard-root');
  const cardCount = cards.length;
  const activeTab = (() => {
    const sel = scroll.querySelector('button[role="tab"][aria-selected="true"]');
    return sel ? sel.textContent.trim() : '(无页签)';
  })();

  const R = [];
  const rel = (id, desc, pass, got) => R.push({ id, desc, pass, got });
  const pageScroller = document.scrollingElement;

  // —— 与视口档无关 ——
  /* R1 量的是**可见盒子**的最右沿，不是 `shell.scrollWidth`。
     第一版写的是 scrollWidth，430 档假红了一次：435 vs 430。逐层查下来那 5px 来自
     PlaybackBar 里 MUI Slider 滑块的 `::after` —— 一个 42px 的**隐形触摸靶**。
     可见的滑块本体 right=422 < shell.right=430，什么都没被裁；而 ≥900 档右栏自带
     `overflow:hidden` 会把它吸收掉，所以只有窄档冒出来。
     判据的意图是「有没有东西被静默裁掉 / 够不着」，隐形触摸靶两样都不是。
     同族：[[reference_gate_measures_wrong_operand]]。scrollWidth 仍作为观察值记下来。 */
  const maxRight = Math.max(...Array.from(shell.querySelectorAll('*'))
    .map((el) => el.getBoundingClientRect())
    .filter((r) => r.width > 0 && r.height > 0)
    .map((r) => r.right));
  rel('R1', '没有可见内容被裁到容器外: max(descendant.right) <= shell.right+1',
      maxRight <= B.shell.right + 1, `maxRight=${Math.round(maxRight)} shell.right=${B.shell.right}`);
  rel('R2', '整页不横向滚: scrollingElement.scrollWidth <= innerWidth+1',
      pageScroller.scrollWidth <= vw + 1, `${pageScroller.scrollWidth} vs ${vw}`);

  if (!stacked) {
    const expectRail = vw >= 1536 ? 380 : vw >= 1200 ? 340 : 320;   // spec §2.3 三档
    rel('R3', '并排: rail.left >= stage.right-1',
        B.rail.x >= B.stage.right - 1, `rail.left=${B.rail.x} stage.right=${B.stage.right}`);
    rel('R4', `右栏定宽 ${expectRail}（spec §2.3 三档）`,
        Math.abs(B.rail.w - expectRail) <= 1, `rail.w=${B.rail.w} 期望=${expectRail}`);
    rel('R5', '右栏三段严丝合缝: |module.h + scroll.clientHeight + actions.h - rail.clientHeight| <= 1'
            + '（一个像素都没被 overflow:hidden 静默吞掉）',
        Math.abs(B.module.h + scroll.clientHeight + B.actions.h - rail.clientHeight) <= 1,
        `${B.module.h}+${scroll.clientHeight}+${B.actions.h} vs ${rail.clientHeight}`);
    rel('R6', '中段确实溢出（数据造够了的验收）: scroll.scrollHeight > scroll.clientHeight+1',
        scroll.scrollHeight > scroll.clientHeight + 1,
        `scroll.sh=${scroll.scrollHeight} ch=${scroll.clientHeight}`);
    rel('R7', '中段是右栏里唯一可滚的',
        (() => Array.from(rail.querySelectorAll('*')).every((el) =>
          el === scroll || !(el.scrollHeight > el.clientHeight + 1 &&
            ['auto', 'scroll'].includes(getComputedStyle(el).overflowY))))(),
        Array.from(rail.querySelectorAll('*')).filter((el) => el !== scroll &&
          el.scrollHeight > el.clientHeight + 1 &&
          ['auto', 'scroll'].includes(getComputedStyle(el).overflowY))
          .map((el) => el.dataset.testid || el.className.toString().slice(0, 40)).join(' | ') || '无');
    rel('R8', '动作区完整可见（没被裁）: actions.bottom <= rail.bottom+1',
        B.actions.bottom <= B.rail.bottom + 1, `actions.bottom=${B.actions.bottom} rail.bottom=${B.rail.bottom}`);
    /* 方的是**棋盘本体**（canvas），不是 `board-stage`。stage 在 ≥900 档是 grid 的
       `minmax(0,1fr)` 那一列，本来就该吃满剩余宽高（这一档量到 884x848）。
       第一版把 R9 写成 `|stage.w - stage.h| <= 2` 于是假红了一次 ——
       判据落错了操作数，不是页面错。 */
    rel('R9', '棋盘本体是方的: |canvas.w - canvas.h| <= 2', canvas
        ? Math.abs(Bc.w - Bc.h) <= 2 : false, canvas ? `${Bc.w}x${Bc.h}` : '没有 canvas');
    rel('R10', '棋盘完整落在 stage 内（四边都没被裁）', canvas
        ? (Bc.x >= B.stage.x - 1 && Bc.right <= B.stage.right + 1
           && Bc.y >= B.stage.y - 1 && Bc.bottom <= B.stage.bottom + 1) : false,
        canvas ? `canvas[${Bc.x},${Bc.y},${Bc.right},${Bc.bottom}] stage[${B.stage.x},${B.stage.y},${B.stage.right},${B.stage.bottom}]` : '没有 canvas');
    rel('R10b', '棋盘不撑破容器高: stage.h <= shell.clientHeight+1',
        B.stage.h <= shell.clientHeight + 1, `stage.h=${B.stage.h} shell.ch=${shell.clientHeight}`);
  } else {
    rel('R3', '堆叠: rail.top >= stage.bottom-1（右栏落到棋盘下方，不并排）',
        B.rail.y >= B.stage.bottom - 1, `rail.top=${B.rail.y} stage.bottom=${B.stage.bottom}`);
    rel('R4', '右栏拿到整幅宽: |rail.w - shell.clientWidth| <= 1',
        Math.abs(B.rail.w - shell.clientWidth) <= 1, `rail.w=${B.rail.w} shell.cw=${shell.clientWidth}`);
    /* ↓ 这一条就是本次要修的那个缺陷。迁移前右栏是 `display:{xs:'none',md:'flex'}`，
         430 竖屏下整条列表直接消失、只剩一块棋盘 ⇒ rail.h === 0 且 cardCount === 0。 */
    rel('R5', '列表在窄档**存在且非零高**（迁移前这里是 display:none）',
        B.rail.h > 0 && cardCount > 0 && box(cards[0]).h > 0,
        `rail.h=${B.rail.h} cards=${cardCount} card0.h=${cardCount ? box(cards[0]).h : 'n/a'}`);
    rel('R6', '整页能滚（窄档唯一可滚处是 shell 自己）',
        shell.scrollHeight > shell.clientHeight + 1 || pageScroller.scrollHeight > vh + 1,
        `shell.sh=${shell.scrollHeight} ch=${shell.clientHeight}`);
    rel('R8', '棋盘不超出视口宽: stage.w <= vw+1', B.stage.w <= vw + 1, `stage.w=${B.stage.w} vw=${vw}`);
    rel('R9', '棋盘本体是方的: |canvas.w - canvas.h| <= 2', canvas
        ? Math.abs(Bc.w - Bc.h) <= 2 : false, canvas ? `${Bc.w}x${Bc.h}` : '没有 canvas');
  }

  /* R11 —— 滚到底之后，最后一张卡完整可见。这一条量的是「够不够得着」，
     必须真的滚过去读，不能从 scrollHeight 推。 */
  const scroller = stacked ? (shell.scrollHeight > shell.clientHeight + 1 ? shell : pageScroller) : scroll;
  const before = scroller.scrollTop;
  scroller.scrollTop = scroller.scrollHeight;
  const lastCard = cardCount ? box(cards[cardCount - 1]) : null;
  const viewportBottom = stacked ? vh : box(scroll).bottom;
  rel('R11', '滚到底后最后一张卡完整可见: lastCard.bottom <= 可视下沿+1',
      lastCard ? lastCard.bottom <= viewportBottom + 1 : false,
      lastCard ? `lastCard.bottom=${lastCard.bottom} 下沿=${viewportBottom}` : '没有卡片');
  scroller.scrollTop = before;

  return { vw, vh, stacked, activeTab, cardCount, dataEnough: cardCount >= 8,
           boxes: B, lastCard,
           /* 观察值，不作判据：窄档这里是 435 vs 430，差的 5px 是滑块的隐形触摸靶（见 R1）。 */
           shellScrollWidth: shell.scrollWidth, shellClientWidth: shell.clientWidth,
           relations: R, failed: R.filter((r) => !r.pass).map((r) => r.id) };
})()
