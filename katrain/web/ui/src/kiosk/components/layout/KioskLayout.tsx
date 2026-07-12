import { Box } from '@mui/material';
import { Outlet, useLocation } from 'react-router-dom';
import { ImmersiveProvider, useImmersive } from '../../context/ImmersiveContext';
import Header from './Header';
import Dock from './Dock';
import SmartBoardConsole from './SmartBoardConsole';
import { L1_PATHS } from './navTabs';

const CONSOLE_ROUTES = ['/kiosk/play'];
interface KioskLayoutProps { username?: string }

const KioskShell = ({ username }: KioskLayoutProps) => {
  const { immersive } = useImmersive();
  const location = useLocation();
  const isL1 = L1_PATHS.includes(location.pathname);
  const showConsole = !immersive && CONSOLE_ROUTES.includes(location.pathname);
  const showDock = !immersive && isL1; // Dock only on first-level pages
  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%', width: '100%', overflow: 'hidden', bgcolor: 'background.default' }}>
      {!immersive && <Header username={username} />}
      <Box sx={{ display: 'flex', flex: 1, minHeight: 0, overflow: 'hidden' }}>
        {showConsole && <SmartBoardConsole />}
        <Box component="main" sx={{ flex: 1, minWidth: 0, overflow: 'auto', display: 'flex', flexDirection: 'column' }}>
          <Outlet />
        </Box>
      </Box>
      {showDock && <Dock />}
    </Box>
  );
};

const KioskLayout = ({ username }: KioskLayoutProps) => (
  <ImmersiveProvider>
    <KioskShell username={username} />
  </ImmersiveProvider>
);

export default KioskLayout;
