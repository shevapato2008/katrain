import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from 'react';
import { useLocation } from 'react-router-dom';
import { API, type GameType } from '../../api';
import { GeometryAPI, type GeometryPhase, type GeometryStatus } from '../../api/geometryApi';

const DEFAULT_STATUS: GeometryStatus = {
  phase: 'required',
  session_calibrated: false,
  last_valid: false,
  capabilities: { camera_ready: false, led_ready: null, geometry_ready: false },
};

interface GeometryContextValue {
  status: GeometryStatus;
  /**
   * 第一次问过服务端了没有。
   *
   * `DEFAULT_STATUS` 的摄像头与几何 capability 是 `false`，LED 是未知；直接画状态格,
   * 就会在**还没问过**的时候说「摄像头未连接」。而「还没读到状态」和「读到了没连上」
   * 是两回事 —— `goHardware.ts` 的注释早就把这条判过一次(值给「—」、不给 tone)。
   * 少了这个布尔,那条注释在标定屏上就落不了地。
   */
  loaded: boolean;
  refresh: () => Promise<void>;
  startCalibration: (trigger: 'auto' | 'manual', resetSessionId?: string, gameType?: GameType) => Promise<void>;
  /** Called only after the original game's vision bind succeeds. */
  completeRecalibration: (sessionId: string) => Promise<void>;
  confirmExisting: () => Promise<void>;
  cancelCalibration: () => Promise<void>;
  relocate: () => Promise<void>;
}

const GeometryContext = createContext<GeometryContextValue | null>(null);
const ACTIVE: GeometryPhase[] = [
  'waiting_empty', 'dark_reference', 'converging_exposure', 'flashing_corners', 'verifying', 'building_baseline',
];

export const GeometryProvider = ({ children }: { children: ReactNode }) => {
  const { pathname } = useLocation();
  const pendingReset = useRef<{ sessionId: string; revision: number; pathname: string; gameType?: GameType } | null>(null);
  const statusRef = useRef<GeometryStatus>(DEFAULT_STATUS);
  const pathnameRef = useRef(pathname);
  const [status, setStatus] = useState<GeometryStatus>(DEFAULT_STATUS);
  const [loaded, setLoaded] = useState(false);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const applyStatus = useCallback((next: GeometryStatus) => {
    statusRef.current = next;
    if (['failed', 'cancelled', 'disabled'].includes(next.phase)) pendingReset.current = null;
    setStatus(next);
  }, []);

  // A deferred reset belongs to the route where the user requested it.
  useEffect(() => {
    pathnameRef.current = pathname;
    if (pendingReset.current?.pathname !== pathname) pendingReset.current = null;
  }, [pathname]);

  const completeRecalibration = useCallback(async (sessionId: string) => {
    const pending = pendingReset.current;
    const current = statusRef.current;
    if (!pending) return;
    if (pending.sessionId !== sessionId || pending.pathname !== pathnameRef.current) {
      pendingReset.current = null;
      return;
    }
    if (current.phase !== 'ready' || !current.session_calibrated
      || !current.capabilities.geometry_ready || (current.geometry_revision ?? 0) <= pending.revision) return;
    pendingReset.current = null;
    // Local bind prepares a fresh reference; RESET_SYNC would immediately invalidate it.
    if (pending.gameType !== 'pvp_local') await API.visionResetSync();
  }, []);

  const refresh = useCallback(async () => {
    try {
      applyStatus(await GeometryAPI.status());
      setLoaded(true);
    } catch (error) {
      pendingReset.current = null;
      if (error instanceof Error && error.message.includes('404')) {
        // 404 = 这台盒子压根没起 capture 服务。**这是一个读到了的结论**,不是没读到 ⇒ 也算 loaded。
        applyStatus({ ...DEFAULT_STATUS, phase: 'disabled' });
        setLoaded(true);
      } else {
        setStatus((previous) => ({
          ...previous, capabilities: { ...previous.capabilities, led_ready: null },
        }));
      }
    }
  }, [applyStatus]);

  const startCalibration = useCallback(async (trigger: 'auto' | 'manual', resetSessionId?: string, gameType?: GameType) => {
    pendingReset.current = resetSessionId ? {
      sessionId: resetSessionId, gameType, revision: statusRef.current.geometry_revision ?? 0, pathname: pathnameRef.current,
    } : null;
    try {
      applyStatus(await GeometryAPI.calibrate(trigger));
    } catch (error) {
      pendingReset.current = null;
      throw error;
    }
  }, [applyStatus]);

  const cancelCalibration = useCallback(async () => {
    pendingReset.current = null;
    applyStatus(await GeometryAPI.cancel());
  }, [applyStatus]);

  const confirmExisting = useCallback(async () => {
    pendingReset.current = null;
    applyStatus(await GeometryAPI.confirmExisting());
  }, [applyStatus]);

  const relocate = useCallback(async () => {
    pendingReset.current = null;
    applyStatus(await GeometryAPI.relocate());
  }, [applyStatus]);

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
    <GeometryContext.Provider value={{ status, loaded, refresh, startCalibration, completeRecalibration, confirmExisting, cancelCalibration, relocate }}>
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
