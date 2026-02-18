import { Box, Typography, Button, CircularProgress, Alert, Chip } from '@mui/material';
import { useParams, useNavigate } from 'react-router-dom';
import { ArrowBack, Undo, Lightbulb, Replay, Explore, ExploreOff } from '@mui/icons-material';
import { useTsumegoProblem } from '../../hooks/useTsumegoProblem';

const TsumegoProblemPage = () => {
  const { problemId } = useParams<{ problemId: string }>();
  const navigate = useNavigate();
  const {
    problem,
    loading,
    error,
    boardSize,
    stones,
    lastMove,
    nextPlayer,
    isSolved,
    isFailed,
    isTryMode,
    elapsedTime,
    attempts,
    showHint,
    hintCoords,
    placeStone,
    undo,
    reset,
    toggleHint,
    enterTryMode,
    exitTryMode,
  } = useTsumegoProblem(problemId || '');

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh' }}>
        <CircularProgress />
      </Box>
    );
  }

  if (error) {
    return (
      <Box sx={{ p: 2 }}>
        <Alert severity="error">{error}</Alert>
        <Button onClick={() => navigate(-1)} sx={{ mt: 1 }}>返回</Button>
      </Box>
    );
  }

  const formatTime = (seconds: number) => {
    const m = Math.floor(seconds / 60);
    const s = seconds % 60;
    return `${m}:${s.toString().padStart(2, '0')}`;
  };

  return (
    <Box sx={{ display: 'flex', height: '100vh', bgcolor: 'background.default' }}>
      {/* Board area */}
      <Box
        sx={{ height: '100%', aspectRatio: '1', position: 'relative', bgcolor: '#c8a456' }}
        data-testid="tsumego-board"
      >
        {/* Simplified board rendering: stones are displayed as indicators */}
        <Box sx={{ p: 2, height: '100%', display: 'flex', flexDirection: 'column', justifyContent: 'center', alignItems: 'center' }}>
          <Typography variant="body2" sx={{ color: 'rgba(0,0,0,0.6)' }}>
            {boardSize}x{boardSize} - {stones.length} stones
          </Typography>
          {lastMove && (
            <Typography variant="caption" sx={{ color: 'rgba(0,0,0,0.5)' }}>
              Last: ({lastMove[0]}, {lastMove[1]})
            </Typography>
          )}
          {showHint && hintCoords && (
            <Typography variant="caption" data-testid="hint-marker" sx={{ color: '#1976d2', fontWeight: 600 }}>
              Hint: ({hintCoords[0]}, {hintCoords[1]})
            </Typography>
          )}
          <Typography variant="caption" sx={{ mt: 1, color: 'rgba(0,0,0,0.5)' }}>
            {nextPlayer === 'B' ? '黑' : '白'}先
          </Typography>
        </Box>
      </Box>

      {/* Controls panel */}
      <Box sx={{ flex: 1, p: 2, display: 'flex', flexDirection: 'column', overflow: 'auto' }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
          <Button onClick={() => navigate(-1)} startIcon={<ArrowBack />} sx={{ minWidth: 40, p: 0.5 }} />
          <Box>
            <Typography variant="h6">{problem?.category || '死活题'}</Typography>
            {problem?.level && (
              <Chip label={problem.level.toUpperCase()} size="small" sx={{ mt: 0.5 }} />
            )}
          </Box>
        </Box>

        {problem?.hint && (
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>{problem.hint}</Typography>
        )}

        {/* Status indicators */}
        {isSolved && (
          <Alert severity="success" sx={{ mb: 2 }}>正确!</Alert>
        )}
        {isFailed && !isTryMode && (
          <Alert severity="error" sx={{ mb: 2 }}>不正确，请重试</Alert>
        )}
        {isTryMode && (
          <Alert severity="info" sx={{ mb: 2 }}>试下模式 - 自由探索</Alert>
        )}

        {/* Timer and attempts */}
        <Box sx={{ display: 'flex', gap: 2, mb: 2 }}>
          <Typography variant="body2" color="text.secondary" data-testid="timer">
            用时: {formatTime(elapsedTime)}
          </Typography>
          <Typography variant="body2" color="text.secondary" data-testid="attempts">
            尝试: {attempts}
          </Typography>
        </Box>

        {/* Action buttons */}
        <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
          <Button variant="outlined" startIcon={<Undo />} onClick={undo}>悔棋</Button>
          <Button variant="outlined" startIcon={<Replay />} onClick={reset}>重置</Button>
          <Button variant="outlined" startIcon={<Lightbulb />} onClick={toggleHint}>
            {showHint ? '隐藏提示' : '提示'}
          </Button>
          {!isTryMode ? (
            <Button variant="outlined" startIcon={<Explore />} onClick={enterTryMode}>试下</Button>
          ) : (
            <Button variant="outlined" startIcon={<ExploreOff />} onClick={exitTryMode}>退出试下</Button>
          )}
        </Box>
      </Box>
    </Box>
  );
};

export default TsumegoProblemPage;
