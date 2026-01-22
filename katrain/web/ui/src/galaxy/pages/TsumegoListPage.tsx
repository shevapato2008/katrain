import { useState, useEffect } from 'react';
import { Box, Typography, Grid, CircularProgress, IconButton, Chip, Breadcrumbs, Link } from '@mui/material';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import { useNavigate, useParams } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { useSettings } from '../context/SettingsContext';
import ProblemCard from '../components/tsumego/ProblemCard';
import { i18n } from '../../i18n';

interface ProblemSummary {
  id: string;
  level: string;
  category: string;
  hint: string;
  initialBlack: string[];
  initialWhite: string[];
}

interface ProgressData {
  completed: boolean;
  attempts: number;
  lastDuration?: number;
}

const getCategoryName = (cat: string): string => {
  const names: Record<string, string> = {
    'life-death': i18n.t('tsumego:life-death', 'Life & Death'),
    'tesuji': i18n.t('tsumego:tesuji', 'Tesuji'),
    'endgame': i18n.t('tsumego:endgame', 'Endgame')
  };
  return names[cat] || cat;
};

const TsumegoListPage = () => {
  const navigate = useNavigate();
  const { level, category } = useParams<{ level: string; category: string }>();
  const { user, token } = useAuth();
  useSettings();

  const [problems, setProblems] = useState<ProblemSummary[]>([]);
  const [progress, setProgress] = useState<Record<string, ProgressData>>({});
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Load problems
    fetch(`/api/v1/tsumego/levels/${level}/categories/${category}?limit=100`)
      .then(res => res.json())
      .then(data => {
        setProblems(data);
        setLoading(false);
      })
      .catch(err => {
        console.error('Failed to load problems:', err);
        setLoading(false);
      });

    // Load progress from localStorage
    const stored = localStorage.getItem('tsumego_progress');
    if (stored) {
      try {
        setProgress(JSON.parse(stored));
      } catch (e) {
        console.error('Failed to parse stored progress', e);
      }
    }

    // If logged in, also fetch from server
    if (user && token) {
      fetch('/api/v1/tsumego/progress', {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      })
        .then(res => res.json())
        .then(data => {
          setProgress(prev => ({ ...prev, ...data }));
        })
        .catch(console.error);
    }
  }, [level, category, user, token]);

  const completedCount = problems.filter(p => progress[p.id]?.completed).length;

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '50vh' }}>
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Box sx={{ p: 4, maxWidth: 1400, mx: 'auto' }}>
      {/* Breadcrumbs */}
      <Box sx={{ display: 'flex', alignItems: 'center', mb: 3 }}>
        <IconButton onClick={() => navigate(`/galaxy/tsumego/${level}`)} sx={{ mr: 1 }}>
          <ArrowBackIcon />
        </IconButton>
        <Breadcrumbs>
          <Link
            component="button"
            variant="body1"
            onClick={() => navigate('/galaxy/tsumego')}
            sx={{ cursor: 'pointer' }}
          >
            {i18n.t('Tsumego', '死活题')}
          </Link>
          <Link
            component="button"
            variant="body1"
            onClick={() => navigate(`/galaxy/tsumego/${level}`)}
            sx={{ cursor: 'pointer' }}
          >
            {level?.toUpperCase()}
          </Link>
          <Typography color="text.primary">{getCategoryName(category || '')}</Typography>
        </Breadcrumbs>
      </Box>

      <Box sx={{ display: 'flex', alignItems: 'center', mb: 4 }}>
        <Box sx={{ flexGrow: 1 }}>
          <Typography variant="h4" sx={{ fontWeight: 'bold' }}>
            {level?.toUpperCase()} - {getCategoryName(category || '')}
          </Typography>
          <Typography variant="subtitle1" color="text.secondary">
            {i18n.t('tsumego:solveProblems', '点击题目开始练习')}
          </Typography>
        </Box>
        <Chip
          label={`${completedCount}/${problems.length}`}
          color={completedCount === problems.length ? 'success' : 'default'}
          sx={{ fontSize: '1rem', px: 1 }}
        />
      </Box>

      <Grid container spacing={2}>
        {problems.map((problem, index) => (
          <Grid size={{ xs: 6, sm: 4, md: 3, lg: 2 }} key={problem.id}>
            <ProblemCard
              index={index}
              initialBlack={problem.initialBlack}
              initialWhite={problem.initialWhite}
              progress={progress[problem.id]}
              onClick={() => navigate(`/galaxy/tsumego/problem/${problem.id}`)}
            />
          </Grid>
        ))}
      </Grid>
    </Box>
  );
};

export default TsumegoListPage;
