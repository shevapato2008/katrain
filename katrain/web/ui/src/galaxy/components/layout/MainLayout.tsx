import { Box } from '@mui/material';
import { Outlet } from 'react-router-dom';
import { GameNavigationProvider } from '../../context/GameNavigationContext';
import GalaxyBottomNav, { GALAXY_BOTTOM_NAV_HEIGHT } from './GalaxyBottomNav';
import GalaxySidebar from './GalaxySidebar';
import GalaxyTopBar from './GalaxyTopBar';
import { useGalaxySidebar } from './useGalaxySidebar';

const MainLayoutChrome = () => {
  const sidebarState = useGalaxySidebar();
  const mobile = sidebarState.mode === 'mobile';

  return (
    <Box
      className="galaxy-root"
      sx={{ width: '100vw', height: '100dvh', overflow: 'hidden', display: 'flex', flexDirection: 'column', bgcolor: 'background.default' }}
    >
      <GalaxyTopBar />
      <Box sx={{ position: 'relative', display: 'flex', flex: 1, minHeight: 0 }}>
        {!mobile && <GalaxySidebar sidebarState={sidebarState} />}
        <Box
          component="main"
          data-testid="galaxy-main"
          sx={{ flex: 1, minWidth: 0, minHeight: 0, display: 'flex', flexDirection: 'column', pb: mobile ? `calc(${GALAXY_BOTTOM_NAV_HEIGHT}px + env(safe-area-inset-bottom))` : 0, boxSizing: 'border-box' }}
        >
          <Outlet />
        </Box>
      </Box>
      {mobile && <GalaxyBottomNav />}
    </Box>
  );
};

const MainLayout = () => (
  <GameNavigationProvider>
    <MainLayoutChrome />
  </GameNavigationProvider>
);

export default MainLayout;
