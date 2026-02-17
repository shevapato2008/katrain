import { useState } from 'react';
import { Box, Typography, TextField, Button } from '@mui/material';
import { useNavigate } from 'react-router-dom';
import { useKioskAuth } from '../context/KioskAuthContext';

const LoginPage = () => {
  const [username, setUsername] = useState('');
  const [pin, setPin] = useState('');
  const { login } = useKioskAuth();
  const navigate = useNavigate();

  const handleLogin = () => {
    login(username, pin);
    navigate('/kiosk/play', { replace: true });
  };

  return (
    <Box
      sx={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        height: '100vh',
        bgcolor: 'background.default',
      }}
    >
      <Box sx={{ width: 360, display: 'flex', flexDirection: 'column', gap: 3 }}>
        <Typography variant="h4" sx={{ textAlign: 'center', color: 'primary.main', fontWeight: 700 }}>
          KaTrain
        </Typography>
        <TextField
          label="用户名"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          fullWidth
          autoFocus
        />
        <TextField
          label="PIN"
          type="password"
          value={pin}
          onChange={(e) => setPin(e.target.value)}
          fullWidth
        />
        <Button
          variant="contained"
          onClick={handleLogin}
          fullWidth
          sx={{ minHeight: 56, fontSize: '1.1rem' }}
        >
          登录
        </Button>
      </Box>
    </Box>
  );
};

export default LoginPage;
