import { Box, Stack, Tab, Tabs, Typography, useTheme } from '@mui/material';
import { useEffect, useMemo, useRef, useState } from 'react';

import { useMeasuredWidth } from '../../hooks/useMeasuredWidth';
import { TIER_DEF_TEXT, BRILLIANCE_BANDS, BRILLIANCE_HELP_TEXT } from './chartDefinitions';
import Segmented from './Segmented';
import { placeChartLabels } from './chartLabelPositions';
import { AnalysisHelpContent, ChartTabHelp, type AnalysisTab } from './AnalysisChartHelp';
import { StoneCircle, StoneDot, stoneFill, stoneRim } from './chartMarks';
import type { MoveAnalysis } from '../../types/live';
import { useTranslation } from '../../hooks/useTranslation';
import {
  badnessRank,
  brillianceRank,
  buildHistogram,
  buildMatchRate,
  buildMatchTimeline,
  gradedMoves,
  BRILLIANCE_MAX,
  longestTop1Run,
  PER_SIDE_LIMIT,
  GRADE_BY_ID,
  GRADE_PHASES,
  GRADE_TIERS,
  isBad,
  isBrilliant,
  selectPerSide,
  type GradeId,
  type PhaseId,
  type PlayerFilter,
} from '../../features/analysis/moveGrade';

interface TrendChartProps {
  analysis: Record<number, MoveAnalysis>;
  totalMoves: number;
  currentMove: number;
  onMoveClick?: (move: number) => void;
  reportMode?: boolean;
}

export default function TrendChart({
  analysis,
  totalMoves,
  currentMove,
  onMoveClick,
  reportMode = false,
}: TrendChartProps) {
  const { t } = useTranslation();
  const theme = useTheme();
  const [tab, setTab] = useState(0);
  const workspaceRef = useRef<HTMLDivElement>(null);
  const [workspaceHeight, setWorkspaceHeight] = useState(180);

  useEffect(() => {
    const plot = workspaceRef.current;
    if (!reportMode || !plot) return;
    const observer = new ResizeObserver(([entry]) => {
      if (entry) setWorkspaceHeight(Math.max(80, Math.floor(entry.contentRect.height)));
    });
    observer.observe(plot);
    return () => observer.disconnect();
  }, [reportMode, tab]);

  // 两张图各要一份实测宽度。**不能共用一个**：它们分属不同 tab，同一时刻只有一个挂载，
  // 共用的话 callback ref 会在切 tab 时被后挂载的那个覆盖，先挂的那张再也收不到尺寸变化。
  const [dualRef, dualWidth] = useMeasuredWidth();
  const [lolliRef, lolliWidth] = useMeasuredWidth();

  // Extract data for chart
  const chartData = useMemo(() => {
    const moves: number[] = [];
    const winrates: number[] = [];
    const scores: number[] = [];

    for (let i = 0; i <= totalMoves; i++) {
      const moveAnalysis = analysis[i];
      if (moveAnalysis) {
        moves.push(i);
        winrates.push(moveAnalysis.winrate * 100);
        scores.push(moveAnalysis.score_lead);
      }
    }

    return { moves, winrates, scores };
  }, [analysis, totalMoves]);

  // Calculate score range for Y-axis
  const scoreRange = useMemo(() => {
    const scores = chartData.scores.filter(s => s !== 0);
    if (scores.length === 0) return { min: -30, max: 30 };
    const maxAbs = Math.max(Math.abs(Math.min(...scores)), Math.abs(Math.max(...scores)));
    const range = Math.ceil(maxAbs / 10) * 10 || 30;
    return { min: -range, max: range };
  }, [chartData.scores]);

  // Get current values for display above chart
  const currentWinrate = useMemo(() => {
    const moveAnalysis = analysis[currentMove];
    return moveAnalysis ? moveAnalysis.winrate * 100 : null;
  }, [analysis, currentMove]);

  const currentScoreLead = useMemo(() => {
    const moveAnalysis = analysis[currentMove];
    return moveAnalysis ? moveAnalysis.score_lead : null;
  }, [analysis, currentMove]);

  // Dual-axis chart with winrate and score lead
  const renderDualChart = () => {
    if (chartData.winrates.length === 0) return null;

    // viewBox 宽 == 容器实测 CSS 宽 ⇒ 缩放比恒为 1：绘图区随右栏伸缩，字号不跟着缩。
    // 改造前这里写死 420，320 档下整张图被缩到 0.79（轴标 11px 只剩 8.7px）。
    const width = dualWidth;
    const height = reportMode ? Math.max(80, workspaceHeight - 34) : 180;
    const leftPadding = 56;
    const rightPadding = 56;
    const topPadding = 16;
    const bottomPadding = reportMode ? 34 : 12;
    const chartWidth = width - leftPadding - rightPadding;
    const chartHeight = height - topPadding - bottomPadding;

    const xStep = chartWidth / Math.max(1, totalMoves);

    // Winrate points (0-100 -> chart coordinates)
    const winratePoints = chartData.winrates.map((value, i) => {
      const x = leftPadding + chartData.moves[i] * xStep;
      const y = topPadding + chartHeight - (value / 100) * chartHeight;
      return `${i === 0 || chartData.moves[i] !== chartData.moves[i - 1] + 1 ? 'M' : 'L'}${x},${y}`;
    }).join(' ');

    // Score points (scoreRange.min to scoreRange.max -> chart coordinates)
    const scorePoints = chartData.scores.map((value, i) => {
      const x = leftPadding + chartData.moves[i] * xStep;
      const normalized = (value - scoreRange.min) / (scoreRange.max - scoreRange.min);
      const y = topPadding + chartHeight - normalized * chartHeight;
      return `${i === 0 || chartData.moves[i] !== chartData.moves[i - 1] + 1 ? 'M' : 'L'}${x},${y}`;
    }).join(' ');

    // Current move indicator
    const currentX = leftPadding + currentMove * xStep;

    // Y-axis labels
    const winrateLabels = ['0%', '50%', '100%'];
    const scoreLabels = [`${scoreRange.min}`, '0', `+${scoreRange.max}`];

    return (
      <svg ref={dualRef} data-testid="trend-dual-chart" width="100%" height={height} viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="xMidYMid meet">
        {/* Grid lines and left Y-axis labels (winrate) */}
        {winrateLabels.map((label, i) => {
          const y = topPadding + chartHeight - (i / 2) * chartHeight;
          return (
            <g key={`wr-${i}`}>
              <line
                x1={leftPadding}
                y1={y}
                x2={width - rightPadding}
                y2={y}
                stroke="rgba(255,255,255,0.1)"
                strokeDasharray={i === 1 ? "4" : "0"}
              />
              <text
                x={leftPadding - 6}
                y={y}
                textAnchor="end"
                dominantBaseline="middle"
                fill="rgba(76, 175, 80, 0.8)"
                fontSize="13"
              >
                {label}
              </text>
            </g>
          );
        })}

        {/* Right Y-axis labels (score) */}
        {scoreLabels.map((label, i) => {
          const y = topPadding + chartHeight - (i / 2) * chartHeight;
          return (
            <text
              key={`sc-${i}`}
              x={width - rightPadding + 6}
              y={y}
              textAnchor="start"
              dominantBaseline="middle"
              fill="rgba(255, 152, 0, 0.8)"
              fontSize="13"
            >
              {label}
            </text>
          );
        })}

        {/* Score line (orange) */}
        <path
          fill="none"
          stroke="#ff9800"
          strokeWidth="1.5"
          strokeOpacity="0.8"
          d={scorePoints}
        />

        {/* Winrate line (green) */}
        <path
          fill="none"
          stroke="#4caf50"
          strokeWidth="2"
          d={winratePoints}
        />

        {/* Current move indicator */}
        <line
          x1={currentX}
          y1={topPadding}
          x2={currentX}
          y2={height - bottomPadding}
          stroke="rgba(255,255,255,0.5)"
          strokeWidth="1"
        />

        {reportMode && <g fill={theme.palette.text.secondary} fontSize={12}>
          {[0, 0.25, 0.5, 0.75, 1].map(fraction => <text key={fraction}
            x={leftPadding + chartWidth * fraction} y={height - 18} textAnchor="middle">
            {Math.round(totalMoves * fraction)}
          </text>)}
          <text x={leftPadding + chartWidth / 2} y={height - 3} textAnchor="middle">{t('grade:axis_move_number', '手数')}</text>
        </g>}

        {/* Click area */}
        <rect
          x={leftPadding}
          y={0}
          width={chartWidth}
          height={height}
          fill="transparent"
          style={{ cursor: 'pointer' }}
          onClick={(e) => {
            if (!onMoveClick) return;
            const rect = e.currentTarget.getBoundingClientRect();
            const x = e.clientX - rect.left;
            const ratio = x / rect.width;
            const move = Math.round(ratio * totalMoves);
            onMoveClick(Math.max(0, Math.min(totalMoves, move)));
          }}
        />
      </svg>
    );
  };

  const [phase, setPhase] = useState<PhaseId>('all');
  const [player, setPlayer] = useState<PlayerFilter>('both');

  // 摊平 + 缺 grade 时退回旧布尔量,现在住在 `features/analysis/moveGrade.ts`
  // —— kiosk 屏 20 用的是同一份,退回规则不许两处各写各的。
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

  /** AI吻合度的两个视图。统计是既有的三行比率，分布是按手数排的吻合带。 */
  type MatchView = 'stats' | 'dist';
  const [matchView, setMatchView] = useState<MatchView>('stats');

  const PHASE_OPTIONS = (['all', ...GRADE_PHASES.map((p) => p.id)] as PhaseId[]).map((p) => ({
    value: p,
    label: t(`grade:phase_${p}`, p),
  }));
  const MATCH_VIEW_OPTIONS: { value: 'stats' | 'dist'; label: string }[] = [
    { value: 'stats', label: t('grade:view_stats', '统计') },
    { value: 'dist', label: t('grade:view_distribution', '分布') },
  ];
  const PLAYER_OPTIONS: { value: PlayerFilter; label: string }[] = [
    { value: 'both', label: t('grade:player_both', '双方') },
    { value: 'B', label: t('grade:player_B', '黑方') },
    { value: 'W', label: t('grade:player_W', '白方') },
  ];

  /** 筛选条。**走势 tab 不用它** —— 那张图画的是整局曲线，截一段等于把上下文砍掉
   *  （Fan 2026-09-01：「对于走势图，不需要切换这些，去掉吧」）。 */
  const filterBar = (withPlayer: boolean) => (
    <Stack direction={reportMode ? "column" : "row"} sx={{ mb: reportMode ? 0 : 1.5, flexWrap: 'wrap', gap: 1 }}>
      <Segmented
        vertical={reportMode}
        options={PHASE_OPTIONS}
        value={phase}
        onChange={setPhase}
        ariaLabel={t('grade:filter_phase', '阶段')}
      />
      {withPlayer && (
        <Segmented
          vertical={reportMode}
        options={PLAYER_OPTIONS}
          value={player}
          onChange={setPlayer}
          ariaLabel={t('grade:filter_player', '棋手')}
        />
      )}
    </Stack>
  );

  /**
   * 图下的数量说明。
   *
   * tab 标签上原来带着 `(5 / 50)` 这样的计数，2026-09-01 按 Fan 的要求去掉了
   * （计数随筛选变 ⇒ 标签宽度跟着变 ⇒ 整条 tab 抖动）。**但计数本身不能跟着消失**：
   * 每方最多只画 5 条（`PER_SIDE_LIMIT`），不说清楚的话用户会以为整局就这么些问题。
   * 所以数量挪到这里，而且**截断了必须说**。
   */
  const countNote = (sel: { shown: unknown[]; total: number; truncated: number }) => (
    <Typography variant="caption" color="text.secondary" sx={{ display: 'block', pt: 1, lineHeight: 1.7 }}>
      {t('grade:count_note', '本阶段共 {n} 处').replace('{n}', String(sel.total))}
      {sel.truncated > 0 && (
        <>
          {' · '}
          {t('grade:truncated_note', '图上每方最多画 {k} 条，另有 {n} 处未画出')
            .replace('{k}', String(PER_SIDE_LIMIT))
            .replace('{n}', String(sel.truncated))}
        </>
      )}
    </Typography>
  );

  /** 妙度分档说明。断点是 `move_grade.yaml` 的 `brilliant.levels_prior`
   *  [0.05, 0.03, 0.02, 0.01, 0.0]，级数 = 1 + 越过的断点数。
   *  官子段的 `phase_prior_scale` 0.6 **只缩放入选门槛**（官子要先验 <6% 才够格），
   *  不缩放这张分档表 —— 分档用绝对先验。这一点 yaml 注释里没写，只有
   *  `move_grade_core._brilliant` 的实现里看得出。 */
  const brillianceDefs = (
    <Box sx={{ pt: 1 }}>
      <Typography variant="caption" color="text.secondary" sx={{ display: 'block', lineHeight: 1.7, mb: 0.75 }}>
        {BRILLIANCE_HELP_TEXT(t).entry}
      </Typography>
      <Typography variant="caption" color="text.secondary" sx={{ display: 'block', lineHeight: 1.7, mb: 0.75 }}>
        {BRILLIANCE_HELP_TEXT(t).probability}
      </Typography>
      <Box
        sx={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))',
          columnGap: 2,
          rowGap: 0.5,
        }}
      >
        {BRILLIANCE_BANDS.map(({ level, band }) => (
          <Box key={level} sx={{ display: 'flex', alignItems: 'flex-end', gap: 0.75, minWidth: 0 }}>
            <Box component="span" sx={{ display: 'inline-flex', alignItems: 'flex-end', gap: '2px', flexShrink: 0 }}>
              {[0, 1, 2, 3, 4].map((i) => (
                <Box
                  key={i}
                  component="span"
                  sx={{
                    width: '3px',
                    height: `${4 + i * 2.5}px`,
                    borderRadius: '1px',
                    bgcolor: i < level ? GRADE_BY_ID.brilliant.color : 'rgba(255,255,255,0.13)',
                  }}
                />
              ))}
            </Box>
            <Typography variant="caption" sx={{ flexShrink: 0, color: 'text.primary', lineHeight: 1.2 }}>
              {t('grade:brilliance', '妙度')} {level}
            </Typography>
            <Typography variant="caption" sx={{ color: 'text.disabled', lineHeight: 1.2 }}>
              {band}
            </Typography>
          </Box>
        ))}
      </Box>
    </Box>
  );

  const sideLabel = (a: MoveAnalysis) =>
    a.player === 'B' ? t('live:black', 'B') : t('live:white', 'W');
  const tierLabel = (a: MoveAnalysis) => {
    const tier = GRADE_BY_ID[(a.grade as GradeId) ?? 'unrated'];
    return tier ? t(tier.i18nKey, tier.zh) : t('grade:unrated', '未评级');
  };

  /**
   * 发挥水准：七档 × 黑白的**纵向**分组柱。
   *
   * 2026-09-01 之前是「一档一行横条」，七行要滚到底才看得见「恶手」那一档
   * （Fan：「这块最好画成纵向的柱状图，不需要滑轮滚到下方才看到所有数据」）。
   * 纵向排布一屏放得下七档，而且相邻两档的高度可以直接比 —— 横条做不到。
   *
   * 编码与其它图一致：**柱子的颜色就是黑白两色**，档位由横轴位置（轴上写着档名）
   * 加标签下那条细色线承载。最高的那一组柱顶直接写「黑」「白」两个字，不用查图例。
   *
   * 分母是**各方自己**在所选阶段内被评级的手数，两方各自归一 —— 与星阵口径一致。
   */
  const renderHistogram = () => {
    const width = lolliWidth;
    const height = reportMode ? workspaceHeight : 250;
    const padL = 34;
    const padR = 10;
    const padT = reportMode ? 56 : 40;
    const padB = 62;
    const plot = height - padT - padB;
    const groupW = (width - padL - padR) / histogram.cells.length;
    const maxRate = Math.max(
      ...histogram.cells.map((c) => Math.max(c.blackRate, c.whiteRate)),
      0.01,
    );
    const gridLines = [0, 0.2, 0.4, 0.6].filter((f) => f <= maxRate);

    return (
      <Box sx={{ bgcolor: 'background.default', borderRadius: 1, minWidth: 0, height: reportMode ? '100%' : undefined }}>
        <svg
          ref={lolliRef}
          data-testid="trend-histogram-chart"
          width="100%"
          height={height}
          viewBox={`0 0 ${width} ${height}`}
          preserveAspectRatio="xMidYMid meet"
          role="img"
          aria-label={t('grade:histogram_aria', '七档发挥水准分布，黑柱为黑方、白柱为白方，各自归一')}
        >
          <StoneCircle cx={padL + 5} cy={12} r={5} black />
          <text x={padL + 15} y={16} fontSize={12} fill={theme.palette.text.secondary}>{t('review:black', '黑')}</text>
          <StoneCircle cx={padL + 47} cy={12} r={5} black={false} />
          <text x={padL + 57} y={16} fontSize={12} fill={theme.palette.text.secondary}>{t('review:white', '白')}</text>
          {gridLines.map((f) => {
            const y = padT + plot - (f / maxRate) * plot;
            return (
              <g key={f}>
                <line x1={padL} y1={y} x2={width - padR} y2={y} stroke="rgba(255,255,255,0.06)" />
                <text x={padL - 6} y={y + 3.5} textAnchor="end" fill={theme.palette.text.secondary} fontSize={reportMode ? 12 : 11}>
                  {Math.round(f * 100)}%
                </text>
              </g>
            );
          })}
          {histogram.cells.map((cell, i) => {
            const x0 = padL + i * groupW;
            const barW = Math.min(17, (groupW - 10) / 2);
            return (
              <g key={cell.tier.id}>
                {([
                  { v: cell.black, rate: cell.blackRate, black: true },
                  { v: cell.white, rate: cell.whiteRate, black: false },
                ] as const).map((b, j) => {
                  const h = Math.max(b.v > 0 ? 2 : 0, (b.rate / maxRate) * plot);
                  const x = x0 + groupW / 2 - barW - 1 + j * (barW + 2);
                  const y = padT + plot - h;
                  return (
                    <g key={j}>
                      <title>
                        {`${t(cell.tier.i18nKey, cell.tier.zh)} · ${b.black ? t('live:black', 'B') : t('live:white', 'W')} ${b.v} (${Math.round(b.rate * 100)}%)`}
                      </title>
                      <rect
                        x={x}
                        y={y}
                        width={barW}
                        height={h}
                        rx={2.5}
                        fill={stoneFill(b.black)}
                        stroke={stoneRim(b.black)}
                        strokeWidth={1.4}
                      />
                      {b.v > 0 && (
                        <text x={x + barW / 2} y={y - (b.black ? 5 : 19)} textAnchor="middle" fill={theme.palette.text.secondary} fontSize={reportMode ? 12 : 11}>
                          {b.v}
                        </text>
                      )}

                    </g>
                  );
                })}
                <text
                  x={x0 + groupW / 2}
                  y={height - padB + 15}
                  textAnchor="middle"
                  fill={theme.palette.text.secondary}
                  fontSize={reportMode ? 12 : 11}
                >
                  {t(cell.tier.i18nKey, cell.tier.zh)}
                </text>
                {/* 档位色退到标签下的一条细线：绿→红的好坏梯度还在，但不与黑白抢通道。 */}
                <line
                  x1={x0 + groupW / 2 - 15}
                  y1={height - padB + 22}
                  x2={x0 + groupW / 2 + 15}
                  y2={height - padB + 22}
                  stroke={cell.tier.color}
                  strokeWidth="2.5"
                  strokeLinecap="round"
                />
                <text
                  x={x0 + groupW / 2}
                  y={height - padB + 36}
                  textAnchor="middle"
                  fill={theme.palette.text.secondary}
                  fontSize={reportMode ? 12 : 11}
                >
                  <tspan x={x0 + groupW / 2}>{Math.round(cell.blackRate * 100)}%</tspan>
                  <tspan x={x0 + groupW / 2} dy={14}>{Math.round(cell.whiteRate * 100)}%</tspan>
                </text>
              </g>
            );
          })}
          <line x1={padL} y1={padT + plot} x2={width - padR} y2={padT + plot} stroke="rgba(255,255,255,0.28)" />
        </svg>
      </Box>
    );
  };

  /** 七档的量化定义。阈值取自生成产物 `GRADE_LADDER_POINTS`（真源 move_grade.yaml），
   *  **不在这里另写一份数** —— 真源一改这里跟着变，不会悄悄过期。
   *  Fan 2026-09-01：「这些标签的定义可以剪短写在图表下方，也可以在悬停的时候展示」。
   *  两个都做了：常驻这条一眼能查，柱子的 `<title>` 给悬停时的逐档数字。 */
  const tierDefs = (
    <Box
      sx={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(230px, 1fr))',
        columnGap: 2,
        rowGap: 0.5,
        pt: 1.5,
      }}
    >
      {GRADE_TIERS.map((tier) => (
        <Box key={tier.id} sx={{ display: 'flex', alignItems: 'baseline', gap: 0.875, minWidth: 0 }}>
          <Box
            component="span"
            sx={{
              flexShrink: 0,
              width: 14,
              height: 3,
              borderRadius: '2px',
              bgcolor: tier.color,
              transform: 'translateY(-3px)',
            }}
          />
          <Typography variant="caption" sx={{ flexShrink: 0, color: 'text.primary' }}>
            {t(tier.i18nKey, tier.zh)}
          </Typography>
          <Typography variant="caption" sx={{ color: 'text.disabled', lineHeight: 1.5 }}>
            {TIER_DEF_TEXT(t)[tier.id]}
          </Typography>
        </Box>
      ))}
    </Box>
  );

  /** 统计视图：三行比率，每行黑白各一条。行前的棋子标记就是「这条是谁的」。 */
  const renderMatchStats = () => (
    <Box sx={reportMode ? { height: '100%', display: 'grid', gridTemplateRows: 'repeat(3, minmax(0,1fr))', gap: '6px' } : undefined}>
      {matchRate.rows.map((row) => (
        <Box key={row.id} sx={{ mb: reportMode ? 0 : 1.75, ...(reportMode ? { minHeight: 0, display: 'flex', flexDirection: 'column', justifyContent: 'space-evenly' } : {}) }}>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', gap: 1, mb: reportMode ? 0 : 0.75 }}>
            <Typography variant="body2" sx={{ color: 'text.primary', ...(reportMode ? { fontSize: 14, lineHeight: '20px' } : {}) }}>
              {t(row.i18nKey, row.zh)}
            </Typography>
            <Typography
              variant="caption"
              color="text.secondary"
              sx={{ fontVariantNumeric: 'tabular-nums', whiteSpace: 'nowrap', display: reportMode ? 'none' : undefined }}
            >
              <StoneDot black /> {row.black}/{row.blackTotal} ({Math.round(row.blackRate * 100)}%)
              <Box component="span" sx={{ display: 'inline-block', width: 12 }} />
              <StoneDot black={false} /> {row.white}/{row.whiteTotal} ({Math.round(row.whiteRate * 100)}%)
            </Typography>
          </Box>
          {([
            { rate: row.blackRate, black: true },
            { rate: row.whiteRate, black: false },
          ] as const).map((b, i) => (
            <Box key={i} sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: reportMode ? 0 : 0.5, ...(reportMode ? { height: 20, flexShrink: 0 } : {}) }}>
              <StoneDot black={b.black} />
              <Box sx={{ flex: 1, height: 9, bgcolor: 'action.hover', borderRadius: '5px', overflow: 'hidden', minWidth: 0 }}>
                <Box
                  sx={{
                    width: `${Math.max(0, Math.min(1, b.rate)) * 100}%`,
                    height: '100%',
                    borderRadius: '5px',
                    bgcolor: row.color,
                    opacity: b.black ? 1 : 0.62,
                  }}
                />
              </Box>
              <Typography
                variant="caption"
                color="text.secondary"
                sx={{ width: 36, textAlign: 'right', fontVariantNumeric: 'tabular-nums', ...(reportMode ? { fontSize: 13, lineHeight: '18px' } : {}) }}
              >
                {Math.round(b.rate * 100)}%
              </Typography>
            </Box>
          ))}
        </Box>
      ))}
    </Box>
  );

  /**
   * 分布视图：按手数排列的吻合带 —— Fan 2026-09-01 点名要的那张图。
   *
   * 「按照手数顺序排列双方命中 top1/top3 的手数，这样可以轻松看出来，双方在哪一段
   * 出现了连续和 AI 吻合的情况，比如从第 105 手到棋局最后一手，全部命中 AI top1 选择，
   * 那就暗示这段时间有作弊嫌疑。」
   *
   * 每一手一格，黑白各一条泳道：满格实色 = 走中一选，半高浅色 = 进前三，底色 = 其他。
   * **连续吻合会自己长成一整块实色**，不用数数字。最长的那一段直接框出来并写清楚。
   *
   * `unknown`（判不了）画成底色，与 `off` 同色 —— 但它**不进统计的分母**，
   * 所以带子上数出来的格数与统计里的分子对不上是正常的；两者的分母在脚注里都写了。
   */
  const renderMatchTimeline = () => {
    const width = lolliWidth;
    const height = reportMode ? workspaceHeight : 148;
    const padL = 34;
    const padR = 14;
    const padT = 26;
    const lane = reportMode ? Math.max(28, (height - 88) / 2) : 28;
    const gap = 14;
    const span = width - padL - padR;
    const first = timeline.length ? timeline[0].move_number : 0;
    const last = timeline.length ? timeline[timeline.length - 1].move_number : totalMoves;
    const range = Math.max(1, last - first);
    const cellW = Math.max((span / range) * 2, 2.4);
    const xOf = (n: number) => padL + ((n - first) / range) * span;
    const runs = { B: longestTop1Run(timeline, 'B'), W: longestTop1Run(timeline, 'W') };
    // 只标注更长的那一方，且至少要 5 手才值得框 —— 框一段 2 手的「连续」是噪声。
    const marked =
      (runs.B?.length ?? 0) >= (runs.W?.length ?? 0)
        ? { side: 'B' as const, run: runs.B }
        : { side: 'W' as const, run: runs.W };
    const showMark = (marked.run?.length ?? 0) >= 5;

    return (
      <Box sx={{ bgcolor: 'background.default', borderRadius: 1, minWidth: 0, height: reportMode ? '100%' : undefined }}>
        <svg
          ref={lolliRef}
          data-testid="trend-match-timeline"
          width="100%"
          height={height}
          viewBox={`0 0 ${width} ${height}`}
          preserveAspectRatio="xMidYMid meet"
          role="img"
          aria-label={t(
            'grade:match_timeline_aria',
            '按手数排列的 AI 吻合分布，黑白各一条带，连续吻合段显示为连续实色块',
          )}
        >
          {(['B', 'W'] as const).map((side, si) => {
            const y = padT + si * (lane + gap);
            return (
              <g key={side}>
                <rect x={padL} y={y} width={span} height={lane} rx={3} fill="rgba(255,255,255,0.045)" />
                {timeline
                  .filter((e) => e.player === side)
                  .map((e) =>
                    e.band === 'top1' ? (
                      <rect key={e.move_number} x={xOf(e.move_number)} y={y} width={cellW} height={lane} rx={1} fill={GRADE_BY_ID.best.color} />
                    ) : e.band === 'top3' ? (
                      <rect
                        key={e.move_number}
                        x={xOf(e.move_number)}
                        y={y + lane * 0.44}
                        width={cellW}
                        height={lane * 0.56}
                        rx={1}
                        fill={GRADE_BY_ID.best.color}
                        fillOpacity={0.42}
                      />
                    ) : null,
                  )}
                <StoneCircle cx={15} cy={y + lane / 2} r={7} black={side === 'B'} />
              </g>
            );
          })}
          {showMark && marked.run && (
            <g>
              <rect
                x={xOf(marked.run.from)}
                y={padT + (marked.side === 'B' ? 0 : lane + gap) - 4}
                width={Math.max(cellW, xOf(marked.run.to) - xOf(marked.run.from) + cellW)}
                height={lane + 8}
                rx={4}
                fill="none"
                stroke={theme.palette.warning.main}
                strokeWidth="1.5"
              />
              <text
                x={Math.min(width - padR, Math.max(padL, (xOf(marked.run.from) + xOf(marked.run.to)) / 2))}
                y={12}
                textAnchor="middle"
                fill={theme.palette.warning.main}
                fontSize={reportMode ? 12 : 11}
              >
                {t('grade:match_longest_run', '{side} 第{from}–{to}手连续{n}手中一选')
                  .replace('{side}', marked.side === 'B' ? t('live:black', 'B') : t('live:white', 'W'))
                  .replace('{from}', String(marked.run.from))
                  .replace('{to}', String(marked.run.to))
                  .replace('{n}', String(marked.run.length))}
              </text>
            </g>
          )}
          <text x={padL - 2} y={height - 4} fill="#8b8885" fontSize={reportMode ? 12 : 11}>{first}</text>
          <text x={width - padR} y={height - 4} textAnchor="end" fill="#8b8885" fontSize={reportMode ? 12 : 11}>{last}</text>
          <text
            x={(padL + width - padR) / 2}
            y={height - 4}
            textAnchor="middle"
            fill={theme.palette.text.secondary}
            fontSize={reportMode ? 12 : 11}
          >
            {t('grade:axis_move_number', '手数')}
          </text>
        </svg>
        <Typography variant="caption" color="text.secondary" sx={{ display: reportMode ? 'none' : 'block', pt: 0.75, lineHeight: 1.7 }}>
          {t('grade:match_timeline_legend', '满格实色 = 走中一选，半高浅色 = 进前三，底色 = 其他')}
        </Typography>
      </Box>
    );
  };

  /**
   * 妙手 / 问题手图：**黑方画在时间轴上方，白方在下方**。
   *
   * 为什么用位置编码哪一方，而不是形状：旧版靠「实心=黑、空心=白」区分，Fan 实测后
   * 直接问「我如何一眼就看出哪个是黑棋」—— 5.5px 圆点上的形状差太弱。位置差是
   * 不用图例、不用悬停就能读的，而且与「走势」tab 的黑升白降是同一个方向约定。
   * 端点仍然画成棋子本色（黑近黑带亮边 / 白近白），两个通道说同一件事，互为冗余。
   *
   * 杆的颜色留给**档位**（小亏 / 失误 / 恶手），这是第二根轴，不与黑白抢通道。
   *
   * `fixedMax`：妙度这类**有固定量程**的量必须钉死上限。按本局最大值归一的话，
   * 全局只有妙度 1 时两个点会双双顶到最高、看着像满级（实测 report 16 就是这样）。
   */
  const renderLollipop = (
    items: MoveAnalysis[],
    magnitude: (a: MoveAnalysis) => number,
    colorOf: (a: MoveAnalysis) => string,
    axisLabel: string,
    tipText: (a: MoveAnalysis) => string,
    fixedMax?: number,
  ) => {
    if (items.length === 0) return null;
    const width = lolliWidth;
    // 缩放比现在恒为 1（viewBox 宽 == CSS 宽），所以这个数就是屏上的像素高。
    const height = reportMode ? workspaceHeight : 196;
    const padL = 40;
    const padR = 24;
    const mid = height / 2;
    const arm = mid - 44;
    const span = Math.max(1, totalMoves);
    const maxMag = fixedMax ?? Math.max(3, Math.ceil(Math.max(...items.map((a) => Math.max(0, magnitude(a)))) / 3) * 3);
    const xOf = (n: number) => padL + (Math.max(0, Math.min(span, n)) / span) * (width - padL - padR);
    const points = items.map(a => ({ x: xOf(a.move_number), y: mid + (a.player === 'B' ? -1 : 1) * Math.max(0, magnitude(a)) / maxMag * arm, label: String(a.move_number), black: a.player === 'B' }));
    const labels = placeChartLabels(points, { left: padL, right: width - 4, top: 28, bottom: height - 20 });

    return (
      <Box sx={{ bgcolor: 'background.default', borderRadius: 1, minWidth: 0, height: reportMode ? '100%' : undefined }}>
        <svg
          ref={lolliRef}
          data-testid="trend-lollipop-chart"
          width="100%"
          height={height}
          viewBox={`0 0 ${width} ${height}`}
          preserveAspectRatio="xMidYMid meet"
          role="img"
          aria-label={`${axisLabel}${t('grade:axis_aria', '，黑方在轴上方、白方在下方，横轴是手数')}`}
        >
          {(fixedMax ? [1, 3, 5] : [maxMag / 3, maxMag * 2 / 3, maxMag]).flatMap(value => [-1, 1].map(sign => {
            const y = mid + sign * value / maxMag * arm;
            return <g key={`${value}:${sign}`}><line x1={padL} y1={y} x2={width - padR} y2={y} stroke="rgba(255,255,255,0.08)" />
              <text x={padL - 6} y={y + 4} textAnchor="end" fontSize={12} fill={theme.palette.text.secondary}>{value}</text></g>;
          }))}
          <line x1={padL} y1={mid} x2={width - padR} y2={mid} stroke="rgba(255,255,255,0.30)" />
          {currentMove > 0 && (
            <>
              <line
                x1={xOf(currentMove)}
                y1={14}
                x2={xOf(currentMove)}
                y2={height - 14}
                stroke="rgba(255,255,255,0.38)"
                strokeDasharray="3 3"
              />
              <text x={reportMode ? width / 2 : xOf(currentMove)} y={11} textAnchor="middle" fill={theme.palette.text.secondary} fontSize={reportMode ? 12 : 11}>
                {t('live:move_number', 'Move')} {currentMove}
              </text>
            </>
          )}
          <StoneCircle cx={padL + 5} cy={22} r={5} black />
          <text x={padL + 16} y={26} fill={theme.palette.text.secondary} fontSize={12}>{t('review:black', '黑')}</text>
          <StoneCircle cx={padL + 5} cy={height - 24} r={5} black={false} />
          <text x={padL + 16} y={height - 20} fill={theme.palette.text.secondary} fontSize={12}>{t('review:white', '白')}</text>
          <text x={width - padR} y={26} textAnchor="end" fill={theme.palette.text.secondary} fontSize={12}>{axisLabel}</text>
          {items.map((a, index) => {
            const color = colorOf(a);
            const len = (Math.max(0, magnitude(a)) / maxMag) * arm;
            const x = xOf(a.move_number);
            const isBlack = a.player === 'B';
            const tipY = isBlack ? mid - len : mid + len;
            const label = labels[index];
            return (
              <g key={a.move_number} style={{ cursor: onMoveClick ? 'pointer' : 'default' }}>
                <title>{tipText(a)}</title>
                <line x1={x} y1={mid} x2={x} y2={tipY} stroke={color} strokeWidth="2.2" strokeOpacity="0.72" />
                <circle cx={x} cy={tipY} r="5.5" fill={stoneFill(isBlack)} stroke={stoneRim(isBlack)} strokeWidth="1.6" />
                {label && (
                  <text
                    x={label.x}
                    y={label.y}
                    textAnchor="middle"
                    fill={theme.palette.text.secondary}
                    fontSize={reportMode ? 12 : 11}
                  >
                    {a.move_number}
                  </text>
                )}
                <circle cx={x} cy={tipY} r="11" fill="transparent" onClick={() => onMoveClick?.(a.move_number)} />
              </g>
            );
          })}
          {/* 横轴：左端 0、右端**这盘棋的总手数**（Fan 明确要求），中间写单位。 */}
          <text x={padL - 2} y={height - 4} fill="#8b8885" fontSize={reportMode ? 12 : 11}>0</text>
          <text x={width - padR} y={height - 4} textAnchor="end" fill="#8b8885" fontSize={reportMode ? 12 : 11}>
            {totalMoves}
          </text>
          <text
            x={(padL + width - padR) / 2}
            y={height - 4}
            textAnchor="middle"
            fill={theme.palette.text.secondary}
            fontSize={reportMode ? 12 : 11}
          >
            {t('grade:axis_move_number', '手数')}
          </text>
        </svg>
      </Box>
    );
  };

  const reportTabs: { id: AnalysisTab; label: string }[] = [
    { id: 'trend', label: t('live:trend_chart', '走势') },
    { id: 'brilliant', label: t('live:brilliant', '妙手') },
    { id: 'mistake', label: t('live:mistakes', '失误') },
    { id: 'perf', label: t('grade:performance', '发挥水准') },
    { id: 'match', label: t('grade:match_rate', 'AI吻合度') },
  ];
  if (reportMode) return <Box sx={{ height: '100%', minHeight: 0, display: 'flex', flexDirection: 'column' }}>
    <Box className="report-chart-tabs" role="tablist" aria-label={t('grade:tabs', '着手评价')} sx={{ display: 'flex', flexShrink: 0, borderBottom: 1, borderColor: 'divider', height: 44,
      '& .chart-tab-help--inactive': { '@container board-rail (max-width: 560px)': { display: 'none' } } }}>
      {reportTabs.map((item, index) => <Box key={item.id} sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', flex: '1 1 auto', minWidth: 0, borderBottom: tab === index ? '2px solid' : '2px solid transparent', borderColor: tab === index ? 'primary.light' : 'transparent', color: tab === index ? 'primary.light' : 'text.secondary' }}>
        <Box component="button" role="tab" aria-selected={tab === index} onClick={() => setTab(index)} sx={{ border: 0, bgcolor: 'transparent', color: 'inherit', fontFamily: 'inherit', fontSize: 14, px: '2px', minWidth: 44, height: 44, whiteSpace: 'nowrap', flex: '0 1 auto', cursor: 'pointer', '@container board-rail (min-width: 560px)': { fontSize: 16 } }}>{item.label}</Box>
        <ChartTabHelp label={item.label} active={tab === index}><AnalysisHelpContent tab={item.id} selection={item.id === 'brilliant' ? brilliants : bads} histogram={histogram} matchRate={matchRate} /></ChartTabHelp>
      </Box>)}
    </Box>
    <Box sx={{ display: 'grid', gridTemplateColumns: tab === 0 ? 'minmax(0,1fr)' : '64px minmax(0,1fr)', gap: 1, p: 1, flex: 1, minHeight: 0, overflow: 'hidden' }}>
      {tab !== 0 && <Box sx={{ minHeight: 0, overflowY: 'auto' }}>{tab === 4 ? <Stack spacing={1}>
        <Segmented vertical options={PHASE_OPTIONS} value={phase} onChange={setPhase} ariaLabel={t('grade:filter_phase', '阶段')} />
        <Segmented vertical options={MATCH_VIEW_OPTIONS} value={matchView} onChange={setMatchView} ariaLabel={t('grade:filter_match_view', '视图')} />
      </Stack> : filterBar(tab === 1 || tab === 2)}</Box>}
      <Box ref={workspaceRef} data-testid="report-chart-workspace" sx={{ minWidth: 0, minHeight: 0, overflow: 'hidden', '& svg': { display: 'block' } }}>
        {tab === 0 && <><Box sx={{ height: 34, display: 'flex', justifyContent: 'space-between', fontSize: 14, gap: 1 }}>
          <span style={{ color: '#8fdfad' }}>{t('live:black_winrate', '黑方胜率')} {currentWinrate == null ? '—' : `${currentWinrate.toFixed(1)}%`}</span>
          <span style={{ color: '#ffb74d' }}>{t('live:black_lead', '黑方领先')} {currentScoreLead == null ? '—' : `${currentScoreLead >= 0 ? '+' : ''}${currentScoreLead.toFixed(1)}`}</span>
        </Box><Box sx={{ bgcolor: 'background.default', borderRadius: 1 }}>{renderDualChart()}</Box></>}
        {tab === 1 && (brilliants.shown.length ? renderLollipop(brilliants.shown, a => a.brilliance ?? 1, () => GRADE_BY_ID.brilliant.color,
          t('grade:axis_brilliance', '妙度 1–5'), a => `${a.move_number} · ${sideLabel(a)} · ${t('grade:brilliance', '妙度')} ${a.brilliance ?? 1}`, BRILLIANCE_MAX) : <Typography>{t('live:no_brilliant', '暂无妙手')}</Typography>)}
        {tab === 2 && (bads.shown.length ? renderLollipop(bads.shown, badnessRank, a => GRADE_BY_ID[(a.grade as GradeId) ?? 'unrated']?.color ?? '#888',
          t('grade:axis_points_lost_short', '目损 · 目'), a => `${a.move_number} · ${sideLabel(a)} · ${tierLabel(a)} · ${badnessRank(a).toFixed(1)}`) : <Typography>{t('live:no_mistakes', '暂无失误')}</Typography>)}
        {tab === 3 && (histogram.blackTotal + histogram.whiteTotal > 0 ? renderHistogram() : <Typography>{t('grade:no_rated_moves', '本阶段没有已评级的着手')}</Typography>)}
        {tab === 4 && (matchRate.blackDecided + matchRate.whiteDecided > 0 ? matchView === 'stats' ? renderMatchStats() : renderMatchTimeline() : <Typography>{t('grade:match_no_data', '本阶段还没有可比对的着手')}</Typography>)}
      </Box>
    </Box>
  </Box>;

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%', minHeight: 0 }}>
      {/* 五个 tab：**不带括号计数、等宽、左对齐**（Fan 2026-09-01）。
          去掉计数的理由不只是整齐 —— 计数会随阶段/棋手筛选变，标签跟着变宽，
          整条 tab 会在用户点筛选时抖动。数量改到各 tab 自己的说明行里报。

          等宽取 88px：五个 × 88 = 440，620 与 520 两档一行放得下。
          320 / 360 两档放不下（内容宽约 285 / 325），所以 `variant="scrollable"`
          必须留着 —— 那两档的栏宽由棋盘定死，不能为了「看起来齐」把字缩到看不清。
          MUI 默认的 standard variant 会把溢出部分 overflow-x:hidden 切掉且**没有
          滚动按钮**，第 5 个 tab 用户根本够不到（Playwright 能点是因为它会程序化
          scrollIntoView，不算数）。 */}
      <Tabs
        value={tab}
        onChange={(_, v) => setTab(v)}
        variant={reportMode ? 'standard' : 'scrollable'}
        scrollButtons={reportMode ? false : 'auto'}
        allowScrollButtonsMobile
        sx={{
          borderBottom: 1,
          borderColor: 'divider',
          minHeight: 40,
          flexShrink: 0,
          bgcolor: 'background.paper',
          '& .MuiTab-root': {
            minHeight: 40,
            minWidth: reportMode ? 0 : 88,
            ...(reportMode ? { flex: '1 1 auto' } : {}),
            py: 0,
            px: 0.5,
            fontSize: '0.84rem',
            textTransform: 'none',
          },
          '& .MuiTabs-flexContainer': { justifyContent: 'flex-start' },
        }}
      >
        <Tab label={t('live:trend_chart', 'Trend')} />
        <Tab label={t('live:brilliant', 'Brilliant')} />
        <Tab label={t('live:mistakes', 'Mistakes')} />
        <Tab label={t('grade:performance', '发挥水准')} />
        <Tab label={t('grade:match_rate', 'AI吻合度')} />
      </Tabs>

      {/* Scrollable content area */}
      <Box sx={{ px: 1.5, py: 1, flex: 1, minHeight: 0, overflow: 'auto' }}>
        {tab === 0 && (
          <Box sx={reportMode ? { height: '100%', minHeight: 0, display: 'flex', flexDirection: 'column' } : undefined}>
            {/* Values display above chart */}
            <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5, px: 0.5 }}>
              <Typography variant="body2" sx={{ color: '#4caf50', fontWeight: 600 }}>
                {t('live:black_winrate', 'Black Winrate')}: {currentWinrate == null ? '—' : `${currentWinrate.toFixed(1)}%`}
              </Typography>
              <Typography variant="body2" sx={{ color: '#ff9800', fontWeight: 600 }}>
                {t('live:black_lead', 'Black Lead')}: {currentScoreLead == null ? '—' : `${currentScoreLead >= 0 ? '+' : ''}${currentScoreLead.toFixed(1)}`} {t('live:points_unit', 'pts')}
              </Typography>
            </Box>
            <Box ref={workspaceRef} sx={{ bgcolor: 'background.default', borderRadius: 1, p: 0.5, ...(reportMode ? { flex: 1, minHeight: 0 } : {}) }}>
              {renderDualChart()}
            </Box>
          </Box>
        )}

        {tab === 1 && (
          <Box>
            {filterBar(true)}
            {brilliants.shown.length === 0 ? (
              <Typography variant="body2" color="text.secondary" sx={{ textAlign: 'center', py: 2 }}>
                {t('live:no_brilliant', 'No brilliant moves')}
              </Typography>
            ) : (
              <>
                {renderLollipop(
                  brilliants.shown,
                  (a) => a.brilliance ?? 1,
                  () => GRADE_BY_ID.brilliant.color,
                  t('grade:axis_brilliance', '妙度 1–5'),
                  (a) =>
                    `${t('live:move_number', 'Move')} ${a.move_number} ${a.move ?? ''} · ${sideLabel(a)} · ${t('grade:brilliance', '妙度')} ${a.brilliance ?? 1}`,
                  /* 妙度量程固定 1–5，不按本局最大值归一：全局只有妙度 1 时，
                     归一会把两个点都顶到最高、看着像满级（report 16 实测就是这样）。 */
                  BRILLIANCE_MAX,
                )}
                {brillianceDefs}
                {countNote(brilliants)}
              </>
            )}
          </Box>
        )}

        {tab === 2 && (
          <Box>
            {filterBar(true)}
            {bads.shown.length === 0 ? (
              <Typography variant="body2" color="text.secondary" sx={{ textAlign: 'center', py: 2 }}>
                {t('live:no_mistakes', 'No mistakes')}
              </Typography>
            ) : (
              <>
                {renderLollipop(
                  bads.shown,
                  (a) => badnessRank(a),
                  (a) => GRADE_BY_ID[(a.grade as GradeId) ?? 'unrated']?.color ?? '#888',
                  t('grade:axis_points_lost', '目损（最大 {n}）').replace(
                    '{n}',
                    Math.max(...bads.shown.map(badnessRank), 0).toFixed(1),
                  ),
                  (a) =>
                    `${t('live:move_number', 'Move')} ${a.move_number} ${a.move ?? ''} · ${sideLabel(a)} · ${tierLabel(a)} · -${badnessRank(a).toFixed(1)} ${t('live:points', 'pts')}`,
                )}
                {countNote(bads)}
              </>
            )}
          </Box>
        )}

        {tab === 3 && (
          <Box>
            {/* 发挥水准：七档分布。分母是该方自己在所选阶段内被评级的手数，两方各自归一。 */}
            {filterBar(false)}
            {histogram.blackTotal + histogram.whiteTotal === 0 ? (
              <Typography variant="body2" color="text.secondary" sx={{ textAlign: 'center', py: 2 }}>
                {t('grade:no_rated_moves', '本阶段没有已评级的着手')}
              </Typography>
            ) : (
              <>
                {renderHistogram()}
                {tierDefs}
                <Typography variant="caption" color="text.secondary" sx={{ display: 'block', pt: 1, lineHeight: 1.7 }}>
                  {t('grade:histogram_footer', '黑 {b} 手 / 白 {w} 手已评级')
                    .replace('{b}', String(histogram.blackTotal))
                    .replace('{w}', String(histogram.whiteTotal))}
                  {histogram.unrated > 0 && (
                    <>
                      {' · '}
                      {t('grade:histogram_unrated', '{n} 手未评级').replace('{n}', String(histogram.unrated))}
                    </>
                  )}
                </Typography>
              </>
            )}
          </Box>
        )}

        {tab === 4 && (
          <Box>
            {/* AI 一致率：实战手与引擎候选表的重合程度。三行**各有各的分母** ——
                「一选」在报告链路用服务端的 is_top_move、直播链路退回上一手 top_moves[0]；
                「前三」「不在前十选」只能靠上一手的候选表算，判不了的手不进分母。 */}
            <Stack direction={reportMode ? "column" : "row"} sx={{ mb: reportMode ? 0 : 1.5, flexWrap: 'wrap', gap: 1, justifyContent: 'space-between' }}>
              <Segmented
                vertical={reportMode}
        options={PHASE_OPTIONS}
                value={phase}
                onChange={setPhase}
                ariaLabel={t('grade:filter_phase', '阶段')}
              />
              <Segmented
                vertical={reportMode}
        options={MATCH_VIEW_OPTIONS}
                value={matchView}
                onChange={setMatchView}
                ariaLabel={t('grade:filter_match_view', '视图')}
              />
            </Stack>
            {matchRate.blackDecided + matchRate.whiteDecided === 0 ? (
              <Typography variant="body2" color="text.secondary" sx={{ textAlign: 'center', py: 2 }}>
                {t('grade:match_no_data', '本阶段还没有可比对的着手')}
              </Typography>
            ) : (
              <>
                {matchView === 'stats' ? renderMatchStats() : renderMatchTimeline()}
                <Typography variant="caption" color="text.secondary" sx={{ display: 'block', pt: 1, lineHeight: 1.7 }}>
                  {t('grade:match_footer', '分母是能与 AI 比对的手数：黑 {b} 手 / 白 {w} 手')
                    .replace('{b}', String(matchRate.blackDecided))
                    .replace('{w}', String(matchRate.whiteDecided))}
                  {matchRate.undecidable > 0
                    ? ` · ${t('grade:match_undecidable', '{n} 手无法比对').replace('{n}', String(matchRate.undecidable))}`
                    : ''}
                </Typography>
                {/* 这句是**硬性**的，不许在任何视图里省掉。分布图会让连续吻合段一眼可见，
                    但一致率高低本来就取决于局面难度（官子段谁都容易和 AI 一致）。
                    这张图的作用是让人看见值得去看的段落，不是替人下结论 ——
                    我们手上判作弊的证据一份都没有，界面上不能暗示我们有。 */}
                <Typography variant="caption" sx={{ display: 'block', mt: 0.5, color: 'warning.main', lineHeight: 1.7 }}>
                  {t(
                    'grade:match_caveat',
                    '一致率高低取决于局面难度，不能单独当作棋力或作弊的证据。',
                  )}
                </Typography>
              </>
            )}
          </Box>
        )}
      </Box>
    </Box>
  );
}
