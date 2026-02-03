import { useState, useEffect, useCallback } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import {
  Box,
  Typography,
  TextField,
  Pagination,
  InputAdornment,
  Skeleton,
  Fade,
  Card,
  CardActionArea,
  Button,
} from '@mui/material';
import SearchIcon from '@mui/icons-material/Search';
import ScienceIcon from '@mui/icons-material/Science';
import { KifuAPI } from '../api/kifuApi';
import type { KifuAlbumSummary, KifuAlbumDetail } from '../types/kifu';
import { useTranslation } from '../../hooks/useTranslation';
import { translateResult } from '../utils/resultTranslation';
import { sgfToMoves } from '../utils/sgfSerializer';
import LiveBoard from '../components/live/LiveBoard';

const PAGE_SIZE = 20;
const ROW_STAGGER = 25;

/* ── Result badge (inline) ── */
function ResultBadge({ result, rules, t }: { result: string | null; rules?: string | null; t: (key: string, fallback?: string) => string }) {
  const raw = result || '?';
  const isBlack = raw.startsWith('B') || raw.startsWith('黑');
  const label = translateResult(result, t, rules);

  return (
    <Typography
      component="span"
      sx={{
        display: 'inline-block',
        fontSize: '0.65rem',
        fontWeight: 700,
        lineHeight: 1,
        px: 0.7,
        py: 0.3,
        borderRadius: '4px',
        fontFamily: "'IBM Plex Mono', monospace",
        bgcolor: isBlack ? 'rgba(10,10,10,0.9)' : 'rgba(255,255,255,0.1)',
        color: isBlack ? '#ccc' : '#f5f3f0',
        border: '1px solid',
        borderColor: isBlack ? 'rgba(255,255,255,0.1)' : 'rgba(255,255,255,0.12)',
        whiteSpace: 'nowrap',
      }}
    >
      {label}
    </Typography>
  );
}

/* ── Skeleton placeholder cards ── */
function SkeletonCards({ count }: { count: number }) {
  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
      {Array.from({ length: count }).map((_, i) => (
        <Box
          key={i}
          sx={{
            p: 1.5,
            borderRadius: '8px',
            bgcolor: 'rgba(255,255,255,0.03)',
            border: '1px solid rgba(255,255,255,0.06)',
          }}
        >
          <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5 }}>
            <Skeleton variant="text" width={200} sx={{ bgcolor: 'rgba(255,255,255,0.04)', fontSize: '0.75rem' }} />
            <Skeleton variant="text" width={60} sx={{ bgcolor: 'rgba(255,255,255,0.04)', fontSize: '0.75rem' }} />
          </Box>
          <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
            <Skeleton variant="text" width={100} sx={{ bgcolor: 'rgba(255,255,255,0.05)', fontSize: '0.9rem' }} />
            <Skeleton variant="text" width={100} sx={{ bgcolor: 'rgba(255,255,255,0.05)', fontSize: '0.9rem' }} />
          </Box>
        </Box>
      ))}
    </Box>
  );
}

/* ── Single game record card (matches live MatchCard compact style) ── */
function GameRecordCard({
  album,
  onClick,
  tMovesUnit,
  t,
  selected,
}: {
  album: KifuAlbumSummary;
  onClick: () => void;
  tMovesUnit: string;
  t: (key: string, fallback?: string) => string;
  selected?: boolean;
}) {
  const r = album.result || '';
  const blackWins = r.startsWith('B') || r.startsWith('黑');

  return (
    <Card
      sx={{
        bgcolor: selected ? 'rgba(76, 175, 80, 0.12)' : 'rgba(255,255,255,0.05)',
        border: selected ? 2 : 1,
        borderColor: selected ? 'primary.main' : 'rgba(255,255,255,0.1)',
        borderRadius: '8px',
        '&:hover': {
          borderColor: selected ? 'primary.main' : 'rgba(255,255,255,0.2)',
          bgcolor: selected ? 'rgba(76, 175, 80, 0.15)' : 'rgba(255,255,255,0.07)',
        },
      }}
    >
      <CardActionArea onClick={onClick} sx={{ p: 1.5 }}>
        {/* Row 1: Event + Date + Moves */}
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 0.5 }}>
          <Typography variant="caption" color="text.secondary" noWrap sx={{ flex: 1 }}>
            {album.event || ''}
            {album.round_name && (
              <Typography component="span" sx={{ opacity: 0.6, fontSize: '0.7rem', ml: 0.5 }}>
                {album.round_name}
              </Typography>
            )}
          </Typography>
          {album.date_played && (
            <Typography variant="caption" color="text.secondary" sx={{ flexShrink: 0, fontSize: '0.7rem', opacity: 0.7 }}>
              {album.date_played}
            </Typography>
          )}
          <Typography variant="caption" color="text.secondary" sx={{ flexShrink: 0 }}>
            {album.move_count} {tMovesUnit}
          </Typography>
        </Box>

        {/* Row 2: Black player  [result]  vs  White player */}
        <Box sx={{ display: 'flex', alignItems: 'center' }}>
          <Box sx={{ display: 'flex', alignItems: 'center', flex: 1, minWidth: 0 }}>
            <Box sx={{
              width: 16, height: 16, borderRadius: '50%', flexShrink: 0, mr: 0.7,
              bgcolor: '#1a1a1a',
              border: '1px solid rgba(255,255,255,0.18)',
              boxShadow: 'inset 0 -0.5px 1px rgba(255,255,255,0.1)',
            }} />
            <Typography
              variant="body2"
              noWrap
              sx={{ fontWeight: blackWins ? 'bold' : 'normal' }}
            >
              {album.player_black}
              {album.black_rank && (
                <Typography component="span" sx={{ color: 'text.secondary', fontSize: '0.68rem', ml: 0.5 }}>
                  {album.black_rank}
                </Typography>
              )}
            </Typography>
          </Box>

          <Box sx={{ px: 1, flexShrink: 0 }}>
            <ResultBadge result={album.result} rules={album.rules} t={t} />
          </Box>

          <Box sx={{ display: 'flex', alignItems: 'center', flex: 1, minWidth: 0, justifyContent: 'flex-end' }}>
            <Typography
              variant="body2"
              noWrap
              sx={{ fontWeight: !blackWins ? 'bold' : 'normal' }}
            >
              {album.white_rank && (
                <Typography component="span" sx={{ color: 'text.secondary', fontSize: '0.68rem', mr: 0.5 }}>
                  {album.white_rank}
                </Typography>
              )}
              {album.player_white}
            </Typography>
            <Box sx={{
              width: 16, height: 16, borderRadius: '50%', flexShrink: 0, ml: 0.7,
              bgcolor: '#e8e4df',
              border: '1px solid rgba(0,0,0,0.25)',
              boxShadow: 'inset 0 0.5px 1px rgba(0,0,0,0.06)',
            }} />
          </Box>
        </Box>
      </CardActionArea>
    </Card>
  );
}

/* ── Main page ── */
export default function KifuLibraryPage() {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const [searchParams, setSearchParams] = useSearchParams();

  const page = Number(searchParams.get('page')) || 1;
  const query = searchParams.get('q') || '';

  const [items, setItems] = useState<KifuAlbumSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [searchInput, setSearchInput] = useState(query);

  // Board preview state
  const [selectedAlbum, setSelectedAlbum] = useState<KifuAlbumSummary | null>(null);
  const [previewMoves, setPreviewMoves] = useState<string[]>([]);
  const [previewColors, setPreviewColors] = useState<('B' | 'W')[]>([]);
  const [previewCurrentMove, setPreviewCurrentMove] = useState(0);
  const [previewBoardSize, setPreviewBoardSize] = useState(19);
  const [previewLoading, setPreviewLoading] = useState(false);

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

  // Load SGF for board preview when a card is clicked
  const handleCardClick = useCallback(async (album: KifuAlbumSummary) => {
    setSelectedAlbum(album);
    setPreviewLoading(true);
    try {
      const detail: KifuAlbumDetail = await KifuAPI.getAlbum(album.id);
      if (detail.sgf_content) {
        const parsed = sgfToMoves(detail.sgf_content);
        setPreviewMoves(parsed.moves);
        setPreviewColors(parsed.stoneColors);
        setPreviewCurrentMove(parsed.moves.length); // Show final position
        setPreviewBoardSize(parsed.metadata.boardSize || album.board_size || 19);
      }
    } catch (err) {
      console.error('Failed to load kifu preview:', err);
    } finally {
      setPreviewLoading(false);
    }
  }, []);

  const handleOpenInResearch = useCallback(() => {
    if (selectedAlbum) {
      navigate(`/galaxy/research?kifu_id=${selectedAlbum.id}`);
    }
  }, [selectedAlbum, navigate]);

  const totalPages = Math.ceil(total / PAGE_SIZE);
  const movesUnit = t('kifu:moves_unit', '手');

  return (
    <Box sx={{ display: 'flex', height: '100%', overflow: 'hidden' }}>
      {/* ── Left Panel: Header + Search + Card List + Pagination ── */}
      <Box sx={{ width: 520, flexShrink: 0, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        {/* Header */}
        <Box sx={{ px: 3, pt: 3, pb: 1.5 }}>
          <Box sx={{ display: 'flex', alignItems: 'baseline', gap: 1.5, mb: 2 }}>
            <Typography variant="h4" sx={{ fontWeight: 700, letterSpacing: '-0.02em' }}>
              {t('kifu:library', '棋谱库')}
            </Typography>
            {!loading && (
              <Typography
                variant="body2"
                sx={{ color: 'text.secondary', fontWeight: 400, opacity: 0.6 }}
              >
                {total.toLocaleString()} {t('kifu:records', 'records')}
                {query ? ` · "${query}"` : ''}
              </Typography>
            )}
          </Box>

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
                  <SearchIcon sx={{ color: 'text.secondary', fontSize: 20, opacity: 0.6 }} />
                </InputAdornment>
              ),
            }}
            sx={{
              '& .MuiOutlinedInput-root': {
                bgcolor: 'rgba(255,255,255,0.025)',
                borderRadius: '10px',
                fontSize: '0.88rem',
                transition: 'all 200ms ease',
                '& fieldset': {
                  borderColor: 'rgba(255,255,255,0.05)',
                },
                '&:hover': {
                  bgcolor: 'rgba(255,255,255,0.04)',
                  '& fieldset': { borderColor: 'rgba(255,255,255,0.08)' },
                },
                '&.Mui-focused': {
                  bgcolor: 'rgba(255,255,255,0.045)',
                  '& fieldset': { borderColor: 'rgba(74,107,92,0.4)' },
                },
              },
            }}
          />
        </Box>

        {/* Scrollable card list */}
        <Box sx={{ flex: 1, overflow: 'auto', px: 2, py: 1, minHeight: 0 }}>
          {loading ? (
            <SkeletonCards count={14} />
          ) : items.length === 0 ? (
            <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', pt: 12, gap: 1 }}>
              <Typography variant="h6" sx={{ color: 'text.secondary', fontWeight: 500 }}>
                {t('kifu:no_results', 'No records found')}
              </Typography>
              {query && (
                <Typography variant="body2" sx={{ color: 'text.secondary', opacity: 0.5 }}>
                  "{query}"
                </Typography>
              )}
            </Box>
          ) : (
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
              {items.map((album, index) => (
                <Fade key={album.id} in timeout={200 + index * ROW_STAGGER}>
                  <Box>
                    <GameRecordCard
                      album={album}
                      onClick={() => handleCardClick(album)}
                      tMovesUnit={movesUnit}
                      t={t}
                      selected={selectedAlbum?.id === album.id}
                    />
                  </Box>
                </Fade>
              ))}
            </Box>
          )}
        </Box>

        {/* Pagination (below card list, bottom of left panel) */}
        {totalPages > 1 && (
          <Box
            sx={{
              display: 'flex',
              justifyContent: 'center',
              py: 1,
              borderTop: '1px solid rgba(255,255,255,0.04)',
              flexShrink: 0,
            }}
          >
            <Pagination
              count={totalPages}
              page={page}
              onChange={handlePageChange}
              color="primary"
              shape="rounded"
              size="small"
            />
          </Box>
        )}
      </Box>

      {/* ── Right Panel: Board Preview ── */}
      <Box
        sx={{
          flex: 1,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          borderLeft: '1px solid rgba(255,255,255,0.06)',
          bgcolor: '#0f0f0f',
          overflow: 'hidden',
        }}
      >
        {selectedAlbum && !previewLoading ? (
          <>
            {/* Board — aligned to top of panel */}
            <Box sx={{ flex: 1, display: 'flex', justifyContent: 'center', alignItems: 'center', width: '100%', minHeight: 0 }}>
              <LiveBoard
                moves={previewMoves}
                stoneColors={previewColors}
                currentMove={previewCurrentMove}
                boardSize={previewBoardSize}
                showCoordinates={true}
              />
            </Box>

            {/* Bottom bar: Navigation (center) + Open in Research (right) */}
            <Box sx={{
              px: 3,
              py: 1.5,
              bgcolor: '#1a1a1a',
              borderTop: '1px solid rgba(255,255,255,0.05)',
              display: 'flex',
              alignItems: 'center',
              width: '100%',
              flexShrink: 0,
            }}>
              {/* Spacer to balance the right-side button */}
              <Box sx={{ flex: 1 }} />

              {/* Move navigation controls (centered) */}
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <Button
                  size="small"
                  disabled={previewCurrentMove === 0}
                  onClick={() => setPreviewCurrentMove(0)}
                  sx={{ minWidth: 32, color: 'text.secondary' }}
                >
                  ⏮
                </Button>
                <Button
                  size="small"
                  disabled={previewCurrentMove === 0}
                  onClick={() => setPreviewCurrentMove(m => Math.max(0, m - 1))}
                  sx={{ minWidth: 32, color: 'text.secondary' }}
                >
                  ◀
                </Button>
                <Typography
                  variant="body2"
                  sx={{
                    mx: 2,
                    fontFamily: '"IBM Plex Mono", monospace',
                    color: 'text.secondary',
                    minWidth: 80,
                    textAlign: 'center',
                  }}
                >
                  {previewCurrentMove} / {previewMoves.length} {movesUnit}
                </Typography>
                <Button
                  size="small"
                  disabled={previewCurrentMove >= previewMoves.length}
                  onClick={() => setPreviewCurrentMove(m => Math.min(previewMoves.length, m + 1))}
                  sx={{ minWidth: 32, color: 'text.secondary' }}
                >
                  ▶
                </Button>
                <Button
                  size="small"
                  disabled={previewCurrentMove >= previewMoves.length}
                  onClick={() => setPreviewCurrentMove(previewMoves.length)}
                  sx={{ minWidth: 32, color: 'text.secondary' }}
                >
                  ⏭
                </Button>
              </Box>

              {/* Open in Research button (right-aligned) */}
              <Box sx={{ flex: 1, display: 'flex', justifyContent: 'flex-end' }}>
                <Button
                  variant="contained"
                  size="small"
                  startIcon={<ScienceIcon sx={{ fontSize: 16 }} />}
                  onClick={handleOpenInResearch}
                  sx={{
                    textTransform: 'none',
                    bgcolor: 'rgba(74,107,92,0.8)',
                    '&:hover': { bgcolor: 'rgba(74,107,92,1)' },
                    borderRadius: '8px',
                    px: 3,
                  }}
                >
                  {t('kifu:open_in_research', '在研究中打开')}
                </Button>
              </Box>
            </Box>
          </>
        ) : previewLoading ? (
          <Box sx={{ flex: 1, display: 'flex', flexDirection: 'column', justifyContent: 'center', alignItems: 'center' }}>
            <Skeleton variant="rectangular" width={360} height={360} sx={{ bgcolor: 'rgba(255,255,255,0.04)', borderRadius: '8px' }} />
            <Typography variant="body2" color="text.secondary" sx={{ mt: 2 }}>
              {t('kifu:loading', '加载中...')}
            </Typography>
          </Box>
        ) : (
          <Box sx={{ flex: 1, display: 'flex', justifyContent: 'center', alignItems: 'center' }}>
            <Typography variant="body2" color="text.secondary" sx={{ opacity: 0.4 }}>
              {t('kifu:select_to_preview', '选择一局棋谱预览')}
            </Typography>
          </Box>
        )}
      </Box>
    </Box>
  );
}
