import { useEffect, useMemo, useState } from 'react';
import { BottomNavigation, BottomNavigationAction, Menu, MenuItem, Paper } from '@mui/material';
import MoreHorizIcon from '@mui/icons-material/MoreHoriz';
import { useLocation } from 'react-router-dom';
import { useTranslation } from '../../../hooks/useTranslation';
import { useGameNavigation } from '../../context/GameNavigationContext';
import { getGalaxyNavigation, isGalaxyNavigationActive } from './galaxyNavigation';

export const GALAXY_BOTTOM_NAV_HEIGHT = 64;

const GalaxyBottomNav = () => {
  const { t } = useTranslation();
  const { requestNavigation } = useGameNavigation();
  const { pathname } = useLocation();
  const items = useMemo(() => getGalaxyNavigation(t), [t]);
  const directItems = items.slice(0, 5);
  const moreItems = items.slice(5);
  const [moreAnchor, setMoreAnchor] = useState<HTMLElement | null>(null);

  useEffect(() => setMoreAnchor(null), [pathname]);

  const activeItem = items.find((item) => isGalaxyNavigationActive(pathname, item.path));

  return (
    <Paper
      component="nav"
      aria-label={t('galaxy.primary_navigation', 'Primary navigation')}
      data-testid="galaxy-bottom-nav"
      elevation={10}
      style={{ position: 'fixed' }}
      sx={{ left: 0, right: 0, bottom: 0, zIndex: (theme) => theme.zIndex.appBar, pb: 'env(safe-area-inset-bottom)' }}
    >
      <BottomNavigation value={activeItem?.key ?? false} showLabels sx={{ height: GALAXY_BOTTOM_NAV_HEIGHT }}>
        {directItems.map((item) => (
          <BottomNavigationAction
            key={item.key}
            data-testid="galaxy-bottom-destination"
            value={item.key}
            label={item.label}
            aria-label={item.label}
            icon={item.icon}
            onClick={() => requestNavigation(item.path)}
          />
        ))}
        <BottomNavigationAction
          value="more"
          label={t('More', 'More')}
          aria-label={t('More', 'More')}
          icon={<MoreHorizIcon />}
          onClick={(event) => setMoreAnchor(event.currentTarget)}
        />
      </BottomNavigation>
      <Menu anchorEl={moreAnchor} open={Boolean(moreAnchor)} onClose={() => setMoreAnchor(null)}>
        {moreItems.map((item) => (
          <MenuItem
            key={item.key}
            selected={isGalaxyNavigationActive(pathname, item.path)}
            onClick={() => {
              setMoreAnchor(null);
              requestNavigation(item.path);
            }}
          >
            {item.icon}
            {item.label}
          </MenuItem>
        ))}
      </Menu>
    </Paper>
  );
};

export default GalaxyBottomNav;
