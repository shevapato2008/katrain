import React, { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import Card from '@mui/material/Card';
import CardContent from '@mui/material/CardContent';
import CardActionArea from '@mui/material/CardActionArea';
import CircularProgress from '@mui/material/CircularProgress';
import { TutorialAPI } from '../../api/tutorialApi';
import type { TutorialExample, TutorialTopic } from '../../types/tutorial';

export default function TutorialTopicDetailPage() {
  const { topicId } = useParams<{ topicId: string }>();
  const navigate = useNavigate();
  const [topic, setTopic] = useState<TutorialTopic | null>(null);
  const [examples, setExamples] = useState<TutorialExample[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!topicId) return;
    Promise.all([
      TutorialAPI.getTopic(topicId),
      TutorialAPI.getTopicExamples(topicId),
    ])
      .then(([t, exs]) => { setTopic(t); setExamples(exs); })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [topicId]);

  if (loading) return <Box display="flex" justifyContent="center" p={4}><CircularProgress /></Box>;
  if (!topic) return <Typography p={3} color="error">主题未找到</Typography>;

  return (
    <Box p={3}>
      <Typography variant="h6" gutterBottom>{topic.title}</Typography>
      <Typography variant="body2" color="text.secondary" mb={3}>{topic.summary}</Typography>
      <Typography variant="subtitle2" gutterBottom>例题</Typography>
      {examples.map(ex => (
        <Card key={ex.id} sx={{ mb: 2 }}>
          <CardActionArea onClick={() => navigate(`/galaxy/tutorials/example/${ex.id}`)}>
            <CardContent>
              <Typography variant="body1">{ex.title}</Typography>
              <Typography variant="body2" color="text.secondary">{ex.summary}</Typography>
              <Typography variant="caption" color="text.secondary" mt={1} display="block">
                {ex.step_count} 步
              </Typography>
            </CardContent>
          </CardActionArea>
        </Card>
      ))}
      {examples.length === 0 && <Typography color="text.secondary">该主题下暂无例题</Typography>}
    </Box>
  );
}
