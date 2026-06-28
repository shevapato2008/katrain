import { Box, Typography } from '@mui/material';
import SGFBoard, { type SGFPayload } from '../../../components/tutorials/SGFBoard';
import type { TutorialFigure } from '../../../types/tutorial';

/**
 * Presentational thumbnail of a single tutorial board diagram.
 * The parent injects `onClick` (e.g. to open a detail dialog); this component
 * holds no state, performs no fetching, and renders no dialog.
 */
export default function FigureThumb({ figure, onClick }: { figure: TutorialFigure; onClick: () => void }) {
  if (figure.board_payload === null) return null;

  const handleKeyDown = (e: React.KeyboardEvent<HTMLDivElement>) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      onClick();
    }
  };

  return (
    <Box
      role="button"
      tabIndex={0}
      onClick={onClick}
      onKeyDown={handleKeyDown}
      sx={{
        display: 'inline-flex',
        flexDirection: 'column',
        alignItems: 'center',
        gap: 0.5,
        minWidth: 48,
        minHeight: 48,
        p: 1,
        borderRadius: 2,
        cursor: 'pointer',
        transition: 'background-color 0.15s ease, transform 0.05s ease',
        '&:hover': { bgcolor: 'action.hover' },
        '&:active': { transform: 'scale(0.97)' },
      }}
    >
      <SGFBoard payload={figure.board_payload as SGFPayload} showFullBoard={false} maxWidth={180} />
      <Typography variant="caption" align="center">
        {figure.figure_label}
      </Typography>
    </Box>
  );
}
