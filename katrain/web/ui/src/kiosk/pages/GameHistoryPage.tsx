import { useState, useEffect, useCallback } from 'react';
import { Box, Typography, List, ListItemButton, CircularProgress, Chip, Button } from '@mui/material';
import { Science as ScienceIcon } from '@mui/icons-material';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { useTranslation } from '../../hooks/useTranslation';
import LiveBoard from '../../components/live/LiveBoard';
import { sgfToMoves } from '../../utils/sgfSerializer';
import KioskResultBadge from '../components/game/KioskResultBadge';
import { UserGamesAPI, type UserGameSummary, type UserGameDetail } from '../../api/userGamesApi';

const PAGE_SIZE = 30;

/**
 * Route: play/pvp/history — 对局历史 (Task 8). Read-only browser over the user's
 * recorded games (user_games), scoped to this account via the JWT. List omits SGF
 * (server-side `include_sgf=False`) so selecting a row triggers a second fetch
 * (UserGamesAPI.get) for the full detail — mirrors KifuPage's selectedId→getAlbum
 * pattern. 复盘 hands off via the same `?user_game_id=` deep link ResearchPage
 * (Task 7b) already wires up; no session pre-creation needed here.
 */
const GameHistoryPage = () => {
  const { t } = useTranslation();
  const { token } = useAuth();
  const navigate = useNavigate();

  const [source, setSource] = useState<'play_local' | 'all'>('play_local');
  const [items, setItems] = useState<UserGameSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<UserGameDetail | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);

  // All setState happens inside the async .then/.catch/.finally callbacks (never
  // synchronously in the effect body) to satisfy react-hooks/set-state-in-effect —
  // mirrors BaipuListPage's fetchAlbums. The initial useState(true) covers the first
  // load; toggling 本地/全部 swaps data in without a loading flash.
  const fetchGames = useCallback((src: 'play_local' | 'all') => {
    if (!token) return;
    UserGamesAPI.list(token, {
      page: 1,
      page_size: PAGE_SIZE,
      ...(src === 'play_local' ? { source: 'play_local' } : {}),
    })
      .then((resp) => {
        setItems(resp.items);
        setError(null);
      })
      .catch((err: Error) => {
        setError(err.message);
      })
      .finally(() => {
        setLoading(false);
      });
  }, [token]);

  useEffect(() => {
    fetchGames(source);
  }, [source, fetchGames]);

  // Fetch full game detail (SGF) when a row is selected — mirrors KifuPage's
  // selectedId→getAlbum effect so the `cancelled` cleanup actually runs (React
  // discards a plain event-handler's return value, so this must be a real effect):
  // rapid taps across rows abort the stale fetch instead of letting it clobber
  // `detail` out of order.
  useEffect(() => {
    if (selectedId === null || !token) return;
    let cancelled = false;
    setDetail(null);
    setPreviewLoading(true);
    UserGamesAPI.get(token, selectedId)
      .then((d) => { if (!cancelled) setDetail(d); })
      .catch((err) => { if (!cancelled) console.error('Failed to load game detail:', err); })
      .finally(() => { if (!cancelled) setPreviewLoading(false); });

    return () => { cancelled = true; };
  }, [selectedId, token]);

  const handleReview = () => {
    if (!detail) return;
    navigate(`/kiosk/research?user_game_id=${detail.id}&analyze=1`);
  };

  const parsed = detail?.sgf_content ? sgfToMoves(detail.sgf_content) : null;

  return (
    <Box sx={{ display: 'flex', flexDirection: 'row', height: '100%', overflow: 'hidden' }}>
      {/* List panel */}
      <Box sx={{ width: 360, flexShrink: 0, display: 'flex', flexDirection: 'column', overflow: 'hidden', borderRight: '1px solid', borderColor: 'divider' }}>
        <Box sx={{ px: 2.5, pt: 2.5, pb: 1.5 }}>
          <Typography variant="h5" sx={{ fontFamily: "'Newsreader','Noto Serif SC',serif", fontWeight: 500, mb: 1.5 }}>
            {t('Game History', '对局历史')}
          </Typography>
          <Box sx={{ display: 'flex', gap: 1 }}>
            <Chip
              label={t('Local games', '本地对局')}
              color={source === 'play_local' ? 'primary' : 'default'}
              onClick={() => setSource('play_local')}
              size="small"
            />
            <Chip
              label={t('All', '全部')}
              color={source === 'all' ? 'primary' : 'default'}
              onClick={() => setSource('all')}
              size="small"
            />
          </Box>
        </Box>

        <Box sx={{ flex: 1, overflow: 'auto', minHeight: 0 }}>
          {loading ? (
            <Box sx={{ display: 'flex', justifyContent: 'center', py: 6 }}>
              <CircularProgress size={28} />
            </Box>
          ) : error ? (
            <Box sx={{ display: 'flex', justifyContent: 'center', py: 6 }}>
              <Typography variant="body2" color="error">{error}</Typography>
            </Box>
          ) : items.length === 0 ? (
            <Box sx={{ display: 'flex', justifyContent: 'center', py: 6, px: 2 }}>
              <Typography variant="body2" color="text.secondary">
                {t('No recorded games yet', '暂无对局记录')}
              </Typography>
            </Box>
          ) : (
            <List disablePadding>
              {items.map((g) => (
                <ListItemButton
                  key={g.id}
                  selected={selectedId === g.id}
                  onClick={() => setSelectedId(g.id)}
                  sx={{ display: 'block', px: 2.5, py: 1.25, borderBottom: '1px solid', borderColor: 'divider' }}
                >
                  <Typography sx={{ fontWeight: 600, fontSize: 14 }}>
                    {g.player_black || t('Black', '黑方')}
                  </Typography>
                  <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }}>
                    {t('vs', '对')} {g.player_white || t('White', '白方')}
                  </Typography>
                  <Typography variant="caption" color="text.secondary">
                    {g.result || '—'} · {g.move_count}{t('moves', '手')} · {g.game_date || g.created_at?.slice(0, 10)}
                  </Typography>
                </ListItemButton>
              ))}
            </List>
          )}
        </Box>
      </Box>

      {/* Preview panel */}
      <Box sx={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', overflow: 'hidden' }}>
        {selectedId ? (
          <>
            <Box sx={{ flex: 1, display: 'flex', justifyContent: 'center', alignItems: 'center', width: '100%', minHeight: 0 }}>
              {previewLoading || !parsed ? (
                <CircularProgress size={32} />
              ) : (
                <LiveBoard
                  moves={parsed.moves}
                  stoneColors={parsed.stoneColors}
                  currentMove={parsed.moves.length}
                  boardSize={parsed.metadata.boardSize || detail?.board_size || 19}
                  showCoordinates
                />
              )}
            </Box>
            <Box sx={{ px: 3, py: 1.5, width: '100%', borderTop: '1px solid', borderColor: 'divider', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 2 }}>
              {detail?.result && <KioskResultBadge result={detail.result} rules={detail.rules} />}
              <Button
                variant="contained"
                startIcon={<ScienceIcon sx={{ fontSize: 16 }} />}
                onClick={handleReview}
                disabled={!detail}
              >
                {t('Review', '复盘')}
              </Button>
            </Box>
          </>
        ) : (
          <Typography color="text.secondary" sx={{ m: 'auto' }}>
            {t('Select a game to preview', '选择一局查看')}
          </Typography>
        )}
      </Box>
    </Box>
  );
};

export default GameHistoryPage;
