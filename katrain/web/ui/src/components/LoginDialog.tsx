import React, { useState } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  Button,
  Box,
  Alert,
  CircularProgress
} from '@mui/material';
import { API } from '../api';
import { useTranslation } from '../hooks/useTranslation';

interface LoginDialogProps {
  open: boolean;
  onClose: () => void;
  onLoginSuccess: (token: string) => void;
}

const LoginDialog: React.FC<LoginDialogProps> = ({ open, onClose, onLoginSuccess }) => {
  const { t } = useTranslation();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      const response = await API.login(username, password);
      onLoginSuccess(response.access_token);
    } catch (err: any) {
      setError(err.message || 'Login failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Dialog open={open} onClose={onClose} maxWidth="xs" fullWidth>
      <form onSubmit={handleSubmit}>
        <DialogTitle>{t("auth:login_title", "登录弈航")}</DialogTitle>
        <DialogContent>
          <Box sx={{ mt: 1, display: 'flex', flexDirection: 'column', gap: 2 }}>
            {error && <Alert severity="error">{error}</Alert>}
            <TextField
              label={t("auth:username", "Username")}
              fullWidth
              autoFocus
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              disabled={loading}
              required
            />
            <TextField
              label={t("auth:password", "Password")}
              type="password"
              fullWidth
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              disabled={loading}
              required
            />
          </Box>
        </DialogContent>
        <DialogActions sx={{ p: 3 }}>
          <Button onClick={onClose} disabled={loading}>{t("auth:cancel_btn", "Cancel")}</Button>
          <Button
            type="submit"
            variant="contained"
            color="primary"
            disabled={loading}
            startIcon={loading ? <CircularProgress size={20} color="inherit" /> : null}
          >
            {loading ? t("auth:logging_in", "Logging in...") : t("auth:login_btn", "Login")}
          </Button>
        </DialogActions>
      </form>
    </Dialog>
  );
};

export default LoginDialog;
