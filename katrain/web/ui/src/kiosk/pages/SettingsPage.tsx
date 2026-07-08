import { useState, type ReactNode } from 'react';
import { Box, Typography, FormControlLabel, Switch, Button } from '@mui/material';
import { useNavigate } from 'react-router-dom';
import DeveloperBoardOutlinedIcon from '@mui/icons-material/DeveloperBoardOutlined';
import PersonOutlineOutlinedIcon from '@mui/icons-material/PersonOutlineOutlined';
import PublicOutlinedIcon from '@mui/icons-material/PublicOutlined';
import OptionChips from '../components/common/OptionChips';
import { useTranslation } from '../../hooks/useTranslation';
import { useOrientation, type Rotation } from '../context/OrientationContext';
import { useSettings } from '../../context/SettingsContext';
import { readAutoAdvance, writeAutoAdvance } from './tsumegoUnits';
import AccountSection from '../components/settings/AccountSection';
import PhysicalBoardStatus from '../components/settings/PhysicalBoardStatus';

// Shared card shell — matches the 7" artifact's `.scard` (raise surface, hairline
// border, rounded). Compact padding so the whole dashboard fits the fixed 464px
// content area (600 − 50px Header − 86px Dock) without scrolling.
const cardSx = {
  bgcolor: 'background.paper',
  border: '1px solid',
  borderColor: 'divider',
  borderRadius: 2,
  px: 1.75,
  py: 1,
} as const;

const columnSx = {
  display: 'flex',
  flexDirection: 'column',
  gap: 1,
  minWidth: 0,
} as const;

const CardHeader = ({ icon, title, sub }: { icon: ReactNode; title: string; sub?: string }) => (
  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 0.75 }}>
    <Box sx={{ display: 'flex', color: 'primary.main', '& svg': { fontSize: 18 } }}>{icon}</Box>
    <Typography variant="body2" sx={{ fontWeight: 700, color: 'text.primary' }}>
      {title}
    </Typography>
    {sub && (
      <Typography variant="caption" sx={{ ml: 'auto', color: 'text.disabled' }}>
        {sub}
      </Typography>
    )}
  </Box>
);

const SettingsPage = () => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { rotation, setRotation } = useOrientation();
  const { language, setLanguage } = useSettings();
  // kiosk exposes only 中/英; map the 2 chip values to the app's language codes.
  const langChip = language === 'en' ? 'en' : 'cn';
  const [autoAdvance, setAutoAdvance] = useState(() => readAutoAdvance());

  const handleAutoAdvanceChange = (checked: boolean) => {
    setAutoAdvance(checked);
    writeAutoAdvance(checked);
  };

  const platforms = [
    { name: '99围棋', color: '#5cb57a' },
    { name: '野狐围棋', color: '#e0a24a' },
    { name: '腾讯围棋', color: '#4a90ff' },
    { name: '新浪围棋', color: '#e2685c' },
  ];

  return (
    <Box sx={{ height: '100%', overflow: 'hidden', px: 1.5, pt: 1, pb: 1, display: 'flex', flexDirection: 'column' }}>
      <Typography variant="h6" component="h2" sx={{ mb: 0.75, fontSize: '1.1rem', flexShrink: 0 }}>
        {t('Settings', '设置')}
      </Typography>

      <Box
        sx={{
          flex: 1,
          minHeight: 0,
          display: 'grid',
          gridTemplateColumns: { xs: '1fr', md: '1fr 1fr' },
          columnGap: 1.5,
          rowGap: 1,
          alignContent: 'start',
        }}
      >
        {/* ── Left column ─────────────────────────────────────────── */}
        <Box sx={columnSx}>
          {/* Physical board — status + recalibrate */}
          <Box sx={cardSx}>
            <CardHeader
              icon={<DeveloperBoardOutlinedIcon />}
              title={t('Physical board', '实体棋盘')}
              sub={t('Camera · LED · Calibration', '摄像头 · LED · 标定')}
            />
            <PhysicalBoardStatus />
            <Button variant="outlined" fullWidth onClick={() => navigate('/kiosk/vision/setup')} sx={{ mt: 1 }}>
              {t('Recalibrate board', '重新标定棋盘')}
            </Button>
          </Box>

          {/* Screen rotation — OptionChips renders its own label as the card title */}
          <Box sx={{ ...cardSx, pb: 0 }}>
            <OptionChips
              label={t('Screen Rotation', '屏幕旋转')}
              options={[
                { value: 0 as Rotation, label: '0° 横屏' },
                { value: 180 as Rotation, label: '180° 横屏翻转' },
              ]}
              value={rotation}
              onChange={(v) => setRotation(v as Rotation)}
            />
          </Box>

          {/* Tsumego auto-advance — the switch label is self-describing */}
          <Box sx={cardSx}>
            <FormControlLabel
              sx={{ ml: 0, mr: 0 }}
              control={<Switch checked={autoAdvance} onChange={(e) => handleAutoAdvanceChange(e.target.checked)} />}
              label={t('tsumego:autoAdvance', '做对后自动进入下一题')}
            />
          </Box>
        </Box>

        {/* ── Right column ────────────────────────────────────────── */}
        <Box sx={columnSx}>
          {/* Language — OptionChips renders its own label.
              kiosk supports only 中/英; switching to 'en' may surface hardcoded 中文 copy
              elsewhere in the kiosk UI — broader t()-wrapping is a follow-up track. */}
          <Box sx={{ ...cardSx, pb: 0 }}>
            <OptionChips
              label={t('Language', '语言')}
              options={[
                { value: 'cn', label: t('中', '中') },
                { value: 'en', label: t('英', '英') },
              ]}
              value={langChip}
              onChange={(v) => { void setLanguage(v as string); }}
            />
          </Box>

          {/* Account — profile + sign out */}
          <Box sx={cardSx}>
            <CardHeader icon={<PersonOutlineOutlinedIcon />} title={t('Account', '账户')} />
            <AccountSection />
          </Box>

          {/* External platforms — display-only, coming soon */}
          <Box sx={cardSx}>
            <CardHeader
              icon={<PublicOutlinedIcon />}
              title={t('External Platforms', '外部平台')}
              sub={t('Coming soon', '敬请期待')}
            />
            <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 1 }}>
              {platforms.map((p) => (
                <Box
                  key={p.name}
                  sx={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 1,
                    bgcolor: 'var(--raise2)',
                    border: '1px solid',
                    borderColor: 'divider',
                    borderRadius: 1.5,
                    px: 1.25,
                    py: 0.75,
                    opacity: 0.7,
                    pointerEvents: 'none',
                  }}
                >
                  <Box sx={{ width: 8, height: 8, borderRadius: '2px', bgcolor: p.color, flexShrink: 0 }} />
                  <Typography
                    variant="body2"
                    sx={{
                      color: 'text.secondary',
                      fontWeight: 500,
                      whiteSpace: 'nowrap',
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                    }}
                  >
                    {p.name}
                  </Typography>
                </Box>
              ))}
            </Box>
          </Box>
        </Box>
      </Box>
    </Box>
  );
};

export default SettingsPage;
