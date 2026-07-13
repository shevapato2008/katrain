import { createContext, useContext, useState, useEffect, useCallback, type ReactNode } from 'react';
import { API } from '../api';

// Define User type matching backend response
interface User {
    id: number;
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
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider = ({ children }: { children: ReactNode }) => {
    const [user, setUser] = useState<User | null>(null);
    const [token, setToken] = useState<string | null>(() => localStorage.getItem('token'));
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
            const stored = localStorage.getItem('token');
            try {
                // Probe /me with the stored token if any; the browser also
                // auto-sends the shared 127.0.0.1 `sb_token` cookie.
                let usedToken: string | null = stored;
                let response = await fetch('/api/v1/auth/me', {
                    headers: stored ? { Authorization: `Bearer ${stored}` } : undefined,
                    signal: controller.signal,
                });
                // Stored token stale/expired? Drop it and retry cookie-only, so a
                // valid box-SSO session still restores instead of bouncing to login.
                if (!response.ok && stored) {
                    localStorage.removeItem('token');
                    usedToken = null;
                    response = await fetch('/api/v1/auth/me', { signal: controller.signal });
                }
                if (cancelled) return;
                if (response.ok) {
                    setUser(await response.json());
                    setToken(usedToken);
                } else {
                    localStorage.removeItem('token');
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
        if (token) {
            try {
                await API.logout(token);
            } catch (e) {
                console.warn("Logout request failed, proceeding with local cleanup");
            }
        }
        localStorage.removeItem('token');
        setToken(null);
        setUser(null);
    }, [token]);

    return (
        <AuthContext.Provider value={{ user, isAuthenticated: !!user, isLoading, login, logout, token }}>
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
