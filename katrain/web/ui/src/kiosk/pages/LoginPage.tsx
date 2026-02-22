import { useState } from 'react';
import { Box, TextField, Button, Typography, Alert } from '@mui/material';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { useTranslation } from '../../hooks/useTranslation';
import RotationSelector from '../components/layout/RotationSelector';

const LoginPage = () => {
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
    } catch (e: any) {
      setError(t('Login failed', '登录失败'));
    } finally {
      setLoading(false);
    }
  };

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%', p: 3 }}>
      <img src="/assets/img/logo.png" alt="弈航" style={{ width: 64, height: 64, marginBottom: 16 }} />
      <Typography variant="h4" sx={{ mb: 1 }}>弈航</Typography>
      <Typography variant="body2" sx={{ mb: 3, color: 'text.secondary' }}>棋道导航者</Typography>
      {error && <Alert severity="error" sx={{ mb: 2, width: '100%', maxWidth: 360 }}>{error}</Alert>}
      <TextField
        label={t('Username', '用户名')}
        value={username}
        onChange={(e) => setUsername(e.target.value)}
        sx={{ mb: 2, width: '100%', maxWidth: 360 }}
      />
      <TextField
        label={t('Password', '密码')}
        type="password"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        sx={{ mb: 2, width: '100%', maxWidth: 360 }}
      />
      <Button
        variant="contained"
        onClick={handleLogin}
        disabled={loading || !username}
        sx={{ width: '100%', maxWidth: 360, minHeight: 48 }}
      >
        {loading ? t('Logging in...', '登录中...') : t('Login', '登录')}
      </Button>
      <Box sx={{ mt: 3 }}>
        <RotationSelector showLabel />
      </Box>
    </Box>
  );
};

export default LoginPage;
