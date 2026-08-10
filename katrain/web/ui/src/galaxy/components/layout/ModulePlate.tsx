import type { ReactNode } from 'react';
import { Box, Button, IconButton, Typography } from '@mui/material';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import { useTranslation } from '../../../hooks/useTranslation';
import { useGameNavigation } from '../../context/GameNavigationContext';

interface ModulePlateProps {
  title: ReactNode;
  subtitle?: ReactNode;
  status?: ReactNode;
  backTo: string;
  showBack?: boolean;
  backLabel?: string;
}

const ModulePlate = ({ title, subtitle, status, backTo, showBack = true, backLabel }: ModulePlateProps) => {
  const { t } = useTranslation();
  const { requestNavigation } = useGameNavigation();

  return (
    <Box
      data-testid="module-plate"
      sx={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: backLabel ? 'space-between' : 'flex-start',
        gap: 1.5,
        minWidth: 0,
        minHeight: 52,
        px: backLabel ? 2 : 0,
      }}
    >
      {showBack && !backLabel && (
        <IconButton
          aria-label={t('Back', 'Back')}
          onClick={() => requestNavigation(backTo)}
          style={{ width: 40, height: 40 }}
          sx={{ flex: '0 0 40px' }}
        >
          <ArrowBackIcon />
        </IconButton>
      )}
      <Box sx={{ minWidth: 0, flex: 1 }}>
        <Typography variant="h6" component="h1" noWrap>{title}</Typography>
        {subtitle != null && <Typography variant="body2" color="text.secondary" noWrap>{subtitle}</Typography>}
      </Box>
      {status != null && <Box sx={{ flex: 'none' }}>{status}</Box>}
      {showBack && backLabel && (
        <Button
          aria-label={`返回${backLabel}`}
          onClick={() => requestNavigation(backTo)}
          startIcon={<ArrowBackIcon />}
          sx={{ flex: 'none', minHeight: 44, whiteSpace: 'nowrap' }}
        >
          {backLabel}
        </Button>
      )}
    </Box>
  );
};

export default ModulePlate;
