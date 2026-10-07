import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';

import { ReportsAPI, type ReportTaskSummary } from '../../api/reportApi';
import LiveBoard, { type AiMoveMarker } from '../../components/live/LiveBoard';
import { useAuth } from '../../context/AuthContext';
import { winrateSeries } from '../../features/report/reportStats';
import { useReportDetail } from '../../features/report/useReportDetail';
import { useSound } from '../../hooks/useSound';
import { useTranslation } from '../../hooks/useTranslation';
import { requestFailureKind } from '../../utils/requestFailure';
import { sgfToMoves } from '../../utils/sgfSerializer';
import { translateResult } from '../../utils/resultTranslation';
import { kifuRulesLabel } from '../../features/kifu/kifuRules';
import { reportPlayerToMove } from '../../utils/reportPlayer';
import { ReportAnalysisRail } from '../components/report/ReportAnalysisRail';
import KioskReportPlayback from '../components/report/KioskReportPlayback';
import { failureLine, failureReason, outcomeLine, rowTitle, yourColor } from '../components/report/reviewPresentation';
import { colsFor, GO_COLS, rowsFor } from '../shell/goBoard';
import { Icon } from '../shell/icons';
import { KioskPagebar } from '../shell/KioskPagebar';
import { durationLabel, elapsedSeconds } from '../utils/durationLabel';
import { interpolate } from '../utils/interpolate';
import { whenLabel } from '../utils/whenLabel';

/**
 * 屏 20 · 复盘 · 报告 `/kiosk/report/:taskId` —— L2 布局 A(盘 516 + 16 + 右栏 460)。
 *
 * **四种棋里只有这一屏的胜率是真的**:报告任务离线跑完 KataGo,逐手 winrate 已经落在
 * `report_task_moves` 里。对局屏不画曲线、这一屏画,不是两套标准,是两个时刻 ——
 * 对局中要抢 Mali,复盘时不用抢。
 *
 * ## 盘那一圈坐标交给外壳画
 *
 * `LiveBoard` 是 canvas,坐标画在它自己里面;布局 A 的四条刻度带由外壳画(四棋类同一套几何)。
 * 两边都画就是两套坐标 —— 所以这里 `showCoordinates={false}`,而
 * **`calculateBoardLayout` 的边距必须跟着从 1.5 收回 0.5**:
 * 线的节距是 `W/(N−1+2·margin)`、刻度带的节距是 `W/N`,只有 margin=0.5 时两者相等。
 * 同一条不变式在 `TsumegoBoard` 上修过一次(Task 14),这次轮到 `LiveBoard`。
 *
 * ## 和稿子不一样的地方
 *
 * ① **滑块换成了「点曲线跳手」。** 稿子这一屏只有四个翻手键,没有滑块;可 187 手的谱
 *    靠四个键一手一手挪走不到第 120 手。原来那条 `PlaybackBar` 的功能落到曲线上 ——
 *    `TrendChart` 本来就支持点击跳手,换控件不能把它丢了。曲线上另画一条竖游标标出「现在在哪」。
 * ② **「用了 6 分 12 秒」现在写得出来了。** 2026-08-23 给 `ReportTaskStatus` 补上了
 *    `started_at` / `completed_at`(表里一直有、只是响应里没有),这一行因此按稿子写。
 *    **但拿不到就不写** —— 云端还没更新的盒子、或者两个章的时钟对不上时,
 *    `elapsedSeconds` 返回 `null`,这一行退回「一共多少手」那句本来就真的话。
 *    编一个耗时上去仍然是假数据,补了字段也不改这一条。
 * ③ **「重算」常驻**,不只在失败时出现。稿子把它和「去研究」并排画在题头 ——
 *    它的用处正是「跑完了但想换个深度再跑一遍」。
 *
 * ## 不再进「沉浸」——那是个会留下一条空带的 bug
 *
 * 这一屏原来 `setImmersive(true)`,而 `immersive` 在 `KioskLayout` 里只干一件事:
 * **把顶栏整块不渲染**。可 `.kiosk-content` 的 `top` 仍然是 `var(--topbar-h)`
 * (`tokens.css:419`),于是屏顶留下一条 **56 高的空黑带** —— 2026-08-23 四图当场看见。
 * 而规范 §5 防跳铁律 1 写死「顶栏永远占 y 0–56,任何层级、任何模块都不变高、不隐藏」,
 * 稿子这一屏画的也是有顶栏的。⇒ 这一屏不再进沉浸。
 * (2026-08-26 更正:屏 14 做题是最后一个现场,还完之后 `ImmersiveContext` 已整个删掉 ——
 *  顶栏现在**无条件渲染**,`KioskLayout.tsx` 上有那条注释,不再有开关可调。)
 */

const BACK_PATH = '/kiosk/report';

/**
 * 盘上格点 →「Q16」。和 `LiveBoard` 内部那个是同一套(跳过 I,y=0 在下)。
 * 用它把「点了盘上哪一格」换成「点的是不是某条 AI 推荐」。
 */
const coordAt = (x: number, y: number): string => `${GO_COLS[x] ?? '?'}${y + 1}`;

type Translate = (key: string, fallback?: string) => string;

function taskStatusLabel(status: string | undefined, t: Translate): string {
  if (status === 'pending') return t('report:queuing', '排队中');
  if (status === 'running') return t('report:generating', '生成中');
  if (status === 'completed') return t('report:completed', '已完成');
  if (status === 'failed') return t('report:failed', '失败');
  return t('report:unknown_status', '未知状态');
}

/**
 * `.rhead` 副行。三种局面各说各的话:
 *
 * | 任务 | 屏上 |
 * |---|---|
 * | 还没有 | 「这一局还没有报告任务」 |
 * | 排队 / 生成中 | 「已分析 a / b 手」—— 这时候「一共多少手」说的是将来,人想知道的是现在到哪儿了 |
 * | 跑完 / 失败 | 「每手算 N 次 · 用了 D」,拿不到耗时时退回「每手算 N 次 · M 手」 |
 *
 * **失败的任务落在最后一行、而且必然走退回那一支** —— 每条把任务放回队列的路
 * 都会清 `completed_at`(后端 `_mark_task_for_retry_or_failure` 与 `/retry` 各一处),
 * 所以「失败」和「跑完但拿不到章」在这里说同一句话,不需要单独判一次。
 */
function headMetaLine(task: ReportTaskSummary | null, fallbackTotalMoves: number, t: Translate): string {
  if (!task) return t('review:no_task', '这一局还没有报告任务');
  if (task.status === 'pending' || task.status === 'running') {
    return interpolate(t('review:analyzed_progress', '已分析 {a} / {b} 手'), {
      a: task.analyzed_moves, b: task.total_moves || fallbackTotalMoves,
    });
  }
  const visits = interpolate(t('review:visits_each', '每手算 {n} 次'), { n: task.requested_visits });
  const elapsed = elapsedSeconds(task.started_at, task.completed_at);
  const tail = elapsed === null
    ? `${task.total_moves || fallbackTotalMoves} ${t('report:moves_unit', '手')}`
    : interpolate(t('review:took', '用了 {d}'), { d: durationLabel(elapsed, t) });
  return `${visits} · ${tail}`;
}

function reportTypeLabel(reportType: string | undefined, t: Translate): string {
  if (reportType === 'deep') return t('report:deep', '深度报告');
  if (reportType === 'normal') return t('report:normal', '普通报告');
  return t('report:unknown_type', '类型未知');
}

export default function ReportDetailPage() {
  const { taskId } = useParams<{ taskId: string }>();
  const navigate = useNavigate();
  const { token, isAuthenticated, user } = useAuth();
  const { t } = useTranslation();
  const { play: playSound } = useSound();
  const {
    task, game, moves, analysisByMove, currentMove, setCurrentMove, loading, error, errorKind, refresh,
  } = useReportDetail(token, taskId, isAuthenticated);

  const [showCoordinates, setShowCoordinates] = useState(true);
  const [showAiMarkers, setShowAiMarkers] = useState(false);
  const [showMoveNumbers, setShowMoveNumbers] = useState(true);
  const [showTerritory, setShowTerritory] = useState(true);
  const reportIdentity = `${taskId || ''}:${task?.id || ''}:${game?.id || ''}`;
  const identityRef = useRef(reportIdentity);
  useLayoutEffect(() => { identityRef.current = reportIdentity; }, [reportIdentity]);
  const [tryModeState, setTryModeState] = useState<{ identity: string; enabled: boolean } | null>(null);
  const [tryState, setTryState] = useState<{ identity: string; baseMove: number; moves: string[] } | null>(null);
  const [activeVariation, setActiveVariation] = useState<{
    identity: string; position: number; move: string;
  } | null>(null);
  const [retryFailure, setRetryFailure] = useState<{ identity: string; message: string } | null>(null);
  const [retryingIdentity, setRetryingIdentity] = useState<string | null>(null);
  const tryMoveMode = tryModeState?.identity === reportIdentity && tryModeState.enabled;
  const tryMoves = tryState?.identity === reportIdentity && tryState.baseMove === currentMove
    ? tryState.moves
    : [];
  const retryError = retryFailure?.identity === reportIdentity ? retryFailure.message : null;
  const retrying = retryingIdentity === reportIdentity;

  // 屏上只说分出来的类别,原文不印 —— 但排障时总得有个地方能看见它。
  useEffect(() => {
    if (error != null) console.warn('[report-detail] error', error);
  }, [error]);

  const previousPosition = useRef<{ identity: string; move: number } | null>(null);
  useEffect(() => {
    if (!game) {
      previousPosition.current = null;
      return;
    }
    const soundIdentity = `${task?.id || taskId || ''}:${game.id}`;
    const previous = previousPosition.current;
    if (previous?.identity === soundIdentity && currentMove > 0 && previous.move !== currentMove) {
      playSound('stone');
    }
    previousPosition.current = { identity: soundIdentity, move: currentMove };
  }, [currentMove, game, playSound, task?.id, taskId]);

  const previewData = useMemo(() => {
    if (!game?.sgf_content) return null;
    try {
      return sgfToMoves(game.sgf_content);
    } catch {
      return null;
    }
  }, [game]);

  const currentAnalysis = analysisByMove[currentMove] ?? null;
  const recommendationSignature = currentAnalysis?.top_moves?.map((move) => move.move).join('\u0000') || '';
  const variationCandidate = activeVariation?.identity === reportIdentity
    && activeVariation.position === currentMove
    ? activeVariation.move
    : null;
  const activeMove = variationCandidate && currentAnalysis?.top_moves?.some((move) => move.move === variationCandidate)
    ? variationCandidate
    : null;

  // 渲染时先屏蔽过期的本地交互(上面),提交之后才真正丢掉 —— 被打断的并发渲染
  // 因此不会作废当前显示的状态。
  useEffect(() => {
    setTryModeState((previous) => (previous?.identity === reportIdentity ? previous : null));
    setTryState((previous) => (
      previous?.identity === reportIdentity && previous.baseMove === currentMove ? previous : null
    ));
    setActiveVariation((previous) => (
      previous?.identity === reportIdentity
      && previous.position === currentMove
      && recommendationSignature.split('\u0000').includes(previous.move)
        ? previous
        : null
    ));
    setRetryFailure((previous) => (previous?.identity === reportIdentity ? previous : null));
  }, [currentMove, recommendationSignature, reportIdentity]);

  const boardSize = previewData?.metadata.boardSize || game?.board_size || 19;
  /**
   * 让子局里这两套下标不是一回事:`previewData.moves` 开头那几个是摆上去的让子石,
   * 而报告的 `move_number` 只数真正的着手(后端把摆子走 `initialStones`)。
   * 盘上的游标因此要加回这个偏移,滑杆的上限要减掉它 —— 不这么做,让子局滑到第 k 手
   * 时盘面是对的、右边的分析却是第 k+让子数 手的,**屏上没有任何东西会说它错位了**。
   */
  const setupCount = previewData?.setupCount ?? 0;
  const boardCursor = currentMove + setupCount;
  const playerToMove = reportPlayerToMove(previewData?.stoneColors, boardCursor, setupCount);
  const totalMoves = previewData
    ? Math.max(0, previewData.moves.length - setupCount)
    : (game?.move_count || 0);
  const ownership = currentAnalysis?.ownership || null;

  const aiMarkers = useMemo((): AiMoveMarker[] | null => {
    if (!currentAnalysis?.top_moves?.length) return null;
    return currentAnalysis.top_moves.slice(0, 5).map((move, index) => ({
      move: move.move,
      rank: index + 1,
      visits: move.visits,
      winrate: playerToMove === 'B' ? move.winrate ?? 0 : 1 - (move.winrate ?? 0),
      score_lead: playerToMove === 'B' ? move.score_lead ?? 0 : -(move.score_lead ?? 0),
    }));
  }, [currentAnalysis, playerToMove]);

  const pvMoves = useMemo(() => {
    if (!activeMove) return null;
    return currentAnalysis?.top_moves?.find((move) => move.move === activeMove)?.pv ?? null;
  }, [activeMove, currentAnalysis]);

  const points = useMemo(() => winrateSeries(moves), [moves]);

  /** 目差那条曲线。和胜率同一条 x 轴(按手数),`score_lead` 与 winrate 同为**黑方视角**。 */
  const leadPoints = useMemo(
    () => moves
      .filter((m) => m.score_lead != null)
      .map((m) => ({ moveNumber: m.move_number, scoreLead: m.score_lead as number })),
    [moves],
  );

  const handleMoveChange = useCallback((move: number) => {
    setActiveVariation(null);
    setCurrentMove(move);
  }, [setCurrentMove]);

  const handleTryToggle = useCallback(() => {
    setTryModeState({ identity: reportIdentity, enabled: !tryMoveMode });
    if (tryMoveMode) setTryState(null);
    setActiveVariation(null);
  }, [reportIdentity, tryMoveMode]);

  const handleRefresh = useCallback(async () => {
    const requestIdentity = reportIdentity;
    await refresh();
    if (identityRef.current === requestIdentity) setRetryFailure(null);
  }, [refresh, reportIdentity]);

  const handleRetryReport = useCallback(async () => {
    const id = Number(taskId);
    if (!isAuthenticated || !Number.isSafeInteger(id) || id <= 0) return;
    const requestIdentity = reportIdentity;
    setRetryingIdentity(requestIdentity);
    setRetryFailure(null);
    try {
      await refresh();
      if (identityRef.current !== requestIdentity) return;
      await ReportsAPI.retry(token, id);
      if (identityRef.current !== requestIdentity) return;
      await refresh();
      if (identityRef.current === requestIdentity) setRetryFailure(null);
    } catch (failure) {
      console.warn('[report-detail] recompute', failure);
      if (identityRef.current === requestIdentity) {
        // 不印原文:盒上断网时 failure.message 是 `Request failed 503: {…}`。
        // 「没发出去」这四个字只对连不上网成立 —— 402/400 是服务端收到了、判断之后拒收的,
        // 说「没发出去」是在替一个已经处理过的请求撒谎。
        setRetryFailure({
          identity: requestIdentity,
          message: failureLine(t('review:recompute_failed', '重算没成'), requestFailureKind(failure), t),
        });
      }
    } finally {
      if (identityRef.current === requestIdentity) setRetryingIdentity(null);
    }
  }, [isAuthenticated, refresh, reportIdentity, t, taskId, token]);

  const shell = (body: React.ReactNode) => (
    <div className="kiosk-rail" data-testid="report-detail-shell">
      <KioskPagebar
        testId="report-detail-pagebar"
        backLabel={t('review:back_review', '复盘')}
        onBack={() => navigate(BACK_PATH)}
        title={t('report:my_reports', '复盘')}
      />
      {body}
    </div>
  );

  if (!isAuthenticated) {
    return shell(
      <div className="empty"><h4>{t('report:login_required_detail', '请先登录后查看报告详情。')}</h4></div>,
    );
  }
  if (loading && !game) {
    return shell(
      <div className="empty" data-testid="report-detail-loading">
        <h4>{t('report:loading_detail', '正在加载复盘')}</h4>
      </div>,
    );
  }
  if (!game) {
    // 「连不上」和「没有这份报告」是两件事。以前一律写「未找到复盘。」,再把后端原文印在下面 ——
    // 盒上报告接口全走云端,断网时就是 503,屏上却说「未找到」(2026-09-14 调研 N24)。
    // `not_found` 只来自报告接口(云端 404 原码透传)或非法 id;对局那一路的 404 钩子里已降为 other。
    const kind = error ? (errorKind ?? 'other') : 'not_found';
    const reason = kind === 'not_found' ? '' : failureReason(kind, t);
    return shell(
      <div className="empty" data-testid="report-detail-error" data-failure={kind}>
        <h4>{kind === 'not_found' ? t('report:not_found', '未找到复盘。') : t('review:detail_failed', '这份报告没读出来')}</h4>
        {reason && <p>{reason}</p>}
        <button type="button" className="kiosk-btn kiosk-btn--pill pill" onClick={() => void handleRefresh()}>
          {t('report:retry_load', '重试加载')}
        </button>
      </div>,
    );
  }
  if (!previewData) {
    return shell(
      <div className="empty" data-testid="report-detail-no-sgf">
        <h4>{t('report:no_sgf', '没有可用于复盘展示的 SGF 数据。')}</h4>
        <button type="button" className="kiosk-btn kiosk-btn--pill pill" onClick={() => void handleRefresh()}>
          {t('report:reload', '重新加载')}
        </button>
      </div>,
    );
  }

  const mine = yourColor(game, user?.username);
  const title = rowTitle(game, mine, t);
  // 副标和复盘列表那一行念的是同一句话 —— 同一局在两屏之间不许改口。
  const savedTs = game.created_at || game.game_date;
  const savedAt = savedTs ? new Date(savedTs).getTime() : NaN;
  const sub = [
    outcomeLine(game, mine, t),
    game.result ? `${game.move_count} ${t('report:moves_unit', '手')}` : null,
    Number.isNaN(savedAt) ? null : whenLabel(savedAt, t),
  ].filter(Boolean).join(' · ');

  return (
    <div className="kiosk-layout-a report-analysis-layout" data-testid="report-detail-page">
      {/* 四条刻度带由**外壳**画(四棋类同一套几何),盘自己那一圈坐标因此关掉 ——
          两边都画就是两套坐标,字号字色还不是同一套。 */}
      <div className="kiosk-board" data-coordinates={showCoordinates} data-testid="report-detail-board">
        <div className="kiosk-board__ruler kiosk-board__ruler--top">
          {colsFor(boardSize).map((c) => <span key={`t${c}`}>{c}</span>)}
        </div>
        <div className="kiosk-board__ruler kiosk-board__ruler--left">
          {rowsFor(boardSize).map((r) => <span key={`l${r}`}>{r}</span>)}
        </div>
        <div className="kiosk-board__play">
          <LiveBoard
            moves={previewData.moves}
            stoneColors={previewData.stoneColors}
            currentMove={boardCursor}
            nextColor={playerToMove}
            boardSize={boardSize}
            showCoordinates={false}
            pvMoves={pvMoves}
            aiMarkers={aiMarkers}
            aiMarkerLimit={5}
            showAiMarkers={showAiMarkers}
            showMoveNumbers={showMoveNumbers}
            showTerritory={showTerritory}
            ownership={showTerritory ? ownership : null}
            minContainerHeight={0}
            tryMoves={tryMoveMode ? tryMoves : undefined}
            onTryMove={tryMoveMode ? (move) => setTryState((previous) => ({
              identity: reportIdentity,
              baseMove: currentMove,
              moves: [
                ...(previous?.identity === reportIdentity && previous.baseMove === currentMove
                  ? previous.moves
                  : []),
                move,
              ],
            })) : undefined}
            // 盘上的标记与候选行都可打开变化，点其它位置关闭。
            onIntersectionClick={!tryMoveMode ? (x, y) => {
              const coord = coordAt(x, y);
              const hit = showAiMarkers && aiMarkers?.some((m) => m.move === coord);
              setActiveVariation(hit ? { identity: reportIdentity, position: currentMove, move: coord } : null);
            } : undefined}
          />
        </div>
        <div className="kiosk-board__ruler kiosk-board__ruler--right">
          {rowsFor(boardSize).map((r) => <span key={`r${r}`}>{r}</span>)}
        </div>
        <div className="kiosk-board__ruler kiosk-board__ruler--bottom">
          {colsFor(boardSize).map((c) => <span key={`b${c}`}>{c}</span>)}
        </div>
      </div>

      <ReportAnalysisRail
        key={reportIdentity}
        testId="report-detail"
        players={[game.player_black || t('review:black', '黑'), game.player_white || t('review:white', '白')]}
        pagebar={(<KioskPagebar
          testId="report-detail-pagebar"
          backLabel={t('review:back_review', '复盘')}
          onBack={() => navigate(BACK_PATH)}
          title={title}
          sub={sub}
        />)}
        analysis={currentAnalysis} analysisByMove={analysisByMove}
        playerToMove={playerToMove} actualMove={previewData.moves[boardCursor]}
        currentMove={currentMove} totalMoves={totalMoves} points={points} lead={leadPoints}
        onMoveClick={handleMoveChange} activeMove={activeMove}
        onCandidateClick={(move) => {
          setTryModeState(null); setTryState(null);
          setActiveVariation(activeMove === move ? null : { identity: reportIdentity, position: currentMove, move });
        }}
        status={(<div className="report-analysis-rail__status" data-testid="report-detail-rhead">
          <span data-testid="report-detail-status">{taskStatusLabel(task?.status, t)} · {reportTypeLabel(task?.report_type, t)}</span>
          <span data-testid="report-detail-progress">{headMetaLine(task, totalMoves, t)}</span>
        </div>)}
        statusVisible={task?.status !== 'completed'}
        metadata={(<div className="report-analysis-rail__status" data-testid="report-detail-metadata">
          <span>{game.result ? translateResult(game.result, t, game.rules) : '—'}</span>
          <span>{kifuRulesLabel(game.rules, t)} · {t('report:komi_label', '贴目')} {game.komi ?? '—'}</span>
        </div>)}
        details={[
          [t('review:black', '黑'), [game.player_black, game.black_rank].filter(Boolean).join(' · ')],
          [t('review:white', '白'), [game.player_white, game.white_rank].filter(Boolean).join(' · ')],
          [t('report:event', '赛事'), [game.event, game.round_name].filter(Boolean).join(' · ')],
          [t('report:date', '日期'), game.game_date || game.created_at],
          [t('report:result', '结果'), game.result],
          [t('report:rules', '规则'), game.rules],
          [t('report:komi', '贴目'), game.komi],
          [t('report:status', '状态'), taskStatusLabel(task?.status, t)],
          [t('report:source', '来源'), game.source],
        ]}
        detailActions={(<><button
              type="button"
              className="kiosk-btn kiosk-btn--pill"
              onClick={() => navigate(`/kiosk/research?${new URLSearchParams({ user_game_id: game.id, from: 'report', task: String(taskId) }).toString()}`)}
            >
              {t('review:to_research', '去研究')}
            </button>
            <button
              type="button"
              className="kiosk-btn kiosk-btn--pill"
              disabled={retrying || !task}
              onClick={() => void handleRetryReport()}
            >
              {retrying ? t('report:retrying', '正在重试…') : t('review:recompute', '重算')}
            </button>
          </>)}
        actions={(<>
          <button type="button" aria-pressed={tryMoveMode} onClick={handleTryToggle}>
            <Icon name="hand-pointing" />{t('report:try', '试下')}
          </button>
          <button type="button" aria-pressed={showTerritory} disabled={!ownership} onClick={() => setShowTerritory((v) => !v)}><Icon name="map-trifold" />{t('report:territory', '领地')}</button>
          <button type="button" aria-pressed={showAiMarkers} onClick={() => setShowAiMarkers((v) => !v)}>
            <Icon name="lightbulb" />{t('Advice', '支招')}
          </button>
          </>)}
        toggles={(<>
          <button type="button" aria-pressed={showMoveNumbers} onClick={() => setShowMoveNumbers((v) => !v)}><Icon name="list-numbers" />{t('report:move_numbers', '手数')}</button>
          <button type="button" aria-pressed={showCoordinates} onClick={() => setShowCoordinates((v) => !v)}>
            <Icon name="corners-out" />{t('Coordinates', '坐标')}
          </button>
          <button type="button" disabled={!activeMove && tryMoves.length === 0} onClick={() => { setTryState(null); setActiveVariation(null); }}>{t('report:clear', '清空')}</button>
        </>)}
        notices={(<>{(error || retryError) && (
          <p className="rverr" role="status" data-testid="report-detail-alert">
            {retryError ?? failureLine(t('review:refresh_failed', '没刷新成功'), errorKind ?? 'other', t)}
            <button type="button" className="kiosk-btn kiosk-btn--pill" onClick={() => void handleRefresh()}>
              {t('report:retry_load', '重试加载')}
            </button>
          </p>
        )}{tryMoveMode && tryMoves.length > 0 && (
          <p className="rverr" role="status" data-testid="report-detail-try">
            {t('report:try', '试下')}: {tryMoves.join(' → ')}
          </p>
        )}
        {activeMove && (
          <p className="rverr" role="status" data-testid="report-detail-variation">
            {t('report:variation_preview', '变化预览 · 点击棋盘关闭')}
            <button type="button" className="kiosk-btn kiosk-btn--pill" onClick={() => setActiveVariation(null)}>
              {t('report:clear_variation', '清除变化')}
            </button>
          </p>
        )}</>)}
        navigation={<KioskReportPlayback testId="report-detail-movenav" currentMove={currentMove} totalMoves={totalMoves} onMoveChange={handleMoveChange} />}
      />
    </div>
  );
}
