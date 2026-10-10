import { Fragment, type ReactNode } from 'react';
import { Outlet, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../../../context/AuthContext';
import { AccessPrompt } from '../../../components/auth/AccessPrompt';
import { ProtectedOutline } from '../../../components/auth/ProtectedOutline';
import { accessAllowed, accessMetadata, kioskAccessPolicy, type AccessFeature } from '../../../components/auth/accessPolicy';
import { LAUNCHER_LOGIN_URL, leaveToLauncher } from '../../shell/boxUrls';

const KioskAuthGuard = ({ children, feature, realAccount }: { children?: ReactNode; feature?: AccessFeature; realAccount?: boolean }) => {
  const auth = useAuth();
  const { pathname } = useLocation();
  const navigate = useNavigate();
  const policy = kioskAccessPolicy(pathname);
  const selectedFeature = feature ?? policy?.feature ?? 'hall';
  const needsRealAccount = realAccount ?? policy?.realAccount ?? false;
  if (accessAllowed(auth.status, auth.isAuthenticated, auth.isGuest, needsRealAccount)) {
    return <Fragment key={auth.identityKey}>{children ?? <Outlet />}</Fragment>;
  }
  const backPath = accessMetadata[selectedFeature].backPath || '/play';
  return <>
    <ProtectedOutline surface="kiosk" feature={selectedFeature} />
    <AccessPrompt open surface="kiosk" status={auth.status} feature={selectedFeature} strictBox={auth.isStrictBoxKiosk}
      onPrimary={() => {
        if (auth.status === 'unavailable') void auth.retry();
        else if (auth.isStrictBoxKiosk) leaveToLauncher(LAUNCHER_LOGIN_URL);
        else navigate('/kiosk/login');
      }}
      onBack={() => navigate(`/kiosk${backPath}`, { replace: true })} />
  </>;
};

export default KioskAuthGuard;
