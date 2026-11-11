import { Dialog, DialogTitle, DialogContent, DialogActions, Button } from '@mui/material';
import { useTranslation } from '../../../hooks/useTranslation';
import LoginMethods from '../../../features/auth/LoginMethods';

interface LoginModalProps { open: boolean; onClose: () => void; onSuccess?: () => void; }

export default function LoginModal({ open, onClose, onSuccess }: LoginModalProps) {
    const { t } = useTranslation();
    return <Dialog open={open} onClose={onClose} maxWidth="xs" fullWidth
        PaperProps={{ sx: {
            borderRadius: 3, p: 1, width: 'calc(100% - 32px)', m: 2,
            '& .MuiTab-root.Mui-selected': { color: 'text.primary' },
            '& .MuiTabs-indicator': { bgcolor: 'primary.light' },
            '& .MuiInputLabel-root.Mui-focused:not(.Mui-error)': { color: 'text.secondary' },
            '& .MuiOutlinedInput-root.Mui-focused:not(.Mui-error) .MuiOutlinedInput-notchedOutline': { borderColor: 'primary.light' },
            '& .MuiButton-outlinedPrimary:not(.Mui-disabled), & .MuiButton-textPrimary:not(.Mui-disabled)': { color: 'text.secondary' },
            '& .MuiButton-outlinedPrimary:not(.Mui-disabled)': { borderColor: 'primary.light' },
        } }}>
        <DialogTitle>{t('auth:login_title', '登录智星盒')}</DialogTitle>
        <DialogContent>{open && <LoginMethods onSuccess={() => { onSuccess?.(); onClose(); }} />}</DialogContent>
        <DialogActions sx={{ px: 3, pb: 1 }}><Button onClick={onClose} sx={{ minHeight: 44 }}>{t('auth:cancel_btn', '取消')}</Button></DialogActions>
    </Dialog>;
}
