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

/** 目差那条曲线的一个点。`scoreLead` 是**黑方**领先的目数(与 winrate 同一个参照系)。 */
export interface LeadPoint { moveNumber: number; scoreLead: number }

/**
 * 目差纵轴的量程。**必须对称**(±top):右轴那三格是 space-between,中间那格就在盒子正中,
 * 量程不对称的话「0」这个字会指到不是 0 的高度上。而正中同时是胜率 50% 那条虚线 ⇒
 * 两条曲线的「均势」重合,这不是巧合,是对的。
 */
function leadTop(points: readonly LeadPoint[]): number {
  const max = Math.max(1, ...points.map((p) => Math.abs(p.scoreLead)));
  return Math.max(6, Math.ceil(max / 3) * 3);
}

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

export function ReviewWinratePlot({
  points, empty, axisTop, axisMid, axisBottom, label, cursor, onPick, lead,
}: {
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
  /** 停在第几手 —— 画一条竖线。`undefined` = 不画(复盘列表那一屏没有游标)。 */
  cursor?: number;
  /**
   * 第二条曲线:逐手目差。**给了才画** —— 屏 19 复盘列表那张缩略图只要胜率一条。
   * galaxy 的走势 tab(`renderDualChart`)画的就是这两条,盒上跟着画同样两条。
   */
  lead?: readonly LeadPoint[];
  /**
   * 点曲线跳到那一手。**不是锦上添花**:187 手的谱靠四个翻手键一手一手挪走不到第 120 手,
   * 而稿子把滑块拿掉了 —— 这条是那个滑块的替代品(`TrendChart` 原来就有)。
   */
  onPick?: (moveNumber: number) => void;
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

  // 目差那条:x 用和胜率同一条(按手数),y 用自己的对称量程。
  const leadPts = lead && lead.length >= 2 ? lead : null;
  const leadMax = leadPts ? leadTop(leadPts) : 0;
  const leadPath = leadPts
    ? leadPts
      .map((p) => `${((p.moveNumber / lastMove) * W).toFixed(1)},${(((leadMax - p.scoreLead) / (2 * leadMax)) * H).toFixed(1)}`)
      .join(' ')
    : null;

  const drop = worstDropIndex(points);
  const last = points[points.length - 1];
  const cursorPoint = cursor == null
    ? null
    : points.reduce((best, p) => (
      Math.abs(p.moveNumber - cursor) < Math.abs(best.moveNumber - cursor) ? p : best
    ), points[0]);

  // 横坐标是**手数**不是数组下标(断掉的手不补点),所以反查也按手数来。
  const pickAt = (clientX: number, el: HTMLElement) => {
    if (!onPick) return;
    const r = el.getBoundingClientRect();
    const ratio = Math.max(0, Math.min(1, (clientX - r.left) / r.width));
    const target = ratio * lastMove;
    const nearest = points.reduce((best, p) => (
      Math.abs(p.moveNumber - target) < Math.abs(best.moveNumber - target) ? p : best
    ), points[0]);
    onPick(nearest.moveNumber);
  };

  return (
    <div className="wrbox">
      {axis}
      <div
        className={onPick ? 'wrplot is-pickable' : 'wrplot'}
        data-testid="review-winrate-plot"
        data-state="plotted"
        data-points={points.length}
        role={onPick ? 'button' : undefined}
        tabIndex={onPick ? 0 : undefined}
        aria-label={onPick ? label : undefined}
        onClick={onPick ? (e) => pickAt(e.clientX, e.currentTarget) : undefined}
        onKeyDown={onPick ? (e) => {
          if (e.key !== 'ArrowLeft' && e.key !== 'ArrowRight') return;
          e.preventDefault();
          const i = cursorPoint ? points.indexOf(cursorPoint) : 0;
          const next = e.key === 'ArrowLeft' ? Math.max(0, i - 1) : Math.min(points.length - 1, i + 1);
          onPick(points[next].moveNumber);
        } : undefined}
      >
        <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" role="img" aria-label={label}>
          <line className="mid" x1="0" y1={H / 2} x2={W} y2={H / 2} />
          {cursorPoint && (
            <line className="cursor" data-testid="review-winrate-cursor"
              x1={x(cursorPoint)} y1="0" x2={x(cursorPoint)} y2={H} />
          )}
          {drop == null ? (
            <polyline className="curve" points={path(0, points.length - 1)} />
          ) : (
            <>
              <polyline className="curve" points={path(0, drop - 1)} />
              <polyline className="curve drop" data-testid="review-winrate-drop" points={path(drop - 1, drop)} />
              <polyline className="curve" points={path(drop, points.length - 1)} />
            </>
          )}
          {leadPath && <polyline className="lead" data-testid="review-lead-curve" points={leadPath} />}
        </svg>
        {/* 当前手那颗点**不画在 svg 里**。svg 是 `preserveAspectRatio="none"`(曲线要拉满盒子),
            而 `<circle>` 会跟着一起被拉 —— 560×96 的画布铺进 436×153 的盒子,圆就成了竖椭圆。
            2026-09-02 之前它已经是横向压扁的(436/560),`.evalpad` 让盒子长高之后更明显。
            改成按百分比定位的 DOM 圆点:x / y 仍旧由同一对 `x()` / `y()` 算,只是换成比例,
            **在任何盒子尺寸下都是正圆**。(棒棒糖图那次踩的是同一个坑,那边的修法是对齐 viewBox;
            这里对不齐 —— 曲线本来就要被拉。) */}
        <span
          className="wrnow"
          data-testid="review-winrate-now"
          style={{ left: `${((x(last) / W) * 100).toFixed(2)}%`, top: `${((y(last) / H) * 100).toFixed(2)}%` }}
        />
      </div>
      {leadPts && (
        <div className="wrlead" data-testid="review-lead-axis">
          <i>{`+${leadMax}`}</i><i>0</i><i>{`\u2212${leadMax}`}</i>
        </div>
      )}
    </div>
  );
}
