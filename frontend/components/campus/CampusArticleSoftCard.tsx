"use client";

import { useState } from "react";
import {
  ChevronDown,
  ChevronUp,
  ExternalLink,
  CalendarDays,
  MapPin,
  Clock,
} from "lucide-react";
import type { MergedCalendarEvent, CalendarSource } from "@/components/campus/CampusActivityCalendar";
import {
  classifyActivity,
  ACTIVITY_META,
} from "@/lib/activityTypes";
import {
  getEventHoldStatus,
  HOLD_STATUS_META,
} from "@/lib/eventHoldStatus";

const CARD_SHELL = [
  "from-rose-100/55 to-orange-50/45 border-rose-200/40",
  "from-orange-100/55 to-amber-50/45 border-orange-200/40",
  "from-violet-100/55 to-purple-50/45 border-violet-200/40",
  "from-teal-100/55 to-cyan-50/45 border-teal-200/40",
] as const;

const SOURCE_LABEL: Record<CalendarSource, string> = {
  unnc_events: "官网活动",
  careers_lecture: "就业讲座",
  careers_jobfair: "招聘会",
  careers_teachin: "企业宣讲",
  ical_timetable: "个人课表",
  user_custom: "自定义",
};

function formatEventDate(iso: string | null): string {
  if (!iso) return "";
  const t = Date.parse(iso);
  if (Number.isNaN(t)) return "";
  const d = new Date(t);
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const dd = String(d.getDate()).padStart(2, "0");
  return `${d.getFullYear()}-${mm}-${dd}`;
}

function formatEventTime(iso: string | null): string {
  if (!iso) return "";
  const t = Date.parse(iso);
  if (Number.isNaN(t)) return "";
  const d = new Date(t);
  return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
}

function buildTimeRange(ev: MergedCalendarEvent): string {
  if (ev.all_day) return "全天";
  const s = formatEventTime(ev.start_iso);
  const e = formatEventTime(ev.end_iso);
  if (s && e && s !== e) return `${s} - ${e}`;
  if (s) return s;
  return "";
}

export function CampusEventSoftCard({
  event,
  index,
}: {
  event: MergedCalendarEvent;
  index: number;
}) {
  const [expanded, setExpanded] = useState(false);
  const hasDesc = !!event.description && event.description.length > 20;
  const kind = classifyActivity({
    title: event.title,
    description: event.description || "",
    source: event.source,
  });
  const meta = ACTIVITY_META[kind];
  const shell = CARD_SHELL[index % CARD_SHELL.length];
  const dateStr = formatEventDate(event.start_iso);
  const timeRange = buildTimeRange(event);
  const holdStatus = getEventHoldStatus(event);
  const holdMeta = HOLD_STATUS_META[holdStatus];

  return (
    <article
      className={`rounded-[1.75rem] bg-gradient-to-br ${shell} backdrop-blur-md border shadow-sm hover:shadow-md transition-shadow overflow-hidden flex flex-col`}
    >
      <div className="p-5 flex flex-col flex-1 min-h-0">
        <div className="flex items-start justify-between gap-2 mb-3">
          <div className="flex flex-wrap items-center gap-1.5 min-w-0">
            <span
              className={`inline-flex items-center gap-1.5 text-[11px] font-medium px-2.5 py-1 rounded-full ${meta.badge}`}
            >
              <span className={`w-1.5 h-1.5 rounded-full ${meta.dot}`} />
              {meta.label}
            </span>
            <span
              className={`inline-flex items-center text-[11px] font-medium px-2.5 py-1 rounded-full shrink-0 ${holdMeta.className}`}
            >
              {holdMeta.label}
            </span>
          </div>
          {dateStr ? (
            <span className="text-[11px] text-slate-500 shrink-0 flex items-center gap-1">
              <CalendarDays size={10} className="opacity-60" />
              {dateStr}
            </span>
          ) : null}
        </div>
        <h3 className="text-base font-semibold text-slate-900 leading-snug line-clamp-3 min-h-[3.75rem]">
          {event.title}
        </h3>

        <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-slate-600 mt-2">
          {timeRange && (
            <span className="flex items-center gap-1">
              <Clock size={11} className="opacity-50" />
              {timeRange}
            </span>
          )}
          {event.location && (
            <span className="flex items-center gap-1 truncate max-w-[180px]">
              <MapPin size={11} className="opacity-50 shrink-0" />
              {event.location}
            </span>
          )}
        </div>

        <p className="text-[11px] text-slate-500 mt-3">
          {SOURCE_LABEL[event.source] ?? event.source}
        </p>

        <div className="flex flex-wrap items-center gap-2 mt-4 pt-3 border-t border-white/50">
          {hasDesc && (
            <button
              type="button"
              onClick={() => setExpanded((v) => !v)}
              className="text-xs text-slate-500 hover:text-violet-700 flex items-center gap-1"
            >
              {expanded ? (
                <>收起 <ChevronUp size={12} /></>
              ) : (
                <>详情 <ChevronDown size={12} /></>
              )}
            </button>
          )}
          {event.url && (
            <a
              href={event.url}
              target="_blank"
              rel="noopener noreferrer"
              className="ml-auto inline-flex items-center gap-1 text-xs font-medium text-slate-800 bg-white/90 hover:bg-white px-3 py-1.5 rounded-full border border-slate-200/80 shadow-sm"
            >
              查看详情
              <ExternalLink size={11} />
            </a>
          )}
        </div>
      </div>
      {expanded && hasDesc && (
        <div className="px-5 pb-5 -mt-1">
          <div className="rounded-2xl bg-white/80 border border-white/90 px-4 py-3 text-sm text-slate-700 leading-relaxed whitespace-pre-line max-h-64 overflow-y-auto">
            {event.description}
          </div>
        </div>
      )}
    </article>
  );
}
