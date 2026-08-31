import { Box, Chip, Stack, Tab, Tabs, Typography, useTheme } from '@mui/material';
import { useMemo, useState } from 'react';
import type { MoveAnalysis } from '../../types/live';
import { useTranslation } from '../../hooks/useTranslation';
import {
  badnessRank,
  brillianceRank,
  buildHistogram,
  buildMatchRate,
  GRADE_BY_ID,
  GRADE_PHASES,
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
}

export default function TrendChart({
  analysis,
  totalMoves,
  currentMove,
  onMoveClick,
}: TrendChartProps) {
  const { t } = useTranslation();
  const theme = useTheme();
  const [tab, setTab] = useState(0);

  // Extract data for chart
  const chartData = useMemo(() => {
    const moves: number[] = [];
    const winrates: number[] = [];
    const scores: number[] = [];

    for (let i = 0; i <= totalMoves; i++) {
      moves.push(i);
      const moveAnalysis = analysis[i];
      if (moveAnalysis) {
        winrates.push(moveAnalysis.winrate * 100);
        scores.push(moveAnalysis.score_lead);
      } else {
        // Interpolate or use default
        winrates.push(50);
        scores.push(0);
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
    return moveAnalysis ? moveAnalysis.winrate * 100 : 50;
  }, [analysis, currentMove]);

  const currentScoreLead = useMemo(() => {
    const moveAnalysis = analysis[currentMove];
    return moveAnalysis ? moveAnalysis.score_lead : 0;
  }, [analysis, currentMove]);

  // Dual-axis chart with winrate and score lead
  const renderDualChart = () => {
    if (chartData.winrates.length === 0) return null;

    const width = 420;
    const height = 180;
    const leftPadding = 42;
    const rightPadding = 42;
    const topPadding = 16;
    const bottomPadding = 12;
    const chartWidth = width - leftPadding - rightPadding;
    const chartHeight = height - topPadding - bottomPadding;

    const xStep = chartWidth / Math.max(1, chartData.winrates.length - 1);

    // Winrate points (0-100 -> chart coordinates)
    const winratePoints = chartData.winrates.map((value, i) => {
      const x = leftPadding + i * xStep;
      const y = topPadding + chartHeight - (value / 100) * chartHeight;
      return `${x},${y}`;
    }).join(' ');

    // Score points (scoreRange.min to scoreRange.max -> chart coordinates)
    const scorePoints = chartData.scores.map((value, i) => {
      const x = leftPadding + i * xStep;
      const normalized = (value - scoreRange.min) / (scoreRange.max - scoreRange.min);
      const y = topPadding + chartHeight - normalized * chartHeight;
      return `${x},${y}`;
    }).join(' ');

    // Current move indicator
    const currentX = leftPadding + currentMove * xStep;

    // Y-axis labels
    const winrateLabels = ['0%', '50%', '100%'];
    const scoreLabels = [`${scoreRange.min}`, '0', `+${scoreRange.max}`];

    return (
      <svg width="100%" height={height} viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="xMidYMid meet">
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
        <polyline
          fill="none"
          stroke="#ff9800"
          strokeWidth="1.5"
          strokeOpacity="0.8"
          points={scorePoints}
        />

        {/* Winrate line (green) */}
        <polyline
          fill="none"
          stroke="#4caf50"
          strokeWidth="2"
          points={winratePoints}
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
            const svgX = (x / rect.width) * width;
            const ratio = (svgX - leftPadding) / chartWidth;
            const move = Math.round(ratio * totalMoves);
            onMoveClick(Math.max(0, Math.min(totalMoves, move)));
          }}
        />
      </svg>
    );
  };

  const [phase, setPhase] = useState<PhaseId>('all');
  const [player, setPlayer] = useState<PlayerFilter>('both');

  const moves = useMemo(() => Object.values(analysis), [analysis]);

  // 直播链路的 analysis 由后端下发旧的三个布尔量、没有 grade；报告链路有 grade。
  // 两者共用这个组件，所以缺 grade 时退回旧布尔量，免得直播页整块空掉。
  const graded = useMemo<MoveAnalysis[]>(() => {
    if (moves.some((m) => m.grade)) return moves;
    return moves.map((m) => ({
      ...m,
      grade: (m.is_brilliant
        ? 'brilliant'
        : m.is_mistake
          ? 'mistake'
          : m.is_questionable
            ? 'inaccuracy'
            : 'unrated') as GradeId,
      points_lost: m.points_lost ?? -(m.delta_score ?? 0),
    }));
  }, [moves]);

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

  // tab 上的计数必须诚实：截断了就写 "5 / 50"，不能只显示截断后的数，
  // 否则用户会以为整盘只有 5 处问题。
  const countLabel = (sel: { shown: unknown[]; total: number }) =>
    sel.total > sel.shown.length ? `${sel.shown.length} / ${sel.total}` : `${sel.total}`;

  const filterBar = (withPlayer: boolean) => (
    <Stack direction="row" spacing={0.5} sx={{ mb: 1, flexWrap: 'wrap', gap: 0.5 }}>
      {(['all', ...GRADE_PHASES.map((p) => p.id)] as PhaseId[]).map((p) => (
        <Chip
          key={p}
          size="small"
          label={t(`grade:phase_${p}`, p)}
          color={phase === p ? 'primary' : 'default'}
          variant={phase === p ? 'filled' : 'outlined'}
          onClick={() => setPhase(p)}
        />
      ))}
      {withPlayer &&
        (['both', 'B', 'W'] as PlayerFilter[]).map((c) => (
          <Chip
            key={c}
            size="small"
            label={t(`grade:player_${c}`, c)}
            color={player === c ? 'primary' : 'default'}
            variant={player === c ? 'filled' : 'outlined'}
            onClick={() => setPlayer(c)}
          />
        ))}
    </Stack>
  );

  const truncationNote = (sel: { shown: unknown[]; total: number; truncated: number }) =>
    sel.truncated > 0 ? (
      <Typography variant="caption" color="text.secondary" sx={{ display: 'block', textAlign: 'center', py: 1 }}>
        {t('grade:truncated_note', '另有 {n} 处未列出，可切换阶段或棋手查看').replace(
          '{n}',
          String(sel.truncated),
        )}
      </Typography>
    ) : null;

  const sideLabel = (a: MoveAnalysis) =>
    a.player === 'B' ? t('live:black', 'B') : t('live:white', 'W');
  const tierLabel = (a: MoveAnalysis) => {
    const tier = GRADE_BY_ID[(a.grade as GradeId) ?? 'unrated'];
    return tier ? t(tier.i18nKey, tier.zh) : t('grade:unrated', '未评级');
  };

  /**
   * 黑白靠透明度是分不出来的（旧实现 white bar 只是 opacity 0.55，截图上两条一模一样）。
   * 改成**实心=黑、空心+斜纹=白**：形状差异不依赖色相，暗背景和色觉障碍下都立得住。
   * 档位色仍然留给「七档」那根轴，不被黑白占用。
   */
  const stoneDot = (side: 'black' | 'white', color: string) => (
    <Box
      component="span"
      sx={{
        display: 'inline-block',
        width: 9,
        height: 9,
        borderRadius: '50%',
        mr: 0.5,
        flexShrink: 0,
        bgcolor: side === 'black' ? color : 'transparent',
        border: side === 'white' ? `1.5px solid ${color}` : 'none',
        boxSizing: 'border-box',
      }}
    />
  );

  /** 一档两条：上黑下白。黑白标记同时出现在数字旁和条形前，不再依赖底部脚注去解释顺序。 */
  const pairedBars = (opts: {
    rowKey: string;
    label: string;
    color: string;
    black: number;
    white: number;
    blackRate: number;
    whiteRate: number;
    blackTotal?: number;
    whiteTotal?: number;
  }) => {
    const fmt = (n: number, rate: number, total?: number) =>
      total == null
        ? `${n} (${Math.round(rate * 100)}%)`
        : `${n}/${total} (${Math.round(rate * 100)}%)`;
    return (
      <Box key={opts.rowKey} sx={{ mb: 1.25 }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 0.5, gap: 1 }}>
          <Typography variant="caption" sx={{ color: opts.color, fontWeight: 600 }}>
            {opts.label}
          </Typography>
          <Typography
            variant="caption"
            color="text.secondary"
            sx={{ fontVariantNumeric: 'tabular-nums', whiteSpace: 'nowrap' }}
          >
            {stoneDot('black', 'currentColor')}
            {fmt(opts.black, opts.blackRate, opts.blackTotal)}
            <Box component="span" sx={{ display: 'inline-block', width: 10 }} />
            {stoneDot('white', 'currentColor')}
            {fmt(opts.white, opts.whiteRate, opts.whiteTotal)}
          </Typography>
        </Box>
        {(['black', 'white'] as const).map((side) => {
          const rate = Math.max(0, Math.min(1, side === 'black' ? opts.blackRate : opts.whiteRate));
          return (
            <Box key={side} sx={{ display: 'flex', alignItems: 'center', mb: 0.25 }}>
              {stoneDot(side, opts.color)}
              <Box
                sx={{
                  flex: 1,
                  height: 8,
                  bgcolor: 'action.hover',
                  borderRadius: 0.5,
                  overflow: 'hidden',
                  minWidth: 0,
                }}
              >
                {rate > 0 && (
                  <Box
                    sx={{
                      width: `${rate * 100}%`,
                      height: '100%',
                      boxSizing: 'border-box',
                      ...(side === 'black'
                        ? { bgcolor: opts.color }
                        : {
                            border: `1.5px solid ${opts.color}`,
                            backgroundImage: `repeating-linear-gradient(45deg, ${opts.color} 0 2px, transparent 2px 5px)`,
                            opacity: 0.85,
                          }),
                    }}
                  />
                )}
              </Box>
            </Box>
          );
        })}
      </Box>
    );
  };

  /**
   * 妙手 / 问题手的棒棒糖图：x 轴是**手数**（不是列表序），y 轴是幅度。
   * 250 手宽度下纯柱会细到看不见，所以用「细杆 + 端点圆」；端点圆承载档位色，
   * 实心=黑、空心=白，与上面的条形图同一套编码。端点即点击热区，保留原来的跳手行为。
   */
  const renderLollipop = (
    items: MoveAnalysis[],
    direction: 'up' | 'down',
    magnitude: (a: MoveAnalysis) => number,
    tipText: (a: MoveAnalysis) => string,
  ) => {
    if (items.length === 0) return null;
    const width = 420;
    // viewBox 宽 420 而右栏实宽约 330 ⇒ 整张图会被缩到 ~0.79。
    // 这里的数是**缩放前**的，想要屏上 ~118px 就得写 150。
    const height = 150;
    const padX = 12;
    const padTop = 16;
    const padBottom = 18;
    const plot = height - padTop - padBottom;
    const span = Math.max(1, totalMoves);
    const maxMag = Math.max(...items.map((a) => Math.max(0, magnitude(a))), 1e-6);
    const baselineY = direction === 'up' ? height - padBottom : padTop;
    const xOf = (n: number) => padX + (Math.max(0, Math.min(span, n)) / span) * (width - padX * 2);
    const labelled: number[] = [];

    return (
      <Box sx={{ bgcolor: 'background.default', borderRadius: 1, px: 0.5, py: 0.5, mb: 1 }}>
        <svg width="100%" height={height} viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="xMidYMid meet">
          <line
            x1={padX}
            y1={baselineY}
            x2={width - padX}
            y2={baselineY}
            stroke="rgba(255,255,255,0.28)"
            strokeWidth="1"
          />
          {currentMove > 0 && (
            <line
              x1={xOf(currentMove)}
              y1={padTop}
              x2={xOf(currentMove)}
              y2={height - padBottom}
              stroke="rgba(255,255,255,0.45)"
              strokeWidth="1"
              strokeDasharray="3 3"
            />
          )}
          {items.map((a) => {
            const color = GRADE_BY_ID[(a.grade as GradeId) ?? 'unrated']?.color ?? '#888';
            const len = (Math.max(0, magnitude(a)) / maxMag) * plot;
            const x = xOf(a.move_number);
            const tipY = direction === 'up' ? baselineY - len : baselineY + len;
            const isBlack = a.player === 'B';
            const showLabel = labelled.every((lx) => Math.abs(lx - x) >= 24);
            if (showLabel) labelled.push(x);
            return (
              <g key={a.move_number} style={{ cursor: onMoveClick ? 'pointer' : 'default' }}>
                <title>{tipText(a)}</title>
                <line x1={x} y1={baselineY} x2={x} y2={tipY} stroke={color} strokeWidth="2" strokeOpacity="0.6" />
                <circle
                  cx={x}
                  cy={tipY}
                  r="5.5"
                  fill={isBlack ? color : theme.palette.background.default}
                  stroke={color}
                  strokeWidth="2"
                />
                {showLabel && (
                  <text
                    x={x}
                    /* 向下的图把手数标在基线**上方**：标在底部会和最深的那根杆撞上。 */
                    y={direction === 'up' ? height - 5 : padTop - 3}
                    textAnchor="middle"
                    fill="rgba(255,255,255,0.55)"
                    fontSize="11"
                  >
                    {a.move_number}
                  </text>
                )}
                <circle
                  cx={x}
                  cy={tipY}
                  r="10"
                  fill="transparent"
                  onClick={() => onMoveClick?.(a.move_number)}
                />
              </g>
            );
          })}
        </svg>
      </Box>
    );
  };

  const moveRow = (a: MoveAnalysis) => {
    const tier = GRADE_BY_ID[(a.grade as GradeId) ?? 'unrated'];
    const color = tier?.color ?? '#888';
    return (
      <Box
        key={a.move_number}
        sx={{
          p: 1.5,
          mb: 1,
          bgcolor: 'background.default',
          borderRadius: 1,
          cursor: 'pointer',
          '&:hover': { bgcolor: 'action.hover' },
          borderLeft: 3,
          borderColor: color,
        }}
        onClick={() => onMoveClick?.(a.move_number)}
      >
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Typography variant="body2" fontWeight="bold">
            {t('live:move_number', 'Move')} {a.move_number} {a.move}
          </Typography>
          <Typography variant="caption" sx={{ color }}>
            {/* 妙手优先显示妙度：走了首选也可能有小额目损（order-0 不等于目数最优，
                实测 17.7%-34.4% 的局面两者不同），旧写法会让妙度标签被那点损失顶掉。 */}
            {a.brilliance
              ? `${t('grade:brilliance', '妙度')} ${a.brilliance}`
              : a.points_lost != null && a.points_lost > 0
                ? `-${a.points_lost.toFixed(1)} ${t('live:points', 'pts')}`
                : ''}
          </Typography>
        </Box>
        <Typography variant="caption" color="text.secondary">
          {a.player === 'B' ? t('live:black', 'B') : t('live:white', 'W')}{' '}
          <Box component="span" sx={{ color }}>
            {tier ? t(tier.i18nKey, tier.zh) : t('grade:unrated', '未评级')}
          </Box>
        </Typography>
      </Box>
    );
  };

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      {/* Sticky tabs header */}
      {/* 五个 tab 在右栏（实测 349px）里放不下：内容宽 500px。MUI 默认 variant 是
          standard —— 溢出部分被 overflow-x:hidden 切掉且**没有滚动按钮**，第 5 个 tab
          用户够不到（Playwright 能点是因为它会程序化 scrollIntoView，不算数）。 */}
      <Tabs
        value={tab}
        onChange={(_, v) => setTab(v)}
        variant="scrollable"
        scrollButtons="auto"
        allowScrollButtonsMobile
        sx={{
          borderBottom: 1,
          borderColor: 'divider',
          minHeight: 36,
          flexShrink: 0,
          bgcolor: 'background.paper',
        }}
      >
        <Tab label={t('live:trend_chart', 'Trend')} sx={{ minHeight: 36, py: 0 }} />
        <Tab label={`${t('live:brilliant', 'Brilliant')} (${countLabel(brilliants)})`} sx={{ minHeight: 36, py: 0 }} />
        <Tab label={`${t('live:mistakes', 'Mistakes')} (${countLabel(bads)})`} sx={{ minHeight: 36, py: 0 }} />
        <Tab label={t('grade:performance', '发挥水准')} sx={{ minHeight: 36, py: 0 }} />
        <Tab label={t('grade:match_rate', 'AI吻合度')} sx={{ minHeight: 36, py: 0 }} />
      </Tabs>

      {/* Scrollable content area */}
      <Box sx={{ px: 1.5, py: 1, flex: 1, overflow: 'auto' }}>
        {tab === 0 && (
          <Box>
            {/* Values display above chart */}
            <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5, px: 0.5 }}>
              <Typography variant="body2" sx={{ color: '#4caf50', fontWeight: 600 }}>
                {t('live:black_winrate', 'Black Winrate')}: {currentWinrate.toFixed(1)}%
              </Typography>
              <Typography variant="body2" sx={{ color: '#ff9800', fontWeight: 600 }}>
                {t('live:black_lead', 'Black Lead')}: {currentScoreLead >= 0 ? '+' : ''}{currentScoreLead.toFixed(1)} {t('live:points_unit', 'pts')}
              </Typography>
            </Box>
            <Box sx={{ bgcolor: 'background.default', borderRadius: 1, p: 0.5 }}>
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
                  'up',
                  (a) => a.brilliance ?? 1,
                  (a) =>
                    `${t('live:move_number', 'Move')} ${a.move_number} ${a.move ?? ''} · ${sideLabel(a)} · ${t('grade:brilliance', '妙度')} ${a.brilliance ?? 1}`,
                )}
                {brilliants.shown.map(moveRow)}
                {truncationNote(brilliants)}
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
                  'down',
                  (a) => badnessRank(a),
                  (a) =>
                    `${t('live:move_number', 'Move')} ${a.move_number} ${a.move ?? ''} · ${sideLabel(a)} · ${tierLabel(a)} · -${badnessRank(a).toFixed(1)} ${t('live:points', 'pts')}`,
                )}
                {bads.shown.map(moveRow)}
                {truncationNote(bads)}
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
                {histogram.cells.map((cell) =>
                  pairedBars({
                    rowKey: cell.tier.id,
                    label: t(cell.tier.i18nKey, cell.tier.zh),
                    color: cell.tier.color,
                    black: cell.black,
                    white: cell.white,
                    blackRate: cell.blackRate,
                    whiteRate: cell.whiteRate,
                  }),
                )}
                <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 1 }}>
                  {t('grade:histogram_footer', '黑 {b} 手 / 白 {w} 手已评级')
                    .replace('{b}', String(histogram.blackTotal))
                    .replace('{w}', String(histogram.whiteTotal))}
                  {histogram.unrated > 0
                    ? ` · ${t('grade:unrated_count', '{n} 手未评级').replace('{n}', String(histogram.unrated))}`
                    : ''}
                </Typography>
              </>
            )}
          </Box>
        )}

        {tab === 4 && (
          <Box>
            {/* AI 一致率：实战手与引擎候选表的重合程度。三行**各有各的分母** ——
                「一选」在报告链路用服务端的 is_top_move、直播链路退回上一手 top_moves[0]；
                「前三」「完全没考虑」只能靠上一手的候选表算，判不了的手不进分母。 */}
            {filterBar(false)}
            {matchRate.blackDecided + matchRate.whiteDecided === 0 ? (
              <Typography variant="body2" color="text.secondary" sx={{ textAlign: 'center', py: 2 }}>
                {t('grade:match_no_data', '本阶段还没有可比对的着手')}
              </Typography>
            ) : (
              <>
                {matchRate.rows.map((row) =>
                  pairedBars({
                    rowKey: row.id,
                    label: t(row.i18nKey, row.zh),
                    color: row.color,
                    black: row.black,
                    white: row.white,
                    blackRate: row.blackRate,
                    whiteRate: row.whiteRate,
                    blackTotal: row.blackTotal,
                    whiteTotal: row.whiteTotal,
                  }),
                )}
                <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 1 }}>
                  {t('grade:match_footer', '分母是能与 AI 比对的手数：黑 {b} 手 / 白 {w} 手')
                    .replace('{b}', String(matchRate.blackDecided))
                    .replace('{w}', String(matchRate.whiteDecided))}
                  {matchRate.undecidable > 0
                    ? ` · ${t('grade:match_undecidable', '{n} 手无法比对').replace('{n}', String(matchRate.undecidable))}`
                    : ''}
                </Typography>
                <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 0.5 }}>
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
