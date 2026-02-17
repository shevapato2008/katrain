import { Box, ButtonBase, Typography } from '@mui/material';
import {
  SportsEsports as PlayIcon,
  Extension as TsumegoIcon,
  Science as ResearchIcon,
  MenuBook as KifuIcon,
  LiveTv as LiveIcon,
  Settings as SettingsIcon,
} from '@mui/icons-material';
import { useNavigate, useLocation, matchPath } from 'react-router-dom';

const primaryTabs = [
  { label: '对弈', icon: <PlayIcon />, path: '/kiosk/play', pattern: '/kiosk/play/*' },
  { label: '死活', icon: <TsumegoIcon />, path: '/kiosk/tsumego', pattern: '/kiosk/tsumego/*' },
  { label: '研究', icon: <ResearchIcon />, path: '/kiosk/research', pattern: '/kiosk/research' },
  { label: '棋谱', icon: <KifuIcon />, path: '/kiosk/kifu', pattern: '/kiosk/kifu/*' },
  { label: '直播', icon: <LiveIcon />, path: '/kiosk/live', pattern: '/kiosk/live/*' },
];

const settingsTab = { label: '设置', icon: <SettingsIcon />, path: '/kiosk/settings', pattern: '/kiosk/settings' };

const NavigationRail = () => {
  const navigate = useNavigate();
  const location = useLocation();

  const isActive = (pattern: string) => !!matchPath(pattern, location.pathname);

  const renderItem = (tab: typeof primaryTabs[0], section: 'main' | 'footer') => {
    const active = isActive(tab.pattern);
    return (
      <ButtonBase
        key={tab.path}
        onClick={() => navigate(tab.path)}
        data-active={active}
        data-section={section}
        sx={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          gap: 0.5,
          py: 1.5,
          width: '100%',
          borderRadius: 1,
          color: active ? 'primary.main' : 'text.secondary',
          bgcolor: active ? 'rgba(92, 181, 122, 0.08)' : 'transparent',
          transition: 'all 150ms ease-out',
          '&:active': { transform: 'scale(0.94)' },
        }}
      >
        <Box sx={{ fontSize: 22, display: 'flex' }}>{tab.icon}</Box>
        <Typography variant="caption" sx={{ fontSize: 11, lineHeight: 1, fontFamily: "'Noto Sans SC', sans-serif" }}>
          {tab.label}
        </Typography>
      </ButtonBase>
    );
  };

  return (
    <Box
      component="nav"
      sx={{
        width: 72,
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        py: 1,
        px: 0.5,
        gap: 0.5,
        borderRight: '1px solid',
        borderColor: 'divider',
        bgcolor: 'background.default',
        flexShrink: 0,
      }}
    >
      {primaryTabs.map((tab) => renderItem(tab, 'main'))}
      <Box sx={{ mt: 'auto' }} />
      <Box sx={{ width: '80%', height: '1px', bgcolor: 'divider', my: 0.5 }} />
      {renderItem(settingsTab, 'footer')}
    </Box>
  );
};

export default NavigationRail;
