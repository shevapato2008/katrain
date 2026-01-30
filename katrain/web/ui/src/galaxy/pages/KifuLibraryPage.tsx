import { useState, useEffect, useCallback } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import {
  Box,
  Typography,
  TextField,
  Pagination,
  CircularProgress,
  InputAdornment,
} from '@mui/material';
import SearchIcon from '@mui/icons-material/Search';
import { KifuAPI } from '../api/kifuApi';
import type { KifuAlbumSummary } from '../types/kifu';
import { useTranslation } from '../../hooks/useTranslation';

const PAGE_SIZE = 20;

export default function KifuLibraryPage() {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const [searchParams, setSearchParams] = useSearchParams();

  // Derive page and query from URL (single source of truth — fixes back/forward navigation)
  const page = Number(searchParams.get('page')) || 1;
  const query = searchParams.get('q') || '';

  const [items, setItems] = useState<KifuAlbumSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [searchInput, setSearchInput] = useState(query);

  // Sync input field when URL changes (e.g. browser back button)
  useEffect(() => {
    setSearchInput(query);
  }, [query]);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const data = await KifuAPI.getAlbums({ q: query || undefined, page, page_size: PAGE_SIZE });
      setItems(data.items);
      setTotal(data.total);
    } catch (err) {
      console.error('Failed to fetch kifu albums:', err);
    } finally {
      setLoading(false);
    }
  }, [query, page]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleSearch = () => {
    const params: Record<string, string> = {};
    if (searchInput) params.q = searchInput;
    // Reset to page 1 on new search
    setSearchParams(params, { replace: false });
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') handleSearch();
  };

  const handlePageChange = (_: unknown, newPage: number) => {
    const params: Record<string, string> = {};
    if (query) params.q = query;
    if (newPage > 1) params.page = String(newPage);
    setSearchParams(params, { replace: false });
  };

  const handleClick = (album: KifuAlbumSummary) => {
    navigate(`/galaxy/research?kifu_id=${album.id}`);
  };

  const handleRowKeyDown = (e: React.KeyboardEvent, album: KifuAlbumSummary) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      handleClick(album);
    }
  };

  const totalPages = Math.ceil(total / PAGE_SIZE);

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden' }}>
      {/* Header + Search */}
      <Box sx={{ p: 3, pb: 2 }}>
        <Typography variant="h4" fontWeight="bold" sx={{ mb: 2 }}>
          {t('kifu:library', '棋谱库')}
        </Typography>
        <TextField
          fullWidth
          size="small"
          placeholder={t('kifu:search_placeholder', 'Search by player, event, date...')}
          value={searchInput}
          onChange={(e) => setSearchInput(e.target.value)}
          onKeyDown={handleKeyDown}
          InputProps={{
            startAdornment: (
              <InputAdornment position="start">
                <SearchIcon sx={{ color: 'text.secondary' }} />
              </InputAdornment>
            ),
          }}
          sx={{ maxWidth: 600 }}
        />
        {!loading && (
          <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
            {total} {t('kifu:records', 'records')}{query ? ` · "${query}"` : ''}
          </Typography>
        )}
      </Box>

      {/* List */}
      <Box sx={{ flex: 1, overflow: 'auto', px: 3 }}>
        {loading ? (
          <Box sx={{ display: 'flex', justifyContent: 'center', pt: 8 }}>
            <CircularProgress />
          </Box>
        ) : items.length === 0 ? (
          <Box sx={{ display: 'flex', justifyContent: 'center', pt: 8 }}>
            <Typography color="text.secondary">{t('kifu:no_results', 'No records found')}</Typography>
          </Box>
        ) : (
          items.map((album) => (
            <Box
              key={album.id}
              role="button"
              tabIndex={0}
              onClick={() => handleClick(album)}
              onKeyDown={(e) => handleRowKeyDown(e, album)}
              sx={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                py: 1.5,
                px: 2,
                mb: 1,
                borderRadius: 1,
                cursor: 'pointer',
                bgcolor: 'rgba(255,255,255,0.03)',
                '&:hover, &:focus-visible': { bgcolor: 'rgba(255,255,255,0.08)', outline: 'none' },
                border: '1px solid rgba(255,255,255,0.06)',
              }}
            >
              {/* Left: event + players */}
              <Box sx={{ minWidth: 0, flex: 1 }}>
                {/* Event line */}
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 0.5 }}>
                  {album.event && (
                    <Typography variant="caption" color="text.secondary" noWrap>
                      {album.event}
                    </Typography>
                  )}
                  {album.round_name && (
                    <Typography variant="caption" color="text.secondary" noWrap>
                      · {album.round_name}
                    </Typography>
                  )}
                  <Typography variant="caption" color="text.secondary">
                    · {album.move_count}{t('kifu:moves', '手')}
                  </Typography>
                  {album.board_size !== 19 && (
                    <Typography variant="caption" color="text.secondary">
                      · {album.board_size}×{album.board_size}
                    </Typography>
                  )}
                </Box>
                {/* Players line */}
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                  <Typography variant="body2" fontWeight={600} noWrap>
                    {album.player_black}
                  </Typography>
                  {album.black_rank && (
                    <Typography variant="caption" color="text.secondary">
                      {album.black_rank}
                    </Typography>
                  )}
                  <Typography
                    variant="caption"
                    sx={{
                      px: 0.8,
                      py: 0.1,
                      borderRadius: 0.5,
                      bgcolor: album.result?.startsWith('B') ? 'rgba(0,0,0,0.6)' : album.result?.startsWith('W') ? 'rgba(255,255,255,0.15)' : 'rgba(128,128,128,0.3)',
                      color: album.result?.startsWith('B') ? '#fff' : 'text.primary',
                      fontWeight: 600,
                      border: '1px solid rgba(255,255,255,0.1)',
                    }}
                  >
                    {album.result || '?'}
                  </Typography>
                  <Typography variant="body2" fontWeight={600} noWrap>
                    {album.player_white}
                  </Typography>
                  {album.white_rank && (
                    <Typography variant="caption" color="text.secondary">
                      {album.white_rank}
                    </Typography>
                  )}
                </Box>
              </Box>

              {/* Right: date */}
              <Typography variant="caption" color="text.secondary" sx={{ ml: 2, whiteSpace: 'nowrap' }}>
                {album.date_played || ''}
              </Typography>
            </Box>
          ))
        )}
      </Box>

      {/* Pagination */}
      {totalPages > 1 && (
        <Box sx={{ display: 'flex', justifyContent: 'center', py: 2, borderTop: '1px solid rgba(255,255,255,0.06)' }}>
          <Pagination
            count={totalPages}
            page={page}
            onChange={handlePageChange}
            color="primary"
            shape="rounded"
          />
        </Box>
      )}
    </Box>
  );
}
