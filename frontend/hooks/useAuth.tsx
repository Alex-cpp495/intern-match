"use client";

import axios from "axios";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";

export type AuthUser = {
  id: number;
  email: string;
  username: string;
};

export type RegisterParams = {
  email: string;
  username: string;
  password: string;
  privacy_consent: boolean;
};

/** 与 /api/auth/me 请求超时一致（毫秒） */
export const AUTH_ME_TIMEOUT_MS = 12_000;

type AuthContextValue = {
  user: AuthUser | null;
  loading: boolean;
  /** 为 true 表示会话校验失败系网络/代理问题（如后端未启动），而非「未登录」 */
  backendUnreachable: boolean;
  login: (
    email: string,
    password: string,
  ) => Promise<{ ok: boolean; error?: string }>;
  register: (
    p: RegisterParams,
  ) => Promise<{ ok: boolean; error?: string }>;
  logout: () => Promise<void>;
  refresh: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

function formatApiError(data: unknown): string {
  if (!data || typeof data !== "object") return "请求失败";
  const detail = (data as { detail?: unknown }).detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    const parts = detail
      .map((x: { msg?: string }) => x.msg)
      .filter(Boolean) as string[];
    return parts.length ? parts.join("；") : "请求失败";
  }
  return "请求失败";
}

function isAuthMeTransportFailure(e: unknown): boolean {
  if (!axios.isAxiosError(e)) return true;
  if (e.code === "ECONNABORTED" || e.message?.includes("timeout")) return true;
  if (!e.response) return true;
  const s = e.response.status;
  return s === 502 || s === 503 || s === 504;
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);
  const [backendUnreachable, setBackendUnreachable] = useState(false);

  const refresh = useCallback(async () => {
    try {
      const { data } = await axios.get<{ user: AuthUser }>("/api/auth/me", {
        withCredentials: true,
        timeout: AUTH_ME_TIMEOUT_MS,
      });
      setUser(data.user);
      setBackendUnreachable(false);
    } catch (e) {
      setUser(null);
      setBackendUnreachable(isAuthMeTransportFailure(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    axios.defaults.withCredentials = true;
    void refresh();
  }, [refresh]);

  const login = useCallback(async (email: string, password: string) => {
    try {
      const { data } = await axios.post<{ user: AuthUser }>(
        "/api/auth/login",
        { email, password },
        { withCredentials: true },
      );
      setUser(data.user);
      return { ok: true as const };
    } catch (e) {
      if (axios.isAxiosError(e) && e.response?.data) {
        return {
          ok: false as const,
          error: formatApiError(e.response.data),
        };
      }
      return { ok: false as const, error: "登录失败，请稍后再试" };
    }
  }, []);

  const register = useCallback(async (p: RegisterParams) => {
    try {
      const { data } = await axios.post<{ user: AuthUser }>(
        "/api/auth/register",
        p,
        { withCredentials: true },
      );
      setUser(data.user);
      return { ok: true as const };
    } catch (e) {
      if (axios.isAxiosError(e) && e.response?.data) {
        return {
          ok: false as const,
          error: formatApiError(e.response.data),
        };
      }
      return { ok: false as const, error: "注册失败，请稍后再试" };
    }
  }, []);

  const logout = useCallback(async () => {
    try {
      await axios.post("/api/auth/logout", {}, { withCredentials: true });
    } finally {
      setUser(null);
    }
  }, []);

  const value = useMemo(
    () => ({
      user,
      loading,
      backendUnreachable,
      login,
      register,
      logout,
      refresh,
    }),
    [user, loading, backendUnreachable, login, register, logout, refresh],
  );

  return (
    <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth 必须在 AuthProvider 内使用");
  }
  return ctx;
}
