import { createContext, useContext, useState, useEffect, type ReactNode } from 'react';

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
    login: (username: string, password: string) => Promise<void>;
    logout: () => void;
    token: string | null;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider = ({ children }: { children: ReactNode }) => {
    const [user, setUser] = useState<User | null>(null);
    const [token, setToken] = useState<string | null>(() => localStorage.getItem('token'));

    useEffect(() => {
        if (token) {
            // Fetch user profile on mount if token exists
            fetchUserProfile(token);
        }
    }, [token]);

    const fetchUserProfile = async (authToken: string) => {
        try {
            const response = await fetch('/api/v1/auth/me', {
                headers: {
                    'Authorization': `Bearer ${authToken}`
                }
            });
            if (response.ok) {
                const userData = await response.json();
                setUser(userData);
            } else {
                // Token invalid
                logout();
            }
        } catch (error) {
            console.error("Failed to fetch user profile", error);
            logout();
        }
    };

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
            
            localStorage.setItem('token', newToken);
            setToken(newToken);
            // fetchUserProfile(newToken); // useEffect will trigger
        } catch (error) {
            throw error;
        }
    };

    const logout = () => {
        localStorage.removeItem('token');
        setToken(null);
        setUser(null);
    };

    return (
        <AuthContext.Provider value={{ user, isAuthenticated: !!user, login, logout, token }}>
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
