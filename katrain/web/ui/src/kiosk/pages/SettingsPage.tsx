import { useState, type ReactNode } from 'react';
import { Box, Typography, FormControlLabel, Switch, Button, Select, MenuItem, IconButton } from '@mui/material';
import { useLocation, useNavigate } from 'react-router-dom';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import DeveloperBoardOutlinedIcon from '@mui/icons-material/DeveloperBoardOutlined';
import PersonOutlineOutlinedIcon from '@mui/icons-material/PersonOutlineOutlined';
import PublicOutlinedIcon from '@mui/icons-material/PublicOutlined';
import TranslateOutlinedIcon from '@mui/icons-material/TranslateOutlined';
import { useTranslation } from '../../hooks/useTranslation';
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
  minHeight: 0,
  overflow: 'hidden',
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
  const location = useLocation();
  // Real, persisted language (loads the catalog + writes localStorage) — not local
  // component state, so the selector actually switches the UI language. `languages`
  // is the shared catalog galaxy uses, so the kiosk offers the same full set.
  const { language, setLanguage, languages } = useSettings();
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

  const handleBack = () => {
    const from = (location.state as { from?: unknown } | null)?.from;
    let destination = '/kiosk/play';

    if (typeof from === 'string') {
      try {
        const url = new URL(from, window.location.origin);
        const decodedPathname = decodeURIComponent(url.pathname);
        const isInternalKioskRoute = url.origin === window.location.origin && decodedPathname.startsWith('/kiosk/');
        const isSettingsRoute =
          decodedPathname === '/kiosk/settings' || decodedPathname.startsWith('/kiosk/settings/');

        if (isInternalKioskRoute && !isSettingsRoute) {
          destination = `${url.pathname}${url.search}${url.hash}`;
        }
      } catch {
        // Malformed or un-decodable return locations use the safe kiosk fallback.
      }
    }

    navigate(destination);
  };

  return (
    <Box sx={{ height: '100%', overflow: 'hidden', px: 1.5, pt: 1, pb: 1, display: 'flex', flexDirection: 'column' }}>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 0.75, flexShrink: 0 }}>
        <IconButton
          aria-label={t('Back', '返回')}
          onClick={handleBack}
          sx={{ minWidth: 48, width: 48, minHeight: 48, height: 48, flexShrink: 0 }}
        >
          <ArrowBackIcon />
        </IconButton>
        <Typography variant="h6" component="h2" sx={{ fontSize: '1.1rem', minWidth: 0 }}>
          {t('Settings', '设置')}
        </Typography>
      </Box>

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
        <Box data-testid="settings-left-column" sx={columnSx}>
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

          {/* Tsumego auto-advance — the switch label is self-describing */}
          <Box sx={cardSx}>
            <FormControlLabel
              sx={{ ml: 0, mr: 0 }}
              control={<Switch checked={autoAdvance} onChange={(e) => handleAutoAdvanceChange(e.target.checked)} />}
              label={t('tsumego:autoAdvance', '做对后自动进入下一题')}
            />
          </Box>

          {/* External platforms live in the shorter column so all settings remain
              reachable inside the fixed 464px kiosk content viewport. */}
          <Box sx={cardSx}>
            <CardHeader
              icon={<PublicOutlinedIcon />}
              title={t('External Platforms', '外部平台')}
              sub={t('Coming soon', '敬请期待')}
            />
            <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 1 }}>
              {platforms.map((p) => (
                <Box key={p.name} sx={{ display: 'flex', alignItems: 'center', gap: 1, bgcolor: 'var(--raise2)', border: '1px solid', borderColor: 'divider', borderRadius: 1.5, px: 1.25, py: 0.75, opacity: 0.7, pointerEvents: 'none' }}>
                  <Box sx={{ width: 8, height: 8, borderRadius: '2px', bgcolor: p.color, flexShrink: 0 }} />
                  <Typography variant="body2" sx={{ color: 'text.secondary', fontWeight: 500, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{p.name}</Typography>
                </Box>
              ))}
            </Box>
          </Box>
        </Box>

        {/* ── Right column ────────────────────────────────────────── */}
        <Box data-testid="settings-right-column" sx={columnSx}>
          {/* Language — shares galaxy's full catalog (11 langs). A compact Select keeps
              the fixed no-scroll dashboard intact where a chip row would overflow. */}
          <Box sx={cardSx}>
            <CardHeader icon={<TranslateOutlinedIcon />} title={t('Language', '语言')} />
            <Select
              fullWidth
              size="small"
              value={language}
              onChange={(e) => { void setLanguage(e.target.value); }}
              MenuProps={{ PaperProps: { sx: { maxHeight: 320 } } }}
            >
              {languages.map((lang) => (
                <MenuItem key={lang.code} value={lang.code}>
                  {lang.name}
                </MenuItem>
              ))}
            </Select>
          </Box>

          {/* Account — profile + sign out */}
          <Box sx={cardSx}>
            <CardHeader icon={<PersonOutlineOutlinedIcon />} title={t('Account', '账户')} />
            <AccountSection />
          </Box>

        </Box>
      </Box>
    </Box>
  );
};

export default SettingsPage;
