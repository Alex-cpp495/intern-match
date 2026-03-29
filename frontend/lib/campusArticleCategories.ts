import type { CalendarSource } from "@/components/campus/CampusActivityCalendar";
import {
  getEventHoldStatus,
  type EventTimingFields,
} from "@/lib/eventHoldStatus";

export type ActivityCategoryId =
  | "all"
  | "ongoing"
  | "unnc_events"
  | "careers_lecture"
  | "careers_jobfair"
  | "careers_teachin";

export const ACTIVITY_CATEGORY_OPTIONS: {
  id: ActivityCategoryId;
  label: string;
}[] = [
  { id: "all", label: "全部" },
  { id: "ongoing", label: "正在进行" },
  { id: "unnc_events", label: "校园活动" },
  { id: "careers_lecture", label: "就业讲座" },
  { id: "careers_jobfair", label: "招聘会" },
  { id: "careers_teachin", label: "企业宣讲" },
];

type CategorizableEvent = EventTimingFields & { source: CalendarSource };

export function eventMatchesCategory(
  ev: CategorizableEvent,
  cat: ActivityCategoryId,
): boolean {
  if (cat === "all") return true;
  if (cat === "ongoing") return getEventHoldStatus(ev) === "ongoing";
  return ev.source === cat;
}

export type ArticleCategoryId = ActivityCategoryId;
export const ARTICLE_CATEGORY_OPTIONS = ACTIVITY_CATEGORY_OPTIONS;
