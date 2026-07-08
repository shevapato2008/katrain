import { Typography } from '@mui/material';
import { useTranslation } from '../../../hooks/useTranslation';
import { translateResult } from '../../../utils/resultTranslation';

interface KioskResultBadgeProps {
  result: string;
  rules?: string | null;
}

const KioskResultBadge = ({ result, rules }: KioskResultBadgeProps) => {
  const { t } = useTranslation();
  const label = translateResult(result, t, rules);
  const isBlack = result.startsWith('B') || result.startsWith('黑');

  return (
    <Typography
      component="span"
      data-testid="result-badge"
      sx={{
        display: 'inline-block',
        fontSize: '0.65rem',
        fontWeight: 700,
        lineHeight: 1,
        px: 0.7,
        py: 0.3,
        borderRadius: '4px',
        fontFamily: "'IBM Plex Mono', monospace",
        bgcolor: isBlack ? '#0a0a0a' : 'var(--raise2)',
        color: 'text.primary',
        border: '1px solid',
        borderColor: 'divider',
        whiteSpace: 'nowrap',
      }}
    >
      {label}
    </Typography>
  );
};

export default KioskResultBadge;
