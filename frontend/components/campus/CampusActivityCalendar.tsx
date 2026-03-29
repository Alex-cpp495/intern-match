"use client";

import { useMemo, useState } from "react";
import {
  AlertTriangle,
  ChevronLeft,
  ChevronRight,
  Clock,
  Download,
  Eye,
  EyeOff,
  ExternalLink,
  MapPin,
} from "lucide-react";
import {
  ACTIVITY_META,
  type ActivityKind,
  classifyActivity,
  countByActivityKind,
} from "@/lib/activityTypes";
import {
  getEventHoldStatus,
  HOLD_STATUS_META,
} from "@/lib/eventHoldStatus";

export type CalendarSource =
  | "unnc_events"
  | "careers_lecture"
  | "careers_jobfair"
  | "careers_teachin"
  | "ical_timetable"
  | "user_custom";

export interface MergedCalendarEvent {
  uid: string;
  title: string;
  start_iso: string | null;
  end_iso: string | null;
  all_day: boolean;
  busy: boolean;
  source: CalendarSource;
  location: string;
  url: string;
  description: string;
  categories: string[];
}

const WEEK_LABELS = ["一", "二", "三", "四", "五", "六", "日"];

const KIND_ORDER: ActivityKind[] = [
  "exam_mock",
  "campus_graduation",
  "campus_open_day",
  "campus_inclusion",
  "campus_competition",
  "campus_symposium",
  "grad_study",
  "workshop",
  "industry_talk",
  "career_series",
  "consulting",
  "campus_event",
  "careers_other",
  "timetable",
  "other",
];

const MAX_TITLES_IN_CELL = 3;

function pad2(n: number) {
  return String(n).padStart(2, "0");
}

function localDateKey(d: Date): string {
  return `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())}`;
}

function parseStartDate(ev: MergedCalendarEvent): string | null {
  if (!ev.start_iso) return null;
  const t = Date.parse(ev.start_iso);
  if (Number.isNaN(t)) return null;
  return localDateKey(new Date(t));
}

/** 跨日活动：在 start～end 的每个本地日历日都占位（最多 60 天防脏数据） */
function localDateKeysForEventRange(ev: MergedCalendarEvent): string[] {
  if (!ev.start_iso) return [];
  const startMs = Date.parse(ev.start_iso);
  if (Number.isNaN(startMs)) return [];
  const endMs = ev.end_iso ? Date.parse(ev.end_iso) : startMs;
  const endOk = !Number.isNaN(endMs) ? endMs : startMs;
  const start = new Date(startMs);
  start.setHours(0, 0, 0, 0);
  const endDay = new Date(Math.max(startMs, endOk));
  endDay.setHours(0, 0, 0, 0);
  const keys: string[] = [];
  const cur = new Date(start);
  let guard = 0;
  while (cur <= endDay && guard < 60) {
    keys.push(localDateKey(cur));
    cur.setDate(cur.getDate() + 1);
    guard += 1;
  }
  return keys;
}

function sourceLabel(source: CalendarSource): string {
  switch (source) {
    case "careers_lecture":
      return "Careers";
    case "careers_jobfair":
      return "招聘会";
    case "careers_teachin":
      return "宣讲会";
    case "unnc_events":
      return "官网";
    case "ical_timetable":
      return "课表";
    case "user_custom":
      return "自建";
    default:
      return "其他来源";
  }
}

interface Props {
  events: MergedCalendarEvent[];
  bySource: Record<string, number>;
  loading?: boolean;
  hiddenUids: Set<string>;
  onToggleHidden: (uid: string) => void;
}

export function CampusActivityCalendar({
  events,
  bySource,
  loading,
  hiddenUids,
  onToggleHidden,
}: Props) {
  const [viewMonth, setViewMonth] = useState(() => {
    const n = new Date();
    return new Date(n.getFullYear(), n.getMonth(), 1);
  });
  const [selectedKey, setSelectedKey] = useState<string | null>(() =>
    localDateKey(new Date()),
  );

  const kindCounts = useMemo(() => countByActivityKind(events), [events]);

  const { byDay, undated } = useMemo(() => {
    const map: Record<string, MergedCalendarEvent[]> = {};
    const noDate: MergedCalendarEvent[] = [];
    for (const ev of events) {
      const keys = localDateKeysForEventRange(ev);
      if (keys.length === 0) {
        noDate.push(ev);
        continue;
      }
      for (const key of keys) {
        if (!map[key]) map[key] = [];
        map[key].push(ev);
      }
    }
    for (const k of Object.keys(map)) {
      map[k].sort((a, b) => {
        const ta = a.start_iso ? Date.parse(a.start_iso) : 0;
        const tb = b.start_iso ? Date.parse(b.start_iso) : 0;
        return ta - tb;
      });
    }
    return { byDay: map, undated: noDate };
  }, [events]);

  const conflictSet = useMemo(() => {
    const timetable = events.filter(
      (e) => e.source === "ical_timetable" && e.start_iso && e.end_iso,
    );
    if (timetable.length === 0) return new Set<string>();

    const slots = timetable.map((e) => ({
      s: Date.parse(e.start_iso!),
      e: Date.parse(e.end_iso!),
    }));

    const ids = new Set<string>();
    for (const ev of events) {
      if (ev.source === "ical_timetable") continue;
      if (!ev.start_iso || !ev.end_iso) continue;
      const evS = Date.parse(ev.start_iso);
      const evE = Date.parse(ev.end_iso);
      if (Number.isNaN(evS) || Number.isNaN(evE)) continue;
      for (const sl of slots) {
        if (evS < sl.e && evE > sl.s) {
          ids.add(ev.uid);
          break;
        }
      }
    }
    return ids;
  }, [events]);

  const year = viewMonth.getFullYear();
  const month = viewMonth.getMonth();
  const first = new Date(year, month, 1);
  const last = new Date(year, month + 1, 0);
  const daysInMonth = last.getDate();
  const startPad = (first.getDay() + 6) % 7;

  const prevMonth = () => setViewMonth(new Date(year, month - 1, 1));
  const nextMonth = () => setViewMonth(new Date(year, month + 1, 1));
  const goToday = () => {
    const n = new Date();
    setViewMonth(new Date(n.getFullYear(), n.getMonth(), 1));
    setSelectedKey(localDateKey(n));
  };

  const monthTitle = `${year} 年 ${month + 1} 月`;
  const selectedEvents = selectedKey ? byDay[selectedKey] ?? [] : [];

  const cellMinH = "min-h-[7.5rem]";

  if (loading) {
    return (
      <div className="card p-12 flex items-center justify-center text-slate-400 text-sm">
        加载日历…
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="card p-3 sm:p-4">
        <p className="text-xs font-medium text-slate-600 mb-2">活动类型（按标题与正文自动归类）</p>
        <div className="flex flex-wrap gap-x-3 gap-y-2 text-[11px] text-slate-600">
          {KIND_ORDER.map((kind) => {
            const n = kindCounts[kind];
            if (n === 0) return null;
            const meta = ACTIVITY_META[kind];
            return (
              <span key={kind} className="inline-flex items-center gap-1.5">
                <span className={`w-2 h-2 rounded-full shrink-0 ${meta.dot}`} />
                <span>{meta.label}</span>
                <span className="text-slate-400 tabular-nums">({n})</span>
              </span>
            );
          })}
        </div>
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 mt-2">
          <p className="text-[10px] text-slate-400">
            数据：官网 {bySource.unnc_events ?? 0} 条 · Careers{" "}
            {bySource.careers_lecture ?? 0} 条 · 招聘会{" "}
            {bySource.careers_jobfair ?? 0} 条 · 宣讲会{" "}
            {bySource.careers_teachin ?? 0} 条 · 个人课表{" "}
            {bySource.ical_timetable ?? 0} 条 · 自建{" "}
            {bySource.user_custom ?? 0} 条（已与下方月历合并）
          </p>
          <a
            href="/api/calendar/merged.ics"
            className="inline-flex items-center gap-1.5 text-[11px] font-medium text-indigo-600 hover:text-indigo-800 border border-indigo-200 rounded-lg px-2.5 py-1 w-fit bg-white hover:bg-indigo-50/80 transition"
            target="_blank"
            rel="noopener noreferrer"
            download="unnc-campus-merged.ics"
          >
            <Download size={13} />
            下载 .ics 导入系统日历
          </a>
        </div>
      </div>

      <div className="flex flex-col gap-4 lg:flex-row lg:items-start">
        {/* 左侧：月历 */}
        <div className="card overflow-hidden flex-1 min-w-0">
          <div className="flex items-center justify-between px-3 py-2.5 border-b border-slate-100 bg-slate-50/80">
            <button
              type="button"
              onClick={prevMonth}
              className="p-1.5 rounded-lg text-slate-500 hover:bg-white hover:text-indigo-600 transition"
              aria-label="上一月"
            >
              <ChevronLeft size={20} />
            </button>
            <div className="flex items-center gap-2">
              <span className="text-sm font-semibold text-slate-800">{monthTitle}</span>
              <button
                type="button"
                onClick={goToday}
                className="text-xs px-2 py-0.5 rounded-full bg-white border border-slate-200 text-slate-600 hover:border-indigo-300 hover:text-indigo-600 transition"
              >
                今天
              </button>
            </div>
            <button
              type="button"
              onClick={nextMonth}
              className="p-1.5 rounded-lg text-slate-500 hover:bg-white hover:text-indigo-600 transition"
              aria-label="下一月"
            >
              <ChevronRight size={20} />
            </button>
          </div>

          <div className="p-1.5 sm:p-2 overflow-x-auto">
            <div className="min-w-[340px] sm:min-w-0">
              <div className="grid grid-cols-7 gap-1 text-center text-[10px] sm:text-[11px] text-slate-400 font-medium mb-1">
                {WEEK_LABELS.map((w) => (
                  <div key={w} className="py-1">
                    {w}
                  </div>
                ))}
              </div>
              <div className="grid grid-cols-7 gap-1">
                {Array.from({ length: startPad }).map((_, i) => (
                  <div key={`pad-${i}`} className={`${cellMinH} rounded-lg`} />
                ))}
                {Array.from({ length: daysInMonth }, (_, i) => {
                  const day = i + 1;
                  const key = `${year}-${pad2(month + 1)}-${pad2(day)}`;
                  const dayEventsAll = byDay[key] ?? [];
                  const dayEventsVisible = dayEventsAll.filter(
                    (e) => !hiddenUids.has(e.uid),
                  );
                  const isToday = key === localDateKey(new Date());
                  const isSelected = key === selectedKey;
                  const dayHasConflict = dayEventsVisible.some((e) =>
                    conflictSet.has(e.uid),
                  );

                  return (
                    <button
                      key={key}
                      type="button"
                      onClick={() => setSelectedKey(key)}
                      className={`${cellMinH} h-full w-full rounded-lg text-left flex flex-col p-1 sm:p-1.5 transition border ${
                        dayHasConflict
                          ? isSelected
                            ? "border-red-600 bg-red-100/90 ring-1 ring-red-300"
                            : "border-red-400 bg-red-100/50 hover:bg-red-100/80"
                          : isSelected
                            ? "border-indigo-500 bg-indigo-50/90 ring-1 ring-indigo-200"
                            : isToday
                              ? "border-indigo-200 bg-indigo-50/30"
                              : "border-slate-100 bg-white hover:bg-slate-50/80"
                      }`}
                    >
                      <span
                        className={`text-[11px] sm:text-xs font-semibold shrink-0 mb-1 ${
                          isSelected ? "text-indigo-800" : "text-slate-700"
                        }`}
                      >
                        {day}
                      </span>
                      <div className="flex flex-col gap-0.5 flex-1 min-h-0 overflow-hidden">
                        {dayEventsVisible.slice(0, MAX_TITLES_IN_CELL).map((ev) => {
                          const kind = classifyActivity(ev);
                          const bar = ACTIVITY_META[kind].cellBar;
                          return (
                            <div
                              key={ev.uid}
                              title={
                                conflictSet.has(ev.uid)
                                  ? `⚠ 与课表冲突 — ${ev.title}`
                                  : ev.title
                              }
                              className={`text-[9px] sm:text-[10px] leading-snug line-clamp-2 pl-1 py-0.5 rounded border-l-[3px] ${bar}`}
                            >
                              {ev.title}
                            </div>
                          );
                        })}
                        {dayEventsVisible.length > MAX_TITLES_IN_CELL && (
                          <span className="text-[9px] text-slate-400 pl-0.5 pt-0.5">
                            +{dayEventsVisible.length - MAX_TITLES_IN_CELL} 项…
                          </span>
                        )}
                      </div>
                    </button>
                  );
                })}
              </div>
            </div>
          </div>
        </div>

        {/* 右侧：当日活动详情（大屏固定右侧；小屏在日历下方） */}
        <aside className="w-full lg:w-[min(24rem,34%)] lg:shrink-0 lg:sticky lg:top-16 lg:max-h-[calc(100vh-4.5rem)] lg:overflow-y-auto">
          <div className="card p-4">
            <h3 className="text-sm font-semibold text-slate-800 mb-3">
              {selectedKey ? `${selectedKey} 的活动` : "选一天查看"}
            </h3>
            {selectedEvents.length === 0 ? (
              <p className="text-sm text-slate-400">当天暂无活动</p>
            ) : (
              <ul className="space-y-3">
                {selectedEvents.map((ev) => {
                  const kind = classifyActivity(ev);
                  const meta = ACTIVITY_META[kind];
                  const hold = getEventHoldStatus(ev);
                  const holdMeta = HOLD_STATUS_META[hold];
                  const hasConflict = conflictSet.has(ev.uid);
                  const isHidden = hiddenUids.has(ev.uid);
                  return (
                    <li key={ev.uid} className={isHidden ? "opacity-45" : ""}>
                      <div
                        className={`block rounded-xl border p-3 transition group ${
                          isHidden
                            ? "border-slate-200 bg-slate-50/50"
                            : hasConflict
                              ? "border-red-200 bg-red-50/30 hover:border-red-300"
                              : "border-slate-100 hover:border-indigo-200 hover:bg-indigo-50/30"
                        }`}
                      >
                        <div className="flex items-start justify-between gap-2">
                          <div className="min-w-0 flex-1">
                            <div className="flex flex-wrap items-center gap-1.5 mb-1">
                              <span
                                className={`inline-block text-[10px] px-1.5 py-0.5 rounded font-medium ${meta.badge}`}
                              >
                                {meta.label}
                              </span>
                              <span
                                className={`inline-block text-[10px] px-1.5 py-0.5 rounded font-medium ${holdMeta.className}`}
                              >
                                {holdMeta.label}
                              </span>
                              <span className="text-[10px] text-slate-400">
                                {sourceLabel(ev.source)}
                              </span>
                              {hasConflict && !isHidden && (
                                <span className="inline-flex items-center gap-0.5 text-[10px] text-red-600 font-medium">
                                  <AlertTriangle
                                    size={11}
                                    className="text-red-500 fill-red-500"
                                    strokeWidth={2.5}
                                  />
                                  与课表冲突
                                </span>
                              )}
                              {isHidden && (
                                <span className="text-[10px] text-slate-400 italic">
                                  已隐藏
                                </span>
                              )}
                            </div>
                            {ev.url && !isHidden ? (
                              <a
                                href={ev.url}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="text-sm font-medium text-slate-800 hover:text-indigo-700 line-clamp-3 block"
                              >
                                {ev.title}
                              </a>
                            ) : (
                              <h4 className={`text-sm font-medium line-clamp-3 ${isHidden ? "text-slate-400" : "text-slate-800"}`}>
                                {ev.title}
                              </h4>
                            )}
                            <div className="flex flex-col gap-1 mt-1.5 text-xs text-slate-500">
                              {ev.start_iso && (
                                <span className="flex items-center gap-1">
                                  <Clock size={11} className="shrink-0" />
                                  {new Date(ev.start_iso).toLocaleString("zh-CN", {
                                    month: "numeric",
                                    day: "numeric",
                                    hour: "2-digit",
                                    minute: "2-digit",
                                  })}
                                  {ev.end_iso &&
                                    ` – ${new Date(ev.end_iso).toLocaleTimeString("zh-CN", {
                                      hour: "2-digit",
                                      minute: "2-digit",
                                    })}`}
                                </span>
                              )}
                              {ev.location?.trim() && (
                                <span className="flex items-start gap-1 break-all">
                                  <MapPin size={11} className="shrink-0 mt-0.5" />
                                  {ev.location}
                                </span>
                              )}
                            </div>
                            {!isHidden && ev.description?.trim() && (
                              <p className="text-xs text-slate-500 mt-2 line-clamp-4">
                                {ev.description}
                              </p>
                            )}
                          </div>
                          <div className="flex flex-col items-center gap-1 shrink-0">
                            <button
                              type="button"
                              title={isHidden ? "在日历中显示" : "从日历中隐藏"}
                              onClick={() => onToggleHidden(ev.uid)}
                              className={`p-1.5 rounded-lg border transition ${
                                isHidden
                                  ? "border-slate-200 text-slate-400 hover:text-indigo-600 hover:border-indigo-200 hover:bg-indigo-50/50"
                                  : "border-slate-100 text-slate-300 hover:text-orange-500 hover:border-orange-200 hover:bg-orange-50/50"
                              }`}
                            >
                              {isHidden ? <Eye size={13} /> : <EyeOff size={13} />}
                            </button>
                            {ev.url && !isHidden && (
                              <a
                                href={ev.url}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="p-1.5 rounded-lg border border-transparent text-slate-300 hover:text-indigo-500"
                              >
                                <ExternalLink size={13} />
                              </a>
                            )}
                          </div>
                        </div>
                      </div>
                    </li>
                  );
                })}
              </ul>
            )}
          </div>
        </aside>
      </div>

      {undated.length > 0 && (
        <div className="card p-4 border-dashed">
          <h3 className="text-sm font-semibold text-slate-600 mb-2">
            未解析到具体日期的条目（{undated.length}）
          </h3>
          <ul className="space-y-2 text-xs text-slate-500">
            {undated.slice(0, 8).map((ev) => {
              const kind = classifyActivity(ev);
              return (
                <li key={ev.uid} className="line-clamp-2">
                  <span
                    className={`inline-block w-1.5 h-1.5 rounded-full align-middle shrink-0 mr-1 ${ACTIVITY_META[kind].dot}`}
                  />
                  <span className="text-slate-400 mr-1">
                    [{ACTIVITY_META[kind].label}]
                  </span>
                  {ev.title}
                </li>
              );
            })}
            {undated.length > 8 && (
              <li className="text-slate-400">… 还有 {undated.length - 8} 条</li>
            )}
          </ul>
        </div>
      )}
    </div>
  );
}
