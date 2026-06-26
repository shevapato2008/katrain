import { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import SearchIcon from '@mui/icons-material/Search';
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
  type CreateUserGameParams,
  type UserGameDetail,
  type UserGameSummary,
} from '../../api/userGamesApi';
import { ReportsAPI, type ReportQueueSummary, type ReportTaskSummary } from '../../api/reportApi';
import PlaybackBar from '../../../components/live/PlaybackBar';
import ReportGameCard, { type ReportGameStatus } from '../../components/report/ReportGameCard';
import ReportImportMenu from '../../components/report/ReportImportMenu';
import ReportLibraryImportDialog from '../../components/report/ReportLibraryImportDialog';
import ReportLocalImportDialog, {
  type LocalImportPayload,
} from '../../components/report/ReportLocalImportDialog';

const PAGE_SIZE = 12;
const POLL_INTERVAL_MS = 2000;

type ImportAction = 'save' | 'normal' | 'deep' | null;

function isActiveTask(task: ReportTaskSummary) {
  return task.status === 'pending' || task.status === 'running';
}

function optimisticTask(gameId: string, reportType: 'normal' | 'deep', totalMoves: number): ReportTaskSummary {
  return {
    id: -Math.floor(Date.now() + Math.random() * 1000),
    user_game_id: gameId,
    status: 'pending',
    report_type: reportType,
    total_moves: totalMoves,
    analyzed_moves: 0,
    requested_visits: reportType === 'deep' ? 2000 : 500,
  };
}

function toLocalCreateParams(payload: LocalImportPayload): CreateUserGameParams {
  return {
    sgf_content: payload.sgfContent,
    source: 'import',
    title: payload.title,
    player_black: payload.playerBlack,
    player_white: payload.playerWhite,
    black_rank: payload.blackRank,
    white_rank: payload.whiteRank,
    board_size: payload.boardSize,
    rules: payload.rules,
    komi: payload.komi,
    move_count: payload.moveCount,
    category: 'game',
  };
}

function toLibraryCreateParams(album: KifuAlbumSummary, sgfContent: string): CreateUserGameParams {
  return {
    sgf_content: sgfContent,
    source: 'kifu_library',
    title: album.event || `${album.player_black} vs ${album.player_white}`,
    player_black: album.player_black,
    player_white: album.player_white,
    black_rank: album.black_rank || undefined,
    white_rank: album.white_rank || undefined,
    result: album.result || undefined,
    board_size: album.board_size,
    rules: album.rules || 'chinese',
    komi: album.komi ?? 7.5,
    move_count: album.move_count,
    category: 'game',
    event: album.event || undefined,
    round_name: album.round_name || undefined,
    game_date: album.date_played || undefined,
  };
}

export default function ReportsPage() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const { token, isAuthenticated } = useAuth();
  const { t } = useTranslation();

  const page = Math.max(1, Number(searchParams.get('page')) || 1);
  const query = searchParams.get('q') || '';

  const [games, setGames] = useState<UserGameSummary[]>([]);
  const [totalGames, setTotalGames] = useState(0);
  const [gamesLoading, setGamesLoading] = useState(true);
  const [gamesError, setGamesError] = useState<string | null>(null);
  const [searchInput, setSearchInput] = useState(query);

  const [tasks, setTasks] = useState<ReportTaskSummary[]>([]);
  const [optimisticTasks, setOptimisticTasks] = useState<ReportTaskSummary[]>([]);
  const [taskError, setTaskError] = useState<string | null>(null);
  const [queueSummary, setQueueSummary] = useState<ReportQueueSummary | null>(null);

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
      setGamesError(error instanceof Error ? error.message : t('report:load_games_failed', 'Failed to load game list'));
    } finally {
      setGamesLoading(false);
    }
  }, [isAuthenticated, page, query, token]);

  const loadTasks = useCallback(async () => {
    if (!token || !isAuthenticated) {
      return;
    }
    try {
      const [taskResponse, summaryResponse] = await Promise.all([
        ReportsAPI.list(token),
        ReportsAPI.summary(token),
      ]);
      setTasks(taskResponse);
      setQueueSummary(summaryResponse);
      setTaskError(null);
    } catch (error) {
      setTaskError(error instanceof Error ? error.message : t('report:load_tasks_failed', 'Failed to load report tasks'));
    }
  }, [isAuthenticated, token]);

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
    loadTasks().catch(() => {});
  }, [loadTasks]);

  const allTasks = useMemo(() => [...optimisticTasks, ...tasks], [optimisticTasks, tasks]);
  const hasActiveTasks = useMemo(() => allTasks.some((task) => isActiveTask(task)), [allTasks]);

  useEffect(() => {
    if (!hasActiveTasks) return;
    const timer = window.setInterval(() => {
      loadTasks().catch(() => {});
    }, POLL_INTERVAL_MS);
    return () => window.clearInterval(timer);
  }, [hasActiveTasks, loadTasks]);

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
        setGamesError(error instanceof Error ? error.message : t('report:load_games_failed', 'Failed to load game list'));
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

  const reportStatesByGame = useMemo<Record<string, ReportGameStatus>>(() => {
    const result: Record<string, ReportGameStatus> = {};
    for (const task of [...allTasks].sort((a, b) => b.id - a.id)) {
      const state = result[task.user_game_id] || {};
      const typeKey = task.report_type === 'deep' ? 'Deep' : 'Normal';
      if (task.status === 'completed') {
        const completedKey = `completed${typeKey}` as keyof ReportGameStatus;
        if (!state[completedKey]) {
          state[completedKey] = task;
        }
      }
      if (isActiveTask(task)) {
        const activeKey = `active${typeKey}` as keyof ReportGameStatus;
        if (!state[activeKey]) {
          state[activeKey] = task;
        }
      }
      if (task.status === 'failed') {
        const failedKey = `failed${typeKey}` as keyof ReportGameStatus;
        if (!state[failedKey]) {
          state[failedKey] = task;
        }
      }
      result[task.user_game_id] = state;
    }
    return result;
  }, [allTasks]);

  const selectedSummary = useMemo(
    () => games.find((game) => game.id === selectedGameId) || null,
    [games, selectedGameId],
  );

  const totalPages = Math.max(1, Math.ceil(totalGames / PAGE_SIZE));

  const refreshAfterMutation = useCallback(async () => {
    await Promise.all([loadGames(), loadTasks()]);
  }, [loadGames, loadTasks]);

  const createReportForGame = useCallback(
    async (game: UserGameSummary | UserGameDetail, reportType: 'normal' | 'deep') => {
      if (!token) return;

      const optimistic = optimisticTask(game.id, reportType, game.move_count);
      setOptimisticTasks((current) => [optimistic, ...current]);

      try {
        const created = await ReportsAPI.create(token, {
          user_game_id: game.id,
          report_type: reportType,
        });
        setOptimisticTasks((current) => current.filter((task) => task.id !== optimistic.id));
        setTasks((current) => [created, ...current.filter((task) => task.id !== created.id)]);
      } catch (error) {
        setOptimisticTasks((current) => current.filter((task) => task.id !== optimistic.id));
        throw error;
      }
    },
    [token],
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
        const createdGame = await UserGamesAPI.create(token, toLocalCreateParams(payload));
        await focusImportedGame(createdGame);
        if (reportType) {
          await createReportForGame(createdGame, reportType);
        }
        setLocalImportOpen(false);
        await loadTasks();
      } catch (error) {
        setTaskError(error instanceof Error ? error.message : t('report:import_failed', 'Failed to import SGF'));
      } finally {
        setLocalImporting(null);
      }
    },
    [createReportForGame, focusImportedGame, loadTasks, token],
  );

  const handleLibraryImport = useCallback(
    async (album: KifuAlbumSummary, reportType?: 'normal' | 'deep') => {
      if (!token) return;
      const action: ImportAction = reportType || 'save';
      setLibraryImporting(action);
      setTaskError(null);
      try {
        const detail = await KifuAPI.getAlbum(album.id);
        const createdGame = await UserGamesAPI.create(token, toLibraryCreateParams(album, detail.sgf_content));
        await focusImportedGame(createdGame);
        if (reportType) {
          await createReportForGame(createdGame, reportType);
        }
        setLibraryImportOpen(false);
        await loadTasks();
      } catch (error) {
        setTaskError(error instanceof Error ? error.message : t('report:library_import_failed', 'Failed to import from library'));
      } finally {
        setLibraryImporting(null);
      }
    },
    [createReportForGame, focusImportedGame, loadTasks, token],
  );

  const handleCreateReport = useCallback(
    async (game: UserGameSummary, reportType: 'normal' | 'deep') => {
      try {
        await createReportForGame(game, reportType);
      } catch (error) {
        setTaskError(error instanceof Error ? error.message : t('report:create_task_failed', 'Failed to create report task'));
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
      setTaskError(error instanceof Error ? error.message : t('report:delete_failed', 'Failed to delete game'));
    } finally {
      setDeleteLoading(false);
      setDeleteTarget(null);
    }
  }, [token, deleteTarget, selectedGameId, refreshAfterMutation]);

  const handleRetry = useCallback(
    async (taskId: number) => {
      if (!token) return;
      try {
        await ReportsAPI.retry(token, taskId);
        await loadTasks();
      } catch (error) {
        setTaskError(error instanceof Error ? error.message : t('report:retry_failed', 'Failed to retry report'));
      }
    },
    [token, loadTasks],
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
      <Box sx={{ display: 'flex', height: '100%', overflow: 'hidden' }}>
        <Box
          sx={{
            flex: 1,
            minWidth: 0,
            display: 'flex',
            flexDirection: 'column',
            overflow: 'hidden',
            p: 3,
            gap: 2,
          }}
        >
          <Box>
            <Typography variant="h4" sx={{ fontWeight: 700, letterSpacing: '-0.02em' }}>
              {t('report:my_reports', 'Review')}
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mt: 0.75 }}>
              {t('report:page_hint', 'Select a game on the right to preview. Create reports from the game card.')}
            </Typography>
          </Box>

          {taskError && (
            <Alert severity="error" onClose={() => setTaskError(null)}>
              {taskError}
            </Alert>
          )}

          <Box
            sx={{
              flex: 1,
              minHeight: 0,
              display: 'flex',
              flexDirection: 'column',
              borderRadius: 3,
              bgcolor: '#111111',
              border: '1px solid rgba(255,255,255,0.06)',
              overflow: 'hidden',
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

            <Box sx={{ flex: 1, minHeight: 0, display: 'flex', justifyContent: 'center', alignItems: 'center', p: 2 }}>
              {previewLoading || gamesLoading ? (
                <CircularProgress />
              ) : previewMoves.length > 0 ? (
                <LiveBoard
                  moves={previewMoves}
                  stoneColors={previewColors}
                  currentMove={previewCurrentMove}
                  boardSize={previewBoardSize}
                  showCoordinates
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
          sx={{
            width: 520,
            flexShrink: 0,
            borderLeft: '1px solid rgba(255,255,255,0.06)',
            display: 'flex',
            flexDirection: 'column',
            overflow: 'hidden',
            bgcolor: 'rgba(20,20,20,0.98)',
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

          <Box sx={{ flex: 1, minHeight: 0, overflow: 'auto', px: 2.5, pb: 2 }}>
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
