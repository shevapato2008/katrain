/* 棋盘页承重实测探针 —— 六个棋盘页共用。
 *
 * 判据先写死成关系式，具体像素只记录不作判据（用户级 CLAUDE.md 的硬性要求）。
 * 断言对象全部是浏览器算出的布局结论：盒子的实际尺寸、能不能滚、有没有被裁。
 * jsdom 对这些无权作证，所以这一关只能在真浏览器里跑。
 *
 * 右栏宽度按 spec §2.3 的四档：≥1920→520，1536–1919→420，1200–1535→360，
 * 900–1199→320，<900 不再是侧栏而是棋盘下方的全宽段。
 */
(() => {
  const q = (s) => document.querySelector(s);
  const shell = q('[data-testid="board-page-shell"]');
  if (!shell) return JSON.stringify({ error: 'board-page-shell not found', url: location.pathname });

  const rail = q('[data-testid="board-right-rail"]');
  const stage = q('[data-testid="board-stage"]');
  const mod = q('[data-testid="board-rail-module"]');
  const scroll = q('[data-testid="board-rail-scroll"]');
  const acts = q('[data-testid="board-rail-actions"]');
  const canvas = stage ? stage.querySelector('canvas') : null;

  const box = (el) => {
    if (!el) return null;
    const b = el.getBoundingClientRect();
    return { x: Math.round(b.x), y: Math.round(b.y), w: Math.round(b.width), h: Math.round(b.height) };
  };
  const over = (el) => (el ? el.scrollHeight - el.clientHeight : null);

  const vw = innerWidth, vh = innerHeight;
  const wide = vw >= 900;
  const expectRail = vw >= 1920 ? 520 : vw >= 1536 ? 420 : vw >= 1200 ? 360 : vw >= 900 ? 320 : null;

  const b = { shell: box(shell), rail: box(rail), stage: box(stage), mod: box(mod), scroll: box(scroll), acts: box(acts), canvas: box(canvas) };
  const checks = [];
  const ok = (name, pass, detail) => checks.push({ name, pass: !!pass, detail });

  /* R1 右栏宽度落在 spec 的档位上（横屏）；竖屏时它是棋盘下方的全宽段。
     竖屏这一档比的是 shell 的 clientWidth 不是 border-box 宽 —— 桌面 Chromium 的
     经典滚动条会从里面吃掉十来个像素，真机是叠加式滚动条不占布局宽度。
     量到的 419 vs 430 就是这条，不是版式问题。 */
  const shellInner = shell.clientWidth;
  ok('R1 右栏宽度=spec 档位', wide ? b.rail && b.rail.w === expectRail : b.rail && Math.abs(b.rail.w - shellInner) <= 1,
    { got: b.rail && b.rail.w, expect: wide ? expectRail : shellInner });

  /* R2 棋盘上方不留任何东西：棋盘列的顶就是 shell 内容的顶 */
  ok('R2 棋盘上方为空', b.stage && b.shell && b.stage.y - b.shell.y <= 1, { stageTop: b.stage && b.stage.y, shellTop: b.shell && b.shell.y });

  /* R3 棋盘是正方形 */
  ok('R3 棋盘正方', b.canvas && Math.abs(b.canvas.w - b.canvas.h) <= 2, b.canvas);

  /* R4 棋盘吃满棋盘列剩下的空间。受限的那一维只允许剩下设计规定的留白：
     BoardPageShell 的 stage padding 6 + LiveBoard 自己的 4 = 每边 10，共 20
     （见 BoardPageShell.tsx 那条注释：「preserves the approved 10px visible board inset」）。
     所以判据是「受限维的余量 ≤ 24」，不是 ≤16 —— 第一版写窄了，改的是判据不是页面。 */
  const INSET = 24;
  const slackW = b.stage && b.canvas ? b.stage.w - b.canvas.w : null;
  const slackH = b.stage && b.canvas ? b.stage.h - b.canvas.h : null;
  ok('R4 棋盘填满可用区', slackW !== null && Math.min(slackW, slackH) <= INSET, { slackW, slackH, allow: INSET });

  /* R5 右栏三段里只有中段可滚 */
  ok('R5 只有中段可滚', over(scroll) >= 0 && over(mod) <= 0 && over(acts) <= 0,
    { scroll: over(scroll), module: over(mod), actions: over(acts) });

  /* R6 横屏时 shell 自己不滚（滚动边界在中段，不该外溢到整页） */
  ok('R6 shell 不自滚(横屏)', !wide || over(shell) <= 1, { shell: over(shell) });

  /* R7 整页不横向滚 */
  const hx = document.documentElement.scrollWidth - document.documentElement.clientWidth;
  ok('R7 无横向滚动', hx <= 1, { overflowX: hx });

  /* R8 动作区完整落在右栏里，没有被裁到看不见 */
  ok('R8 动作区未被裁', !wide || (b.acts && b.rail && b.acts.y + b.acts.h <= b.rail.y + b.rail.h + 1),
    { actsBottom: b.acts && b.acts.y + b.acts.h, railBottom: b.rail && b.rail.y + b.rail.h });

  /* R9 这一档到底有没有把中段撑到需要滚 —— 「装得下的数据量下量出来的数字一概不算」。
     不溢出不算错，但必须至少有一档溢出过，否则「能不能滚」这一问根本没被问到。 */
  ok('R9 本档中段已溢出(信息位)', over(scroll) > 0, { railScrolls: over(scroll) });

  return JSON.stringify({
    vp: vw + 'x' + vh, url: location.pathname,
    fails: checks.filter(c => !c.pass && c.name !== 'R9 本档中段已溢出(信息位)'),
    overflowed: checks.find(c => c.name === 'R9 本档中段已溢出(信息位)').pass,
    railScrolls: over(scroll),          // >0 说明这一档真的把中段撑溢出了
    px: b,                              // 只记录，不作判据
  });
})()
