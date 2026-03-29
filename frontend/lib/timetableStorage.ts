import type { MergedCalendarEvent } from "@/components/campus/CampusActivityCalendar";

export const TIMETABLE_EVENTS_KEY = "intern-match-timetable-events-v1";
export const TIMETABLE_URL_KEY = "intern-match-timetable-url-v1";

function isRecord(x: unknown): x is Record<string, unknown> {
  return typeof x === "object" && x !== null;
}

const SOURCES: MergedCalendarEvent["source"][] = [
  "ical_timetable",
  "unnc_events",
  "careers_lecture",
  "careers_jobfair",
  "careers_teachin",
  "user_custom",
];

/** 将 POST /calendar/import/ical 返回的单条事件规范为前端合并类型 */
export function normalizeImportedEvent(raw: unknown): MergedCalendarEvent | null {
  if (!isRecord(raw)) return null;
  const uid = String(raw.uid ?? "");
  if (!uid) return null;
  const s = String(raw.source ?? "ical_timetable");
  const source = SOURCES.includes(s as MergedCalendarEvent["source"])
    ? (s as MergedCalendarEvent["source"])
    : "ical_timetable";
  return {
    uid,
    title: String(raw.title ?? ""),
    start_iso: raw.start_iso == null ? null : String(raw.start_iso),
    end_iso: raw.end_iso == null ? null : String(raw.end_iso),
    all_day: Boolean(raw.all_day),
    busy: Boolean(raw.busy),
    source,
    location: String(raw.location ?? ""),
    url: String(raw.url ?? ""),
    description: String(raw.description ?? ""),
    categories: Array.isArray(raw.categories)
      ? raw.categories.map(String)
      : [],
  };
}

export function loadTimetableFromStorage(): MergedCalendarEvent[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = localStorage.getItem(TIMETABLE_EVENTS_KEY);
    if (!raw) return [];
    const arr = JSON.parse(raw) as unknown;
    if (!Array.isArray(arr)) return [];
    return arr
      .map((x) => normalizeImportedEvent(x))
      .filter((x): x is MergedCalendarEvent => x !== null);
  } catch {
    return [];
  }
}

export function saveTimetableToStorage(
  events: MergedCalendarEvent[],
  url?: string,
): void {
  if (typeof window === "undefined") return;
  localStorage.setItem(TIMETABLE_EVENTS_KEY, JSON.stringify(events));
  if (url !== undefined) {
    if (url.trim()) localStorage.setItem(TIMETABLE_URL_KEY, url.trim());
    else localStorage.removeItem(TIMETABLE_URL_KEY);
  }
}

export function loadTimetableUrlFromStorage(): string {
  if (typeof window === "undefined") return "";
  try {
    return localStorage.getItem(TIMETABLE_URL_KEY) ?? "";
  } catch {
    return "";
  }
}

export function clearTimetableStorage(): void {
  if (typeof window === "undefined") return;
  localStorage.removeItem(TIMETABLE_EVENTS_KEY);
  localStorage.removeItem(TIMETABLE_URL_KEY);
}
