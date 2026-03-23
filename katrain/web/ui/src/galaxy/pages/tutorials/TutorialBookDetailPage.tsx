import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import CircularProgress from '@mui/material/CircularProgress';
import Alert from '@mui/material/Alert';
import Button from '@mui/material/Button';
import Accordion from '@mui/material/Accordion';
import AccordionSummary from '@mui/material/AccordionSummary';
import AccordionDetails from '@mui/material/AccordionDetails';
import List from '@mui/material/List';
import ListItemButton from '@mui/material/ListItemButton';
import ListItemText from '@mui/material/ListItemText';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import { TutorialAPI } from '../../api/tutorialApi';
import type { TutorialBookDetail, TutorialSection } from '../../types/tutorial';

export default function TutorialBookDetailPage() {
  const { bookId } = useParams<{ bookId: string }>();
  const navigate = useNavigate();
  const [book, setBook] = useState<TutorialBookDetail | null>(null);
  const [sections, setSections] = useState<Record<number, TutorialSection[]>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = () => {
    if (!bookId) return;
    setLoading(true);
    setError(null);
    TutorialAPI.getBook(Number(bookId))
      .then(async (b) => {
        setBook(b);
        // Load sections for each chapter
        const sectionMap: Record<number, TutorialSection[]> = {};
        await Promise.all(
          b.chapters.map(async (ch) => {
            const secs = await TutorialAPI.getSections(ch.id);
            sectionMap[ch.id] = secs;
          })
        );
        setSections(sectionMap);
      })
      .catch(e => setError(e instanceof Error ? e.message : '加载失败'))
      .finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, [bookId]);

  if (loading) return <Box display="flex" justifyContent="center" p={4}><CircularProgress /></Box>;
  if (error) return <Box p={3}><Alert severity="error">{error} <Button onClick={load}>重试</Button></Alert></Box>;
  if (!book) return <Box p={3}><Typography>书籍不存在</Typography></Box>;

  return (
    <Box p={3}>
      <Button size="small" onClick={() => navigate(`/galaxy/tutorials/${book.category}`)} sx={{ mb: 1 }}>← 返回</Button>
      <Typography variant="h5" gutterBottom>{book.title}</Typography>
      {book.author && <Typography variant="body2" color="text.secondary" gutterBottom>{book.author}</Typography>}

      {book.chapters.map(ch => (
        <Accordion key={ch.id} defaultExpanded={book.chapters.length <= 3}>
          <AccordionSummary expandIcon={<ExpandMoreIcon />}>
            <Typography>{ch.chapter_number} {ch.title}</Typography>
            <Typography variant="caption" color="text.secondary" sx={{ ml: 2 }}>
              {ch.section_count} 节
            </Typography>
          </AccordionSummary>
          <AccordionDetails sx={{ p: 0 }}>
            <List dense disablePadding>
              {(sections[ch.id] ?? []).map(sec => (
                <ListItemButton
                  key={sec.id}
                  onClick={() => navigate(`/galaxy/tutorials/section/${sec.id}`)}
                >
                  <ListItemText
                    primary={`${sec.section_number}. ${sec.title}`}
                    secondary={`${sec.figure_count} 个变化图`}
                  />
                </ListItemButton>
              ))}
            </List>
          </AccordionDetails>
        </Accordion>
      ))}
    </Box>
  );
}
