import { Fragment, useEffect, useState, useRef, useCallback, useMemo } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
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
  CATEGORY_META,
  UNIT_SIZE,
  sequenceKey,
  readAutoAdvance,
  levelChinese,
  readPhysicalMode,
  writePhysicalMode,
  writeLastLevel,
  writeLastCategory,
} from './tsumegoUnits';
import { interpolate } from '../utils/interpolate';
import { writeActiveSession } from '../utils/activeSession';
import PhysicalStatePanel from '../components/tsumego/PhysicalStatePanel';
import { KioskPagebar } from '../shell/KioskPagebar';
import { KioskActions, type KioskAction } from '../shell/KioskActions';
import { GO_COLS, colsFor, rowsFor } from '../shell/goBoard';

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


  // ── 稿子 `data-screen="puzzle"`(屏 14 · L2 布局 A)────────────────────────
  // 盘 516 + 16 + 右栏 460;右栏五块:页控条 / 这一题 / 你的走法 / 第 N 单元 / 动作区。
  //
  // ⚠️ **题库里没有「题面」这种东西。** `TsumegoProblem` 的列只有
  // id / level / category / hint(16 字,「黑先」「白先」这种) / board_size /
  // initial_black / initial_white / sgf_content —— **没有标题,也没有一段讲人话的题面**。
  // 稿子上那段「黑先。白有两颗子,各剩两口气……」是**画稿时手写的**(稿子自己的注释写着),
  // 页控条上那个「一手叫吃两边」同理。⇒ **不搬,也不编。**
  // 这一屏能诚实说出口的只有 `hint` 那一句,加上这一屏自己的规则(落子即判)。
  // 稿子第三个标签「示意题面」也去掉:它标的是「这题是稿子上现摆的」,真题来自题库,挂着就是撒谎。
  const categoryName = problem ? t(`tsumego:${problem.category}`, CATEGORY_META[problem.category]?.zh ?? problem.category) : '';
  const levelName = problem ? levelChinese(problem.level) : '';

  // 这一题属于第几单元 —— 顺序表算得出来就算,算不出来(深链 + 取不到)就退回类目那一层。
  const unitNumber = currentIndex >= 0 ? Math.floor(currentIndex / UNIT_SIZE) + 1 : null;
  const unitIds = unitNumber === null
    ? []
    : sequence.slice((unitNumber - 1) * UNIT_SIZE, unitNumber * UNIT_SIZE);
  const backTarget = problem
    ? unitNumber === null
      ? `/kiosk/tsumego/${problem.level}/${problem.category}`
      : `/kiosk/tsumego/${problem.level}/${problem.category}/${unitNumber}`
    : null;
  const backLabel = unitNumber === null
    ? categoryName
    : interpolate(t('tsumego:unit_n', '第 {n} 单元'), { n: unitNumber });
  const backToUnit = useCallback(() => {
    flushProgress();
    if (backTarget) navigate(backTarget);
    else navigate(-1);
  }, [navigate, backTarget, flushProgress]);

  const coordLabel = (x: number, y: number) => `${GO_COLS[x] ?? '?'}${y + 1}`;

  // 「试了几次」和屏 12/13 同一个口径:`attempts` 数的是**失败**的那几次,最后成了的那次自己加。
  const tries = attempts + (isSolved ? 1 : 0);

  // 右栏的动作区。稿子四个键(提示 / 退一手 / 重摆 / 下一题)加上「上一题」= 五个,
  // **一排五格、格子一样大**(§11:格高、图标、字号一律走共享 `.kiosk-actions button`)。
  // 「试下」不在这里 —— 它是**模式**不是动作,归下面那排开关(原来是「试下 / 退出试下」
  // 两个按钮轮流出现,那本来就是一个开关的两半)。
  const actions: KioskAction[] = [
    {
      key: 'hint',
      icon: 'lightbulb',
      label: showHint ? t('Hide Hint', '收提示') : t('Hint', '提示'),
      onClick: toggleHint,
      pressed: showHint,
      disabled: physicalEnabled && physical.phase !== 'ready',
    },
    {
      key: 'undo',
      icon: 'arrow-counter-clockwise',
      // ⚠️ **不能用 `t('Undo', …)`** —— cn PO 里 `Undo` 是「悔棋」,翻译表赢过默认值,
      // 屏上会写「悔棋」。做题没有对手,悔的是自己上一手,稿子写的是「退一手」。
      label: t('tsumego:undoMove', '退一手'),
      onClick: undo,
      // 实体模式下悔棋要**从盘上拿子**(LED 引导),屏幕上按一下会让机器和盘对不上。
      disabled: physicalEnabled,
      reason: t('tsumego:undoPhysical', '实体棋盘上请直接把子拿掉，按灯光提示走'),
    },
    { key: 'reset', icon: 'arrows-clockwise', label: t('Reset', '重摆'), onClick: handleReset },
    {
      key: 'prev',
      icon: 'caret-left',
      label: t('tsumego:prev', '上一题'),
      onClick: handlePrev,
      disabled: isFirst,
      reason: sequence.length === 0
        ? t('tsumego:noSequence', '读不到这一类的题号，上/下一题暂时用不了')
        : t('tsumego:isFirst', '这是第一题'),
    },
    isLast
      ? { key: 'next', icon: 'squares-four', label: t('tsumego:backToUnit', '返回单元'), onClick: backToUnit }
      : {
          key: 'next',
          icon: 'skip-forward',
          label: t('tsumego:next', '下一题'),
          onClick: handleNext,
          disabled: !nextId,
          reason: t('tsumego:noSequence', '读不到这一类的题号，上/下一题暂时用不了'),
        },
  ];

  if (loading || error) {
    return (
      <div className="kiosk-layout-b">
        <KioskPagebar
          testId="puzzle-pagebar"
          // 同上:`tsumego:practiceProblems` 在 PO 里是一整句「练习死活题以提高计算能力」,
          // 当标题用会把一句话塞进页控条。
          title={t('tsumego:loadingTitle', '做题')}
          backLabel={t('Back', '返回')}
          onBack={() => navigate(-1)}
        />
        {error ? (
          <div className="empty" data-testid="puzzle-error">
            {/* `tsumego:loadError` 在 PO 里是「死活题库加载失败，请稍后重试。」——
                那是**一句话**,而这里要的是一个标题;原因写在下面那行。 */}
            <h4>{t('tsumego:problemLoadError', '这道题读不到')}</h4>
            <p>{error}</p>
          </div>
        ) : (
          <div className="empty" data-testid="puzzle-loading">
            <h4>{t('tsumego:loadingProblem', '正在读这道题…')}</h4>
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="kiosk-layout-a">
      {/* 盘跨满整个 516 木框:`TsumegoBoard` 是一块 canvas,**坐标画在它自己里面**,
          再套共享的四条刻度带就是两套坐标。见 `go-screens.css` 的 `--full`。 */}
      <div className="kiosk-board">
        {/* 四条刻度带由**外壳**画(四棋类同一套几何),盘自己那一圈坐标因此关掉 ——
            两边都画就是两套坐标,字号字色还不是同一套。 */}
        <div className="kiosk-board__ruler kiosk-board__ruler--top">
          {colsFor(boardSize).map((c) => <span key={`t${c}`}>{c}</span>)}
        </div>
        <div className="kiosk-board__ruler kiosk-board__ruler--left">
          {rowsFor(boardSize).map((r) => <span key={`l${r}`}>{r}</span>)}
        </div>
        <div className="kiosk-board__play" data-testid="tsumego-board">
          <TsumegoBoard
            boardSize={boardSize}
            showCoordinates={false}
            stones={displayStones}
            lastMove={lastMove}
            hintCoords={hintCoords}
            showHint={showHint}
            extraMarkers={extraMarkers}
            disabled={isSolved || (isFailed && !isTryMode)}
            moveHistory={moveHistory}
            onPlaceStone={(x, y) => {
              // 实体模式下屏幕点击只在轮到人时受理(别的阶段盘由引导接管);
              // 受理之后由机器引导实体盘跟上。
              if (physicalEnabled && physical.phase !== 'ready') return;
              const preBoard = physicalEnabled ? stonesToVisionBoard(stones, boardSize) : null;
              const result = placeStone(x, y);
              if (result?.sound) playSound(result.sound);
              // 试下是**屏幕上的自由探索**(识别已暂停),一次都不许喂给实体机器 ——
              // 喂一下就把它从 ready 顶出去了。
              if (physicalEnabled && !isTryMode && preBoard) physical.onScreenMove(result, preBoard);
            }}
          />
        </div>
        <div className="kiosk-board__ruler kiosk-board__ruler--right">
          {rowsFor(boardSize).map((r) => <span key={`r${r}`}>{r}</span>)}
        </div>
        <div className="kiosk-board__ruler kiosk-board__ruler--bottom">
          {colsFor(boardSize).map((c) => <span key={`b${c}`}>{c}</span>)}
        </div>
        <SuccessOverlay
          show={isSolved}
          message={t('tsumego:solved', '正确！')}
          onComplete={autoAdvanceEnabled ? handleAutoComplete : undefined}
          delayMs={1500}
        />
      </div>

      <div className="kiosk-rail">
        <KioskPagebar
          testId="puzzle-pagebar"
          backLabel={backLabel}
          onBack={backToUnit}
          title={interpolate(t('tsumego:problem_no', '第 {n} 题'), { n: currentIndex >= 0 ? currentIndex + 1 : 1 })}
          sub={`${levelName} · ${categoryName}`}
          // §11 只允许一个页级图标键。这一屏它只在**标定失效**时出现 ——
          // 实体棋盘开不了的时候,得有一条走得通的路,而不只是一句解释。
          action={physicalHint?.calibrate ? {
            icon: 'camera',
            label: t('tsumego:goCalibrate', '去标定'),
            onClick: () => navigate('/kiosk/vision/setup'),
          } : undefined}
        />

        <div className="panel">
          <h3>{t('tsumego:thisProblem', '这一题')}</h3>
          <p className="qtext" data-testid="puzzle-statement">
            {problem?.hint ? <b>{problem.hint}。</b> : null}
            {t(
              'Find the one move — judged on placement, a wrong move is taken straight back.',
              '找出那一手 —— 落子即判，走错当场退回。',
            )}
          </p>
          <div style={{ display: 'flex', gap: 8, marginTop: 12 }}>
            <span className="kiosk-tag">{categoryName}</span>
            <span className="kiosk-tag">{levelName}</span>
          </div>
        </div>

        <div className="railsec">
          <div className="rst">
            <span>{physicalEnabled ? t('tsumego:physicalBoard', '实体棋盘') : t('tsumego:yourMoves', '你的走法')}</span>
            <b data-testid="puzzle-counters">
              {t('Time', '用时')} {inPhysicalSetup ? t('tsumego:preparingBoard', '准备中') : formatTime(elapsedTime)}
              {/* 一次都没试过时**不写「0 次」** —— 和屏 13 同一条:0 次是一个次数,
                  「还没开始」不是。做对的那一次要算进去(`attempts` 数的是失败的那几次)。 */}
              {tries > 0 ? ` · ${interpolate(t('tsumego:tries_n', '{n} 次'), { n: tries })}` : ''}
              {lastDuration != null
                ? ` · ${t('tsumego:lastTimeShort', '上次')} ${formatTime(lastDuration)}`
                : ''}
            </b>
          </div>
          <div className="railsec__body">
            {/* 实体模式下这一块换成**盘上该做什么** —— 和「你的走法」是同一个位置上的同一件事
                (现在轮到我做什么),所以是**换内容不是加一块**:加一块会把动作区顶出右栏,
                而动作区贴底靠的是 margin-top:auto,顶出去就在画布外面了。 */}
            {physicalEnabled && !['off', 'ready', 'solved'].includes(physical.phase) ? (
              <div data-testid="puzzle-physical-guide">
                <PhysicalStatePanel state={physical} />
                {(physical.phase === 'clearing' || physical.phase === 'clearing_next') && (
                  <p className="qtext">
                    {t('tsumego:physClear', '请清空棋盘')}
                    {physical.extra.length > 0
                      ? interpolate(t('tsumego:physClearLeft', '（还剩 {n} 颗）'), { n: physical.extra.length })
                      : ''}
                  </p>
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
                  <p className="qtext">{t('tsumego:physReply', '请按棋盘灯光摆放棋子（应手 / 提子），让棋盘和屏幕一致。')}</p>
                )}
                {physical.phase === 'removing' && (
                  <p className="qtext">
                    {interpolate(
                      t('tsumego:physRemove', '答错了：请取回 {n} 颗棋子（蓝灯）'),
                      { n: physical.extra.length },
                    )}
                    {physical.missing.length > 0
                      ? interpolate(t('tsumego:physRestore', '，并放回被提的 {n} 颗（红 / 绿灯）'), { n: physical.missing.length })
                      : ''}
                  </p>
                )}
                {physical.phase === 'restoring' && (
                  <p className="qtext">{t('tsumego:physVerify', '正在核对棋盘和题面是否一致，请按灯光调整棋子。')}</p>
                )}
                {!physical.ledOk && (
                  <p className="qtext" data-testid="puzzle-led-down">
                    <b>{t('tsumego:physNoLed', 'LED 没连上，请按屏幕提示操作。')}</b>
                  </p>
                )}
              </div>
            ) : (
              <>
                {/* 摆盘完成的那一刻要说一句 —— 实体模式下人是**低头看盘**的,
                    屏幕不说「轮到你了、落哪一色」,他不知道机器已经准备好了。 */}
                {physicalEnabled && physical.phase === 'ready' && (
                  <p className="qtext" data-testid="puzzle-physical-ready">
                    <b>{t('tsumego:setupDone', '摆盘完成 · 轮到你了')}</b>
                    {' '}
                    {nextPlayer === 'B'
                      ? t('tsumego:placeAnswerBlack', '请在正解点落一手黑棋，棋盘会自动识别')
                      : t('tsumego:placeAnswerWhite', '请在正解点落一手白棋，棋盘会自动识别')}
                  </p>
                )}
                <div className="mvrows" data-testid="puzzle-moves">
                {moveHistory.length === 0 ? (
                  <>
                    <span className="n">—</span>
                    <span className="mv" style={{ color: 'var(--dim)' }}>{t('tsumego:noMoveYet', '还没落子')}</span>
                    <span className="mv" />
                  </>
                ) : (
                  moveHistory.map((m, i) => {
                    const last = i === moveHistory.length - 1;
                    // 判定只写在**最后一手**上:前面那些既没对也没错,是走到这儿的路。
                    const verdict = !last
                      ? ''
                      : isSolved
                        ? t('tsumego:solvedShort', '对了')
                        : isTryMode
                          ? t('tsumego:tryModeShort', '试下')
                          : isFailed
                            ? t('tsumego:wrongShort', '走错了')
                            : '';
                    return (
                      <Fragment key={`${m.coords[0]}-${m.coords[1]}-${i}`}>
                        <span className="n">{i + 1}</span>
                        <span className={last ? 'mv now' : 'mv'}>
                          {m.player === 'B' ? t('Black', '黑') : t('White', '白')} {coordLabel(m.coords[0], m.coords[1])}
                        </span>
                        <span className="mv" style={isFailed && last && !isTryMode ? { color: 'var(--bad)' } : undefined}>
                          {verdict}
                        </span>
                      </Fragment>
                    );
                  })
                )}
                </div>
              </>
            )}
          </div>
        </div>

        {/* 两个开关 + 右端一句「为什么那个开关是灰的」。`role="switch"` 不是 `aria-pressed`:
            后者是「这个按钮此刻被按住」,而这两个是**状态**。长相与对局屏那排逐字相同。 */}
        <div className="gtoggles gtoggles--switch" role="group" aria-label={t('tsumego:modes', '模式')}>
          <button
            type="button"
            role="switch"
            aria-checked={isTryMode}
            data-testid="try-mode-toggle"
            disabled={physicalEnabled && physical.phase !== 'ready'}
            onClick={() => (isTryMode ? exitTryMode() : enterTryMode())}
          >
            {t('Try', '试下')}
          </button>
          <button
            type="button"
            role="switch"
            aria-checked={physicalMode}
            data-testid="physical-mode-toggle"
            // 打开要看条件,**关掉永远允许** —— 条件掉了不能把人锁在一块死盘上。
            disabled={!physicalMode && !physicalAvailable}
            onClick={() => setPhysical(!physicalMode)}
          >
            {t('tsumego:physicalBoard', '实体棋盘')}
          </button>
          <i className="ghint" data-testid="puzzle-toggle-hint">{physicalHint?.text ?? ''}</i>
        </div>

        <div className="panel" data-testid="puzzle-unit">
          <h3>
            {unitNumber === null
              ? t('tsumego:unitUnknown', '这一单元')
              : `${interpolate(t('tsumego:unit_n', '第 {n} 单元'), { n: unitNumber })} · ${interpolate(t('tsumego:unit_total', '{n} 题'), { n: unitIds.length })}`}
          </h3>
          {unitIds.length > 0 ? (
            <div className="dots" data-testid="puzzle-dots">
              {unitIds.map((id) => (
                <i
                  key={id}
                  className={id === problemId ? 'now' : progress[id]?.completed ? 'ok' : undefined}
                />
              ))}
            </div>
          ) : (
            // 顺序表读不到 ⇒ 这一层**真的不知道**这道题在第几单元、旁边还有哪些题。
            // 点阵不画一排空格子冒充「都没做」,上/下一题也跟着灰 —— 两处同一个原因,写出来。
            <p className="qtext" data-testid="puzzle-no-sequence">
              {t('tsumego:noSequence', '读不到这一类的题号，上/下一题暂时用不了')}
            </p>
          )}
        </div>

        <KioskActions actions={actions} ariaLabel={t('tsumego:actions', '做题操作')} testId="puzzle-actions" />
      </div>
    </div>
  );
};

export default TsumegoProblemPage;
