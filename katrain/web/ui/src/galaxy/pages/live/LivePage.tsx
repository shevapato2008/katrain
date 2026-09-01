/* 直播 · 列表页 —— 冻结原型 `live-list` 的改版态。
 *
 * 与直播观战页（`LiveMatchPage.tsx`，已批准的样板）**同一个壳**：
 * `BoardPageShell` + `ModulePlate`，右栏三段（模块牌 / 中段唯一可滚 / 动作区），
 * 棋盘上方不留任何东西（spec §2.2/§2.3）。
 *
 * 迁移前这一页是「左 棋盘 + 页头 / 右 500px 写死宽度的列表」，标题在棋盘正上方，
 * 播放条挂在棋盘底下。S8 那轮只换了页头，整体版式没动 —— 本次补上。
 */
import { useState, useEffect, useCallback } from 'react';
import { Box, Typography, Tabs, Tab, Button, Chip, CircularProgress } from '@mui/material';
import FiberManualRecordIcon from '@mui/icons-material/FiberManualRecord';
import { useNavigate } from 'react-router-dom';
import { useLiveMatches } from '../../../hooks/live/useLiveMatches';
import { useLiveMatch } from '../../../hooks/live/useLiveMatch';
import MatchList from '../../../components/live/MatchList';
import LiveBoard from '../../../components/live/LiveBoard';
import PlaybackBar from '../../../components/live/PlaybackBar';
import UpcomingList from '../../../components/live/UpcomingList';
import type { MatchSummary } from '../../../types/live';
import { useTranslation } from '../../../hooks/useTranslation';
import { i18n } from '../../../i18n';
import BoardPageShell from '../../components/board/BoardPageShell';
import { useBoardCoordinates } from '../../components/board/useBoardCoordinates';
import ModulePlate from '../../components/layout/ModulePlate';

export default function LivePage() {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const [rightTab, setRightTab] = useState(0);
  const [selectedMatchId, setSelectedMatchId] = useState<string | null>(null);
  const [boardEdge, setBoardEdge] = useState(0);
  const coordinates = useBoardCoordinates(boardEdge);

  const { matches, liveCount, loading } = useLiveMatches({ limit: 50 });

  // Get detailed match data for the selected match
  const {
    match: selectedMatch,
    loading: matchLoading,
    currentMove,
    setCurrentMove,
    /* `analysisMode: 'none'` 不是优化，是这一页的正确档位：本页 `analysis` 零引用
       （`LiveBoard` 只收 moves/currentMove），而 hook 的默认档 'poll' 会在每次换局时
       发 `analysis/preload`。测试环境实测：盘面 816B–2.3KB，那份分析 326KB–1.64MB，
       差 400–700 倍，且和盘面抢同一条链路 —— 用户看到的就是「点了半天棋盘不出来」。
       观战页（`LiveMatchPage`）要画 AI 标记，那边照旧用默认档。 */
  } = useLiveMatch(selectedMatchId || undefined, { pollInterval: 5000, analysisMode: 'none' });

  /* hook 换 matchId 时**不清空** `match`，所以等待期里 `selectedMatch` 仍是上一局。
     判据不能用 `matchLoading`：从点击到 effect 里 `setLoading(true)` 之间还有一帧，
     那一帧 loading 是 false 而 match 是旧的。用身份比对没有这个缝 ——
     「手里这份是不是我点的那一局」是个确定的事实。 */
  const matchReady = selectedMatch != null && selectedMatch.id === selectedMatchId;

  // Auto-select first match when matches load
  useEffect(() => {
    if (matches.length > 0 && !selectedMatchId) {
      // Prefer live matches, otherwise first match
      const liveMatch = matches.find((m) => m.status === 'live');
      setSelectedMatchId(liveMatch?.id || matches[0].id);
    }
  }, [matches, selectedMatchId]);

  const handleSelectMatch = useCallback((match: MatchSummary) => {
    setSelectedMatchId(match.id);
  }, []);

  const handleEnterMatch = () => {
    if (selectedMatchId) {
      navigate(`/galaxy/live/${selectedMatchId}`);
    }
  };

  // Split matches for display
  const liveMatches = matches.filter((m) => m.status === 'live');
  const finishedMatches = matches.filter((m) => m.status === 'finished');

  /* 模块牌的副标题/状态跟着**选中的那局**走，不跟着页签走。
     冻结稿把「赛事预告」画成整屏的一个分支（棋盘留空、副标题写「赛事预告」），
     那是稿子的分支枚举是平的、表达不了「选中对局 × 页签」这两维的正交组合。
     真页面里页签只换右栏那份列表：瞟一眼赛程就把已经选好的预览清掉，是白丢状态。 */
  const plateSubtitle = matchReady && selectedMatch
    ? `${i18n.translatePlayer(selectedMatch.player_black)} vs ${i18n.translatePlayer(selectedMatch.player_white)}`
      + ` · ${selectedMatch.move_count} ${t('live:moves')}`
    /* 等待期里说「正在加载」，不留上一局的名字 —— Fan 的截图里模块牌写着上上局的
       两位棋手，而高亮的是刚点的那一局，三个数分属三局。 */
    : selectedMatchId ? t('live:loading_match', '正在加载棋局…')
    : t('live:select_match');

  /* 状态徽章照抄 `LiveMatchPage.tsx:140`。稿子这一屏只画了「直播中」那一种，
     但列表页选得中已结束的对局 —— 同一个模块牌在两页上得长得一样。 */
  const plateStatus = !matchReady || !selectedMatch ? undefined : selectedMatch.status === 'live' ? (
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
      /* 原来这里写的是 `loading && !selectedMatch`，而 `loading` 是**列表**的加载态。
         列表一加载完它就是 false，于是换局的整个等待期都落到「有 selectedMatch」
         这一支上：既没有任何提示，画的还是上一局。判据量错了操作数 ——
         该看的是「手里这份是不是我点的那一局」。 */
      board={!matchReady ? (
        selectedMatchId || loading ? (
          <Box
            data-testid="live-board-loading"
            sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 1.5 }}
          >
            <CircularProgress size={28} />
            <Typography variant="body2" color="text.secondary">
              {t('live:loading_match', '正在加载棋局…')}
            </Typography>
          </Box>
        ) : (
          <Typography variant="body2" color="text.secondary" sx={{ opacity: 0.5, textAlign: 'center', px: 2 }}>
            {matches.length === 0 ? t('live:no_matches') : t('live:select_match')}
          </Typography>
        )
      ) : selectedMatch ? (
        <LiveBoard
          moves={selectedMatch.moves}
          currentMove={currentMove}
          showMoveNumbers={false}
          /* spec §3.2 的自动档：棋盘边长低于 500px 时坐标默认关闭。
             本页右栏塞的是列表、没有显示开关那一段，所以只取 `visible`，不挂 toggle
             —— 与棋谱库页（S4）同一口径。 */
          showCoordinates={coordinates.visible}
          /* 让 stage 定尺寸，不让 LiveBoard 用自己的 400 下限把格子撑破。 */
          minimumCanvasSize={0}
          minContainerHeight={0}
        />
      ) : (
        <Typography variant="body2" color="text.secondary" sx={{ opacity: 0.5, textAlign: 'center', px: 2 }}>
          {/* 稿子写的是「从右边选一场对局观看」。沿用不带方位的既有词条 ——
              <900px 竖屏下列表在棋盘**下方**，「从右边」就是假的（同 S4 棋谱库页）。 */}
          {matches.length === 0 ? t('live:no_matches') : t('live:select_match')}
        </Typography>
      )}
      modulePlate={(
        <ModulePlate
          title={t('Live')}
          subtitle={plateSubtitle}
          status={plateStatus}
          /* 直播是一级导航页，没有上一级 —— 同棋谱库页（`KifuLibraryPage.tsx:378`）。 */
          backTo="/galaxy/live"
          showBack={false}
        />
      )}
      railBody={(
        <>
          <Box sx={{ px: 1.5, borderBottom: 1, borderColor: 'divider' }}>
            <Tabs value={rightTab} onChange={(_, v) => setRightTab(v)}>
              <Tab label={t('live:top_matches')} />
              <Tab label={t('live:upcoming')} />
            </Tabs>
          </Box>

          <Box sx={{ p: 1.5 }}>
            {rightTab === 0 ? (
              <>
                {liveCount > 0 && (
                  <Box sx={{ mb: 2 }}>
                    <Typography variant="subtitle2" color="text.secondary" sx={{ mb: 1 }}>
                      {t('live:now_live')} ({liveCount})
                    </Typography>
                    <MatchList
                      matches={liveMatches}
                      compact
                      selectedId={selectedMatchId || undefined}
                      onSelect={handleSelectMatch}
                    />
                  </Box>
                )}
                <Box>
                  <Typography variant="subtitle2" color="text.secondary" sx={{ mb: 1 }}>
                    {t('live:history')}
                  </Typography>
                  <MatchList
                    matches={finishedMatches.slice(0, 10)}
                    loading={loading}
                    compact
                    selectedId={selectedMatchId || undefined}
                    onSelect={handleSelectMatch}
                  />
                </Box>
              </>
            ) : (
              <UpcomingList limit={20} />
            )}
          </Box>
        </>
      )}
      actions={(
        <>
          {/* 播放条从棋盘底下挪进动作区（稿子同址）。它是共享件，自带
              `RAIL_TIGHT`（460）的窄档收缩。 */}
          {matchReady && selectedMatch && (
            <PlaybackBar
              currentMove={currentMove}
              totalMoves={selectedMatch.move_count}
              onMoveChange={setCurrentMove}
              isLive={selectedMatch.status === 'live'}
            />
          )}
          <Box sx={{ p: 2, pt: matchReady ? 1 : 2 }}>
            {/* 迁移前这个按钮在「赛事预告」页签下**整个不渲染**。它作用于选中的那局、
                与页签无关，所以改成常驻：没有可进入的对局时禁用。 */}
            <Button
              data-testid="live-enter-match"
              variant="contained"
              fullWidth
              size="large"
              onClick={handleEnterMatch}
              disabled={!matchReady || matchLoading}
              sx={{ py: 1.5 }}
            >
              {selectedMatch?.status === 'live' ? t('live:enter_live') : t('live:view_game')}
            </Button>
          </Box>
        </>
      )}
    />
  );
}
