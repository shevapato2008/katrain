import { createContext, useContext, useState, useEffect, useCallback, type ReactNode } from 'react';
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
}

interface AuthContextType {
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
    // True until the mount-time session probe settles. Guards MUST wait for this
    // before redirecting, otherwise a valid persisted session (localStorage token
    // OR the shared box-SSO cookie) flashes the login page on every fresh page
    // load — e.g. re-entering 围棋, which is a full :8080→:8081 navigation.
    const [isLoading, setIsLoading] = useState(true);

    useEffect(() => {
        let cancelled = false;
        // Bound the probe so a hung /me never leaves the kiosk stuck on the
        // guard's loading spinner with no escape (falls through to login instead).
        const controller = new AbortController();
        const timeout = setTimeout(() => controller.abort(), 8000);
        const bootstrap = async () => {
            // This deletion is synchronous and precedes the first network call,
            // preventing an old JS Bearer token from overriding the box cookie.
            if (isStrictBoxKiosk) localStorage.removeItem('token');
            const stored = isStrictBoxKiosk ? null : localStorage.getItem('token');
            try {
                // Probe /me with the stored token if any; the browser also
                // auto-sends the shared 127.0.0.1 `sb_go_token` cookie.
                let usedToken: string | null = stored;
                let response = await fetch('/api/v1/auth/me', {
                    headers: stored ? { Authorization: `Bearer ${stored}` } : undefined,
                    signal: controller.signal,
                });
                // Stored token stale/expired? Drop it and retry cookie-only, so a
                // valid box-SSO session still restores instead of bouncing to login.
                if (!isStrictBoxKiosk && !response.ok && stored) {
                    localStorage.removeItem('token');
                    usedToken = null;
                    response = await fetch('/api/v1/auth/me', { signal: controller.signal });
                }
                if (cancelled) return;
                if (response.ok) {
                    setUser(await response.json());
                    setToken(usedToken);
                } else {
                    if (!isStrictBoxKiosk) localStorage.removeItem('token');
                    setToken(null);
                    setUser(null);
                }
            } catch {
                if (!cancelled) setUser(null);
            } finally {
                if (!cancelled) setIsLoading(false);
            }
        };
        bootstrap().finally(() => clearTimeout(timeout));
        return () => {
            cancelled = true;
            clearTimeout(timeout);
            controller.abort();
        };
    }, []);

    const login = async (username: string, password: string) => {
        if (isStrictBoxKiosk) {
            throw new Error('Direct login is disabled in strict box mode');
        }
        try {
            const response = await fetch('/api/v1/auth/login', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ username, password })
            });

            if (!response.ok) {
                throw new Error('Login failed');
            }

            const data = await response.json();
            const newToken = data.access_token;

            // 先把用户资料拉到再返回,确保 isAuthenticated(=!!user)在 navigate 前已为 true,
            // 否则首次登录会因 user 尚未加载被 AuthGuard 弹回登录页(需点两次)。
            // A non-strict direct login has the freshly issued token in memory;
            // use it for the active-session verification before persisting it.
            const meRes = await fetch('/api/v1/auth/me', {
                headers: { 'Authorization': `Bearer ${newToken}` }
            });
            if (!meRes.ok) {
                throw new Error('Login failed');
            }
            const userData = await meRes.json();

            localStorage.setItem('token', newToken);
            setUser(userData);
            setToken(newToken);
        } catch (error) {
            throw error;
        }
    };

    const logout = useCallback(async () => {
        // Call backend to cleanup sessions before clearing local state
        if (isStrictBoxKiosk || token) {
            try {
                // Strict box identity lives in the HttpOnly cookie, so omit
                // Bearer and let the browser send the same-origin cookie.
                // Galaxy and legacy kiosk retain their historical token path.
                await API.logout(isStrictBoxKiosk ? undefined : token ?? undefined);
            } catch (e) {
                console.warn("Logout request failed, proceeding with local cleanup");
            }
        }
        localStorage.removeItem('token');
        setToken(null);
        setUser(null);
    }, [token]);

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
            value={{ user, isAuthenticated: !!user, isLoading, login, logout, token, isGuest, isStrictBoxKiosk }}
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
