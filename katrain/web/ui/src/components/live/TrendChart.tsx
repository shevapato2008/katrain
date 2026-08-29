import { Box, Chip, Stack, Tab, Tabs, Typography } from '@mui/material';
import { useMemo, useState } from 'react';
import type { MoveAnalysis } from '../../types/live';
import { useTranslation } from '../../hooks/useTranslation';
import {
  badnessRank,
  brillianceRank,
  buildHistogram,
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
            {a.points_lost != null && a.points_lost > 0
              ? `-${a.points_lost.toFixed(1)} ${t('live:points', 'pts')}`
              : a.brilliance
                ? `${t('grade:brilliance', '玄妙')} ${a.brilliance}`
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
      <Tabs
        value={tab}
        onChange={(_, v) => setTab(v)}
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
                {histogram.cells.map((cell) => (
                  <Box key={cell.tier.id} sx={{ mb: 1 }}>
                    <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 0.25 }}>
                      <Typography variant="caption" sx={{ color: cell.tier.color, fontWeight: 600 }}>
                        {t(cell.tier.i18nKey, cell.tier.zh)}
                      </Typography>
                      <Typography variant="caption" color="text.secondary">
                        {cell.black} ({Math.round(cell.blackRate * 100)}%) · {cell.white} (
                        {Math.round(cell.whiteRate * 100)}%)
                      </Typography>
                    </Box>
                    {(['black', 'white'] as const).map((side) => (
                      <Box
                        key={side}
                        sx={{ height: 6, bgcolor: 'action.hover', borderRadius: 0.5, mb: 0.25, overflow: 'hidden' }}
                      >
                        <Box
                          sx={{
                            width: `${(side === 'black' ? cell.blackRate : cell.whiteRate) * 100}%`,
                            height: '100%',
                            bgcolor: cell.tier.color,
                            opacity: side === 'black' ? 1 : 0.55,
                          }}
                        />
                      </Box>
                    ))}
                  </Box>
                ))}
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
      </Box>
    </Box>
  );
}
