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

interface RegisterDialogProps {
  open: boolean;
  onClose: () => void;
  onRegisterSuccess: (username: string) => void;
}

const RegisterDialog: React.FC<RegisterDialogProps> = ({ open, onClose, onRegisterSuccess }) => {
  const { t } = useTranslation();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (password !== confirmPassword) {
      setError(t("Passwords do not match"));
      return;
    }

    setLoading(true);

    try {
      await API.register(username, password);
      onRegisterSuccess(username);
      onClose();
    } catch (err: any) {
      setError(err.message || 'Registration failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Dialog open={open} onClose={onClose} maxWidth="xs" fullWidth>
      <form onSubmit={handleSubmit}>
        <DialogTitle>{t("Register for KaTrain")}</DialogTitle>
        <DialogContent>
          <Box sx={{ mt: 1, display: 'flex', flexDirection: 'column', gap: 2 }}>
            {error && <Alert severity="error">{error}</Alert>}
            <TextField
              label={t("Username")}
              fullWidth
              autoFocus
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              disabled={loading}
              required
            />
            <TextField
              label={t("Password")}
              type="password"
              fullWidth
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              disabled={loading}
              required
            />
            <TextField
              label={t("Confirm Password")}
              type="password"
              fullWidth
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              disabled={loading}
              required
            />
          </Box>
        </DialogContent>
        <DialogActions sx={{ p: 3 }}>
          <Button onClick={onClose} disabled={loading}>{t("Cancel")}</Button>
          <Button
            type="submit"
            variant="contained"
            color="primary"
            disabled={loading}
            startIcon={loading ? <CircularProgress size={20} color="inherit" /> : null}
          >
            {loading ? t("Registering...") : t("Register")}
          </Button>
        </DialogActions>
      </form>
    </Dialog>
  );
};

export default RegisterDialog;
