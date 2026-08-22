import { MISTAKE_SCORE_LOSS, type WinratePoint } from '../../../features/report/reportStats';

/**
 * 屏 19 复盘 ·「这一局的胜率」那条曲线。**四种棋里只有围棋这条是真的** ——
 * 报告离线跑完,逐手 winrate 已经落在 `report_task_moves` 里。
 *
 * ## 三条不许违反的
 *
 * ① **上黑下白。** cron 那条分析线固定 `reportAnalysisWinratesAs: "BLACK"`
 *    (`katrain/cron/clients/katago.py:83`),`winrate` 恒为黑方胜率,1.0 画在顶上 ——
 *    和 galaxy 的 `ScoreGraph`、和对局屏那条同向。**同一局在两屏之间上下颠倒**
 *    是五子棋 2026-08-02 踩过的坑。
 * ② **纵坐标不能省。** 没有刻度带的话,50↔53 和 20↔80 长得一模一样。
 * ③ **没算过的时候不画线。** 一条贴着中线的平线 = 把「没算过」伪装成「算过了,是均势」。
 *    空态由调用方给一句话,这里只负责 `is-empty` 那个壳。
 *
 * 断点不插值:`winrateSeries` 已经把算失败的手剔掉了,横坐标按**手数**摆,
 * 所以「只算到第 40 手」的报告画出来就是短的一截,不会假装整局都算过。
 */

const W = 560;
const H = 96;

/** 掉得最狠的那一手 —— 红的那一段就是它。返回的是**后一个点**在数组里的下标。 */
function worstDropIndex(points: readonly WinratePoint[]): number | null {
  let worst: number | null = null;
  let worstSwing = 0;
  for (let i = 1; i < points.length; i += 1) {
    const p = points[i];
    // 判据借的是仓里已有的失误线,不另立一个「掉多少算掉」——
    // 屏上标红的那一手和三格里数进「失误」的那些手必须是同一批。
    if (p.deltaScore == null || p.deltaScore > MISTAKE_SCORE_LOSS) continue;
    if (p.player == null) continue;
    // 走子方的损失换算成胜率:黑走坏 → 黑胜率跌;白走坏 → 黑胜率涨。
    const swing = p.player === 'B'
      ? points[i - 1].winrate - p.winrate
      : p.winrate - points[i - 1].winrate;
    if (swing > worstSwing) {
      worstSwing = swing;
      worst = i;
    }
  }
  return worst;
}

export function ReviewWinratePlot({ points, empty, axisTop, axisMid, axisBottom, label }: {
  points: readonly WinratePoint[];
  /**
   * 空态那句话。**传了就画它、不画线**;点不够两个时也画它 ——
   * 所以调用方必须一直备着一句能解释「为什么这儿是空的」的话,不能给空字符串。
   */
  empty: string;
  axisTop: string;
  axisMid: string;
  axisBottom: string;
  label: string;
}) {
  const axis = (
    <div className="wraxis">
      <i>{axisTop}</i><i>{axisMid}</i><i>{axisBottom}</i>
    </div>
  );

  if (empty !== '' || points.length < 2) {
    return (
      <div className="wrbox">
        {axis}
        <div className="wrplot is-empty" data-testid="review-winrate-plot" data-state="empty">
          <span>{empty}</span>
        </div>
      </div>
    );
  }

  const lastMove = points[points.length - 1].moveNumber || 1;
  const x = (p: WinratePoint) => (p.moveNumber / lastMove) * W;
  const y = (p: WinratePoint) => (1 - p.winrate) * H;
  const path = (from: number, to: number) =>
    points.slice(from, to + 1).map((p) => `${x(p).toFixed(1)},${y(p).toFixed(1)}`).join(' ');

  const drop = worstDropIndex(points);
  const last = points[points.length - 1];

  return (
    <div className="wrbox">
      {axis}
      <div className="wrplot" data-testid="review-winrate-plot" data-state="plotted" data-points={points.length}>
        <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" role="img" aria-label={label}>
          <line className="mid" x1="0" y1={H / 2} x2={W} y2={H / 2} />
          {drop == null ? (
            <polyline className="curve" points={path(0, points.length - 1)} />
          ) : (
            <>
              <polyline className="curve" points={path(0, drop - 1)} />
              <polyline className="curve drop" data-testid="review-winrate-drop" points={path(drop - 1, drop)} />
              <polyline className="curve" points={path(drop, points.length - 1)} />
            </>
          )}
          <circle className="now" cx={x(last)} cy={y(last)} r="5" />
        </svg>
      </div>
    </div>
  );
}
