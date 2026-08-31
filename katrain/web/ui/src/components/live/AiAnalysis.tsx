import { Box, Typography, Tooltip } from '@mui/material';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import type { MoveAnalysis, TopMove } from '../../types/live';
import { useMemo } from 'react';
import { useTranslation } from '../../hooks/useTranslation';
import {
  dominantProfile,
  formatHumanPickRate,
  humanPickBarRatio,
  rankLabel,
} from '../../features/analysis/humanTendency';

/**
 * 五列的宽度。用 minmax() 钉死每列的**内容下限**，而不是给纯 fr 权重 ——
 * 纯权重下「5段选择率」这个表头会被压到 41px 然后省略号截断（真浏览器量过）。
 * 下限之和 288px，右栏实测可用宽 293px，正好装得下且不横向溢出。
 */
const HUMAN_GRID =
  'minmax(58px, 1.1fr) minmax(46px, 0.8fr) minmax(56px, 0.95fr) minmax(48px, 0.85fr) minmax(80px, 1.3fr)';

interface AiAnalysisProps {
  currentMove: number;
  analysis: Record<number, MoveAnalysis>;
  onMoveHover?: (pv: string[] | null) => void;
  topN?: number;  // Number of top moves to display (default 3)
  // Touch (kiosk) variant: tap a row to toggle its variation. The parent owns
  // the active move (and derives the PV) so navigation auto-resets it. Galaxy
  // uses onMoveHover (mouse) instead and leaves these undefined.
  onMoveSelect?: (moveKey: string | null) => void;
  activeMove?: string | null;
}

// Stone color indicator component
function StoneIndicator({ color, size = 16 }: { color: 'B' | 'W'; size?: number }) {
  return (
    <Box
      sx={{
        width: size,
        height: size,
        borderRadius: '50%',
        bgcolor: color === 'B' ? '#1a1a1a' : '#f5f5f5',
        border: color === 'W' ? '1px solid #666' : 'none',
        flexShrink: 0,
      }}
    />
  );
}

export default function AiAnalysis({
  currentMove,
  analysis,
  onMoveHover,
  topN = 3,  // Show top 3 + actual move if not in top 3
  onMoveSelect,
  activeMove = null,
}: AiAnalysisProps) {
  const { t } = useTranslation();
  const currentAnalysis = analysis[currentMove];

  // Determine who plays next (not who just moved)
  // At move 0 (empty board), Black plays next
  // At move N, the next player is Black if N is even, White if N is odd
  const nextPlayer: 'B' | 'W' = currentMove % 2 === 0 ? 'B' : 'W';

  // Build the display list with proper percentage calculation
  // Note: actual move comes from the NEXT position's analysis record
  // because analysis[N].actual_move is the move that LED to position N (move N)
  // but we want to show what move N+1 was (the move from this position)
  const nextAnalysis = analysis[currentMove + 1];

  const displayMoves = useMemo(() => {
    if (!currentAnalysis || !currentAnalysis.top_moves || currentAnalysis.top_moves.length === 0) {
      return [];
    }

    const topMoves = currentAnalysis.top_moves.slice(0, topN);
    // Get the actual move from the next position's analysis (what was actually played from here)
    const actualMove = nextAnalysis?.move;

    // Check if actual move is in top N
    const actualMoveInTop = actualMove ? topMoves.findIndex(m => m.move === actualMove) : -1;

    let movesToShow: (TopMove & { isActualMove?: boolean; actualMoveVisits?: number })[] = [];

    if (actualMoveInTop >= 0 || !actualMove) {
      // Actual move is in top N or no actual move - show top N only
      movesToShow = topMoves.map((m) => ({
        ...m,
        isActualMove: actualMove === m.move,
      }));
    } else {
      // Actual move is NOT in top N - show top N + actual move
      // Find actual move in all top_moves
      const actualMoveData = currentAnalysis.top_moves.find(m => m.move === actualMove);
      movesToShow = topMoves.map(m => ({
        ...m,
        isActualMove: false,
      }));

      // Add actual move with potentially 0 visits
      if (actualMoveData) {
        movesToShow.push({
          ...actualMoveData,
          isActualMove: true,
        });
      } else {
        // Actual move not even in analysis - create placeholder
        movesToShow.push({
          move: actualMove,
          visits: 0,
          winrate: currentAnalysis.winrate,
          score_lead: currentAnalysis.score_lead,
          prior: 0,
          pv: [],
          psv: 0,  // No psv data for move not in analysis
          isActualMove: true,
          actualMoveVisits: 0,
        });
      }
    }

    // Calculate percentage based on playSelectionValue (psv)
    // psv is KataGo's composite ranking metric, more meaningful than visits
    const totalPsv = movesToShow.reduce((sum, m) => sum + (m.psv || 0), 0);
    const totalVisits = movesToShow.reduce((sum, m) => sum + m.visits, 0);

    // Use psv for percentage if available, fall back to visits for legacy data
    const usePsv = totalPsv > 0;
    return movesToShow.map(m => ({
      ...m,
      percentage: usePsv
        ? ((m.psv || 0) / totalPsv) * 100
        : (totalVisits > 0 ? (m.visits / totalVisits) * 100 : 0),
    }));
  }, [currentAnalysis, nextAnalysis, topN]);

  // 表头要说清「这是谁的选择率」。档位来自数据本身（每个候选点都带 human_profile），
  // 不是前端写死的常量 —— 服务端换档之后，老报告的数字仍然自证是按哪一档算的。
  const humanProfile = dominantProfile(displayMoves);
  const humanRank = rankLabel(humanProfile);
  const humanHeader = humanRank
    ? t('live:human_pick_rate_ranked', '{rank}选择率').replace('{rank}', humanRank)
    : t('live:human_pick_rate', '人类选择率');
  const humanHeaderHint = humanRank
    ? t(
        'live:human_pick_rate_hint_ranked',
        '每 100 位 {rank} 棋手里大约有几位会下这一点。这是「多少人会下」，不是「该不该下」。',
      ).replace('{rank}', humanRank)
    : t('live:human_pick_rate_hint', '这一列显示人类棋手会下这一点的比例，与 AI 的推荐顺位无关。');

  if (!currentAnalysis) {
    return (
      <Box sx={{ px: 1.5, py: 1 }}>
        <Typography variant="subtitle2" sx={{ mb: 1, fontSize: '0.8rem' }}>
          {t('live:ai_recommendations', 'AI Recommendations')}
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ textAlign: 'center', py: 1.5 }}>
          {t('live:analysis_pending', 'Analysis pending...')}
        </Typography>
        <Typography variant="caption" color="text.secondary" sx={{ display: 'block', textAlign: 'center' }}>
          {t('live:analysis_auto_processed', 'Analysis is automatically processed in the background')}
        </Typography>
      </Box>
    );
  }

  return (
    <Box sx={{ px: 1.5, py: 1 }}>
      {/* Header */}
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 0.5 }}>
        <Typography variant="subtitle2" sx={{ fontSize: '0.8rem' }}>{t('live:ai_recommendations', 'AI Recommendations')}</Typography>
        <Typography variant="caption" color="text.secondary">
          {t('live:after_move', 'After move')} {currentMove}
        </Typography>
      </Box>

      {/* Column headers */}
      <Box
        sx={{
          display: 'grid',
          gridTemplateColumns: HUMAN_GRID,
          gap: 0.5,
          mb: 0.25,
          px: 1,
          py: 0.25,
          bgcolor: 'rgba(255,255,255,0.05)',
          borderRadius: 1,
        }}
      >
        <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.8rem' }}>{t('live:suggested_move', 'Move')}</Typography>
        <Typography variant="caption" color="text.secondary" sx={{ textAlign: 'center', fontSize: '0.7rem' }}>{t('live:recommendation', 'Score')}</Typography>
        <Tooltip title={humanHeaderHint}>
          <Typography
            variant="caption"
            color="text.secondary"
            noWrap
            sx={{ textAlign: 'center', fontSize: '0.7rem', cursor: 'help' }}
          >
            {humanHeader}
          </Typography>
        </Tooltip>
        <Typography variant="caption" color="text.secondary" sx={{ textAlign: 'center', fontSize: '0.7rem' }}>{t('live:lead_pts', 'Lead')}</Typography>
        <Typography variant="caption" color="text.secondary" sx={{ textAlign: 'center', fontSize: '0.7rem' }}>{t('live:winrate', 'Winrate')}</Typography>
      </Box>

      {/* Move rows */}
      <Box sx={{ height: 150, overflowY: 'auto' }}>
        {displayMoves.map((move, index) => (
          <MoveRow
            key={move.move}
            move={move}
            rank={index + 1}
            percentage={move.percentage}
            isActualMove={move.isActualMove || false}
            nextPlayer={nextPlayer}
            onHover={onMoveHover ? (hovering) => onMoveHover(hovering ? move.pv : null) : undefined}
            isSelected={move.move === activeMove}
            onSelect={onMoveSelect ? () => onMoveSelect(move.move === activeMove ? null : move.move) : undefined}
          />
        ))}
      </Box>
    </Box>
  );
}

interface MoveRowProps {
  move: TopMove;
  rank: number;
  percentage: number;
  isActualMove: boolean;
  nextPlayer: 'B' | 'W';
  onHover?: (hovering: boolean) => void;
  isSelected?: boolean;       // touch variant: this row's variation is active
  onSelect?: () => void;      // touch variant: tap to toggle the variation
}

function MoveRow({ move, rank, percentage, isActualMove, nextPlayer, onHover, isSelected = false, onSelect }: MoveRowProps) {
  const { t } = useTranslation();
  // Score lead from next player's perspective (who these recommendations are for)
  // KataGo reports score_lead from Black's perspective (positive = Black ahead)
  // If next player is White, we negate it
  const rawScoreLead = move.score_lead ?? 0;
  const scoreLead = nextPlayer === 'B' ? rawScoreLead : -rawScoreLead;

  // Winrate from next player's perspective
  const rawWinrate = move.winrate ?? 0.5;
  const winrate = nextPlayer === 'B' ? rawWinrate : 1 - rawWinrate;
  const opponentWinrate = 1 - winrate;

  return (
    <Box
      sx={{
        display: 'grid',
        gridTemplateColumns: HUMAN_GRID,
        gap: 0.5,
        py: 0.5,
        px: 1,
        minHeight: onSelect ? 48 : undefined,
        mb: 0.25,
        borderRadius: 1,
        cursor: onSelect || onHover ? 'pointer' : 'default',
        transition: 'background-color 0.15s',
        bgcolor: isSelected ? 'action.selected' : isActualMove ? 'rgba(76, 175, 80, 0.15)' : 'transparent',
        border: isSelected || isActualMove ? '1px solid' : '1px solid transparent',
        borderColor: isSelected ? 'primary.main' : isActualMove ? 'success.main' : 'transparent',
        '&:hover': { bgcolor: 'action.hover' },
      }}
      onMouseEnter={() => onHover?.(true)}
      onMouseLeave={() => onHover?.(false)}
      onClick={onSelect}
      role={onSelect ? 'button' : undefined}
      tabIndex={onSelect ? 0 : undefined}
      aria-label={onSelect ? `${t('live:preview_variation', '预览变化')} ${move.move}` : undefined}
      aria-pressed={onSelect ? isSelected : undefined}
      onKeyDown={onSelect ? (event) => {
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault();
          onSelect();
        }
      } : undefined}
    >
      {/* Move position with stone color indicator */}
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75 }}>
        <StoneIndicator color={nextPlayer} size={14} />
        <Typography variant="body2" fontWeight="bold" sx={{ fontSize: '0.85rem' }}>
          {move.move}
        </Typography>
        {isActualMove && (
          <Tooltip title={t('live:actual_move', 'Actual move played')}>
            <CheckCircleIcon sx={{ fontSize: 14, color: 'success.main' }} />
          </Tooltip>
        )}
      </Box>

      {/* Recommendation percentage (推荐度) */}
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <Box
          sx={{
            minWidth: 48,
            height: 24,
            px: 1,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            bgcolor: rank === 1 ? 'primary.main' : 'rgba(255,255,255,0.1)',
            borderRadius: 1,
            boxSizing: 'border-box',
          }}
        >
          <Typography
            variant="body2"
            fontWeight="bold"
            color={rank === 1 ? 'primary.contrastText' : 'text.primary'}
            sx={{ lineHeight: 1, fontSize: '0.8rem' }}
          >
            {percentage.toFixed(0)}%
          </Typography>
        </Box>
      </Box>

      {/* 人类倾向（每 100 人里 N 人）。刻意不用百分号：同一行里「推荐度」已经是百分比，
          两列都印 % 会被扫读成一对；差异放在字形层，不依赖颜色。
          微条是**绝对刻度**（0-100 人），不随同屏其它行归一化。 */}
      <Box
        sx={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          gap: 0.25,
          minWidth: 0,
        }}
      >
        <Typography
          variant="body2"
          fontWeight="bold"
          noWrap
          sx={{
            lineHeight: 1,
            fontSize: '0.8rem',
            fontVariantNumeric: 'tabular-nums',
            color: move.human_prior == null ? 'text.disabled' : 'text.primary',
          }}
        >
          {formatHumanPickRate(move.human_prior)}
        </Typography>
        {/* 没有数据就不画条 —— 空轨道本身就是诚实的表达，画个 0 宽条反而像「有数据但是 0」。 */}
        {move.human_prior != null && (
          <Box sx={{ width: '100%', maxWidth: 44, height: 3, bgcolor: 'action.hover', borderRadius: 2 }}>
            <Box
              sx={{
                width: `${humanPickBarRatio(move.human_prior) * 100}%`,
                height: '100%',
                bgcolor: 'info.main',
                borderRadius: 2,
              }}
            />
          </Box>
        )}
      </Box>

      {/* Score lead (领先目数) - on colored background based on current player */}
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <Box
          sx={{
            minWidth: 50,
            height: 24,
            px: 0.75,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            bgcolor: nextPlayer === 'B' ? '#1a1a1a' : '#f5f5f5',
            color: nextPlayer === 'B' ? '#fff' : '#000',
            borderRadius: 1,
            border: nextPlayer === 'W' ? '1px solid #666' : 'none',
            boxSizing: 'border-box',
          }}
        >
          <Typography variant="body2" fontWeight="bold" sx={{ lineHeight: 1, fontSize: '0.8rem' }}>
            {scoreLead >= 0 ? '+' : ''}{scoreLead.toFixed(1)}
          </Typography>
        </Box>
      </Box>

      {/* Winrate (胜率%) - show both players */}
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 0.5 }}>
        {/* Current player winrate - on colored background */}
        <Box
          sx={{
            minWidth: 36,
            height: 24,
            px: 0.5,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            bgcolor: nextPlayer === 'B' ? '#1a1a1a' : '#f5f5f5',
            color: nextPlayer === 'B' ? '#fff' : '#000',
            borderRadius: 1,
            border: '1px solid',
            borderColor: nextPlayer === 'B' ? '#1a1a1a' : '#666',
            boxSizing: 'border-box',
          }}
        >
          <Typography variant="body2" fontWeight="bold" sx={{ lineHeight: 1, fontSize: '0.8rem' }}>
            {(winrate * 100).toFixed(1)}
          </Typography>
        </Box>
        {/* Opponent winrate - on opposite colored background */}
        <Box
          sx={{
            minWidth: 36,
            height: 24,
            px: 0.5,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            bgcolor: nextPlayer === 'W' ? '#1a1a1a' : '#f5f5f5',
            color: nextPlayer === 'W' ? '#fff' : '#000',
            borderRadius: 1,
            border: '1px solid',
            borderColor: nextPlayer === 'W' ? '#1a1a1a' : '#666',
            boxSizing: 'border-box',
          }}
        >
          <Typography variant="body2" fontWeight="bold" sx={{ lineHeight: 1, fontSize: '0.8rem' }}>
            {(opponentWinrate * 100).toFixed(1)}
          </Typography>
        </Box>
      </Box>
    </Box>
  );
}
