import { Box } from '@mui/material';
import { Outlet } from 'react-router-dom';
import GalaxySidebar from './GalaxySidebar';
import { GameNavigationProvider } from '../../context/GameNavigationContext';

const MainLayout = () => {
  return (
    <GameNavigationProvider>
      <Box sx={{ display: 'flex', height: '100vh', width: '100vw', overflow: 'hidden', bgcolor: 'background.default' }}>
        <GalaxySidebar />
        <Box component="main" sx={{ flexGrow: 1, overflow: 'auto', display: 'flex', flexDirection: 'column' }}>
          <Outlet />
        </Box>
      </Box>
    </GameNavigationProvider>
  );
};

export default MainLayout;
