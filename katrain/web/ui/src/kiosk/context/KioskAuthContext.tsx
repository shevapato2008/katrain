import { createContext, useContext, useState, type ReactNode } from 'react';

interface KioskUser {
  name: string;
  rank: string;
}

interface KioskAuthState {
  isAuthenticated: boolean;
  user: KioskUser | null;
  login: (username: string, pin: string) => void;
  logout: () => void;
}

const KioskAuthContext = createContext<KioskAuthState | null>(null);

export const useKioskAuth = () => {
  const ctx = useContext(KioskAuthContext);
  if (!ctx) throw new Error('useKioskAuth must be used within KioskAuthProvider');
  return ctx;
};

export const KioskAuthProvider = ({ children }: { children: ReactNode }) => {
  const [user, setUser] = useState<KioskUser | null>(null);

  const login = (username: string, _pin: string) => {
    // Mock auth: always succeeds. Real auth integrated in Phase 4.
    setUser({ name: username || '棋手', rank: '1D' });
  };

  const logout = () => setUser(null);

  return (
    <KioskAuthContext.Provider value={{ isAuthenticated: !!user, user, login, logout }}>
      {children}
    </KioskAuthContext.Provider>
  );
};
