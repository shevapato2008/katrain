import { Box } from '@mui/material';
import MockBoard from '../components/game/MockBoard';
import GameControlPanel from '../components/game/GameControlPanel';
import { mockGameState } from '../data/mocks';

const GamePage = () => {
  return (
    <Box sx={{ display: 'flex', height: '100vh', bgcolor: 'background.default' }}>
      <Box sx={{ height: '100%', aspectRatio: '1' }}>
        <MockBoard moveNumber={mockGameState.moveNumber} />
      </Box>
      <Box sx={{ flex: 1, overflow: 'auto' }}>
        <GameControlPanel {...mockGameState} />
      </Box>
    </Box>
  );
};

export default GamePage;
