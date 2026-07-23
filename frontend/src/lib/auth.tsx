'use client';

import React, {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  type ReactNode,
} from 'react';
import type { User, LoginPayload, RegisterPayload, RegistrationResponse } from '@/types';
import { authApi, setTokens, clearTokens } from '@/lib/api';

// ============================================================
// Auth Context Types
// ============================================================
interface AuthContextType {
  user: User | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  login: (payload: LoginPayload) => Promise<User>;
  loginWithGoogle: (credential: string, state: string) => Promise<User>;
  register: (payload: RegisterPayload) => Promise<RegistrationResponse>;
  logout: () => Promise<void>;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

// ============================================================
// Auth Provider
// ============================================================
export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  // Check existing session on mount
  useEffect(() => {
    authApi
        .refresh()
        .then((session) => {
          setTokens(session.access_token);
          return authApi.getMe();
        })
        .then((userData) => setUser(userData))
        .catch(() => {
          clearTokens();
          setUser(null);
        })
        .finally(() => setIsLoading(false));
  }, []);

  const login = useCallback(async (payload: LoginPayload) => {
    const response = await authApi.login(payload);
    setTokens(response.access_token);
    setUser(response.user);
    return response.user;
  }, []);

  const loginWithGoogle = useCallback(async (credential: string, state: string) => {
    const response = await authApi.googleLogin(credential, state);
    setTokens(response.access_token);
    setUser(response.user);
    return response.user;
  }, []);

  const register = useCallback(async (payload: RegisterPayload) => {
    const response = await authApi.register(payload);
    setUser(null);
    return response;
  }, []);

  const logout = useCallback(async () => {
    try {
      await authApi.logout();
    } catch (err) {
      console.error('Failed to revoke the server session', err);
    } finally {
      clearTokens();
      // Start the hard navigation before React can render the anonymous guard;
      // otherwise WebKit can race the guard's `/` redirect against `/login`.
      window.location.replace('/login');
    }
  }, []);

  const refreshUser = useCallback(async () => {
    try {
      const userData = await authApi.getMe();
      setUser(userData);
    } catch (err) {
      console.error('Failed to refresh user context', err);
    }
  }, []);

  return (
    <AuthContext.Provider
      value={{
        user,
        isLoading,
        isAuthenticated: !!user,
        login,
        loginWithGoogle,
        register,
        logout,
        refreshUser,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

// ============================================================
// useAuth Hook
// ============================================================
export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
