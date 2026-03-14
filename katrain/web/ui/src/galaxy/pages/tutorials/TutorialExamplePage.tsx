import React, { useCallback, useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import Button from '@mui/material/Button';
import LinearProgress from '@mui/material/LinearProgress';
import Chip from '@mui/material/Chip';
import CircularProgress from '@mui/material/CircularProgress';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import ArrowForwardIcon from '@mui/icons-material/ArrowForward';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import { TutorialAPI } from '../../api/tutorialApi';
import type { TutorialExample } from '../../types/tutorial';
import StepDisplay from '../../components/tutorials/StepDisplay';

export default function TutorialExamplePage() {
  const { exampleId } = useParams<{ exampleId: string }>();
  const [example, setExample] = useState<TutorialExample | null>(null);
  const [currentStepIndex, setCurrentStepIndex] = useState(0);
  const [completed, setCompleted] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!exampleId) return;
    TutorialAPI.getExample(exampleId)
      .then(setExample)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [exampleId]);

  const currentStep = example?.steps[currentStepIndex] ?? null;
  const isLast = example ? currentStepIndex === example.steps.length - 1 : false;

  const saveProgress = useCallback((stepIdx: number, done: boolean) => {
    if (!example) return;
    TutorialAPI.updateProgress(example.id, {
      topic_id: example.topic_id,
      last_step_id: example.steps[stepIdx].id,
      completed: done,
    }).catch(console.error);
  }, [example]);

  const goNext = () => {
    if (!example) return;
    if (isLast) {
      setCompleted(true);
      saveProgress(currentStepIndex, true);
    } else {
      const next = currentStepIndex + 1;
      setCurrentStepIndex(next);
      saveProgress(next, false);
    }
  };

  const goPrev = () => {
    if (currentStepIndex > 0) setCurrentStepIndex(i => i - 1);
  };

  if (loading) return <Box display="flex" justifyContent="center" p={4}><CircularProgress /></Box>;
  if (!example) return <Typography p={3} color="error">例子未找到</Typography>;

  const progressPct = ((currentStepIndex + 1) / example.steps.length) * 100;

  return (
    <Box p={3} maxWidth={640} mx="auto">
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={1}>
        <Typography variant="h6">{example.title}</Typography>
        {completed && <Chip icon={<CheckCircleIcon />} label="已完成" color="success" size="small" />}
      </Box>
      <LinearProgress variant="determinate" value={progressPct} sx={{ mb: 2 }} />
      <Typography variant="caption" color="text.secondary" mb={2} display="block">
        第 {currentStepIndex + 1} / {example.steps.length} 步
      </Typography>
      {currentStep && <StepDisplay step={currentStep} onAudioEnded={isLast ? undefined : goNext} />}
      <Box display="flex" gap={2} mt={3}>
        <Button startIcon={<ArrowBackIcon />} onClick={goPrev} disabled={currentStepIndex === 0} variant="outlined">
          上一步
        </Button>
        <Button
          endIcon={isLast ? <CheckCircleIcon /> : <ArrowForwardIcon />}
          onClick={goNext}
          variant="contained"
          color={isLast ? 'success' : 'primary'}
        >
          {isLast ? '完成' : '下一步'}
        </Button>
      </Box>
    </Box>
  );
}
