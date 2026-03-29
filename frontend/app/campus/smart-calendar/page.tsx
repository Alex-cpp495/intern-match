"use client";

import {
  Suspense,
  useCallback,
  useEffect,
  useMemo,
  useState,
} from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import {
  ArrowLeft,
  Bot,
  CalendarCheck2,
  Loader2,
  MessageCircle,
  Send,
  Sparkles,
  X,
} from "lucide-react";
import {
  CampusActivityCalendar,
  type CalendarSource,
  type MergedCalendarEvent,
} from "@/components/campus/CampusActivityCalendar";
import { loadTimetableFromStorage } from "@/lib/timetableStorage";
import { consumeSmartCalendarPrefillFromSession } from "@/lib/matchToCalendarPrefill";
import { saveLastSmartCalendarSession } from "@/lib/storage";
import { useAuth } from "@/hooks/useAuth";
import {
  useSmartCalendarStore,
  type FilteredEvent,
  type SmartCalendarApiResponse,
} from "@/hooks/useSmartCalendarStore";

const DAY_NAMES = ["周日", "周一", "周二", "周三", "周四", "周五", "周六"];

function pad2(n: number) {
  return String(n).padStart(2, "0");
}

function extractBusySlots(
  timetableEvents: MergedCalendarEvent[],
): Record<string, string[][]> | null {
  const busy: Record<string, Set<string>> = {};
  let count = 0;
  for (const ev of timetableEvents) {
    if (!ev.start_iso || !ev.end_iso) continue;
    const start = new Date(ev.start_iso);
    const end = new Date(ev.end_iso);
    if (isNaN(start.getTime()) || isNaN(end.getTime())) continue;
    const day = DAY_NAMES[start.getDay()];
    const s = `${pad2(start.getHours())}:${pad2(start.getMinutes())}`;
    const e = `${pad2(end.getHours())}:${pad2(end.getMinutes())}`;
    const key = `${s}\t${e}`;
    if (!busy[day]) busy[day] = new Set();
    if (!busy[day].has(key)) {
      busy[day].add(key);
      count++;
    }
  }
  if (count === 0) return null;
  const out: Record<string, string[][]> = {};
  for (const [day, keys] of Object.entries(busy)) {
    out[day] = Array.from(keys).map((k) => {
      const [a, b] = k.split("\t");
      return [a, b];
    });
  }
  return out;
}

function toCalendarEvent(ev: FilteredEvent): MergedCalendarEvent {
  return {
    uid: ev.event_uid,
    title: ev.title,
    start_iso: ev.start_iso || null,
    end_iso: ev.end_iso || null,
    all_day: ev.all_day,
    busy: false,
    source: ev.source as CalendarSource,
    location: ev.location,
    url: ev.url,
    description: ev.description,
    categories: ev.categories,
  };
}

function persistSmartOutcome(userId: number | undefined, res: SmartCalendarApiResponse) {
  if (!userId || !res.thread_id) return;
  saveLastSmartCalendarSession(userId, {
    thread_id: res.thread_id,
    summary: res.result.summary,
    event_count: res.result.filtered_events.length,
    updatedAt: new Date().toISOString(),
  });
}

function SmartCalendarPageInner() {
  const searchParams = useSearchParams();
  const { user } = useAuth();
  const store = useSmartCalendarStore();

  const [goals, setGoals] = useState("");
  const [focus, setFocus] = useState("");
  const [horizon, setHorizon] = useState(14);
  const [grade, setGrade] = useState("");

  const [prefillHint, setPrefillHint] = useState<string | null>(null);

  const [timetableEvents, setTimetableEvents] = useState<MergedCalendarEvent[]>([]);
  const timetableBusy = useMemo(() => extractBusySlots(timetableEvents), [timetableEvents]);

  const [followupText, setFollowupText] = useState("");
  const [hiddenUids, setHiddenUids] = useState<Set<string>>(new Set());

  useEffect(() => {
    setTimetableEvents(loadTimetableFromStorage());
  }, []);

  useEffect(() => {
    if (searchParams.get("from") !== "match") return;
    const payload = consumeSmartCalendarPrefillFromSession();
    if (!payload) {
      setPrefillHint(null);
      return;
    }
    setGoals(payload.goals);
    setFocus(payload.focus);
    if (payload.grade) setGrade(payload.grade);
    if (payload.horizon_days && [7, 10, 14, 21].includes(payload.horizon_days)) {
      setHorizon(payload.horizon_days);
    }
    setPrefillHint("已根据实习匹配结果预填目标与关注方向，可直接提交或修改后再筛选。");
  }, [searchParams]);

  // persist outcome when data arrives
  useEffect(() => {
    if (store.data) {
      persistSmartOutcome(user?.id, store.data);
    }
  }, [store.data, user?.id]);

  // reset hidden set when new data arrives
  useEffect(() => {
    if (store.data) setHiddenUids(new Set());
  }, [store.data]);

  const calendarEvents = useMemo<MergedCalendarEvent[]>(() => {
    if (!store.data) return [];
    const recs = store.data.result.filtered_events.map(toCalendarEvent);
    const tt = timetableEvents.filter((e) => e.source === "ical_timetable");
    const seen = new Set(recs.map((r) => r.uid));
    const ttExtra = tt.filter((e) => !seen.has(e.uid));
    return [...recs, ...ttExtra];
  }, [store.data, timetableEvents]);

  const bySource = useMemo(() => {
    const counts: Record<string, number> = {};
    for (const ev of calendarEvents) {
      counts[ev.source] = (counts[ev.source] || 0) + 1;
    }
    return counts;
  }, [calendarEvents]);

  function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setHiddenUids(new Set());
    const focus_areas = focus
      .split(/[,，、\s]+/)
      .map((s) => s.trim())
      .filter(Boolean);
    store.submit({
      goals: goals.trim(),
      focus_areas,
      horizon_days: horizon,
      grade: grade.trim(),
      timetable_busy: timetableBusy,
    });
  }

  function onFollowup(e: React.FormEvent) {
    e.preventDefault();
    if (!followupText.trim() || !store.threadId) return;
    store.followup({
      goals: goals.trim(),
      focus_areas: [],
      horizon_days: horizon,
      grade: grade.trim(),
      thread_id: store.threadId,
      followup: followupText.trim(),
      timetable_busy: timetableBusy,
    });
    setFollowupText("");
  }

  const toggleHidden = useCallback((uid: string) => {
    setHiddenUids((prev) => {
      const next = new Set(prev);
      if (next.has(uid)) next.delete(uid);
      else next.add(uid);
      return next;
    });
  }, []);

  const visibleRecCount = useMemo(() => {
    if (!store.data) return 0;
    return store.data.result.filtered_events.filter((ev) => !hiddenUids.has(ev.event_uid))
      .length;
  }, [store.data, hiddenUids]);

  const { loading, followupLoading, data, error: err } = store;

  return (
    <div className="min-h-screen bg-gradient-to-b from-violet-50/40 via-white to-stone-50/30 py-8 px-4">
      <div className="max-w-6xl mx-auto">
        <Link
          href="/campus"
          className="inline-flex items-center gap-2 text-sm text-slate-500 hover:text-violet-600 transition mb-6"
        >
          <ArrowLeft size={16} />
          返回校园动态
        </Link>

        <div className="flex items-start gap-3 mb-2">
          <div className="w-11 h-11 rounded-2xl bg-gradient-to-br from-violet-500 to-indigo-600 flex items-center justify-center shadow-md shrink-0">
            <Bot size={22} className="text-white" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-slate-900 tracking-tight">
              智能活动筛选
            </h1>
            <p className="text-sm text-slate-500 mt-1 leading-relaxed">
              告诉 AI 助手你的目标和方向，它会从校园活动中筛选出最相关的，直接展示在日历上，你可以自由删改。
            </p>
            <p className="text-xs text-slate-400 mt-2">
              还没做实习匹配？{" "}
              <Link
                href="/?match=1"
                className="text-violet-600 hover:text-violet-800 font-medium"
              >
                先去 AI 匹配
              </Link>
            </p>
          </div>
        </div>

        {prefillHint && (
          <div className="mt-4 rounded-xl border border-emerald-200 bg-emerald-50/90 px-4 py-3 text-sm text-emerald-900">
            {prefillHint}
          </div>
        )}

        {/* ───── loading banner (visible even when returning from other pages) ───── */}
        {loading && (
          <div className="mt-6 rounded-2xl border border-violet-200 bg-violet-50/90 px-5 py-4 text-center">
            <div className="flex items-center justify-center gap-2 text-violet-900 font-semibold">
              <Loader2 size={18} className="animate-spin shrink-0" />
              AI 正在分析活动…
            </div>
            <p className="text-xs text-violet-800/80 mt-2 leading-relaxed">
              通常需 <span className="font-medium">30–90 秒</span>。
              你可以先浏览其他页面，生成不会中断——完成后回到这里即可查看结果。
            </p>
          </div>
        )}

        {/* ───── 筛选表单 ───── */}
        <form
          onSubmit={onSubmit}
          className="mt-8 rounded-[1.75rem] bg-white/80 backdrop-blur-md border border-stone-200/60 shadow-sm p-6 space-y-4"
        >
          <div>
            <label className="block text-xs font-medium text-slate-600 mb-1.5">
              你的目标 / 现状（必填）
            </label>
            <textarea
              value={goals}
              onChange={(e) => setGoals(e.target.value)}
              rows={5}
              required
              className="w-full rounded-xl border border-stone-200 px-4 py-3 text-sm outline-none focus:ring-2 focus:ring-violet-300/50 focus:border-violet-400"
              placeholder="例如：大二商科，想练演讲，对互联网和金融都在了解中…"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-600 mb-1.5">
              关注方向（可用逗号分隔）
            </label>
            <input
              type="text"
              value={focus}
              onChange={(e) => setFocus(e.target.value)}
              placeholder="软技能, 行业探索, 宣讲会"
              className="w-full rounded-xl border border-stone-200 px-4 py-2.5 text-sm outline-none focus:ring-2 focus:ring-violet-300/50"
            />
          </div>
          <div className="flex flex-wrap gap-4">
            <div>
              <label className="block text-xs font-medium text-slate-600 mb-1.5">
                时间范围（天）
              </label>
              <select
                value={horizon}
                onChange={(e) => setHorizon(Number(e.target.value))}
                className="rounded-xl border border-stone-200 px-3 py-2 text-sm"
              >
                {[7, 10, 14, 21].map((d) => (
                  <option key={d} value={d}>
                    未来 {d} 天
                  </option>
                ))}
              </select>
            </div>
            <div className="flex-1 min-w-[140px]">
              <label className="block text-xs font-medium text-slate-600 mb-1.5">
                年级（可选）
              </label>
              <input
                type="text"
                value={grade}
                onChange={(e) => setGrade(e.target.value)}
                placeholder="如 大二"
                className="w-full rounded-xl border border-stone-200 px-4 py-2.5 text-sm outline-none focus:ring-2 focus:ring-violet-300/50"
              />
            </div>
          </div>

          {/* ───── 课表状态 ───── */}
          <div className="flex items-center gap-2 rounded-xl border border-stone-100 bg-stone-50/50 px-4 py-3">
            <CalendarCheck2 size={16} className={timetableBusy ? "text-emerald-600" : "text-slate-400"} />
            {timetableBusy ? (
              <p className="text-xs text-slate-600">
                已加载课表（{timetableEvents.length} 条事件），筛选时将自动标记冲突活动
              </p>
            ) : (
              <p className="text-xs text-slate-500">
                未检测到课表，
                <Link href="/campus" className="text-violet-600 hover:text-violet-800 font-medium">
                  去校园动态页导入 Scientia 课表
                </Link>
                后可自动标记冲突
              </p>
            )}
          </div>

          {err && !data && (
            <div className="rounded-xl bg-red-50 border border-red-100 px-4 py-3 text-sm text-red-700">
              {err}
            </div>
          )}

          <button
            type="submit"
            disabled={loading}
            className="w-full sm:w-auto inline-flex items-center justify-center gap-2 rounded-xl bg-slate-900 text-white font-medium text-sm px-8 py-3 hover:bg-slate-800 disabled:opacity-60 transition-colors"
          >
            {loading ? (
              <>
                <Loader2 size={16} className="animate-spin" />
                AI 正在分析活动（通常约 30–90 秒，单次请求）…
              </>
            ) : (
              <>
                <Sparkles size={16} />
                {data ? "重新筛选" : "智能筛选"}
              </>
            )}
          </button>
        </form>

        {/* ───── 结果区 ───── */}
        {data && (
          <div className="mt-8 space-y-6">
            <div className="rounded-[1.75rem] bg-white/90 border border-violet-100/80 shadow-sm p-5">
              <div className="flex items-start justify-between gap-4">
                <div className="min-w-0 flex-1">
                  <h2 className="text-sm font-semibold text-violet-800 flex items-center gap-2 mb-2">
                    <Bot size={16} />
                    筛选摘要
                  </h2>
                  <p className="text-sm text-slate-700 leading-relaxed">
                    {data.result.summary}
                  </p>
                </div>
                <div className="text-right shrink-0">
                  <p className="text-2xl font-bold text-violet-600">
                    {visibleRecCount}
                  </p>
                  <p className="text-[11px] text-slate-400">
                    {hiddenUids.size > 0
                      ? `推荐活动可见（已隐藏 ${hiddenUids.size}）`
                      : "推荐活动"}
                  </p>
                </div>
              </div>
              <p className="text-[11px] text-slate-400 mt-3">
                模型 {data.model} · 消息步数约 {data.agent_steps} ·
                月历已合并个人课表（若在校园页导入）与推荐活动 ·
                眼睛图标仅隐藏推荐项
              </p>
            </div>

            {data.result.filtered_events.length > 0 && (
              <div className="rounded-[1.75rem] bg-white/80 border border-stone-200/50 shadow-sm p-4">
                <p className="text-xs font-medium text-slate-600 mb-2">
                  活动相关度（点击可隐藏）
                </p>
                <div className="flex flex-wrap gap-1.5">
                  {data.result.filtered_events
                    .filter((ev) => !hiddenUids.has(ev.event_uid))
                    .map((ev) => {
                      const pct = Math.round(ev.relevance_score * 100);
                      const bg =
                        pct >= 80
                          ? "bg-emerald-100 text-emerald-800 border-emerald-200"
                          : pct >= 60
                            ? "bg-blue-100 text-blue-800 border-blue-200"
                            : "bg-slate-100 text-slate-700 border-slate-200";
                      return (
                        <button
                          key={ev.event_uid}
                          type="button"
                          onClick={() => toggleHidden(ev.event_uid)}
                          title={`${ev.reason}\n点击隐藏`}
                          className={`inline-flex items-center gap-1 text-[10px] px-2 py-1 rounded-full border transition hover:opacity-70 ${bg}`}
                        >
                          <span className="font-semibold">{pct}%</span>
                          <span className="max-w-[120px] truncate">
                            {ev.title}
                          </span>
                          <X size={10} className="opacity-40" />
                        </button>
                      );
                    })}
                </div>
              </div>
            )}

            <CampusActivityCalendar
              events={calendarEvents}
              bySource={bySource}
              hiddenUids={hiddenUids}
              onToggleHidden={toggleHidden}
            />

            <div className="rounded-[1.75rem] bg-white/90 border border-indigo-100/80 shadow-sm p-5">
              <h2 className="text-sm font-semibold text-indigo-800 flex items-center gap-2 mb-2">
                <MessageCircle size={16} />
                继续调整
              </h2>
              <p className="text-xs text-slate-500 mb-3">
                对筛选结果不满意？可以继续对话，AI 会基于上下文重新筛选。
              </p>

              {err && (
                <div className="rounded-xl bg-red-50 border border-red-100 px-4 py-3 text-sm text-red-700 mb-3">
                  {err}
                </div>
              )}

              <form onSubmit={onFollowup} className="flex gap-2">
                <input
                  type="text"
                  value={followupText}
                  onChange={(e) => setFollowupText(e.target.value)}
                  placeholder="例如：只看宣讲会 / 去掉周末的 / 多筛一些技能类的…"
                  className="flex-1 rounded-xl border border-stone-200 px-4 py-2.5 text-sm outline-none focus:ring-2 focus:ring-indigo-300/50"
                />
                <button
                  type="submit"
                  disabled={followupLoading || !followupText.trim()}
                  className="shrink-0 inline-flex items-center justify-center gap-1.5 rounded-xl bg-indigo-600 text-white font-medium text-sm px-5 py-2.5 hover:bg-indigo-700 disabled:opacity-50 transition-colors"
                >
                  {followupLoading ? (
                    <Loader2 size={14} className="animate-spin" />
                  ) : (
                    <Send size={14} />
                  )}
                  发送
                </button>
              </form>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default function SmartCalendarPage() {
  return (
    <Suspense
      fallback={
        <div className="min-h-[50vh] flex flex-col items-center justify-center gap-2 text-slate-500 text-sm">
          <Loader2 className="w-8 h-8 animate-spin text-violet-500" />
          加载中…
        </div>
      }
    >
      <SmartCalendarPageInner />
    </Suspense>
  );
}
