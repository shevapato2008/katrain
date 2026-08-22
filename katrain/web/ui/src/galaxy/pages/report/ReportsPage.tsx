import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import SearchIcon from '@mui/icons-material/Search';
import ContentPageHeader from '../../components/layout/ContentPageHeader';
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
  toLibraryUserGameParams,
  toLocalUserGameParams,
} from '../../../features/report/reportModel';
import PlaybackBar from '../../../components/live/PlaybackBar';
import ReportGameCard from '../../components/report/ReportGameCard';
import ReportImportMenu from '../../components/report/ReportImportMenu';
import ReportLibraryImportDialog from '../../components/report/ReportLibraryImportDialog';
import ReportLocalImportDialog, {
  type LocalImportPayload,
} from '../../components/report/ReportLocalImportDialog';

const PAGE_SIZE = 12;

type ImportAction = 'save' | 'normal' | 'deep' | null;

export default function ReportsPage() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const { token, isAuthenticated } = useAuth();
  const { t } = useTranslation();
  const translationRef = useRef(t);
  translationRef.current = t;

  const page = Math.max(1, Number(searchParams.get('page')) || 1);
  const query = searchParams.get('q') || '';

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
    clearError: clearReportTasksError,
    refresh: refreshTasks,
    createReport,
    retryReport,
  } = useReportTasks(isAuthenticated ? token : null);

  const [selectedGameId, setSelectedGameId] = useState<string | null>(null);
  const [selectedGame, setSelectedGame] = useState<UserGameDetail | null>(null);
  const [previewMoves, setPreviewMoves] = useState<string[]>([]);
  const [previewColors, setPreviewColors] = useState<('B' | 'W')[]>([]);
  const [previewBoardSize, setPreviewBoardSize] = useState(19);
  const [previewCurrentMove, setPreviewCurrentMove] = useState(0);
  const [previewLoading, setPreviewLoading] = useState(false);

  const [localImportOpen, setLocalImportOpen] = useState(false);
  const [libraryImportOpen, setLibraryImportOpen] = useState(false);
  const [localImporting, setLocalImporting] = useState<ImportAction>(null);
  const [libraryImporting, setLibraryImporting] = useState<ImportAction>(null);

  const [deleteTarget, setDeleteTarget] = useState<string | null>(null);
  const [deleteLoading, setDeleteLoading] = useState(false);

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
      try {
        const createdGame = await UserGamesAPI.create(token, toLocalUserGameParams(payload));
        await focusImportedGame(createdGame);
        if (reportType) {
          await createReportForGame(createdGame, reportType);
        }
        setLocalImportOpen(false);
        await refreshTasks();
      } catch (error) {
        setTaskError(error instanceof Error ? error.message : translationRef.current('report:import_failed', 'Failed to import SGF'));
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
      try {
        const detail = await KifuAPI.getAlbum(album.id);
        const createdGame = await UserGamesAPI.create(token, toLibraryUserGameParams(album, detail.sgf_content));
        await focusImportedGame(createdGame);
        if (reportType) {
          await createReportForGame(createdGame, reportType);
        }
        setLibraryImportOpen(false);
        await refreshTasks();
      } catch (error) {
        setTaskError(error instanceof Error ? error.message : translationRef.current('report:library_import_failed', 'Failed to import from library'));
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

  if (!isAuthenticated) {
    return (
      <Box sx={{ p: 4 }}>
        <Alert severity="info">{t('report:login_required', 'Please log in to view and generate game reviews.')}</Alert>
      </Box>
    );
  }

  return (
    <>
      {/* 承重：**基态是窄档**，`@media (min-width:900px)` 才回到并排 —— 与 `BoardPageShell`
          同一档、同一写法（900 / 1200 / 1536）。这样写而不是反过来，是因为宽档那一支
          必须与改动前逐字一致：宽档本来就是对的，这次只补窄档。

          改之前这里是一条写死的 `flex-direction: row; flex-wrap: nowrap`，右栏 `width:520`
          且 `flexShrink:0`。430 视口下实测：左栏被压到 **48px**（只剩 p:3 的左右内边距）、
          右栏仍占 520，两栏合计 **568 > 430**，`split.scrollWidth 568 vs clientWidth 430`
          —— 超出的部分被 `overflow:hidden` 直接切掉，棋局卡右边 118px 永远看不到，
          也没有任何地方能滚过去。 */}
      <Box
        data-testid="reports-split"
        sx={{
          display: 'flex',
          flexDirection: 'column',
          height: '100%',
          overflowY: 'auto',
          overflowX: 'hidden',
          // 底部导航是 position:fixed 的浮层，窄档下会盖住内容最后 64px。
          // 与 BoardPageShell 同一句。
          pb: 'calc(64px + env(safe-area-inset-bottom))',
          '@media (min-width:900px)': {
            flexDirection: 'row',
            overflow: 'hidden',
            pb: 0,
          },
        }}
      >
        <Box
          data-testid="reports-preview-pane"
          sx={{
            // 窄档：按内容占高、整幅宽，滚动交给外层那一条。
            flex: 'none',
            width: '100%',
            minWidth: 0,
            display: 'flex',
            flexDirection: 'column',
            overflow: 'visible',
            p: 3,
            gap: 2,
            '@media (min-width:900px)': {
              flex: 1,
              width: 'auto',
              overflow: 'hidden',
            },
          }}
        >
          <Box>
            <ContentPageHeader title={t('report:my_reports', 'Review')} />
            {/* 操作提示原来是页头第二行。spec §2.4 禁长副标题进页头，下沉到正文首行。 */}
            <Typography variant="body2" color="text.secondary" sx={{ mt: 0.75 }}>
              {t('report:page_hint', 'Select a game on the right to preview. Create reports from the game card.')}
            </Typography>
          </Box>

          {(taskError || reportTasksError) && (
            <Alert severity="error" onClose={() => {
              setTaskError(null);
              clearReportTasksError();
            }}>
              {taskError || reportTasksError}
            </Alert>
          )}

          <Box
            sx={{
              // 窄档没有「剩余高度」可分 —— 外层已经是滚动列，flex:1 在这里会退化成
              // 由内容决定，量到多少算多少。改成按内容占高，棋盘那一格自己撑出方形。
              flex: 'none',
              minHeight: 0,
              display: 'flex',
              flexDirection: 'column',
              borderRadius: 3,
              bgcolor: '#111111',
              border: '1px solid rgba(255,255,255,0.06)',
              overflow: 'hidden',
              '@media (min-width:900px)': { flex: 1 },
            }}
          >
            <Box sx={{ px: 3, py: 2, borderBottom: '1px solid rgba(255,255,255,0.06)' }}>
              <Typography variant="h5" sx={{ fontWeight: 700 }}>
                {selectedGame?.title || selectedGame?.event || selectedSummary?.title || selectedSummary?.event || t('report:select_game', 'Select a game')}
              </Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
                {selectedGame
                  ? `${selectedGame.player_black || t('report:black', 'Black')} vs ${selectedGame.player_white || t('report:white', 'White')} · ${selectedGame.move_count} ${t('report:moves_unit', 'moves')}`
                  : t('report:select_game_hint', 'Select a game from the right panel, or import a new SGF / library game.')}
              </Typography>
            </Box>

            <Box
              data-testid="reports-preview-stage"
              sx={{
                // 窄档用 1:1 定尺（同 BoardPageShell 的 board-stage），宽档仍旧吃剩余高度。
                flex: 'none',
                aspectRatio: '1 / 1',
                minHeight: 0,
                display: 'flex',
                justifyContent: 'center',
                alignItems: 'center',
                p: 2,
                '@media (min-width:900px)': { flex: 1, aspectRatio: 'auto' },
              }}
            >
              {previewLoading || gamesLoading ? (
                <CircularProgress />
              ) : previewMoves.length > 0 ? (
                <LiveBoard
                  moves={previewMoves}
                  stoneColors={previewColors}
                  currentMove={previewCurrentMove}
                  boardSize={previewBoardSize}
                  showCoordinates
                  /* 两个 400px 地板必须关掉：430 档下这一格净宽只有 382，
                     默认的 `minHeight: 400` 会把定尺格顶破。已迁的两页同样传 0/0
                     （见 ReportDetailPage.tsx 那段注释）。宽档这一格本来就 > 400，
                     去掉地板不改变宽档任何一个数。 */
                  minimumCanvasSize={0}
                  minContainerHeight={0}
                />
              ) : (
                <Typography variant="body2" color="text.secondary">
                  {t('report:no_preview', 'No game to preview yet.')}
                </Typography>
              )}
            </Box>

            <PlaybackBar
              currentMove={previewCurrentMove}
              totalMoves={previewMoves.length}
              onMoveChange={setPreviewCurrentMove}
            />
          </Box>
        </Box>

        <Box
          data-testid="reports-list-pane"
          sx={{
            width: '100%',
            flexShrink: 1,
            // 窄档两栏上下堆叠，左边那条竖线会变成横在中间的一道，改到顶边。
            borderTop: '1px solid rgba(255,255,255,0.06)',
            display: 'flex',
            flexDirection: 'column',
            overflow: 'visible',
            bgcolor: 'rgba(20,20,20,0.98)',
            '@media (min-width:900px)': {
              width: 520,
              flexShrink: 0,
              borderTop: 'none',
              borderLeft: '1px solid rgba(255,255,255,0.06)',
              overflow: 'hidden',
            },
          }}
        >
          <Box sx={{ p: 3, pb: 2 }}>
            <Typography variant="h5" sx={{ fontWeight: 700 }}>
              {t('report:game_list', 'Game List')}
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mt: 0.75, mb: queueSummary && (queueSummary.pending > 0 || queueSummary.running > 0 || queueSummary.failed > 0) ? 1 : 2 }}>
              {t('report:game_list_hint', '{count} games. Search by player, title, or event.').replace('{count}', totalGames.toLocaleString())}
            </Typography>
            {queueSummary && (queueSummary.pending > 0 || queueSummary.running > 0 || queueSummary.failed > 0) && (
              <Stack direction="row" spacing={0.75} sx={{ mb: 1.5 }}>
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
            <Stack spacing={1.5}>
              <ReportImportMenu
                onImportLocal={() => setLocalImportOpen(true)}
                onImportLibrary={() => setLibraryImportOpen(true)}
              />
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
                    bgcolor: 'rgba(255,255,255,0.03)',
                  },
                }}
              />
            </Stack>
          </Box>

          {gamesError && (
            <Box sx={{ px: 3, pb: 2 }}>
              <Alert severity="error">{gamesError}</Alert>
            </Box>
          )}

          <Box
            data-testid="reports-list-scroll"
            sx={{
              // 窄档不在自己内部滚 —— 页面已经是一条滚动列，列表里再套一个滚动区
              // 就成了「中段里再套中段」，两条滚动条互相抢。
              flex: 'none',
              minHeight: 0,
              overflow: 'visible',
              px: 2.5,
              pb: 2,
              '@media (min-width:900px)': { flex: 1, overflow: 'auto' },
            }}
          >
            {gamesLoading ? (
              <Box sx={{ height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <CircularProgress size={28} />
              </Box>
            ) : games.length === 0 ? (
              <Box sx={{ height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', px: 2 }}>
                <Typography variant="body2" color="text.secondary">
                  {query ? t('report:no_match', 'No games matching “{query}”.').replace('{query}', query) : t('report:no_games', 'No games yet. Import one to generate a report.')}
                </Typography>
              </Box>
            ) : (
              <Stack spacing={1.25}>
                {games.map((game, index) => (
                  <Fade key={game.id} in timeout={200 + index * 40}>
                    <Box>
                      <ReportGameCard
                        game={game}
                        selected={game.id === selectedGameId}
                        reportState={reportStatesByGame[game.id] || {}}
                        onSelect={() => setSelectedGameId(game.id)}
                        onCreateReport={(reportType) => handleCreateReport(game, reportType)}
                        onOpenReport={(taskId) => navigate(`/galaxy/report/${taskId}`)}
                        onRetry={(taskId) => handleRetry(taskId)}
                        onDelete={() => setDeleteTarget(game.id)}
                      />
                    </Box>
                  </Fade>
                ))}
              </Stack>
            )}
          </Box>

          {totalPages > 1 && (
            <Box
              sx={{
                display: 'flex',
                justifyContent: 'center',
                py: 1.5,
                borderTop: '1px solid rgba(255,255,255,0.06)',
                flexShrink: 0,
              }}
            >
              <Pagination count={totalPages} page={page} onChange={handlePageChange} color="primary" size="small" />
            </Box>
          )}
        </Box>
      </Box>

      <ReportLocalImportDialog
        open={localImportOpen}
        loading={localImporting !== null}
        onClose={() => setLocalImportOpen(false)}
        onSubmit={handleLocalImport}
      />

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
