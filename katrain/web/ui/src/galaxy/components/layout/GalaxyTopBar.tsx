import type { ReactNode } from 'react';
import { Box, ButtonBase } from '@mui/material';
import { SYSTEM_UI_FONT } from '../../theme';
import { useGameNavigation } from '../../context/GameNavigationContext';

interface GalaxyTopBarProps {
  rightSlot?: ReactNode;
}

const GalaxyTopBar = ({ rightSlot }: GalaxyTopBarProps) => {
  const { requestNavigation } = useGameNavigation();

  return (
    <Box
      component="header"
      data-testid="galaxy-top-bar"
      sx={{
        boxSizing: 'border-box',
        height: 52,
        minHeight: 52,
        px: 2,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        bgcolor: 'background.paper',
        borderBottom: '1px solid',
        borderColor: 'divider',
      }}
    >
      <ButtonBase
        aria-label="回到首页"
        onClick={() => requestNavigation('/galaxy')}
        sx={{ height: '100%', gap: 1, borderRadius: 1, px: 0.5 }}
      >
        <img
          src="/assets/img/logo-white.png"
          alt="智星盒 StellaBox"
          style={{ width: 32, height: 32, objectFit: 'contain' }}
        />
        <Box
          component="span"
          className="galaxy-brand-cn"
          sx={{ fontFamily: '"Galaxy Long Cang"', fontSize: 22, lineHeight: 1, fontWeight: 400 }}
        >
          智星盒
        </Box>
        <Box
          component="span"
          className="galaxy-brand-latin"
          sx={{ fontFamily: SYSTEM_UI_FONT, fontSize: 14, lineHeight: 1, fontWeight: 600, letterSpacing: '0.02em' }}
        >
          StellaBox
        </Box>
      </ButtonBase>
      {rightSlot && <Box sx={{ display: 'flex', alignItems: 'center' }}>{rightSlot}</Box>}
    </Box>
  );
};

export default GalaxyTopBar;
