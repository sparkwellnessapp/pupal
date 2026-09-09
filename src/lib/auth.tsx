'use client';

import React, { createContext, useContext, useState, useEffect, useCallback, useRef } from 'react';

import { shouldRenew } from './session';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8080';

// NOTE (PR-2): the auth calls in this file deliberately use RAW fetch and do NOT
// route through apiFetch. A wrong password legitimately returns 401 — if login
// threw ApiAuthError it would be reported as "session expired" and would trigger
// the stash-and-logout flow on a failed login attempt. Auth is the one place where
// a 401 is a normal answer, not a session failure.

/** How often we re-check whether the token is close enough to expiry to renew.
 * Cheap: it only decodes a local JWT; the network call happens at most once per
 * renewal window. */
const RENEWAL_CHECK_INTERVAL_MS = 15 * 60 * 1000;   // 15 min

// Types
export interface User {
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
    // ── onboarding (migration 022) ──────────────────────────────────────────
    /** 'female' | 'male' | 'unspecified'. Collected, not yet read by any copy. */
    gender?: string | null;
    /** NULL ⇒ has not finished onboarding. The gate keys off exactly this. */
    onboarding_completed_at?: string | null;
    schools?: Array<{
        id: string;
        name: string;
        city?: string | null;
        /** סמל מוסד — the institution's identity; null for a free-text school. */
        ministry_symbol?: string | null;
    }>;
    /** == users.school_id, the PR-G6 attribution key; always schools[0]. */
    primary_school_id?: string | null;
}

interface AuthState {
    user: User | null;
    token: string | null;
    isLoading: boolean;
    isAuthenticated: boolean;
}

/** Thrown by login() when the password was RIGHT but the address is unproven.
 *  A distinct type, not a message match: the caller must open the verification
 *  panel rather than tell her she mistyped her password. */
export class EmailNotVerifiedError extends Error {
    constructor(public readonly email: string) {
        super('email not verified');
        this.name = 'EmailNotVerifiedError';
    }
}

interface AuthContextType extends AuthState {
    login: (email: string, password: string) => Promise<void>;
    /** [024] Creates the account and emails a code. Returns WITHOUT a session —
     *  an address nobody proved gets none. `verifyEmail` is what signs her in. */
    signup: (email: string, password: string, fullName: string) => Promise<void>;
    verifyEmail: (email: string, code: string) => Promise<void>;
    resendCode: (email: string) => Promise<void>;
    /** Adopts a session minted by Sign in with Google. */
    adoptSession: (accessToken: string, user: User) => void;
    logout: () => void;
    refreshUser: () => Promise<void>;
    /**
     * Adopt a profile payload the caller ALREADY holds (every onboarding write
     * answers with the full profile). refreshUser swallows its errors by design,
     * so relying on it to land the completion stamp would risk the gate bouncing
     * the teacher straight back into the flow she just finished.
     */
    applyUser: (user: User) => void;
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
            // 403 means the credentials were CORRECT and the address is not yet
            // proven. Typed, so the caller opens the code panel instead of
            // rendering "wrong password" over a right one.
            if (response.status === 403) throw new EmailNotVerifiedError(email);
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

        // [024] NO SESSION HERE. The account exists and is unusable until the
        // code is redeemed (owner ruling A4), so nothing is stored and nothing
        // about `state` changes. Reading `access_token` from this response is
        // what the old client did and is exactly the bug this comment prevents.
        await response.json().catch(() => ({}));
    }, []);

    /** Adopt a session the caller already holds — Sign in with Google and
     *  verify-email both come back with a full {token, user} pair, and
     *  re-fetching it would only add a way to fail. */
    const adoptSession = useCallback((accessToken: string, user: User) => {
        try {
            localStorage.setItem(TOKEN_KEY, accessToken);
            localStorage.setItem(USER_KEY, JSON.stringify(user));
        } catch {
            // A blocked localStorage must not stop the session existing in memory.
        }
        setState({ user, token: accessToken, isLoading: false, isAuthenticated: true });
    }, []);

    /** [024] Redeem a verification code. THIS is where a signup gets its session. */
    const verifyEmail = useCallback(async (email: string, code: string) => {
        const response = await fetch(`${API_BASE}/api/v0/auth/verify-email`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email, code }),
        });

        if (!response.ok) {
            const error = await response.json().catch(() => ({ detail: 'הקוד שגוי או שפג תוקפו' }));
            throw new Error(error.detail || 'הקוד שגוי או שפג תוקפו');
        }

        const data = await response.json();
        adoptSession(data.access_token, data.user);
        // Declared ABOVE this callback on purpose: a dependency array is
        // evaluated during render, so naming a `const` defined further down
        // would be a TDZ ReferenceError, not a lint nit.
    }, [adoptSession]);

    /** Ask for a new code. Always resolves — the endpoint answers 202 for every
     *  address by design, so a rejection here would be inventing information the
     *  server deliberately refuses to give. */
    const resendCode = useCallback(async (email: string) => {
        await fetch(`${API_BASE}/api/v0/auth/resend-code`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email }),
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

    // Refresh user data (profile only — NOT the token; see renewToken below)
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

    const applyUser = useCallback((user: User) => {
        try {
            localStorage.setItem(USER_KEY, JSON.stringify(user));
        } catch {
            // A full/blocked localStorage must not stop the session from
            // reflecting the new profile in memory.
        }
        setState(prev => ({ ...prev, user }));
    }, []);

    // ── PR-2: sliding renewal (C9) ──────────────────────────────────────────
    // POST /auth/refresh already existed and nothing called it. It is gated on a
    // VALID token, so it can only renew BEFORE expiry — which is exactly what we
    // do. With a 7-day TTL and a 48h renewal window, any teacher who opens the app
    // even once every 5 days never sees an expiry. Zero backend change.
    const renewing = useRef(false);

    const renewToken = useCallback(async (token: string) => {
        if (renewing.current) return;
        renewing.current = true;
        try {
            const response = await fetch(`${API_BASE}/api/v0/auth/refresh`, {
                method: 'POST',
                headers: { Authorization: `Bearer ${token}` },
            });
            if (!response.ok) return;    // still valid until it isn't; never log out from here
            const data = await response.json();
            if (!data?.access_token) return;
            localStorage.setItem(TOKEN_KEY, data.access_token);
            if (data.user) localStorage.setItem(USER_KEY, JSON.stringify(data.user));
            setState(prev => ({
                ...prev,
                token: data.access_token,
                user: data.user ?? prev.user,
            }));
        } catch {
            // Offline / transient — the token is still valid; try again next tick.
        } finally {
            renewing.current = false;
        }
    }, []);

    // Check on mount and on a low-frequency interval while the tab lives.
    useEffect(() => {
        if (!state.isAuthenticated) return;

        const check = () => {
            const token = localStorage.getItem(TOKEN_KEY);
            if (token && shouldRenew(token)) void renewToken(token);
        };
        check();
        const id = setInterval(check, RENEWAL_CHECK_INTERVAL_MS);
        // Also re-check when the tab regains focus — a laptop reopened after days
        // is exactly the case where the token drifted into the renewal window.
        window.addEventListener('focus', check);
        return () => {
            clearInterval(id);
            window.removeEventListener('focus', check);
        };
    }, [state.isAuthenticated, renewToken]);

    return (
        <AuthContext.Provider value={{ ...state, login, signup, verifyEmail, resendCode, adoptSession, logout, refreshUser, applyUser }}>
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
