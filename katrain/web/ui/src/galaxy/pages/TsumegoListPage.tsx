import { useState, useEffect } from 'react';
import { Box, Typography, Grid, CircularProgress, Chip } from '@mui/material';
import { useNavigate, useParams } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { useSettings } from '../../context/SettingsContext';
import { useTranslation } from '../../hooks/useTranslation';
import ContentPageHeader from '../components/layout/ContentPageHeader';
import ProblemCard from '../components/tsumego/ProblemCard';

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

const UNIT_SIZE = 20;

const TsumegoListPage = () => {
  const navigate = useNavigate();
  const { level, category, unit } = useParams<{ level: string; category: string; unit: string }>();
  const { user, token } = useAuth();
  useSettings();
  const { t } = useTranslation();

  // Get translated category name
  const getCategoryName = (cat: string): string => {
    return t(`tsumego:${cat}`) || cat;
  };

  // Helper function for string interpolation
  const interpolate = (template: string, values: Record<string, string | number>): string => {
    return template.replace(/\{(\w+)\}/g, (_, key) => String(values[key] ?? key));
  };

  const [problems, setProblems] = useState<ProblemSummary[]>([]);
  const [progress, setProgress] = useState<Record<string, ProgressData>>({});
  const [loading, setLoading] = useState(true);

  // Parse unit number
  const unitNumber = parseInt(unit || '1', 10);
  const offset = (unitNumber - 1) * UNIT_SIZE;

  useEffect(() => {
    // Load problems for this unit
    fetch(`/api/v1/tsumego/levels/${level}/categories/${category}?offset=${offset}&limit=${UNIT_SIZE}`)
      .then(res => {
        if (!res.ok) {
          throw new Error(`API error: ${res.status}`);
        }
        return res.json();
      })
      .then(data => {
        if (Array.isArray(data)) {
          setProblems(data);
        } else {
          console.error('Unexpected data format:', data);
          setProblems([]);
        }
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
  }, [level, category, unit, offset, user, token]);

  const completedCount = problems.filter(p => progress[p.id]?.completed).length;
  const startProblem = offset + 1;
  const endProblem = offset + problems.length;

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '50vh' }}>
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Box sx={{ p: 4, maxWidth: 1400, mx: 'auto' }}>
      {/* 面包屑四级 → 一个返回键（spec §2.4）。完成度 Chip 是**单个**状态件，
          进页头最右的 status 槽 —— §2.4 允许「状态放最右」，禁的是往页头堆多个 chip。 */}
      <ContentPageHeader
        title={`${t('tsumego:unit')} ${unitNumber}`}
        parentLabel={getCategoryName(category || '')}
        parentTo={`/galaxy/tsumego/${level}/${category}`}
        status={
          <Chip
            label={`${completedCount}/${problems.length}`}
            color={completedCount === problems.length ? 'success' : 'default'}
            sx={{ fontSize: '1rem', px: 1 }}
          />
        }
      />
      <Typography variant="subtitle1" color="text.secondary" sx={{ mt: 1, mb: 4 }}>
        {interpolate(t('tsumego:problemRange'), { start: startProblem, end: endProblem })}
      </Typography>

      <Grid container spacing={2}>
        {problems.map((problem, index) => (
          <Grid size={{ xs: 6, sm: 4, md: 3, lg: 2 }} key={problem.id}>
            <ProblemCard
              index={offset + index}
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
