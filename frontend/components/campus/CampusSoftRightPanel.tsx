"use client";

import { CalendarDays, ChevronRight, Sparkles } from "lucide-react";
import type { MergedCalendarEvent } from "@/components/campus/CampusActivityCalendar";

function pad2(n: number) {
  return String(n).padStart(2, "0");
}

function localDateKey(d: Date): string {
  return `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())}`;
}

function dailyCountsLastDays(
  events: MergedCalendarEvent[],
  n: number,
): { label: string; count: number }[] {
  const today = new Date();
  const out: { label: string; count: number }[] = [];
  for (let i = n - 1; i >= 0; i--) {
    const d = new Date(
      today.getFullYear(),
      today.getMonth(),
      today.getDate() - i,
    );
    const key = localDateKey(d);
    let c = 0;
    for (const ev of events) {
      if (!ev.start_iso) continue;
      const t = Date.parse(ev.start_iso);
      if (Number.isNaN(t)) continue;
      if (localDateKey(new Date(t)) === key) c += 1;
    }
    out.push({
      label: `${d.getMonth() + 1}/${d.getDate()}`,
      count: c,
    });
  }
  return out;
}

function startOfTodayMs(): number {
  const d = new Date();
  return new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
}

function upcomingEvents(events: MergedCalendarEvent[], limit: number) {
  const t0 = startOfTodayMs();
  return [...events]
    .filter((e) => {
      if (!e.start_iso) return false;
      const t = Date.parse(e.start_iso);
      return !Number.isNaN(t) && t >= t0;
    })
    .sort((a, b) => Date.parse(a.start_iso!) - Date.parse(b.start_iso!))
    .slice(0, limit);
}

function formatShort(iso: string | null): string {
  if (!iso) return "";
  const t = Date.parse(iso);
  if (Number.isNaN(t)) return "";
  const d = new Date(t);
  return `${pad2(d.getMonth() + 1)}-${pad2(d.getDate())}`;
}

export function CampusSoftRightPanel({
  events,
  loading,
  onGoCalendar,
}: {
  events: MergedCalendarEvent[];
  loading: boolean;
  onGoCalendar?: () => void;
}) {
  const bars = dailyCountsLastDays(events, 12);
  const maxC = Math.max(1, ...bars.map((b) => b.count));
  const upcoming = upcomingEvents(events, 5);

  return (
    <div className="space-y-5">
      <div className="rounded-[1.75rem] bg-white/60 backdrop-blur-md p-5 shadow-sm border border-stone-200/45">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-semibold text-slate-800 flex items-center gap-2">
            <Sparkles size={16} className="text-violet-500" />
            活动热度
          </h3>
          <span className="text-[10px] uppercase tracking-wider text-slate-400">
            近 12 天
          </span>
        </div>
        {loading ? (
          <div className="h-28 flex items-center justify-center text-slate-400 text-xs">
            加载中…
          </div>
        ) : (
          <div className="flex items-end justify-between gap-1 h-28 pl-0.5">
            {bars.map((b, i) => (
              <div
                key={`${b.label}-${i}`}
                className="flex-1 flex flex-col items-center gap-1 min-w-0"
              >
                <div
                  className="w-full max-w-[14px] mx-auto rounded-full bg-gradient-to-t from-violet-200 to-pink-200 transition-all"
                  style={{
                    height: `${8 + (b.count / maxC) * 72}px`,
                    minHeight: b.count > 0 ? 12 : 4,
                  }}
                  title={`${b.label}: ${b.count} 场`}
                />
                <span className="text-[9px] text-slate-400 truncate w-full text-center">
                  {b.label}
                </span>
              </div>
            ))}
          </div>
        )}
        <p className="text-xs text-slate-500 mt-3">
          共收录{" "}
          <span className="font-semibold text-slate-700">{events.length}</span>{" "}
          条日历事件
        </p>
      </div>

      <div className="rounded-[1.75rem] bg-white/60 backdrop-blur-md p-5 shadow-sm border border-stone-200/45">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-semibold text-slate-800 flex items-center gap-2">
            <CalendarDays size={16} className="text-teal-600" />
            近期活动
          </h3>
          <button
            type="button"
            onClick={onGoCalendar}
            className="text-[11px] text-slate-400 hover:text-violet-600 flex items-center gap-0.5"
          >
            日历
            <ChevronRight size={12} />
          </button>
        </div>
        {loading ? (
          <p className="text-xs text-slate-400 py-4">加载中…</p>
        ) : upcoming.length === 0 ? (
          <p className="text-xs text-slate-400 py-2">暂无即将到来的事件</p>
        ) : (
          <ul className="space-y-2.5">
            {upcoming.map((ev) => (
              <li key={ev.uid}>
                <a
                  href={ev.url || undefined}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="block rounded-2xl bg-gradient-to-br from-teal-50/50 to-cyan-50/45 backdrop-blur-sm px-3 py-2.5 border border-teal-100/55 hover:border-teal-200/80 transition-colors"
                >
                  <p className="text-xs font-medium text-slate-800 line-clamp-2 leading-snug">
                    {ev.title}
                  </p>
                  <p className="text-[10px] text-teal-700/80 mt-1">
                    {formatShort(ev.start_iso)}
                    {ev.location ? ` · ${ev.location.slice(0, 18)}` : ""}
                  </p>
                </a>
              </li>
            ))}
          </ul>
        )}
      </div>

    </div>
  );
}
