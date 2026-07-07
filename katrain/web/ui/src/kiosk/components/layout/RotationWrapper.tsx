import { type ReactNode } from 'react';
import { useOrientation, type Rotation } from '../../context/OrientationContext';

const STYLES: Record<Rotation, { transform: string; width: string; height: string }> = {
  0:   { transform: '',                                       width: '100vw', height: '100vh' },
  180: { transform: 'rotate(180deg) translate(-100%, -100%)', width: '100vw', height: '100vh' },
};

const RotationWrapper = ({ children }: { children: ReactNode }) => {
  const { rotation } = useOrientation();
  const s = STYLES[rotation];
  return (
    <div data-testid="rotation-wrapper" style={{
      ...s, transformOrigin: 'top left', overflow: 'hidden', position: 'fixed', top: 0, left: 0,
    }}>
      {children}
    </div>
  );
};

export default RotationWrapper;
