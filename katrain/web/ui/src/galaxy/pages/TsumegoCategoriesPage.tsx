import { useState, useEffect } from 'react';
import { Box, Typography, Card, CardActionArea, CircularProgress, IconButton, Breadcrumbs, Link } from '@mui/material';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import { useNavigate, useParams } from 'react-router-dom';
import { useSettings } from '../../context/SettingsContext';
import { useTranslation } from '../../hooks/useTranslation';

interface CategoryInfo {
  category: string;
  name: string;
  count: number;
}

const CATEGORY_ICONS: Record<string, string> = {
  'life-death': '⚔️',
  'tesuji': '✨',
  'endgame': '🎯'
};

const TsumegoCategoriesPage = () => {
  const navigate = useNavigate();
  const { level } = useParams<{ level: string }>();
  useSettings();
  const { t } = useTranslation();
  const [categories, setCategories] = useState<CategoryInfo[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`/api/v1/tsumego/levels/${level}/categories`)
      .then(res => res.json())
      .then(data => {
        setCategories(data);
        setLoading(false);
      })
      .catch(err => {
        console.error('Failed to load categories:', err);
        setLoading(false);
      });
  }, [level]);

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
        <IconButton onClick={() => navigate('/galaxy/tsumego')} sx={{ mr: 1 }}>
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
          <Typography color="text.primary">{level?.toUpperCase()}</Typography>
        </Breadcrumbs>
      </Box>

      <Typography variant="h4" sx={{ mb: 1, fontWeight: 'bold' }}>
        {level?.toUpperCase()} - {t('tsumego:selectCategory')}
      </Typography>
      <Typography variant="subtitle1" color="text.secondary" sx={{ mb: 4 }}>
        {t('tsumego:categoryDesc')}
      </Typography>

      {/* Vertical card list */}
      <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
        {categories.map((cat) => (
          <Card
            key={cat.category}
            sx={{
              maxWidth: 480,
              borderRadius: 3,
              bgcolor: 'rgba(255,255,255,0.05)',
              transition: 'transform 0.2s, box-shadow 0.2s',
              '&:hover': {
                transform: 'translateX(4px)',
                boxShadow: 4
              }
            }}
          >
            <CardActionArea onClick={() => navigate(`/galaxy/tsumego/${level}/${cat.category}`)}>
              <Box
                sx={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 2,
                  px: 3,
                  py: 2,
                  height: 72
                }}
              >
                {/* Icon */}
                <Typography
                  sx={{
                    fontSize: 32,
                    width: 48,
                    textAlign: 'center',
                    flexShrink: 0
                  }}
                >
                  {CATEGORY_ICONS[cat.category] || '📋'}
                </Typography>

                {/* Category name */}
                <Typography
                  variant="h6"
                  sx={{
                    fontWeight: 'bold',
                    flexGrow: 1,
                    whiteSpace: 'nowrap',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis'
                  }}
                >
                  {t(`tsumego:${cat.category}`)}
                </Typography>

                {/* Problem count */}
                <Typography
                  variant="body1"
                  color="text.secondary"
                  sx={{
                    flexShrink: 0,
                    whiteSpace: 'nowrap'
                  }}
                >
                  {cat.count} {t('tsumego:problems')}
                </Typography>
              </Box>
            </CardActionArea>
          </Card>
        ))}
      </Box>
    </Box>
  );
};

export default TsumegoCategoriesPage;
