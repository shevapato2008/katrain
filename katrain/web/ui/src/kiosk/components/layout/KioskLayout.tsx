import { Box } from '@mui/material';
import { Outlet } from 'react-router-dom';
import StatusBar from './StatusBar';
import NavigationRail from './NavigationRail';
import TopTabBar from './TopTabBar';
import { useOrientation } from '../../context/OrientationContext';

interface KioskLayoutProps {
  username?: string;
}

const KioskLayout = ({ username }: KioskLayoutProps) => {
  const { isPortrait } = useOrientation();

  return (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'column',
        height: '100%',
        width: '100%',
        overflow: 'hidden',
        bgcolor: 'background.default',
      }}
    >
      <StatusBar username={username} />
      {isPortrait ? (
        <>
          <TopTabBar />
          <Box
            component="main"
            sx={{ flex: 1, overflow: 'auto', display: 'flex', flexDirection: 'column' }}
          >
            <Outlet />
          </Box>
        </>
      ) : (
        <Box sx={{ display: 'flex', flex: 1, overflow: 'hidden' }}>
          <NavigationRail />
          <Box
            component="main"
            sx={{ flex: 1, overflow: 'auto', display: 'flex', flexDirection: 'column' }}
          >
            <Outlet />
          </Box>
        </Box>
      )}
    </Box>
  );
};

export default KioskLayout;
