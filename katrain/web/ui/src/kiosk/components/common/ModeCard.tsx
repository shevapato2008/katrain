import { Box, Typography, ButtonBase } from '@mui/material';
import { useNavigate } from 'react-router-dom';

interface ModeCardProps {
  title: string;
  subtitle: string;
  icon: React.ReactNode;
  to: string;
  variant?: 'default' | 'primary';
}

// Compact HORIZONTAL card, matching the 7" artifact's `.opt` (play-hub-states.html §01):
// a 44×44 icon tile on the left, title + 2-line subtitle on the right — ~70px tall.
// Deliberately NOT a tall vertical icon-on-top card: on the 1024×600 kiosk the whole
// 对弈 hub (greeting + resume + two 3-card rows) must fit without scrolling, and the
// oversized vertical cards were the "太大了很丑" problem this replaces.
const ModeCard = ({ title, subtitle, icon, to, variant = 'default' }: ModeCardProps) => {
  const navigate = useNavigate();
  const isPrimary = variant === 'primary';

  return (
    <ButtonBase
      onClick={() => navigate(to)}
      data-testid={isPrimary ? 'mode-card-primary' : undefined}
      sx={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'flex-start',
        textAlign: 'left',
        gap: 1.5, // 12px
        width: '100%',
        p: '13px 15px',
        borderRadius: '15px',
        border: '1px solid',
        borderColor: isPrimary ? 'primary.dark' : 'divider',
        bgcolor: isPrimary ? 'transparent' : 'background.paper',
        backgroundImage: isPrimary ? 'linear-gradient(135deg,#2a5344,#1c2f28)' : 'none',
        transition: 'transform 130ms cubic-bezier(.2,.7,.3,1), border-color 130ms',
        '&:hover': { borderColor: 'primary.main' },
        '&:active': { transform: 'scale(0.97)', borderColor: 'primary.main' },
        '&:focus-visible': { outline: '2px solid', outlineColor: 'primary.main', outlineOffset: 2 },
        '@media (prefers-reduced-motion: reduce)': {
          transition: 'none',
          '&:active': { transform: 'none' },
        },
      }}
    >
      <Box
        sx={{
          width: 44,
          height: 44,
          flexShrink: 0,
          borderRadius: '12px',
          display: 'grid',
          placeItems: 'center',
          fontSize: 24,
          bgcolor: isPrimary ? 'rgba(88,181,122,0.16)' : 'var(--raise2)',
          border: '1px solid',
          borderColor: isPrimary ? 'primary.dark' : 'divider',
          color: isPrimary ? 'primary.main' : 'text.secondary',
          '& svg': { fontSize: 'inherit' },
        }}
      >
        {icon}
      </Box>
      <Box sx={{ minWidth: 0 }}>
        <Typography sx={{ fontSize: 16, fontWeight: 600, color: 'text.primary', lineHeight: 1.2 }}>
          {title}
        </Typography>
        <Typography
          sx={{
            fontSize: 11,
            color: isPrimary ? 'text.primary' : 'text.secondary',
            mt: '2px',
            lineHeight: 1.3,
            display: '-webkit-box',
            WebkitLineClamp: 2,
            WebkitBoxOrient: 'vertical',
            overflow: 'hidden',
          }}
        >
          {subtitle}
        </Typography>
      </Box>
    </ButtonBase>
  );
};

export default ModeCard;
