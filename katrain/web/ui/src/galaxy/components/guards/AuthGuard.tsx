import { ReactNode } from 'react';
import { useAuth } from '../../context/AuthContext';
import { Box, Button, Typography, Paper } from '@mui/material';
import LockIcon from '@mui/icons-material/Lock';

// Simple Login Reminder Component
const LoginReminder = () => (
    <Box sx={{ display: 'flex', height: '100%', alignItems: 'center', justifyContent: 'center' }}>
        <Paper sx={{ p: 4, display: 'flex', flexDirection: 'column', alignItems: 'center', maxWidth: 400 }}>
            <LockIcon sx={{ fontSize: 64, color: 'text.secondary', mb: 2 }} />
            <Typography variant="h5" gutterBottom>Login Required</Typography>
            <Typography variant="body1" color="text.secondary" align="center" sx={{ mb: 3 }}>
                This feature is only available to registered users. Please login to continue.
            </Typography>
            {/* Logic to trigger login dialog would go here, or just tell user to use sidebar */}
            <Typography variant="caption" color="text.disabled">
                Use the Login button in the sidebar.
            </Typography>
        </Paper>
    </Box>
);

export const AuthGuard = ({ children }: { children: ReactNode }) => {
    const { isAuthenticated } = useAuth();

    if (!isAuthenticated) {
        return <LoginReminder />;
    }

    return <>{children}</>;
};
