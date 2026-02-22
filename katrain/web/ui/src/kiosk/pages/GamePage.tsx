import { useEffect, useState } from 'react';
import { Box, Typography, Button, CircularProgress } from '@mui/material';
import { ExitToApp } from '@mui/icons-material';
import { useNavigate, useParams } from 'react-router-dom';
import { useGameSession } from '../../hooks/useGameSession';
import { useAuth } from '../../context/AuthContext';
import Board from '../../components/Board';
import GameControlPanel from '../components/game/GameControlPanel';
import { useTranslation } from '../../hooks/useTranslation';
import { useOrientation } from '../context/OrientationContext';

const GamePage = () => {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const { sessionId } = useParams<{ sessionId: string }>();
  const { token } = useAuth();
  const { isPortrait } = useOrientation();
  const session = useGameSession({ token: token ?? undefined });
  const [analysisToggles, setAnalysisToggles] = useState({
    show_ownership: false,
    show_hints: false,
    show_move_numbers: false,
    show_coordinates: true,
  });

  useEffect(() => {
    if (sessionId) session.setSessionId(sessionId);
  }, [sessionId]);

  if (!session.gameState) {
    return (
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%' }}>
        <CircularProgress />
      </Box>
    );
  }

  const gameState = session.gameState;
  const gameTitle = `${gameState.players_info.B.name} vs ${gameState.players_info.W.name}`;

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%', bgcolor: 'background.default' }}>
      {/* Header */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', px: 2, py: 1 }}>
        <Typography variant="subtitle1" sx={{ fontWeight: 600 }}>{gameTitle}</Typography>
        <Button variant="outlined" size="small" startIcon={<ExitToApp />}
          onClick={() => navigate('/kiosk/play')}>
          {t('Exit', '退出')}
        </Button>
      </Box>
      {/* Board + Panel */}
      <Box sx={{ display: 'flex', flexDirection: isPortrait ? 'column' : 'row', flex: 1, overflow: 'hidden' }}>
        <Box sx={isPortrait ? { width: '100%', maxHeight: '50%', aspectRatio: '1' } : { height: '100%', aspectRatio: '1' }}>
          <Board
            gameState={gameState}
            onMove={session.onMove}
            onNavigate={session.onNavigate}
            analysisToggles={analysisToggles}
          />
        </Box>
        <Box sx={{ flex: 1, overflow: 'auto' }}>
          <GameControlPanel
            gameState={gameState}
            onAction={session.handleAction}
            onNavigate={session.onNavigate}
            analysisToggles={analysisToggles}
            onToggleAnalysis={(key) => setAnalysisToggles(prev => ({ ...prev, [key]: !prev[key as keyof typeof prev] }))}
          />
        </Box>
      </Box>
    </Box>
  );
};

export default GamePage;
