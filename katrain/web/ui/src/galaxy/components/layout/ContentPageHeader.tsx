import ArrowBackRoundedIcon from '@mui/icons-material/ArrowBackRounded';
import { Box, Button, Typography } from '@mui/material';
import { useGameNavigation } from '../../context/GameNavigationContext';

interface ContentPageHeaderProps {
  title: string;
  parentLabel: string;
  parentTo: string;
}

const ContentPageHeader = ({ title, parentLabel, parentTo }: ContentPageHeaderProps) => {
  const { requestNavigation } = useGameNavigation();

  return (
    <Box sx={{ minHeight: 48, display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 2 }}>
      <Typography component="h1" variant="h4" sx={{ fontWeight: 800, letterSpacing: '-0.02em' }}>
        {title}
      </Typography>
      <Button
        aria-label={`返回${parentLabel}`}
        startIcon={<ArrowBackRoundedIcon />}
        onClick={() => requestNavigation(parentTo)}
        variant="outlined"
        color="inherit"
        sx={{ minHeight: 40, borderColor: 'divider', color: 'text.secondary', px: 2, flex: 'none' }}
      >
        {parentLabel}
      </Button>
    </Box>
  );
};

export default ContentPageHeader;
