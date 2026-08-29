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
  /**
   * 第一次问过服务端了没有。
   *
   * **不是锦上添花:`DEFAULT_STATUS` 的三个 capability 全是 `false`**,直接拿去画状态格,
   * 就会在**还没问过**的时候说「摄像头未连接」。而「还没读到状态」和「读到了没连上」
   * 是两回事 —— `goHardware.ts` 的注释早就把这条判过一次(值给「—」、不给 tone)。
   * 少了这个布尔,那条注释在标定屏上就落不了地。
   */
  loaded: boolean;
  refresh: () => Promise<void>;
  startCalibration: (trigger: 'auto' | 'manual') => Promise<void>;
  confirmExisting: () => Promise<void>;
  cancelCalibration: () => Promise<void>;
}

const GeometryContext = createContext<GeometryContextValue | null>(null);
const ACTIVE: GeometryPhase[] = ['waiting_empty', 'dark_reference', 'flashing_corners', 'verifying', 'building_baseline'];

export const GeometryProvider = ({ children }: { children: ReactNode }) => {
  const [status, setStatus] = useState<GeometryStatus>(DEFAULT_STATUS);
  const [loaded, setLoaded] = useState(false);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const refresh = useCallback(async () => {
    try {
      setStatus(await GeometryAPI.status() as GeometryStatus);
      setLoaded(true);
    } catch (error) {
      if (error instanceof Error && error.message.includes('404')) {
        // 404 = 这台盒子压根没起 capture 服务。**这是一个读到了的结论**,不是没读到 ⇒ 也算 loaded。
        setStatus({ ...DEFAULT_STATUS, phase: 'disabled' });
        setLoaded(true);
      }
      // 其它错误(502 / 超时)**故意不置 loaded** —— 那才是「还没问出来」。
    }
  }, []);

  const startCalibration = useCallback(async (trigger: 'auto' | 'manual') => {
    setStatus(await GeometryAPI.calibrate(trigger));
  }, []);

  const cancelCalibration = useCallback(async () => {
    setStatus(await GeometryAPI.cancel());
  }, []);

  const confirmExisting = useCallback(async () => {
    setStatus(await GeometryAPI.confirmExisting());
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
    <GeometryContext.Provider value={{ status, loaded, refresh, startCalibration, confirmExisting, cancelCalibration }}>
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
