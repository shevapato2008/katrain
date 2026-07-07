import { useState, useEffect, useCallback } from 'react';
import {
  Box, Typography, TextField, InputAdornment, Card, CardActionArea, Fade, Button,
  CircularProgress, Pagination, Snackbar, Alert,
} from '@mui/material';
import { Search as SearchIcon, Science as ScienceIcon } from '@mui/icons-material';
import { useNavigate } from 'react-router-dom';
import LiveBoard from '../../components/live/LiveBoard';
import { sgfToMoves } from '../../utils/sgfSerializer';
import KioskResultBadge from '../components/game/KioskResultBadge';
import { KifuAPI } from '../../api/kifuApi';
import { useResearchSession } from '../../hooks/useResearchSession';
import type { KifuAlbumSummary } from '../../types/kifu';
import { useTranslation } from '../../hooks/useTranslation';

const ROW_STAGGER = 25;
const DEBOUNCE_MS = 350;
const PAGE_SIZE = 20;

const KifuPage = () => {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const { createSession } = useResearchSession();
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [searchInput, setSearchInput] = useState('');
  const [query, setQuery] = useState('');
  const [page, setPage] = useState(1);
  const [kifuList, setKifuList] = useState<KifuAlbumSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [previewMoves, setPreviewMoves] = useState<string[]>([]);
  const [previewColors, setPreviewColors] = useState<('B' | 'W')[]>([]);
  const [previewCurrentMove, setPreviewCurrentMove] = useState(0);
  const [previewBoardSize, setPreviewBoardSize] = useState(19);
  const [previewSgf, setPreviewSgf] = useState<string | null>(null);
  const [previewHandicap, setPreviewHandicap] = useState(0);
  const [opening, setOpening] = useState(false);
  const [openError, setOpenError] = useState<string | null>(null);

  // Single source of truth for album fetching (takes explicit args so its identity never
  // changes → no spurious effect re-fires). Replaces the old initial-load + debounced-fetch
  // effects, which together caused a mount double-fetch and a page/search double-fetch.
  const fetchAlbums = useCallback((q: string, p: number) => {
    setLoading(true);
    setError(null);
    KifuAPI.getAlbums({ q: q || undefined, page: p, page_size: PAGE_SIZE })
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

  // Debounce: once typing settles, commit the query AND reset to page 1 together.
  // React 18 batches both setStates inside the timeout → a single re-render → one fetch.
  useEffect(() => {
    const timer = setTimeout(() => {
      setQuery(searchInput);
      setPage(1);
    }, DEBOUNCE_MS);
    return () => clearTimeout(timer);
  }, [searchInput]);

  // Sole fetch effect: fires once on mount (query='' page=1) and once per query/page change.
  useEffect(() => {
    fetchAlbums(query, page);
  }, [query, page, fetchAlbums]);

  // Fetch full kifu detail (SGF) when a game is selected
  useEffect(() => {
    if (selectedId === null) return;
    let cancelled = false;
    setPreviewMoves([]);
    setPreviewColors([]);
    setPreviewCurrentMove(0);
    setPreviewSgf(null);
    setPreviewHandicap(0);

    KifuAPI.getAlbum(selectedId)
      .then((detail) => {
        if (cancelled) return;
        if (detail.sgf_content) {
          const parsed = sgfToMoves(detail.sgf_content);
          setPreviewMoves(parsed.moves);
          setPreviewColors(parsed.stoneColors);
          setPreviewCurrentMove(parsed.moves.length);
          // Trust the SGF's own SZ[] first (metadata-first, aligns kiosk to Galaxy);
          // fixes a latent grid/coord mismatch when DB board_size disagrees with SGF.
          setPreviewBoardSize(parsed.metadata.boardSize || detail.board_size || 19);
          setPreviewSgf(detail.sgf_content);
          setPreviewHandicap(parsed.metadata.handicap ?? detail.handicap ?? 0);
        }
      })
      .catch((err) => {
        if (!cancelled) console.error('Failed to load kifu detail:', err);
      });

    return () => { cancelled = true; };
  }, [selectedId]);

  const handleOpenInResearch = async () => {
    if (!previewSgf || opening) return;
    setOpening(true);
    setOpenError(null);
    try {
      // previewMoves includes handicap setup stones (AB[]), but the backend redo() only
      // walks move-nodes; subtract handicap to land on the right node. At the terminal
      // (default) this equals the real move count → exact terminal; mid-scrub & handicap
      // are also correct; non-handicap (handicap=0) is unchanged.
      const initialMove = Math.max(0, previewCurrentMove - previewHandicap);
      const sessionId = await createSession(previewSgf, { initialMove, skipAnalysis: true });
      if (sessionId) {
        navigate(`/kiosk/research/session/${sessionId}`);
      } else {
        setOpenError(t('Failed to open in research', '打开研究失败，请重试'));
      }
    } catch {
      // Defensive: createSession swallows errors and returns null, so this is rarely hit.
      setOpenError(t('Failed to open in research', '打开研究失败，请重试'));
    } finally {
      setOpening(false);
    }
  };

  const selectedKifu = kifuList.find(k => k.id === selectedId);
  const totalPages = Math.ceil(total / PAGE_SIZE);

  return (
    <Box sx={{ display: 'flex', flexDirection: 'row', height: '100%', overflow: 'hidden' }}>
      {/* List panel: Title + Search + Card list + Pagination */}
      <Box sx={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        {/* Header */}
        <Box sx={{ px: 3, pt: 3, pb: 1.5 }}>
          <Box sx={{ display: 'flex', alignItems: 'baseline', gap: 1.5, mb: 2 }}>
            <Typography variant="h4" sx={{ fontFamily: "'Newsreader','Noto Serif SC',serif", fontWeight: 500, letterSpacing: 0 }}>
              {t('Game Records', '棋谱库')}
            </Typography>
            <Typography variant="body2" sx={{ color: 'text.secondary', fontWeight: 400, opacity: 0.6 }}>
              {total.toLocaleString()} {t('games', '局')}
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
                bgcolor: 'var(--raise2)',
                borderRadius: '10px',
                fontSize: '0.88rem',
                transition: 'all 200ms ease',
                '& fieldset': { borderColor: 'divider' },
                '&:hover': {
                  '& fieldset': { borderColor: '#3a4d45' },
                },
                '&.Mui-focused': {
                  '& fieldset': { borderColor: 'primary.main' },
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
                          bgcolor: selected ? 'linear-gradient(135deg,#1f3a30,#18211f)' : 'background.paper',
                          border: 1,
                          borderColor: selected ? 'primary.main' : 'divider',
                          borderRadius: '13px',
                          '&:hover': {
                            borderColor: selected ? 'primary.main' : '#3a4d45',
                          },
                        }}
                      >
                        <CardActionArea onClick={() => setSelectedId(kifu.id)} sx={{ p: 1.5 }}>
                          {/* Row 1: Event + Round + Date + Moves */}
                          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 0.5 }}>
                            <Typography variant="caption" color="text.secondary" noWrap sx={{ flex: 1 }}>
                              {kifu.event}
                              {kifu.round_name && (
                                <Typography component="span" sx={{ opacity: 0.6, fontSize: '0.7rem', ml: 0.5 }}>
                                  {kifu.round_name}
                                </Typography>
                              )}
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
                              <KioskResultBadge result={result} rules={kifu.rules} />
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

        {/* Pagination (bottom of list panel) */}
        {totalPages > 1 && (
          <Box sx={{ display: 'flex', justifyContent: 'center', py: 1, borderTop: '1px solid', borderColor: 'divider', flexShrink: 0 }}>
            <Pagination
              count={totalPages}
              page={page}
              onChange={(_, p) => setPage(p)}
              color="primary"
              shape="rounded"
              size="small"
            />
          </Box>
        )}
      </Box>

      {/* Preview panel: Board Preview */}
      <Box
        sx={{
          flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center',
          bgcolor: 'background.default', overflow: 'hidden',
          borderLeft: '1px solid rgba(255,255,255,0.06)',
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
                showCoordinates={true}
              />
            </Box>

            {/*
              Bottom bar: move navigation (center) + Open in Research (right).
              flexWrap + button-as-direct-child guarantees no clipping: on panels too
              narrow for one row, the button drops to its own row instead of clipping/
              vertically wrapping. On wide panels it stays a single row (D4).
            */}
            <Box
              data-testid="kifu-preview-nav"
              sx={{
                px: 3, py: 1.5, bgcolor: '#1a1a1a',
                borderTop: '1px solid rgba(255,255,255,0.05)',
                display: 'flex', flexWrap: 'wrap', alignItems: 'center', justifyContent: 'center',
                columnGap: 1, rowGap: 1, width: '100%', flexShrink: 0,
              }}
            >
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, flexGrow: 1, flexShrink: 0, justifyContent: 'center' }}>
                <Button size="small" aria-label="first" disabled={previewCurrentMove === 0}
                  onClick={() => setPreviewCurrentMove(0)} sx={{ minWidth: 32, color: 'text.secondary' }}>⏮</Button>
                <Button size="small" aria-label="prev" disabled={previewCurrentMove === 0}
                  onClick={() => setPreviewCurrentMove(m => Math.max(0, m - 1))} sx={{ minWidth: 32, color: 'text.secondary' }}>◀</Button>
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
                  {previewCurrentMove} / {previewMoves.length} {t('moves', '手')}
                </Typography>
                <Button size="small" aria-label="next" disabled={previewCurrentMove >= previewMoves.length}
                  onClick={() => setPreviewCurrentMove(m => Math.min(previewMoves.length, m + 1))} sx={{ minWidth: 32, color: 'text.secondary' }}>▶</Button>
                <Button size="small" aria-label="last" disabled={previewCurrentMove >= previewMoves.length}
                  onClick={() => setPreviewCurrentMove(previewMoves.length)} sx={{ minWidth: 32, color: 'text.secondary' }}>⏭</Button>
              </Box>

              <Button
                variant="contained"
                size="small"
                startIcon={opening ? <CircularProgress size={16} color="inherit" /> : <ScienceIcon sx={{ fontSize: 16 }} />}
                onClick={handleOpenInResearch}
                disabled={!previewSgf || opening}
                sx={{
                  whiteSpace: 'nowrap',
                  flexShrink: 0,
                  textTransform: 'none',
                  minWidth: 150,
                  minHeight: 40,
                  bgcolor: 'rgba(74,107,92,0.8)',
                  '&:hover': { bgcolor: 'rgba(74,107,92,1)' },
                  borderRadius: '8px',
                  px: 3,
                }}
              >
                {t('Open in Research', '在研究中打开')}
              </Button>
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

      {/* Failure feedback for "Open in Research" */}
      <Snackbar
        open={!!openError}
        autoHideDuration={4000}
        onClose={() => setOpenError(null)}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
      >
        <Alert severity="error" onClose={() => setOpenError(null)}>{openError}</Alert>
      </Snackbar>
    </Box>
  );
};

export default KifuPage;
