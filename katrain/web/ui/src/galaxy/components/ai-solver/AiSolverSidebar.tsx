import { Box, Typography, Button, ToggleButton, ToggleButtonGroup, Select, MenuItem, Alert, CircularProgress } from '@mui/material';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import AiSolverToolbar from './AiSolverToolbar';
import type { AnalysisDepth, UseAiSolverBoardReturn } from '../../hooks/useAiSolverBoard';
import type { AiMoveMarker } from '../live/LiveBoard';

interface AiSolverSidebarProps {
  board: UseAiSolverBoardReturn;
  onRegionClear: () => void;
  parsedMarkers: AiMoveMarker[] | null;
  pvText: string | null;
  onHoverPV: (pv: string[] | null) => void;
}

const DEPTH_LABELS: Record<AnalysisDepth, string> = {
  quick: '快速',
  standard: '标准',
  deep: '深入',
};

export default function AiSolverSidebar({
  board,
  onRegionClear,
  parsedMarkers,
  pvText,
  onHoverPV,
}: AiSolverSidebarProps) {
  const effectiveRegion = board.getEffectiveRegion();

  return (
    <Box sx={{
      width: 380,
      minWidth: 380,
      borderLeft: '1px solid rgba(255,255,255,0.05)',
      bgcolor: '#141414',
      display: 'flex',
      flexDirection: 'column',
      overflow: 'auto',
    }}>
      {/* Header */}
      <Box sx={{ p: 2, pb: 1 }}>
        <Typography variant="h6" sx={{ fontWeight: 700, color: 'text.primary' }}>
          AI解题
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
          摆放棋子后点击开始解题
        </Typography>
      </Box>

      {/* Player to move */}
      <Box sx={{ px: 2, py: 1 }}>
        <Typography variant="caption" color="text.secondary" sx={{ mb: 0.5, display: 'block' }}>
          先手
        </Typography>
        <ToggleButtonGroup
          value={board.playerToMove}
          exclusive
          onChange={(_, val) => val && board.setPlayerToMove(val)}
          size="small"
          fullWidth
        >
          <ToggleButton value="B" sx={{ textTransform: 'none', fontSize: '0.85rem' }}>
            黑先
          </ToggleButton>
          <ToggleButton value="W" sx={{ textTransform: 'none', fontSize: '0.85rem' }}>
            白先
          </ToggleButton>
        </ToggleButtonGroup>
      </Box>

      {/* Toolbar */}
      <Box sx={{ px: 2, py: 1 }}>
        <AiSolverToolbar
          activeTool={board.activeTool}
          onToolChange={board.setActiveTool}
          onClear={board.handleClear}
        />
      </Box>

      {/* Board size */}
      <Box sx={{ px: 2, py: 1 }}>
        <Typography variant="caption" color="text.secondary" sx={{ mb: 0.5, display: 'block' }}>
          棋盘大小
        </Typography>
        <Select
          value={board.boardSize}
          onChange={(e) => {
            board.setBoardSize(Number(e.target.value));
            board.handleClear();
          }}
          size="small"
          fullWidth
          sx={{ fontSize: '0.85rem' }}
        >
          <MenuItem value={9}>9 x 9</MenuItem>
          <MenuItem value={13}>13 x 13</MenuItem>
          <MenuItem value={19}>19 x 19</MenuItem>
        </Select>
      </Box>

      {/* Analysis depth */}
      <Box sx={{ px: 2, py: 1 }}>
        <Typography variant="caption" color="text.secondary" sx={{ mb: 0.5, display: 'block' }}>
          分析深度
        </Typography>
        <ToggleButtonGroup
          value={board.analysisDepth}
          exclusive
          onChange={(_, val) => val && board.setAnalysisDepth(val)}
          size="small"
          fullWidth
        >
          {(['quick', 'standard', 'deep'] as AnalysisDepth[]).map((d) => (
            <ToggleButton key={d} value={d} sx={{ textTransform: 'none', fontSize: '0.85rem' }}>
              {DEPTH_LABELS[d]}
            </ToggleButton>
          ))}
        </ToggleButtonGroup>
      </Box>

      {/* Region info */}
      <Box sx={{ px: 2, py: 1 }}>
        <Typography variant="caption" color="text.secondary" sx={{ mb: 0.5, display: 'block' }}>
          分析区域
        </Typography>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <Typography variant="body2" color="text.secondary" sx={{ fontFamily: '"IBM Plex Mono", monospace', fontSize: '0.8rem' }}>
            {effectiveRegion
              ? `(${effectiveRegion.x1},${effectiveRegion.y1}) → (${effectiveRegion.x2},${effectiveRegion.y2})`
              : '无 (请摆放棋子)'}
            {!board.region && effectiveRegion && ' [自动]'}
            {board.region && ' [手动]'}
          </Typography>
          {board.region && (
            <Button size="small" variant="text" onClick={onRegionClear} sx={{ textTransform: 'none', fontSize: '0.75rem', minWidth: 0 }}>
              清除
            </Button>
          )}
        </Box>
      </Box>

      {/* Analysis results */}
      {parsedMarkers && parsedMarkers.length > 0 && (
        <Box sx={{ px: 2, py: 1 }}>
          <Typography variant="caption" color="text.secondary" sx={{ mb: 0.5, display: 'block' }}>
            分析结果
          </Typography>
          {parsedMarkers.map((m, idx) => (
            <Box
              key={m.move}
              onMouseEnter={() => {
                // Show PV for this move if available from raw result
                const result = board.analysisResult;
                const turnResult = result?.turnInfos?.[0] ?? result;
                const moveInfo = turnResult?.moveInfos?.[idx];
                if (moveInfo?.pv) {
                  onHoverPV(moveInfo.pv);
                }
              }}
              onMouseLeave={() => onHoverPV(null)}
              sx={{
                display: 'flex',
                alignItems: 'center',
                gap: 1.5,
                py: 0.5,
                px: 1,
                borderRadius: 1,
                cursor: 'pointer',
                '&:hover': { bgcolor: 'rgba(255,255,255,0.05)' },
              }}
            >
              <Typography
                variant="body2"
                sx={{
                  fontWeight: idx === 0 ? 700 : 400,
                  color: idx === 0 ? 'primary.main' : 'text.primary',
                  fontFamily: '"IBM Plex Mono", monospace',
                  minWidth: 30,
                }}
              >
                {m.move}
              </Typography>
              <Typography variant="caption" color="text.secondary" sx={{ fontFamily: '"IBM Plex Mono", monospace' }}>
                胜率 {(m.winrate * 100).toFixed(1)}%
              </Typography>
              <Typography variant="caption" color="text.secondary" sx={{ fontFamily: '"IBM Plex Mono", monospace' }}>
                {m.visits >= 1000 ? `${(m.visits / 1000).toFixed(1)}k` : m.visits} 次
              </Typography>
            </Box>
          ))}
        </Box>
      )}

      {/* PV text display */}
      {pvText && (
        <Box sx={{ px: 2, py: 1 }}>
          <Typography variant="caption" color="text.secondary" sx={{ mb: 0.5, display: 'block' }}>
            最佳变化
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{
            fontFamily: '"IBM Plex Mono", monospace',
            fontSize: '0.8rem',
            lineHeight: 1.6,
            wordBreak: 'break-all',
          }}>
            {pvText}
          </Typography>
        </Box>
      )}

      {/* Error display */}
      {board.analysisError && (
        <Box sx={{ px: 2, py: 1 }}>
          <Alert
            severity="error"
            onClose={() => {}}
            sx={{ fontSize: '0.8rem' }}
            action={
              <Button size="small" color="inherit" onClick={board.startAnalysis} sx={{ textTransform: 'none' }}>
                重试
              </Button>
            }
          >
            {board.analysisError}
          </Alert>
        </Box>
      )}

      {/* Spacer */}
      <Box sx={{ flexGrow: 1 }} />

      {/* Analyze button */}
      <Box sx={{ p: 2 }}>
        <Button
          variant="contained"
          color="success"
          fullWidth
          size="large"
          startIcon={board.isAnalyzing ? <CircularProgress size={18} color="inherit" /> : <PlayArrowIcon />}
          disabled={board.isAnalyzing || board.stones.length === 0}
          onClick={board.startAnalysis}
          sx={{
            textTransform: 'none',
            fontWeight: 700,
            fontSize: '1rem',
            py: 1.5,
          }}
        >
          {board.isAnalyzing ? '分析中...' : '开始解题'}
        </Button>
      </Box>
    </Box>
  );
}
