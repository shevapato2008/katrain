import { useState, type KeyboardEvent } from 'react';
import { Box, TextField, Button, Typography, Alert, useTheme } from '@mui/material';
import { alpha } from '@mui/material/styles';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { useTranslation } from '../../hooks/useTranslation';
import { KIOSK_SERIF } from '../theme';

// Brand lockup matches the Header (智星盒 / StellaBox) — Newsreader serif, jade console palette.
const BRAND_SERIF = KIOSK_SERIF;

const LoginPage = () => {
  const theme = useTheme();
  const { login } = useAuth();
  const navigate = useNavigate();
  const { t } = useTranslation();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleLogin = async () => {
    setError('');
    setLoading(true);
    try {
      await login(username, password);
      navigate('/kiosk/play', { replace: true });
    } catch {
      setError(t('Login failed', '登录失败'));
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e: KeyboardEvent) => {
    if (e.key === 'Enter' && username && !loading) handleLogin();
  };

  // Faint go-board grid — the split panel's single signature; hairline rules, radial-masked to fade at the edges.
  const gridBg = {
    position: 'absolute',
    inset: 0,
    pointerEvents: 'none',
    backgroundImage:
      `linear-gradient(${theme.palette.divider} 1px, transparent 1px),` +
      `linear-gradient(90deg, ${theme.palette.divider} 1px, transparent 1px)`,
    backgroundSize: '46px 46px',
    opacity: 0.24,
    maskImage: 'radial-gradient(ellipse 72% 62% at 50% 44%, #000 0%, transparent 76%)',
    WebkitMaskImage: 'radial-gradient(ellipse 72% 62% at 50% 44%, #000 0%, transparent 76%)',
  } as const;

  const inputSx = { '& .MuiOutlinedInput-root': { bgcolor: 'var(--raise2)' } };

  return (
    <Box sx={{ display: 'flex', width: '100%', height: '100%', bgcolor: 'background.default' }}>
      {/* ── Left: brand panel — centered lockup, enlarged mark ── */}
      <Box
        sx={{
          position: 'relative',
          flexShrink: 0,
          width: '42%',
          minWidth: 320,
          maxWidth: 460,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          px: 5,
          borderRight: '1px solid',
          borderColor: 'divider',
          background: `linear-gradient(158deg, ${theme.palette.background.paper} 0%, ${theme.palette.background.default} 82%)`,
        }}
      >
        <Box sx={gridBg} />
        <Box
          sx={{
            position: 'absolute',
            inset: 0,
            pointerEvents: 'none',
            background: `radial-gradient(circle 220px at 50% 42%, ${alpha(theme.palette.primary.main, 0.14)}, transparent 68%)`,
          }}
        />

        <Box sx={{ position: 'relative', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 2 }}>
          <Box
            component="img"
            src="/assets/img/logo-white.png"
            alt="智星盒 StellaBox"
            sx={{ width: 80, height: 80, objectFit: 'contain', mb: 0.5 }}
          />
          <Box sx={{ display: 'flex', alignItems: 'baseline', gap: 1.5 }}>
            <Typography sx={{ fontFamily: BRAND_SERIF, fontWeight: 500, fontSize: 48, lineHeight: 1, letterSpacing: '3px' }}>
              智星盒
            </Typography>
            <Typography
              component="span"
              sx={{ fontFamily: BRAND_SERIF, fontStyle: 'italic', fontSize: 19, color: 'text.secondary' }}
            >
              StellaBox
            </Typography>
          </Box>
          <Typography sx={{ fontSize: 14, color: 'text.secondary', letterSpacing: '0.46em', pl: '0.46em' }}>
            棋道导航者
          </Typography>
        </Box>

        <Typography
          variant="caption"
          sx={{ position: 'absolute', bottom: 28, left: 0, right: 0, textAlign: 'center', color: 'text.disabled', letterSpacing: '0.12em' }}
        >
          围棋智能终端
        </Typography>
      </Box>

      {/* ── Right: sign-in form ── */}
      <Box sx={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', p: 3 }}>
        <Box
          sx={{
            width: '100%',
            maxWidth: 380,
            bgcolor: 'background.paper',
            border: '1px solid',
            borderColor: 'divider',
            borderRadius: '16px',
            p: 3.5,
            display: 'flex',
            flexDirection: 'column',
            gap: 2,
          }}
        >
          {error && <Alert severity="error">{error}</Alert>}
          <TextField
            fullWidth
            label={t('Username', '用户名')}
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            onKeyDown={handleKeyDown}
            sx={inputSx}
          />
          <TextField
            fullWidth
            label={t('Password', '密码')}
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            onKeyDown={handleKeyDown}
            sx={inputSx}
          />
          <Button
            fullWidth
            variant="contained"
            color="primary"
            onClick={handleLogin}
            disabled={loading || !username}
            sx={{ minHeight: 52, mt: 0.5, fontSize: '1rem', letterSpacing: '0.1em' }}
          >
            {loading ? t('Logging in...', '登录中...') : t('Login', '登录')}
          </Button>
        </Box>
      </Box>
    </Box>
  );
};

export default LoginPage;
