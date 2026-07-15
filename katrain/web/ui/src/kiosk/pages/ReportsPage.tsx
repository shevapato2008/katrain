import SearchIcon from '@mui/icons-material/Search';
import {
  Alert, Box, Button, Chip, CircularProgress, Dialog, DialogActions, DialogContent,
  DialogContentText, DialogTitle, InputAdornment, Pagination, PaginationItem, Stack,
  TextField, Typography,
} from '@mui/material';
import { useCallback, useEffect, useRef, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';

import { KifuAPI } from '../../api/kifuApi';
import type { ReportType } from '../../api/reportApi';
import { UserGamesAPI, type UserGameDetail, type UserGameSummary } from '../../api/userGamesApi';
import LiveBoard from '../../components/live/LiveBoard';
import PlaybackBar from '../../components/live/PlaybackBar';
import { useAuth } from '../../context/AuthContext';
import { toLibraryUserGameParams, toLocalUserGameParams } from '../../features/report/reportModel';
import { useReportTasks } from '../../features/report/useReportTasks';
import { useTranslation } from '../../hooks/useTranslation';
import type { KifuAlbumSummary } from '../../types/kifu';
import { sgfToMoves } from '../../utils/sgfSerializer';
import ReportGameCard from '../components/report/ReportGameCard';
import ReportImportMenu from '../components/report/ReportImportMenu';
import ReportLibraryImportDialog from '../components/report/ReportLibraryImportDialog';
import ReportLocalImportDialog, { type LocalImportPayload } from '../components/report/ReportLocalImportDialog';

const PAGE_SIZE = 12;
type ImportAction = 'save' | ReportType | null;

const messageOf = (error: unknown, fallback: string) => error instanceof Error ? error.message : fallback;

export default function ReportsPage() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const { token, isAuthenticated } = useAuth();
  const { t } = useTranslation();
  const translationRef = useRef(t);
  translationRef.current = t;

  const page = Math.max(1, Number(searchParams.get('page')) || 1);
  const query = searchParams.get('q') || '';
  const [searchInput, setSearchInput] = useState(query);
  const [games, setGames] = useState<UserGameSummary[]>([]);
  const [totalGames, setTotalGames] = useState(0);
  const [gamesLoading, setGamesLoading] = useState(Boolean(token));
  const [gamesError, setGamesError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const [selectedGameId, setSelectedGameId] = useState<string | null>(null);
  const [selectedGame, setSelectedGame] = useState<UserGameDetail | null>(null);
  const [previewMoves, setPreviewMoves] = useState<string[]>([]);
  const [previewColors, setPreviewColors] = useState<('B' | 'W')[]>([]);
  const [previewBoardSize, setPreviewBoardSize] = useState(19);
  const [previewCurrentMove, setPreviewCurrentMove] = useState(0);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const previewRequestRef = useRef(0);

  const [localImportOpen, setLocalImportOpen] = useState(false);
  const [libraryImportOpen, setLibraryImportOpen] = useState(false);
  const [localImporting, setLocalImporting] = useState<ImportAction>(null);
  const [libraryImporting, setLibraryImporting] = useState<ImportAction>(null);
  const [deleteTarget, setDeleteTarget] = useState<string | null>(null);
  const [deleteLoading, setDeleteLoading] = useState(false);

  const {
    queueSummary, reportStatesByGame, error: tasksError, clearError: clearTasksError,
    refresh: refreshTasks, createReport, retryReport,
  } = useReportTasks(isAuthenticated ? token : null);

  const loadGames = useCallback(async () => {
    if (!token || !isAuthenticated) {
      setGamesLoading(false);
      return null;
    }
    setGamesLoading(true);
    setGamesError(null);
    try {
      const response = await UserGamesAPI.list(token, {
        page, page_size: PAGE_SIZE, q: query || undefined, sort: 'created_at_desc',
      });
      setGames(response.items);
      setTotalGames(response.total);
      return response;
    } catch (error) {
      setGamesError(messageOf(error, translationRef.current('report:load_games_failed', '加载棋谱失败，请重试。')));
      return null;
    } finally {
      setGamesLoading(false);
    }
  }, [isAuthenticated, page, query, token]);

  const clearPreview = useCallback(() => {
    setSelectedGame(null);
    setPreviewMoves([]);
    setPreviewColors([]);
    setPreviewCurrentMove(0);
    setPreviewError(null);
  }, []);

  const applyPreview = useCallback((game: UserGameDetail) => {
    if (!game.sgf_content.trim()) throw new Error(translationRef.current('report:missing_sgf', '棋谱缺少 SGF 内容'));
    if (!/^\s*\(\s*;/.test(game.sgf_content) || !/\)\s*$/.test(game.sgf_content)) {
      throw new Error(translationRef.current('report:malformed_sgf', '无法解析棋谱'));
    }
    const parsed = sgfToMoves(game.sgf_content);
    const boardSize = parsed.metadata.boardSize || game.board_size || 19;
    if (![9, 13, 19].includes(boardSize)) throw new Error(translationRef.current('report:unsupported_board', '不支持此棋盘尺寸'));
    setSelectedGame(game);
    setPreviewMoves(parsed.moves);
    setPreviewColors(parsed.stoneColors);
    setPreviewBoardSize(boardSize);
    setPreviewCurrentMove(parsed.moves.length);
    setPreviewError(null);
  }, []);

  const loadPreview = useCallback(async (gameId: string) => {
    if (!token || !isAuthenticated) return;
    const request = ++previewRequestRef.current;
    setPreviewLoading(true);
    setPreviewError(null);
    try {
      const game = await UserGamesAPI.get(token, gameId);
      if (request !== previewRequestRef.current) return;
      applyPreview(game);
    } catch (error) {
      if (request !== previewRequestRef.current) return;
      clearPreview();
      setPreviewError(messageOf(error, translationRef.current('report:preview_failed', '棋谱预览加载失败')));
    } finally {
      if (request === previewRequestRef.current) setPreviewLoading(false);
    }
  }, [applyPreview, clearPreview, isAuthenticated, token]);

  useEffect(() => setSearchInput(query), [query]);
  useEffect(() => { void loadGames(); }, [loadGames]);
  useEffect(() => {
    if (games.length === 0) {
      setSelectedGameId(null);
      clearPreview();
      return;
    }
    setSelectedGameId((current) => current && games.some(({ id }) => id === current) ? current : games[0].id);
  }, [clearPreview, games]);
  useEffect(() => {
    if (!selectedGameId) return;
    if (selectedGame?.id === selectedGameId) return;
    void loadPreview(selectedGameId);
    return () => { previewRequestRef.current += 1; };
  }, [loadPreview, selectedGame?.id, selectedGameId]);

  const totalPages = Math.max(1, Math.ceil(totalGames / PAGE_SIZE));
  const createForGame = useCallback((game: UserGameSummary, reportType: ReportType) => (
    createReport({ userGameId: game.id, reportType, totalMoves: game.move_count })
  ), [createReport]);

  const updateLocation = useCallback((nextQuery: string, nextPage: number) => {
    const params: Record<string, string> = {};
    if (nextQuery) params.q = nextQuery;
    if (nextPage > 1) params.page = String(nextPage);
    setSearchParams(params);
  }, [setSearchParams]);
  const handleSearch = () => updateLocation(searchInput.trim(), 1);

  const focusImportedGame = useCallback(async (game: UserGameDetail) => {
    setSelectedGameId(game.id);
    applyPreview(game);
    setSearchInput('');
    if (page !== 1 || query) setSearchParams({});
    else await loadGames();
  }, [applyPreview, loadGames, page, query, setSearchParams]);

  const handleLocalImport = useCallback(async (payload: LocalImportPayload, reportType?: ReportType) => {
    if (!token) return;
    setLocalImporting(reportType ?? 'save');
    setActionError(null);
    try {
      const created = await UserGamesAPI.create(token, toLocalUserGameParams(payload));
      await focusImportedGame(created);
      if (reportType) await createForGame(created, reportType);
      setLocalImportOpen(false);
      await refreshTasks();
    } catch (error) {
      setActionError(messageOf(error, translationRef.current('report:import_failed', '导入失败，请重试。')));
    } finally {
      setLocalImporting(null);
    }
  }, [createForGame, focusImportedGame, refreshTasks, token]);

  const handleLibraryImport = useCallback(async (album: KifuAlbumSummary, reportType?: ReportType) => {
    if (!token) return;
    setLibraryImporting(reportType ?? 'save');
    setActionError(null);
    try {
      const albumDetail = await KifuAPI.getAlbum(album.id);
      const created = await UserGamesAPI.create(token, toLibraryUserGameParams(album, albumDetail.sgf_content));
      await focusImportedGame(created);
      if (reportType) await createForGame(created, reportType);
      setLibraryImportOpen(false);
      await refreshTasks();
    } catch (error) {
      setActionError(messageOf(error, translationRef.current('report:library_import_failed', '从棋谱库导入失败，请重试。')));
    } finally {
      setLibraryImporting(null);
    }
  }, [createForGame, focusImportedGame, refreshTasks, token]);

  const confirmDelete = useCallback(async () => {
    if (!token || !deleteTarget) return;
    const deletedId = deleteTarget;
    setDeleteLoading(true);
    setActionError(null);
    try {
      await UserGamesAPI.delete(token, deletedId);
      if (selectedGameId === deletedId) {
        setSelectedGameId(null);
        clearPreview();
      }
      const next = await loadGames();
      await refreshTasks();
      if (next && next.items.length === 0 && page > 1 && next.total > 0) updateLocation(query, page - 1);
      setDeleteTarget(null);
    } catch (error) {
      setActionError(messageOf(error, translationRef.current('report:delete_failed', '删除失败，请重试。')));
    } finally {
      setDeleteLoading(false);
    }
  }, [clearPreview, deleteTarget, loadGames, page, query, refreshTasks, selectedGameId, token, updateLocation]);

  if (!isAuthenticated) return <Alert severity="info">{t('report:login_required', '请先登录后查看复盘。')}</Alert>;

  const combinedError = actionError || tasksError;
  return (
    <>
      <Box data-testid="report-list-page" sx={{ display: 'flex', width: '100%', height: '100%', minWidth: 0, overflow: 'hidden' }}>
        <Box sx={{ width: '54%', minWidth: 0, display: 'flex', flexDirection: 'column', overflow: 'hidden', borderRight: 1, borderColor: 'divider' }}>
          <Box sx={{ flex: 1, minHeight: 0, display: 'grid', placeItems: 'center', p: 1.25, overflow: 'hidden' }}>
            {previewLoading ? <CircularProgress aria-label={t('report:preview_loading', '正在加载预览')} />
              : previewError ? (
                <Alert
                  severity="error"
                  action={<Button onClick={() => selectedGameId && void loadPreview(selectedGameId)} sx={{ minWidth: 48, minHeight: 48 }}>{t('report:retry_preview', '重试预览')}</Button>}
                  sx={{ maxWidth: '92%', overflowWrap: 'anywhere' }}
                >{previewError}</Alert>
              ) : selectedGame ? (
                <LiveBoard moves={previewMoves} stoneColors={previewColors} currentMove={previewCurrentMove} boardSize={previewBoardSize} showCoordinates />
              ) : (
                <Typography color="text.secondary">{t('report:no_preview', '选择一局棋谱预览')}</Typography>
              )}
          </Box>
          <Box data-testid="report-playback" sx={{ flexShrink: 0, minWidth: 0 }}>
            <PlaybackBar currentMove={previewCurrentMove} totalMoves={previewMoves.length} onMoveChange={setPreviewCurrentMove} touchSized />
          </Box>
        </Box>

        <Box data-testid="report-list-panel" sx={{ width: '46%', minWidth: 0, display: 'flex', flexDirection: 'column', overflow: 'hidden', bgcolor: 'background.default' }}>
          <Box sx={{ px: 2, pt: 1.25, pb: 1, flexShrink: 0, minWidth: 0 }}>
            <Stack direction="row" alignItems="center" spacing={1} sx={{ minWidth: 0 }}>
              <Box sx={{ flex: 1, minWidth: 0 }}>
                <Typography variant="h5" noWrap sx={{ fontFamily: "'Newsreader','Noto Serif SC',serif", fontWeight: 600 }}>{t('report:my_reports', '复盘')}</Typography>
                <Stack direction="row" spacing={0.6} sx={{ mt: 0.5, minWidth: 0, overflow: 'hidden' }}>
                  {queueSummary?.pending ? <Chip size="small" label={`${queueSummary.pending} ${t('report:summary_queued', '排队中')}`} /> : null}
                  {queueSummary?.running ? <Chip size="small" color="warning" variant="outlined" label={`${queueSummary.running} ${t('report:summary_running', '生成中')}`} /> : null}
                  {queueSummary?.failed ? <Chip size="small" color="error" variant="outlined" label={`${queueSummary.failed} ${t('report:summary_failed', '失败')}`} /> : null}
                </Stack>
              </Box>
              <ReportImportMenu onImportLocal={() => setLocalImportOpen(true)} onImportLibrary={() => setLibraryImportOpen(true)} />
            </Stack>
            <TextField
              fullWidth size="small" value={searchInput} onChange={(event) => setSearchInput(event.target.value)}
              onKeyDown={(event) => { if (event.key === 'Enter') handleSearch(); }}
              placeholder={t('report:search_placeholder', '搜索棋手、标题或赛事')}
              slotProps={{ input: { startAdornment: <InputAdornment position="start"><SearchIcon fontSize="small" /></InputAdornment> } }}
              sx={{ mt: 1, minWidth: 0, '& .MuiInputBase-root': { minHeight: 48 } }}
            />
            {combinedError && (
              <Alert
                severity="error"
                action={<Button onClick={() => { setActionError(null); clearTasksError(); void refreshTasks(); }} sx={{ minWidth: 48, minHeight: 48 }}>{t('report:retry_tasks', '重试任务')}</Button>}
                sx={{ mt: 1, py: 0, overflowWrap: 'anywhere' }}
              >{combinedError}</Alert>
            )}
            {gamesError && (
              <Alert severity="error" action={<Button onClick={() => void loadGames()} sx={{ minWidth: 48, minHeight: 48 }}>{t('common:retry', '重试')}</Button>} sx={{ mt: 1, py: 0 }}>{gamesError}</Alert>
            )}
          </Box>

          <Box data-testid="report-card-scroll" sx={{ flex: 1, minHeight: 0, minWidth: 0, overflowY: 'auto', overflowX: 'hidden', px: 1.5, pb: 1 }}>
            {gamesLoading && games.length === 0 ? <Box sx={{ height: '100%', display: 'grid', placeItems: 'center' }}><CircularProgress size={30} /></Box>
              : games.length === 0 ? <Box sx={{ height: '100%', display: 'grid', placeItems: 'center', px: 2 }}><Typography color="text.secondary">{query ? t('report:no_match', '没有匹配的棋谱') : t('report:no_games', '暂无棋谱，请先导入')}</Typography></Box>
                : <Stack spacing={1}>{games.map((game) => (
                  <ReportGameCard
                    key={game.id} game={game} selected={game.id === selectedGameId}
                    reportState={reportStatesByGame[game.id] || {}}
                    onSelect={() => setSelectedGameId(game.id)}
                    onCreateReport={(reportType) => { setActionError(null); void createForGame(game, reportType).catch(() => undefined); }}
                    onOpenReport={(taskId) => navigate(`/kiosk/report/${taskId}`)}
                    onRetry={(taskId) => { void retryReport(taskId).catch(() => undefined); }}
                    onDelete={() => setDeleteTarget(game.id)}
                  />
                ))}</Stack>}
          </Box>

          <Box data-testid="report-pagination" sx={{ minHeight: 48, flexShrink: 0, display: 'grid', placeItems: 'center', borderTop: 1, borderColor: 'divider', overflow: 'hidden' }}>
            {totalPages > 1 && <Pagination count={totalPages} page={page} onChange={(_event, nextPage) => updateLocation(query, nextPage)} size="small" siblingCount={0} boundaryCount={1} renderItem={(item) => <PaginationItem {...item} sx={{ minWidth: 48, minHeight: 48 }} />} />}
          </Box>
        </Box>
      </Box>

      <ReportLocalImportDialog open={localImportOpen} loading={localImporting !== null} onClose={() => setLocalImportOpen(false)} onSubmit={handleLocalImport} />
      <ReportLibraryImportDialog open={libraryImportOpen} loading={libraryImporting !== null} onClose={() => setLibraryImportOpen(false)} onImport={handleLibraryImport} />
      <Dialog open={deleteTarget !== null} onClose={() => { if (!deleteLoading) setDeleteTarget(null); }}>
        <DialogTitle>{t('report:delete_confirm_title', '确认删除棋谱')}</DialogTitle>
        <DialogContent><DialogContentText>{t('report:delete_confirm_body', '删除后将无法恢复，关联复盘数据也会一并删除。')}</DialogContentText></DialogContent>
        <DialogActions>
          <Button onClick={() => setDeleteTarget(null)} disabled={deleteLoading} sx={{ minWidth: 48, minHeight: 48 }}>{t('common:cancel', '取消')}</Button>
          <Button onClick={() => void confirmDelete()} color="error" disabled={deleteLoading} sx={{ minWidth: 48, minHeight: 48 }}>{t('report:confirm_delete', '确认删除')}</Button>
        </DialogActions>
      </Dialog>
    </>
  );
}
