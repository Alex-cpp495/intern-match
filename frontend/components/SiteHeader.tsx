"use client";

import { useState } from "react";
import Link from "next/link";
import Image from "next/image";
import { usePathname, useSearchParams } from "next/navigation";
import { Loader2, LogIn, LogOut, Menu, User, X } from "lucide-react";
import { UNNC_LOGO } from "@/lib/unnc-brand";
import { MATCH_ENTRY } from "@/lib/routes";
import { useAuth } from "@/hooks/useAuth";
import { useSmartCalendarStore } from "@/hooks/useSmartCalendarStore";

const NAV_LINKS = [
  { href: "/", label: "首页" },
  { href: MATCH_ENTRY, label: "实习匹配" },
  { href: "/campus", label: "校园动态" },
  { href: "/me", label: "我的" },
] as const;

function navActive(pathname: string, href: string, onMatchFlow: boolean): boolean {
  if (href === MATCH_ENTRY) return pathname === "/" && onMatchFlow;
  if (href === "/") return pathname === "/" && !onMatchFlow;
  return pathname === href || pathname.startsWith(`${href}/`);
}

export default function SiteHeader() {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const onMatchFlow = pathname === "/" && searchParams.get("match") === "1";
  const [mobileOpen, setMobileOpen] = useState(false);
  const { user, loading, logout, backendUnreachable, refresh } = useAuth();
  const smartCal = useSmartCalendarStore();

  return (
    <header className="sticky top-0 z-50 w-full glass-effect border-b border-unnc-blue/10">
      {backendUnreachable && !loading && (
        <div className="w-full bg-amber-50 border-b border-amber-200 px-4 py-2 text-center text-xs text-amber-950">
          <span className="font-medium">无法连接后端 API</span>
          （Next 将 <code className="px-1 bg-amber-100 rounded">/api/*</code>{" "}
          转发到{" "}
          <code className="px-1 bg-amber-100 rounded">
            {process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}
          </code>
          ）。请在本机启动 FastAPI（如{" "}
          <code className="px-1 bg-amber-100 rounded">uvicorn main:app --reload --port 8000</code>
          ）后{" "}
          <button
            type="button"
            onClick={() => void refresh()}
            className="underline font-semibold text-amber-900 hover:text-amber-700"
          >
            点击重试
          </button>
          。
        </div>
      )}
      <div className="container max-w-7xl mx-auto pl-2 pr-4 md:pl-4 md:pr-8 flex h-16 items-center w-full">
        {/* 左侧品牌区：桌面固定宽度，便于中间导航几何居中 */}
        <div className="flex md:w-56 shrink-0 min-w-0 items-center">
          <Link
            href="/"
            className="flex items-center gap-4 md:gap-6 -ml-1 md:-ml-2 min-w-0 group transition-opacity duration-300 hover:opacity-90"
          >
            <Image
              src={UNNC_LOGO}
              alt=""
              width={44}
              height={44}
              className="h-10 w-auto max-h-10 shrink-0 object-contain object-left opacity-95"
              priority
            />
            <span className="text-lg font-bold bg-gradient-to-r from-unnc-navy to-unnc-blue bg-clip-text text-transparent whitespace-nowrap">
              NottFind
            </span>
          </Link>
        </div>

        {/* 桌面：在剩余宽度内居中；移动端占位撑开 */}
        <nav className="hidden md:flex flex-1 items-center justify-center gap-0.5 min-w-0 px-2">
          {NAV_LINKS.map((link) => {
            const active = navActive(pathname, link.href, onMatchFlow);
            return (
              <Link
                key={`${link.href}-${link.label}`}
                href={link.href}
                className={`text-sm font-medium px-3 py-2 rounded-lg transition-all duration-200 relative group whitespace-nowrap ${
                  active
                    ? "text-unnc-blue bg-unnc-sky"
                    : "text-gray-600 hover:text-unnc-blue hover:bg-gray-50"
                }`}
              >
                {link.label}
                <div
                  className={`absolute bottom-0 left-1/2 -translate-x-1/2 w-5 h-0.5 bg-unnc-gold rounded-full transition-all duration-300 ${
                    active ? "opacity-100" : "opacity-0 group-hover:opacity-100"
                  }`}
                />
              </Link>
            );
          })}

          {smartCal.loading && (
            <Link
              href="/campus/smart-calendar"
              className="ml-1 inline-flex items-center gap-1.5 text-[11px] font-medium text-violet-700 bg-violet-50 border border-violet-200 rounded-full px-3 py-1 hover:bg-violet-100 transition animate-pulse"
              title="智能日历正在生成中，点击查看"
            >
              <Loader2 size={12} className="animate-spin" />
              日历生成中…
            </Link>
          )}
        </nav>

        <div className="flex md:w-56 shrink-0 flex-1 md:flex-none justify-end items-center gap-2 min-w-[2.75rem]">
          {loading ? (
            <div className="hidden md:block w-8 h-8 rounded-full bg-slate-100 animate-pulse" />
          ) : user ? (
            <div className="hidden md:flex items-center gap-2">
              <div className="w-8 h-8 rounded-full bg-gradient-to-br from-blue-500 to-blue-700 flex items-center justify-center">
                <User size={14} className="text-white" />
              </div>
              <span className="text-sm text-slate-700 font-medium max-w-[100px] truncate">
                {user.username}
              </span>
              <button
                type="button"
                onClick={() => void logout()}
                className="p-1.5 rounded-lg text-slate-400 hover:text-red-500 hover:bg-red-50 transition-colors"
                title="退出登录"
              >
                <LogOut size={16} />
              </button>
            </div>
          ) : (
            <Link
              href="/login"
              className="hidden md:inline-flex items-center gap-1.5 px-4 py-2 rounded-xl text-sm font-medium bg-slate-900 text-white hover:bg-slate-800 transition-colors shadow-sm"
            >
              <LogIn size={14} />
              登录
            </Link>
          )}
          <button
            className="md:hidden p-2 rounded-lg hover:bg-gray-100 transition shrink-0"
            type="button"
            onClick={() => setMobileOpen(!mobileOpen)}
            aria-expanded={mobileOpen}
            aria-label={mobileOpen ? "关闭菜单" : "打开菜单"}
          >
            {mobileOpen ? <X size={22} /> : <Menu size={22} />}
          </button>
        </div>
      </div>

      {mobileOpen && (
        <div className="md:hidden border-t border-gray-100 bg-white/98 backdrop-blur-sm">
          <nav className="container max-w-7xl mx-auto pl-2 pr-4 md:pl-4 md:pr-8 py-4 flex flex-col gap-1">
            {smartCal.loading && (
              <Link
                href="/campus/smart-calendar"
                onClick={() => setMobileOpen(false)}
                className="flex items-center gap-2 px-4 py-3 rounded-xl text-sm font-medium text-violet-700 bg-violet-50 animate-pulse"
              >
                <Loader2 size={14} className="animate-spin" />
                智能日历生成中，点击查看
              </Link>
            )}
            {NAV_LINKS.map((link) => {
              const active = navActive(pathname, link.href, onMatchFlow);
              return (
                <Link
                  key={`${link.href}-${link.label}`}
                  href={link.href}
                  onClick={() => setMobileOpen(false)}
                  className={`flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-medium transition-all ${
                    active
                      ? "text-unnc-blue bg-unnc-sky"
                      : "text-gray-600 hover:bg-gray-50"
                  }`}
                >
                  {link.label}
                </Link>
              );
            })}
            <div className="mt-2 pt-2 border-t border-gray-100">
              {user ? (
                <div className="flex items-center justify-between px-4 py-3">
                  <div className="flex items-center gap-2 min-w-0">
                    <div className="w-7 h-7 rounded-full bg-gradient-to-br from-blue-500 to-blue-700 flex items-center justify-center shrink-0">
                      <User size={12} className="text-white" />
                    </div>
                    <span className="text-sm text-slate-700 font-medium truncate">
                      {user.username}
                    </span>
                  </div>
                  <button
                    type="button"
                    onClick={() => {
                      setMobileOpen(false);
                      void logout();
                    }}
                    className="text-sm text-red-500 font-medium px-3 py-1.5 rounded-lg hover:bg-red-50 transition-colors"
                  >
                    退出
                  </button>
                </div>
              ) : (
                <Link
                  href="/login"
                  onClick={() => setMobileOpen(false)}
                  className="flex items-center gap-2 w-full px-4 py-3 rounded-xl text-sm font-medium text-unnc-blue hover:bg-unnc-sky transition-all"
                >
                  <LogIn size={16} />
                  登录 / 注册
                </Link>
              )}
            </div>
          </nav>
        </div>
      )}
    </header>
  );
}
