import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from 'react';
import { GeometryAPI, type GeometryPhase, type GeometryStatus } from '../../api/geometryApi';

const DEFAULT_STATUS: GeometryStatus = {
  phase: 'required',
  session_calibrated: false,
  last_valid: false,
  capabilities: { camera_ready: false, led_ready: false, geometry_ready: false },
};

interface GeometryContextValue {
  status: GeometryStatus;
  refresh: () => Promise<void>;
  startCalibration: (trigger: 'auto' | 'manual') => Promise<void>;
  cancelCalibration: () => Promise<void>;
}

const GeometryContext = createContext<GeometryContextValue | null>(null);
const ACTIVE: GeometryPhase[] = ['waiting_empty', 'dark_reference', 'flashing_corners', 'verifying', 'building_baseline'];

export const GeometryProvider = ({ children }: { children: ReactNode }) => {
  const [status, setStatus] = useState<GeometryStatus>(DEFAULT_STATUS);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const refresh = useCallback(async () => {
    try {
      setStatus(await GeometryAPI.status() as GeometryStatus);
    } catch (error) {
      if (error instanceof Error && error.message.includes('404')) {
        setStatus({ ...DEFAULT_STATUS, phase: 'disabled' });
      }
    }
  }, []);

  const startCalibration = useCallback(async (trigger: 'auto' | 'manual') => {
    setStatus(await GeometryAPI.calibrate(trigger));
  }, []);

  const cancelCalibration = useCallback(async () => {
    setStatus(await GeometryAPI.cancel());
  }, []);

  useEffect(() => {
    let cancelled = false;
    const poll = async () => {
      await refresh();
      if (cancelled) return;
      timerRef.current = setTimeout(poll, ACTIVE.includes(status.phase) ? 300 : 1000);
    };
    void poll();
    return () => {
      cancelled = true;
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [refresh, status.phase]);

  return (
    <GeometryContext.Provider value={{ status, refresh, startCalibration, cancelCalibration }}>
      {children}
    </GeometryContext.Provider>
  );
};

// eslint-disable-next-line react-refresh/only-export-components
export const useGeometry = () => {
  const context = useContext(GeometryContext);
  if (!context) throw new Error('useGeometry must be used within GeometryProvider');
  return context;
};

// eslint-disable-next-line react-refresh/only-export-components
export const useOptionalGeometry = () => useContext(GeometryContext);
