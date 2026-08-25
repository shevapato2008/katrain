/* 承重实测 —— 关系式先写死，再读数。
   E1 动作区永远完整落在 app 盒子里（bottom <= app.bottom+1）
   E2 模块牌永远贴着右栏顶（top >= rail.top-1）
   E3 桌面档：右栏本身不滚（rail.scrollHeight <= clientHeight+1）
   E4 桌面档：shell 不滚（横竖都不）
   E5 桌面档：main 不滚
   E6 棋盘不溢出 stage-box
   E7 每个改版棋盘页在 1440×900 下至少有一个分支真的把中段撑到要滚
      —— 装得下的数据量下量出来的数字不算
   E8 body 无横向滚动 */
(() => {
  const R = [], overflowed = {};
  const keep = { screen: S.screen, branch: S.branch, vp: S.vp, mode: S.mode, dialog: S.dialog };
  const fail = (t, m) => R.push({ t, m });
  S.mode = 'new'; S.stress = true;
  for (const sc of SCREENS) {
    if (sc.id === 'overview' || !V2[sc.id] && sc.kind !== 'board') continue;
    for (const b of (sc.branches || [{ id: 'default' }])) {
      for (const v of VPS) {
        S.screen = sc.id; S.branch = b.id; S.vp = v.id; S.dialog = null;
        renderFrame();
        const tag = `${sc.id}/${b.id}/${v.id}`;
        const app = document.getElementById('app');
        const shell = app.querySelector('.shell');
        /* 改版里有的 V2 是内容页（死活题难度列表），本来就没有棋盘壳 —— 跳过，
           但它自己那条「一屏装得下不用滚」的期望在 09-overview 的量里单独验。 */
        if (!shell) { if (!app.querySelector('.content')) fail(tag, 'no .shell and no .content'); continue; }
        const mob = v.id === '430x880';
        const rail = shell.querySelector('.rail');
        const mod = shell.querySelector('.rail-module');
        const scr = shell.querySelector('.rail-scroll');
        const acts = shell.querySelector('.rail-actions');
        const stage = shell.querySelector('.stage-box');
        const cv = shell.querySelector('.boardcv');
        const k = (/scale\(([\d.]+)\)/.exec(app.style.transform || '') || [0, 1])[1] * 1;
        const rc = (e) => { const r = e.getBoundingClientRect(); return { t: r.top / k, b: r.bottom / k, l: r.left / k, r: r.right / k }; };
        const A = rc(app);

        if (!mob) {
          if (rc(acts).b > A.b + 1) fail(tag, `E1 动作区被切: ${rc(acts).b.toFixed(0)} > ${A.b.toFixed(0)}`);
          if (rc(mod).t < rc(rail).t - 1) fail(tag, 'E2 模块牌不在右栏顶');
          if (rail.scrollHeight > rail.clientHeight + 1) fail(tag, `E3 右栏自己在滚 ${rail.scrollHeight}>${rail.clientHeight}`);
          if (shell.scrollHeight > shell.clientHeight + 1) fail(tag, `E4 shell 竖向溢出 ${shell.scrollHeight}>${shell.clientHeight}`);
          if (shell.scrollWidth > shell.clientWidth + 1) fail(tag, `E4 shell 横向溢出 ${shell.scrollWidth}>${shell.clientWidth}`);
          const main = app.querySelector('.main');
          if (main.scrollHeight > main.clientHeight + 1) fail(tag, `E5 main 溢出 ${main.scrollHeight}>${main.clientHeight}`);
          if (scr && scr.scrollHeight > scr.clientHeight + 1) { overflowed[sc.id] = overflowed[sc.id] || {}; overflowed[sc.id][v.id] = (overflowed[sc.id][v.id] || 0) + 1; }
        }
        if (cv) {
          const px = Number(cv.dataset.edge);
          if (px > stage.clientWidth + 1 || px > stage.clientHeight + 1) fail(tag, `E6 棋盘 ${px} 溢出 stage ${stage.clientWidth}×${stage.clientHeight}`);
        }
        if (document.documentElement.scrollWidth > window.innerWidth + 1) fail(tag, 'E8 页面横向滚动');
      }
    }
  }
  const noOverflow = Object.keys(V2).filter(id => !(overflowed[id] && overflowed[id]['1280x640']));
  S.stress = false; Object.assign(S, keep); renderFrame();
  return JSON.stringify({ fails: R, overflowed, neverOverflowed: noOverflow });
})()
