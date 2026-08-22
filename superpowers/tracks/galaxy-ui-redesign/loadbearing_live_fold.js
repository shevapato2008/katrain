/* 直播观战页：显示开关在不在折线以下。
 *
 * 「折线」= 右栏中段（`board-rail-scroll`，统一版式里唯一可滚的那一段）的可视下沿。
 * 判据：开关块的**顶边**必须落在中段的可视范围内 —— 顶边都看不见，用户就不知道有这组开关。
 * 具体像素只记录不作判据。
 */
(() => {
  const q = (id) => document.querySelector(`[data-testid="${id}"]`);
  const box = (el) => { const r = el.getBoundingClientRect(); return {
    y: Math.round(r.top), h: Math.round(r.height), bottom: Math.round(r.bottom) }; };

  const scroll = q('board-rail-scroll');
  const grid = q('live-match-display-controls-grid');
  const coord = q('live-coordinate-toggle');
  if (!scroll || !grid) return { fatal: 'not found', scroll: !!scroll, grid: !!grid };

  const sr = scroll.getBoundingClientRect();
  const gr = grid.getBoundingClientRect();
  const cr = coord ? coord.getBoundingClientRect() : null;

  // 开关块相对中段顶端的偏移（把当前滚动位置算回去，得到「不滚时」的位置）
  const offsetTop = Math.round(gr.top - sr.top + scroll.scrollTop);
  const visibleH = Math.round(scroll.clientHeight);
  const belowFoldBy = offsetTop - visibleH;      // >0 = 要滚这么多才露头
  const wholeBlockBottom = Math.round((cr ? cr.bottom : gr.bottom) - sr.top + scroll.scrollTop);

  const R = [];
  const rel = (id, desc, pass, got) => R.push({ id, desc, pass, got });
  rel('F1', '开关块顶边不需要滚就能看见: offsetTop < 中段可视高',
      offsetTop < visibleH, `offsetTop=${offsetTop} visibleH=${visibleH} 差=${belowFoldBy}`);
  rel('F2', '整块（含坐标那行）完整可见: wholeBlockBottom <= 中段可视高',
      wholeBlockBottom <= visibleH, `blockBottom=${wholeBlockBottom} visibleH=${visibleH}`);

  return { vw: innerWidth, vh: innerHeight,
           moveCounter: (document.querySelector('[data-testid="board-rail-module"]')?.innerText || '').replace(/\s+/g,' ').slice(0,80),
           scrollNeedsScrolling: scroll.scrollHeight > scroll.clientHeight + 1,
           scrollH: scroll.scrollHeight, visibleH, offsetTop, belowFoldBy, wholeBlockBottom,
           relations: R, failed: R.filter(r=>!r.pass).map(r=>r.id) };
})()
