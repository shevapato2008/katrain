import { useEffect, useState, useRef, useCallback, useMemo } from 'react';
import { Box, Typography, Button, CircularProgress, Alert, Chip } from '@mui/material';
import { useParams, useNavigate } from 'react-router-dom';
import {
  ArrowBack,
  Undo,
  Lightbulb,
  Replay,
  Explore,
  ExploreOff,
  NavigateBefore,
  NavigateNext,
  FormatListBulleted,
  SmartToy,
} from '@mui/icons-material';
import { useTsumegoProblem } from '../../hooks/useTsumegoProblem';
import { useTranslation } from '../../hooks/useTranslation';
import { useSound } from '../../hooks/useSound';
import { useTsumegoProgress } from '../../context/TsumegoProgressContext';
import TsumegoBoard from '../../components/tsumego/TsumegoBoard';
import SuccessOverlay from '../components/tsumego/SuccessOverlay';
import BoardSetupGuide from '../components/vision/BoardSetupGuide';
import { useVision } from '../context/VisionContext';
import { useVisionSync } from '../hooks/useVisionSync';
import { usePhysicalTsumego, stonesToVisionBoard } from '../hooks/usePhysicalTsumego';
import { useOrientation } from '../context/OrientationContext';
import { sequenceKey, readAutoAdvance } from './tsumegoUnits';

interface ProblemSummary {
  id: string;
}

const formatTime = (seconds: number) => {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}:${s.toString().padStart(2, '0')}`;
};

const TsumegoProblemPage = () => {
  const { problemId } = useParams<{ problemId: string }>();
  const navigate = useNavigate();
  const { t } = useTranslation();
  const { play: playSound } = useSound();
  const { isPortrait } = useOrientation();
  const { progress } = useTsumegoProgress();
  const {
    problem,
    loading,
    error,
    boardSize,
    stones,
    lastMove,
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
    flushProgress,
  } = useTsumegoProblem(problemId || '');

  const { visionStatus } = useVision();
  const visionSync = useVisionSync(null); // No session bind for tsumego — physical mode drives vision setup mode
  const [physicalMode, setPhysicalMode] = useState(
    () => localStorage.getItem('kiosk-tsumego-physical') === '1',
  );
  const togglePhysical = useCallback(() => {
    setPhysicalMode((prev) => {
      const next = !prev;
      try { localStorage.setItem('kiosk-tsumego-physical', next ? '1' : '0'); } catch { /* best-effort */ }
      return next;
    });
  }, []);
  // recognition_ready = 相机+模型+几何全就绪；物理盘固定 19 路（PRD Q1：非 19 路题隐藏物理模式）
  const physicalAvailable = visionStatus.enabled && visionStatus.recognitionReady && boardSize === 19;
  // problem 数据必须与当前路由匹配，防止题目切换途中用旧 stones 启动新题流程
  const physicalProblemReady = !!problem && problem.id === problemId;
  const physicalEnabled = physicalMode && physicalAvailable && physicalProblemReady;

  // ---- Prev/Next sequence (4.1) ----
  // Sequence of problem ids for the whole category, sourced from sessionStorage (written by
  // the units pages). If missing (deep-link), fetch the full category list once and cache it.
  const [sequence, setSequence] = useState<string[]>([]);

  // flushProgress must run BEFORE every navigation away from the current problem (4.1/4.2).
  // Navigation keeps THIS page mounted (only :problemId changes), so the hook's unmount-flush
  // won't fire between problems — we must flush manually here. flushProgress is idempotent
  // (guarded inside the hook), so calling it before navigate is always safe.

  // useVisionSync(null) here never binds a session (its WS/unbind cleanup only runs for a
  // non-null sessionId), so it leaves nothing dangling on its own. Physical-mode lifecycle
  // (setup mode, move detection arming, LED, pause) is owned by usePhysicalTsumego, which
  // tears itself down explicitly (visionMoveDetection/visionPause/visionMonitor/LedAPI.clear)
  // whenever `enabled` flips false or `problemKey` changes — see its enable-effect cleanup.

  useEffect(() => {
    if (!problem) return;
    const key = sequenceKey(problem.level, problem.category);
    let seq: string[] = [];
    try {
      const raw = sessionStorage.getItem(key);
      if (raw) {
        const parsed = JSON.parse(raw);
        if (Array.isArray(parsed)) seq = parsed.filter((x): x is string => typeof x === 'string');
      }
    } catch {
      seq = [];
    }

    if (seq.length > 0) {
      setSequence(seq);
      return;
    }

    // Missing/empty — fetch the full category list once and cache it.
    const controller = new AbortController();
    fetch(`/api/v1/tsumego/levels/${problem.level}/categories/${problem.category}?limit=1000`, {
      signal: controller.signal,
    })
      .then((res) => (res.ok ? res.json() : Promise.reject(new Error(`HTTP ${res.status}`))))
      .then((data: ProblemSummary[]) => {
        const ids = Array.isArray(data) ? data.map((p) => p.id) : [];
        try {
          sessionStorage.setItem(key, JSON.stringify(ids));
        } catch {
          /* best-effort */
        }
        setSequence(ids);
      })
      .catch(() => {
        /* best-effort; prev/next stay disabled if we can't build the sequence */
      });
    return () => controller.abort();
  }, [problem]);

  const currentIndex = useMemo(
    () => (problemId ? sequence.indexOf(problemId) : -1),
    [sequence, problemId],
  );
  const isFirst = currentIndex <= 0;
  const isLast = currentIndex >= 0 && currentIndex === sequence.length - 1;
  const prevId = currentIndex > 0 ? sequence[currentIndex - 1] : null;
  const nextId = currentIndex >= 0 && currentIndex < sequence.length - 1 ? sequence[currentIndex + 1] : null;

  // "Last time" for this problem (4.3) — from the unified progress source.
  const lastDuration = problemId ? progress[problemId]?.lastDuration : undefined;

  // ---- Navigation helpers (flush progress + leave) ----
  const navigateToProblem = useCallback(
    (id: string) => {
      flushProgress(); // persist the leaving problem's attempt (4.1/4.2)
      navigate(`/kiosk/tsumego/problem/${id}`);
    },
    [navigate, flushProgress],
  );

  const goToUnits = useCallback(() => {
    flushProgress();
    if (problem) {
      navigate(`/kiosk/tsumego/${problem.level}/${problem.category}`);
    } else {
      navigate(-1);
    }
  }, [navigate, problem, flushProgress]);

  const handlePrev = useCallback(() => {
    if (prevId) navigateToProblem(prevId);
  }, [prevId, navigateToProblem]);

  const handleNext = useCallback(() => {
    if (nextId) {
      navigateToProblem(nextId);
    } else {
      // Last problem in category — "下一题" becomes "返回单元".
      goToUnits();
    }
  }, [nextId, navigateToProblem, goToUnits]);

  // Auto-advance (4.2): default ON, ~1.5s after solving, unless last problem or disabled.
  // Guard against double-fire (SuccessOverlay's timer + any re-render). Reset per problem.
  const autoAdvancedRef = useRef(false);
  // Reset per-problem UI flags when the route param changes (this page stays mounted across
  // prev/next + auto-advance, so React does NOT remount it — we must reset manually).
  useEffect(() => {
    autoAdvancedRef.current = false;
  }, [problemId]);

  // Physical mode owns the clearing_next → advance handoff (PRD TR7); the timer-based
  // auto-advance below stays screen-only.
  const autoAdvanceEnabled = isSolved && !isLast && !!nextId && readAutoAdvance() && !physicalEnabled;

  const handleAutoComplete = useCallback(() => {
    if (autoAdvancedRef.current) return;
    if (!nextId) return;
    autoAdvancedRef.current = true;
    navigateToProblem(nextId);
  }, [nextId, navigateToProblem]);

  const physical = usePhysicalTsumego({
    enabled: physicalEnabled,
    problemKey: problem?.id ?? null,
    boardSize,
    stones,
    isSolved,
    showHint,
    hintCoords,
    isTryMode,
    autoAdvance: readAutoAdvance() && !isLast && !!nextId,
    syncEvents: visionSync.syncEvents,
    placeStone,
    undo,
    playMoveSound: playSound,
    onAdvance: handleAutoComplete, // 与既有 auto-advance 同一导航路径
  });

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%' }}>
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

  return (
    <Box sx={{ display: 'flex', flexDirection: isPortrait ? 'column' : 'row', height: '100%', bgcolor: 'background.default' }}>
      {/* Board area */}
      <Box
        sx={
          isPortrait
            ? { width: '100%', maxHeight: '50%', aspectRatio: '1', position: 'relative' }
            : { height: '100%', aspectRatio: '1', position: 'relative' }
        }
        data-testid="tsumego-board"
      >
        <TsumegoBoard
          boardSize={boardSize}
          stones={stones}
          lastMove={lastMove}
          hintCoords={hintCoords}
          showHint={showHint}
          disabled={isSolved || (isFailed && !isTryMode)}
          moveHistory={moveHistory}
          onPlaceStone={(x, y) => {
            // Physical mode: screen clicks only while it's the user's turn (guides own the
            // board in other phases); the machine then guides the physical board to follow.
            if (physicalEnabled && physical.phase !== 'ready') return;
            const preBoard = physicalEnabled ? stonesToVisionBoard(stones, boardSize) : null;
            const result = placeStone(x, y);
            if (result?.sound) playSound(result.sound);
            if (physicalEnabled && preBoard) physical.onScreenMove(result, preBoard);
          }}
        />
        {/* Success overlay + auto-advance (4.2). onComplete only wired when auto-advance is
            active (not last, enabled in settings) — its internal timer is cleaned up on
            unmount / when show flips false, so it cannot leak or mis-fire (R5). */}
        <SuccessOverlay
          show={isSolved}
          message={t('tsumego:solved', '正确！')}
          onComplete={autoAdvanceEnabled ? handleAutoComplete : undefined}
          delayMs={1500}
        />
      </Box>

      {/* Controls panel */}
      <Box sx={{ flex: 1, p: 2, display: 'flex', flexDirection: 'column', overflow: 'auto' }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
          <Button onClick={goToUnits} startIcon={<ArrowBack />} sx={{ minWidth: 40, p: 0.5 }} />
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
        {isFailed && !isTryMode && (
          <Alert severity="error" sx={{ mb: 2 }}>{t('Incorrect, try again', '不正确，请重试')}</Alert>
        )}
        {isTryMode && (
          <Alert severity="info" sx={{ mb: 2 }}>{t('Try mode - free exploration', '试下模式 - 自由探索')}</Alert>
        )}

        {/* Timer and attempts */}
        <Box sx={{ display: 'flex', gap: 2, mb: 2, flexWrap: 'wrap' }}>
          <Typography variant="body2" color="text.secondary" data-testid="timer">
            {t('Time', '用时')}: {formatTime(elapsedTime)}
          </Typography>
          <Typography variant="body2" color="text.secondary" data-testid="attempts">
            {t('Attempts', '尝试')}: {attempts}
          </Typography>
          {lastDuration != null && (
            <Typography variant="body2" color="text.secondary" data-testid="last-time">
              {t('tsumego:lastTime', '上次用时')}: {formatTime(lastDuration)}
            </Typography>
          )}
        </Box>

        {/* Action buttons */}
        <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
          <Button variant="outlined" startIcon={<Undo />} onClick={undo}>{t('Undo', '悔棋')}</Button>
          <Button variant="outlined" startIcon={<Replay />} onClick={reset}>{t('Reset', '重置')}</Button>
          <Button
            variant="outlined"
            startIcon={<Lightbulb />}
            onClick={toggleHint}
            disabled={physicalEnabled && physical.phase !== 'ready'}
          >
            {showHint ? t('Hide Hint', '隐藏提示') : t('Hint', '提示')}
          </Button>
          {!isTryMode ? (
            <Button
              variant="outlined"
              startIcon={<Explore />}
              onClick={enterTryMode}
              disabled={physicalEnabled && physical.phase !== 'ready'}
            >
              {t('Try', '试下')}
            </Button>
          ) : (
            <Button variant="outlined" startIcon={<ExploreOff />} onClick={exitTryMode}>{t('Exit Try', '退出试下')}</Button>
          )}
          <Button
            variant={physicalMode ? 'contained' : 'outlined'}
            color={physicalMode ? 'success' : 'inherit'}
            startIcon={<SmartToy />}
            disabled={!physicalAvailable}
            onClick={togglePhysical}
          >
            {physicalMode ? t('tsumego:physicalOn', '退出物理棋盘') : t('tsumego:physicalOff', '使用物理棋盘')}
          </Button>
        </Box>

        {/* Prev / Next navigation (4.1) — prominent touch buttons. */}
        <Box sx={{ display: 'flex', gap: 1.5, mt: 2 }}>
          <Button
            variant="contained"
            color="inherit"
            size="large"
            startIcon={<NavigateBefore />}
            onClick={handlePrev}
            disabled={isFirst}
            data-testid="prev-problem"
            sx={{ flex: 1, py: 1.5, fontSize: '1.05rem' }}
          >
            {t('tsumego:prev', '上一题')}
          </Button>
          {isLast ? (
            <Button
              variant="contained"
              color="primary"
              size="large"
              startIcon={<FormatListBulleted />}
              onClick={goToUnits}
              data-testid="next-problem"
              sx={{ flex: 1, py: 1.5, fontSize: '1.05rem' }}
            >
              {t('tsumego:backToUnit', '返回单元')}
            </Button>
          ) : (
            <Button
              variant="contained"
              color="primary"
              size="large"
              endIcon={<NavigateNext />}
              onClick={handleNext}
              data-testid="next-problem"
              sx={{ flex: 1, py: 1.5, fontSize: '1.05rem' }}
            >
              {t('tsumego:next', '下一题')}
            </Button>
          )}
        </Box>

        {/* Physical-board phase guidance */}
        {physicalEnabled && !['off', 'ready', 'solved'].includes(physical.phase) && (
          <Box sx={{ mt: 2 }}>
            {(physical.phase === 'clearing' || physical.phase === 'clearing_next') && (
              <Alert severity="info">
                请清空棋盘{physical.extra.length > 0 ? `（剩 ${physical.extra.length} 颗）` : ''}
              </Alert>
            )}
            {physical.phase === 'setup' && (
              <BoardSetupGuide
                matched={physical.stageMatched}
                total={physical.stageTotal}
                missing={physical.missing}
                extra={physical.extra}
                stage={physical.stage}
                isComplete={false}
                onStartProblem={() => {}}
                onSkip={togglePhysical}
              />
            )}
            {physical.phase === 'replying' && (
              <Alert severity="info">请按棋盘灯光摆放棋子（应手/提子），使棋盘与屏幕一致</Alert>
            )}
            {physical.phase === 'removing' && (
              <Alert severity="warning">
                答错了：请取回 {physical.extra.length} 颗棋子（蓝灯）
                {physical.missing.length > 0 ? `，并放回被提的 ${physical.missing.length} 颗棋子（红/绿灯）` : ''}
              </Alert>
            )}
            {physical.phase === 'restoring' && (
              <Alert severity="info">正在校验棋盘与题面一致，请按灯光调整棋子</Alert>
            )}
            {!physical.ledOk && <Alert severity="warning" sx={{ mt: 1 }}>LED 未连接，请按屏幕提示操作</Alert>}
          </Box>
        )}
      </Box>
    </Box>
  );
};

export default TsumegoProblemPage;
