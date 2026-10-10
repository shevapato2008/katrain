import { useEffect, useRef, useState } from 'react';
import { useAuth } from '../../../context/AuthContext';
import type { AccessFeature } from '../../../components/auth/accessPolicy';
import { AccessPrompt } from '../../../components/auth/AccessPrompt';
import LoginModal from './LoginModal';

interface AuthRequiredDialogProps {
    open: boolean;
    onClose: () => void;
    message?: string;
    feature?: AccessFeature;
    onAuthenticated?: () => void;
}

/** Login preserves the public page. Writes still require their original confirmation. */
const AuthRequiredDialog = ({ open, onClose, message, feature = 'analysis', onAuthenticated = onClose }: AuthRequiredDialogProps) => {
    const auth = useAuth();
    const [loginOpen, setLoginOpen] = useState(false);
    const previous = useRef({ open, status: auth.status });
    useEffect(() => {
        const recovered = open && previous.current.open && auth.status === 'authenticated'
            && (previous.current.status === 'checking' || previous.current.status === 'unavailable');
        previous.current = { open, status: auth.status };
        if (recovered) {
            setLoginOpen(false);
            onAuthenticated();
        }
    }, [open, auth.status, onAuthenticated]);
    const status = auth.status === 'authenticated' ? 'guest' : auth.status;
    return <>
        <AccessPrompt open={open && !loginOpen} surface="galaxy" status={status} feature={feature} action message={message}
            onBack={onClose}
            onPrimary={() => { if (status === 'unavailable') void auth.retry(); else setLoginOpen(true); }} />
        {loginOpen && <LoginModal open onClose={() => setLoginOpen(false)} onSuccess={onAuthenticated} />}
    </>;
};

export default AuthRequiredDialog;
