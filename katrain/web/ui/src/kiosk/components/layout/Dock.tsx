import { Box, ButtonBase, Typography, useTheme } from '@mui/material';
import { useNavigate, useLocation, matchPath } from 'react-router-dom';
import { useTranslation } from '../../../hooks/useTranslation';
import { primaryTabs, reportTab, type NavTab } from './navTabs';

const dockTabs: NavTab[] = [...primaryTabs, reportTab];

const Dock = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const theme = useTheme();
  const { t } = useTranslation();

  const isActive = (pattern: string) => !!matchPath(pattern, location.pathname);

  const renderItem = (tab: NavTab) => {
    const active = isActive(tab.pattern);
    return (
      <ButtonBase
        key={tab.path}
        onClick={() => navigate(tab.path)}
        data-active={active}
        sx={{
          flex: 1,
          minWidth: 0,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          gap: 0.5,
          borderRadius: '14px',
          color: active ? '#0e1a13' : 'text.secondary',
          bgcolor: active ? 'primary.main' : 'transparent',
          transform: active ? 'translateY(-2px)' : 'none',
          boxShadow: active ? `0 10px 24px -10px ${theme.palette.primary.main}` : 'none',
          transition: 'all 150ms ease-out',
          '&:hover': active ? undefined : { bgcolor: 'rgba(255,255,255,0.03)' },
          '&:active': { transform: active ? 'translateY(-2px) scale(0.96)' : 'scale(0.94)' },
        }}
      >
        <Box sx={{ display: 'flex', '& svg': { fontSize: 24 } }}>{tab.icon}</Box>
        <Typography sx={{ fontSize: 13, fontWeight: 600, letterSpacing: '.5px' }}>
          {t(`kiosk:nav_${tab.path.split('/').at(-1)}`, tab.label)}
        </Typography>
      </ButtonBase>
    );
  };

  return (
    <Box
      component="nav"
      sx={{
        height: 86,
        flexShrink: 0,
        display: 'flex',
        alignItems: 'stretch',
        px: 1.75,
        py: 1,
        gap: 0.5,
        borderTop: '1px solid',
        borderColor: 'divider',
      }}
    >
      {dockTabs.map(renderItem)}
    </Box>
  );
};

export default Dock;
