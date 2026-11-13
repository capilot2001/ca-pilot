"use client";

/**
 * Auth STUB (ADR-0008). Isolated behind this seam so real auth swaps in later
 * without touching screens. The "session" is a fake value in sessionStorage —
 * no real credentials are checked.
 */
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";

const SESSION_KEY = "lf_session";

export interface SessionUser {
  name: string;
  email: string;
}

interface AuthContextValue {
  user: SessionUser | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (email: string) => void;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

function readSession(): SessionUser | null {
  try {
    const raw = sessionStorage.getItem(SESSION_KEY);
    return raw ? (JSON.parse(raw) as SessionUser) : null;
  } catch {
    return null;
  }
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<SessionUser | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  // Read the stored session after mount to avoid a hydration mismatch.
  useEffect(() => {
    setUser(readSession());
    setIsLoading(false);
  }, []);

  const login = useCallback((email: string) => {
    const u: SessionUser = {
      email,
      name: email.split("@")[0] || "Demo Owner",
    };
    try {
      sessionStorage.setItem(SESSION_KEY, JSON.stringify(u));
    } catch {
      /* private mode — keep the session in memory only */
    }
    setUser(u);
  }, []);

  const logout = useCallback(() => {
    try {
      sessionStorage.removeItem(SESSION_KEY);
    } catch {
      /* ignore */
    }
    setUser(null);
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      isAuthenticated: !!user,
      isLoading,
      login,
      logout,
    }),
    [user, isLoading, login, logout]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within <AuthProvider>");
  return ctx;
}
