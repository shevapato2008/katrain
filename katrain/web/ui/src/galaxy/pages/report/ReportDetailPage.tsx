/**
 * ReportDetailPage —— 复盘·报告详情页
 *
 * 版式：走统一的 `BoardPageShell`（spec §2.2/§2.3）—— 棋盘是唯一连续伸缩区域，
 * 棋盘正上方不放任何东西，右栏三段：模块牌 / 中段（唯一可滚）/ 动作区。
 *
 * 迁版式前这里是手写的两栏 flex：返回键 + 「黑 vs 白」+ 「进入研究室」压在棋盘正上方，
 * 右栏写死 `width: 500`、自带一层底色，且**没有 <900 的形态**（右栏不让位，棋盘被挤扁）。
 *
 * 这一页和直播观战页（`live/LiveMatchPage`）是同一组零件：LiveBoard / AiAnalysis /
 * TrendChart / PlaybackBar，连显示开关都是同一组（试下·领地·手数·建议·坐标）。
 * 所以显示开关直接复用 `live/LiveMatchDisplayControls`，不再在这里写第二份 —— 迁版式前
 * 这里那个 `ToggleButtonGroup` 就是它的一份手抄，还多抄错了一处：「领地」按有没有 ownership
 * 分成了两个几乎相同的分支（其中 disabled 那支连 Tooltip 都掉了，也就没人告诉用户为什么按不动）。
 */

import { useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { Alert, Box, Button, CircularProgress, Skeleton } from '@mui/material';

import LiveBoard, { type AiMoveMarker } from '../../../components/live/LiveBoard';
import { useAuth } from '../../../context/AuthContext';
import { useSound } from '../../../hooks/useSound';
import { useTranslation } from '../../../hooks/useTranslation';
import { sgfToMoves } from '../../../utils/sgfSerializer';
import { reportPlayerToMove } from '../../../utils/reportPlayer';
import { useReportDetail } from '../../../features/report/useReportDetail';
import AiAnalysis from '../../../components/live/AiAnalysis';
import PlaybackBar from '../../../components/live/PlaybackBar';
import TrendChart from '../../../components/live/TrendChart';
import ReportMetaPanel from '../../components/report/ReportMetaPanel';
import ReportAnalysisLayout from '../../components/report/ReportAnalysisLayout';
import BoardPageShell from '../../components/board/BoardPageShell';
import ModulePlate from '../../components/layout/ModulePlate';
import { useBoardCoordinates } from '../../components/board/useBoardCoordinates';
import LiveMatchDisplayControls from '../live/LiveMatchDisplayControls';
import ReplayBoard3D from '../../components/board/ReplayBoard3D';

const BACK_TO = '/galaxy/report';

// 三个早退形态（未登录 / 加载中 / 出错）也走同一副骨架 —— 照 `LiveMatchPage.tsx:79-125`。
// 迁版式前它们是裸 `Box p={4}`，于是「棋盘正上方不放任何东西」这条在错误态下等于没实现。
/* 占位不是控件 —— 与 `LiveMatchPage` 同一处修正（那份是原件，这份是抄件）。
   原来是 `<Button disabled><Skeleton/></Button>`，按构造就没有可及名。 */
const LoadingControls = () => (
  <Box sx={{ py: 2, display: 'grid', gridTemplateColumns: 'repeat(4, minmax(0, 1fr))', gap: '6px' }}>
    {Array.from({ length: 4 }, (_, index) => (
      <Skeleton key={index} variant="rounded" height={54} />
    ))}
  </Box>
);

const LoadingActions = () => (
  <Box sx={{ py: 2 }}>
    <Skeleton variant="rounded" height={40} />
  </Box>
);

export default function ReportDetailPage() {
  const { taskId } = useParams();
  const navigate = useNavigate();
  const { token, isAuthenticated } = useAuth();
  const { t } = useTranslation();

  const {
    task,
    game,
    analysisByMove,
    currentMove,
    setCurrentMove,
    loading,
    error,
  } = useReportDetail(token, taskId, isAuthenticated);
  const [view3d, setView3d] = useState(false);
  const [pvMoves, setPvMoves] = useState<string[] | null>(null);
  const [showAiMarkers, setShowAiMarkers] = useState(true);
  const [showMoveNumbers, setShowMoveNumbers] = useState(false);
  const [showTerritory, setShowTerritory] = useState(false);
  const [tryMoveMode, setTryMoveMode] = useState(false);
  const [tryMoves, setTryMoves] = useState<string[]>([]);
  const [boardEdge, setBoardEdge] = useState(0);
  const coordinates = useBoardCoordinates(boardEdge);

  // Sound on move navigation
  const { play: playSound } = useSound();
  const prevMoveRef = useRef<number | null>(null);

  useEffect(() => {
    if (currentMove > 0 && prevMoveRef.current !== null && currentMove !== prevMoveRef.current) {
      playSound('stone');
    }
    prevMoveRef.current = currentMove;
  }, [currentMove, playSound]);

  const previewData = useMemo(() => {
    if (!game?.sgf_content) return null;
    return sgfToMoves(game.sgf_content);
  }, [game]);

  const currentAnalysis = analysisByMove[currentMove] || null;
  const setupCount = previewData?.setupCount ?? 0;
  const boardCursor = currentMove + setupCount;
  const playerToMove = reportPlayerToMove(previewData?.stoneColors, boardCursor, setupCount);

  const aiMarkers = useMemo((): AiMoveMarker[] | null => {
    if (!showAiMarkers || !currentAnalysis?.top_moves?.length) return null;
    return currentAnalysis.top_moves.slice(0, 5).map((topMove, index) => ({
      move: topMove.move,
      rank: index + 1,
      visits: topMove.visits,
      winrate: playerToMove === 'B' ? topMove.winrate ?? 0 : 1 - (topMove.winrate ?? 0),
      score_lead: playerToMove === 'B' ? topMove.score_lead ?? 0 : -(topMove.score_lead ?? 0),
    }));
  }, [currentAnalysis, showAiMarkers, playerToMove]);

  const ownership = showTerritory ? currentAnalysis?.ownership || null : null;
  const boardSize = previewData?.metadata.boardSize || game?.board_size || 19;
  // 让子局:`moves` 开头是摆子,报告的 move_number 只数着手。见 kiosk 同名页那段注释。
  const totalMoves = previewData ? Math.max(0, previewData.moves.length - setupCount) : 0;

  if (!isAuthenticated) {
    return (
      <BoardPageShell
        onBoardSizeChange={setBoardEdge}
        /* 未登录和出错都**不是加载态** —— 脉动的骨架屏在说「东西还在路上」，
           而这两屏都已经定局了。静止占位 + 不挂 `displayControls`/`actions`：
           没有对局可显示，就没有可开关的东西。 */
        board={<Skeleton data-testid="board-unauthenticated-skeleton" variant="rectangular" animation={false} width="100%" height="100%" />}
        modulePlate={<ModulePlate title={t('report:review', '复盘')} backTo={BACK_TO} />}
        railBody={(
          <Box sx={{ py: 2 }}>
            <Alert severity="info">{t('report:login_required_detail', 'Please log in to view report details.')}</Alert>
          </Box>
        )}
        actions={null}
      />
    );
  }

  if (loading) {
    return (
      <BoardPageShell
        onBoardSizeChange={setBoardEdge}
        board={<Skeleton data-testid="board-loading-skeleton" variant="rectangular" width="100%" height="100%" />}
        modulePlate={(
          <ModulePlate
            title={t('report:loading_detail', '正在打开复盘')}
            subtitle={<Skeleton width={180} />}
            status={<CircularProgress size={22} />}
            backTo={BACK_TO}
          />
        )}
        railBody={<Box sx={{ py: 2 }}><Skeleton height={120} /><Skeleton height={160} /><Skeleton height={180} /></Box>}
        displayControls={<LoadingControls />}
        actions={<LoadingActions />}
      />
    );
  }

  if (error) {
    return (
      <BoardPageShell
        onBoardSizeChange={setBoardEdge}
        board={<Skeleton data-testid="board-error-skeleton" variant="rectangular" animation={false} width="100%" height="100%" />}
        modulePlate={<ModulePlate title={t('report:review', '复盘')} backTo={BACK_TO} />}
        railBody={(
          <Box sx={{ py: 2 }}>
            <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>
            <Button
              variant="outlined"
              onClick={() => navigate(BACK_TO)}
              sx={{ minWidth: 96, minHeight: 40 }}
            >
              {t('report:back_to_list', 'Back to review list')}
            </Button>
          </Box>
        )}
        actions={null}
      />
    );
  }

  return (
    <BoardPageShell
      onBoardSizeChange={setBoardEdge}
      board={previewData ? (
        view3d ? <ReplayBoard3D moves={previewData.moves} stoneColors={previewData.stoneColors} currentMove={boardCursor} boardSize={boardSize} handicapCount={setupCount} showCoordinates={coordinates.visible} showMoveNumbers={showMoveNumbers} showAiMarkers={showAiMarkers} aiMarkers={aiMarkers} showTerritory={showTerritory} ownership={ownership} tryMoves={tryMoveMode ? tryMoves : undefined} onTryMove={tryMoveMode ? (move) => setTryMoves((prev) => [...prev, move]) : undefined} /> : <LiveBoard
          moves={previewData.moves}
          stoneColors={previewData.stoneColors}
          currentMove={boardCursor}
          nextColor={playerToMove}
          pvMoves={pvMoves}
          boardSize={boardSize}
          aiMarkers={aiMarkers}
          aiMarkerLimit={5}
          showAiMarkers={showAiMarkers}
          showMoveNumbers={showMoveNumbers}
          showTerritory={showTerritory}
          showCoordinates={coordinates.visible}
          ownership={ownership}
          tryMoves={tryMoveMode ? tryMoves : undefined}
          onTryMove={tryMoveMode ? (move: string) => setTryMoves((prev) => [...prev, move]) : undefined}
          /* 两个 400px 地板必须关掉。默认值（LiveBoard.tsx:325-326）会给根 Box 加
             `minHeight: 400`，在 shell 那个 `aspectRatio: 1/1` 的定尺格里就是「越量越大」，
             1024×768 和 430×880 两档必然撑破。已迁的两页同样传 0/0。 */
          minimumCanvasSize={0}
          minContainerHeight={0}
        />
      ) : (
        <Alert severity="info">{t('report:no_sgf', 'No SGF data available for review.')}</Alert>
      )}
      fixedRail
      modulePlate={null}
      railBody={(
        <ReportAnalysisLayout
          identity={<ReportMetaPanel game={game} task={task} currentMove={currentMove} currentAnalysis={currentAnalysis} backTo={BACK_TO} />}
          recommendations={<>
            {task?.status !== 'completed' && <Alert severity={task?.status === 'failed' ? 'error' : 'info'} sx={{ py: 0, '& .MuiAlert-message': { fontSize: 18 } }}>{task?.status === 'running' ? `${t('report:generating', '分析中')} · ${task.analyzed_moves} / ${task.total_moves} ${t('live:moves', '手')}` : task?.status === 'failed' ? t('report:failed', '分析失败') : t('report:queuing', '等待分析')}</Alert>}
            <AiAnalysis currentMove={currentMove} analysis={analysisByMove} onMoveHover={setPvMoves} topN={5} reportMode playerToMove={playerToMove} actualMove={previewData?.moves[boardCursor]} />
          </>}
          analysis={<Box data-testid="report-trend-region" sx={{ height: '100%', minHeight: 0 }}><TrendChart reportMode analysis={analysisByMove} totalMoves={totalMoves} currentMove={currentMove} onMoveClick={setCurrentMove} /></Box>}
          controls={<LiveMatchDisplayControls
            reportMode
            tryMoveMode={tryMoveMode}
            showTerritory={showTerritory}
            showMoveNumbers={showMoveNumbers}
            showAiMarkers={showAiMarkers}
            showCoordinates={coordinates.visible}
            view3d={view3d}
            ownershipAvailable={currentAnalysis?.ownership != null}
            tryMoves={tryMoves}
            onTryMoveToggle={() => {
              setTryMoveMode((enabled) => !enabled);
              if (tryMoveMode) setTryMoves([]);
            }}
            onTerritoryToggle={() => setShowTerritory((visible) => !visible)}
            onMoveNumbersToggle={() => setShowMoveNumbers((visible) => !visible)}
            onAiMarkersToggle={() => setShowAiMarkers((visible) => !visible)}
            onCoordinatesToggle={coordinates.toggle}
            on3dToggle={() => setView3d((value) => !value)}
            onClearTryMoves={() => setTryMoves([])}
          />}
          navigation={<PlaybackBar inline currentMove={currentMove} totalMoves={totalMoves} onMoveChange={setCurrentMove} />}
        />
      )}
      actions={null}
    />
  );
}
