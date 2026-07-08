import { createContext, useContext, useState, type ReactNode } from 'react';

interface ImmersiveContextValue {
  immersive: boolean;
  setImmersive: (v: boolean) => void;
}

const ImmersiveContext = createContext<ImmersiveContextValue | undefined>(undefined);

export const ImmersiveProvider = ({ children }: { children: ReactNode }) => {
  const [immersive, setImmersive] = useState(false);
  return (
    <ImmersiveContext.Provider value={{ immersive, setImmersive }}>
      {children}
    </ImmersiveContext.Provider>
  );
};

export function useImmersive(): ImmersiveContextValue {
  const ctx = useContext(ImmersiveContext);
  if (!ctx) throw new Error('useImmersive must be used within an ImmersiveProvider');
  return ctx;
}
