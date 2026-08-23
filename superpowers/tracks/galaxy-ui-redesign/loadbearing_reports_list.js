/* 复盘列表页（ReportsPage）承重实测 —— 真浏览器，jsdom 对这里的任何一条无权作证。
 *
 * **取代 `loadbearing_reports_page.js`**（已删）。那一份量的是迁移前那条
 * 「reports-split / reports-preview-pane / reports-list-pane」的两栏链，
 * 迁到 `BoardPageShell` 之后那四个 testid 一个都不存在了 —— 留着它只会
 * 在拿不到操作数时 fatal 或静默跳过。闸的操作数没了，闸就得跟着换，不是留着当摆设。
 * （同族：[[reference_gate_lives_where_operands_are]]）
 *
 * 关系式先写死，具体像素只记录不作判据。
 * R1–R10 是 `BoardPageShell` 这条链共有的（与 `loadbearing_live_list.js` 同形）；
 * **R12–R14 是这一页自己的**：分页够不够得着、没选棋局时动作区是空的、未登录支。
 *
 * 跑法（需要后端 8001 + 已 build 的 static + 一个名下有 >12 局的登录态）：
 *   B=~/.claude/skills/gstack/browse/dist/browse
 *   $B viewport 1440x900 && $B goto http://127.0.0.1:8001/galaxy/report
 *   $B wait '[data-testid="reports-list"]' && $B wait --networkidle
 *   $B eval superpowers/tracks/galaxy-ui-redesign/loadbearing_reports_list.js
 *
 * 取数前置：`dataEnough` 必须为 true（每页 12 条，要看到分页得 >12 局）。
 * 装得下的数据量下量出来的数字一概不算 —— 返回值是**三态**不是两态，见 `verdict`。
 *
 * 2026-08-23 实测（探针账号名下 20 局 fixture）：
 *   四档视口 × 已登录 + 未登录支 = 5 轮，R1–R14 全过。关键几个数：
 *     1536 右栏 380 / 1440 右栏 340 / 1024 右栏 320（三档各跑到一次）
 *     R5 三段严丝合缝：59+684+104 == 848（1440 档）
 *     R6 中段实测溢出 sh=1934 vs 可视 684；R12 分页 bottom=779 <= 下沿 796
 *     棋盘 828 / 684 / 410 —— 迁移前这一页棋盘只有 467，是全站最小的一块
 *
 *   `verdict` 三态各跑到一次（[[reference_every_gate_branch_must_execute_once]]）：
 *     ① 已登录 + 20 局      → 绿
 *     ② 已登录 + 0 局（空态）→ 绿（R6/R11/R12 按设计跳过；R13 量到 59+789+0 == 848，
 *                              动作区高 0 而三段和仍然严丝合缝）
 *     ③ 未登录支            → 绿（R14：登录键在，动作区高 86）
 *     ④ 已登录 + 只有 3 局   → **作废**，不是绿也不是红。这一条是特意设计的：
 *                              装得下的数据量下 R6/R12 会红，若报成红，下一个人
 *                              会去「修」一个根本没错的版式。
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

  const list = q('reports-list');
  const cards = list ? list.querySelectorAll('.MuiCard-root, [data-testid="report-game-card"]') : [];
  const cardCount = cards.length;
  const pager = scroll.querySelector('.MuiPagination-root');
  const guest = !!q('reports-login');
  /* 三种「按设计就没有列表」的支：未登录 / 名下 0 局。它们是真实产品状态，
     R6/R11/R12（都以「列表长到要滚」为前提）在这几支上不适用，跳过。
     但**不能**因此就绿：`dataEnough` 单独守住「列表非空却没造够」那种情况 ——
     只有 3 张卡时装得下，量出来的数字一概不算，整轮作废（见返回值的 verdict）。 */
  const emptyState = !guest && cardCount === 0;
  const noList = guest || emptyState;

  const R = [];
  const rel = (id, desc, pass, got) => R.push({ id, desc, pass, got });
  const pageScroller = document.scrollingElement;

  // —— 外壳共有的 ——
  const maxRight = Math.max(...Array.from(shell.querySelectorAll('*'))
    .map((el) => el.getBoundingClientRect())
    .filter((r) => r.width > 0 && r.height > 0).map((r) => r.right));
  rel('R1', '没有可见内容被裁到容器外: max(descendant.right) <= shell.right+1',
      maxRight <= B.shell.right + 1, `maxRight=${Math.round(maxRight)} shell.right=${B.shell.right}`);
  rel('R2', '整页不横向滚', pageScroller.scrollWidth <= vw + 1, `${pageScroller.scrollWidth} vs ${vw}`);

  if (!stacked) {
    const expectRail = vw >= 1536 ? 380 : vw >= 1200 ? 340 : 320;
    rel('R3', '并排: rail.left >= stage.right-1', B.rail.x >= B.stage.right - 1,
        `rail.left=${B.rail.x} stage.right=${B.stage.right}`);
    rel('R4', `右栏定宽 ${expectRail}（spec §2.3 三档）`, Math.abs(B.rail.w - expectRail) <= 1,
        `rail.w=${B.rail.w} 期望=${expectRail}`);
    rel('R5', '右栏三段严丝合缝（一个像素都没被 hidden 吞掉）',
        Math.abs(B.module.h + scroll.clientHeight + B.actions.h - rail.clientHeight) <= 1,
        `${B.module.h}+${scroll.clientHeight}+${B.actions.h} vs ${rail.clientHeight}`);
    /* R6 是「数据造够了」的**前置**，不是版式不变量 —— 未登录支中段只有一条 Alert，
       按设计就没有可溢出的东西。那一支跳过，不是把闸改绿：它在已登录支照跑。 */
    rel('R6', '中段确实溢出（数据造够了的验收）',
        noList ? true : scroll.scrollHeight > scroll.clientHeight + 1,
        noList ? '无列表支（未登录 / 名下 0 局），跳过' : `scroll.sh=${scroll.scrollHeight} ch=${scroll.clientHeight}`);
    rel('R7', '中段是右栏里唯一可滚的',
        Array.from(rail.querySelectorAll('*')).every((el) => el === scroll ||
          !(el.scrollHeight > el.clientHeight + 1 && ['auto','scroll'].includes(getComputedStyle(el).overflowY))),
        Array.from(rail.querySelectorAll('*')).filter((el) => el !== scroll &&
          el.scrollHeight > el.clientHeight + 1 && ['auto','scroll'].includes(getComputedStyle(el).overflowY))
          .map((el) => el.dataset.testid || el.className.toString().slice(0, 40)).join(' | ') || '无');
    rel('R8', '动作区完整可见: actions.bottom <= rail.bottom+1',
        B.actions.bottom <= B.rail.bottom + 1, `actions.bottom=${B.actions.bottom} rail.bottom=${B.rail.bottom}`);
    rel('R9', '棋盘本体是方的', canvas ? Math.abs(Bc.w - Bc.h) <= 2 : true,
        canvas ? `${Bc.w}x${Bc.h}` : '本支无棋盘（空态/未登录），跳过');
    rel('R10', '棋盘不撑破容器高: stage.h <= shell.clientHeight+1',
        B.stage.h <= shell.clientHeight + 1, `stage.h=${B.stage.h} shell.ch=${shell.clientHeight}`);
  } else {
    rel('R3', '堆叠: rail.top >= stage.bottom-1', B.rail.y >= B.stage.bottom - 1,
        `rail.top=${B.rail.y} stage.bottom=${B.stage.bottom}`);
    rel('R4', '右栏拿到整幅宽', Math.abs(B.rail.w - shell.clientWidth) <= 1,
        `rail.w=${B.rail.w} shell.cw=${shell.clientWidth}`);
    rel('R5', '列表存在且非零高', B.rail.h > 0 && (guest || cardCount > 0),
        `rail.h=${B.rail.h} cards=${cardCount} guest=${guest}`);
    rel('R6', '整页能滚', shell.scrollHeight > shell.clientHeight + 1 || pageScroller.scrollHeight > vh + 1,
        `shell.sh=${shell.scrollHeight} ch=${shell.clientHeight}`);
    rel('R8', '棋盘不超出视口宽', B.stage.w <= vw + 1, `stage.w=${B.stage.w} vw=${vw}`);
    rel('R9', '棋盘本体是方的', canvas ? Math.abs(Bc.w - Bc.h) <= 2 : true,
        canvas ? `${Bc.w}x${Bc.h}` : '本支无棋盘，跳过');
  }

  // —— 这一页自己的三条 ——
  const scroller = stacked ? (shell.scrollHeight > shell.clientHeight + 1 ? shell : pageScroller) : scroll;
  const before = scroller.scrollTop;
  scroller.scrollTop = scroller.scrollHeight;
  const lastCard = cardCount ? box(cards[cardCount - 1]) : null;
  const pagerBox = pager ? box(pager) : null;
  const visibleBottom = stacked ? vh : box(scroll).bottom;
  rel('R11', '滚到底后最后一张棋局卡完整可见',
      noList ? true : (lastCard ? lastCard.bottom <= visibleBottom + 1 : false),
      noList ? '无列表支，跳过' : (lastCard ? `lastCard.bottom=${lastCard.bottom} 下沿=${visibleBottom}` : '没有卡片'));
  /* R12：分页是中段的**最后**一块，S4 记过第 600 页那种四位数居中会折成两行。
     这里量的是「滚到底之后它整块露得出来」，不是「它有多高」。 */
  rel('R12', '滚到底后分页整块可见（它在中段最末，比最后一张卡还靠下）',
      noList ? true : (pagerBox ? pagerBox.bottom <= visibleBottom + 1 && pagerBox.h > 0 : false),
      noList ? '无列表支，跳过' : (pagerBox ? `pager.bottom=${pagerBox.bottom} h=${pagerBox.h} 下沿=${visibleBottom}` : '没有分页（局数 <= 一页）'));
  scroller.scrollTop = before;

  /* R13：没选中棋局时 `actions` 传的是 null —— 动作区高 0，而三段和仍要等于右栏高
     （R5 已经覆盖等式，这里单独把「空动作区」这个分支钉住，防止有人为了好看塞个占位）。 */
  rel('R13', '没有预览时动作区是空的（不塞占位控件）',
      canvas ? true : (guest ? B.actions.h > 0 : B.actions.h === 0),
      `canvas=${!!canvas} guest=${guest} actions.h=${B.actions.h}`);

  /* R14：未登录支也走同一个壳（迁移前它是一块光秃秃的 Alert，连左右栏都没有）。 */
  rel('R14', '未登录支同样在统一外壳里，且动作区有登录键',
      guest ? (!!q('reports-login') && B.actions.h > 0) : true,
      guest ? `login 键在=${!!q('reports-login')} actions.h=${B.actions.h}` : '已登录支，跳过');

  const failed = R.filter((r) => !r.pass).map((r) => r.id);
  const dataEnough = noList || cardCount >= 8;
  return { vw, vh, stacked, guest, emptyState, cardCount, dataEnough,
           /* 三态，不是两态。「列表非空但没造够」既不是绿也不是红 —— 是**作废**：
              装得下的数据量下量出来的数字一概不算，别拿它当通过，也别去「修」版式。 */
           verdict: !dataEnough ? '作废：列表非空但没造够（<8 张卡），本轮不作数'
                  : failed.length ? '红' : '绿',
           boxes: B, lastCard, pagerBox,
           shellScrollWidth: shell.scrollWidth, shellClientWidth: shell.clientWidth,
           relations: R, failed };
})()
