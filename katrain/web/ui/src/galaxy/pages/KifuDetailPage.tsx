import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Box, Typography, CircularProgress, Alert, Button, IconButton } from '@mui/material';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';

import Board from '../../components/Board';
import AnalysisPanel from '../../components/AnalysisPanel';
import ScoreGraph from '../../components/ScoreGraph';
import { useGameSession } from '../hooks/useGameSession';
import { KifuAPI } from '../api/kifuApi';
import { API } from '../../api';
import { i18n } from '../../i18n';
import type { KifuAlbumDetail } from '../types/kifu';

export default function KifuDetailPage() {
  const { albumId } = useParams<{ albumId: string }>();
  const navigate = useNavigate();
  const { gameState, onMove, onNavigate, sessionId, initNewSession } = useGameSession();

  const [album, setAlbum] = useState<KifuAlbumDetail | null>(null);
  const [albumError, setAlbumError] = useState<string | null>(null);
  const [sgfLoaded, setSgfLoaded] = useState(false);

  // Fetch album detail
  useEffect(() => {
    if (!albumId) return;
    setAlbum(null);
    setAlbumError(null);
    setSgfLoaded(false);
    KifuAPI.getAlbum(Number(albumId))
      .then(setAlbum)
      .catch((err) => setAlbumError(err.message || 'Failed to load kifu'));
  }, [albumId]);

  // Init session + load SGF once album is fetched
  useEffect(() => {
    if (!album || sgfLoaded) return;
    if (!sessionId) {
      initNewSession();
      return;
    }
    API.loadSGF(sessionId, album.sgf_content)
      .then(() => API.redo(sessionId, 9999))
      .then(() => setSgfLoaded(true))
      .catch((err) => console.error('Failed to load SGF:', err));
  }, [album, sessionId, sgfLoaded, initNewSession]);

  // Loading state
  if (!album && !albumError) {
    return (
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%' }}>
        <CircularProgress />
      </Box>
    );
  }

  // Error state
  if (albumError || !album) {
    return (
      <Box sx={{ p: 3 }}>
        <Alert severity="error" sx={{ mb: 2 }}>
          {albumError || i18n.t('kifu:load_error', 'Failed to load game record')}
        </Alert>
        <Button startIcon={<ArrowBackIcon />} onClick={() => navigate('/galaxy/kifu')}>
          {i18n.t('kifu:back_to_list', 'Back to library')}
        </Button>
      </Box>
    );
  }

  return (
      <Box sx={{ display: 'flex', height: '100%', overflow: 'hidden' }}>
        {/* Left: Board area */}
        <Box sx={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden', p: 2 }}>
          {/* Header */}
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
            <IconButton onClick={() => navigate('/galaxy/kifu')} size="small">
              <ArrowBackIcon />
            </IconButton>
            <Typography variant="h6" sx={{ flex: 1 }} noWrap>
              {album.player_black} vs {album.player_white}
            </Typography>
          </Box>

          {/* Board */}
          <Box sx={{ flex: 1, minHeight: 0, display: 'flex', justifyContent: 'center', alignItems: 'center', bgcolor: '#262626', borderRadius: 1 }}>
            {gameState ? (
              <Board
                gameState={gameState}
                onMove={(x, y) => onMove(x, y)}
                onNavigate={onNavigate}
                analysisToggles={{ coords: true }}
              />
            ) : (
              <Typography color="text.secondary">{i18n.t('Loading Board...', 'Loading Board...')}</Typography>
            )}
          </Box>

          {/* Score graph */}
          <Box sx={{ height: 150, borderTop: '1px solid #444', bgcolor: '#1e1e1e', mt: 1, borderRadius: 1 }}>
            {gameState && <ScoreGraph gameState={gameState} onNavigate={onNavigate} showScore={true} showWinrate={true} />}
          </Box>
        </Box>

        {/* Right: Sidebar */}
        <Box
          sx={{
            width: 400,
            borderLeft: 1,
            borderColor: 'divider',
            display: 'flex',
            flexDirection: 'column',
            overflow: 'hidden',
            bgcolor: 'rgba(40, 40, 45, 0.95)',
          }}
        >
          {/* Game info */}
          <Box sx={{ p: 2.5, borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
            {/* Event */}
            {album.event && (
              <Typography variant="subtitle2" fontWeight={600} sx={{ mb: 0.5 }}>
                {album.event}
                {album.round_name && (
                  <Typography component="span" variant="caption" color="text.secondary" sx={{ ml: 1 }}>
                    {album.round_name}
                  </Typography>
                )}
              </Typography>
            )}

            {/* Players */}
            <Box sx={{ mt: 1.5, display: 'flex', flexDirection: 'column', gap: 1 }}>
              {/* Black player */}
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <Box sx={{ width: 12, height: 12, borderRadius: '50%', bgcolor: '#1a1a1a', border: '1px solid rgba(255,255,255,0.2)', flexShrink: 0 }} />
                <Typography variant="body2" fontWeight={600}>{album.player_black}</Typography>
                {album.black_rank && (
                  <Typography variant="caption" color="text.secondary">{album.black_rank}</Typography>
                )}
              </Box>

              {/* Result badge */}
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, pl: 2.5 }}>
                <Typography
                  variant="caption"
                  sx={{
                    px: 1,
                    py: 0.25,
                    borderRadius: 0.5,
                    bgcolor: album.result?.startsWith('B') ? 'rgba(0,0,0,0.6)' : album.result?.startsWith('W') ? 'rgba(255,255,255,0.15)' : 'rgba(128,128,128,0.3)',
                    color: album.result?.startsWith('B') ? '#fff' : 'text.primary',
                    fontWeight: 600,
                    border: '1px solid rgba(255,255,255,0.1)',
                  }}
                >
                  {album.result || '?'}
                </Typography>
              </Box>

              {/* White player */}
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <Box sx={{ width: 12, height: 12, borderRadius: '50%', bgcolor: '#e8e8e8', flexShrink: 0 }} />
                <Typography variant="body2" fontWeight={600}>{album.player_white}</Typography>
                {album.white_rank && (
                  <Typography variant="caption" color="text.secondary">{album.white_rank}</Typography>
                )}
              </Box>
            </Box>
          </Box>

          {/* Meta info */}
          <Box sx={{ p: 2.5, borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
            <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 1.5 }}>
              {album.date_played && (
                <MetaItem label={i18n.t('kifu:date', 'Date')} value={album.date_played} />
              )}
              {album.komi != null && (
                <MetaItem label={i18n.t('kifu:komi', 'Komi')} value={String(album.komi)} />
              )}
              {album.handicap > 0 && (
                <MetaItem label={i18n.t('kifu:handicap', 'Handicap')} value={String(album.handicap)} />
              )}
              <MetaItem label={i18n.t('kifu:board_size', 'Board')} value={`${album.board_size}×${album.board_size}`} />
              {album.move_count > 0 && (
                <MetaItem label={i18n.t('kifu:moves', 'Moves')} value={String(album.move_count)} />
              )}
              {album.rules && (
                <MetaItem label={i18n.t('kifu:rules', 'Rules')} value={album.rules} />
              )}
              {album.place && (
                <MetaItem label={i18n.t('kifu:place', 'Place')} value={album.place} />
              )}
              {album.source && (
                <MetaItem label={i18n.t('kifu:source', 'Source')} value={album.source} />
              )}
            </Box>
          </Box>

          {/* Analysis panel */}
          <Box sx={{ flexGrow: 1, overflow: 'hidden' }}>
            {gameState && (
              <AnalysisPanel
                gameState={gameState}
                onNodeAction={() => {}}
                onShowPV={() => {}}
                onClearPV={() => {}}
              />
            )}
          </Box>
        </Box>
      </Box>
  );
}

function MetaItem({ label, value }: { label: string; value: string }) {
  return (
    <Box>
      <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.7rem', letterSpacing: '0.03em' }}>
        {label}
      </Typography>
      <Typography variant="body2" sx={{ fontSize: '0.8rem' }}>
        {value}
      </Typography>
    </Box>
  );
}
