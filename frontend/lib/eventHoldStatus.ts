export type EventHoldStatus = "upcoming" | "ongoing" | "past" | "unknown";

/** 与日历事件一致的时间字段，避免 lib 依赖组件造成循环引用 */
export interface EventTimingFields {
  start_iso: string | null;
  end_iso: string | null;
  all_day: boolean;
}

function startOfLocalDayMs(d: Date): number {
  return new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
}

function endOfLocalDayMs(d: Date): number {
  return startOfLocalDayMs(d) + 24 * 60 * 60 * 1000 - 1;
}

/**
 * 根据开始/结束时间判断活动是否已举办、进行中或尚未举办。
 * - 全日事件：按本地日历日的起止范围判断（支持跨日区间）。
 * - 无结束时间：以开始时刻为点事件，已过开始即视为已举办。
 */
export function getEventHoldStatus(
  ev: EventTimingFields,
  nowMs: number = Date.now(),
): EventHoldStatus {
  const startMs = ev.start_iso ? Date.parse(ev.start_iso) : NaN;
  const endMs = ev.end_iso ? Date.parse(ev.end_iso) : NaN;

  if (Number.isNaN(startMs)) {
    return "unknown";
  }

  if (ev.all_day) {
    const startD = new Date(startMs);
    const endD = Number.isNaN(endMs) ? startD : new Date(endMs);
    const rangeStart = startOfLocalDayMs(startD);
    const rangeEnd = endOfLocalDayMs(endD);
    if (nowMs < rangeStart) return "upcoming";
    if (nowMs > rangeEnd) return "past";
    return "ongoing";
  }

  const effectiveEndMs = Number.isNaN(endMs) ? startMs : endMs;
  if (nowMs < startMs) return "upcoming";
  if (nowMs > effectiveEndMs) return "past";
  return "ongoing";
}

export const HOLD_STATUS_META: Record<
  EventHoldStatus,
  { label: string; className: string }
> = {
  upcoming: {
    label: "未举办",
    className:
      "bg-emerald-100/90 text-emerald-900 border border-emerald-200/80",
  },
  ongoing: {
    label: "进行中",
    className: "bg-amber-100/90 text-amber-900 border border-amber-200/80",
  },
  past: {
    label: "已举办",
    className: "bg-slate-200/80 text-slate-600 border border-slate-300/60",
  },
  unknown: {
    label: "时间未定",
    className: "bg-slate-100/90 text-slate-500 border border-slate-200/70",
  },
};
