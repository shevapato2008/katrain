import { useState, useEffect, useCallback } from 'react';
import {
  Box, Typography, TextField, InputAdornment, Card, CardActionArea, Fade, Button,
  CircularProgress,
} from '@mui/material';
import { Search as SearchIcon, Science as ScienceIcon } from '@mui/icons-material';
import { useNavigate } from 'react-router-dom';
import LiveBoard from '../../components/live/LiveBoard';
import { sgfToMoves } from '../../utils/sgfSerializer';
import KioskResultBadge from '../components/game/KioskResultBadge';
import { KifuAPI } from '../../api/kifuApi';
import type { KifuAlbumSummary } from '../../types/kifu';
import { useTranslation } from '../../hooks/useTranslation';

const ROW_STAGGER = 25;
const DEBOUNCE_MS = 350;

const KifuPage = () => {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [searchInput, setSearchInput] = useState('');
  const [kifuList, setKifuList] = useState<KifuAlbumSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [previewMoves, setPreviewMoves] = useState<string[]>([]);
  const [previewColors, setPreviewColors] = useState<('B' | 'W')[]>([]);
  const [previewCurrentMove, setPreviewCurrentMove] = useState(0);
  const [previewBoardSize, setPreviewBoardSize] = useState(19);

  const fetchAlbums = useCallback((query: string) => {
    setLoading(true);
    setError(null);
    KifuAPI.getAlbums({ q: query || undefined })
      .then((resp) => {
        setKifuList(resp.items);
        setTotal(resp.total);
      })
      .catch((err: Error) => {
        setError(err.message);
      })
      .finally(() => {
        setLoading(false);
      });
  }, []);

  // Initial load
  useEffect(() => {
    fetchAlbums('');
  }, [fetchAlbums]);

  // Debounced search
  useEffect(() => {
    const timer = setTimeout(() => {
      fetchAlbums(searchInput);
    }, DEBOUNCE_MS);
    return () => clearTimeout(timer);
  }, [searchInput, fetchAlbums]);

  // Fetch full kifu detail (SGF) when a game is selected
  useEffect(() => {
    if (selectedId === null) return;
    let cancelled = false;
    setPreviewMoves([]);
    setPreviewColors([]);
    setPreviewCurrentMove(0);

    KifuAPI.getAlbum(selectedId)
      .then((detail) => {
        if (cancelled) return;
        if (detail.sgf_content) {
          const parsed = sgfToMoves(detail.sgf_content);
          setPreviewMoves(parsed.moves);
          setPreviewColors(parsed.stoneColors);
          setPreviewCurrentMove(parsed.moves.length);
          setPreviewBoardSize(detail.board_size || 19);
        }
      })
      .catch((err) => {
        if (!cancelled) console.error('Failed to load kifu detail:', err);
      });

    return () => { cancelled = true; };
  }, [selectedId]);

  const selectedKifu = kifuList.find(k => k.id === selectedId);

  return (
    <Box sx={{ display: 'flex', height: '100%', overflow: 'hidden' }}>
      {/* Left panel: Title + Search + Card list */}
      <Box sx={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        {/* Header */}
        <Box sx={{ px: 3, pt: 3, pb: 1.5 }}>
          <Box sx={{ display: 'flex', alignItems: 'baseline', gap: 1.5, mb: 2 }}>
            <Typography variant="h5" sx={{ fontWeight: 700, letterSpacing: '-0.02em' }}>
              {t('Game Records', '棋谱库')}
            </Typography>
            <Typography variant="body2" sx={{ color: 'text.secondary', fontWeight: 400, opacity: 0.6 }}>
              {total} {t('games', '局')}
            </Typography>
          </Box>

          <TextField
            fullWidth
            size="small"
            placeholder={t('Search players, events...', '搜索棋手、赛事...')}
            value={searchInput}
            onChange={e => setSearchInput(e.target.value)}
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
                '& fieldset': { borderColor: 'rgba(255,255,255,0.05)' },
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
          {loading && kifuList.length === 0 ? (
            <Box sx={{ display: 'flex', justifyContent: 'center', py: 6 }}>
              <CircularProgress size={32} />
            </Box>
          ) : error ? (
            <Box sx={{ display: 'flex', justifyContent: 'center', py: 6 }}>
              <Typography variant="body2" color="error">{error}</Typography>
            </Box>
          ) : (
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
              {kifuList.map((kifu, index) => {
                const result = kifu.result ?? '';
                const blackWins = result.startsWith('B') || result.startsWith('黑');
                const selected = selectedId === kifu.id;

                return (
                  <Fade key={kifu.id} in timeout={200 + index * ROW_STAGGER}>
                    <Box>
                      <Card
                        sx={{
                          bgcolor: selected ? 'rgba(76,175,80,0.12)' : 'rgba(255,255,255,0.05)',
                          border: selected ? 2 : 1,
                          borderColor: selected ? 'primary.main' : 'rgba(255,255,255,0.1)',
                          borderRadius: '8px',
                          '&:hover': {
                            borderColor: selected ? 'primary.main' : 'rgba(255,255,255,0.2)',
                            bgcolor: selected ? 'rgba(76,175,80,0.15)' : 'rgba(255,255,255,0.07)',
                          },
                        }}
                      >
                        <CardActionArea onClick={() => setSelectedId(kifu.id)} sx={{ p: 1.5 }}>
                          {/* Row 1: Event + Date + Moves */}
                          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 0.5 }}>
                            <Typography variant="caption" color="text.secondary" noWrap sx={{ flex: 1 }}>
                              {kifu.event}
                            </Typography>
                            <Typography variant="caption" color="text.secondary" sx={{ flexShrink: 0, fontSize: '0.7rem', opacity: 0.7 }}>
                              {kifu.date_played}
                            </Typography>
                            <Typography variant="caption" color="text.secondary" sx={{ flexShrink: 0 }}>
                              {kifu.move_count} {t('moves', '手')}
                            </Typography>
                          </Box>

                          {/* Row 2: Black player [ResultBadge] White player */}
                          <Box sx={{ display: 'flex', alignItems: 'center' }}>
                            <Box sx={{ display: 'flex', alignItems: 'center', flex: 1, minWidth: 0 }}>
                              <Box sx={{
                                width: 16, height: 16, borderRadius: '50%', flexShrink: 0, mr: 0.7,
                                bgcolor: '#1a1a1a',
                                border: '1px solid rgba(255,255,255,0.18)',
                                boxShadow: 'inset 0 -0.5px 1px rgba(255,255,255,0.1)',
                              }} />
                              <Typography variant="body2" noWrap sx={{ fontWeight: blackWins ? 'bold' : 'normal' }}>
                                {kifu.player_black}
                                <Typography component="span" sx={{ color: 'text.secondary', fontSize: '0.68rem', ml: 0.5 }}>
                                  {kifu.black_rank}
                                </Typography>
                              </Typography>
                            </Box>

                            <Box sx={{ px: 1, flexShrink: 0 }}>
                              <KioskResultBadge result={result} />
                            </Box>

                            <Box sx={{ display: 'flex', alignItems: 'center', flex: 1, minWidth: 0, justifyContent: 'flex-end' }}>
                              <Typography variant="body2" noWrap sx={{ fontWeight: !blackWins ? 'bold' : 'normal' }}>
                                <Typography component="span" sx={{ color: 'text.secondary', fontSize: '0.68rem', mr: 0.5 }}>
                                  {kifu.white_rank}
                                </Typography>
                                {kifu.player_white}
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
                    </Box>
                  </Fade>
                );
              })}
            </Box>
          )}
        </Box>
      </Box>

      {/* Right panel: Board Preview */}
      <Box
        sx={{
          flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center',
          borderLeft: '1px solid rgba(255,255,255,0.06)', bgcolor: '#0f0f0f', overflow: 'hidden',
        }}
      >
        {selectedKifu ? (
          <>
            <Box sx={{ flex: 1, display: 'flex', justifyContent: 'center', alignItems: 'center', width: '100%', minHeight: 0 }}>
              <LiveBoard
                moves={previewMoves}
                stoneColors={previewColors}
                currentMove={previewCurrentMove}
                boardSize={previewBoardSize}
              />
            </Box>

            {/* Bottom bar: Navigation + Open in Research */}
            <Box
              data-testid="kifu-preview-nav"
              sx={{
                px: 3, py: 1.5, bgcolor: '#1a1a1a',
                borderTop: '1px solid rgba(255,255,255,0.05)',
                display: 'flex', alignItems: 'center', width: '100%', flexShrink: 0,
              }}
            >
              <Box sx={{ flex: 1 }} />

              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <Button size="small" sx={{ minWidth: 32, color: 'text.secondary' }}>⏮</Button>
                <Button size="small" sx={{ minWidth: 32, color: 'text.secondary' }}>◀</Button>
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
                  {selectedKifu.move_count} / {selectedKifu.move_count} {t('moves', '手')}
                </Typography>
                <Button size="small" sx={{ minWidth: 32, color: 'text.secondary' }}>▶</Button>
                <Button size="small" sx={{ minWidth: 32, color: 'text.secondary' }}>⏭</Button>
              </Box>

              <Box sx={{ flex: 1, display: 'flex', justifyContent: 'flex-end' }}>
                <Button
                  variant="contained"
                  size="small"
                  startIcon={<ScienceIcon sx={{ fontSize: 16 }} />}
                  onClick={() => navigate('/kiosk/research')}
                  sx={{
                    bgcolor: 'rgba(74,107,92,0.8)',
                    '&:hover': { bgcolor: 'rgba(74,107,92,1)' },
                    borderRadius: '8px',
                    px: 3,
                  }}
                >
                  {t('Open in Research', '在研究中打开')}
                </Button>
              </Box>
            </Box>
          </>
        ) : (
          <Box sx={{ flex: 1, display: 'flex', justifyContent: 'center', alignItems: 'center' }}>
            <Typography variant="body2" color="text.secondary" sx={{ opacity: 0.4 }}>
              {t('Select a game to preview', '选择一局棋谱预览')}
            </Typography>
          </Box>
        )}
      </Box>
    </Box>
  );
};

export default KifuPage;
