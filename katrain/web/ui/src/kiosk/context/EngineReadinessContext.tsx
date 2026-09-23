import {
  createContext,
  useContext,
} from 'react';

export type EngineReadiness = 'warming' | 'unavailable' | 'ready';

// Existing isolated kiosk tests and components retain their pre-gate behavior unless
// they are mounted under the kiosk application's provider.
export const EngineReadinessContext = createContext<EngineReadiness>('ready');

export const useEngineReadiness = () => useContext(EngineReadinessContext);
