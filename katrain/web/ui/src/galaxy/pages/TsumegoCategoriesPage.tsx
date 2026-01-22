import { useState, useEffect } from 'react';
import { Box, Typography, Grid, Card, CardContent, CardActionArea, CircularProgress, IconButton, Breadcrumbs, Link } from '@mui/material';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import { useNavigate, useParams } from 'react-router-dom';
import { useSettings } from '../context/SettingsContext';
import { useTranslation } from '../../hooks/useTranslation';

interface CategoryInfo {
  category: string;
  name: string;
  count: number;
}

const CATEGORY_ICONS: Record<string, string> = {
  'life-death': '⚔',
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
    <Box sx={{ p: 4, maxWidth: 1200, mx: 'auto' }}>
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

      <Grid container spacing={3}>
        {categories.map((cat) => (
          <Grid size={{ xs: 12, sm: 6, md: 4 }} key={cat.category}>
            <Card
              sx={{
                borderRadius: 3,
                transition: 'transform 0.2s, box-shadow 0.2s',
                '&:hover': {
                  transform: 'translateY(-4px)',
                  boxShadow: 8
                }
              }}
            >
              <CardActionArea onClick={() => navigate(`/galaxy/tsumego/${level}/${cat.category}`)}>
                <CardContent sx={{ textAlign: 'center', py: 4 }}>
                  <Typography variant="h2" sx={{ mb: 2, opacity: 0.3 }}>
                    {CATEGORY_ICONS[cat.category] || '题'}
                  </Typography>
                  <Typography variant="h5" sx={{ fontWeight: 'bold', mb: 1 }}>
                    {t(`tsumego:${cat.category}`)}
                  </Typography>
                  <Typography variant="h6" color="text.secondary">
                    {cat.count} {t('tsumego:problems')}
                  </Typography>
                </CardContent>
              </CardActionArea>
            </Card>
          </Grid>
        ))}
      </Grid>
    </Box>
  );
};

export default TsumegoCategoriesPage;
