import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import Paper from '@mui/material/Paper';
import type { TutorialStep } from '../../types/tutorial';
import { TutorialAPI } from '../../api/tutorialApi';
import AudioPlayer from './AudioPlayer';
import SGFBoard, { type SGFPayload } from './SGFBoard';

interface StepDisplayProps {
  step: TutorialStep;
  onAudioEnded?: () => void;
}

export default function StepDisplay({ step, onAudioEnded }: StepDisplayProps) {
  const imageUrl = step.image_asset ? TutorialAPI.assetUrl(step.image_asset) : null;
  const audioUrl = step.audio_asset ? TutorialAPI.assetUrl(step.audio_asset) : null;
  const figureUrl = step.book_figure_asset ? TutorialAPI.assetUrl(step.book_figure_asset) : null;

  if (step.board_mode === 'sgf') {
    return (
      <Box
        sx={{
          display: 'flex',
          flexDirection: { xs: 'column', sm: 'row' },
          gap: 2,
        }}
      >
        {/* Left panel: book figure + Chinese text */}
        <Box sx={{ flex: '0 0 auto', minWidth: 0, maxWidth: { xs: '100%', sm: 320 }, width: { xs: '100%', sm: 320 } }}>
          {figureUrl && (
            <Box
              component="img"
              src={figureUrl}
              alt="书中图例"
              sx={{ width: '100%', maxWidth: 320, display: 'block', borderRadius: 1, mb: 1 }}
            />
          )}
          {step.book_text && (
            <Typography
              variant="body2"
              sx={{ color: 'text.secondary', fontStyle: 'italic', lineHeight: 1.6, fontSize: '0.8rem' }}
            >
              {step.book_text}
            </Typography>
          )}
        </Box>

        {/* Right panel: SGF board + narration + audio */}
        <Box sx={{ flex: 1, minWidth: 0 }}>
          {!!step.board_payload && (
            <Box sx={{ mb: 2 }}>
              <SGFBoard payload={step.board_payload as SGFPayload} />
            </Box>
          )}
          <Paper variant="outlined" sx={{ p: 2, mb: 2 }}>
            <Typography variant="body1">{step.narration}</Typography>
          </Paper>
          <AudioPlayer src={audioUrl} autoPlay={false} onEnded={onAudioEnded} />
        </Box>
      </Box>
    );
  }

  // board_mode === 'image' (existing behavior)
  return (
    <Box>
      {imageUrl && (
        <Box
          component="img"
          src={imageUrl}
          alt={`Step ${step.order}`}
          sx={{ width: '100%', maxWidth: 480, display: 'block', mx: 'auto', mb: 2, borderRadius: 1 }}
        />
      )}
      <Paper variant="outlined" sx={{ p: 2, mb: 2 }}>
        <Typography variant="body1">{step.narration}</Typography>
      </Paper>
      <AudioPlayer src={audioUrl} autoPlay={false} onEnded={onAudioEnded} />
    </Box>
  );
}
