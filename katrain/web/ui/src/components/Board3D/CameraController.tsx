import { forwardRef, memo } from 'react';
import { OrbitControls } from '@react-three/drei';
import { MOUSE } from 'three';
import { BOARD_SURFACE_Y } from './constants';

interface CameraControllerProps {
  target?: [number, number, number];
  interactive?: boolean;
  /** Lock polar angle (fraction of π). Only used when interactive=false. */
  fixedPolarAngle?: number;
  /** Minimum azimuth (yaw) angle in radians. Default 0 (locked, galaxy behavior). */
  minAzimuthAngle?: number;
  /** Maximum azimuth (yaw) angle in radians. Default 0 (locked, galaxy behavior). */
  maxAzimuthAngle?: number;
}

const CameraController = forwardRef<any, CameraControllerProps>(
  ({ target, interactive = true, fixedPolarAngle, minAzimuthAngle = 0, maxAzimuthAngle = 0 }, ref) => {
    const controlTarget = target || [0, BOARD_SURFACE_Y, 0];

    const minPolar = !interactive && fixedPolarAngle != null
      ? fixedPolarAngle * Math.PI
      : Math.PI * 0.05;
    const maxPolar = !interactive && fixedPolarAngle != null
      ? fixedPolarAngle * Math.PI
      : Math.PI * 0.38;

    return (
      <OrbitControls
        ref={ref}
        target={controlTarget}
        enableDamping={interactive}
        dampingFactor={0.08}
        minDistance={10}
        maxDistance={50}
        minPolarAngle={minPolar}
        maxPolarAngle={maxPolar}
        minAzimuthAngle={minAzimuthAngle}
        maxAzimuthAngle={maxAzimuthAngle}
        enablePan={false}
        enableRotate={interactive}
        enableZoom={interactive}
        mouseButtons={interactive ? {
          LEFT: MOUSE.ROTATE,
          MIDDLE: MOUSE.DOLLY,
        } : {}}
      />
    );
  });

CameraController.displayName = 'CameraController';

export default memo(CameraController);
