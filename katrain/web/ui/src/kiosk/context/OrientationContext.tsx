import { createContext, useContext, useState, useCallback, type ReactNode } from 'react';

export type Rotation = 0 | 90 | 180 | 270;

interface OrientationContextType {
  rotation: Rotation;
  isPortrait: boolean;
  setRotation: (rotation: Rotation) => void;
}

const OrientationContext = createContext<OrientationContextType | undefined>(undefined);

const STORAGE_KEY = 'katrain_kiosk_rotation';
const VALID: Rotation[] = [0, 90, 180, 270];

const readStored = (): Rotation => {
  const v = Number(localStorage.getItem(STORAGE_KEY));
  return VALID.includes(v as Rotation) ? (v as Rotation) : 0;
};

export const OrientationProvider = ({ children }: { children: ReactNode }) => {
  const [rotation, setRotationState] = useState<Rotation>(readStored);

  const setRotation = useCallback((r: Rotation) => {
    setRotationState(r);
    localStorage.setItem(STORAGE_KEY, String(r));
  }, []);

  // 棋智盒外壳屏幕为固定横屏(60° 倾斜立式),kiosk 一律按横屏布局,不再做竖屏/旋转判断。
  return (
    <OrientationContext.Provider value={{ rotation, isPortrait: false, setRotation }}>
      {children}
    </OrientationContext.Provider>
  );
};

export const useOrientation = () => {
  const ctx = useContext(OrientationContext);
  if (!ctx) throw new Error('useOrientation must be used within an OrientationProvider');
  return ctx;
};
