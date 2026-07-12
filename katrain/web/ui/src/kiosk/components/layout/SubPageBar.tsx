import { Box, Typography, Button } from '@mui/material';
import { ArrowBack } from '@mui/icons-material';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from '../../../hooks/useTranslation';

interface SubPageBarProps {
  title: string;
  onBack?: () => void;
  to?: string;
  right?: React.ReactNode;
}

// Standard back bar for all non-L1 kiosk pages. The Dock is hidden on these
// routes (KioskLayout, Task 2), so this is the only way back up the stack.
const SubPageBar = ({ title, onBack, to, right }: SubPageBarProps) => {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const handleBack = () => {
    if (onBack) onBack();
    else if (to) navigate(to);
    else navigate(-1);
  };
  return (
    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, px: 2.5, py: 1.25,
      borderBottom: '1px solid', borderColor: 'divider', flexShrink: 0, minHeight: 52 }}>
      <Button onClick={handleBack} startIcon={<ArrowBack />} aria-label={t('Back', '返回')}
        sx={{ minHeight: 40, px: 1.75, color: 'text.primary', bgcolor: 'var(--raise2)',
          border: '1px solid', borderColor: 'divider' }}>
        {t('Back', '返回')}
      </Button>
      <Typography sx={{ fontSize: 17, fontWeight: 600, color: 'text.primary',
        overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{title}</Typography>
      {right && <Box sx={{ ml: 'auto', display: 'flex', alignItems: 'center', gap: 1 }}>{right}</Box>}
    </Box>
  );
};

export default SubPageBar;
