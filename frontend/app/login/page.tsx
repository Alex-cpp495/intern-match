"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { useAuth } from "@/hooks/useAuth";

function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const callbackUrl = searchParams.get("callbackUrl") || "/";
  const { login, loading: authLoading, user } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!authLoading && user) {
      router.replace(callbackUrl.startsWith("/") ? callbackUrl : "/");
    }
  }, [authLoading, user, router, callbackUrl]);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    const r = await login(email.trim(), password);
    setSubmitting(false);
    if (r.ok) {
      router.push(callbackUrl.startsWith("/") ? callbackUrl : "/");
    } else {
      setError(r.error ?? "登录失败");
    }
  }

  return (
    <div className="min-h-[calc(100vh-4rem)] flex items-center justify-center bg-gradient-to-b from-white via-orange-50/[0.04] to-stone-100/[0.12]">
      <div className="w-full max-w-sm mx-4">
        <div className="rounded-[1.75rem] bg-white/70 backdrop-blur-md border border-stone-200/50 shadow-lg p-8">
          <div className="w-16 h-16 mx-auto mb-5 rounded-2xl bg-gradient-to-br from-blue-500 to-blue-700 flex items-center justify-center shadow-md">
            <svg
              viewBox="0 0 24 24"
              className="w-8 h-8 text-white"
              fill="currentColor"
            >
              <rect x="3" y="3" width="8" height="8" rx="1" opacity="0.9" />
              <rect x="13" y="3" width="8" height="8" rx="1" opacity="0.7" />
              <rect x="3" y="13" width="8" height="8" rx="1" opacity="0.7" />
              <rect x="13" y="13" width="8" height="8" rx="1" opacity="0.5" />
            </svg>
          </div>

          <h1 className="text-xl font-bold text-slate-900 mb-2 text-center">
            登录 NottFind
          </h1>
          <p className="text-sm text-slate-500 mb-6 text-center">
            使用宁诺邮箱账号登录
          </p>

          {error && (
            <div className="mb-4 rounded-xl bg-red-50 border border-red-200/60 px-4 py-3 text-sm text-red-700">
              {error}
            </div>
          )}

          <form onSubmit={onSubmit} className="space-y-4">
            <div>
              <label
                htmlFor="login-email"
                className="block text-xs font-medium text-slate-600 mb-1.5"
              >
                学校邮箱
              </label>
              <input
                id="login-email"
                type="email"
                autoComplete="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="name@nottingham.edu.cn"
                className="w-full rounded-xl border border-stone-200 bg-white/80 px-4 py-2.5 text-sm outline-none focus:ring-2 focus:ring-unnc-blue/30 focus:border-unnc-blue"
              />
            </div>
            <div>
              <label
                htmlFor="login-password"
                className="block text-xs font-medium text-slate-600 mb-1.5"
              >
                密码
              </label>
              <input
                id="login-password"
                type="password"
                autoComplete="current-password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full rounded-xl border border-stone-200 bg-white/80 px-4 py-2.5 text-sm outline-none focus:ring-2 focus:ring-unnc-blue/30 focus:border-unnc-blue"
              />
            </div>
            <button
              type="submit"
              disabled={submitting || authLoading}
              className="w-full py-3 rounded-xl text-white font-medium text-sm bg-slate-900 hover:bg-slate-800 disabled:opacity-60 transition-colors shadow-md"
            >
              {submitting ? "登录中…" : "登录"}
            </button>
          </form>

          <p className="text-center text-sm text-slate-600 mt-6">
            还没有账号？{" "}
            <Link
              href="/register"
              className="text-unnc-blue font-medium hover:underline"
            >
              注册
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense
      fallback={
        <div className="min-h-[calc(100vh-4rem)] flex items-center justify-center">
          <p className="text-slate-400 text-sm">加载中…</p>
        </div>
      }
    >
      <LoginForm />
    </Suspense>
  );
}
