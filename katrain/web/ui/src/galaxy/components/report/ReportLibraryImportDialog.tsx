import { useCallback, useEffect, useState } from 'react';
import {
  Box,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Pagination,
  Stack,
  TextField,
  Typography,
} from '@mui/material';

import { KifuAPI } from '../../../api/kifuApi';
import { translateResult } from '../../../utils/resultTranslation';
import type { KifuAlbumSummary } from '../../../types/kifu';
import { useTranslation } from '../../../hooks/useTranslation';

interface ReportLibraryImportDialogProps {
  open: boolean;
  loading?: boolean;
  onClose: () => void;
  onImport: (album: KifuAlbumSummary, reportType?: 'normal' | 'deep') => void;
}

const PAGE_SIZE = 20;

export default function ReportLibraryImportDialog({
  open,
  loading = false,
  onClose,
  onImport,
}: ReportLibraryImportDialogProps) {
  const { t } = useTranslation();
  const [query, setQuery] = useState('');
  const [page, setPage] = useState(1);
  const [items, setItems] = useState<KifuAlbumSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [selectedAlbum, setSelectedAlbum] = useState<KifuAlbumSummary | null>(null);
  const [fetching, setFetching] = useState(false);

  const fetchData = useCallback(async () => {
    if (!open) return;
    setFetching(true);
    try {
      const response = await KifuAPI.getAlbums({
        q: query || undefined,
        page,
        page_size: PAGE_SIZE,
      });
      setItems(response.items);
      setTotal(response.total);
      if (response.items.length > 0 && !selectedAlbum) {
        setSelectedAlbum(response.items[0]);
      }
    } finally {
      setFetching(false);
    }
  }, [open, page, query, selectedAlbum]);

  useEffect(() => {
    fetchData().catch(() => {});
  }, [fetchData]);

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <Dialog open={open} onClose={() => !loading && onClose()} maxWidth="md" fullWidth>
      <DialogTitle>{t('report:import_library', 'Import from library')}</DialogTitle>
      <DialogContent>
        <Stack spacing={2} sx={{ pt: 1 }}>
          <TextField
            label={t('report:search', 'Search')}
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === 'Enter') {
                setPage(1);
                fetchData().catch(() => {});
              }
            }}
            placeholder={t('report:search_placeholder_lib', 'Search by player, event, date')}
            fullWidth
          />
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1, maxHeight: 420, overflow: 'auto' }}>
            {fetching ? (
              <Typography color="text.secondary">{t('report:loading', 'Loading...')}</Typography>
            ) : items.length === 0 ? (
              <Typography color="text.secondary">{t('report:no_results', 'No games found.')}</Typography>
            ) : (
              items.map((album) => (
                <Box
                  key={album.id}
                  onClick={() => setSelectedAlbum(album)}
                  sx={{
                    p: 1.5,
                    borderRadius: 1,
                    cursor: 'pointer',
                    border: '1px solid',
                    borderColor: selectedAlbum?.id === album.id ? 'primary.main' : 'rgba(255,255,255,0.08)',
                    bgcolor: selectedAlbum?.id === album.id ? 'rgba(76, 175, 80, 0.12)' : 'rgba(255,255,255,0.03)',
                  }}
                >
                  <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 0.5 }}>
                    <Typography variant="body2" noWrap sx={{ flex: 1 }}>
                      {album.event || `${album.player_black} vs ${album.player_white}`}
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      {album.date_played || '-'} · {album.move_count} {t('report:moves_unit', 'moves')}
                    </Typography>
                  </Stack>
                  <Stack direction="row" justifyContent="space-between" alignItems="center">
                    <Typography variant="subtitle2">{album.player_black}</Typography>
                    <Typography variant="caption" color="text.secondary">{album.result ? translateResult(album.result, t, album.rules) : t('report:no_result', 'No result')}</Typography>
                    <Typography variant="subtitle2">{album.player_white}</Typography>
                  </Stack>
                </Box>
              ))
            )}
          </Box>
          {totalPages > 1 && (
            <Pagination
              count={totalPages}
              page={page}
              onChange={(_, newPage) => setPage(newPage)}
            />
          )}
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose} disabled={loading}>{t('report:cancel', 'Cancel')}</Button>
        <Button disabled={loading || !selectedAlbum} onClick={() => selectedAlbum && onImport(selectedAlbum)}>
          {loading ? t('report:importing', 'Importing...') : t('report:import_only', 'Import only')}
        </Button>
        <Button
          variant="contained"
          disabled={loading || !selectedAlbum}
          onClick={() => selectedAlbum && onImport(selectedAlbum, 'normal')}
        >
          {t('report:import_and_normal', 'Import & generate normal report')}
        </Button>
        <Button
          variant="outlined"
          disabled={loading || !selectedAlbum}
          onClick={() => selectedAlbum && onImport(selectedAlbum, 'deep')}
        >
          {t('report:import_and_deep', 'Import & generate deep report')}
        </Button>
      </DialogActions>
    </Dialog>
  );
}
