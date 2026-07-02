import { createContext, useContext, useState, useEffect, useCallback, type ReactNode } from 'react';
import { API, type VisionStatusResponse } from '../../api';

export interface VisionStatus {
  enabled: boolean;
  cameraConnected: boolean;
  poseLocked: boolean;
  syncState: string;
  boundSessionId: string | null;
  recognitionReady: boolean;
}

interface VisionContextType {
  visionStatus: VisionStatus;
  isVisionEnabled: boolean;
  refreshStatus: () => Promise<void>;
}

const DEFAULT_STATUS: VisionStatus = {
  enabled: false,
  cameraConnected: false,
  poseLocked: false,
  syncState: 'idle',
  boundSessionId: null,
  recognitionReady: false,
};

const VisionContext = createContext<VisionContextType | undefined>(undefined);

const POLL_INTERVAL_MS = 3000;

const mapResponse = (r: VisionStatusResponse): VisionStatus => ({
  enabled: r.enabled,
  cameraConnected: r.camera_connected,
  poseLocked: r.pose_locked,
  syncState: r.sync_state,
  boundSessionId: r.bound_session_id,
  recognitionReady: r.recognition_ready ?? false,
});

export const VisionProvider = ({ children }: { children: ReactNode }) => {
  const [visionStatus, setVisionStatus] = useState<VisionStatus>(DEFAULT_STATUS);

  const refreshStatus = useCallback(async () => {
    try {
      const response = await API.visionStatus();
      setVisionStatus(mapResponse(response));
    } catch (err) {
      console.error('Failed to fetch vision status', err);
      // Keep the last known status on transient errors rather than
      // resetting to defaults, so the UI does not flicker.
    }
  }, []);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- initial network poll is asynchronous
    refreshStatus();
    const interval = setInterval(refreshStatus, POLL_INTERVAL_MS);
    return () => clearInterval(interval);
  }, [refreshStatus]);

  return (
    <VisionContext.Provider value={{ visionStatus, isVisionEnabled: visionStatus.enabled, refreshStatus }}>
      {children}
    </VisionContext.Provider>
  );
};

// eslint-disable-next-line react-refresh/only-export-components
export const useVision = () => {
  const ctx = useContext(VisionContext);
  if (!ctx) throw new Error('useVision must be used within a VisionProvider');
  return ctx;
};

// eslint-disable-next-line react-refresh/only-export-components
export const useOptionalVision = () => useContext(VisionContext);
