import { useState, useEffect } from 'react';
import { Box, Typography, Card, CardActionArea, CircularProgress } from '@mui/material';
import { useNavigate, useParams } from 'react-router-dom';
import { useSettings } from '../../context/SettingsContext';
import { useTranslation } from '../../hooks/useTranslation';
import ContentPageHeader from '../components/layout/ContentPageHeader';

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
      {/* 原来这里是「返回图标键 + 面包屑」两段式，标题另起一行还带着 "- 选择分类"。
          spec §2.4 明令面包屑不进页头，返回键与标题同行；层级信息由返回键的无障碍名承载。 */}
      <ContentPageHeader
        title={level?.toUpperCase() ?? ''}
        parentLabel={t('Tsumego')}
        parentTo="/galaxy/tsumego"
      />
      <Typography variant="subtitle1" color="text.secondary" sx={{ mt: 1, mb: 4 }}>
        {t('tsumego:selectCategory')} · {t('tsumego:categoryDesc')}
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
