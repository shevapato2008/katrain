import { Box, ButtonBase, Typography, useTheme } from '@mui/material';
import { alpha } from '@mui/material/styles';
import { useNavigate, useLocation, matchPath } from 'react-router-dom';
import { primaryTabs, settingsTab, type NavTab } from './navTabs';

const TopTabBar = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const theme = useTheme();

  const isActive = (pattern: string) => !!matchPath(pattern, location.pathname);

  const renderItem = (tab: NavTab) => {
    const active = isActive(tab.pattern);
    return (
      <ButtonBase
        key={tab.path}
        onClick={() => navigate(tab.path)}
        data-active={active}
        sx={{
          display: 'flex',
          alignItems: 'center',
          gap: 0.5,
          px: 1.5,
          height: '100%',
          borderRadius: 1,
          color: active ? 'primary.main' : 'text.secondary',
          bgcolor: active ? alpha(theme.palette.primary.main, 0.08) : 'transparent',
          transition: 'all 150ms ease-out',
          '&:active': { transform: 'scale(0.94)' },
        }}
      >
        <Box sx={{ fontSize: 18, display: 'flex' }}>{tab.icon}</Box>
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
        height: 48,
        display: 'flex',
        alignItems: 'center',
        px: 0.5,
        gap: 0.5,
        borderBottom: '1px solid',
        borderColor: 'divider',
        bgcolor: 'background.default',
        flexShrink: 0,
      }}
    >
      {primaryTabs.map(renderItem)}
      <Box sx={{ ml: 'auto' }} />
      {renderItem(settingsTab)}
    </Box>
  );
};

export default TopTabBar;
