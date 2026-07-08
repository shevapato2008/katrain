import { useEffect, useState, useRef, useCallback, useMemo } from 'react';
import { Box, Typography, Button, CircularProgress, Alert } from '@mui/material';
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
} from '@mui/icons-material';
import { useTsumegoProblem } from '../../hooks/useTsumegoProblem';
import { useTranslation } from '../../hooks/useTranslation';
import { useSound } from '../../hooks/useSound';
import { useTsumegoProgress } from '../../context/TsumegoProgressContext';
import { API } from '../../api';
import TsumegoBoard from '../../components/tsumego/TsumegoBoard';
import SuccessOverlay from '../components/tsumego/SuccessOverlay';
import BoardSetupGuide from '../components/vision/BoardSetupGuide';
import { useVision } from '../context/VisionContext';
import { useImmersive } from '../context/ImmersiveContext';
import { useVisionSync } from '../hooks/useVisionSync';
import { sequenceKey, readAutoAdvance, levelChinese, readPhysicalMode, writePhysicalMode, writeLastLevel } from './tsumegoUnits';
import { writeActiveSession } from '../utils/activeSession';
import PhysicalModeToggle from '../components/tsumego/PhysicalModeToggle';
import PhysicalStatePanel from '../components/tsumego/PhysicalStatePanel';
import { usePhysicalTsumego, type PhysicalTsumegoOptions } from '../hooks/usePhysicalTsumego';

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
  const { progress } = useTsumegoProgress();
  const { setImmersive } = useImmersive();
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

  const { isVisionEnabled } = useVision();
  const visionSync = useVisionSync(null); // No session bind for tsumego — uses setup mode
  const [setupSkipped, setSetupSkipped] = useState(false);
  const [setupDone, setSetupDone] = useState(!isVisionEnabled);

  // Physical-mode toggle seam (B2.5) — single declaration in the whole track. OFF (default)
  // means screen point-select solving is unchanged; Phase D (D1.3) reads this same state to
  // drive the 5-state PhysicalStatePanel + usePhysicalTsumego.
  const [physicalMode, setPhysicalMode] = useState(readPhysicalMode());
  const capable = isVisionEnabled;

  // ---- Prev/Next sequence (4.1) ----
  // Sequence of problem ids for the whole category, sourced from sessionStorage (written by
  // the units pages). If missing (deep-link), fetch the full category list once and cache it.
  const [sequence, setSequence] = useState<string[]>([]);

  // flushProgress must run BEFORE every navigation away from the current problem (4.1/4.2).
  // Navigation keeps THIS page mounted (only :problemId changes), so the hook's unmount-flush
  // won't fire between problems — we must flush manually here. flushProgress is idempotent
  // (guarded inside the hook), so calling it before navigate is always safe.

  // R6 vision-cleanup finding: setup mode is entered imperatively via API.visionSetupMode;
  // there is NO explicit server teardown endpoint for setup mode. useVisionSync(null) here
  // never binds a session (its WS/unbind cleanup only runs for a non-null sessionId), so it
  // leaves nothing dangling. The only per-navigation/unmount concerns are the JS timers, and
  // those live inside SuccessOverlay (cleaned up on hide/unmount) — there are no page-level
  // timers to leak. We reset the vision setup UI flags per problem (the load effect below).

  // Immersive solve screen — hide the Dock + left board console while a problem is open.
  useEffect(() => {
    setImmersive(true);
    return () => setImmersive(false);
  }, [setImmersive]);

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

  // Populate the hub 继续练习 card + 上次 level highlight (B2.2/B2.4) whenever a problem loads.
  useEffect(() => {
    if (!problem) return;
    writeLastLevel(problem.level);
    writeActiveSession({
      kind: 'practice',
      label: `${levelChinese(problem.level)} · ${t(`tsumego:${problem.category}`, problem.category)} · 第 ${currentIndex + 1} 题`,
      route: `/kiosk/tsumego/problem/${problem.id}`,
      ts: Date.now(),
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps -- snapshot label written once per problem; `t` intentionally excluded
  }, [problem, currentIndex]);

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
    setSetupDone(!isVisionEnabled);
    setSetupSkipped(false);
  }, [problemId, isVisionEnabled]);

  const autoAdvanceEnabled = isSolved && !isLast && !!nextId && readAutoAdvance();

  const handleAutoComplete = useCallback(() => {
    if (autoAdvancedRef.current) return;
    if (!nextId) return;
    autoAdvancedRef.current = true;
    navigateToProblem(nextId);
  }, [nextId, navigateToProblem]);

  // Enter vision setup mode when problem loads with initial stones
  useEffect(() => {
    if (!isVisionEnabled || setupSkipped || !stones.length || !boardSize) return;
    // Convert stones to board matrix for vision setup
    const board: number[][] = Array.from({ length: boardSize }, () => Array(boardSize).fill(0));
    for (const s of stones) {
      const [col, row] = s.coords;
      if (col >= 0 && col < boardSize && row >= 0 && row < boardSize) {
        board[boardSize - 1 - row][col] = s.player === 'B' ? 1 : 2; // Y-flip for vision
      }
    }
    API.visionSetupMode(board);
    setSetupDone(false);
  }, [isVisionEnabled, setupSkipped, stones.length, boardSize, problemId]);

  // Watch for setup complete
  useEffect(() => {
    if (!isVisionEnabled) return;
    const completeEvent = visionSync.syncEvents.find((e) => e.type === 'setup_complete');
    if (completeEvent) setSetupDone(true);
  }, [visionSync.syncEvents, isVisionEnabled]);

  // ---- Physical-mode wiring (D1.3) ----
  // Called unconditionally (rules of hooks) — `enabled: physicalMode` (B2.5's single-owner
  // state, reused here, NOT re-declared) IS the on/off lifecycle. The real hook has no
  // enable()/disable() methods, so there is deliberately no lifecycle effect here; the stub
  // only reacts to `opts.enabled`, everything else below is accepted purely for TYPE parity
  // with the real hook so it is a drop-in replacement later (phase-D-real-contract.md).
  const physicalOpts: PhysicalTsumegoOptions = {
    enabled: physicalMode,
    // This repo's useVisionSync exposes no WS-open flag (real-contract note) — typed
    // placeholder derived from live sync traffic; swap for a real "connected" signal
    // when the real hook lands.
    visionConnected: visionSync.syncEvents.length > 0,
    problemKey: problemId ?? null,
    // No reset/resync counter exists on this page yet — static placeholder.
    resyncKey: 0,
    boardSize,
    stones,
    isSolved,
    showHint,
    hintCoords,
    isTryMode,
    autoAdvance: readAutoAdvance() && !!nextId,
    syncEvents: visionSync.syncEvents,
    placeStone,
    undo,
    playMoveSound: playSound,
    onAdvance: handleNext,
  };
  const physical = usePhysicalTsumego(physicalOpts);

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
    <Box sx={{ display: 'flex', flexDirection: 'row', height: '100%', bgcolor: 'background.default' }}>
      {/* Board area */}
      <Box
        sx={{ height: '100%', aspectRatio: '1', position: 'relative' }}
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
            const result = placeStone(x, y);
            if (result?.sound) playSound(result.sound);
          }}
        />
        {/* Success overlay + auto-advance (4.2). onComplete only wired when auto-advance is
            active (not last, enabled in settings) — its internal timer is cleaned up on
            unmount / when show flips false, so it cannot leak or mis-fire (R5). */}
        <SuccessOverlay
          show={isSolved}
          message={t('tsumego:solved', '恭喜答对！')}
          onComplete={autoAdvanceEnabled ? handleAutoComplete : undefined}
          delayMs={1500}
        />
      </Box>

      {/* Controls panel */}
      <Box sx={{ flex: 1, p: 2, display: 'flex', flexDirection: 'column', overflow: 'auto' }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, mb: 2, flexWrap: 'wrap' }}>
          <Button onClick={goToUnits} startIcon={<ArrowBack />} sx={{ minWidth: 40, p: 0.5 }} />
          {problem && (
            <Typography variant="body2" sx={{ color: 'text.secondary' }}>
              <Box component="span">死活</Box>
              <Box component="span" sx={{ mx: 0.75, color: 'text.disabled' }}>›</Box>
              <Box component="span">{levelChinese(problem.level)}</Box>
              <Box component="span" sx={{ mx: 0.75, color: 'text.disabled' }}>›</Box>
              <Box component="span">{t(`tsumego:${problem.category}`, problem.category)}</Box>
              <Box component="span" sx={{ mx: 0.75, color: 'text.disabled' }}>›</Box>
              <Box component="span" sx={{ color: 'text.primary', fontWeight: 600 }}>第 {currentIndex + 1} 题</Box>
            </Typography>
          )}
        </Box>

        {problem?.hint && (
          <Box
            sx={{
              mb: 2,
              p: 1.5,
              borderRadius: 2,
              bgcolor: 'background.paper',
              border: '1px solid',
              borderColor: 'divider',
            }}
          >
            <Typography variant="body2" sx={{ color: 'text.secondary' }}>{problem.hint}</Typography>
          </Box>
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

        {/* Physical-mode status panel (D1.3) — physical mode ON only. TR1 dual-input:
            TsumegoBoard's onPlaceStone below is untouched and un-gated — screen clicks and
            physical placement coexist; the stub doesn't consume `placeStone` at all (the
            real adapter wires the `onScreenMove` passthrough later). */}
        {physicalMode && (
          <Box sx={{ mb: 2 }}>
            <PhysicalStatePanel state={physical} />
          </Box>
        )}

        {/* Timer and attempts — .mrow pill row */}
        <Box
          sx={{
            display: 'flex',
            gap: 2,
            mb: 2,
            flexWrap: 'wrap',
            bgcolor: 'background.paper',
            border: '1px solid',
            borderColor: 'divider',
            borderRadius: 2,
            px: 1.5,
            py: 1,
          }}
        >
          <Typography variant="body2" sx={{ color: 'text.secondary' }} data-testid="timer">
            {t('Time', '用时')}: {formatTime(elapsedTime)}
          </Typography>
          <Typography variant="body2" sx={{ color: 'text.secondary' }} data-testid="attempts">
            {t('Attempts', '尝试')}: {attempts}
          </Typography>
          {lastDuration != null && (
            <Typography variant="body2" sx={{ color: 'text.secondary' }} data-testid="last-time">
              {t('tsumego:lastTime', '上次用时')}: {formatTime(lastDuration)}
            </Typography>
          )}
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

        <Box sx={{ mt: 2 }}>
          <PhysicalModeToggle
            checked={physicalMode}
            capable={capable}
            onChange={(v) => { writePhysicalMode(v); setPhysicalMode(v); }}
          />
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
            sx={{
              flex: 1,
              py: 1.5,
              fontSize: '1.05rem',
              bgcolor: 'background.paper',
              color: 'text.primary',
              '&:hover': { bgcolor: 'background.paper' },
            }}
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

        {/* Vision setup guide for initial position */}
        {isVisionEnabled && !setupDone && !setupSkipped && stones.length > 0 && (
          <Box sx={{ mt: 2 }}>
            <BoardSetupGuide
              matched={visionSync.setupProgress?.matched ?? 0}
              total={visionSync.setupProgress?.total ?? stones.length}
              missing={visionSync.setupProgress?.missing ?? []}
              isComplete={visionSync.isSetupComplete}
              onStartProblem={() => setSetupDone(true)}
              onSkip={() => { setSetupSkipped(true); setSetupDone(true); }}
            />
          </Box>
        )}
      </Box>
    </Box>
  );
};

export default TsumegoProblemPage;
