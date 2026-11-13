import { ConsumptionQuoteDialog } from '../../../features/membership/ConsumptionQuoteDialog';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import DeleteOutlineIcon from '@mui/icons-material/DeleteOutline';
import SearchIcon from '@mui/icons-material/Search';
import LoginIcon from '@mui/icons-material/Login';
import {
  Alert,
  Box,
  Button,
  Chip,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogContentText,
  DialogTitle,
  Fade,
  InputAdornment,
  IconButton,
  Menu,
  MenuItem,
  Pagination,
  Stack,
  TextField,
  Typography,
} from '@mui/material';

import LiveBoard from '../../../components/live/LiveBoard';
import { useAuth } from '../../../context/AuthContext';
import { useTranslation } from '../../../hooks/useTranslation';
import { sgfToMoves } from '../../../utils/sgfSerializer';
import { KifuAPI } from '../../../api/kifuApi';
import type { KifuAlbumSummary } from '../../../types/kifu';
import {
  UserGamesAPI,
  type UserGameDetail,
  type UserGameSummary,
} from '../../../api/userGamesApi';
import { useReportTasks } from '../../../features/report/useReportTasks';
import {
  presentReportTier,
  toLibraryUserGameParams,
  toLocalUserGameParams,
} from '../../../features/report/reportModel';
import PlaybackBar from '../../../components/live/PlaybackBar';
import { useReplayStoneSound } from '../../../hooks/useReplayStoneSound';
import ReportGameCard from '../../components/report/ReportGameCard';
import ReportImportMenu from '../../components/report/ReportImportMenu';
import ReportLibraryImportDialog from '../../components/report/ReportLibraryImportDialog';
import ReportLocalImportDialog, {
  type LocalImportPayload,
} from '../../components/report/ReportLocalImportDialog';
import BoardPageShell from '../../components/board/BoardPageShell';
import { useBoardCoordinates } from '../../components/board/useBoardCoordinates';
import ModulePlate from '../../components/layout/ModulePlate';
import LoginModal from '../../components/auth/LoginModal';

const PAGE_SIZE = 12;

type ImportAction = 'save' | 'normal' | 'deep' | null;

export default function ReportsPage() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const { token, isAuthenticated, identityKey, status } = useAuth();
  const { t } = useTranslation();
  const translationRef = useRef(t);
  translationRef.current = t;

  const page = Math.max(1, Number(searchParams.get('page')) || 1);
  const query = searchParams.get('q') || '';

  const [reportMenuAnchor, setReportMenuAnchor] = useState<HTMLElement | null>(null);
  const [games, setGames] = useState<UserGameSummary[]>([]);
  const [totalGames, setTotalGames] = useState(0);
  const [gamesLoading, setGamesLoading] = useState(true);
  const [gamesError, setGamesError] = useState<string | null>(null);
  const [searchInput, setSearchInput] = useState(query);

  const [taskError, setTaskError] = useState<string | null>(null);
  const {
    queueSummary,
    reportStatesByGame,
    error: reportTasksError,
    billingError: reportBillingError,
    clearError: clearReportTasksError,
    refresh: refreshTasks,
    createReport,
    retryReport,
    pendingQuote, quoteBusy, confirmQuote, cancelQuote,
  } = useReportTasks(token, isAuthenticated, identityKey, status);

  const [selectedGameId, setSelectedGameId] = useState<string | null>(null);
  const [selectedGame, setSelectedGame] = useState<UserGameDetail | null>(null);
  const [previewMoves, setPreviewMoves] = useState<string[]>([]);
  const [previewColors, setPreviewColors] = useState<('B' | 'W')[]>([]);
  const [previewBoardSize, setPreviewBoardSize] = useState(19);
  const [previewSetupCount, setPreviewSetupCount] = useState(0);
  const [previewCurrentMove, setPreviewCurrentMove] = useState(0);
  const [replaySelection, setReplaySelection] = useState<{ id: string | null; move: number } | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);

  const [localImportOpen, setLocalImportOpen] = useState(false);
  const [libraryImportOpen, setLibraryImportOpen] = useState(false);
  const [localImporting, setLocalImporting] = useState<ImportAction>(null);
  const [libraryImporting, setLibraryImporting] = useState<ImportAction>(null);

  const [deleteTarget, setDeleteTarget] = useState<string | null>(null);
  const [deleteLoading, setDeleteLoading] = useState(false);

  const [boardEdge, setBoardEdge] = useState(0);
  const coordinates = useBoardCoordinates(boardEdge);
  const [loginOpen, setLoginOpen] = useState(false);

  const loadGames = useCallback(async () => {
    if (!token || !isAuthenticated) {
      setGamesLoading(false);
      return;
    }
    setGamesLoading(true);
    setGamesError(null);
    try {
      const response = await UserGamesAPI.list(token, {
        page,
        page_size: PAGE_SIZE,
        q: query || undefined,
        sort: 'created_at_desc',
      });
      setGames(response.items);
      setTotalGames(response.total);
    } catch (error) {
      setGamesError(error instanceof Error ? error.message : translationRef.current('report:load_games_failed', 'Failed to load game list'));
    } finally {
      setGamesLoading(false);
    }
  }, [isAuthenticated, page, query, token]);

  const applyPreview = useCallback((game: UserGameDetail) => {
    const parsed = sgfToMoves(game.sgf_content);
    setSelectedGame(game);
    setPreviewMoves(parsed.moves);
    setPreviewColors(parsed.stoneColors);
    setPreviewSetupCount(parsed.setupCount ?? 0);
    setPreviewBoardSize(parsed.metadata.boardSize || game.board_size || 19);
    setPreviewCurrentMove(parsed.moves.length);
  }, []);

  useEffect(() => {
    setSearchInput(query);
  }, [query]);

  useEffect(() => {
    loadGames().catch(() => {});
  }, [loadGames]);

  useEffect(() => {
    if (games.length === 0) {
      setSelectedGameId(null);
      setSelectedGame(null);
      setPreviewMoves([]);
      setPreviewColors([]);
      setPreviewCurrentMove(0);
      return;
    }
    setSelectedGameId((current) => (current && games.some((game) => game.id === current) ? current : games[0].id));
  }, [games]);

  useEffect(() => {
    if (!token || !isAuthenticated || !selectedGameId) return;
    if (selectedGame?.id === selectedGameId) return;
    let cancelled = false;
    setPreviewLoading(true);
    UserGamesAPI.get(token, selectedGameId)
      .then((game) => {
        if (cancelled) return;
        applyPreview(game);
      })
      .catch((error) => {
        if (cancelled) return;
        setGamesError(error instanceof Error ? error.message : translationRef.current('report:load_games_failed', 'Failed to load game list'));
      })
      .finally(() => {
        if (!cancelled) {
          setPreviewLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [applyPreview, isAuthenticated, selectedGame?.id, selectedGameId, token]);

  const selectedSummary = useMemo(
    () => games.find((game) => game.id === selectedGameId) || null,
    [games, selectedGameId],
  );

  const selectPreviewMove = (move: number) => {
    setReplaySelection({ id: selectedGameId, move });
    setPreviewCurrentMove(move);
  };
  useReplayStoneSound({ identity: selectedGameId, cursor: Math.max(0, previewCurrentMove - previewSetupCount), move: previewMoves[previewCurrentMove - 1],
    ready: selectedGame?.id === selectedGameId && selectedGame !== null && !previewLoading, boardSize: previewBoardSize,
    selected: replaySelection?.id === selectedGameId && replaySelection.move === previewCurrentMove });

  const totalPages = Math.max(1, Math.ceil(totalGames / PAGE_SIZE));

  const refreshAfterMutation = useCallback(async () => {
    await Promise.all([loadGames(), refreshTasks()]);
  }, [loadGames, refreshTasks]);

  const createReportForGame = useCallback(
    async (game: UserGameSummary | UserGameDetail, reportType: 'normal' | 'deep') => {
      await createReport({ userGameId: game.id, reportType, totalMoves: game.move_count });
    },
    [createReport],
  );

  const handleSearch = () => {
    const nextQuery = searchInput.trim();
    const params: Record<string, string> = {};
    if (nextQuery) params.q = nextQuery;
    setSearchParams(params, { replace: false });
  };

  const handlePageChange = (_: unknown, nextPage: number) => {
    const params: Record<string, string> = {};
    if (query) params.q = query;
    if (nextPage > 1) params.page = String(nextPage);
    setSearchParams(params, { replace: false });
  };

  const focusImportedGame = useCallback(
    async (game: UserGameDetail) => {
      setSelectedGameId(game.id);
      setSelectedGame(game);
      applyPreview(game);
      setSearchInput('');
      if (page !== 1 || query) {
        setSearchParams({}, { replace: false });
      } else {
        await refreshAfterMutation();
      }
    },
    [applyPreview, page, query, refreshAfterMutation, setSearchParams],
  );

  const handleLocalImport = useCallback(
    async (payload: LocalImportPayload, reportType?: 'normal' | 'deep') => {
      if (!token) return;
      const action: ImportAction = reportType || 'save';
      setLocalImporting(action);
      setTaskError(null);
      let reportStarted = false;
      try {
        const createdGame = await UserGamesAPI.create(token, toLocalUserGameParams(payload));
        await focusImportedGame(createdGame);
        if (reportType) {
          reportStarted = true;
          await createReportForGame(createdGame, reportType);
        }
        setLocalImportOpen(false);
        await refreshTasks();
      } catch (error) {
        if (!reportStarted) setTaskError(error instanceof Error ? error.message : translationRef.current('report:import_failed', 'Failed to import SGF'));
      } finally {
        setLocalImporting(null);
      }
    },
    [createReportForGame, focusImportedGame, refreshTasks, token],
  );

  const handleLibraryImport = useCallback(
    async (album: KifuAlbumSummary, reportType?: 'normal' | 'deep') => {
      if (!token) return;
      const action: ImportAction = reportType || 'save';
      setLibraryImporting(action);
      setTaskError(null);
      let reportStarted = false;
      try {
        const detail = await KifuAPI.getAlbum(album.id);
        const createdGame = await UserGamesAPI.create(token, toLibraryUserGameParams(album, detail.sgf_content));
        await focusImportedGame(createdGame);
        if (reportType) {
          reportStarted = true;
          await createReportForGame(createdGame, reportType);
        }
        setLibraryImportOpen(false);
        await refreshTasks();
      } catch (error) {
        if (!reportStarted) setTaskError(error instanceof Error ? error.message : translationRef.current('report:library_import_failed', 'Failed to import from library'));
      } finally {
        setLibraryImporting(null);
      }
    },
    [createReportForGame, focusImportedGame, refreshTasks, token],
  );

  const handleCreateReport = useCallback(
    async (game: UserGameSummary, reportType: 'normal' | 'deep') => {
      try {
        await createReportForGame(game, reportType);
      } catch {
        // useReportTasks owns and clears creation errors.
      }
    },
    [createReportForGame],
  );

  const handleDeleteConfirm = useCallback(async () => {
    if (!token || !deleteTarget) return;
    setDeleteLoading(true);
    try {
      await UserGamesAPI.delete(token, deleteTarget);
      if (selectedGameId === deleteTarget) {
        setSelectedGameId(null);
        setSelectedGame(null);
        setPreviewMoves([]);
        setPreviewColors([]);
        setPreviewCurrentMove(0);
      }
      await refreshAfterMutation();
    } catch (error) {
      setTaskError(error instanceof Error ? error.message : translationRef.current('report:delete_failed', 'Failed to delete game'));
    } finally {
      setDeleteLoading(false);
      setDeleteTarget(null);
    }
  }, [token, deleteTarget, selectedGameId, refreshAfterMutation]);

  const handleRetry = useCallback(
    async (taskId: number) => {
      try {
        await retryReport(taskId);
      } catch {
        // useReportTasks owns and clears retry errors.
      }
    },
    [retryReport],
  );

  const hasPreview = previewMoves.length > 0;
  const movesUnit = t('report:moves_unit', 'moves');

  /* 模块牌副标题：选中棋局后是对局双方 + 手数，没选中时是「选择一局棋谱」。
     与棋谱库页（S4，`KifuLibraryPage.tsx:325`）同一口径。
     迁移前预览卡有自己的标题栏（棋局标题 + 双方 · 手数）；标题栏整块没了，
     **棋局标题下沉到右栏那张卡上**（`ReportGameCard` 本来就画标题，选中态高亮），
     模块牌只留双方 + 手数 —— 稿子 `plate2({title:'复盘', sub:'申真谞 vs 柯洁 · 250 手'})` 同址。 */
  /* 详情还在路上时退回列表里那条摘要 —— 双方名字摘要里就有，不必等 SGF 回来
     才敢写标题，否则每选一局副标题都会先塌成「选择一局棋谱」再撑回去。 */
  const plateGame = selectedGame ?? selectedSummary;
  const plateSubtitle = plateGame
    ? `${plateGame.player_black || t('report:black', 'Black')} vs ${plateGame.player_white || t('report:white', 'White')}`
      + ` · ${plateGame.move_count} ${movesUnit}`
    : t('report:select_game', 'Select a game');

  /* 状态位：选中那一局的报告状态。spec §2.4「状态放最右」，只留**一个**状态件不堆
     —— 队列汇总（几个生成中/排队中/失败）仍在右栏中段顶部，那是整页的状态，不是这一局的。 */
  const selectedReportState = selectedGameId ? reportStatesByGame[selectedGameId] : undefined;
  useEffect(() => { setReportMenuAnchor(null); }, [selectedGameId, identityKey]);

  const plateStatus = (() => {
    const state = selectedReportState;
    if (!state) return undefined;
    /* 优先级与卡片上一致（`ReportGameCard.tsx:83`）：进行中 > 失败 > 已完成 ——
       一局同时有「深度已完成」和「普通生成中」时，说「生成中」才是当下在发生的事。 */
    if (state.activeNormal || state.activeDeep) {
      return <Chip size="small" color="warning" variant="outlined" label={t('report:summary_running', 'running')} />;
    }
    if (state.failedNormal || state.failedDeep) {
      return <Chip size="small" color="error" variant="outlined" label={t('report:summary_failed', 'failed')} />;
    }
    if (state.completedNormal || state.completedDeep) {
      return <Chip size="small" color="success" variant="outlined" label={t('report:summary_done', '已完成')} />;
    }
    return undefined;
  })();

  if (!isAuthenticated) {
    return (
      <>
        <BoardPageShell
          board={(
            <Typography variant="body2" color="text.secondary" sx={{ opacity: 0.5, textAlign: 'center', px: 2 }}>
              {t('report:login_required', 'Please log in to view and generate game reviews.')}
            </Typography>
          )}
          modulePlate={(
            <ModulePlate
              title={t('report:my_reports', 'Review')}
              backTo="/report"
              showBack={false}
            />
          )}
          railBody={(
            <Box sx={{ py: 2 }}>
              <Alert severity="info">
                {t('report:login_required', 'Please log in to view and generate game reviews.')}
              </Alert>
            </Box>
          )}
          actions={(
            <Box sx={{ py: 2 }}>
              {/* 稿子的未登录支给了这个按钮。左栏底部也有一个登录按钮，但那是全站的，
                  而「请先登录」这句话就写在这一屏上、旁边却没有可按的东西 ——
                  代价只是本页再挂一份 `LoginModal`（对话框状态，两份不会同时开）。 */}
              <Button
                data-testid="reports-login"
                variant="contained"
                fullWidth
                size="large"
                startIcon={<LoginIcon />}
                onClick={() => setLoginOpen(true)}
                sx={{ py: 1.5 }}
              >
                {t('Login', 'Sign In')}
              </Button>
            </Box>
          )}
        />
        <LoginModal open={loginOpen} onClose={() => setLoginOpen(false)} />
      </>
    );
  }

  return (
    <>
      {/* Keep the shared shell; this report page reserves a 552px content rail for compact external tier status. */}
      <Box sx={{ height: '100%', minHeight: 0,
        '& [data-testid="board-page-shell"]': { '@media (min-width:900px)': { gridTemplateColumns: 'minmax(0,1fr) 592px' } },
        '& [data-testid="board-rail-scroll"]': { scrollbarGutter: 'auto' },
      }}>
      <BoardPageShell
        onBoardSizeChange={setBoardEdge}
        board={(
          <Box sx={{ width: '100%', height: '100%', minHeight: 0, display: 'flex', flexDirection: 'column' }}>
            <Box data-testid="reports-preview-title" sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', px: 2.5, minHeight: 44, flex: 'none' }}>
              <Typography variant="h6">{t('review:rail_title', 'Selected game')}</Typography>
              <Stack direction="row" alignItems="center" spacing={1}>{plateStatus}
              {selectedSummary && selectedSummary.source !== 'kifu_library' && <IconButton
                aria-label={t('report:delete_game', 'Delete game')} onClick={() => setDeleteTarget(selectedSummary.id)}
                sx={{ width: 44, height: 44, color: 'text.secondary' }}><DeleteOutlineIcon /></IconButton>}
              </Stack>
            </Box>
            <Box sx={{ flex: 1, minHeight: 0, width: '100%', display: 'grid', placeItems: 'center' }}>
        {previewLoading || gamesLoading ? (
          <CircularProgress data-testid="reports-preview-spinner" />
        ) : hasPreview ? (
          <LiveBoard
            moves={previewMoves}
            stoneColors={previewColors}
            currentMove={previewCurrentMove}
            handicapCount={previewSetupCount}
            boardSize={previewBoardSize}
            /* 迁移前这里写死 `showCoordinates`。改成走 spec §3.2 的自动档（棋盘边长
               低于 500px 时默认关闭）。本页右栏塞的是列表、没有显示开关那一段，
               所以只取 `visible` 不挂 toggle —— 同 S4 棋谱库页。 */
            showCoordinates={coordinates.visible}
            minimumCanvasSize={0}
            minContainerHeight={0}
          />
        ) : (
          <Typography variant="body2" color="text.secondary" sx={{ opacity: 0.5, textAlign: 'center', px: 2 }}>
            {t('report:no_preview', 'No game to preview yet.')}
          </Typography>
        )}
            </Box>
            <Box sx={{ px: 2.5, flex: 'none' }}>
              <Typography variant="body2" color="text.secondary" noWrap>{plateSubtitle}</Typography>
              {hasPreview && <PlaybackBar currentMove={previewCurrentMove} totalMoves={previewMoves.length} onMoveChange={selectPreviewMove} />}
              <Box data-testid="reports-preview-actions" sx={{ display: 'flex', justifyContent: 'center', py: 1 }}>
                <Button variant="contained" aria-haspopup="menu" aria-expanded={Boolean(reportMenuAnchor)}
                  disabled={!selectedSummary} sx={{ minHeight: 48, minWidth: 160 }}
                  onClick={event => setReportMenuAnchor(event.currentTarget)}>
                  {t('review:analysis_report', 'Analysis report')}
                </Button>
              </Box>
            </Box>
          </Box>
        )}
        modulePlate={(
          <Box sx={{ pt: 2 }}><ModulePlate
            title={t('review:sec_games', 'History games')}
            status={<Typography variant="caption" color="text.secondary">{t('review:all_games', '{n} games').replace('{n}', String(totalGames))}</Typography>}
            /* 复盘是一级导航页，没有上一级 —— 同棋谱库页 / 直播列表页。 */
            backTo="/report"
            showBack={false}
          /></Box>
        )}
        railBody={(
          <>
            <Box sx={{ pb: 2 }}>
              {(taskError || reportTasksError) && (
                <Alert
                  severity="error"
                  sx={{ mb: 1.5 }}
                  onClose={() => {
                    setTaskError(null);
                    clearReportTasksError();
                  }}
                >
                  {taskError || reportTasksError}
                </Alert>
              )}



              <Stack spacing={1.5}>
                <TextField
                  fullWidth
                  size="small"
                  placeholder={t('report:search_placeholder', 'Search by player, title, or event')}
                  value={searchInput}
                  onChange={(event) => setSearchInput(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === 'Enter') {
                      handleSearch();
                    }
                  }}
                  InputProps={{
                    startAdornment: (
                      <InputAdornment position="start">
                        <SearchIcon sx={{ color: 'text.secondary', fontSize: 20, opacity: 0.65 }} />
                      </InputAdornment>
                    ),
                  }}
                  sx={{
                    '& .MuiOutlinedInput-root': {
                      height: 44,
                      bgcolor: 'rgba(255,255,255,0.03)',
                    },
                  }}
                />
              </Stack>


            </Box>

            {gamesError && (
              <Box sx={{ pb: 1.5 }}>
                <Alert severity="error">{gamesError}</Alert>
              </Box>
            )}

            <Box data-testid="reports-list" sx={{ pb: 1 }}>
              {gamesLoading ? (
                <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', py: 6 }}>
                  <CircularProgress size={28} />
                </Box>
              ) : games.length === 0 ? (
                <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', px: 2, py: 6 }}>
                  <Typography variant="body2" color="text.secondary" sx={{ textAlign: 'center' }}>
                    {query ? t('report:no_match', 'No games matching \u201c{query}\u201d.').replace('{query}', query) : t('report:no_games', 'No games yet. Import one to generate a report.')}
                  </Typography>
                </Box>
              ) : (
                <Stack spacing={1}>
                  {games.map((game, index) => (
                    <Fade key={game.id} in timeout={200 + index * 40}>
                      <Box>
                        <ReportGameCard
                          game={game}
                          selected={game.id === selectedGameId}
                          reportState={reportStatesByGame[game.id] || {}}
                          onSelect={() => setSelectedGameId(game.id)}
                        />
                      </Box>
                    </Fade>
                  ))}
                </Stack>
              )}
            </Box>

            {totalPages > 1 && (
              <Box sx={{ display: 'flex', justifyContent: 'center', px: 1, pb: 2 }}>
                {/* 分页保持 MUI 默认密度、不收 `siblingCount` —— 收了会丢直达页码，
                    账本上就是丢控件。同 S4 棋谱库页那条注释。 */}
                <Pagination count={totalPages} page={page} onChange={handlePageChange} color="primary" size="small" />
              </Box>
            )}
          </>
        )}
        actions={(
          <Box sx={{ py: 2 }}>
              {queueSummary && (queueSummary.pending > 0 || queueSummary.running > 0 || queueSummary.failed > 0) && (
                <Stack direction="row" spacing={0.75} sx={{ mb: 1.5, flexWrap: 'wrap', rowGap: 0.75 }}>
                  {queueSummary.running > 0 && (
                    <Chip label={`${queueSummary.running} ${t('report:summary_running', 'running')}`} size="small" color="warning" variant="outlined" sx={{ height: 22, fontSize: '0.7rem' }} />
                  )}
                  {queueSummary.pending > 0 && (
                    <Chip label={`${queueSummary.pending} ${t('report:summary_queued', 'queued')}`} size="small" variant="outlined" sx={{ height: 22, fontSize: '0.7rem' }} />
                  )}
                  {queueSummary.failed > 0 && (
                    <Chip label={`${queueSummary.failed} ${t('report:summary_failed', 'failed')}`} size="small" color="error" variant="outlined" sx={{ height: 22, fontSize: '0.7rem' }} />
                  )}
                </Stack>
              )}
                <ReportImportMenu
                  onImportLocal={() => setLocalImportOpen(true)}
                  onImportLibrary={() => setLibraryImportOpen(true)}
                />
          </Box>
        )}
      />

      </Box>
      <Menu anchorEl={reportMenuAnchor} open={Boolean(reportMenuAnchor)} onClose={() => setReportMenuAnchor(null)}>
        {(['normal', 'deep'] as const).map(tier => {
          const value = presentReportTier(selectedReportState ?? {}, tier, selectedSummary?.move_count ?? 0);
          const active = value.status === 'pending' || value.status === 'running';
          const action = active ? t('review:tier_working', 'Generating')
            : value.viewable ? t('review:tier_view', 'View')
              : value.status === 'failed' ? t('kifu:retry', 'Retry') : t('review:tier_generate', 'Generate');
          const label = tier === 'normal' ? t('report:tier_normal', 'Normal report') : t('report:tier_deep', 'Advanced report');
          return <MenuItem key={tier} disabled={active || !selectedSummary} sx={{ minHeight: '48px', '@media (min-width:600px)': { minHeight: '48px' } }} onClick={() => {
            if (active || !selectedSummary) return;
            setReportMenuAnchor(null);
            if (value.viewable) navigate(`/report/${value.task!.id}`);
            else if (value.status === 'failed') void handleRetry(value.task!.id);
            else void handleCreateReport(selectedSummary, tier);
          }}>{action} {label}</MenuItem>;
        })}
      </Menu>
      <ReportLocalImportDialog
        open={localImportOpen}
        loading={localImporting !== null}
        onClose={() => setLocalImportOpen(false)}
        onSubmit={handleLocalImport}
      />

      <ConsumptionQuoteDialog quote={pendingQuote?.quote ?? null} busy={quoteBusy} error={reportBillingError ? reportTasksError : null} onCancel={cancelQuote}
        onConfirm={() => { void confirmQuote().catch(() => undefined); }} />
      <ReportLibraryImportDialog
        open={libraryImportOpen}
        loading={libraryImporting !== null}
        onClose={() => setLibraryImportOpen(false)}
        onImport={handleLibraryImport}
      />

      <Dialog
        open={deleteTarget !== null}
        onClose={() => setDeleteTarget(null)}
      >
        <DialogTitle>{t('report:delete_confirm_title', 'Confirm deletion')}</DialogTitle>
        <DialogContent>
          <DialogContentText>
            {t('report:delete_confirm_body', 'This will permanently delete the game and all associated analysis data. Are you sure?')}
          </DialogContentText>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDeleteTarget(null)} disabled={deleteLoading}>
            {t('common:cancel', 'Cancel')}
          </Button>
          <Button onClick={handleDeleteConfirm} color="error" disabled={deleteLoading}>
            {t('report:delete_game', 'Delete game')}
          </Button>
        </DialogActions>
      </Dialog>
    </>
  );
}
