import { useState } from 'react';
import { Box, Typography, Divider, Card, CardActionArea, CardContent } from '@mui/material';
import OptionChips from '../components/common/OptionChips';
import { useTranslation } from '../../hooks/useTranslation';
import { useOrientation, type Rotation } from '../context/OrientationContext';

const SettingsPage = () => {
  const { t } = useTranslation();
  const { rotation, setRotation } = useOrientation();
  const [language, setLanguage] = useState('zh');

  const platforms = [
    { name: '99围棋', desc: t('Kids Go teaching platform', '少儿围棋教学平台') },
    { name: '野狐围棋', desc: t('Tencent professional Go platform', '腾讯旗下专业对弈平台') },
    { name: '腾讯围棋', desc: t('Online play and spectating', '在线对弈与观战') },
    { name: '新浪围棋', desc: t('Go news and live streaming', '围棋资讯与直播') },
  ];

  return (
    <Box sx={{ height: '100%', overflow: 'auto', p: 3 }}>
      <Typography variant="h5" sx={{ mb: 2 }}>{t('Settings', '设置')}</Typography>
      <Divider sx={{ mb: 3 }} />

      <OptionChips
        label={t('Screen Rotation', '屏幕旋转')}
        options={[
          { value: 0 as Rotation, label: '0° 横屏' },
          { value: 90 as Rotation, label: '90° 竖屏' },
          { value: 180 as Rotation, label: '180° 横屏翻转' },
          { value: 270 as Rotation, label: '270° 竖屏翻转' },
        ]}
        value={rotation}
        onChange={(v) => setRotation(v as Rotation)}
      />

      <OptionChips
        label={t('Language', '语言')}
        options={[
          { value: 'zh', label: '中文' },
          { value: 'en', label: 'English' },
          { value: 'ja', label: '日本語' },
          { value: 'ko', label: '한국어' },
        ]}
        value={language}
        onChange={setLanguage}
      />

      <Typography variant="body2" sx={{ color: 'text.secondary', mt: 3, mb: 1.5 }}>
        {t('External Platforms', '外部平台')}
      </Typography>
      <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 1.5 }}>
        {platforms.map((p) => (
          <Card key={p.name} variant="outlined" sx={{ bgcolor: 'background.paper' }}>
            <CardActionArea sx={{ p: 0 }}>
              <CardContent sx={{ py: 1.5, px: 2, '&:last-child': { pb: 1.5 } }}>
                <Typography variant="body1" sx={{ fontWeight: 500 }}>{p.name}</Typography>
                <Typography variant="caption" sx={{ color: 'text.secondary' }}>{p.desc}</Typography>
              </CardContent>
            </CardActionArea>
          </Card>
        ))}
      </Box>
    </Box>
  );
};

export default SettingsPage;
