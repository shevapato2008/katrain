import { Dialog, useTheme } from '@mui/material';
import LoginMethods from '../../../features/auth/LoginMethods';

interface LoginModalProps { open: boolean; onClose: () => void; onSuccess?: () => void; }

export default function LoginModal({ open, onClose, onSuccess }: LoginModalProps) {
    const theme = useTheme();
    return <Dialog open={open} onClose={onClose} maxWidth={false} fullWidth aria-labelledby="named-auth-title"
        slotProps={{ backdrop: { sx: { bgcolor: '#0008' } }, paper: { sx: {
            width: 'calc(100% - 32px)', maxWidth: 480, m: 2, p: '28px',
            borderRadius: '16px', border: '1px solid #ffffff15', bgcolor: '#252525',
            backgroundImage: 'none', boxShadow: '0 22px 80px #0008', fontFamily: theme.typography.fontFamily,
        } } }}>
        {open && <LoginMethods onClose={onClose} onSuccess={() => { onSuccess?.(); onClose(); }} />}
    </Dialog>;
}
