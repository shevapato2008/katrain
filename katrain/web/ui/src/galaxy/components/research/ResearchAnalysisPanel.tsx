import { Box, Typography, LinearProgress, Divider, IconButton, Stack, Slider, Tooltip, Tabs, Tab } from '@mui/material';
import { useState, useMemo, useCallback, useEffect, useRef } from 'react';
import ChevronLeftIcon from '@mui/icons-material/ChevronLeft';
import ChevronRightIcon from '@mui/icons-material/ChevronRight';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import PauseIcon from '@mui/icons-material/Pause';
import KeyboardDoubleArrowLeftIcon from '@mui/icons-material/KeyboardDoubleArrowLeft';
import KeyboardDoubleArrowRightIcon from '@mui/icons-material/KeyboardDoubleArrowRight';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import ResearchToolbar, { type PlaceMode, type EditMode } from './ResearchToolbar';
import { useTranslation } from '../../../hooks/useTranslation';

// Convert Move.coords [x, y] to GTP notation (e.g., [3, 15] → "D16")
// x = column index into GTP_LETTERS, y = 0-based row from bottom
const GTP_LETTERS = 'ABCDEFGHJKLMNOPQRSTUVWXYZ'; // skip I
function coordsToGtp(coords: [number, number]): string {
  const [x, y] = coords;
  return `${GTP_LETTERS[x]}${y + 1}`;
}

// Shared column layout for AI recommendation tables — must match AiAnalysis in live module
const AI_TABLE_COLUMNS = '1fr 1fr 1fr 1fr';

interface AnalysisMove {
  move: string;
  coords: [number, number] | null;
  winrate: number;
  scoreLead?: number;
  scoreLoss: number;
  visits: number;
  psv?: number;
  pv?: string[];
  pointsLost?: number;
  prior?: number;
}

interface HistoryEntry {
  node_id: number;
  winrate: number | null;
  score: number | null;
}

// Map rules identifier to display name (needs t function passed in)
function rulesDisplayName(rules: string, t: (key: string, fallback: string) => string): string {
  switch (rules.toLowerCase()) {
    case 'chinese': return t('research:rules_chinese', '中国规则');
    case 'japanese': return t('research:rules_japanese', '日本规则');
    case 'korean': return t('research:rules_korean', '韩国规则');
    default: return rules;
  }
}

interface ResearchAnalysisPanelProps {
  playerBlack: string;
  playerWhite: string;
  currentMove: number;
  totalMoves: number;
  onMoveChange: (move: number) => void;
  winrate: number;
  scoreLead: number;
  // Game metadata
  rules?: string;
  komi?: number;
  handicap?: number;
  boardSize?: number;
  showMoveNumbers: boolean;
  onToggleMoveNumbers: () => void;
  onPass: () => void;
  editMode: EditMode;
  onEditModeChange: (mode: EditMode) => void;
  placeMode: PlaceMode;
  onPlaceModeChange: (mode: PlaceMode) => void;
  showHints: boolean;
  onToggleHints: () => void;
  showTerritory: boolean;
  onToggleTerritory: () => void;
  onClear: () => void;
  onOpen?: () => void;
  onSave?: () => void;
  onCopyToClipboard?: () => void;
  onSaveToCloud?: () => void;
  onOpenFromCloud?: () => void;
  isAnalysisPending?: boolean;
  // Real data props
  analysisMoves?: AnalysisMove[];
  history?: HistoryEntry[];
  playerToMove?: string;
  // Children of current node: [color, [row, col] | null][]
  children?: [string, [number, number] | null][];
}

// Threshold for classifying moves (in score points, matching live module)
const BRILLIANT_THRESHOLD = 2.0;      // gains >= 2.0 points → 妙手
const MISTAKE_THRESHOLD = -3.0;       // loses >= 3.0 points → 问题手
const QUESTIONABLE_THRESHOLD = -1.5;  // loses >= 1.5 points → 疑问手

export default function ResearchAnalysisPanel({
  playerBlack,
  playerWhite,
  currentMove,
  totalMoves,
  onMoveChange,
  winrate,
  scoreLead,
  showMoveNumbers,
  onToggleMoveNumbers,
  onPass,
  editMode,
  onEditModeChange,
  placeMode,
  onPlaceModeChange,
  showHints,
  onToggleHints,
  showTerritory,
  onToggleTerritory,
  onClear,
  onOpen,
  onSave,
  onCopyToClipboard,
  onSaveToCloud,
  onOpenFromCloud,
  rules,
  komi,
  handicap,
  boardSize,
  isAnalysisPending = false,
  analysisMoves,
  history,
  playerToMove,
  children,
}: ResearchAnalysisPanelProps) {
  const { t } = useTranslation();
  const [trendTab, setTrendTab] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const audioCache = useRef<Record<string, HTMLAudioElement>>({});

  // Auto-play effect
  useEffect(() => {
    if (!isPlaying) return;
    const interval = setInterval(() => {
      if (currentMove < totalMoves) {
        onMoveChange(currentMove + 1);
      } else {
        setIsPlaying(false);
      }
    }, 1000);
    return () => clearInterval(interval);
  }, [isPlaying, currentMove, totalMoves, onMoveChange]);

  // Stop playing when reaching end
  useEffect(() => {
    if (currentMove >= totalMoves) setIsPlaying(false);
  }, [currentMove, totalMoves]);

  // Play stone sound on navigation
  const prevMoveRef = useRef(currentMove);
  useEffect(() => {
    if (currentMove !== prevMoveRef.current) {
      prevMoveRef.current = currentMove;
      const soundName = 'stone1';
      if (!audioCache.current[soundName]) {
        audioCache.current[soundName] = new Audio(`/assets/sounds/${soundName}.wav`);
      }
      const audio = audioCache.current[soundName];
      audio.currentTime = 0;
      audio.play().catch(() => {});
    }
  }, [currentMove]);

  const winratePercent = winrate * 100;
  const blackAdvantage = winrate > 0.5;

  const iconButtonStyle = {
    color: 'text.secondary',
    '&:hover': { color: 'text.primary', bgcolor: 'rgba(255,255,255,0.05)' },
  };

  // Classify moves as 妙手 or 问题手 from history score changes
  // Uses score delta (in points) matching the live module's thresholds
  const { goodMoves, badMoves } = useMemo(() => {
    const good: { moveIndex: number; delta: number; player: string }[] = [];
    const bad: { moveIndex: number; delta: number; player: string }[] = [];
    if (!history || history.length < 2) return { goodMoves: good, badMoves: bad };

    // In handicap games (handicap > 0), move 1 = White (odd=W, even=B)
    // In normal games, move 1 = Black (odd=B, even=W)
    const isHandicap = (handicap ?? 0) > 0;

    for (let i = 1; i < history.length; i++) {
      const prev = history[i - 1];
      const curr = history[i];
      if (prev.score === null || curr.score === null) continue;

      // Determine player who made move i based on handicap parity
      const player: string = isHandicap
        ? (i % 2 === 1 ? 'W' : 'B')
        : (i % 2 === 1 ? 'B' : 'W');

      // Score delta from the moving player's perspective
      // score is Black's lead in points (positive = Black ahead)
      const rawScoreDelta = curr.score - prev.score;
      const playerDelta = player === 'B' ? rawScoreDelta : -rawScoreDelta;

      if (playerDelta >= BRILLIANT_THRESHOLD) {
        good.push({ moveIndex: i, delta: playerDelta, player });
      } else if (playerDelta <= QUESTIONABLE_THRESHOLD) {
        // Both mistakes (<=−3.0) and questionable moves (−3.0 < delta <= −1.5)
        bad.push({ moveIndex: i, delta: playerDelta, player });
      }
    }
    // Sort: good moves by largest delta desc, bad moves by worst delta asc
    good.sort((a, b) => b.delta - a.delta);
    bad.sort((a, b) => a.delta - b.delta);
    return { goodMoves: good, badMoves: bad };
  }, [history, handicap]);

  // Determine next player for AI recommendations display
  const nextPlayer: 'B' | 'W' = playerToMove === 'W' ? 'W' : 'B';

  // Determine actual move played from children of current node
  const actualMoveGtp = useMemo(() => {
    if (!children || children.length === 0) return null;
    const firstChild = children[0];
    if (!firstChild[1]) return null; // pass move
    return coordsToGtp(firstChild[1]);
  }, [children]);

  // Build display moves: top 3 + actual move (matching Live module logic)
  const displayMoves = useMemo(() => {
    if (!analysisMoves || analysisMoves.length === 0) return [];

    const topN = 3;
    const topMoves = analysisMoves.slice(0, topN);

    // Check if actual move is in top N
    const actualMoveInTop = actualMoveGtp ? topMoves.findIndex(m => m.move === actualMoveGtp) : -1;

    let movesToShow: (AnalysisMove & { isActualMove?: boolean })[] = [];

    if (actualMoveInTop >= 0 || !actualMoveGtp) {
      // Actual move is in top N or no actual move - show top N only
      movesToShow = topMoves.map(m => ({
        ...m,
        isActualMove: actualMoveGtp === m.move,
      }));
    } else {
      // Actual move is NOT in top N - show top N + actual move
      movesToShow = topMoves.map(m => ({
        ...m,
        isActualMove: false,
      }));

      // Find actual move in all analysis moves
      const actualMoveData = analysisMoves.find(m => m.move === actualMoveGtp);
      if (actualMoveData) {
        movesToShow.push({
          ...actualMoveData,
          isActualMove: true,
        });
      } else {
        // Actual move not in analysis - create placeholder
        movesToShow.push({
          move: actualMoveGtp,
          coords: null,
          winrate: 0,
          scoreLead: 0,
          scoreLoss: 0,
          visits: 0,
          psv: 0,
          isActualMove: true,
        });
      }
    }

    // Calculate percentage based on psv (matching Live module)
    const totalPsv = movesToShow.reduce((sum, m) => sum + (m.psv || 0), 0);
    const totalVisits = movesToShow.reduce((sum, m) => sum + m.visits, 0);
    const usePsv = totalPsv > 0;

    return movesToShow.map(m => ({
      ...m,
      percentage: usePsv
        ? ((m.psv || 0) / totalPsv) * 100
        : (totalVisits > 0 ? (m.visits / totalVisits) * 100 : 0),
    }));
  }, [analysisMoves, actualMoveGtp]);

  const renderTrendChart = useCallback(() => {
    const width = 420;
    const height = 140;
    const leftPad = 42;
    const rightPad = 42;
    const topPad = 12;
    const bottomPad = 12;
    const chartWidth = width - leftPad - rightPad;
    const chartHeight = height - topPad - bottomPad;

    // Build winrate data points from history
    const dataPoints: { x: number; y: number }[] = [];
    if (history && history.length > 1) {
      const maxIdx = history.length - 1;
      for (let i = 0; i < history.length; i++) {
        if (history[i].winrate !== null) {
          dataPoints.push({
            x: leftPad + (i / maxIdx) * chartWidth,
            y: topPad + chartHeight - (history[i].winrate as number) * chartHeight,
          });
        }
      }
    }

    // Build path string
    let pathD = '';
    if (dataPoints.length >= 2) {
      pathD = `M ${dataPoints[0].x} ${dataPoints[0].y}`;
      for (let i = 1; i < dataPoints.length; i++) {
        pathD += ` L ${dataPoints[i].x} ${dataPoints[i].y}`;
      }
    }

    // Fill area: black side (above 50%) and white side (below 50%)
    const midY = topPad + chartHeight / 2;
    let fillPathBlack = '';
    let fillPathWhite = '';
    if (dataPoints.length >= 2) {
      // Black fill: area between line and 50% where winrate > 50%
      fillPathBlack = `M ${dataPoints[0].x} ${midY}`;
      for (const p of dataPoints) {
        fillPathBlack += ` L ${p.x} ${Math.min(p.y, midY)}`;
      }
      fillPathBlack += ` L ${dataPoints[dataPoints.length - 1].x} ${midY} Z`;

      // White fill: area between 50% and line where winrate < 50%
      fillPathWhite = `M ${dataPoints[0].x} ${midY}`;
      for (const p of dataPoints) {
        fillPathWhite += ` L ${p.x} ${Math.max(p.y, midY)}`;
      }
      fillPathWhite += ` L ${dataPoints[dataPoints.length - 1].x} ${midY} Z`;
    }

    return (
      <svg width="100%" height={height} viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="xMidYMid meet">
        {/* Grid lines at 0%, 50%, 100% */}
        {[0, 0.5, 1].map((ratio, i) => {
          const y = topPad + chartHeight - ratio * chartHeight;
          return (
            <g key={i}>
              <line
                x1={leftPad} y1={y} x2={width - rightPad} y2={y}
                stroke="rgba(255,255,255,0.1)"
                strokeDasharray={ratio === 0.5 ? '4' : '0'}
              />
              <text x={leftPad - 6} y={y} textAnchor="end" dominantBaseline="middle" fill="rgba(76,175,80,0.8)" fontSize="11">
                {`${(ratio * 100).toFixed(0)}%`}
              </text>
            </g>
          );
        })}
        {/* 50% center line */}
        <line
          x1={leftPad} y1={midY}
          x2={leftPad + chartWidth} y2={midY}
          stroke="rgba(76,175,80,0.3)" strokeWidth="1.5"
        />
        {/* Fill areas */}
        {fillPathBlack && (
          <path d={fillPathBlack} fill="rgba(30,30,30,0.4)" />
        )}
        {fillPathWhite && (
          <path d={fillPathWhite} fill="rgba(200,200,200,0.15)" />
        )}
        {/* Winrate line */}
        {pathD && (
          <path d={pathD} fill="none" stroke="#4caf50" strokeWidth="1.5" />
        )}
        {/* Current move indicator */}
        {totalMoves > 0 && (
          <line
            x1={leftPad + (currentMove / totalMoves) * chartWidth}
            y1={topPad}
            x2={leftPad + (currentMove / totalMoves) * chartWidth}
            y2={height - bottomPad}
            stroke="rgba(255,255,255,0.5)"
            strokeWidth="1"
          />
        )}
        {/* "No data" placeholder when no analysis available */}
        {dataPoints.length === 0 && (
          <text x={width / 2} y={height / 2} textAnchor="middle" dominantBaseline="middle" fill="rgba(255,255,255,0.2)" fontSize="14">
            {t('research:analysis_placeholder', '分析数据将在此显示')}
          </text>
        )}
      </svg>
    );
  }, [history, currentMove, totalMoves]);

  const handleChartClick = useCallback((e: React.MouseEvent<SVGSVGElement>) => {
    if (!history || history.length < 2 || totalMoves === 0) return;
    const svg = e.currentTarget;
    const rect = svg.getBoundingClientRect();
    const svgWidth = 420;
    const leftPad = 42;
    const rightPad = 42;
    const chartWidth = svgWidth - leftPad - rightPad;
    // Map click position to move index
    const relX = ((e.clientX - rect.left) / rect.width) * svgWidth - leftPad;
    const ratio = Math.max(0, Math.min(1, relX / chartWidth));
    const moveIdx = Math.round(ratio * totalMoves);
    onMoveChange(moveIdx);
  }, [history, totalMoves, onMoveChange]);

  return (
    <Box sx={{
      width: 500,
      height: '100%',
      display: 'flex',
      flexDirection: 'column',
      bgcolor: 'background.paper',
      borderLeft: '1px solid rgba(255,255,255,0.05)',
    }}>
      <Box sx={{ flexGrow: 1, overflow: 'auto', display: 'flex', flexDirection: 'column' }}>
        {/* Player Info + Winrate Bar */}
        <Box sx={{ p: 2, borderBottom: 1, borderColor: 'divider' }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 1.5 }}>
            <Box sx={{ flex: 1 }}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <Box sx={{ width: 16, height: 16, borderRadius: '50%', bgcolor: '#000', boxShadow: '0 1px 2px rgba(0,0,0,0.3)' }} />
                <Typography variant="body1" fontWeight={blackAdvantage ? 700 : 400} sx={{ fontSize: '0.95rem' }}>
                  {playerBlack || t('research:black', '黑方')}
                </Typography>
              </Box>
            </Box>
            <Typography variant="body2" color="text.secondary">vs</Typography>
            <Box sx={{ flex: 1, textAlign: 'right' }}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, justifyContent: 'flex-end' }}>
                <Typography variant="body1" fontWeight={!blackAdvantage ? 700 : 400} sx={{ fontSize: '0.95rem' }}>
                  {playerWhite || t('research:white', '白方')}
                </Typography>
                <Box sx={{ width: 16, height: 16, borderRadius: '50%', bgcolor: '#fff', border: '1px solid', borderColor: 'grey.400', boxShadow: '0 1px 2px rgba(0,0,0,0.2)' }} />
              </Box>
            </Box>
          </Box>

          {/* Game metadata summary */}
          {(handicap != null && handicap > 0 || rules || komi != null || boardSize != null) && (
            <Box sx={{
              display: 'flex',
              flexWrap: 'wrap',
              gap: 0.75,
              mb: 1.5,
              pb: 1.25,
              borderBottom: '1px solid rgba(255,255,255,0.06)',
            }}>
              {boardSize != null && (
                <Typography variant="caption" sx={{
                  px: 1, py: 0.25,
                  bgcolor: 'rgba(255,255,255,0.06)',
                  borderRadius: 0.5,
                  color: 'text.secondary',
                  fontSize: '0.75rem',
                  letterSpacing: 0.3,
                }}>
                  {boardSize}×{boardSize}
                </Typography>
              )}
              {rules && (
                <Typography variant="caption" sx={{
                  px: 1, py: 0.25,
                  bgcolor: 'rgba(255,255,255,0.06)',
                  borderRadius: 0.5,
                  color: 'text.secondary',
                  fontSize: '0.75rem',
                  letterSpacing: 0.3,
                }}>
                  {rulesDisplayName(rules, t)}
                </Typography>
              )}
              {komi != null && (
                <Typography variant="caption" sx={{
                  px: 1, py: 0.25,
                  bgcolor: 'rgba(255,255,255,0.06)',
                  borderRadius: 0.5,
                  color: 'text.secondary',
                  fontSize: '0.75rem',
                  letterSpacing: 0.3,
                }}>
                  {t('research:komi', '贴目 {komi}').replace('{komi}', String(komi))}
                </Typography>
              )}
              {handicap != null && handicap > 0 && (
                <Typography variant="caption" sx={{
                  px: 1, py: 0.25,
                  bgcolor: 'rgba(76,175,80,0.12)',
                  borderRadius: 0.5,
                  color: '#81c784',
                  fontSize: '0.75rem',
                  fontWeight: 600,
                  letterSpacing: 0.3,
                }}>
                  {t('research:handicap', '让{handicap}子').replace('{handicap}', String(handicap))}
                </Typography>
              )}
            </Box>
          )}

          {/* Winrate bar */}
          <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5 }}>
            <Typography variant="body2" fontWeight={blackAdvantage ? 700 : 400} sx={{ fontSize: '0.875rem' }}>
              {winratePercent.toFixed(1)}%
            </Typography>
            <Typography variant="body2" color="text.secondary" fontWeight={700} sx={{ fontSize: '0.875rem' }}>
              {t('research:points', '{delta} 目').replace('{delta}', `${scoreLead > 0 ? '+' : ''}${scoreLead.toFixed(1)}`)}
            </Typography>
            <Typography variant="body2" fontWeight={!blackAdvantage ? 700 : 400} sx={{ fontSize: '0.875rem' }}>
              {(100 - winratePercent).toFixed(1)}%
            </Typography>
          </Box>
          <LinearProgress
            variant="determinate"
            value={winratePercent}
            sx={{
              height: 8,
              borderRadius: 4,
              bgcolor: 'grey.200',
              '& .MuiLinearProgress-bar': { bgcolor: '#000', borderRadius: 4 },
            }}
          />
        </Box>

        {/* Toolbar */}
        <Box sx={{ p: 2 }}>
          <ResearchToolbar
            isAnalyzing={true}
            showMoveNumbers={showMoveNumbers}
            onToggleMoveNumbers={onToggleMoveNumbers}
            onPass={onPass}
            editMode={editMode}
            onEditModeChange={onEditModeChange}
            placeMode={placeMode}
            onPlaceModeChange={onPlaceModeChange}
            showHints={showHints}
            onToggleHints={onToggleHints}
            showTerritory={showTerritory}
            onToggleTerritory={onToggleTerritory}
            onClear={onClear}
            onOpen={onOpen}
            onSave={onSave}
            onCopyToClipboard={onCopyToClipboard}
            onSaveToCloud={onSaveToCloud}
            onOpenFromCloud={onOpenFromCloud}
            isAnalysisPending={isAnalysisPending}
          />
        </Box>

        <Divider />

        {/* AI Recommendations */}
        <Box sx={{ px: 2, py: 1.5 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 0.5 }}>
            <Typography variant="body2" sx={{ fontWeight: 600 }}>
              {t('research:ai_recommendations', 'AI 推荐')}
            </Typography>
            {analysisMoves && analysisMoves.length > 0 && (
              <Typography variant="caption" color="text.secondary">
                {t('research:after_move', '第 {currentMove} 手后').replace('{currentMove}', String(currentMove))}
              </Typography>
            )}
          </Box>
          {/* Column headers */}
          <Box sx={{
            display: 'grid',
            gridTemplateColumns: AI_TABLE_COLUMNS,
            gap: 0.5,
            px: 1,
            py: 0.5,
            bgcolor: 'rgba(255,255,255,0.05)',
            borderRadius: 1,
            mb: 0.5,
          }}>
            <Typography variant="body2" color="text.secondary" sx={{ fontSize: '0.8rem' }}>{t('research:col_move', '着手')}</Typography>
            <Typography variant="body2" color="text.secondary" sx={{ textAlign: 'center', fontSize: '0.8rem' }}>{t('research:col_recommendation', '推荐度')}</Typography>
            <Typography variant="body2" color="text.secondary" sx={{ textAlign: 'center', fontSize: '0.8rem' }}>{t('research:col_score_diff', '目差')}</Typography>
            <Typography variant="body2" color="text.secondary" sx={{ textAlign: 'center', fontSize: '0.8rem' }}>{t('research:col_winrate', '胜率')}</Typography>
          </Box>
          {/* Move rows */}
          {displayMoves.length > 0 ? (
            <Box sx={{ maxHeight: 160, overflowY: 'auto' }}>
              {displayMoves.map((move) => {
                // scoreLead is from Black's perspective; adjust for display player
                const rawScore = move.scoreLead ?? 0;
                const sLead = nextPlayer === 'B' ? rawScore : -rawScore;
                const wr = nextPlayer === 'B' ? move.winrate : 1 - move.winrate;
                const oppWr = 1 - wr;
                const isActual = move.isActualMove || false;
                return (
                  <Box
                    key={move.move}
                    sx={{
                      display: 'grid',
                      gridTemplateColumns: AI_TABLE_COLUMNS,
                      gap: 0.5,
                      py: 0.5,
                      px: 1,
                      mb: 0.25,
                      borderRadius: 1,
                      cursor: 'pointer',
                      transition: 'background-color 0.15s',
                      bgcolor: isActual ? 'rgba(76, 175, 80, 0.15)' : 'transparent',
                      border: isActual ? '1px solid' : '1px solid transparent',
                      borderColor: isActual ? 'success.main' : 'transparent',
                      '&:hover': { bgcolor: 'action.hover' },
                    }}
                  >
                    {/* Move */}
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75 }}>
                      <Box sx={{
                        width: 14, height: 14, borderRadius: '50%', flexShrink: 0,
                        bgcolor: nextPlayer === 'B' ? '#1a1a1a' : '#f5f5f5',
                        border: nextPlayer === 'W' ? '1px solid #666' : 'none',
                      }} />
                      <Typography variant="body2" fontWeight="bold" sx={{ fontSize: '0.85rem' }}>
                        {move.move}
                      </Typography>
                      {isActual && (
                        <CheckCircleIcon sx={{ fontSize: 14, color: 'success.main' }} />
                      )}
                    </Box>
                    {/* Recommendation % */}
                    <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                      <Box sx={{
                        minWidth: 48, height: 24, px: 1,
                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                        bgcolor: isActual ? 'primary.main' : 'rgba(255,255,255,0.1)',
                        borderRadius: 1,
                      }}>
                        <Typography variant="body2" fontWeight="bold"
                          color={isActual ? 'primary.contrastText' : 'text.primary'}
                          sx={{ lineHeight: 1, fontSize: '0.8rem' }}>
                          {move.percentage.toFixed(0)}%
                        </Typography>
                      </Box>
                    </Box>
                    {/* Score lead */}
                    <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                      <Box sx={{
                        minWidth: 50, height: 24, px: 0.75,
                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                        bgcolor: nextPlayer === 'B' ? '#1a1a1a' : '#f5f5f5',
                        color: nextPlayer === 'B' ? '#fff' : '#000',
                        borderRadius: 1,
                        border: nextPlayer === 'W' ? '1px solid #666' : 'none',
                      }}>
                        <Typography variant="body2" fontWeight="bold" sx={{ lineHeight: 1, fontSize: '0.8rem' }}>
                          {sLead >= 0 ? '+' : ''}{sLead.toFixed(1)}
                        </Typography>
                      </Box>
                    </Box>
                    {/* Winrate */}
                    <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 0.5 }}>
                      <Box sx={{
                        minWidth: 40, height: 24, px: 0.5,
                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                        bgcolor: nextPlayer === 'B' ? '#1a1a1a' : '#f5f5f5',
                        color: nextPlayer === 'B' ? '#fff' : '#000',
                        borderRadius: 1, border: '1px solid',
                        borderColor: nextPlayer === 'B' ? '#1a1a1a' : '#666',
                      }}>
                        <Typography variant="body2" fontWeight="bold" sx={{ lineHeight: 1, fontSize: '0.8rem' }}>
                          {(wr * 100).toFixed(1)}
                        </Typography>
                      </Box>
                      <Box sx={{
                        minWidth: 40, height: 24, px: 0.5,
                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                        bgcolor: nextPlayer === 'W' ? '#1a1a1a' : '#f5f5f5',
                        color: nextPlayer === 'W' ? '#fff' : '#000',
                        borderRadius: 1, border: '1px solid',
                        borderColor: nextPlayer === 'W' ? '#1a1a1a' : '#666',
                      }}>
                        <Typography variant="body2" fontWeight="bold" sx={{ lineHeight: 1, fontSize: '0.8rem' }}>
                          {(oppWr * 100).toFixed(1)}
                        </Typography>
                      </Box>
                    </Box>
                  </Box>
                );
              })}
            </Box>
          ) : (
            <Box sx={{ height: 80, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <Typography variant="body2" color="text.secondary" sx={{ textAlign: 'center' }}>
                {isAnalysisPending ? t('research:analyzing', '正在分析...') : t('research:waiting_analysis', '等待分析数据')}
              </Typography>
            </Box>
          )}
        </Box>

        <Divider />

        {/* Trend Tabs */}
        <Box sx={{ display: 'flex', flexDirection: 'column', flex: 1, minHeight: 0 }}>
          <Tabs
            value={trendTab}
            onChange={(_, v) => setTrendTab(v)}
            sx={{
              borderBottom: 1,
              borderColor: 'divider',
              minHeight: 40,
              flexShrink: 0,
              bgcolor: 'background.paper',
            }}
          >
            <Tab label={t('research:trend_chart', '走势图')} sx={{ minHeight: 40, py: 0, fontSize: '0.9rem' }} />
            <Tab label={t('research:brilliant_moves', '妙手 ({count})').replace('{count}', String(goodMoves.length))} sx={{ minHeight: 40, py: 0, fontSize: '0.9rem' }} />
            <Tab label={t('research:mistakes', '问题手 ({count})').replace('{count}', String(badMoves.length))} sx={{ minHeight: 40, py: 0, fontSize: '0.9rem' }} />
          </Tabs>

          <Box sx={{ px: 1.5, py: 1, flex: 1, overflow: 'auto' }}>
            {trendTab === 0 && (
              <Box>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5, px: 0.5 }}>
                  <Typography variant="body2" sx={{ color: '#4caf50', fontWeight: 600, fontSize: '0.875rem' }}>
                    {t('research:black_winrate', '黑方胜率: {winrate}%').replace('{winrate}', winratePercent.toFixed(1))}
                  </Typography>
                  <Typography variant="body2" sx={{ color: '#ff9800', fontWeight: 600, fontSize: '0.875rem' }}>
                    {t('research:black_lead', '黑方领先: {score} 目').replace('{score}', `${scoreLead >= 0 ? '+' : ''}${scoreLead.toFixed(1)}`)}
                  </Typography>
                </Box>
                <Box
                  sx={{ bgcolor: 'background.default', borderRadius: 1, p: 0.5, cursor: 'pointer' }}
                  onClick={handleChartClick as any}
                >
                  {renderTrendChart()}
                </Box>
              </Box>
            )}
            {trendTab === 1 && (
              <Box>
                {goodMoves.length === 0 ? (
                  <Typography variant="body2" color="text.secondary" sx={{ textAlign: 'center', py: 2 }}>
                    {t('research:no_brilliant_moves', '暂无妙手')}
                  </Typography>
                ) : (
                  goodMoves.map((m) => (
                    <Box
                      key={m.moveIndex}
                      onClick={() => onMoveChange(m.moveIndex)}
                      sx={{
                        display: 'flex', alignItems: 'center', gap: 1.5,
                        px: 1.5, py: 0.75, mb: 0.5, borderRadius: 1,
                        cursor: 'pointer',
                        bgcolor: m.moveIndex === currentMove ? 'rgba(76,175,80,0.15)' : 'transparent',
                        '&:hover': { bgcolor: 'action.hover' },
                      }}
                    >
                      <Box sx={{
                        width: 16, height: 16, borderRadius: '50%', flexShrink: 0,
                        bgcolor: m.player === 'B' ? '#1a1a1a' : '#f5f5f5',
                        border: m.player === 'W' ? '1px solid #666' : 'none',
                      }} />
                      <Typography variant="body2" sx={{ fontWeight: 600, minWidth: 60 }}>
                        {t('research:move_n', '第 {n} 手').replace('{n}', String(m.moveIndex))}
                      </Typography>
                      <Typography variant="body2" sx={{ color: '#4caf50', fontWeight: 600 }}>
                        {t('research:points', '{delta} 目').replace('{delta}', `+${m.delta.toFixed(1)}`)}
                      </Typography>
                    </Box>
                  ))
                )}
              </Box>
            )}
            {trendTab === 2 && (
              <Box>
                {badMoves.length === 0 ? (
                  <Typography variant="body2" color="text.secondary" sx={{ textAlign: 'center', py: 2 }}>
                    {t('research:no_mistakes', '暂无问题手')}
                  </Typography>
                ) : (
                  badMoves.map((m) => (
                    <Box
                      key={m.moveIndex}
                      onClick={() => onMoveChange(m.moveIndex)}
                      sx={{
                        display: 'flex', alignItems: 'center', gap: 1.5,
                        px: 1.5, py: 0.75, mb: 0.5, borderRadius: 1,
                        cursor: 'pointer',
                        bgcolor: m.moveIndex === currentMove ? 'rgba(244,67,54,0.15)' : 'transparent',
                        '&:hover': { bgcolor: 'action.hover' },
                      }}
                    >
                      <Box sx={{
                        width: 16, height: 16, borderRadius: '50%', flexShrink: 0,
                        bgcolor: m.player === 'B' ? '#1a1a1a' : '#f5f5f5',
                        border: m.player === 'W' ? '1px solid #666' : 'none',
                      }} />
                      <Typography variant="body2" sx={{ fontWeight: 600, minWidth: 60 }}>
                        {t('research:move_n', '第 {n} 手').replace('{n}', String(m.moveIndex))}
                      </Typography>
                      <Typography variant="body2" sx={{
                        color: m.delta <= MISTAKE_THRESHOLD ? '#f44336' : '#ff9800',
                        fontWeight: 600,
                      }}>
                        {t('research:points', '{delta} 目').replace('{delta}', m.delta.toFixed(1))}
                      </Typography>
                    </Box>
                  ))
                )}
              </Box>
            )}
          </Box>
        </Box>
      </Box>

      {/* Navigation Bar - pinned to bottom */}
      <Divider />
      <Box sx={{ pt: 1, pb: 1.5, px: 2, bgcolor: '#1a1a1a' }}>
        <Box sx={{ px: 1, mb: 0.5 }}>
          <Slider
            value={currentMove}
            min={0}
            max={Math.max(totalMoves, 1)}
            onChange={(_, v) => onMoveChange(v as number)}
            sx={{
              '& .MuiSlider-thumb': { width: 16, height: 16 },
              '& .MuiSlider-track': { height: 4 },
              '& .MuiSlider-rail': { height: 4 },
            }}
          />
        </Box>

        <Stack direction="row" justifyContent="center" alignItems="center" spacing={0.5}>
          <Tooltip title={t('research:first', '最初')}>
            <IconButton size="small" onClick={() => onMoveChange(0)} disabled={currentMove === 0} sx={iconButtonStyle}>
              <KeyboardDoubleArrowLeftIcon />
            </IconButton>
          </Tooltip>
          <Tooltip title={t('research:back', '后退')}>
            <IconButton size="small" onClick={() => onMoveChange(Math.max(0, currentMove - 1))} disabled={currentMove === 0} sx={iconButtonStyle}>
              <ChevronLeftIcon />
            </IconButton>
          </Tooltip>
          <IconButton
            size="medium"
            color="primary"
            onClick={() => {
              if (currentMove >= totalMoves) {
                onMoveChange(0);
              }
              setIsPlaying(!isPlaying);
            }}
            sx={{
              bgcolor: 'primary.main',
              color: 'primary.contrastText',
              '&:hover': { bgcolor: 'primary.dark' },
              mx: 0.5,
            }}
          >
            {isPlaying ? <PauseIcon /> : <PlayArrowIcon />}
          </IconButton>
          <Tooltip title={t('research:next', '前进')}>
            <IconButton size="small" onClick={() => onMoveChange(Math.min(totalMoves, currentMove + 1))} disabled={currentMove >= totalMoves} sx={iconButtonStyle}>
              <ChevronRightIcon />
            </IconButton>
          </Tooltip>
          <Tooltip title={t('research:last', '最终')}>
            <IconButton size="small" onClick={() => onMoveChange(totalMoves)} disabled={currentMove >= totalMoves} sx={iconButtonStyle}>
              <KeyboardDoubleArrowRightIcon />
            </IconButton>
          </Tooltip>
          <Typography variant="body2" color="text.secondary" sx={{ ml: 2, minWidth: 90, fontSize: '0.9rem' }}>
            {t('research:move_counter', '{current} / {total} 手').replace('{current}', String(currentMove)).replace('{total}', String(totalMoves))}
          </Typography>
        </Stack>
      </Box>
    </Box>
  );
}
