import { useState } from 'react';
import { Dialog, DialogTitle, DialogContent, DialogActions, Button, TextField, Alert, Box, Link } from '@mui/material';
import { useAuth } from '../../context/AuthContext';
import { API } from '../../../api';

interface LoginModalProps {
    open: boolean;
    onClose: () => void;
}

const LoginModal = ({ open, onClose }: LoginModalProps) => {
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
            setError('Please fill in all fields');
            return;
        }

        if (isRegister && password !== confirmPassword) {
            setError('Passwords do not match');
            return;
        }

        setLoading(true);
        try {
            if (isRegister) {
                // Register then login
                await API.register(username, password);
                setSuccessMsg('Registration successful! Logging in...');
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
            const msg = err.message || 'Operation failed';
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
                {isRegister ? 'Create Account' : 'Login to Galaxy Go'}
            </DialogTitle>
            <DialogContent>
                {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
                {successMsg && <Alert severity="success" sx={{ mb: 2 }}>{successMsg}</Alert>}
                
                <TextField
                    autoFocus
                    margin="dense"
                    label="Username"
                    fullWidth
                    variant="outlined"
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                    disabled={loading}
                />
                <TextField
                    margin="dense"
                    label="Password"
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
                        label="Confirm Password"
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
                        {isRegister ? "Already have an account? Login" : "Don't have an account? Register"}
                    </Link>
                </Box>
            </DialogContent>
            <DialogActions sx={{ px: 3, pb: 2 }}>
                <Button onClick={onClose} disabled={loading}>Cancel</Button>
                <Button onClick={handleSubmit} variant="contained" disabled={loading}>
                    {isRegister ? 'Register' : 'Login'}
                </Button>
            </DialogActions>
        </Dialog>
    );
};

export default LoginModal;