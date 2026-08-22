import { useEffect, useState, useRef, useCallback, useMemo } from 'react';
import { Box, Typography, Button, CircularProgress, Alert } from '@mui/material';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Undo,
  Lightbulb,
  Replay,
  Explore,
  ExploreOff,
  NavigateBefore,
  NavigateNext,
  FormatListBulleted,
  CheckCircle,
} from '@mui/icons-material';
import { useTsumegoProblem } from '../../hooks/useTsumegoProblem';
import { useTranslation } from '../../hooks/useTranslation';
import { useSound } from '../../hooks/useSound';
import { useTsumegoProgress } from '../../context/TsumegoProgressContext';
import TsumegoBoard from '../../components/tsumego/TsumegoBoard';
import SuccessOverlay from '../components/tsumego/SuccessOverlay';
import BoardSetupGuide from '../components/vision/BoardSetupGuide';
import { useVision } from '../context/VisionContext';
import { useOptionalGeometry } from '../context/GeometryContext';
import { useImmersive } from '../context/ImmersiveContext';
import { useVisionSync } from '../hooks/useVisionSync';
import { usePhysicalTsumego, stonesToVisionBoard } from '../hooks/usePhysicalTsumego';
import {
  sequenceKey,
  readAutoAdvance,
  levelChinese,
  readPhysicalMode,
  writePhysicalMode,
  writeLastLevel,
  writeLastCategory,
} from './tsumegoUnits';
import { writeActiveSession } from '../utils/activeSession';
import PhysicalModeToggle from '../components/tsumego/PhysicalModeToggle';
import PhysicalStatePanel from '../components/tsumego/PhysicalStatePanel';
import { KioskPagebar } from '../shell/KioskPagebar';

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
    nextPlayer,
    elapsedTime,
    attempts,
    showHint,
    hintCoords,
    moveHistory,
    placeStone,
    undo,
    reset,
    restartTimer,
    toggleHint,
    enterTryMode,
    exitTryMode,
    flushProgress,
  } = useTsumegoProblem(problemId || '');

  const { visionStatus } = useVision();
  const geometry = useOptionalGeometry();
  const visionSync = useVisionSync(null); // No session bind for tsumego — physical mode drives vision setup mode

  // Physical-mode toggle — single owner, persisted via tsumegoUnits (develop's key kiosk_tsumego_physical).
  const [physicalMode, setPhysicalMode] = useState(readPhysicalMode);
  const setPhysical = useCallback((v: boolean) => {
    writePhysicalMode(v);
    setPhysicalMode(v);
  }, []);
  // Reset re-runs the physical clearing→setup lifecycle (reset() keeps problem.id, so the
  // hook's per-problem restart won't fire on its own — bump resyncKey to force it).
  const [resyncKey, setResyncKey] = useState(0);
  const handleReset = useCallback(() => {
    reset();
    setResyncKey((k) => k + 1);
  }, [reset]);
  // recognition_ready = 相机+模型+几何全就绪；物理盘固定 19 路（PRD Q1：非 19 路题隐藏物理模式）
  const physicalAvailable = visionStatus.enabled && visionStatus.recognitionReady && boardSize === 19;
  // problem 数据必须与当前路由匹配，防止题目切换途中用旧 stones 启动新题流程
  const physicalProblemReady = !!problem && problem.id === problemId;
  const physicalEnabled = physicalMode && physicalAvailable && physicalProblemReady;

  // Why can't the physical board be turned on right now? A silently-disabled toggle is confusing —
  // surface the reason (and a tap-through to calibration) as a hint. The common case after a server
  // restart: the saved geometry lock reloads but session_calibrated resets, so it needs a one-tap
  // re-confirm on the calibration page (not a full recalibration).
  const geoPhase = geometry?.status.phase;
  const physicalHint: { text: string; calibrate?: boolean; severity: 'info' | 'warning' } | null =
    physicalMode || physicalAvailable
      ? null
      : boardSize !== 19
        ? { text: t('tsumego:physNeed19', '物理棋盘仅支持 19 路题目'), severity: 'info' }
        : !visionStatus.enabled
          ? { text: t('tsumego:physNoCamera', '未检测到摄像头 / 视觉服务未启用'), severity: 'warning' }
          : geoPhase && geoPhase !== 'ready' && geoPhase !== 'disabled'
            ? geoPhase === 'degraded' || geoPhase === 'failed'
              ? { text: t('tsumego:physGeoDrift', '棋盘标定已失效，请重新标定棋盘'), calibrate: true, severity: 'warning' }
              : { text: t('tsumego:physGeoConfirm', '物理棋盘需先确认棋盘标定（服务重启后需重新确认一次）'), calibrate: true, severity: 'warning' }
            : { text: t('tsumego:physConnecting', '正在连接摄像头与识别模型，请稍候…'), severity: 'info' };

  // ---- Prev/Next sequence (4.1) ----
  // Sequence of problem ids for the whole category, sourced from sessionStorage (written by
  // the units pages). If missing (deep-link), fetch the full category list once and cache it.
  const [sequence, setSequence] = useState<string[]>([]);

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
    writeLastCategory(problem.category);
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

  // Physical-board tsumego — real hook with our availability gating (recognition + geometry + 19-路).
  const physical = usePhysicalTsumego({
    enabled: physicalEnabled,
    visionConnected: visionSync.connected,
    problemKey: problem?.id ?? null,
    resyncKey,
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

  // Physical mode: don't count board-setup time toward 用时. Rebase the answer clock the first
  // time the board reaches 'ready' after (re)entering setup; answer-phase revisits to 'ready'
  // (after a reply / wrong-move removal) keep the clock running.
  const answerClockArmedRef = useRef(false);
  useEffect(() => {
    if (!physicalEnabled) {
      answerClockArmedRef.current = false;
      return;
    }
    if (['clearing', 'clearing_next', 'setup'].includes(physical.phase)) {
      answerClockArmedRef.current = true; // in setup → arm the next ready-restart
    } else if (physical.phase === 'ready' && answerClockArmedRef.current) {
      answerClockArmedRef.current = false;
      restartTimer();
    }
  }, [physicalEnabled, physical.phase, restartTimer]);

  const inPhysicalSetup =
    physicalEnabled && ['clearing', 'clearing_next', 'setup'].includes(physical.phase);

  // Flag wrong/extra physical stones on the electronic board with a red ✕. physical.extra is in
  // vision coords [row(0=top), col, color]; TsumegoBoard wants board coords [x=col, y=(size-1-row)].
  // Occlusion-proof: the screen is never hidden by the stone sitting on the physical LED.
  const extraMarkers = useMemo<[number, number][]>(
    () => (physicalEnabled ? physical.extra.map(([row, col]) => [col, boardSize - 1 - row]) : []),
    [physicalEnabled, physical.extra, boardSize],
  );

  // While CLEARING the physical board, the goal is an empty board — every stone is "extra" and gets
  // a ✕. Showing the static solved/target stones underneath them means removing a physical stone
  // clears only its ✕ while the electronic stone lingers (unreasonable). Render an empty board
  // during clearing so the ✕'s float on bare intersections and vanish one-by-one as stones come off.
  const clearingPhysical =
    physicalEnabled && (physical.phase === 'clearing' || physical.phase === 'clearing_next');
  const displayStones = clearingPhysical ? [] : stones;

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
          stones={displayStones}
          lastMove={lastMove}
          hintCoords={hintCoords}
          showHint={showHint}
          extraMarkers={extraMarkers}
          disabled={isSolved || (isFailed && !isTryMode)}
          moveHistory={moveHistory}
          onPlaceStone={(x, y) => {
            // Physical mode: screen clicks only while it's the user's turn (guides own the
            // board in other phases); the machine then guides the physical board to follow.
            if (physicalEnabled && physical.phase !== 'ready') return;
            const preBoard = physicalEnabled ? stonesToVisionBoard(stones, boardSize) : null;
            const result = placeStone(x, y);
            if (result?.sound) playSound(result.sound);
            // Try-mode clicks are screen-only exploration (recognition is paused) — never feed
            // them to the physical machine, or a single click pushes it out of 'ready'.
            if (physicalEnabled && !isTryMode && preBoard) physical.onScreenMove(result, preBoard);
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
        {/* 布局 A:做题屏有棋盘 ⇒ 页控条在**右栏顶部**,不是通栏(§11 那张表)。 */}
        <KioskPagebar
          title={
            problem
              ? `${t('Life & Death', '死活')} › ${levelChinese(problem.level)} › ${t(`tsumego:${problem.category}`, problem.category)} › 第 ${currentIndex + 1} 题`
              : t('Life & Death', '死活棋')
          }
          backLabel={t('Back', '返回')}
          onBack={goToUnits}
        />

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
        {isFailed && !isTryMode && (
          <Alert severity="error" sx={{ mb: 2 }}>{t('Incorrect, try again', '不正确，请重试')}</Alert>
        )}
        {isTryMode && (
          <Alert severity="info" sx={{ mb: 2 }}>{t('Try mode - free exploration', '试下模式 - 自由探索')}</Alert>
        )}

        {/* Physical-mode status panel (develop) — concise phase chip; renders null off/clearing/restoring. */}
        {physicalMode && (
          <Box sx={{ mb: 2 }}>
            <PhysicalStatePanel state={physical} />
          </Box>
        )}

        {/* Timer and attempts — pill row (develop styling); OUR time hides board-setup as 准备中. */}
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
            {t('Time', '用时')}: {inPhysicalSetup ? t('tsumego:preparingBoard', '准备中') : formatTime(elapsedTime)}
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
          {/* Physical mode is board-driven: take moves back by removing physical stones
              (LED-guided), not the screen button — a screen undo desyncs the machine. */}
          <Button variant="outlined" startIcon={<Undo />} onClick={undo} disabled={physicalEnabled}>{t('Undo', '悔棋')}</Button>
          <Button variant="outlined" startIcon={<Replay />} onClick={handleReset}>{t('Reset', '重置')}</Button>
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
        </Box>

        {/* Physical-mode toggle (develop's Switch). capable = physicalMode || physicalAvailable so
            turning ON is gated on availability, but turning OFF is always allowed (a dropped
            availability must never strand the user with a dead board). */}
        <Box sx={{ mt: 2 }}>
          <PhysicalModeToggle
            checked={physicalMode}
            capable={physicalMode || physicalAvailable}
            onChange={setPhysical}
          />
        </Box>

        {/* Why the toggle is off/unavailable (ours) — with a tap-through to calibration. */}
        {physicalHint && (
          <Alert
            severity={physicalHint.severity}
            sx={{ mt: 1 }}
            action={
              physicalHint.calibrate ? (
                <Button color="inherit" size="small" href="/kiosk/vision/setup">
                  {t('tsumego:goCalibrate', '去标定')}
                </Button>
              ) : undefined
            }
          >
            {physicalHint.text}
          </Alert>
        )}

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

        {/* Physical-board "ready to answer" cue (setup complete; setup_done voice fires in the machine) */}
        {physicalEnabled && physical.phase === 'ready' && (
          <Box sx={{ mt: 2 }}>
            <Alert severity="success" icon={<CheckCircle fontSize="inherit" />}>
              <Typography variant="body1" sx={{ fontWeight: 600 }}>{t('tsumego:setupDone', '摆盘完成 · 轮到你了')}</Typography>
              {nextPlayer === 'B'
                ? t('tsumego:placeAnswerBlack', '请在正解点落一手黑棋，棋盘会自动识别')
                : t('tsumego:placeAnswerWhite', '请在正解点落一手白棋，棋盘会自动识别')}
            </Alert>
          </Box>
        )}

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
                onSkip={() => setPhysical(false)}
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
