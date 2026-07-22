"use client";

import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";

import { fetchCurrentUser, login as apiLogin, logout as apiLogout, registerUser } from "@/lib/api/auth";
import { API_BASE_URL, setAccessToken } from "@/lib/api/client";
import type { User } from "@/lib/types";

interface AuthContextValue {
  user: User | null;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, fullName?: string) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const response = await fetch(`${API_BASE_URL}/auth/refresh`, {
          method: "POST",
          credentials: "include",
        });
        if (response.ok) {
          const data = await response.json();
          setAccessToken(data.access_token);
          const currentUser = await fetchCurrentUser();
          setUser(currentUser);
        }
      } catch {
        // no valid session, stay logged out
      } finally {
        setIsLoading(false);
      }
    })();
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const tokens = await apiLogin(email, password);
    setAccessToken(tokens.access_token);
    const currentUser = await fetchCurrentUser();
    setUser(currentUser);
  }, []);

  const register = useCallback(async (email: string, password: string, fullName?: string) => {
    await registerUser(email, password, fullName);
    await login(email, password);
  }, [login]);

  const logout = useCallback(async () => {
    await apiLogout();
    setAccessToken(null);
    setUser(null);
  }, []);

  return (
    <AuthContext.Provider value={{ user, isLoading, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
