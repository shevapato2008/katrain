import { createContext, useContext, useState, useEffect, useCallback, useRef, type ReactNode } from 'react';
import { API } from '../api';
import { setKioskIdentity } from '../kiosk/storage/kioskActivityStorage';

// Define User type matching backend response
interface User {
    id: number;
    // Stable per-account identity key (assigned at registration; never reused). This is the
    // ONLY identity key the client-side storage isolation shim (kioskActivityStorage) trusts
    // to namespace localStorage — `id` is not used for that because it is not guaranteed
    // stable across the box-SSO / cross-platform identity paths the way `uuid` is.
    uuid?: string;
    username: string;
    rank: string;
    credits: number;
    avatar_url?: string;
    // Only controls editing UI. The backend write routes enforce admin access.
    is_admin?: boolean;
}

export type AuthStatus = 'checking' | 'authenticated' | 'guest' | 'expired' | 'unavailable';

interface AuthContextType {
    status: AuthStatus;
    retry: () => Promise<void>;
    identityKey: string | null;
    user: User | null;
    isAuthenticated: boolean;
    isLoading: boolean;
    login: (username: string, password: string) => Promise<void>;
    logout: () => Promise<void>;
    token: string | null;
    // True for the shared zero-persistence `guest` account (box-SSO guest mode).
    isGuest: boolean;
    // True only for a kiosk-2d build with VITE_BOX_SSO_STRICT=true — the box
    // identity lives solely in the HttpOnly cookie and direct login/registration
    // forms must not be shown; callers redirect to the setup-wizard instead.
    isStrictBoxKiosk: boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

// Box SSO strictness is deliberately independent from the kiosk UI boundary.
// Legacy kiosk and Galaxy builds retain their historical Bearer/localStorage
// contract; only a build with both flags authenticates solely through the
// HttpOnly `sb_go_token` cookie (whose value is never visible to this module).
const isKioskBuild = __KIOSK_2D_ONLY__;
const isStrictBoxKiosk = isKioskBuild && import.meta.env.VITE_BOX_SSO_STRICT === 'true';

export const AuthProvider = ({ children }: { children: ReactNode }) => {
    const [user, setUser] = useState<User | null>(null);
    const [token, setToken] = useState<string | null>(() =>
        isStrictBoxKiosk ? null : localStorage.getItem('token')
    );
    const [status, setStatus] = useState<AuthStatus>('checking');
    const generation = useRef(0);
    const activeController = useRef<AbortController | null>(null);
    const activeProbe = useRef<Promise<void> | null>(null);
    const hadIdentity = useRef(false);
    const isLoading = status === 'checking';

    const invalidatePending = useCallback(() => {
        generation.current += 1;
        activeController.current?.abort();
        activeController.current = null;
        activeProbe.current = null;
        return generation.current;
    }, []);

    const retry = useCallback((): Promise<void> => {
        // One probe owns the entire Bearer -> cookie fallback, including its timeout.
        if (activeProbe.current) return activeProbe.current;
        const requestGeneration = generation.current;
        const controller = new AbortController();
        activeController.current = controller;
        const current = () => generation.current === requestGeneration && !controller.signal.aborted;
        const stored = isStrictBoxKiosk ? null : localStorage.getItem('token');
        let usedToken = stored;
        const hadCredential = Boolean(stored) || hadIdentity.current;
        setUser(null);
        setStatus('checking');
        setKioskIdentity(null, false);

        let timeout: ReturnType<typeof setTimeout>;
        const deadline = new Promise<never>((_, reject) => {
            timeout = setTimeout(() => {
                controller.abort();
                reject(new Error('Authentication probe timed out'));
            }, 8000);
        });
        const probe = async () => {
            let response = await fetch('/api/v1/auth/me', {
                headers: stored ? { Authorization: `Bearer ${stored}` } : undefined,
                signal: controller.signal,
            });
            if (!current()) return;
            // Only a real /me 401 invalidates a Bearer. Service errors, permissions
            // failures and network errors retain it for the next explicit retry.
            if (!isStrictBoxKiosk && response.status === 401 && stored) {
                localStorage.removeItem('token');
                setToken(null);
                usedToken = null;
                response = await fetch('/api/v1/auth/me', { signal: controller.signal });
                if (!current()) return;
            }
            if (response.ok) {
                const restoredUser: User = await response.json();
                if (!current()) return;
                hadIdentity.current = true;
                setUser(restoredUser);
                setToken(usedToken);
                setStatus(restoredUser.username === 'guest' ? 'guest' : 'authenticated');
            } else if (response.status === 401) {
                setToken(null);
                setStatus(hadCredential ? 'expired' : 'guest');
            } else {
                setStatus('unavailable');
            }
        };
        const pending = Promise.race([probe(), deadline]).catch(() => {
            // Abort may mean either the bounded deadline or a newer login/logout.
            if (generation.current === requestGeneration) setStatus('unavailable');
        }).finally(() => {
            clearTimeout(timeout!);
            if (activeController.current === controller) {
                activeController.current = null;
                activeProbe.current = null;
            }
        });
        activeProbe.current = pending;
        return pending;
    }, []);

    useEffect(() => {
        // Strict builds never read a JS credential or override the HttpOnly cookie.
        if (isStrictBoxKiosk) localStorage.removeItem('token');
        void retry();
        return () => { invalidatePending(); };
    }, [retry, invalidatePending]);

    const login = async (username: string, password: string) => {
        if (isStrictBoxKiosk) throw new Error('Direct login is disabled in strict box mode');
        const requestGeneration = invalidatePending();
        try {
            const response = await fetch('/api/v1/auth/login', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ username, password }),
            });
            if (!response.ok) throw new Error('Login failed');
            const data = await response.json();
            const newToken = data.access_token;
            const meRes = await fetch('/api/v1/auth/me', {
                headers: { Authorization: `Bearer ${newToken}` },
            });
            if (!meRes.ok) throw new Error('Login failed');
            const userData: User = await meRes.json();
            // A logout or newer login owns the state even if this request settles later.
            if (generation.current !== requestGeneration) return;
            localStorage.setItem('token', newToken);
            hadIdentity.current = true;
            setUser(userData);
            setToken(newToken);
            setStatus(userData.username === 'guest' ? 'guest' : 'authenticated');
        } catch (error) {
            if (generation.current === requestGeneration && status === 'checking') setStatus('unavailable');
            throw error;
        }
    };

    const logout = useCallback(async () => {
        invalidatePending();
        // Remove identity before awaiting network cleanup so private children unmount now.
        hadIdentity.current = false;
        localStorage.removeItem('token');
        setToken(null);
        setUser(null);
        setStatus('guest');
        setKioskIdentity(null, false);
        if (isStrictBoxKiosk || token || user) {
            try {
                await API.logout(isStrictBoxKiosk ? undefined : token ?? undefined);
            } catch {
                console.warn('Logout request failed, proceeding with local cleanup');
            }
        }
    }, [token, user, invalidatePending]);

    const isGuest = user?.username === 'guest';

    // Push the resolved identity into the kiosk storage-isolation singleton — but ONLY once
    // resolved (never while isLoading). This is what lets provider-less/module-level call
    // sites (activeSession.ts, the TsumegoProgressContext default value, baipuApi.ts) inherit
    // "empty until resolved" for free: until this fires, kioskActivityStorage's singleton
    // stays on its own safe ephemeral default, so no read there can ever surface a prior
    // real user's (or the legacy unscoped) data during the first-paint window.
    useEffect(() => {
        if (isLoading) return;
        setKioskIdentity(isGuest ? null : (user?.uuid ?? null), isGuest);
    }, [isLoading, isGuest, user]);

    return (
        <AuthContext.Provider
            value={{ user, isAuthenticated: !!user, isLoading, status, retry,
                identityKey: user ? user.uuid ?? `${user.id}:${user.username}` : null,
                login, logout, token, isGuest, isStrictBoxKiosk }}
        >
            {children}
        </AuthContext.Provider>
    );
};

export const useAuth = () => {
    const context = useContext(AuthContext);
    if (context === undefined) {
        throw new Error('useAuth must be used within an AuthProvider');
    }
    return context;
};
