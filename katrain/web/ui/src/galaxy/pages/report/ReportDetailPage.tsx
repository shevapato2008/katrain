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
import ScienceIcon from '@mui/icons-material/Science';
import { Alert, Box, Button, CircularProgress, Skeleton } from '@mui/material';

import LiveBoard, { type AiMoveMarker } from '../../../components/live/LiveBoard';
import { useAuth } from '../../../context/AuthContext';
import { useSound } from '../../../hooks/useSound';
import { useTranslation } from '../../../hooks/useTranslation';
import { sgfToMoves } from '../../../utils/sgfSerializer';
import { useReportDetail } from '../../../features/report/useReportDetail';
import AiAnalysis from '../../../components/live/AiAnalysis';
import PlaybackBar from '../../../components/live/PlaybackBar';
import TrendChart from '../../../components/live/TrendChart';
import ReportMetaPanel from '../../components/report/ReportMetaPanel';
import BoardPageShell from '../../components/board/BoardPageShell';
import ModulePlate from '../../components/layout/ModulePlate';
import { useBoardCoordinates } from '../../components/board/useBoardCoordinates';
import LiveMatchDisplayControls from '../live/LiveMatchDisplayControls';

const BACK_TO = '/galaxy/report';

// 三个早退形态（未登录 / 加载中 / 出错）也走同一副骨架 —— 照 `LiveMatchPage.tsx:79-125`。
// 迁版式前它们是裸 `Box p={4}`，于是「棋盘正上方不放任何东西」这条在错误态下等于没实现。
/* 占位不是控件 —— 与 `LiveMatchPage` 同一处修正（那份是原件，这份是抄件）。
   原来是 `<Button disabled><Skeleton/></Button>`，按构造就没有可及名。 */
const LoadingControls = () => (
  <Box sx={{ p: 2, display: 'grid', gridTemplateColumns: 'repeat(4, minmax(0, 1fr))', gap: '6px' }}>
    {Array.from({ length: 4 }, (_, index) => (
      <Skeleton key={index} variant="rounded" height={54} />
    ))}
  </Box>
);

const LoadingActions = () => (
  <Box sx={{ p: 2 }}>
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
  } = useReportDetail(isAuthenticated ? token : null, taskId);
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

  const aiMarkers = useMemo((): AiMoveMarker[] | null => {
    if (!showAiMarkers || !currentAnalysis?.top_moves?.length) return null;
    return currentAnalysis.top_moves.slice(0, 3).map((topMove, index) => ({
      move: topMove.move,
      rank: index + 1,
      visits: topMove.visits,
      winrate: topMove.winrate ?? 0,
      score_lead: topMove.score_lead ?? 0,
    }));
  }, [currentAnalysis, showAiMarkers]);

  const ownership = showTerritory ? currentAnalysis?.ownership || null : null;
  const boardSize = previewData?.metadata.boardSize || game?.board_size || 19;
  // 让子局:`moves` 开头是摆子,报告的 move_number 只数着手。见 kiosk 同名页那段注释。
  const setupCount = previewData?.setupCount ?? 0;
  const boardCursor = currentMove + setupCount;
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
          <Box sx={{ p: 2 }}>
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
        railBody={<Box sx={{ p: 2 }}><Skeleton height={120} /><Skeleton height={160} /><Skeleton height={180} /></Box>}
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
          <Box sx={{ p: 2 }}>
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

  const black = game?.player_black || t('report:black', 'Black');
  const white = game?.player_white || t('report:white', 'White');

  /* 「进入研究室」带着这一局走。改版前它是 `navigate('/galaxy/research')` —— 不带任何
     棋局参数，点进去是一张空棋盘（冻结稿 V2 的注释：「现状漏了棋局参数，改版补上」）。
     Fan 2026-08-22 点头补上。

     参数用 `user_game_id`（`user_games` 那套 uuid），不是 `kifu_id` —— 研究页原有的
     `?kifu_id=` 走的是棋谱库 `KifuAPI.getAlbum`，是**另一个 id 空间**；把报告的
     game id 塞进去只会加载到一局无关的棋，比不跳转更坏。

     不带 `&analyze=1`：这一局报告页已经分析过一遍，进研究室是为了摆变化；而全盘扫描
     是计费动作，不该由一次导航悄悄触发。要分析就在研究页按「开始研究」。 */
  const researchHref = game?.id
    ? `/galaxy/research?user_game_id=${encodeURIComponent(game.id)}`
    : null;

  return (
    <BoardPageShell
      onBoardSizeChange={setBoardEdge}
      board={previewData ? (
        <LiveBoard
          moves={previewData.moves}
          stoneColors={previewData.stoneColors}
          currentMove={boardCursor}
          pvMoves={pvMoves}
          boardSize={boardSize}
          aiMarkers={aiMarkers}
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
      modulePlate={(
        <ModulePlate
          title={`${black} vs ${white}`}
          subtitle={`${currentMove} / ${totalMoves} ${t('live:moves', '手')}`}
          /* 返回键在右栏左上角（Fan 2026-08-22 裁定，见 ModulePlate 的注释）。
             `backLabel` 不上屏，只把无障碍名做成「返回复盘」。
             报告状态/类型仍留在右栏的 ReportMetaPanel 里 —— 规范 §2.4「chip 一律不进
             页头」那半句没有被这次裁定推翻，继续有效。 */
          backTo={BACK_TO}
          backLabel={t('report:review', '复盘')}
        />
      )}
      railBody={(
        <>
          <ReportMetaPanel
            game={game}
            task={task}
            currentMove={currentMove}
            currentAnalysis={currentAnalysis}
          />
          {/* 显示开关紧跟在对局信息之后，而不是 shell 的 `displayControls` 槽。
              冻结稿 V2 把它放在中段最末，但那是按稿子里那份**很短**的假数据排的；
              真数据下（250 手的报告，AI 推荐 3 行 + 失误 24 条）它会掉到折线以下
              208px（1440×900）/ 389px（1024×768），要滚一屏才够得着 —— 迁版式前它
              就在对局信息下面、一直可见。稿子的意图是「不用滚就能看见」（参考图里
              它是露着的），真数据下只有放在这里才成立。
              顺序也与死活题页一致：身份块（本题 / 对局信息）→ 工具格 → 其余内容。
              **直播页可能有同样的问题，但本机没有直播数据量不到，记进待议。** */}
          <LiveMatchDisplayControls
            tryMoveMode={tryMoveMode}
            showTerritory={showTerritory}
            showMoveNumbers={showMoveNumbers}
            showAiMarkers={showAiMarkers}
            showCoordinates={coordinates.visible}
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
            onClearTryMoves={() => setTryMoves([])}
          />

          <Box sx={{ borderBottom: 1, borderColor: 'divider' }}>
            {/* 人类倾向那一列**有意不开**。2026-09-01 Fan 裁定「先不加了，规则不统一，
                没有很好的产品价值」—— 依据是同一手在 rank_5k 下 86.3%、rank_5d 下 27.4%
                （实测第 98 手 H9，五档对照见当日会话），固定一个档位对职业棋谱和对新手
                都不贴切，那个数没法自证该信谁。
                组件侧的实现与测试保留（`AiAnalysis` 的 `showHumanTendency` 默认 false），
                将来若按「跟看的人走」重做参照系，把这个 prop 加回来即可。 */}
            <AiAnalysis currentMove={currentMove} analysis={analysisByMove} onMoveHover={setPvMoves} />
          </Box>
          {/* TrendChart 自带 `height:100%` + 内部 `flex:1; overflow:auto` 的滚动壳。
              中段是唯一可滚的那一段，所以这里必须给它 `flex:'none'` 让它按内容占高，
              否则要么内部那个滚动条形同虚设，要么变成中段里再套一个中段。
              照 `LiveMatchPage.tsx:176` 的同一层包装，别省。 */}
          <Box data-testid="report-trend-region" sx={{ flex: 'none' }}>
            <TrendChart
              analysis={analysisByMove}
              totalMoves={totalMoves}
              currentMove={currentMove}
              onMoveClick={setCurrentMove}
            />
          </Box>
          {/* 「进入研究室」是一次性的跳出动作，不是随手拨的开关，所以按冻结稿 V2 落在
              中段最末一节而不是动作区 —— 动作区留给播放条，跟直播页一致。 */}
          <Box sx={{ p: 2, borderTop: 1, borderColor: 'divider' }}>
            <Button
              fullWidth
              variant="outlined"
              startIcon={<ScienceIcon />}
              disabled={!researchHref}
              onClick={() => { if (researchHref) navigate(researchHref); }}
              sx={{ textTransform: 'none', minHeight: 40 }}
            >
              {t('report:enter_research', 'Open in Research')}
            </Button>
          </Box>
        </>
      )}
      actions={(
        <PlaybackBar
          currentMove={currentMove}
          totalMoves={totalMoves}
          onMoveChange={setCurrentMove}
        />
      )}
    />
  );
}
