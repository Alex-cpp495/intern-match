"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import axios from "axios";
import {
  ChevronLeft,
  ChevronRight,
  Loader2,
  MessageCircle,
  Newspaper,
  Plus,
  Radio,
  Sparkles,
  Trash2,
} from "lucide-react";
import { useAuth } from "@/hooks/useAuth";
import {
  CampusActivityCalendar,
  type MergedCalendarEvent,
  type CalendarSource,
} from "@/components/campus/CampusActivityCalendar";
import { CampusEventSoftCard } from "@/components/campus/CampusArticleSoftCard";
import { CampusSoftRightPanel } from "@/components/campus/CampusSoftRightPanel";
import { CampusSoftShell, type CampusTab } from "@/components/campus/CampusSoftShell";
import { TimetableImportControls } from "@/components/campus/TimetableImportControls";
import {
  WechatArticleCard,
  type WechatArticle,
} from "@/components/campus/WechatArticleCard";
import { WechatCustomQueriesPanel } from "@/components/campus/WechatCustomQueriesPanel";
import {
  ACTIVITY_CATEGORY_OPTIONS,
  type ActivityCategoryId,
  eventMatchesCategory,
} from "@/lib/campusArticleCategories";
import {
  clearTimetableStorage,
  loadTimetableFromStorage,
  loadTimetableUrlFromStorage,
  saveTimetableToStorage,
} from "@/lib/timetableStorage";
import {
  loadCustomCampusEvents,
  saveCustomCampusEvents,
  newCustomEventUid,
} from "@/lib/customCampusEventsStorage";

type TabKey = CampusTab;

function mergeMergedCustomTimetable(
  merged: MergedCalendarEvent[],
  custom: MergedCalendarEvent[],
  timetable: MergedCalendarEvent[],
): MergedCalendarEvent[] {
  const map = new Map<string, MergedCalendarEvent>();
  for (const e of merged) map.set(e.uid, e);
  for (const e of custom) map.set(e.uid, e);
  for (const e of timetable) map.set(e.uid, e);
  return Array.from(map.values());
}

function localDateTimeToIso(dateStr: string, timeStr: string): string | null {
  const dp = dateStr.split("-").map(Number);
  const tp = timeStr.split(":").map(Number);
  if (dp.length !== 3 || tp.length < 2) return null;
  const [y, m, d] = dp;
  const hh = tp[0];
  const mm = tp[1] ?? 0;
  if (!y || !m || !d || Number.isNaN(hh) || Number.isNaN(mm)) return null;
  const dt = new Date(y, m - 1, d, hh, mm, 0, 0);
  if (Number.isNaN(dt.getTime())) return null;
  return dt.toISOString();
}

const NON_TIMETABLE_SOURCES: CalendarSource[] = [
  "unnc_events",
  "careers_lecture",
  "careers_jobfair",
  "careers_teachin",
  "wechat_event",
  "user_custom",
];

const CAMPUS_BG_REFRESH_DATE_KEY = "intern-match-campus-bg-refresh-date";

function CampusCustomEventsPanel({
  events,
  onAdd,
  onRemove,
}: {
  events: MergedCalendarEvent[];
  onAdd: (ev: MergedCalendarEvent) => void;
  onRemove: (uid: string) => void;
}) {
  const [title, setTitle] = useState("");
  const [date, setDate] = useState(() =>
    new Date().toISOString().slice(0, 10),
  );
  const [startT, setStartT] = useState("14:00");
  const [endT, setEndT] = useState("15:30");
  const [loc, setLoc] = useState("");

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!title.trim()) return;
    const start_iso = localDateTimeToIso(date, startT);
    const end_iso = localDateTimeToIso(date, endT);
    if (!start_iso || !end_iso) return;
    onAdd({
      uid: newCustomEventUid(),
      title: title.trim(),
      start_iso,
      end_iso,
      all_day: false,
      busy: false,
      source: "user_custom",
      location: loc.trim(),
      url: "",
      description: "",
      categories: ["自建"],
    });
    setTitle("");
  }

  return (
    <div className="rounded-[1.75rem] border border-violet-200/50 bg-white/75 backdrop-blur-md shadow-sm p-4 sm:p-5 space-y-4">
      <div>
        <h3 className="text-sm font-semibold text-slate-800 flex items-center gap-2">
          <Plus size={16} className="text-violet-600" />
          添加个人事项
        </h3>
        <p className="text-xs text-slate-500 mt-1">
          自建活动会写入本机并与课表、官网活动一起显示在月历上。
        </p>
      </div>
      <form
        onSubmit={handleSubmit}
        className="flex flex-col sm:flex-row sm:flex-wrap gap-2 sm:items-end"
      >
        <input
          type="text"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="标题（必填）"
          className="flex-1 min-w-[140px] rounded-xl border border-stone-200 px-3 py-2 text-sm"
          required
        />
        <input
          type="date"
          value={date}
          onChange={(e) => setDate(e.target.value)}
          className="rounded-xl border border-stone-200 px-3 py-2 text-sm w-full sm:w-auto"
        />
        <input
          type="time"
          value={startT}
          onChange={(e) => setStartT(e.target.value)}
          className="rounded-xl border border-stone-200 px-3 py-2 text-sm w-full sm:w-32"
        />
        <input
          type="time"
          value={endT}
          onChange={(e) => setEndT(e.target.value)}
          className="rounded-xl border border-stone-200 px-3 py-2 text-sm w-full sm:w-32"
        />
        <input
          type="text"
          value={loc}
          onChange={(e) => setLoc(e.target.value)}
          placeholder="地点（可选）"
          className="flex-1 min-w-[120px] rounded-xl border border-stone-200 px-3 py-2 text-sm"
        />
        <button
          type="submit"
          className="inline-flex items-center justify-center gap-1.5 rounded-xl bg-violet-600 text-white text-sm font-medium px-4 py-2 hover:bg-violet-700 transition-colors"
        >
          <Plus size={16} />
          添加
        </button>
      </form>
      {events.length > 0 && (
        <ul className="space-y-2 border-t border-stone-100 pt-3">
          {events.map((ev) => (
            <li
              key={ev.uid}
              className="flex items-center justify-between gap-2 text-xs text-slate-600 bg-stone-50/80 rounded-lg px-3 py-2"
            >
              <span className="truncate">
                {ev.title}
                {ev.start_iso && (
                  <span className="text-slate-400 ml-1">
                    · {new Date(ev.start_iso).toLocaleString("zh-CN", {
                      month: "numeric",
                      day: "numeric",
                      hour: "2-digit",
                      minute: "2-digit",
                    })}
                  </span>
                )}
              </span>
              <button
                type="button"
                onClick={() => onRemove(ev.uid)}
                className="shrink-0 p-1 rounded-lg text-slate-400 hover:text-red-600 hover:bg-red-50 transition-colors"
                aria-label="删除"
              >
                <Trash2 size={14} />
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export default function CampusPage() {
  const { user } = useAuth();
  const [tab, setTab] = useState<TabKey>("articles");
  const [category, setCategory] = useState<ActivityCategoryId>("all");
  const [mergedEvents, setMergedEvents] = useState<MergedCalendarEvent[]>([]);
  const [bySource, setBySource] = useState<Record<string, number>>({});
  const [timetableEvents, setTimetableEvents] = useState<MergedCalendarEvent[]>(
    [],
  );
  const [savedTimetableUrl, setSavedTimetableUrl] = useState("");
  const [hiddenUids, setHiddenUids] = useState<Set<string>>(new Set());
  const [loadingCalendar, setLoadingCalendar] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  /** 后台 refresh-all 后，公众号活动 AI 较慢，继续静默轮询合并日历 */
  const mergePollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const tabRef = useRef<TabKey>("articles");
  useEffect(() => {
    tabRef.current = tab;
  }, [tab]);
  const [currentPage, setCurrentPage] = useState(1);
  const PAGE_SIZE = 18;
  const [customEvents, setCustomEvents] = useState<MergedCalendarEvent[]>([]);

  const [wechatArticles, setWechatArticles] = useState<WechatArticle[]>([]);
  const [loadingWechat, setLoadingWechat] = useState(false);
  const [wechatLoaded, setWechatLoaded] = useState(false);
  const [wechatPage, setWechatPage] = useState(1);
  const [wechatFilter, setWechatFilter] = useState<string>("all");

  const loadWechatArticles = useCallback(() => {
    setLoadingWechat(true);
    axios
      .get("/api/articles")
      .then((res) => {
        const list: WechatArticle[] = res.data.articles || [];
        setWechatArticles(list);
        setWechatLoaded(true);
      })
      .catch(() => {
        setWechatArticles([]);
      })
      .finally(() => {
        setLoadingWechat(false);
      });
  }, []);

  const loadMergedCalendar = useCallback((opts?: { silent?: boolean }) => {
    if (!opts?.silent) setLoadingCalendar(true);
    return axios
      .get("/api/calendar/merged")
      .then((res) => {
        setMergedEvents(res.data.events || []);
        setBySource(res.data.by_source || {});
      })
      .catch(() => {
        if (!opts?.silent) {
          setMergedEvents([]);
          setBySource({});
        }
      })
      .finally(() => {
        if (!opts?.silent) setLoadingCalendar(false);
      });
  }, []);

  useEffect(() => {
    if (tab === "wechat" && !wechatLoaded && !loadingWechat) {
      loadWechatArticles();
    }
  }, [tab, wechatLoaded, loadingWechat, loadWechatArticles]);

  useEffect(() => {
    loadMergedCalendar();
    setTimetableEvents(loadTimetableFromStorage());
    setSavedTimetableUrl(loadTimetableUrlFromStorage());
    try {
      const raw = localStorage.getItem("intern-match-hidden-uids-v1");
      if (raw) {
        const arr = JSON.parse(raw) as unknown;
        if (Array.isArray(arr)) setHiddenUids(new Set(arr.map(String)));
      }
    } catch { /* ignore */ }
    return () => {
      if (mergePollRef.current) {
        clearInterval(mergePollRef.current);
        mergePollRef.current = null;
      }
    };
  }, [loadMergedCalendar]);

  /** 每个自然日首次打开本页时后台触发全量刷新（与后端定时任务互补），并延迟拉取合并日历 */
  useEffect(() => {
    if (typeof window === "undefined") return;
    const today = new Date().toDateString();
    try {
      if (localStorage.getItem(CAMPUS_BG_REFRESH_DATE_KEY) === today) return;
      localStorage.setItem(CAMPUS_BG_REFRESH_DATE_KEY, today);
    } catch {
      return;
    }
    axios.post("/api/campus/refresh-all").catch(() => {});
    const t1 = window.setTimeout(() => {
      void loadMergedCalendar({ silent: true });
    }, 12_000);
    const t2 = window.setTimeout(() => {
      void loadMergedCalendar({ silent: true });
    }, 35_000);
    return () => {
      window.clearTimeout(t1);
      window.clearTimeout(t2);
    };
  }, [loadMergedCalendar]);

  useEffect(() => {
    if (!user) return;
    setCustomEvents(loadCustomCampusEvents(user.id));
  }, [user]);

  const addCustomEvent = useCallback(
    (ev: MergedCalendarEvent) => {
      setCustomEvents((prev) => {
        const next = [...prev, ev];
        if (user) saveCustomCampusEvents(user.id, next);
        return next;
      });
    },
    [user],
  );

  const removeCustomEvent = useCallback(
    (uid: string) => {
      setCustomEvents((prev) => {
        const next = prev.filter((e) => e.uid !== uid);
        if (user) saveCustomCampusEvents(user.id, next);
        return next;
      });
    },
    [user],
  );

  const toggleHidden = useCallback((uid: string) => {
    setHiddenUids((prev) => {
      const next = new Set(prev);
      if (next.has(uid)) next.delete(uid);
      else next.add(uid);
      try {
        localStorage.setItem(
          "intern-match-hidden-uids-v1",
          JSON.stringify(Array.from(next)),
        );
      } catch { /* ignore */ }
      return next;
    });
  }, []);

  const displayEvents = useMemo(
    () =>
      mergeMergedCustomTimetable(
        mergedEvents,
        customEvents,
        timetableEvents,
      ),
    [mergedEvents, customEvents, timetableEvents],
  );

  const displayBySource = useMemo(() => {
    const icalLocal = timetableEvents.filter(
      (e) => e.source === "ical_timetable",
    ).length;
    return {
      ...bySource,
      ical_timetable: (bySource.ical_timetable ?? 0) + icalLocal,
      user_custom:
        (bySource.user_custom ?? 0) +
        customEvents.filter((e) => e.source === "user_custom").length,
    };
  }, [bySource, timetableEvents, customEvents]);

  const activityEvents = useMemo(
    () =>
      displayEvents
        .filter((e) => NON_TIMETABLE_SOURCES.includes(e.source))
        .sort((a, b) => {
          const ta = a.start_iso ? Date.parse(a.start_iso) : 0;
          const tb = b.start_iso ? Date.parse(b.start_iso) : 0;
          return tb - ta;
        }),
    [displayEvents],
  );

  const wechatAccountList = useMemo(() => {
    const accounts = new Set<string>();
    for (const a of wechatArticles) {
      if (a.account) accounts.add(a.account);
    }
    return Array.from(accounts).sort();
  }, [wechatArticles]);

  const filteredWechat = useMemo(() => {
    if (wechatFilter === "all") return wechatArticles;
    return wechatArticles.filter((a) => a.account === wechatFilter);
  }, [wechatArticles, wechatFilter]);

  const wechatTotalPages = Math.max(1, Math.ceil(filteredWechat.length / PAGE_SIZE));
  const safeWechatPage = Math.min(wechatPage, wechatTotalPages);
  const visibleWechat = useMemo(
    () => filteredWechat.slice((safeWechatPage - 1) * PAGE_SIZE, safeWechatPage * PAGE_SIZE),
    [filteredWechat, safeWechatPage],
  );

  const handleRefresh = async () => {
    if (mergePollRef.current) {
      clearInterval(mergePollRef.current);
      mergePollRef.current = null;
    }
    setRefreshing(true);
    setLoadingCalendar(true);
    try {
      await axios.post("/api/campus/refresh-all");
    } catch {
      await loadMergedCalendar({ silent: true });
      setLoadingCalendar(false);
      setRefreshing(false);
      return;
    }
    // 爬取 + 公众号活动 AI 逐篇调用需数分钟～十余分钟，不能只在 2～3 秒后拉一次日历
    await new Promise((r) => setTimeout(r, 10_000));
    await loadMergedCalendar({ silent: true });
    if (tabRef.current === "wechat") loadWechatArticles();
    setLoadingCalendar(false);
    setRefreshing(false);

    let ticks = 0;
    const maxTicks = 24;
    mergePollRef.current = setInterval(() => {
      ticks += 1;
      void loadMergedCalendar({ silent: true });
      if (tabRef.current === "wechat") loadWechatArticles();
      if (ticks >= maxTicks && mergePollRef.current) {
        clearInterval(mergePollRef.current);
        mergePollRef.current = null;
      }
    }, 25_000);
  };

  const filteredActivities = useMemo(() => {
    return activityEvents.filter((e) => eventMatchesCategory(e, category));
  }, [activityEvents, category]);

  const totalPages = Math.max(1, Math.ceil(filteredActivities.length / PAGE_SIZE));
  const safePage = Math.min(currentPage, totalPages);

  const visibleActivities = useMemo(
    () => filteredActivities.slice((safePage - 1) * PAGE_SIZE, safePage * PAGE_SIZE),
    [filteredActivities, safePage],
  );

  const isLoading = loadingCalendar;

  const main =
    tab === "calendar" ? (
      <div className="space-y-4">
        <TimetableImportControls
          timetableCount={timetableEvents.length}
          savedUrl={savedTimetableUrl}
          onImported={(events, url) => {
            setTimetableEvents(events);
            saveTimetableToStorage(events, url);
            if (url !== undefined) setSavedTimetableUrl(url.trim());
          }}
          onClear={() => {
            clearTimetableStorage();
            setTimetableEvents([]);
            setSavedTimetableUrl("");
          }}
        />
        {user ? (
          <CampusCustomEventsPanel
            events={customEvents}
            onAdd={addCustomEvent}
            onRemove={removeCustomEvent}
          />
        ) : null}
        <div className="rounded-[1.75rem] bg-white/65 backdrop-blur-md border border-stone-200/50 shadow-sm p-4 sm:p-6 overflow-hidden">
          <CampusActivityCalendar
            events={displayEvents}
            bySource={displayBySource}
            loading={loadingCalendar}
            hiddenUids={hiddenUids}
            onToggleHidden={toggleHidden}
          />
        </div>
      </div>
    ) : tab === "wechat" ? (
      loadingWechat ? (
        <div className="flex items-center justify-center py-24 rounded-[1.75rem] bg-white/45 backdrop-blur-md border border-stone-200/40">
          <Loader2 size={28} className="animate-spin text-violet-500" />
        </div>
      ) : (
        <>
          <header className="mb-2">
            <h1 className="text-2xl sm:text-3xl md:text-4xl font-bold text-slate-900 tracking-tight">
              校园公众号精选
            </h1>
            <p className="text-sm text-slate-500 mt-2 max-w-2xl leading-relaxed">
              聚合搜狗微信搜索中校园相关公众号的文章，点击可跳转阅读原文。
            </p>
          </header>

          <WechatCustomQueriesPanel onAfterChange={loadWechatArticles} />

          <div className="flex flex-wrap gap-2 mb-6">
            <button
              type="button"
              onClick={() => { setWechatFilter("all"); setWechatPage(1); }}
              className={`inline-flex items-center gap-1.5 px-4 py-2 rounded-full text-xs sm:text-sm font-medium transition-all ${
                wechatFilter === "all"
                  ? "bg-slate-900 text-white shadow-md"
                  : "bg-white/60 backdrop-blur-md text-slate-600 border border-stone-200/50 hover:border-violet-300/45"
              }`}
            >
              <Sparkles size={14} className="opacity-80 shrink-0" />
              全部
              <span className="ml-1 text-[11px] opacity-70">
                {wechatArticles.length}
              </span>
            </button>
            {wechatAccountList.map((acct) => (
              <button
                key={acct}
                type="button"
                onClick={() => { setWechatFilter(acct); setWechatPage(1); }}
                className={`inline-flex items-center gap-1.5 px-4 py-2 rounded-full text-xs sm:text-sm font-medium transition-all ${
                  wechatFilter === acct
                    ? "bg-slate-900 text-white shadow-md"
                    : "bg-white/60 backdrop-blur-md text-slate-600 border border-stone-200/50 hover:border-violet-300/45"
                }`}
              >
                {acct}
                <span className="ml-1 text-[11px] opacity-70">
                  {wechatArticles.filter((a) => a.account === acct).length}
                </span>
              </button>
            ))}
          </div>

          {filteredWechat.length === 0 ? (
            <div className="rounded-[1.75rem] bg-white/50 backdrop-blur-md border border-dashed border-stone-300/55 py-16 text-center text-slate-400">
              <MessageCircle size={40} className="mx-auto mb-3 opacity-35" />
              <p className="text-sm">暂无公众号文章，点击刷新获取最新内容</p>
            </div>
          ) : (
            <>
              <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-2 2xl:grid-cols-3 gap-4 md:gap-5">
                {visibleWechat.map((article, i) => (
                  <WechatArticleCard
                    key={`${article.title}-${i}`}
                    article={article}
                    index={i}
                  />
                ))}
              </div>
              {wechatTotalPages > 1 && (
                <nav className="flex items-center justify-center gap-1.5 mt-8">
                  <button
                    type="button"
                    disabled={safeWechatPage <= 1}
                    onClick={() => setWechatPage((p) => Math.max(1, p - 1))}
                    className="p-2 rounded-xl text-slate-500 hover:text-violet-700 hover:bg-white/60 border border-transparent hover:border-stone-200/50 transition-colors disabled:opacity-30 disabled:pointer-events-none"
                  >
                    <ChevronLeft size={18} />
                  </button>

                  {(() => {
                    const pages: (number | "…")[] = [];
                    if (wechatTotalPages <= 7) {
                      for (let i = 1; i <= wechatTotalPages; i++) pages.push(i);
                    } else {
                      pages.push(1);
                      if (safeWechatPage > 3) pages.push("…");
                      const lo = Math.max(2, safeWechatPage - 1);
                      const hi = Math.min(wechatTotalPages - 1, safeWechatPage + 1);
                      for (let i = lo; i <= hi; i++) pages.push(i);
                      if (safeWechatPage < wechatTotalPages - 2) pages.push("…");
                      pages.push(wechatTotalPages);
                    }
                    return pages.map((p, idx) =>
                      p === "…" ? (
                        <span
                          key={`w-ellipsis-${idx}`}
                          className="w-9 text-center text-xs text-slate-400 select-none"
                        >
                          …
                        </span>
                      ) : (
                        <button
                          key={p}
                          type="button"
                          onClick={() => setWechatPage(p)}
                          className={`min-w-[36px] h-9 rounded-xl text-sm font-medium transition-all ${
                            p === safeWechatPage
                              ? "bg-slate-900 text-white shadow-md"
                              : "text-slate-600 bg-white/55 backdrop-blur-md border border-stone-200/50 hover:border-violet-300/60 hover:text-violet-700"
                          }`}
                        >
                          {p}
                        </button>
                      ),
                    );
                  })()}

                  <button
                    type="button"
                    disabled={safeWechatPage >= wechatTotalPages}
                    onClick={() => setWechatPage((p) => Math.min(wechatTotalPages, p + 1))}
                    className="p-2 rounded-xl text-slate-500 hover:text-violet-700 hover:bg-white/60 border border-transparent hover:border-stone-200/50 transition-colors disabled:opacity-30 disabled:pointer-events-none"
                  >
                    <ChevronRight size={18} />
                  </button>

                  <span className="ml-3 text-xs text-slate-400">
                    共 {filteredWechat.length} 篇
                  </span>
                </nav>
              )}
            </>
          )}
        </>
      )
    ) : isLoading ? (
      <div className="flex items-center justify-center py-24 rounded-[1.75rem] bg-white/45 backdrop-blur-md border border-stone-200/40">
        <Loader2 size={28} className="animate-spin text-violet-500" />
      </div>
    ) : (
      <>
        <header className="mb-2">
          <h1 className="text-2xl sm:text-3xl md:text-4xl font-bold text-slate-900 tracking-tight">
            投资你的校园生活
          </h1>
          <p className="text-sm text-slate-500 mt-2 max-w-2xl leading-relaxed">
            聚合官网活动、就业讲座、招聘会、企业宣讲会与公众号活动。按来源浏览，或切换到「活动日历」查看月视图。
          </p>
        </header>

        <div className="flex flex-wrap gap-2 mb-6">
          {ACTIVITY_CATEGORY_OPTIONS.map(({ id, label }) => (
            <button
              key={id}
              type="button"
              onClick={() => {
                setCategory(id);
                setCurrentPage(1);
              }}
              className={`inline-flex items-center gap-1.5 px-4 py-2 rounded-full text-xs sm:text-sm font-medium transition-all ${
                category === id
                  ? "bg-slate-900 text-white shadow-md"
                  : "bg-white/60 backdrop-blur-md text-slate-600 border border-stone-200/50 hover:border-violet-300/45"
              }`}
            >
              {id === "all" ? (
                <Sparkles size={14} className="opacity-80 shrink-0" />
              ) : id === "ongoing" ? (
                <Radio size={14} className="opacity-80 shrink-0" />
              ) : null}
              {label}
            </button>
          ))}
        </div>

        {filteredActivities.length === 0 ? (
          <div className="rounded-[1.75rem] bg-white/50 backdrop-blur-md border border-dashed border-stone-300/55 py-16 text-center text-slate-400 px-4">
            <Newspaper size={40} className="mx-auto mb-3 opacity-35" />
            {category === "wechat_event" ? (
              <div className="text-sm text-slate-500 max-w-lg mx-auto space-y-2">
                <p>
                  「公众号活动」由后台用 AI
                  分析微信文章生成，不是点浏览器刷新就能立刻出现。
                </p>
                <p>
                  请点击本页<strong>顶部 Tab 那一行最右侧</strong>的
                  <strong>圆形箭头</strong>（鼠标悬停显示「刷新当前视图」），会触发全量后台任务；AI
                  可能要 <strong>5～15 分钟</strong> 才写完数据。
                </p>
                <p className="text-xs text-slate-400">
                  若久等仍为空：确认后端已配置 DEEPSEEK_API_KEY，并查看终端是否报错；也可在 PowerShell
                  执行{" "}
                  <code className="text-violet-700 bg-violet-50 px-1 rounded">
                    POST /api/wechat-events/refresh
                  </code>{" "}
                  单独重跑抽取。
                </p>
              </div>
            ) : (
              <p className="text-sm">
                该分类下暂无内容，换个分类或点击顶部右侧圆形刷新试试
              </p>
            )}
          </div>
        ) : (
          <>
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-2 2xl:grid-cols-3 gap-4 md:gap-5">
              {visibleActivities.map((ev, i) => (
                <CampusEventSoftCard
                  key={ev.uid}
                  event={ev}
                  index={i}
                />
              ))}
            </div>
            {totalPages > 1 && (
              <nav className="flex items-center justify-center gap-1.5 mt-8">
                <button
                  type="button"
                  disabled={safePage <= 1}
                  onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
                  className="p-2 rounded-xl text-slate-500 hover:text-violet-700 hover:bg-white/60 border border-transparent hover:border-stone-200/50 transition-colors disabled:opacity-30 disabled:pointer-events-none"
                >
                  <ChevronLeft size={18} />
                </button>

                {(() => {
                  const pages: (number | "…")[] = [];
                  if (totalPages <= 7) {
                    for (let i = 1; i <= totalPages; i++) pages.push(i);
                  } else {
                    pages.push(1);
                    if (safePage > 3) pages.push("…");
                    const lo = Math.max(2, safePage - 1);
                    const hi = Math.min(totalPages - 1, safePage + 1);
                    for (let i = lo; i <= hi; i++) pages.push(i);
                    if (safePage < totalPages - 2) pages.push("…");
                    pages.push(totalPages);
                  }
                  return pages.map((p, idx) =>
                    p === "…" ? (
                      <span
                        key={`ellipsis-${idx}`}
                        className="w-9 text-center text-xs text-slate-400 select-none"
                      >
                        …
                      </span>
                    ) : (
                      <button
                        key={p}
                        type="button"
                        onClick={() => setCurrentPage(p)}
                        className={`min-w-[36px] h-9 rounded-xl text-sm font-medium transition-all ${
                          p === safePage
                            ? "bg-slate-900 text-white shadow-md"
                            : "text-slate-600 bg-white/55 backdrop-blur-md border border-stone-200/50 hover:border-violet-300/60 hover:text-violet-700"
                        }`}
                      >
                        {p}
                      </button>
                    ),
                  );
                })()}

                <button
                  type="button"
                  disabled={safePage >= totalPages}
                  onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
                  className="p-2 rounded-xl text-slate-500 hover:text-violet-700 hover:bg-white/60 border border-transparent hover:border-stone-200/50 transition-colors disabled:opacity-30 disabled:pointer-events-none"
                >
                  <ChevronRight size={18} />
                </button>

                <span className="ml-3 text-xs text-slate-400">
                  共 {filteredActivities.length} 条
                </span>
              </nav>
            )}
          </>
        )}
      </>
    );

  const right = (
    <CampusSoftRightPanel
      events={displayEvents}
      loading={loadingCalendar}
      onGoCalendar={() => setTab("calendar")}
    />
  );

  return (
    <CampusSoftShell
      tab={tab}
      onTabChange={(t) => {
        setTab(t);
        if (t === "articles") setCurrentPage(1);
        if (t === "wechat") setWechatPage(1);
      }}
      onRefresh={handleRefresh}
      refreshing={refreshing}
      main={main}
      right={right}
    />
  );
}
