import { useCallback, useLayoutEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import { createPortal } from 'react-dom';
import Modal from '@mui/material/Modal';
import CloseIcon from '@mui/icons-material/Close';

import {
  badnessRank,
  brillianceRank,
  buildHistogram,
  buildMatchRate,
  buildMatchTimeline,
  gradedMoves,
  isBad,
  isBrilliant,
  selectPerSide,
  BRILLIANCE_MAX,
  GRADE_BY_ID,
  GRADE_PHASES,
  type GradeId,
  type PhaseId,
  type PlayerFilter,
} from '../../../features/analysis/moveGrade';
import { AnalysisHelpContent, ChartTabHelp } from '../../../components/live/AnalysisChartHelp';
import { useChartSize } from '../../../hooks/useChartSize';
import { placeChartLabels } from '../../../components/live/chartLabelPositions';
import type { MoveAnalysis } from '../../../types/live';
import { useTranslation } from '../../../hooks/useTranslation';
import { interpolate } from '../../utils/interpolate';
import { Icon } from '../../shell/icons';
import './reportWorkspace.css';

/** Kiosk presentation of the shared grading calculations. Filters stay beside
 * the plot; definitions and sample limits live in the active tab's help. */

type TabId = 'recommend' | 'trend' | 'brilliant' | 'mistake' | 'perf' | 'match';
type MatchView = 'stats' | 'dist';

/** 黑白两色取自 galaxy 的 `chartMarks.tsx`,四个前端同一组值。 */
const STONE_BLACK = '#0d0d0d';
const STONE_BLACK_RIM = 'rgba(255,255,255,0.80)';
const STONE_WHITE = '#f2efea';
const STONE_WHITE_RIM = 'rgba(0,0,0,0.35)';

/** 棒棒糖图的画布。尺寸取实测渲染像素,缩放比恒为 1 —— 否则 `preserveAspectRatio="xMidYMid meet"`
 *  下 x/y 缩放不等,`<circle>` 会画成椭圆(560×79 摊到 384×85 是 0.686 : 1.076)。 */

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
 * svg 里的网格线用同一个分数画,而 svg 是 `preserveAspectRatio="xMidYMid meet"`
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
  const [plotRef, { width, height }] = useChartSize(320, 300);
  const mid = height / 2;
  const arm = mid - 24;
  const span = Math.max(1, totalMoves);
  const xOf = (move: number) => 16 + (width - 32) * (move / span);
  const plotted = points.map(p => ({ ...p, x: xOf(p.move), y: mid + (p.black ? -1 : 1) * arm * Math.min(1, p.value / top), label: String(p.move) }));
  const labels = placeChartLabels(plotted, { left: 0, right: width, top: 0, bottom: height });

  return (
    <div className="lolli">
      <div className="laxis">
        <span className="lside" style={{ top: '25%' }}>{blackLabel}</span>
        <span className="lside" style={{ top: '75%' }}>{whiteLabel}</span>
        {ticks.map((t) => {
          const f = (arm / height * 100 * t) / top;
          return [
            <u key={`u${t}`} style={{ top: `${50 - f}%` }}>{t}</u>,
            <u key={`d${t}`} style={{ top: `${50 + f}%` }}>{t}</u>,
          ];
        })}
      </div>
      <div className="lplot is-pickable">
        <div ref={plotRef} className="lplot-canvas">
          <svg
            viewBox={`0 0 ${width} ${height}`}
            preserveAspectRatio="xMidYMid meet"
            role="img"
            aria-label={label}
            data-testid="grade-lollipop"
          >
            {ticks.map((t) => {
              const d = arm * (t / top);
              return [
                <line key={`gu${t}`} className="lgrid" x1="0" y1={mid - d} x2={width} y2={mid - d} />,
                <line key={`gd${t}`} className="lgrid" x1="0" y1={mid + d} x2={width} y2={mid + d} />,
              ];
            })}
            <line className="lax" x1="0" y1={mid} x2={width} y2={mid} />
            {plotted.map((p, index) => {
              const { x, y } = p;
              const on = selected === p.move;
              return (
                <g key={`${p.move}-${p.black ? 'b' : 'w'}`} onClick={() => onPick(p)} style={{ cursor: 'pointer' }}>
                  {/* 命中区比点大一圈 —— 7 寸触摸屏上 5px 的圆点按不准。 */}
                  <rect x={x - 11} y={0} width={22} height={height} fill="transparent" />
                  <line className={on ? 'lstem on' : 'lstem'} x1={x} y1={mid} x2={x} y2={y} stroke={p.color} />
                  {on && <circle className="lhalo" cx={x} cy={y} r={8.5} stroke={p.color} />}
                  {labels[index] && <text x={labels[index]!.x} y={labels[index]!.y} fontSize={12} textAnchor="middle" fill="currentColor">{p.move}</text>}
                  <circle cx={x} cy={y} r={5} fill={stoneFill(p.black)} stroke={stoneRim(p.black)} strokeWidth={1.5} />
                </g>
              );
            })}
          </svg>
        </div>
        <span className="lscale">
          <span>1</span><span>{Math.round(span / 4)}</span><span>{Math.round(span / 2)}</span>
          <span>{Math.round((span * 3) / 4)}</span><span>{span}</span>
        </span>
      </div>
    </div>
  );
}

export default function MoveGradePanel({
  analysis, totalMoves, onMoveClick, trend, recommendation,
}: {
  analysis: Record<number, MoveAnalysis>;
  /** 整局手数 —— 棒棒糖图的横轴量程。**不能拿画出来的最后一个点顶替**,见 `Lollipop`。 */
  totalMoves: number;
  onMoveClick: (move: number) => void;
  /** 走势那一 tab 的内容 —— 曲线的接线长在页面上,见文件头①。 */
  trend: ReactNode;
  /** Current-position candidates supplied by the report rail. */
  recommendation?: ReactNode;
}) {
  const { t } = useTranslation();
  const hasRecommendation = recommendation !== undefined;
  const [selectedTab, setTab] = useState<TabId>(hasRecommendation ? 'recommend' : 'trend');
  const tab = selectedTab === 'recommend' && !hasRecommendation ? 'trend' : selectedTab;
  const [expanded, setExpanded] = useState(false);
  const hostRef = useRef<HTMLDivElement>(null);
  const mainMountRef = useRef<HTMLDivElement>(null);
  const dialogMountRef = useRef<HTMLDivElement>(null);
  // The portal target never changes. Moving its DOM host preserves supplied
  // children, measurements and selection without a second hidden workspace.
  const [workspace] = useState(() => {
    const node = document.createElement('div');
    node.className = 'report-workspace report-workspace__content';
    return node;
  });
  const attachDialog = useCallback((node: HTMLDivElement | null) => {
    dialogMountRef.current = node;
    // MUI may attach its portal after our layout effect (including StrictMode).
    if (expanded && node) node.appendChild(workspace);
  }, [expanded, workspace]);
  useLayoutEffect(() => {
    const mount = expanded ? dialogMountRef.current : mainMountRef.current;
    mount?.appendChild(workspace);
    return () => workspace.remove();
  }, [expanded, workspace]);
  const [player, setPlayer] = useState<PlayerFilter>('both');
  const [phase, setPhase] = useState<PhaseId>('all');
  const [matchView, setMatchView] = useState<MatchView>('stats');
  /** 图上选中的那一手。切 tab / 换阶段之后它可能已经不在图上了,渲染时按图里有没有判。 */
  const [picked, setPicked] = useState<number | null>(null);

  const graded = useMemo(() => gradedMoves(analysis), [analysis]);
  const brilliants = useMemo(
    () => selectPerSide(graded.filter(isBrilliant), brillianceRank, { phase, player }),
    [graded, phase, player],
  );
  const bads = useMemo(
    () => selectPerSide(graded.filter(isBad), badnessRank, { phase, player }),
    [graded, phase, player],
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
    ...(hasRecommendation ? [{ id: 'recommend' as const, label: t('live:recommend_tab', '推荐') }] : []),
    { id: 'trend', label: t('live:trend_chart', '走势') },
    { id: 'brilliant', label: t('live:brilliant', '妙手') },
    { id: 'mistake', label: t('live:mistakes', '失误') },
    { id: 'perf', label: t('grade:performance', '发挥水准') },
    { id: 'match', label: t('grade:match_rate', 'AI吻合度') },
  ];
  const PHASE_OPTIONS: { id: PhaseId; label: string }[] = ([
    'all', ...GRADE_PHASES.map((p) => p.id),
  ] as PhaseId[]).map((p) => ({
    id: p,
    label: t(`grade:phase_${p}`, { all: '全盘', opening: '布局', midgame: '中盘', endgame: '官子' }[p]),
  }));

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
      {(tab === 'brilliant' || tab === 'mistake') && <div className="kiosk-optseg gseg gsub" role="group" aria-label={t('grade:filter_player', '棋手')}>
        {(['both', 'B', 'W'] as const).map(side => <button type="button" key={side} aria-pressed={player === side} onClick={() => { setPlayer(side); setPicked(null); }}>{t(`grade:player_${side}`, { both: '双方', B: '黑方', W: '白方' }[side])}</button>)}
      </div>}
      {right}
    </div>
  );

  const selLine = (pts: Pt[], _sel: { total: number; truncated: number }, detail: (p: Pt) => string) => {
    const hit = pts.find(p => p.move === picked);
    return hit ? <p className="selline on" data-testid="grade-selline" data-state="picked">{detail(hit)}</p> : null;
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

          <p className="gempty">{t('live:no_brilliant', '暂无妙手')}</p>
        </>
      );
    }
    const pts = toPoints(brilliants.shown, (a) => a.brilliance ?? 1, () => GRADE_BY_ID.brilliant.color);
    return (
      <>

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
          t('grade:sel_brilliant', '第 {n} 手 {m} · {s} · 妙度 {k} —— AI初选概率仅为 {p}%，深入计算后成为首选'),
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
    if (bads.shown.length === 0) {
      return <p className="gempty">{t('live:no_mistakes', '暂无失误')}</p>;
    }
    const pts = toPoints(
      bads.shown,
      (a) => badnessRank(a),
      (a) => GRADE_BY_ID[(a.grade as GradeId) ?? 'unrated']?.color ?? '#888',
    );
    const top = niceTop(Math.max(...pts.map((p) => p.value)));
    return (
      <>

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
      return <p className="gempty">{t('grade:no_rated_moves', '本阶段没有已评级的着手')}</p>;
    }
    const maxRate = Math.max(...histogram.cells.map((c) => Math.max(c.blackRate, c.whiteRate)), 0.01);
    // The top tick must match the normalization used for bar heights.
    const guide = maxRate;
    return (
      <>
        <div className="grade-chart-legend"><span><Stone black />{t('review:black', '黑')}</span><span><Stone black={false} />{t('review:white', '白')}</span></div>
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
                      {/* `.hbt` 是柱子百分比高度的**参照物**。不能把 `<b>` 直接挂在
                          `.hb` 下：那一层的高度是内容撑出来的，百分比会解析成 auto ⇒ 恒 0。
                          详见 `go-screens.css` 里 `.hbt` 头上那段。 */}
                      <span className="hbt">
                        <b
                          style={{
                            // 有值就至少 2px —— 0.5% 画出来是 0.3px,等于「有」和「没有」长得一样。
                            height: `${b.v > 0 ? Math.max(2, (b.rate / maxRate) * 100) : 0}%`,
                            background: b.black ? STONE_BLACK : STONE_WHITE,
                            boxShadow: `inset 0 0 0 1.4px ${b.black ? STONE_BLACK_RIM : STONE_WHITE_RIM}`,
                          }}
                        ><u>{b.v}</u></b>
                      </span>
                    </span>
                  ))}
                </span>
                <em>{t(cell.tier.i18nKey, cell.tier.zh)}</em>
                <small>{Math.round(cell.blackRate * 100)}%<br />{Math.round(cell.whiteRate * 100)}%</small>
                <i style={{ background: cell.tier.color }} />
              </div>
            ))}
          </div>
        </div>
      </>
    );
  };

  const viewSeg = (
      <div className="kiosk-optseg gseg gsub gview" role="group" aria-label={t('grade:filter_match_view', '视图')}>
        {([['stats', t('grade:view_stats', '统计')], ['dist', t('grade:view_distribution', '分布')]] as const).map(([v, zh]) => (
          <button key={v} type="button" aria-pressed={matchView === v} onClick={() => setMatchView(v as MatchView)}>
            {zh}
          </button>
        ))}
      </div>
    );

  const renderMatch = () => {
    if (matchRate.blackDecided + matchRate.whiteDecided === 0) {
      return <p className="gempty">{t('grade:match_no_data', '本阶段还没有可比对的着手')}</p>;
    }
    return (
      <>

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
          </>
        )}
      </>
    );
  };

  const content = (
    <div className="gradebody report-workspace__panel" data-tab={tab} data-testid="grade-panel"
      onKeyDown={event => {
        // Portal events follow the React tree rather than the modal's DOM host.
        if (expanded && event.key === 'Escape') {
          event.stopPropagation();
          setExpanded(false);
        }
      }}>
      <div className="report-workspace__tabs" role="group" aria-label={t('grade:tabs', '着手评价')}>
        {TABS.map(x => <div className="grade-tab" key={x.id} data-tab-id={x.id} data-active={tab === x.id}>
          <button type="button" aria-pressed={tab === x.id} onClick={() => { setTab(x.id); setPicked(null); }}>{x.label}</button>
          {tab === x.id && <ChartTabHelp key={x.id} label={x.label}>
            {x.id === 'recommend' ? <p>{t('report:recommend_help', '推荐度是 AI 对候选着点的选择倾向，不是人类落子的概率。目差和胜率以待落子方为基准；正目差表示该方领先。点按候选可预览变化，实战着点不在前五时追加显示；缺少评估以 — 表示。')}</p>
              : <AnalysisHelpContent tab={x.id} selection={tab === 'brilliant' ? brilliants : bads} histogram={histogram} matchRate={matchRate} />}
          </ChartTabHelp>}
        </div>)}
        <button type="button" className="report-workspace__expand" aria-expanded={expanded}
          aria-label={expanded ? t('report:collapse_workspace', '收起分析工作区') : t('report:expand_workspace', '放大当前分析图表或推荐列表')}
          onClick={() => setExpanded(value => !value)}>
          {expanded ? <CloseIcon /> : <Icon name="corners-out" />}
        </button>
      </div>
      <div className="grade-workspace" data-filters={tab !== 'trend' && tab !== 'recommend'}>
        {tab !== 'trend' && tab !== 'recommend' && filterBar(tab === 'match' ? viewSeg : null)}
        <div className="grade-chart-main">
          {tab === 'recommend' && recommendation}
          {tab === 'trend' && trend}
          {tab === 'brilliant' && renderBrilliant()}
          {tab === 'mistake' && renderMistake()}
          {tab === 'perf' && renderPerf()}
          {tab === 'match' && renderMatch()}
        </div>
      </div>
    </div>
  );

  return (
    <div ref={hostRef} className="report-workspace report-workspace__host">
      <div ref={mainMountRef} className="report-workspace__mount" />
      <Modal open={expanded} onClose={() => setExpanded(false)} keepMounted disableScrollLock
        container={() => hostRef.current?.closest<HTMLElement>('.report-analysis-rail') ?? hostRef.current!}
        className="report-chart-dialog">
        <div ref={attachDialog} className="report-chart-dialog__mount" role="dialog" aria-modal="true"
          aria-label={TABS.find(item => item.id === tab)?.label} tabIndex={-1} />
      </Modal>
      {createPortal(content, workspace)}
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
