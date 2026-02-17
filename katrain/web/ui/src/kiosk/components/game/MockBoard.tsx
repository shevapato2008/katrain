import { Box, Typography } from '@mui/material';

const MockBoard = ({ moveNumber = 0 }: { moveNumber?: number }) => (
  <Box
    sx={{
      aspectRatio: '1',
      height: '100%',
      bgcolor: '#8b7355',
      borderRadius: 1,
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      position: 'relative',
      overflow: 'hidden',
      flexShrink: 0,
    }}
  >
    <Box
      sx={{
        position: 'absolute',
        inset: '8%',
        backgroundImage:
          'repeating-linear-gradient(0deg, transparent, transparent calc(100%/18 - 1px), rgba(0,0,0,0.3) calc(100%/18 - 1px), rgba(0,0,0,0.3) calc(100%/18)), repeating-linear-gradient(90deg, transparent, transparent calc(100%/18 - 1px), rgba(0,0,0,0.3) calc(100%/18 - 1px), rgba(0,0,0,0.3) calc(100%/18))',
      }}
    />
    <Typography variant="caption" sx={{ color: 'rgba(0,0,0,0.4)', zIndex: 1 }}>
      棋盘 · 第{moveNumber}手
    </Typography>
  </Box>
);

export default MockBoard;
