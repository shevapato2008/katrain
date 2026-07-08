import { Box, Typography, ButtonBase } from '@mui/material';
import { useNavigate } from 'react-router-dom';

interface ModeCardProps {
  title: string;
  subtitle: string;
  icon: React.ReactNode;
  to: string;
  variant?: 'default' | 'primary';
}

// Fixed line-height (em) for the subtitle — used both as the Typography's
// lineHeight and to compute the reserved 2-line block, so a 1-line subtitle
// always reserves the same vertical space as a 2-line one and every
// ModeCard ends up the same height regardless of copy or which grid it's in.
const SUBTITLE_LINE_HEIGHT = 1.35;

const ModeCard = ({ title, subtitle, icon, to, variant = 'default' }: ModeCardProps) => {
  const navigate = useNavigate();
  const isPrimary = variant === 'primary';

  return (
    <ButtonBase
      onClick={() => navigate(to)}
      data-testid={isPrimary ? 'mode-card-primary' : undefined}
      sx={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        gap: 1.25,
        flex: 1,
        minHeight: 132,
        borderRadius: 3,
        bgcolor: isPrimary ? 'primary.dark' : 'background.paper',
        border: '1px solid',
        borderColor: isPrimary ? 'primary.main' : 'divider',
        p: 2,
        transition: 'transform 100ms ease-out, border-color 200ms',
        '&:hover': {
          borderColor: 'primary.main',
        },
        '&:active': {
          transform: 'scale(0.96)',
          borderColor: 'primary.main',
        },
        '&:focus-visible': {
          outline: '2px solid',
          outlineColor: 'primary.main',
          outlineOffset: 2,
        },
        '@media (prefers-reduced-motion: reduce)': {
          transition: 'none',
          '&:active': { transform: 'none' },
        },
      }}
    >
      <Box sx={{ fontSize: 40, color: 'primary.main', display: 'flex' }}>{icon}</Box>
      <Typography variant="h6" sx={{ color: 'text.primary' }}>{title}</Typography>
      <Typography
        variant="body2"
        sx={{
          color: isPrimary ? 'text.primary' : 'text.secondary',
          textAlign: 'center',
          lineHeight: SUBTITLE_LINE_HEIGHT,
          minHeight: `${SUBTITLE_LINE_HEIGHT * 2}em`,
          display: '-webkit-box',
          WebkitLineClamp: 2,
          WebkitBoxOrient: 'vertical',
          overflow: 'hidden',
        }}
      >
        {subtitle}
      </Typography>
    </ButtonBase>
  );
};

export default ModeCard;
