import React from 'react';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import Paper from '@mui/material/Paper';
import type { TutorialStep } from '../../types/tutorial';
import { TutorialAPI } from '../../api/tutorialApi';
import AudioPlayer from './AudioPlayer';

interface StepDisplayProps {
  step: TutorialStep;
  onAudioEnded?: () => void;
}

export default function StepDisplay({ step, onAudioEnded }: StepDisplayProps) {
  const imageUrl = step.image_asset ? TutorialAPI.assetUrl(step.image_asset) : null;
  const audioUrl = step.audio_asset ? TutorialAPI.assetUrl(step.audio_asset) : null;

  return (
    <Box>
      {step.board_mode === 'image' && imageUrl && (
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
