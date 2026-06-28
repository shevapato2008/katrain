import { useState, useEffect } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  IconButton,
  Slider,
  Button,
  Box,
  Typography,
} from '@mui/material';
import { Close } from '@mui/icons-material';
import SGFBoard, { type SGFPayload } from '../../../components/tutorials/SGFBoard';
import type { TutorialFigure } from '../../../types/tutorial';

export default function FigureDialog({
  figure,
  open,
  onClose,
}: {
  figure: TutorialFigure | null;
  open: boolean;
  onClose: () => void;
}) {
  // Max move number across numeric labels (0 when there are none).
  const maxStep = Math.max(
    0,
    ...Object.values(figure?.board_payload?.labels ?? {})
      .map(Number)
      .filter((n) => !Number.isNaN(n)),
  );

  const [showFull, setShowFull] = useState(false);
  const [step, setStep] = useState(maxStep);

  // Reset replay state whenever a new figure opens.
  useEffect(() => {
    setShowFull(false);
    setStep(maxStep);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [figure, open]);

  if (!figure || !figure.board_payload) return null;

  return (
    <Dialog open={open} onClose={onClose} maxWidth="lg" fullWidth>
      <DialogTitle
        sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', pr: 1 }}
      >
        <span>{figure.figure_label}</span>
        <IconButton onClick={onClose} aria-label="close">
          <Close />
        </IconButton>
      </DialogTitle>

      <DialogContent>
        <Box sx={{ display: 'flex', justifyContent: 'center' }}>
          <SGFBoard
            payload={figure.board_payload as SGFPayload}
            showFullBoard={showFull}
            maxMoveStep={maxStep > 0 ? step : undefined}
            maxWidth={'min(80vw, 560px)'}
          />
        </Box>

        <Box
          sx={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: 2,
            mt: 2,
            flexWrap: 'wrap',
          }}
        >
          <Button variant="outlined" onClick={() => setShowFull((v) => !v)}>
            {showFull ? '局部' : '全盘'}
          </Button>

          {maxStep > 0 && (
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, minWidth: 240, flex: 1 }}>
              <Slider
                min={0}
                max={maxStep}
                value={step}
                onChange={(_, v) => setStep(v as number)}
                aria-label="move-step"
                sx={{ flex: 1 }}
              />
              <Typography variant="body2" sx={{ whiteSpace: 'nowrap' }}>
                手数 {step}/{maxStep}
              </Typography>
            </Box>
          )}
        </Box>
      </DialogContent>
    </Dialog>
  );
}
