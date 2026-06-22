import type { ReactNode } from 'react';
import { useGeometry } from '../../context/GeometryContext';
import GeometryCalibrationWorkspace from './GeometryCalibrationWorkspace';

const PhysicalBoardGuard = ({ children, requireRecognition = false }: { children: ReactNode; requireRecognition?: boolean }) => {
  const { status } = useGeometry();
  const ready = status.phase === 'disabled' || (
    status.phase === 'ready' && status.session_calibrated && status.capabilities.geometry_ready
    && (!requireRecognition || status.capabilities.recognition_ready)
  );

  if (ready) return <>{children}</>;

  return <GeometryCalibrationWorkspace mode="guard" requireRecognition={requireRecognition} />;
};

export default PhysicalBoardGuard;
