import { forwardRef, memo } from 'react';
import { OrbitControls } from '@react-three/drei';
import { MOUSE } from 'three';
import { BOARD_SURFACE_Y } from './constants';

const CameraController = forwardRef<any>((_, ref) => {
  return (
    <OrbitControls
      ref={ref}
      target={[0, BOARD_SURFACE_Y, 0]}
      enableDamping
      dampingFactor={0.08}
      minDistance={10}
      maxDistance={50}
      minPolarAngle={Math.PI * 0.05}
      maxPolarAngle={Math.PI * 0.38}
      minAzimuthAngle={0}
      maxAzimuthAngle={0}
      enablePan={false}
      mouseButtons={{
        LEFT: MOUSE.ROTATE,
        MIDDLE: MOUSE.DOLLY,
      }}
    />
  );
});

CameraController.displayName = 'CameraController';

export default memo(CameraController);
