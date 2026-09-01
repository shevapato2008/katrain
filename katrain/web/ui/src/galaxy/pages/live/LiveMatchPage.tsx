import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import FiberManualRecordIcon from '@mui/icons-material/FiberManualRecord';
import { Alert, Box, Button, Chip, CircularProgress, Skeleton } from '@mui/material';
import { useParams } from 'react-router-dom';

import AiAnalysis from '../../../components/live/AiAnalysis';
import LiveBoard, { type AiMoveMarker } from '../../../components/live/LiveBoard';
import MatchInfo from '../../../components/live/MatchInfo';
import PlaybackBar from '../../../components/live/PlaybackBar';
import TrendChart from '../../../components/live/TrendChart';
import { useLiveMatch } from '../../../hooks/live/useLiveMatch';
import { useSound } from '../../../hooks/useSound';
import { useTranslation } from '../../../hooks/useTranslation';
import { i18n } from '../../../i18n';
import BoardPageShell from '../../components/board/BoardPageShell';
import { useBoardCoordinates } from '../../components/board/useBoardCoordinates';
import ModulePlate from '../../components/layout/ModulePlate';
import LiveMatchDisplayControls from './LiveMatchDisplayControls';

/* 加载态的占位**不是控件**。原来这里是 `<Button disabled><Skeleton/></Button>` ——
   一个禁用按钮，子元素只有骨架，于是既没有可见文字也没有 `aria-label`：读屏用户
   在这一屏上会听到五个没有名字的按钮，键盘用户会数到五个到不了任何地方的停靠点。
   占位就画成占位（`Skeleton` 本身不是可交互元素，无障碍树里不出现），
   高度沿用原来的 40，视觉落点不变。
   2026-08-22 全量控件账本量到：本页加载态/错误态各 6 个无名控件，
   报告详情页同款 5 个（那份是从这里抄过去的）。 */
const LoadingControls = () => (
  <Box sx={{ py: 2, display: 'grid', gridTemplateColumns: 'repeat(2, minmax(0, 1fr))', gap: 0.5 }}>
    {Array.from({ length: 5 }, (_, index) => (
      <Skeleton key={index} variant="rounded" height={40} />
    ))}
  </Box>
);

const LoadingActions = () => (
  <Box sx={{ py: 2 }}>
    <Skeleton variant="rounded" height={40} />
  </Box>
);

export default function LiveMatchPage() {
  const { matchId } = useParams<{ matchId: string }>();
  const { t } = useTranslation();
  const { match, loading, error, currentMove, setCurrentMove, analysis, refresh } = useLiveMatch(matchId);
  const [pvMoves, setPvMoves] = useState<string[] | null>(null);
  const [showAiMarkers, setShowAiMarkers] = useState(true);
  const [showMoveNumbers, setShowMoveNumbers] = useState(false);
  const [showTerritory, setShowTerritory] = useState(false);
  const [tryMoveMode, setTryMoveMode] = useState(false);
  const [tryMoves, setTryMoves] = useState<string[]>([]);
  const [boardEdge, setBoardEdge] = useState(0);
  const [retrying, setRetrying] = useState(false);
  const coordinates = useBoardCoordinates(boardEdge);

  const { play: playSound } = useSound();
  const prevMoveRef = useRef<number | null>(null);
  useEffect(() => {
    if (match && currentMove > 0 && prevMoveRef.current !== null && currentMove !== prevMoveRef.current) {
      playSound('stone');
    }
    prevMoveRef.current = currentMove;
  }, [currentMove, match, playSound]);

  const currentAnalysis = analysis[currentMove];
  const aiMarkers = useMemo((): AiMoveMarker[] | null => {
    if (!currentAnalysis?.top_moves?.length) return null;
    return currentAnalysis.top_moves.slice(0, 3).map((topMove, index) => ({
      move: topMove.move,
      rank: index + 1,
      visits: topMove.visits,
      winrate: topMove.winrate ?? 0,
      score_lead: topMove.score_lead ?? 0,
    }));
  }, [currentAnalysis]);
  const ownership = currentAnalysis?.ownership || null;

  const handleRetry = useCallback(async () => {
    setRetrying(true);
    try {
      await refresh();
    } finally {
      setRetrying(false);
    }
  }, [refresh]);

  if (loading) {
    return (
      <BoardPageShell
        onBoardSizeChange={setBoardEdge}
        board={<Skeleton data-testid="board-loading-skeleton" variant="rectangular" width="100%" height="100%" />}
        modulePlate={(
          <ModulePlate
            title={t('live:loading_match', 'Loading live match')}
            subtitle={<Skeleton width={180} />}
            status={<CircularProgress size={22} />}
            backTo="/galaxy/live"
          />
        )}
        railBody={<Box sx={{ py: 2 }}><Skeleton height={120} /><Skeleton height={160} /><Skeleton height={180} /></Box>}
        displayControls={<LoadingControls />}
        actions={<LoadingActions />}
      />
    );
  }

  if (error || !match) {
    return (
      <BoardPageShell
        onBoardSizeChange={setBoardEdge}
        /* 错误态**不是加载态**：骨架屏会脉动，那是在说「东西还在路上」，而这一屏
           已经失败了。`animation={false}` 让它退成一块静止的占位。同理下面不再
           挂 `displayControls`/`actions` —— 加载不出对局，就没有可开关的东西，
           画一排永远按不动的占位只是在假装还有内容。 */
        board={<Skeleton data-testid="board-error-skeleton" variant="rectangular" animation={false} width="100%" height="100%" />}
        modulePlate={<ModulePlate title={t('live:match', 'Live match')} backTo="/galaxy/live" />}
        railBody={(
          <Box sx={{ py: 2 }}>
            <Alert severity="error" sx={{ mb: 2 }}>
              {error?.message || t('live:load_error', 'Failed to load match data')}
            </Alert>
            <Button
              variant="outlined"
              aria-label={t('Retry', 'Retry')}
              disabled={retrying}
              onClick={() => void handleRetry()}
              sx={{ minWidth: 96, minHeight: 40 }}
            >
              {retrying ? <CircularProgress size={20} /> : t('Retry', 'Retry')}
            </Button>
          </Box>
        )}
        actions={null}
      />
    );
  }

  const tournament = i18n.translateTournament(match.tournament);
  const round = match.round_name ? i18n.translateRound(match.round_name) : null;
  const subtitle = `${tournament}${round ? ` · ${round}` : ''} · ${currentMove} / ${match.move_count} ${t('live:moves')}`;
  const status = match.status === 'live' ? (
    <Chip
      icon={<FiberManualRecordIcon sx={{ fontSize: 10 }} />}
      label={t('live:status_live')}
      size="small"
      color="error"
      sx={{ '& .MuiChip-icon': { animation: 'pulse 1.5s infinite' } }}
    />
  ) : (
    <Chip label={t('live:status_finished')} size="small" variant="outlined" />
  );

  return (
    <BoardPageShell
      onBoardSizeChange={setBoardEdge}
      board={(
        <LiveBoard
          moves={match.moves}
          currentMove={currentMove}
          pvMoves={pvMoves}
          aiMarkers={aiMarkers}
          showAiMarkers={showAiMarkers}
          showMoveNumbers={showMoveNumbers}
          showTerritory={showTerritory}
          showCoordinates={coordinates.visible}
          ownership={ownership}
          tryMoves={tryMoveMode ? tryMoves : undefined}
          onTryMove={tryMoveMode ? (move: string) => setTryMoves((previous) => [...previous, move]) : undefined}
          minimumCanvasSize={0}
          minContainerHeight={0}
        />
      )}
      modulePlate={(
        <ModulePlate
          title={`${i18n.translatePlayer(match.player_black)} vs ${i18n.translatePlayer(match.player_white)}`}
          subtitle={subtitle}
          status={status}
          backTo="/galaxy/live"
        />
      )}
      railBody={(
        <>
          <MatchInfo match={match} currentMove={currentMove} analysis={currentAnalysis} headingMode="metadata-only" />
          {/* 显示开关紧跟在对局信息之后，而不是 shell 的 `displayControls` 槽。

              冻结稿 V2 把它排在中段最末，但那是按稿子里那份**很短**的假数据排的。
              真数据实测（yike_182849，312 手全部分析完、48 处失误）：排在最末时
              开关块的顶边在折线**以下 32px**（1440x900）/ **164px**（1024x768），
              整块要滚 127 / 259px 才露全 —— 用户得先滚一屏才知道有这组开关。
              稿子的意图是「不用滚就能看见」（参考图里它是露着的），
              真数据下只有放在这里才成立。

              复盘·报告详情页 2026-08-22 已经这样改过（那页是 208/389px），
              当时记了一条待议：「直播页用同一个共享件、同样挂在 displayControls 槽，
              但本机没有直播数据量不到」。现在量到了 —— 本机库里有 123 场真实对局，
              那条待议的前提是错的。

              顺序也与死活题页一致：身份块（对局信息）→ 工具格 → 其余内容。 */}
          <LiveMatchDisplayControls
            tryMoveMode={tryMoveMode}
            showTerritory={showTerritory}
            showMoveNumbers={showMoveNumbers}
            showAiMarkers={showAiMarkers}
            showCoordinates={coordinates.visible}
            ownershipAvailable={ownership != null}
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
            <AiAnalysis currentMove={currentMove} analysis={analysis} onMoveHover={setPvMoves} />
          </Box>
          <Box data-testid="live-match-trend-region" sx={{ flex: 'none' }}>
            <TrendChart
              analysis={analysis}
              totalMoves={match.move_count}
              currentMove={currentMove}
              onMoveClick={setCurrentMove}
            />
          </Box>
        </>
      )}
      actions={(
        <PlaybackBar
          currentMove={currentMove}
          totalMoves={match.move_count}
          onMoveChange={setCurrentMove}
          isLive={match.status === 'live'}
        />
      )}
    />
  );
}
