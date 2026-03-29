"use client";

import { useState } from "react";
import Link from "next/link";
import {
  Bot,
  CalendarDays,
  ChevronLeft,
  ChevronRight,
  Info,
  MessageCircle,
  Newspaper,
  RefreshCw,
} from "lucide-react";

export type CampusTab = "calendar" | "articles" | "wechat";

export function CampusSoftShell({
  tab,
  onTabChange,
  onRefresh,
  refreshing,
  main,
  right,
}: {
  tab: CampusTab;
  onTabChange: (t: CampusTab) => void;
  onRefresh: () => void;
  refreshing: boolean;
  main: React.ReactNode;
  right: React.ReactNode;
}) {
  const [panelOpen, setPanelOpen] = useState(true);

  return (
    <div className="min-h-[calc(100vh-4rem)] bg-gradient-to-b from-white via-orange-50/[0.04] to-stone-100/[0.12]">
      <div className="max-w-[1580px] mx-auto flex gap-3 md:gap-6 lg:gap-8 px-3 sm:px-5 md:px-8 py-6 md:py-8">
        <div className="flex-1 min-w-0 flex flex-col gap-5">
          <div className="flex items-center gap-2 flex-wrap">
            {/* Tab 切换按钮 */}
            <div className="inline-flex rounded-full bg-white/60 backdrop-blur-md border border-stone-200/50 p-1 shadow-sm">
              <button
                type="button"
                onClick={() => onTabChange("articles")}
                className={`px-3 sm:px-5 py-1.5 sm:py-2 rounded-full text-xs sm:text-sm font-medium flex items-center gap-1.5 sm:gap-2 transition-colors ${
                  tab === "articles"
                    ? "bg-slate-900 text-white shadow-md"
                    : "text-slate-600"
                }`}
              >
                <Newspaper size={14} className="sm:w-[15px] sm:h-[15px]" />{" "}
                <span className="hidden sm:inline">学生资讯</span>
                <span className="sm:hidden">资讯</span>
              </button>
              <button
                type="button"
                onClick={() => onTabChange("wechat")}
                className={`px-3 sm:px-5 py-1.5 sm:py-2 rounded-full text-xs sm:text-sm font-medium flex items-center gap-1.5 sm:gap-2 transition-colors ${
                  tab === "wechat"
                    ? "bg-slate-900 text-white shadow-md"
                    : "text-slate-600"
                }`}
              >
                <MessageCircle size={14} className="sm:w-[15px] sm:h-[15px]" />{" "}
                <span className="hidden sm:inline">公众号文章</span>
                <span className="sm:hidden">公众号</span>
              </button>
              <button
                type="button"
                onClick={() => onTabChange("calendar")}
                className={`px-3 sm:px-5 py-1.5 sm:py-2 rounded-full text-xs sm:text-sm font-medium flex items-center gap-1.5 sm:gap-2 transition-colors ${
                  tab === "calendar"
                    ? "bg-slate-900 text-white shadow-md"
                    : "text-slate-600"
                }`}
              >
                <CalendarDays size={14} className="sm:w-[15px] sm:h-[15px]" />{" "}
                <span className="hidden sm:inline">活动日历</span>
                <span className="sm:hidden">日历</span>
              </button>
            </div>

            {/* 智能活动筛选 - 紧凑横向卡片 */}
            <Link
              href="/campus/smart-calendar"
              className="inline-flex items-center gap-2 rounded-full bg-gradient-to-r from-indigo-500/90 to-violet-600/90 px-3 sm:px-4 py-1.5 sm:py-2 text-white shadow-sm hover:opacity-90 transition-opacity"
            >
              <Bot size={14} className="shrink-0" />
              <span className="text-xs sm:text-sm font-medium whitespace-nowrap">智能筛选</span>
              <ChevronRight size={12} className="opacity-70" />
            </Link>

            {/* 提示 - 紧凑横向卡片 */}
            <div className="hidden md:inline-flex items-center gap-1.5 rounded-full bg-violet-50/60 backdrop-blur-sm border border-violet-200/40 px-3 sm:px-4 py-1.5 sm:py-2">
              <Info size={13} className="text-violet-400 shrink-0" />
              <span className="text-[11px] sm:text-xs text-slate-500">
                {tab === "wechat"
                  ? "聚合搜狗微信搜索的校园相关公众号文章，点击可跳转原文"
                  : "学生资讯聚合了官网活动、讲座、招聘会与宣讲会"}
              </span>
            </div>

            <button
              type="button"
              title="刷新当前视图"
              onClick={onRefresh}
              disabled={refreshing}
              className="ml-auto p-2.5 rounded-full text-slate-400 hover:text-violet-600 hover:bg-white/55 hover:backdrop-blur-sm border border-transparent hover:border-stone-200/50 transition-colors disabled:opacity-40"
            >
              <RefreshCw
                size={18}
                className={refreshing ? "animate-spin" : ""}
              />
            </button>
          </div>

          {main}
        </div>

        {/* 右侧面板：可左右折叠 */}
        <aside className="hidden lg:flex shrink-0 relative">
          {/* 折叠切换按钮 */}
          <button
            type="button"
            onClick={() => setPanelOpen((v) => !v)}
            title={panelOpen ? "收起侧栏" : "展开侧栏"}
            className="absolute -left-3 top-28 z-10 w-6 h-12 flex items-center justify-center rounded-full bg-white/80 backdrop-blur-sm border border-stone-200/60 shadow-sm text-slate-400 hover:text-violet-600 hover:border-violet-200 transition-colors"
          >
            {panelOpen ? (
              <ChevronRight size={14} />
            ) : (
              <ChevronLeft size={14} />
            )}
          </button>

          <div
            className={`transition-[width,opacity] duration-300 ease-in-out overflow-hidden ${
              panelOpen
                ? "w-72 xl:w-80 opacity-100"
                : "w-0 opacity-0"
            }`}
          >
            <div className="w-72 xl:w-80 sticky top-24">{right}</div>
          </div>
        </aside>
      </div>
    </div>
  );
}
