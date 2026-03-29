"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { useAuth } from "@/hooks/useAuth";

export default function RegisterPage() {
  const router = useRouter();
  const { register, loading: authLoading, user } = useAuth();
  const [email, setEmail] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [privacy, setPrivacy] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!authLoading && user) {
      router.replace("/");
    }
  }, [authLoading, user, router]);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (password !== confirm) {
      setError("两次输入的密码不一致");
      return;
    }
    if (password.length < 8) {
      setError("密码至少 8 位");
      return;
    }
    if (!privacy) {
      setError("请阅读并同意隐私政策与用户条款");
      return;
    }
    setSubmitting(true);
    const r = await register({
      email: email.trim(),
      username: username.trim(),
      password,
      privacy_consent: privacy,
    });
    setSubmitting(false);
    if (r.ok) {
      router.push("/");
    } else {
      setError(r.error ?? "注册失败");
    }
  }

  return (
    <div className="min-h-[calc(100vh-4rem)] flex items-center justify-center bg-gradient-to-b from-white via-orange-50/[0.04] to-stone-100/[0.12] py-10">
      <div className="w-full max-w-sm mx-4">
        <div className="rounded-[1.75rem] bg-white/70 backdrop-blur-md border border-stone-200/50 shadow-lg p-8">
          <h1 className="text-xl font-bold text-slate-900 mb-2 text-center">
            注册 NottFind
          </h1>
          <p className="text-sm text-slate-500 mb-6 text-center">
            仅限 @nottingham.edu.cn 邮箱
          </p>

          {error && (
            <div className="mb-4 rounded-xl bg-red-50 border border-red-200/60 px-4 py-3 text-sm text-red-700">
              {error}
            </div>
          )}

          <form onSubmit={onSubmit} className="space-y-4">
            <div>
              <label
                htmlFor="reg-email"
                className="block text-xs font-medium text-slate-600 mb-1.5"
              >
                学校邮箱
              </label>
              <input
                id="reg-email"
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
                htmlFor="reg-username"
                className="block text-xs font-medium text-slate-600 mb-1.5"
              >
                用户名（2–32 位，字母数字下划线或中文）
              </label>
              <input
                id="reg-username"
                type="text"
                autoComplete="username"
                required
                minLength={2}
                maxLength={32}
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                className="w-full rounded-xl border border-stone-200 bg-white/80 px-4 py-2.5 text-sm outline-none focus:ring-2 focus:ring-unnc-blue/30 focus:border-unnc-blue"
              />
            </div>
            <div>
              <label
                htmlFor="reg-password"
                className="block text-xs font-medium text-slate-600 mb-1.5"
              >
                密码（至少 8 位）
              </label>
              <input
                id="reg-password"
                type="password"
                autoComplete="new-password"
                required
                minLength={8}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full rounded-xl border border-stone-200 bg-white/80 px-4 py-2.5 text-sm outline-none focus:ring-2 focus:ring-unnc-blue/30 focus:border-unnc-blue"
              />
            </div>
            <div>
              <label
                htmlFor="reg-confirm"
                className="block text-xs font-medium text-slate-600 mb-1.5"
              >
                确认密码
              </label>
              <input
                id="reg-confirm"
                type="password"
                autoComplete="new-password"
                required
                value={confirm}
                onChange={(e) => setConfirm(e.target.value)}
                className="w-full rounded-xl border border-stone-200 bg-white/80 px-4 py-2.5 text-sm outline-none focus:ring-2 focus:ring-unnc-blue/30 focus:border-unnc-blue"
              />
            </div>
            <label className="flex items-start gap-2 text-xs text-slate-600 cursor-pointer">
              <input
                type="checkbox"
                checked={privacy}
                onChange={(e) => setPrivacy(e.target.checked)}
                className="mt-0.5 rounded border-stone-300"
              />
              <span>
                我已阅读并同意隐私政策与用户条款（注册即表示同意本平台收集邮箱与用户名用于账号服务）
              </span>
            </label>
            <button
              type="submit"
              disabled={submitting || authLoading}
              className="w-full py-3 rounded-xl text-white font-medium text-sm bg-slate-900 hover:bg-slate-800 disabled:opacity-60 transition-colors shadow-md"
            >
              {submitting ? "注册中…" : "注册并登录"}
            </button>
          </form>

          <p className="text-center text-sm text-slate-600 mt-6">
            已有账号？{" "}
            <Link
              href="/login"
              className="text-unnc-blue font-medium hover:underline"
            >
              登录
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}
