import { createContext, useContext, useState, useEffect, useCallback, type ReactNode } from 'react';
import { API } from '../api';

// Define User type matching backend response
interface User {
    id: number;
    username: string;
    rank: string;
    credits: number;
    avatar_url?: string;
    // 只加这个布尔。原始手机号由后端 `repo.get_phone_e164` 单点取，**永不进 /auth/me**；
    // 掩码串 `phone_masked` 也只在 bind 成功那一次返回一次 ⇒ 设置页刷新后只能显示「已绑定」。
    // ⚠️ 这个 interface 是纯编译期断言：:70 与 :119 都是 `setUser(await res.json())`，
    // 生 JSON 直接进 state，运行时对 /auth/me 的真实返回没有任何约束。后端哪天漏发这一格，
    // TS 一句话都不会说，而 `!user.phone_bound` 会把已绑号的人判成未绑。
    phone_bound: boolean;
}

interface AuthContextType {
    user: User | null;
    isAuthenticated: boolean;
    isLoading: boolean;
    login: (username: string, password: string) => Promise<void>;
    loginByPhone: (challengeId: string, code: string) => Promise<void>;
    refreshUser: () => Promise<void>;
    logout: () => Promise<void>;
    token: string | null;
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

    // 与 login 同一条口径：**先把用户资料拉到再返回**，确保 isAuthenticated(=!!user)
    // 在 navigate 之前已为 true —— 否则首次登录会被 AuthGuard 弹回登录页（需点两次），
    // 见上面 login 里那段注释。写入全部排在可能抛出的那一步之后，失败时不留半截状态。
    const loginByPhone = async (challengeId: string, code: string) => {
        if (isStrictBoxKiosk) {
            // D-U3「盒子什么都不改」：盒端身份是云端账号经 box_sso_bootstrap 交下来的，
            // 本地再开一条发码登录会造出第二个身份来源。与 login 同一条口径。
            throw new Error('Direct login is disabled in strict box mode');
        }
        // 注意：/auth/phone/login 只回 {access_token, token_type}，**没有 refresh_token**
        // （/auth/login 有）。本文件本来也不读 refresh_token，所以没有行为差异；
        // 但手机登录拿到的是纯 Bearer 会话，7 天到期后只能重新收码。
        const data = await API.loginByPhone(challengeId, code);
        const newToken = data.access_token;
        const meRes = await fetch('/api/v1/auth/me', {
            headers: { Authorization: `Bearer ${newToken}` },
        });
        if (!meRes.ok) {
            throw new Error('Login failed');
        }
        const userData = await meRes.json();
        localStorage.setItem('token', newToken);
        setUser(userData);
        setToken(newToken);
    };

    // 绑定手机成功后要让 user.phone_bound 当场翻面（Task 16 的免费额度文案与侧栏入口都读它）。
    // 严格盒端没有 Bearer，靠同源 cookie，所以头是可选的 —— 这里的三元由编译期常量
    // `isStrictBoxKiosk` 决定，严格档会把 localStorage 那一支整个 DCE 掉，
    // 这正是 scripts/verify-kiosk.sh:44-57 那道「dist 里不许出现 localStorage.getItem('token')」
    // 的闸能过的原因。改成运行时判断会当场让 build:smartbox-kiosk-2d 变红。
    //
    // **失败要抛，不能静默不动。** 原计划写的是 `if (res.ok) setUser(...)`：那样刷新失败时
    // 什么都不做也什么都不说，Task 16 的「绑定成功后文案翻面」会静默不翻，用户看到的是
    // 「明明绑成功了却还提示我去绑」。抛出去，让调用方决定要不要提示或重试。
    // （旧 user 保留不动 —— 一次 /me 失败不构成把人踢下线的理由。）
    const refreshUser = useCallback(async () => {
        const stored = isStrictBoxKiosk ? null : localStorage.getItem('token');
        const res = await fetch('/api/v1/auth/me', {
            headers: stored ? { Authorization: `Bearer ${stored}` } : undefined,
        });
        if (!res.ok) {
            throw new Error(`Failed to refresh user ${res.status}`);
        }
        setUser(await res.json());
    }, []);

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

    return (
        <AuthContext.Provider value={{ user, isAuthenticated: !!user, isLoading, login, loginByPhone, refreshUser, logout, token }}>
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
