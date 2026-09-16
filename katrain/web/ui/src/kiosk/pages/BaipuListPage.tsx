import { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import {
  Box, Typography, TextField, InputAdornment, Card, CardActionArea, Fade, Button,
  CircularProgress, Pagination, Snackbar, Alert, Chip, Divider,
} from '@mui/material';
import {
  Search as SearchIcon, GridOn as GridOnIcon, UploadFile as UploadIcon, History as HistoryIcon,
} from '@mui/icons-material';
import { useNavigate } from 'react-router-dom';
import LiveBoard from '../../components/live/LiveBoard';
import { sgfToMoves } from '../../utils/sgfSerializer';
import { KifuAPI } from '../../api/kifuApi';
import { cacheSgf, listRecent, getCachedSgf, type BaipuRecentEntry } from '../../api/baipuApi';
import type { KifuAlbumSummary } from '../../types/kifu';
import { useTranslation } from '../../hooks/useTranslation';
import { useAuth } from '../../context/AuthContext';
import { kioskActivityStorage } from '../storage/kioskActivityStorage';

const ROW_STAGGER = 25;
const DEBOUNCE_MS = 350;
const PAGE_SIZE = 20;

/**
 * 摆谱 list page: pick a 19×19 SGF to guide-place on the physical board.
 * Sources: (b primary) browse the kifu library and cache the chosen SGF locally;
 * (a fallback) import a local .sgf file. Either way the SGF is cached in
 * localStorage so the session page is offline-safe (decision Codex#9 / (b)).
 */
const BaipuListPage = () => {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Box-SSO guest mode (client-side zero-persistence, 4th layer): `recent` is read
  // SYNCHRONOUSLY at first paint, before AuthContext's async /me probe may have resolved —
  // so the store used by the lazy useState initializer below MUST be empty
  // (identityKey=null) while isLoading, exactly like TsumegoProgressContext. `store` is
  // memoized on the resolved identity signature so every read/write in this component (not
  // just the first-paint one) stays consistently scoped to the SAME store.
  const { user, isGuest, isLoading } = useAuth();
  const identityKey = user?.uuid ?? null;
  const store = useMemo(
    () => kioskActivityStorage(isLoading || isGuest ? null : identityKey, isGuest),
    [isLoading, isGuest, identityKey],
  );

  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [searchInput, setSearchInput] = useState('');
  const [query, setQuery] = useState('');
  const [page, setPage] = useState(1);
  const [kifuList, setKifuList] = useState<KifuAlbumSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [recent, setRecent] = useState<BaipuRecentEntry[]>(() =>
    isLoading ? [] : listRecent(kioskActivityStorage(isGuest ? null : identityKey, isGuest)),
  );

  // Re-hydrate `recent` once identity resolves (or changes) — the useState initializer above
  // only runs once, at mount, so a later resolution/transition needs an explicit refresh.
  // Synchronizing with the external identity-scoped store here is exactly what this effect is
  // for; there is no render-time equivalent since `store` itself is only known once resolved.
  useEffect(() => {
    if (isLoading) return;
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setRecent(listRecent(store));
  }, [isLoading, store]);

  const [previewMoves, setPreviewMoves] = useState<string[]>([]);
  const [previewColors, setPreviewColors] = useState<('B' | 'W')[]>([]);
  const [previewBoardSize, setPreviewBoardSize] = useState(19);
  const [previewSgf, setPreviewSgf] = useState<string | null>(null);
  const [previewName, setPreviewName] = useState('');
  const [actionError, setActionError] = useState<string | null>(null);

  // All setState happens inside the async callbacks (never synchronously in the
  // effect body) to satisfy react-hooks/set-state-in-effect. The initial
  // useState(true) covers the first load; refetches swap data in without a flash.
  const fetchAlbums = useCallback((q: string, p: number) => {
    KifuAPI.getAlbums({ q: q || undefined, page: p, page_size: PAGE_SIZE })
      .then((resp) => {
        setKifuList(resp.items);
        setTotal(resp.total);
        setError(null);
      })
      .catch((err: Error) => {
        setError(err.message);
      })
      .finally(() => {
        setLoading(false);
      });
  }, []);

  useEffect(() => {
    const timer = setTimeout(() => {
      setQuery(searchInput);
      setPage(1);
    }, DEBOUNCE_MS);
    return () => clearTimeout(timer);
  }, [searchInput]);

  useEffect(() => {
    fetchAlbums(query, page);
  }, [query, page, fetchAlbums]);

  // Only 19×19 records can be guide-placed (the LED board is physically 19×19).
  // NOTE: this filters the CURRENT page client-side; `total`/pagination still
  // reflects all board sizes (the board-mode kifu dispatcher has no board_size
  // filter). For pro libraries (≈all 19×19) the difference is negligible; a fully
  // filtered-out page shows the empty state below. A precise fix needs a
  // board_size query param threaded through the kifu repository/dispatcher.
  const visibleKifu = kifuList.filter((k) => k.board_size === 19);

  // Select a library game: clear stale preview (event handler — allowed) and trigger fetch.
  const handleSelect = (id: number) => {
    setSelectedId(id);
    setPreviewMoves([]);
    setPreviewColors([]);
    setPreviewSgf(null);
  };

  // Fetch detail SGF for preview when a library game is selected. The effect only
  // performs async work; state is set inside the .then callback (not synchronously).
  useEffect(() => {
    if (selectedId === null) return;
    let cancelled = false;
    KifuAPI.getAlbum(selectedId)
      .then((detail) => {
        if (cancelled || !detail.sgf_content) return;
        const parsed = sgfToMoves(detail.sgf_content);
        setPreviewMoves(parsed.moves);
        setPreviewColors(parsed.stoneColors);
        setPreviewBoardSize(parsed.metadata.boardSize || detail.board_size || 19);
        setPreviewSgf(detail.sgf_content);
        setPreviewName(`${detail.player_black} vs ${detail.player_white}`.trim());
      })
      .catch((err) => { if (!cancelled) console.error('Failed to load kifu detail:', err); });
    return () => { cancelled = true; };
  }, [selectedId]);

  const startSession = (id: string, name: string, sgf: string) => {
    cacheSgf(id, name, sgf, store);
    navigate(`/kiosk/baipu/session/${encodeURIComponent(id)}`, { state: { sgf, name } });
  };

  const handleStartSelected = () => {
    if (!previewSgf || selectedId === null) return;
    startSession(`kifu_${selectedId}`, previewName || `kifu ${selectedId}`, previewSgf);
  };

  const handleImportFile = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      const text = String(reader.result || '');
      if (!text.includes('(;')) {
        setActionError(t('Not a valid SGF file', '不是有效的 SGF 文件'));
        return;
      }
      const id = `local_${Date.now()}`;
      startSession(id, file.name.replace(/\.sgf$/i, ''), text);
    };
    reader.onerror = () => setActionError(t('Failed to read file', '读取文件失败'));
    reader.readAsText(file);
    e.target.value = ''; // allow re-importing the same file
  };

  const handleResume = (entry: BaipuRecentEntry) => {
    const cached = getCachedSgf(entry.id, store);
    if (!cached) {
      setActionError(t('Cached SGF no longer available', '缓存棋谱已失效'));
      setRecent(listRecent(store));
      return;
    }
    startSession(cached.id, cached.name, cached.sgf);
  };

  const totalPages = Math.ceil(total / PAGE_SIZE);
  const selectedKifu = visibleKifu.find((k) => k.id === selectedId);

  return (
    <Box sx={{ display: 'flex', flexDirection: 'row', height: '100%', overflow: 'hidden' }}>
      {/* List panel */}
      <Box sx={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        <Box sx={{ px: 3, pt: 3, pb: 1.5 }}>
          <Box sx={{ display: 'flex', alignItems: 'baseline', gap: 1.5, mb: 2 }}>
            <Typography variant="h4" sx={{ fontWeight: 700, letterSpacing: '-0.02em' }}>
              {t('Stone Placement', '摆谱')}
            </Typography>
            <Typography variant="body2" sx={{ color: 'text.secondary', fontWeight: 400, opacity: 0.6 }}>
              {t('19×19 only', '仅 19 路')}
            </Typography>
            <Box sx={{ flex: 1 }} />
            <Button
              size="small"
              startIcon={<UploadIcon sx={{ fontSize: 18 }} />}
              onClick={() => fileInputRef.current?.click()}
              data-testid="baipu-import"
              sx={{ textTransform: 'none', color: 'text.secondary' }}
            >
              {t('Import SGF', '导入棋谱')}
            </Button>
            <input ref={fileInputRef} type="file" accept=".sgf" hidden onChange={handleImportFile} />
          </Box>

          <TextField
            fullWidth
            size="small"
            placeholder={t('Search players, events...', '搜索棋手、赛事...')}
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            InputProps={{
              startAdornment: (
                <InputAdornment position="start">
                  <SearchIcon sx={{ color: 'text.secondary', fontSize: 20, opacity: 0.6 }} />
                </InputAdornment>
              ),
            }}
            sx={{
              '& .MuiOutlinedInput-root': {
                bgcolor: 'var(--raise2)', borderRadius: '10px', fontSize: '0.88rem',
                '& fieldset': { borderColor: 'divider' },
              },
            }}
          />
        </Box>

        {/* Recent / resume */}
        {recent.length > 0 && (
          <Box sx={{ px: 3, pb: 1 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, mb: 0.5 }}>
              <HistoryIcon sx={{ fontSize: 15, color: 'text.secondary', opacity: 0.6 }} />
              <Typography variant="caption" color="text.secondary">{t('Recent', '最近')}</Typography>
            </Box>
            <Box sx={{ display: 'flex', gap: 0.75, flexWrap: 'wrap' }}>
              {recent.slice(0, 6).map((r) => (
                <Chip
                  key={r.id}
                  label={r.name}
                  size="small"
                  onClick={() => handleResume(r)}
                  data-testid="baipu-recent-chip"
                  sx={{ bgcolor: 'background.paper', border: '1px solid', borderColor: 'divider', maxWidth: 180 }}
                />
              ))}
            </Box>
            <Divider sx={{ mt: 1.5, borderColor: 'divider' }} />
          </Box>
        )}

        {/* Card list */}
        <Box sx={{ flex: 1, overflow: 'auto', px: 2, py: 1, minHeight: 0 }}>
          {loading && kifuList.length === 0 ? (
            <Box sx={{ display: 'flex', justifyContent: 'center', py: 6 }}><CircularProgress size={32} /></Box>
          ) : error ? (
            <Box sx={{ display: 'flex', justifyContent: 'center', py: 6 }}>
              <Typography variant="body2" color="error">{error}</Typography>
            </Box>
          ) : visibleKifu.length === 0 ? (
            <Box data-testid="baipu-empty" sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 1, py: 6, px: 3, textAlign: 'center' }}>
              <GridOnIcon sx={{ fontSize: 40, color: 'text.secondary', opacity: 0.3 }} />
              <Typography variant="body2" color="text.secondary">
                {t('No 19×19 records found', '未找到 19 路棋谱')}
              </Typography>
              <Typography variant="caption" color="text.secondary" sx={{ opacity: 0.6 }}>
                {t('Try a different search, or import an SGF file.', '换个关键词，或导入一个 SGF 文件。')}
              </Typography>
            </Box>
          ) : (
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
              {visibleKifu.map((kifu, index) => {
                const selected = selectedId === kifu.id;
                return (
                  <Fade key={kifu.id} in timeout={200 + index * ROW_STAGGER}>
                    <Box>
                      <Card
                        sx={{
                          bgcolor: selected ? 'primary.dark' : 'background.paper',
                          border: selected ? 2 : 1,
                          borderColor: selected ? 'primary.main' : 'divider',
                          borderRadius: '8px',
                        }}
                      >
                        <CardActionArea onClick={() => handleSelect(kifu.id)} sx={{ p: 1.5 }}>
                          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 0.5 }}>
                            <Typography variant="caption" color="text.secondary" noWrap sx={{ flex: 1 }}>
                              {kifu.event}
                            </Typography>
                            <Typography variant="caption" color="text.secondary" sx={{ flexShrink: 0 }}>
                              {kifu.move_count} {t('moves', '手')}
                            </Typography>
                          </Box>
                          <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                            <Typography variant="body2" noWrap>{kifu.player_black}</Typography>
                            <Typography variant="caption" color="text.secondary" sx={{ px: 1 }}>vs</Typography>
                            <Typography variant="body2" noWrap>{kifu.player_white}</Typography>
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

        {totalPages > 1 && (
          <Box sx={{ display: 'flex', justifyContent: 'center', py: 1, borderTop: '1px solid', borderColor: 'divider', flexShrink: 0 }}>
            <Pagination count={totalPages} page={page} onChange={(_, p) => setPage(p)} color="primary" shape="rounded" size="small" />
          </Box>
        )}
      </Box>

      {/* Preview panel */}
      <Box
        sx={{
          flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center',
          bgcolor: 'background.default', overflow: 'hidden',
          borderLeft: '1px solid',
          borderColor: 'divider',
        }}
      >
        {selectedKifu && previewSgf ? (
          <>
            <Box sx={{ flex: 1, display: 'flex', justifyContent: 'center', alignItems: 'center', width: '100%', minHeight: 0 }}>
              <LiveBoard moves={previewMoves} stoneColors={previewColors} currentMove={previewMoves.length} boardSize={previewBoardSize} showCoordinates />
            </Box>
            <Box sx={{ px: 3, py: 2, bgcolor: 'background.paper', borderTop: '1px solid', borderColor: 'divider', width: '100%', display: 'flex', justifyContent: 'center' }}>
              <Button
                variant="contained"
                onClick={handleStartSelected}
                data-testid="baipu-start"
                sx={{ minWidth: 220, minHeight: 52, fontSize: '1.05rem', borderRadius: '10px', textTransform: 'none' }}
              >
                {t('Start placing', '开始摆谱')}
              </Button>
            </Box>
          </>
        ) : (
          <Box sx={{ flex: 1, display: 'flex', justifyContent: 'center', alignItems: 'center' }}>
            <Typography variant="body2" color="text.secondary" sx={{ opacity: 0.4 }}>
              {t('Select or import a game to begin', '选择或导入一局棋谱以开始')}
            </Typography>
          </Box>
        )}
      </Box>

      <Snackbar open={!!actionError} autoHideDuration={4000} onClose={() => setActionError(null)} anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}>
        <Alert severity="error" onClose={() => setActionError(null)}>{actionError}</Alert>
      </Snackbar>
    </Box>
  );
};

export default BaipuListPage;
