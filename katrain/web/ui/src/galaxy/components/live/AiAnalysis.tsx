import { Box, Typography, IconButton, Button, Tooltip } from '@mui/material';
import RefreshIcon from '@mui/icons-material/Refresh';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import type { MoveAnalysis, TopMove } from '../../types/live';
import { LiveAPI } from '../../api/live';
import { useState, useMemo } from 'react';
import { i18n } from '../../../i18n';

interface AiAnalysisProps {
  matchId: string;
  currentMove: number;
  analysis: Record<number, MoveAnalysis>;
  onMoveHover?: (pv: string[] | null) => void;
  topN?: number;  // Number of top moves to display (default 3)
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
  matchId,
  currentMove,
  analysis,
  onMoveHover,
  topN = 3,
}: AiAnalysisProps) {
  const [requesting, setRequesting] = useState(false);
  const [requestError, setRequestError] = useState<string | null>(null);

  const currentAnalysis = analysis[currentMove];

  const handleRequestAnalysis = async () => {
    setRequesting(true);
    setRequestError(null);
    try {
      await LiveAPI.requestAnalysis(matchId, Math.max(0, currentMove - 5), currentMove);
    } catch (err) {
      setRequestError(err instanceof Error ? err.message : 'Request failed');
    } finally {
      setRequesting(false);
    }
  };

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

  if (!currentAnalysis) {
    return (
      <Box sx={{ p: 2 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 2 }}>
          <Typography variant="subtitle2">{i18n.t('live:ai_recommendations', 'AI Recommendations')}</Typography>
          <Tooltip title={i18n.t('live:request_analysis', 'Request analysis')}>
            <IconButton size="small" onClick={handleRequestAnalysis} disabled={requesting}>
              <RefreshIcon fontSize="small" />
            </IconButton>
          </Tooltip>
        </Box>
        <Typography variant="body2" color="text.secondary" sx={{ textAlign: 'center', py: 2 }}>
          {requesting ? i18n.t('live:requesting_analysis', 'Requesting analysis...') : i18n.t('live:no_analysis', 'No analysis data')}
        </Typography>
        {requestError && (
          <Typography variant="caption" color="error" sx={{ display: 'block', textAlign: 'center' }}>
            {requestError}
          </Typography>
        )}
        {!requesting && (
          <Button
            size="small"
            variant="outlined"
            fullWidth
            onClick={handleRequestAnalysis}
            sx={{ mt: 1 }}
          >
            {i18n.t('live:request_analysis', 'Request analysis')}
          </Button>
        )}
      </Box>
    );
  }

  return (
    <Box sx={{ p: 2 }}>
      {/* Header */}
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 1.5 }}>
        <Typography variant="subtitle2">{i18n.t('live:ai_recommendations', 'AI Recommendations')}</Typography>
        <Typography variant="caption" color="text.secondary">
          {i18n.t('live:after_move', 'After move')} {currentMove}
        </Typography>
      </Box>

      {/* Column headers like XingZhen */}
      <Box
        sx={{
          display: 'grid',
          gridTemplateColumns: '80px 1fr 70px 100px',
          gap: 1,
          mb: 1,
          px: 1,
          py: 0.5,
          bgcolor: 'rgba(255,255,255,0.05)',
          borderRadius: 1,
        }}
      >
        <Typography variant="caption" color="text.secondary">{i18n.t('live:suggested_move', 'Move')}</Typography>
        <Typography variant="caption" color="text.secondary" sx={{ textAlign: 'center' }}>{i18n.t('live:recommendation', 'Score')}</Typography>
        <Typography variant="caption" color="text.secondary" sx={{ textAlign: 'center' }}>{i18n.t('live:lead_pts', 'Lead')}</Typography>
        <Typography variant="caption" color="text.secondary" sx={{ textAlign: 'center' }}>{i18n.t('live:winrate', 'Winrate')}</Typography>
      </Box>

      {/* Move rows */}
      <Box>
        {displayMoves.map((move, index) => (
          <MoveRow
            key={move.move}
            move={move}
            rank={index + 1}
            percentage={move.percentage}
            isActualMove={move.isActualMove || false}
            nextPlayer={nextPlayer}
            onHover={(hovering) => {
              if (onMoveHover) {
                onMoveHover(hovering ? move.pv : null);
              }
            }}
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
}

function MoveRow({ move, rank, percentage, isActualMove, nextPlayer, onHover }: MoveRowProps) {
  // Score lead from next player's perspective (who these recommendations are for)
  // KataGo reports score_lead from Black's perspective (positive = Black ahead)
  // If next player is White, we negate it
  const scoreLead = nextPlayer === 'B' ? move.score_lead : -move.score_lead;

  // Winrate from next player's perspective
  const winrate = nextPlayer === 'B' ? move.winrate : 1 - move.winrate;
  const opponentWinrate = 1 - winrate;

  return (
    <Box
      sx={{
        display: 'grid',
        gridTemplateColumns: '80px 1fr 70px 100px',
        gap: 1,
        p: 1,
        mb: 0.5,
        borderRadius: 1,
        cursor: 'pointer',
        transition: 'background-color 0.15s',
        bgcolor: isActualMove ? 'rgba(76, 175, 80, 0.15)' : 'transparent',
        border: isActualMove ? '1px solid' : '1px solid transparent',
        borderColor: isActualMove ? 'success.main' : 'transparent',
        '&:hover': { bgcolor: 'action.hover' },
      }}
      onMouseEnter={() => onHover?.(true)}
      onMouseLeave={() => onHover?.(false)}
    >
      {/* Move position with stone color indicator */}
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
        <StoneIndicator color={nextPlayer} size={14} />
        <Typography variant="body2" fontWeight="bold">
          {move.move}
        </Typography>
        {isActualMove && (
          <Tooltip title={i18n.t('live:actual_move', 'Actual move played')}>
            <CheckCircleIcon sx={{ fontSize: 14, color: 'success.main' }} />
          </Tooltip>
        )}
      </Box>

      {/* Recommendation percentage (推荐度) */}
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <Box
          sx={{
            minWidth: 45,
            px: 1,
            py: 0.25,
            bgcolor: rank === 1 ? 'primary.main' : 'rgba(255,255,255,0.1)',
            borderRadius: 1,
            textAlign: 'center',
          }}
        >
          <Typography
            variant="caption"
            fontWeight="bold"
            color={rank === 1 ? 'primary.contrastText' : 'text.primary'}
          >
            {percentage.toFixed(0)}%
          </Typography>
        </Box>
      </Box>

      {/* Score lead (领先目数) - on colored background based on current player */}
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <Box
          sx={{
            minWidth: 50,
            px: 1,
            py: 0.25,
            bgcolor: nextPlayer === 'B' ? '#1a1a1a' : '#f5f5f5',
            color: nextPlayer === 'B' ? '#fff' : '#000',
            borderRadius: 1,
            textAlign: 'center',
            border: nextPlayer === 'W' ? '1px solid #666' : 'none',
          }}
        >
          <Typography variant="caption" fontWeight="medium">
            {scoreLead >= 0 ? '+' : ''}{scoreLead.toFixed(1)}
          </Typography>
        </Box>
      </Box>

      {/* Winrate (胜率%) - show both players */}
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 0.5 }}>
        {/* Current player winrate - on colored background */}
        <Box
          sx={{
            minWidth: 38,
            px: 0.5,
            py: 0.25,
            bgcolor: nextPlayer === 'B' ? '#1a1a1a' : '#f5f5f5',
            color: nextPlayer === 'B' ? '#fff' : '#000',
            borderRadius: 1,
            textAlign: 'center',
            border: nextPlayer === 'W' ? '1px solid #666' : 'none',
          }}
        >
          <Typography variant="caption" fontWeight="bold">
            {(winrate * 100).toFixed(1)}
          </Typography>
        </Box>
        {/* Opponent winrate - on opposite colored background */}
        <Box
          sx={{
            minWidth: 38,
            px: 0.5,
            py: 0.25,
            bgcolor: nextPlayer === 'W' ? '#1a1a1a' : '#f5f5f5',
            color: nextPlayer === 'W' ? '#fff' : '#000',
            borderRadius: 1,
            textAlign: 'center',
            border: nextPlayer === 'B' ? '1px solid #666' : 'none',
          }}
        >
          <Typography variant="caption" fontWeight="bold">
            {(opponentWinrate * 100).toFixed(1)}
          </Typography>
        </Box>
      </Box>
    </Box>
  );
}
