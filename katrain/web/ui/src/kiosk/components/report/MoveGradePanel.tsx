import { useMemo, useState, type ReactNode } from 'react';

import {
  badnessRank,
  brillianceRank,
  buildHistogram,
  buildMatchRate,
  buildMatchTimeline,
  gradedMoves,
  isBad,
  isBrilliant,
  longestTop1Run,
  selectPerSide,
  BRILLIANCE_MAX,
  GRADE_BY_ID,
  GRADE_PHASES,
  PER_SIDE_LIMIT,
  type GradeId,
  type PhaseId,
} from '../../../features/analysis/moveGrade';
import type { MoveAnalysis } from '../../../types/live';
import { useTranslation } from '../../../hooks/useTranslation';
import { interpolate } from '../../utils/interpolate';

/**
 * 屏 20 ·「着手评价」折叠块 —— galaxy `TrendChart` 那五个 tab 搬上盒子。
 *
 * **名字、顺序、功能与 galaxy 全等**,只改摆放和画法(Fan 2026-09-01:
 * 「我们可以改展示位置和展示方式,但尽量要让用户一眼就能识别对应上」)。
 * 五个 tab:走势 / 妙手 / 失误 / 发挥水准 / AI吻合度;阶段筛选照留;
 * AI吻合度 的「统计 / 分布」也和 galaxy 一样并在同一行右端。
 *
 * ## 三条和 galaxy 不同的,理由都是 460×516
 *
 * ① **走势那一 tab 的内容由调用方给**(`trend` 槽)。曲线、游标、点击跳手的接线本来就
 *    长在页面上(`ReviewWinratePlot` 那一套),搬进来只会让同一份状态跨两层传。
 * ② **没有棋手筛选(双方/黑方/白方)。** 不是省事:`chartMarks.tsx` 那条铁律
 *    「颜色给黑白,档位给位置」在这儿一样管用 —— 棒棒糖黑在轴上白在轴下、直方图黑柱白柱
 *    并排、吻合度上黑下白两条带,**黑白已经在图里分开了**,再放一个筛选器是拿 34px
 *    换屏上已有的信息。7 寸触摸屏没有 hover,能不点就不点。
 * ③ **AI吻合度·统计收成一类一行**(galaxy 是三组各两条,45/组 × 3 = 135,而体只有 212)。
 *    绝对手数挪到下面那句分母里说,**一个数都没丢**。
 *
 * ## 数据一行都不重算
 *
 * `gradedMoves` / `selectPerSide` / `buildHistogram` / `buildMatchRate` /
 * `buildMatchTimeline` 全部来自共享的 `features/analysis/moveGrade.ts`,和 galaxy 同一份。
 * 判级本身在服务端做(阈值真源 `katrain/core/move_grade.yaml`),这里只查表、筛选、画。
 * **七个档位色一律从 `GRADE_BY_ID[id].color` 取,不写进 CSS** —— 写了就会和 yaml 漂。
 */

type TabId = 'trend' | 'brilliant' | 'mistake' | 'perf' | 'match';
type MatchView = 'stats' | 'dist';

/** 黑白两色取自 galaxy 的 `chartMarks.tsx`,四个前端同一组值。 */
const STONE_BLACK = '#0d0d0d';
const STONE_BLACK_RIM = 'rgba(255,255,255,0.80)';
const STONE_WHITE = '#f2efea';
const STONE_WHITE_RIM = 'rgba(0,0,0,0.35)';

/** 棒棒糖图的画布。尺寸取实测渲染像素,缩放比恒为 1 —— 否则 `preserveAspectRatio="none"`
 *  下 x/y 缩放不等,`<circle>` 会画成椭圆(560×79 摊到 384×85 是 0.686 : 1.076)。 */
const LOLLI_W = 384;
const LOLLI_H = 85;

function stoneFill(black: boolean) { return black ? STONE_BLACK : STONE_WHITE; }
function stoneRim(black: boolean) { return black ? STONE_BLACK_RIM : STONE_WHITE_RIM; }

/**
 * 目损那根轴的量程。**取 3 的倍数**,好让三档刻度落在整数上(11.2 → 12 ⇒ 12/8/4)。
 * 妙度不走这里:它的量程按规范固定 1–5,不随本局最大值动。
 */
function niceTop(max: number): number {
  return Math.max(3, Math.ceil(max / 3) * 3);
}

type Pt = { move: number; value: number; black: boolean; color: string; a: MoveAnalysis };

/**
 * 棒棒糖图。黑在轴上、白在轴下 —— 与 galaxy `renderLollipop` 同构。
 *
 * 纵轴刻度**按真分数绝对定位**(`top: X%`),不用 space-between 均分:
 * 妙度 5/3/1 落在整幅的 0/20/40%,均分会摆到 0/16.7/33.3%,**那样刻度本身在说谎**。
 * svg 里的网格线用同一个分数画,而 svg 是 `preserveAspectRatio="none"`
 * ⇒ 横线的 y 分数在任何缩放下不变,两边对得死。
 */
function Lollipop({
  points, top, ticks, selected, onPick, blackLabel, whiteLabel, label, totalMoves,
}: {
  points: Pt[];
  top: number;
  /**
   * 横轴的量程 —— **整局手数,不是「画出来的最后一个点」**。
   * 拿最后一个点当量程的话,妙手那张图到第 140 手就到头、失误那张到第 152 手到头,
   * 两张图上同一个 x 位置指着不同的手数,而刻度上写的数还都「对」。
   */
  totalMoves: number;
  ticks: number[];
  selected: number | null;
  onPick: (p: Pt) => void;
  blackLabel: string;
  whiteLabel: string;
  label: string;
}) {
  const mid = LOLLI_H / 2;
  const span = Math.max(1, totalMoves);
  const xOf = (move: number) => 8 + (LOLLI_W - 16) * (move / span);

  return (
    <div className="lolli">
      <div className="laxis">
        <span className="lside" style={{ top: '25%' }}>{blackLabel}</span>
        <span className="lside" style={{ top: '75%' }}>{whiteLabel}</span>
        {ticks.map((t) => {
          const f = (50 * t) / top;
          return [
            <u key={`u${t}`} style={{ top: `${50 - f}%` }}>{t}</u>,
            <u key={`d${t}`} style={{ top: `${50 + f}%` }}>{t}</u>,
          ];
        })}
      </div>
      <div className="lplot is-pickable">
        <svg
          viewBox={`0 0 ${LOLLI_W} ${LOLLI_H}`}
          preserveAspectRatio="none"
          role="img"
          aria-label={label}
          data-testid="grade-lollipop"
        >
          {ticks.map((t) => {
            const d = mid * (t / top);
            return [
              <line key={`gu${t}`} className="lgrid" x1="0" y1={mid - d} x2={LOLLI_W} y2={mid - d} />,
              <line key={`gd${t}`} className="lgrid" x1="0" y1={mid + d} x2={LOLLI_W} y2={mid + d} />,
            ];
          })}
          <line className="lax" x1="0" y1={mid} x2={LOLLI_W} y2={mid} />
          {points.map((p) => {
            const x = xOf(p.move);
            const h = mid * Math.min(1, p.value / top);
            const y = p.black ? mid - h : mid + h;
            const on = selected === p.move;
            return (
              <g key={`${p.move}-${p.black ? 'b' : 'w'}`} onClick={() => onPick(p)} style={{ cursor: 'pointer' }}>
                {/* 命中区比点大一圈 —— 7 寸触摸屏上 5px 的圆点按不准。 */}
                <rect x={x - 11} y={0} width={22} height={LOLLI_H} fill="transparent" />
                <line className={on ? 'lstem on' : 'lstem'} x1={x} y1={mid} x2={x} y2={y} stroke={p.color} />
                {on && <circle className="lhalo" cx={x} cy={y} r={8.5} stroke={p.color} />}
                <circle cx={x} cy={y} r={5} fill={stoneFill(p.black)} stroke={stoneRim(p.black)} strokeWidth={1.5} />
              </g>
            );
          })}
        </svg>
        <span className="lscale">
          <span>1</span><span>{Math.round(span / 4)}</span><span>{Math.round(span / 2)}</span>
          <span>{Math.round((span * 3) / 4)}</span><span>{span}</span>
        </span>
      </div>
    </div>
  );
}

export default function MoveGradePanel({
  analysis, totalMoves, onMoveClick, trend,
}: {
  analysis: Record<number, MoveAnalysis>;
  /** 整局手数 —— 棒棒糖图的横轴量程。**不能拿画出来的最后一个点顶替**,见 `Lollipop`。 */
  totalMoves: number;
  onMoveClick: (move: number) => void;
  /** 走势那一 tab 的内容 —— 曲线的接线长在页面上,见文件头①。 */
  trend: ReactNode;
}) {
  const { t } = useTranslation();
  const [tab, setTab] = useState<TabId>('trend');
  const [phase, setPhase] = useState<PhaseId>('all');
  const [matchView, setMatchView] = useState<MatchView>('stats');
  /** 图上选中的那一手。切 tab / 换阶段之后它可能已经不在图上了,渲染时按图里有没有判。 */
  const [picked, setPicked] = useState<number | null>(null);

  const graded = useMemo(() => gradedMoves(analysis), [analysis]);
  const brilliants = useMemo(
    () => selectPerSide(graded.filter(isBrilliant), brillianceRank, { phase, player: 'both' }),
    [graded, phase],
  );
  const bads = useMemo(
    () => selectPerSide(graded.filter(isBad), badnessRank, { phase, player: 'both' }),
    [graded, phase],
  );
  const histogram = useMemo(() => buildHistogram(graded, phase), [graded, phase]);
  const matchRate = useMemo(() => buildMatchRate(graded, phase), [graded, phase]);
  const timeline = useMemo(() => buildMatchTimeline(graded, phase), [graded, phase]);

  const sideLabel = (a: MoveAnalysis) => (
    a.player === 'B' ? t('review:black', '黑') : t('review:white', '白')
  );
  const tierLabel = (a: MoveAnalysis) => {
    const tier = GRADE_BY_ID[(a.grade as GradeId) ?? 'unrated'];
    return tier ? t(tier.i18nKey, tier.zh) : t('grade:unrated', '未评级');
  };

  const TABS: { id: TabId; label: string }[] = [
    { id: 'trend', label: t('live:trend_chart', '走势') },
    { id: 'brilliant', label: t('live:brilliant', '妙手') },
    { id: 'mistake', label: t('live:mistakes', '失误') },
    { id: 'perf', label: t('grade:performance', '发挥水准') },
    { id: 'match', label: t('grade:match_rate', 'AI吻合度') },
  ];
  const PHASE_OPTIONS: { id: PhaseId; label: string }[] = ([
    'all', ...GRADE_PHASES.map((p) => p.id),
  ] as PhaseId[]).map((p) => ({ id: p, label: t(`grade:phase_${p}`, p) }));

  /** 筛选行。**走势 tab 不用它** —— 那张图画的是整局曲线,截一段等于把上下文砍掉
   *  (galaxy 同一条,Fan 2026-09-01 定的)。 */
  const filterBar = (right: ReactNode) => (
    <div className="gfilters">
      <div className="kiosk-optseg gseg gsub" role="group" aria-label={t('grade:filter_phase', '阶段')}>
        {PHASE_OPTIONS.map((p) => (
          <button
            key={p.id}
            type="button"
            aria-pressed={phase === p.id}
            onClick={() => { setPhase(p.id); setPicked(null); }}
          >
            {p.label}
          </button>
        ))}
      </div>
      {right}
    </div>
  );

  /**
   * 计数与截断。**截断了必须说** —— 每方最多画 5 条,不说清楚用户会以为整局就这么些问题。
   *
   * 截断那句用的是**自铸的** `grade:truncated_plot`,不是 galaxy 的 `grade:truncated_note`:
   * 后者在 cn PO 里是「另有 {n} 处未列出，可切换阶段或棋手查看」—— 占位符少一个 `{k}`
   * (闸三会红),而且**「切换棋手」在盒上是假话**,这一屏按设计没有棋手筛选。
   * 同一个 msgid 兼管两件事、逼调用方撒谎,仓里既有的修法就是铸新 key(见闸四那段说明)。
   */
  const countNote = (sel: { total: number; truncated: number }) => (
    interpolate(t('grade:count_note', '本阶段共 {n} 处'), { n: sel.total })
    + (sel.truncated > 0
      ? ` · ${interpolate(t('grade:truncated_plot', '图上每方最多画 {k} 条，另有 {n} 处未画出'), { k: PER_SIDE_LIMIT, n: sel.truncated })}`
      : '')
  );

  /**
   * 图下那一行是**两态**的:没选中说计数与截断,选中说这一手。
   * 一行两态是有意的 —— 7 寸屏多一行就要从图上扣 20px,而这两句不会同时想看。
   */
  const selLine = (pts: Pt[], sel: { total: number; truncated: number }, detail: (p: Pt) => string) => {
    const hit = pts.find((p) => p.move === picked) ?? null;
    return hit
      ? <p className="selline on" data-testid="grade-selline" data-state="picked">{detail(hit)}</p>
      : (
        <p className="selline" data-testid="grade-selline" data-state="hint">
          {`${countNote(sel)} —— ${t('grade:pick_hint', '点图上任一手看详情')}`}
        </p>
      );
  };

  const toPoints = (rows: MoveAnalysis[], value: (a: MoveAnalysis) => number, color: (a: MoveAnalysis) => string): Pt[] => (
    rows.map((a) => ({
      move: a.move_number, value: value(a), black: a.player === 'B', color: color(a), a,
    }))
  );

  const renderBrilliant = () => {
    if (brilliants.shown.length === 0) {
      return (
        <>
          {filterBar(<span className="gunit">{t('grade:axis_brilliance', '妙度 1–5')}</span>)}
          <p className="gempty">{t('live:no_brilliant', '暂无妙手')}</p>
        </>
      );
    }
    const pts = toPoints(brilliants.shown, (a) => a.brilliance ?? 1, () => GRADE_BY_ID.brilliant.color);
    return (
      <>
        {filterBar(<span className="gunit">{t('grade:axis_brilliance', '妙度 1–5')}</span>)}
        <Lollipop
          points={pts}
          top={BRILLIANCE_MAX}
          ticks={[5, 3, 1]}
          selected={picked}
          totalMoves={totalMoves}
          onPick={(p) => { setPicked(p.move); onMoveClick(p.move); }}
          blackLabel={t('review:black', '黑')}
          whiteLabel={t('review:white', '白')}
          label={`${t('grade:axis_brilliance', '妙度 1–5')}${t('grade:axis_aria', '，黑方在轴上方、白方在下方，横轴是手数')}`}
        />
        {selLine(pts, brilliants, (p) => interpolate(
          t('grade:sel_brilliant', '第 {n} 手 {m} · {s} · 妙度 {k} —— 走的就是引擎首选，而引擎自己只给了 {p}% 先验（越低越妙）'),
          {
            n: p.move,
            m: p.a.move ?? '',
            s: sideLabel(p.a),
            k: p.a.brilliance ?? 1,
            p: ((p.a.top_prior ?? 0) * 100).toFixed(1),
          },
        ))}
      </>
    );
  };

  const renderMistake = () => {
    const unit = <span className="gunit">{t('grade:axis_points_lost_short', '目损 · 目')}</span>;
    if (bads.shown.length === 0) {
      return (<>{filterBar(unit)}<p className="gempty">{t('live:no_mistakes', '暂无失误')}</p></>);
    }
    const pts = toPoints(
      bads.shown,
      (a) => badnessRank(a),
      (a) => GRADE_BY_ID[(a.grade as GradeId) ?? 'unrated']?.color ?? '#888',
    );
    const top = niceTop(Math.max(...pts.map((p) => p.value)));
    return (
      <>
        {filterBar(unit)}
        <Lollipop
          points={pts}
          top={top}
          ticks={[top, (top * 2) / 3, top / 3]}
          selected={picked}
          totalMoves={totalMoves}
          onPick={(p) => { setPicked(p.move); onMoveClick(p.move); }}
          blackLabel={t('review:black', '黑')}
          whiteLabel={t('review:white', '白')}
          label={`${t('grade:axis_points_lost_short', '目损 · 目')}${t('grade:axis_aria', '，黑方在轴上方、白方在下方，横轴是手数')}`}
        />
        {selLine(pts, bads, (p) => interpolate(
          t('grade:sel_bad', '第 {n} 手 {m} · {s} · {g} · 目损 {x} 目'),
          { n: p.move, m: p.a.move ?? '', s: sideLabel(p.a), g: tierLabel(p.a), x: p.value.toFixed(1) },
        ))}
      </>
    );
  };

  const renderPerf = () => {
    if (histogram.blackTotal + histogram.whiteTotal === 0) {
      return (<>{filterBar(null)}<p className="gempty">{t('grade:no_rated_moves', '本阶段没有已评级的着手')}</p></>);
    }
    const maxRate = Math.max(...histogram.cells.map((c) => Math.max(c.blackRate, c.whiteRate)), 0.01);
    // 参考线取 20%(与 galaxy 的 0/20/40/60 同一族,460 宽只画得下一条)。
    const guide = maxRate >= 0.2 ? 0.2 : Math.round(maxRate * 100) / 100;
    return (
      <>
        {filterBar(null)}
        <div className="hist">
          <div className="hyaxis">
            <i>{`${Math.round(guide * 100)}%`}</i>
            <i>0</i>
          </div>
          <div className="hcols" data-testid="grade-histogram">
            {histogram.cells.map((cell) => (
              <div className="hg" key={cell.tier.id}>
                <span className="hbars">
                  {([
                    { v: cell.black, rate: cell.blackRate, black: true },
                    { v: cell.white, rate: cell.whiteRate, black: false },
                  ] as const).map((b) => (
                    <span className="hb" key={b.black ? 'b' : 'w'}>
                      <u>{b.v}</u>
                      <b
                        style={{
                          // 有值就至少 2px —— 0.5% 画出来是 0.3px,等于「有」和「没有」长得一样。
                          height: `${b.v > 0 ? Math.max(2, (b.rate / maxRate) * 100) : 0}%`,
                          background: b.black ? STONE_BLACK : STONE_WHITE,
                          boxShadow: `inset 0 0 0 1.4px ${b.black ? STONE_BLACK_RIM : STONE_WHITE_RIM}`,
                        }}
                      />
                    </span>
                  ))}
                </span>
                <em>{t(cell.tier.i18nKey, cell.tier.zh)}</em>
                <i style={{ background: cell.tier.color }} />
              </div>
            ))}
          </div>
        </div>
        <p className="gnote">
          {interpolate(t('grade:histogram_footer', '黑 {b} 手 / 白 {w} 手已评级'), {
            b: histogram.blackTotal, w: histogram.whiteTotal,
          })}
          {histogram.unrated > 0
            ? ` · ${interpolate(t('grade:histogram_unrated', '{n} 手未评级'), { n: histogram.unrated })}`
            : ''}
        </p>
      </>
    );
  };

  const renderMatch = () => {
    const viewSeg = (
      <div className="kiosk-optseg gseg gsub gview" role="group" aria-label={t('grade:filter_match_view', '视图')}>
        {([['stats', t('grade:view_stats', '统计')], ['dist', t('grade:view_distribution', '分布')]] as const).map(([v, zh]) => (
          <button key={v} type="button" aria-pressed={matchView === v} onClick={() => setMatchView(v as MatchView)}>
            {zh}
          </button>
        ))}
      </div>
    );
    if (matchRate.blackDecided + matchRate.whiteDecided === 0) {
      return (<>{filterBar(viewSeg)}<p className="gempty">{t('grade:match_no_data', '本阶段还没有可比对的着手')}</p></>);
    }
    const runB = longestTop1Run(timeline, 'B');
    const runW = longestTop1Run(timeline, 'W');
    const run = (runW?.length ?? 0) >= (runB?.length ?? 0) ? runW : runB;
    const runSide = run === runW ? t('review:white', '白') : t('review:black', '黑');
    return (
      <>
        {filterBar(viewSeg)}
        {matchView === 'stats' ? (
          <div className="mtab" data-testid="grade-match-stats">
            {matchRate.rows.map((row) => (
              <div className="mr" key={row.id}>
                <span className="ml">{t(row.i18nKey, row.zh)}</span>
                {([
                  { black: true, rate: row.blackRate },
                  { black: false, rate: row.whiteRate },
                ] as const).map((b) => (
                  <span className="mu" key={b.black ? 'b' : 'w'}>
                    <Stone black={b.black} />
                    <i><b style={{ width: `${Math.round(b.rate * 100)}%`, background: row.color }} /></i>
                    <u>{`${Math.round(b.rate * 100)}%`}</u>
                  </span>
                ))}
              </div>
            ))}
          </div>
        ) : (
          <>
            <div className="mband" data-testid="grade-match-dist">
              {(['B', 'W'] as const).map((side) => (
                <div className="kiosk-ribbon" key={side}>
                  <span className="kiosk-ribbon__lead">
                    {side === 'B' ? t('review:black', '黑') : t('review:white', '白')}
                  </span>
                  <div className="kiosk-ribbon__track mtrack">
                    {timeline.filter((e) => e.player === side).map((e) => (
                      <i key={e.move_number} data-m={e.band} />
                    ))}
                  </div>
                </div>
              ))}
              <div className="kiosk-ribbon__scale">
                <span>1</span>
                <span>{t('grade:axis_move_number', '手数')}</span>
                <span>{timeline.length > 0 ? timeline[timeline.length - 1].move_number : 0}</span>
              </div>
            </div>
            <p className="mlegend">
              <i data-m="top1" />{t('grade:match_top1', '走中 AI 一选')}
              <i data-m="top3" />{t('grade:match_top3', '走进 AI 前三')}
              <i data-m="off" />{t('grade:match_other', '其他')}
              {run && run.length > 1 && (
                <em>
                  {interpolate(t('grade:match_longest_run', '{side} 第{from}–{to}手连续{n}手中一选'), {
                    side: runSide, from: run.from, to: run.to, n: run.length,
                  })}
                </em>
              )}
            </p>
          </>
        )}
        <p className="gnote">
          {interpolate(t('grade:match_footer', '分母是能与 AI 比对的手数：黑 {b} 手 / 白 {w} 手'), {
            b: matchRate.blackDecided, w: matchRate.whiteDecided,
          })}
          {matchRate.undecidable > 0
            ? ` · ${interpolate(t('grade:match_undecidable', '{n} 手无法比对'), { n: matchRate.undecidable })}`
            : ''}
        </p>
        {/* 这句是**硬性**的,不许在任何视图里省掉(galaxy 同一条注)。一致率高低本来就取决于
            局面难度(官子段谁都容易和 AI 一致)。我们手上判作弊的证据一份都没有,
            界面上不能暗示我们有。 */}
        <p className="gwarn">
          {t('grade:match_caveat', '一致率高低取决于局面难度，不能单独当作棋力或作弊的证据。')}
        </p>
      </>
    );
  };

  return (
    <div className="gradebody" data-tab={tab} data-testid="grade-panel">
      <div className="kiosk-optseg gseg gseg5" role="group" aria-label={t('grade:tabs', '着手评价')}>
        {TABS.map((x) => (
          <button
            key={x.id}
            type="button"
            aria-pressed={tab === x.id}
            onClick={() => { setTab(x.id); setPicked(null); }}
          >
            {x.label}
          </button>
        ))}
      </div>
      {tab === 'trend' && trend}
      {tab === 'brilliant' && renderBrilliant()}
      {tab === 'mistake' && renderMistake()}
      {tab === 'perf' && renderPerf()}
      {tab === 'match' && renderMatch()}
    </div>
  );
}

/** 正文里的一颗棋子。用 SVG 而不是带边框的 div:边框盒在不同字号下会被四舍五入成椭圆。 */
function Stone({ black }: { black: boolean }) {
  return (
    <svg className="sm" viewBox="0 0 12 12" aria-hidden="true">
      <circle cx="6" cy="6" r="4.6" fill={stoneFill(black)} stroke={stoneRim(black)} strokeWidth="1.2" />
    </svg>
  );
}
