import SearchIcon from '@mui/icons-material/Search';
import {
  Alert,
  Box,
  Button,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  IconButton,
  Pagination,
  PaginationItem,
  Stack,
  TextField,
  Typography,
} from '@mui/material';
import { useCallback, useEffect, useRef, useState } from 'react';

import { KifuAPI } from '../../../api/kifuApi';
import type { ReportType } from '../../../api/reportApi';
import { useTranslation } from '../../../hooks/useTranslation';
import type { KifuAlbumSummary } from '../../../types/kifu';

interface ReportLibraryImportDialogProps {
  open: boolean;
  loading?: boolean;
  error?: string | null;
  onClose: () => void;
  onImport: (album: KifuAlbumSummary, reportType?: ReportType) => void;
}

const PAGE_SIZE = 10;
const actionButtonSx = {
  minWidth: 48,
  minHeight: 48,
  px: 1,
  whiteSpace: 'normal',
  overflowWrap: 'anywhere',
  lineHeight: 1.15,
};

export default function ReportLibraryImportDialog({
  open,
  loading = false,
  error = null,
  onClose,
  onImport,
}: ReportLibraryImportDialogProps) {
  const { t } = useTranslation();
  const [queryInput, setQueryInput] = useState('');
  const [query, setQuery] = useState('');
  const [page, setPage] = useState(1);
  const [items, setItems] = useState<KifuAlbumSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [selectedAlbum, setSelectedAlbum] = useState<KifuAlbumSummary | null>(null);
  const [fetching, setFetching] = useState(false);
  const [fetchError, setFetchError] = useState(false);
  const requestGenerationRef = useRef(0);

  const fetchData = useCallback(async () => {
    if (!open) return;
    const requestGeneration = ++requestGenerationRef.current;
    setFetching(true);
    setFetchError(false);
    setSelectedAlbum(null);
    try {
      const response = await KifuAPI.getAlbums({
        ...(query ? { q: query } : {}),
        page,
        page_size: PAGE_SIZE,
      });
      if (requestGeneration !== requestGenerationRef.current) return;
      setItems(response.items);
      setTotal(response.total);
      setSelectedAlbum(response.items[0] ?? null);
    } catch {
      if (requestGeneration !== requestGenerationRef.current) return;
      setItems([]);
      setTotal(0);
      setSelectedAlbum(null);
      setFetchError(true);
    } finally {
      if (requestGeneration === requestGenerationRef.current) setFetching(false);
    }
  }, [open, page, query]);

  useEffect(() => {
    void fetchData();
    return () => { requestGenerationRef.current += 1; };
  }, [fetchData]);

  const search = () => {
    const nextQuery = queryInput.trim();
    setPage(1);
    if (nextQuery === query && page === 1) void fetchData();
    else setQuery(nextQuery);
  };
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const submit = (reportType?: ReportType) => {
    if (!selectedAlbum || loading || fetching) return;
    if (reportType) onImport(selectedAlbum, reportType);
    else onImport(selectedAlbum);
  };

  return (
    <Dialog
      open={open}
      onClose={() => { if (!loading) onClose(); }}
      fullWidth
      maxWidth={false}
      slotProps={{
        paper: {
          sx: {
            width: 'calc(100vw - 24px)',
            maxWidth: '960px',
            height: 'calc(100dvh - 24px)',
            maxHeight: '576px',
            overflow: 'hidden',
            display: 'flex',
            flexDirection: 'column',
          },
        },
      }}
    >
      <DialogTitle sx={{ flexShrink: 0, py: 1.5 }}>{t('report:import_library', '从棋谱库导入')}</DialogTitle>
      <DialogContent
        data-testid="report-library-import-content"
        dividers
        sx={{ minWidth: 0, minHeight: 0, overflowY: 'auto', overflowX: 'hidden', py: 1.5 }}
      >
        <Stack spacing={1.5} sx={{ minWidth: 0 }}>
          {error && <Alert severity="error">{error}</Alert>}
          <Stack direction="row" spacing={1} sx={{ minWidth: 0 }}>
            <TextField
              value={queryInput}
              onChange={(event) => setQueryInput(event.target.value)}
              onKeyDown={(event) => { if (event.key === 'Enter') search(); }}
              disabled={loading}
              placeholder={t('report:search_placeholder_lib', '按棋手、赛事、日期搜索')}
              fullWidth
              slotProps={{
                htmlInput: {
                  'aria-label': t('report:search_library', '搜索棋谱库'),
                  style: { minHeight: 48, minWidth: 48, boxSizing: 'border-box' },
                },
              }}
              sx={{ minWidth: 0, minHeight: 48, '& .MuiInputBase-root': { minHeight: 48 } }}
            />
            <IconButton
              aria-label={t('report:search', '搜索')}
              onClick={search}
              disabled={loading}
              sx={{ minWidth: 48, minHeight: 48, flexShrink: 0 }}
            >
              <SearchIcon />
            </IconButton>
          </Stack>

          {fetching ? (
            <Box sx={{ minHeight: 96, display: 'grid', placeItems: 'center' }}>
              <CircularProgress size={32} aria-label={t('report:loading', '加载中...')} />
            </Box>
          ) : fetchError ? (
            <Alert
              severity="error"
              action={<Button color="inherit" onClick={() => { void fetchData(); }} sx={actionButtonSx}>{t('common:retry', '重试')}</Button>}
            >
              {t('report:library_load_failed', '棋谱加载失败，请重试。')}
            </Alert>
          ) : items.length === 0 ? (
            <Typography color="text.secondary">{t('report:no_results', '没有搜索到棋谱。')}</Typography>
          ) : (
            <Stack spacing={1} sx={{ minWidth: 0 }}>
              {items.map((item) => {
                const selected = selectedAlbum?.id === item.id;
                const title = item.event || t(
                  'report:library_players_title',
                  '{black} 对 {white}',
                )
                  .replace('{black}', item.player_black)
                  .replace('{white}', item.player_white);
                return (
                  <Button
                    key={item.id}
                    aria-pressed={selected}
                    aria-label={t(
                      'report:library_game_accessible',
                      '{title}，黑方 {black} 对 白方 {white}',
                    )
                      .replace('{title}', title)
                      .replace('{black}', item.player_black)
                      .replace('{white}', item.player_white)}
                    onClick={() => setSelectedAlbum(item)}
                    disabled={loading || fetching}
                    variant={selected ? 'contained' : 'outlined'}
                    sx={{
                      minWidth: 48,
                      minHeight: 56,
                      width: '100%',
                      justifyContent: 'stretch',
                      textAlign: 'left',
                      whiteSpace: 'normal',
                      overflowWrap: 'anywhere',
                      px: 1.5,
                    }}
                  >
                    <Box sx={{ display: 'grid', gridTemplateColumns: 'minmax(0,1fr) auto', gap: 1, width: '100%', minWidth: 0 }}>
                      <Box sx={{ minWidth: 0 }}>
                        <Typography noWrap variant="body2" sx={{ fontWeight: 600 }}>{title}</Typography>
                        <Typography noWrap variant="caption" color="text.secondary">
                          {item.player_black} {item.black_rank || ''} · {item.player_white} {item.white_rank || ''}
                        </Typography>
                      </Box>
                      <Typography variant="caption" color="text.secondary" sx={{ textAlign: 'right', whiteSpace: 'normal' }}>
                        {item.date_played || '—'} · {item.move_count} {t('report:moves_unit', '手')}
                      </Typography>
                    </Box>
                  </Button>
                );
              })}
            </Stack>
          )}

          {totalPages > 1 && (
            <Pagination
              count={totalPages}
              page={page}
              disabled={loading || fetching}
              onChange={(_event, nextPage) => setPage(nextPage)}
              renderItem={(item) => <PaginationItem {...item} sx={{ minWidth: 48, minHeight: 48 }} />}
              siblingCount={1}
              boundaryCount={1}
              sx={{ alignSelf: 'center', '& .MuiButtonBase-root': { minWidth: 48, minHeight: 48 } }}
            />
          )}
        </Stack>
      </DialogContent>
      <DialogActions
        data-testid="report-library-import-actions"
        sx={{
          flexShrink: 0,
          overflowX: 'hidden',
          display: 'grid',
          gridTemplateColumns: 'repeat(4, minmax(0, 1fr))',
          gap: 1,
          p: 1.5,
          '& > :not(style) ~ :not(style)': { ml: 0 },
        }}
      >
        <Button disabled={loading} onClick={onClose} sx={actionButtonSx}>{t('common:cancel', '取消')}</Button>
        <Button disabled={loading || fetching || !selectedAlbum} onClick={() => submit()} sx={actionButtonSx}>
          {loading ? t('report:importing', '导入中...') : t('report:import_only', '仅导入')}
        </Button>
        <Button variant="contained" disabled={loading || fetching || !selectedAlbum} onClick={() => submit('normal')} sx={actionButtonSx}>
          {t('report:import_and_normal', '导入并生成普通报告')}
        </Button>
        <Button variant="outlined" disabled={loading || fetching || !selectedAlbum} onClick={() => submit('deep')} sx={actionButtonSx}>
          {t('report:import_and_deep', '导入并生成深度报告')}
        </Button>
      </DialogActions>
    </Dialog>
  );
}
