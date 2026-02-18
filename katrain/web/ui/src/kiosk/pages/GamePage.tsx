import { Box, Typography, Button } from '@mui/material';
import { ExitToApp } from '@mui/icons-material';
import { useNavigate } from 'react-router-dom';
import MockBoard from '../components/game/MockBoard';
import GameControlPanel from '../components/game/GameControlPanel';
import { mockGameState } from '../data/mocks';

const GamePage = () => {
  const navigate = useNavigate();

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', height: '100vh', bgcolor: 'background.default' }}>
      {/* Header */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', px: 2, py: 1 }}>
        <Typography variant="subtitle1" sx={{ fontWeight: 600 }}>{mockGameState.gameTitle}</Typography>
        <Button
          variant="outlined"
          size="small"
          startIcon={<ExitToApp />}
          onClick={() => navigate('/kiosk/play')}
        >
          退出
        </Button>
      </Box>
      {/* Board + Panel */}
      <Box sx={{ display: 'flex', flex: 1, overflow: 'hidden' }}>
        <Box sx={{ height: '100%', aspectRatio: '1' }}>
          <MockBoard moveNumber={mockGameState.moveNumber} />
        </Box>
        <Box sx={{ flex: 1, overflow: 'auto' }}>
          <GameControlPanel {...mockGameState} />
        </Box>
      </Box>
    </Box>
  );
};

export default GamePage;
