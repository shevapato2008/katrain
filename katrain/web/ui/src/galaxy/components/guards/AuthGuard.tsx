import { Fragment, useState, type ReactNode } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../../context/AuthContext';
import { AccessPrompt } from '../../../components/auth/AccessPrompt';
import { ProtectedOutline } from '../../../components/auth/ProtectedOutline';
import { accessAllowed, accessMetadata, type AccessFeature } from '../../../components/auth/accessPolicy';
import LoginModal from '../auth/LoginModal';

export const AuthGuard = ({ children, feature = 'hall', realAccount = feature === 'hall' || feature === 'rated' }: {
    children: ReactNode;
    feature?: AccessFeature;
    realAccount?: boolean;
}) => {
    const auth = useAuth();
    const navigate = useNavigate();
    const [loginOpen, setLoginOpen] = useState(false);
    const status = auth.status;
    if (accessAllowed(status, auth.isAuthenticated, auth.isGuest, realAccount)) {
        return <Fragment key={auth.identityKey}>{children}</Fragment>;
    }
    return <>
        <ProtectedOutline surface="galaxy" feature={feature} />
        <AccessPrompt open={!loginOpen} surface="galaxy" status={status} feature={feature}
            onPrimary={() => { if (status === 'unavailable') void auth.retry(); else setLoginOpen(true); }}
            onBack={() => navigate(`/galaxy${accessMetadata[feature].backPath}`, { replace: true })} />
        {loginOpen && <LoginModal open onClose={() => setLoginOpen(false)} />}
    </>;
};
