import React, { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import List from '@mui/material/List';
import ListItem from '@mui/material/ListItem';
import ListItemButton from '@mui/material/ListItemButton';
import ListItemText from '@mui/material/ListItemText';
import Divider from '@mui/material/Divider';
import CircularProgress from '@mui/material/CircularProgress';
import { TutorialAPI } from '../../api/tutorialApi';
import type { TutorialTopic } from '../../types/tutorial';

export default function TutorialTopicsPage() {
  const { categorySlug } = useParams<{ categorySlug: string }>();
  const navigate = useNavigate();
  const [topics, setTopics] = useState<TutorialTopic[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!categorySlug) return;
    TutorialAPI.getTopics(categorySlug)
      .then(setTopics)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [categorySlug]);

  if (loading) return <Box display="flex" justifyContent="center" p={4}><CircularProgress /></Box>;

  return (
    <Box p={3}>
      <Typography variant="h6" gutterBottom>选择主题</Typography>
      <List>
        {topics.map((topic, i) => (
          <React.Fragment key={topic.id}>
            {i > 0 && <Divider />}
            <ListItem disablePadding>
              <ListItemButton onClick={() => navigate(`/galaxy/tutorials/topic/${topic.id}`)}>
                <ListItemText primary={topic.title} secondary={topic.summary} />
              </ListItemButton>
            </ListItem>
          </React.Fragment>
        ))}
        {topics.length === 0 && <Typography color="text.secondary">该分类下暂无主题</Typography>}
      </List>
    </Box>
  );
}
