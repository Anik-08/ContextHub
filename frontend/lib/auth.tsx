"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { api } from "@/lib/api";
import type { AuthResponse, User } from "@/lib/types";

const TOKEN_KEY = "contexthub_token";

type AuthStatus = "loading" | "authenticated" | "unauthenticated";

type AuthContextValue = {
  user: User | null;
  token: string | null;
  status: AuthStatus;
  login: (email: string, password: string) => Promise<User>;
  register: (email: string, password: string, name: string) => Promise<User>;
  logout: () => void;
};

const AuthContext = createContext<AuthContextValue | null>(null);

function readStoredToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(TOKEN_KEY);
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(readStoredToken);
  const [status, setStatus] = useState<AuthStatus>(
    readStoredToken() ? "loading" : "unauthenticated",
  );

  useEffect(() => {
    if (!token) return;
    let cancelled = false;

    api<User>("/api/auth/me", { token })
      .then((me) => {
        if (cancelled) return;
        setUser(me);
        setStatus("authenticated");
      })
      .catch(() => {
        if (cancelled) return;
        window.localStorage.removeItem(TOKEN_KEY);
        setToken(null);
        setUser(null);
        setStatus("unauthenticated");
      });

    return () => {
      cancelled = true;
    };
  }, [token]);

  const persistAuth = useCallback((auth: AuthResponse) => {
    window.localStorage.setItem(TOKEN_KEY, auth.access_token);
    setToken(auth.access_token);
    setUser(auth.user);
    setStatus("authenticated");
  }, []);

  const login = useCallback(
    async (email: string, password: string) => {
      const auth = await api<AuthResponse>("/api/auth/login", {
        method: "POST",
        body: { email, password },
      });
      persistAuth(auth);
      return auth.user;
    },
    [persistAuth],
  );

  const register = useCallback(
    async (email: string, password: string, name: string) => {
      const auth = await api<AuthResponse>("/api/auth/register", {
        method: "POST",
        body: { email, password, name },
      });
      persistAuth(auth);
      return auth.user;
    },
    [persistAuth],
  );

  const logout = useCallback(() => {
    window.localStorage.removeItem(TOKEN_KEY);
    setToken(null);
    setUser(null);
    setStatus("unauthenticated");
  }, []);

  const value = useMemo(
    () => ({ user, token, status, login, register, logout }),
    [user, token, status, login, register, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return ctx;
}