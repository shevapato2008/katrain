import { Box, Typography, Button, CircularProgress, Alert, Chip } from '@mui/material';
import { useParams, useNavigate } from 'react-router-dom';
import { ArrowBack, Undo, Lightbulb, Replay, Explore, ExploreOff } from '@mui/icons-material';
import { useTsumegoProblem } from '../../hooks/useTsumegoProblem';
import { useTranslation } from '../../hooks/useTranslation';
import { useSound } from '../../hooks/useSound';
import TsumegoBoard from '../../components/tsumego/TsumegoBoard';

const TsumegoProblemPage = () => {
  const { problemId } = useParams<{ problemId: string }>();
  const navigate = useNavigate();
  const { t } = useTranslation();
  const { play: playSound } = useSound();
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
    moveHistory,
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
        <Button onClick={() => navigate(-1)} sx={{ mt: 1 }}>{t('Back', '返回')}</Button>
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
      <Box sx={{ height: '100%', aspectRatio: '1' }} data-testid="tsumego-board">
        <TsumegoBoard
          boardSize={boardSize}
          stones={stones}
          lastMove={lastMove}
          hintCoords={hintCoords}
          showHint={showHint}
          disabled={isSolved || (isFailed && !isTryMode)}
          moveHistory={moveHistory}
          onPlaceStone={(x, y) => {
            const result = placeStone(x, y);
            if (result) playSound('stone');
          }}
        />
      </Box>

      {/* Controls panel */}
      <Box sx={{ flex: 1, p: 2, display: 'flex', flexDirection: 'column', overflow: 'auto' }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
          <Button onClick={() => navigate(-1)} startIcon={<ArrowBack />} sx={{ minWidth: 40, p: 0.5 }} />
          <Box>
            <Typography variant="h6">{problem?.category || t('Tsumego', '死活题')}</Typography>
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
          <Alert severity="success" sx={{ mb: 2 }}>{t('Correct!', '正确!')}</Alert>
        )}
        {isFailed && !isTryMode && (
          <Alert severity="error" sx={{ mb: 2 }}>{t('Incorrect, try again', '不正确，请重试')}</Alert>
        )}
        {isTryMode && (
          <Alert severity="info" sx={{ mb: 2 }}>{t('Try mode - free exploration', '试下模式 - 自由探索')}</Alert>
        )}

        {/* Timer and attempts */}
        <Box sx={{ display: 'flex', gap: 2, mb: 2 }}>
          <Typography variant="body2" color="text.secondary" data-testid="timer">
            {t('Time', '用时')}: {formatTime(elapsedTime)}
          </Typography>
          <Typography variant="body2" color="text.secondary" data-testid="attempts">
            {t('Attempts', '尝试')}: {attempts}
          </Typography>
        </Box>

        {/* Action buttons */}
        <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
          <Button variant="outlined" startIcon={<Undo />} onClick={undo}>{t('Undo', '悔棋')}</Button>
          <Button variant="outlined" startIcon={<Replay />} onClick={reset}>{t('Reset', '重置')}</Button>
          <Button variant="outlined" startIcon={<Lightbulb />} onClick={toggleHint}>
            {showHint ? t('Hide Hint', '隐藏提示') : t('Hint', '提示')}
          </Button>
          {!isTryMode ? (
            <Button variant="outlined" startIcon={<Explore />} onClick={enterTryMode}>{t('Try', '试下')}</Button>
          ) : (
            <Button variant="outlined" startIcon={<ExploreOff />} onClick={exitTryMode}>{t('Exit Try', '退出试下')}</Button>
          )}
        </Box>
      </Box>
    </Box>
  );
};

export default TsumegoProblemPage;
