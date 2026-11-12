import { useEffect } from 'react';
import { Box, CircularProgress } from '@mui/material';
import { Navigate, useNavigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { LAUNCHER_LOGIN_URL } from '../shell/boxUrls';
import LoginMethods from '../../features/auth/LoginMethods';
import { KIOSK_SANS } from '../theme';

export default function LoginPage() {
  const { isAuthenticated, isLoading, isStrictBoxKiosk, isGuest } = useAuth();
  const navigate = useNavigate();
  useEffect(() => {
    if (isStrictBoxKiosk) window.location.href = LAUNCHER_LOGIN_URL;
  }, [isStrictBoxKiosk]);
  if (isStrictBoxKiosk) return <Box sx={{ display: 'flex', width: '100%', height: '100%', alignItems: 'center', justifyContent: 'center', bgcolor: 'background.default' }}><CircularProgress /></Box>;
  if (!isLoading && isAuthenticated && !isGuest) return <Navigate to="/kiosk/play" replace />;
  const enterPlay = () => navigate('/kiosk/play', { replace: true });
  return <Box data-testid="kiosk-login-page" sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', sm: '41% minmax(0, 1fr)' }, minHeight: '100dvh', width: '100%', bgcolor: '#101b16', fontFamily: KIOSK_SANS }}>
    <Box sx={{ display: { xs: 'none', sm: 'flex' }, flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: '24px', borderRight: '1px solid #49634e' }}>
      <Box sx={{ position: 'relative', width: 128, height: 144, '&:before': { position: 'absolute', content: '""', inset: '-28px -46px', background: 'radial-gradient(ellipse, #58b57a24, transparent 68%)' } }}>
        <Box component="img" src="/assets/img/logo-white.png" alt="" sx={{ position: 'relative', width: '100%', height: '100%', objectFit: 'contain' }} />
      </Box>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: '16px', whiteSpace: 'nowrap' }}>
        <Box component="span" sx={{ fontFamily: '"SmartBox Brand LongCang", serif', fontSize: 36, lineHeight: 1.35, color: '#eef4ed', fontSynthesis: 'none' }}>智星盒</Box>
        <Box component="span" sx={{ fontFamily: '"SmartBox Fondamento", serif', fontSize: 28, lineHeight: 1.35, color: '#b7cabb', fontSynthesis: 'none' }}>StellaBox</Box>
      </Box>
    </Box>
    <Box sx={{ display: 'flex', alignItems: 'safe center', justifyContent: 'center', minWidth: 0, p: { xs: '20px', sm: '26px 38px' }, overflowY: 'auto' }}>
      <Box sx={{ width: '100%', maxWidth: 528, my: 'auto', bgcolor: '#1a2a21', border: '1px solid #49634e', borderRadius: '20px', p: '22px' }}>
        <LoginMethods surface="kiosk" onSuccess={enterPlay} onGuest={enterPlay} />
      </Box>
    </Box>
  </Box>;
}
