import { createContext, useContext, useState, useCallback, type ReactNode } from 'react';

export type Rotation = 0 | 180;

interface OrientationContextType {
  rotation: Rotation;
  setRotation: (rotation: Rotation) => void;
}

const OrientationContext = createContext<OrientationContextType | undefined>(undefined);

const STORAGE_KEY = 'katrain_kiosk_rotation';
const VALID: Rotation[] = [0, 180];

// Clamp: stale 90/270 (portrait, removed 2026-07-06) or garbage → 0, and rewrite storage.
const readStored = (): Rotation => {
  const v = Number(localStorage.getItem(STORAGE_KEY));
  if (VALID.includes(v as Rotation)) return v as Rotation;
  localStorage.setItem(STORAGE_KEY, '0');
  return 0;
};

export const OrientationProvider = ({ children }: { children: ReactNode }) => {
  const [rotation, setRotationState] = useState<Rotation>(readStored);
  const setRotation = useCallback((r: Rotation) => {
    setRotationState(r);
    localStorage.setItem(STORAGE_KEY, String(r));
  }, []);
  return (
    <OrientationContext.Provider value={{ rotation, setRotation }}>
      {children}
    </OrientationContext.Provider>
  );
};

export const useOrientation = () => {
  const ctx = useContext(OrientationContext);
  if (!ctx) throw new Error('useOrientation must be used within an OrientationProvider');
  return ctx;
};
