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
        bgcolor: isBlack ? 'rgba(10,10,10,0.9)' : 'rgba(255,255,255,0.1)',
        color: isBlack ? '#ccc' : '#f5f3f0',
        border: '1px solid',
        borderColor: isBlack ? 'rgba(255,255,255,0.1)' : 'rgba(255,255,255,0.12)',
        whiteSpace: 'nowrap',
      }}
    >
      {label}
    </Typography>
  );
};

export default KioskResultBadge;
