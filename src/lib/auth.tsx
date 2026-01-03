'use client';

import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8080';

// Types
interface User {
    id: string;
    email: string;
    full_name: string;
    subscription_status: string;
    started_trial_at?: string;
    started_pro_at?: string;
    trial_ends_at?: string;
    is_subscription_active: boolean;
    subject_matters: Array<{
        id: number;
        code: string;
        name_en: string;
        name_he: string;
    }>;
    created_at: string;
}

interface AuthState {
    user: User | null;
    token: string | null;
    isLoading: boolean;
    isAuthenticated: boolean;
}

interface AuthContextType extends AuthState {
    login: (email: string, password: string) => Promise<void>;
    signup: (email: string, password: string, fullName: string) => Promise<void>;
    logout: () => void;
    refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

// Storage keys
const TOKEN_KEY = 'pupal_auth_token';
const USER_KEY = 'pupal_user';

// Auth Provider Component
export function AuthProvider({ children }: { children: React.ReactNode }) {
    const [state, setState] = useState<AuthState>({
        user: null,
        token: null,
        isLoading: true,
        isAuthenticated: false,
    });

    // Initialize auth state from localStorage
    useEffect(() => {
        const storedToken = localStorage.getItem(TOKEN_KEY);
        const storedUser = localStorage.getItem(USER_KEY);

        if (storedToken && storedUser) {
            try {
                const user = JSON.parse(storedUser);
                setState({
                    user,
                    token: storedToken,
                    isLoading: false,
                    isAuthenticated: true,
                });
                // Verify token is still valid
                verifyToken(storedToken);
            } catch {
                // Invalid stored data, clear it
                localStorage.removeItem(TOKEN_KEY);
                localStorage.removeItem(USER_KEY);
                setState({
                    user: null,
                    token: null,
                    isLoading: false,
                    isAuthenticated: false,
                });
            }
        } else {
            setState(prev => ({ ...prev, isLoading: false }));
        }
    }, []);

    // Verify token with backend
    const verifyToken = async (token: string) => {
        try {
            const response = await fetch(`${API_BASE}/api/v0/auth/me`, {
                headers: {
                    Authorization: `Bearer ${token}`,
                },
            });

            if (!response.ok) {
                // Token is invalid, logout
                logout();
                return;
            }

            const user = await response.json();
            localStorage.setItem(USER_KEY, JSON.stringify(user));
            setState(prev => ({ ...prev, user }));
        } catch {
            // Network error, keep current state
        }
    };

    // Login
    const login = useCallback(async (email: string, password: string) => {
        const response = await fetch(`${API_BASE}/api/v0/auth/login`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ email, password }),
        });

        if (!response.ok) {
            const error = await response.json().catch(() => ({ detail: 'שגיאה בהתחברות' }));
            throw new Error(error.detail || 'שגיאה בהתחברות');
        }

        const data = await response.json();

        // Store in localStorage
        localStorage.setItem(TOKEN_KEY, data.access_token);
        localStorage.setItem(USER_KEY, JSON.stringify(data.user));

        setState({
            user: data.user,
            token: data.access_token,
            isLoading: false,
            isAuthenticated: true,
        });
    }, []);

    // Signup
    const signup = useCallback(async (email: string, password: string, fullName: string) => {
        const response = await fetch(`${API_BASE}/api/v0/auth/signup`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ email, password, full_name: fullName }),
        });

        if (!response.ok) {
            const error = await response.json().catch(() => ({ detail: 'שגיאה ביצירת החשבון' }));
            throw new Error(error.detail || 'שגיאה ביצירת החשבון');
        }

        const data = await response.json();

        // Store in localStorage
        localStorage.setItem(TOKEN_KEY, data.access_token);
        localStorage.setItem(USER_KEY, JSON.stringify(data.user));

        setState({
            user: data.user,
            token: data.access_token,
            isLoading: false,
            isAuthenticated: true,
        });
    }, []);

    // Logout
    const logout = useCallback(() => {
        localStorage.removeItem(TOKEN_KEY);
        localStorage.removeItem(USER_KEY);

        setState({
            user: null,
            token: null,
            isLoading: false,
            isAuthenticated: false,
        });
    }, []);

    // Refresh user data
    const refreshUser = useCallback(async () => {
        if (!state.token) return;

        try {
            const response = await fetch(`${API_BASE}/api/v0/auth/me`, {
                headers: {
                    Authorization: `Bearer ${state.token}`,
                },
            });

            if (response.ok) {
                const user = await response.json();
                localStorage.setItem(USER_KEY, JSON.stringify(user));
                setState(prev => ({ ...prev, user }));
            }
        } catch {
            // Ignore errors
        }
    }, [state.token]);

    return (
        <AuthContext.Provider value={{ ...state, login, signup, logout, refreshUser }}>
            {children}
        </AuthContext.Provider>
    );
}

// Hook for using auth context
export function useAuth() {
    const context = useContext(AuthContext);
    if (context === undefined) {
        throw new Error('useAuth must be used within an AuthProvider');
    }
    return context;
}

// Helper to get auth token for API calls
export function getAuthToken(): string | null {
    if (typeof window === 'undefined') return null;
    return localStorage.getItem(TOKEN_KEY);
}

// Helper to get auth headers for API calls
export function getAuthHeaders(): Record<string, string> {
    const token = getAuthToken();
    if (!token) return {};
    return { Authorization: `Bearer ${token}` };
}
