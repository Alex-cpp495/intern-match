import type { MergedCalendarEvent } from "@/components/campus/CampusActivityCalendar";

function key(uid: number) {
  return `intern-match-user-custom-events-u${uid}`;
}

function isRecord(x: unknown): x is Record<string, unknown> {
  return typeof x === "object" && x !== null;
}

export function normalizeCustomEvent(raw: unknown): MergedCalendarEvent | null {
  if (!isRecord(raw)) return null;
  const uid = String(raw.uid ?? "");
  if (!uid || !uid.startsWith("user_custom_")) return null;
  return {
    uid,
    title: String(raw.title ?? "未命名"),
    start_iso: raw.start_iso == null ? null : String(raw.start_iso),
    end_iso: raw.end_iso == null ? null : String(raw.end_iso),
    all_day: Boolean(raw.all_day),
    busy: false,
    source: "user_custom",
    location: String(raw.location ?? ""),
    url: String(raw.url ?? ""),
    description: String(raw.description ?? ""),
    categories: Array.isArray(raw.categories)
      ? raw.categories.map(String)
      : [],
  };
}

export function loadCustomCampusEvents(uid: number): MergedCalendarEvent[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = localStorage.getItem(key(uid));
    if (!raw) return [];
    const arr = JSON.parse(raw) as unknown;
    if (!Array.isArray(arr)) return [];
    return arr
      .map((x) => normalizeCustomEvent(x))
      .filter((x): x is MergedCalendarEvent => x !== null);
  } catch {
    return [];
  }
}

export function saveCustomCampusEvents(
  uid: number,
  events: MergedCalendarEvent[],
): void {
  try {
    localStorage.setItem(key(uid), JSON.stringify(events));
  } catch {
    /* */
  }
}

export function newCustomEventUid(): string {
  return `user_custom_${Date.now()}_${Math.random().toString(36).slice(2, 9)}`;
}
