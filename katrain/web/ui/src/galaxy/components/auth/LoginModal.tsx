import { useState } from 'react';
import { Dialog, DialogTitle, DialogContent, DialogActions, Button, TextField, Alert, Box, Link } from '@mui/material';
import { useAuth } from '../../../context/AuthContext';
import { useSettings } from '../../context/SettingsContext';
import { API } from '../../../api';
import { i18n } from '../../../i18n';

interface LoginModalProps {
    open: boolean;
    onClose: () => void;
}

const LoginModal = ({ open, onClose }: LoginModalProps) => {
    useSettings(); // Subscribe to translation changes
    const { login } = useAuth();
    const [isRegister, setIsRegister] = useState(false);
    const [username, setUsername] = useState('');
    const [password, setPassword] = useState('');
    const [confirmPassword, setConfirmPassword] = useState('');
    const [error, setError] = useState('');
    const [successMsg, setSuccessMsg] = useState('');
    const [loading, setLoading] = useState(false);

    const handleSubmit = async () => {
        setError('');
        setSuccessMsg('');
        if (!username || !password) {
            setError(i18n.t('auth:err_fill_all', 'Please fill in all fields'));
            return;
        }

        if (isRegister && password !== confirmPassword) {
            setError(i18n.t('auth:err_pass_mismatch', 'Passwords do not match'));
            return;
        }

        setLoading(true);
        try {
            if (isRegister) {
                // Register then login
                await API.register(username, password);
                setSuccessMsg(i18n.t('auth:success_register', 'Registration successful! Logging in...'));
                await login(username, password);
            } else {
                await login(username, password);
            }
            onClose();
            // Reset state slightly after close for smooth transition
            setTimeout(() => {
                setUsername('');
                setPassword('');
                setConfirmPassword('');
                setIsRegister(false);
                setSuccessMsg('');
            }, 500);
        } catch (err: any) {
            const msg = err.message || i18n.t('auth:err_failed', 'Operation failed');
            setError(msg);
        } finally {
            setLoading(false);
        }
    };

    const toggleMode = () => {
        setIsRegister(!isRegister);
        setError('');
        setSuccessMsg('');
        setPassword('');
        setConfirmPassword('');
    };

    return (
        <Dialog open={open} onClose={onClose} PaperProps={{ sx: { borderRadius: 3, p: 1, minWidth: 350 } }}>
            <DialogTitle>
                {isRegister ? i18n.t('auth:register_title', 'Create Account') : i18n.t('auth:login_title', 'Login to Galaxy Go')}
            </DialogTitle>
            <DialogContent>
                {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
                {successMsg && <Alert severity="success" sx={{ mb: 2 }}>{successMsg}</Alert>}
                
                <TextField
                    autoFocus
                    margin="dense"
                    label={i18n.t('auth:username', 'Username')}
                    fullWidth
                    variant="outlined"
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                    disabled={loading}
                />
                <TextField
                    margin="dense"
                    label={i18n.t('auth:password', 'Password')}
                    type="password"
                    fullWidth
                    variant="outlined"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    onKeyPress={(e) => e.key === 'Enter' && handleSubmit()}
                    disabled={loading}
                />
                
                {isRegister && (
                    <TextField
                        margin="dense"
                        label={i18n.t('auth:confirm_password', 'Confirm Password')}
                        type="password"
                        fullWidth
                        variant="outlined"
                        value={confirmPassword}
                        onChange={(e) => setConfirmPassword(e.target.value)}
                        onKeyPress={(e) => e.key === 'Enter' && handleSubmit()}
                        disabled={loading}
                    />
                )}

                <Box sx={{ mt: 2, textAlign: 'center' }}>
                    <Link component="button" variant="body2" onClick={toggleMode} disabled={loading} sx={{ textDecoration: 'none' }}>
                        {isRegister ? i18n.t('auth:switch_to_login', 'Already have an account? Login') : i18n.t('auth:switch_to_register', "Don't have an account? Register")}
                    </Link>
                </Box>
            </DialogContent>
            <DialogActions sx={{ px: 3, pb: 2 }}>
                <Button onClick={onClose} disabled={loading}>{i18n.t('auth:cancel_btn', 'Cancel')}</Button>
                <Button onClick={handleSubmit} variant="contained" disabled={loading}>
                    {isRegister ? i18n.t('auth:register_btn', 'Register') : i18n.t('auth:login_btn', 'Login')}
                </Button>
            </DialogActions>
        </Dialog>
    );
};

export default LoginModal;