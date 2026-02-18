import { useState, useEffect } from 'react';
import { Box, Typography, Card, CardActionArea, CircularProgress, IconButton, Breadcrumbs, Link } from '@mui/material';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import { useNavigate, useParams } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { useSettings } from '../context/SettingsContext';
import { useTranslation } from '../../hooks/useTranslation';

interface ProgressData {
  completed: boolean;
}

const UNIT_SIZE = 20;

// Calculate progress dots (5 dots representing progress percentage)
const ProgressDots = ({ completed, total }: { completed: number; total: number }) => {
  const percentage = total > 0 ? completed / total : 0;
  let filledDots = 0;

  if (percentage === 0) {
    filledDots = 0;
  } else if (percentage <= 0.2) {
    filledDots = 1;
  } else if (percentage <= 0.4) {
    filledDots = 2;
  } else if (percentage <= 0.6) {
    filledDots = 3;
  } else if (percentage <= 0.8) {
    filledDots = 4;
  } else {
    filledDots = 5;
  }

  return (
    <Box sx={{ display: 'flex', gap: 0.5 }}>
      {[0, 1, 2, 3, 4].map(i => (
        <Box
          key={i}
          sx={{
            width: 8,
            height: 8,
            borderRadius: '50%',
            bgcolor: i < filledDots ? '#4caf50' : 'rgba(255,255,255,0.2)'
          }}
        />
      ))}
    </Box>
  );
};

const TsumegoUnitsPage = () => {
  const navigate = useNavigate();
  const { level, category } = useParams<{ level: string; category: string }>();
  const { user, token } = useAuth();
  useSettings();
  const { t } = useTranslation();

  const [problemIds, setProblemIds] = useState<string[]>([]);
  const [progress, setProgress] = useState<Record<string, ProgressData>>({});
  const [loading, setLoading] = useState(true);

  // Get translated category name
  const getCategoryName = (cat: string): string => {
    return t(`tsumego:${cat}`) || cat;
  };

  // Helper function for string interpolation
  const interpolate = (template: string, values: Record<string, string | number>): string => {
    return template.replace(/\{(\w+)\}/g, (_, key) => String(values[key] ?? key));
  };

  useEffect(() => {
    // Load all problem IDs for this category
    fetch(`/api/v1/tsumego/levels/${level}/categories/${category}?limit=1000`)
      .then(res => {
        if (!res.ok) {
          throw new Error(`API error: ${res.status}`);
        }
        return res.json();
      })
      .then(data => {
        if (Array.isArray(data)) {
          setProblemIds(data.map((p: { id: string }) => p.id));
        } else {
          console.error('Unexpected data format:', data);
          setProblemIds([]);
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
  }, [level, category, user, token]);

  // Calculate units
  const totalProblems = problemIds.length;
  const totalUnits = Math.ceil(totalProblems / UNIT_SIZE);

  const units = Array.from({ length: totalUnits }, (_, i) => {
    const start = i * UNIT_SIZE;
    const end = Math.min(start + UNIT_SIZE, totalProblems);
    const unitProblemIds = problemIds.slice(start, end);
    const completedInUnit = unitProblemIds.filter(id => progress[id]?.completed).length;

    return {
      unitNumber: i + 1,
      startProblem: start + 1,
      endProblem: end,
      total: end - start,
      completed: completedInUnit
    };
  });

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '50vh' }}>
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Box sx={{ p: 4, pl: 6 }}>
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
            {t('Tsumego')}
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

      <Typography variant="h4" sx={{ mb: 1, fontWeight: 'bold' }}>
        {level?.toUpperCase()} {getCategoryName(category || '')} - {t('tsumego:selectUnit')}
      </Typography>
      <Typography variant="subtitle1" color="text.secondary" sx={{ mb: 4 }}>
        {interpolate(t('tsumego:unitDesc'), { total: totalProblems, units: totalUnits })}
      </Typography>

      {/* Unit cards — row-first grid: 1,2,3 then 4,5,6 etc. */}
      <Box
        sx={{
          display: 'grid',
          gap: 1.5,
          gridTemplateColumns: {
            xs: '1fr',
            sm: 'repeat(2, 1fr)',
            md: 'repeat(3, 1fr)',
          },
        }}
      >
        {units.map((unit) => (
          <Card
            key={unit.unitNumber}
            sx={{
              borderRadius: 2.5,
              bgcolor: 'rgba(255,255,255,0.05)',
              transition: 'transform 0.2s, box-shadow 0.2s',
              '&:hover': {
                transform: 'translateX(4px)',
                boxShadow: 4
              }
            }}
          >
            <CardActionArea onClick={() => navigate(`/galaxy/tsumego/${level}/${category}/${unit.unitNumber}`)}>
              <Box
                sx={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  px: 2.5,
                  py: 1.5,
                }}
              >
                {/* Left side: unit info */}
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                  <Typography variant="subtitle1" sx={{ fontWeight: 'bold', minWidth: 56 }}>
                    {t('tsumego:unit')} {unit.unitNumber}
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    {interpolate(t('tsumego:problemRange'), { start: unit.startProblem, end: unit.endProblem })}
                  </Typography>
                </Box>

                {/* Right side: progress */}
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
                  <ProgressDots completed={unit.completed} total={unit.total} />
                  <Typography
                    variant="body2"
                    sx={{
                      minWidth: 42,
                      textAlign: 'right',
                      fontSize: '0.82rem',
                      color: unit.completed === unit.total ? '#4caf50' : 'text.secondary'
                    }}
                  >
                    {unit.completed}/{unit.total}
                  </Typography>
                </Box>
              </Box>
            </CardActionArea>
          </Card>
        ))}
      </Box>
    </Box>
  );
};

export default TsumegoUnitsPage;
