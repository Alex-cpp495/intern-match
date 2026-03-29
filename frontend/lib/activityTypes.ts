/**
 * 根据标题、正文与来源推断活动类型，用于日历配色与图例。
 * 规则按优先级匹配（越靠前越具体）。
 */

export type ActivityKind =
  | "exam_mock"
  | "campus_graduation"
  | "campus_open_day"
  | "campus_inclusion"
  | "campus_competition"
  | "campus_symposium"
  | "grad_study"
  | "workshop"
  | "industry_talk"
  | "career_series"
  | "consulting"
  | "campus_event"
  | "careers_other"
  | "timetable"
  | "other";

export interface ClassifiableEvent {
  title: string;
  description: string;
  source: string;
}

type Rule = { kind: ActivityKind; test: (zh: string, en: string) => boolean };

const rules: Rule[] = [
  {
    kind: "exam_mock",
    test: (zh, en) =>
      /模考|模拟考|模\s*拟/.test(zh) ||
      /practice\s*test|mock\s*exam|official\s*practice/i.test(en),
  },
  {
    kind: "campus_graduation",
    test: (zh, en) =>
      /毕业典礼|学位授予|commencement|graduation\s*ceremony/i.test(zh + en),
  },
  {
    kind: "campus_open_day",
    test: (zh, en) =>
      /开放日|校园开放|open\s*day|openday/i.test(zh + en),
  },
  {
    kind: "campus_inclusion",
    test: (zh) => /残障|融合周|共融|无障碍|inclusion\s*week/i.test(zh),
  },
  {
    kind: "campus_competition",
    test: (zh, en) =>
      (/竞赛|大赛|比赛|挑战赛|锦标赛|改装赛/.test(zh) && !/模考|模拟/.test(zh)) ||
      (/competition|contest|hackathon/i.test(en) && !/practice\s*test/i.test(en)),
  },
  {
    kind: "campus_symposium",
    test: (zh, en) =>
      /研讨会|高峰论坛|学术会议|symposium|forum(?!\s*career)/i.test(zh + en),
  },
  {
    kind: "grad_study",
    test: (zh, en) =>
      /宣讲会|招生|研究生院|升学|出国|留学|访学|硕士|博士项目/.test(zh) ||
      /info[-\s]?session|admission|graduate\s*school|master('|s)?\s*program/i.test(
        en,
      ) ||
      /\b(INSEAD|UCL|GRE|GMAT)\b.*(宣讲|session|info)/i.test(zh + en) ||
      /meet.*dean|university.*info|college.*fair/i.test(en),
  },
  {
    kind: "workshop",
    test: (zh, en) =>
      /workshop|工作坊|写作工坊|简历工坊|技能工作坊|职业工坊/i.test(zh + en) ||
      /personal\s*statement/i.test(en) ||
      /career\s*skill|discover\s*your\s*strengths|survival\s*guide/i.test(en),
  },
  {
    kind: "industry_talk",
    test: (zh, en) =>
      /行业分享|产业分享|industry\s*sharing|FOSE\s*industry|校友分享|企业分享|CMO|CEO分享|嘉宾分享/.test(
        zh + en,
      ) ||
      /alumni|guest\s*speaker|来自.*的分享/i.test(en),
  },
  {
    kind: "career_series",
    test: (zh, en) =>
      /春招|秋招|招聘季|career\s*preparation\s*week|career\s*week|双选会|招聘会|open\s*day.*career/i.test(
        zh + en,
      ),
  },
  {
    kind: "consulting",
    test: (zh, en) =>
      /咨询预约|预约咨询|一对一|简历辅导|面试辅导|职业咨询室|cv\s*clinic/i.test(zh) ||
      /coaching|career\s*advis/i.test(en),
  },
];

export function classifyActivity(ev: ClassifiableEvent): ActivityKind {
  if (ev.source === "ical_timetable") return "timetable";
  if (ev.source === "user_custom") return "campus_event";
  if (ev.source === "careers_jobfair") return "career_series";
  if (ev.source === "careers_teachin") return "industry_talk";

  const zh = `${ev.title}\n${ev.description}`;
  const en = zh.toLowerCase();

  for (const { kind, test } of rules) {
    if (test(zh, en)) return kind;
  }

  if (ev.source === "unnc_events") return "campus_event";
  if (ev.source === "careers_lecture") return "careers_other";
  return "other";
}

export const ACTIVITY_META: Record<
  ActivityKind,
  { label: string; cellBar: string; badge: string; dot: string }
> = {
  exam_mock: {
    label: "考试 / 模考",
    cellBar: "border-l-amber-500 bg-amber-50/90 text-amber-950",
    badge: "bg-amber-100 text-amber-900 border border-amber-200/80",
    dot: "bg-amber-500",
  },
  campus_graduation: {
    label: "毕业典礼",
    cellBar: "border-l-fuchsia-600 bg-fuchsia-50/90 text-fuchsia-950",
    badge: "bg-fuchsia-100 text-fuchsia-900 border border-fuchsia-200/80",
    dot: "bg-fuchsia-600",
  },
  campus_open_day: {
    label: "开放日",
    cellBar: "border-l-lime-600 bg-lime-50/90 text-lime-950",
    badge: "bg-lime-100 text-lime-900 border border-lime-200/80",
    dot: "bg-lime-600",
  },
  campus_inclusion: {
    label: "融合 / 共融",
    cellBar: "border-l-purple-600 bg-purple-50/90 text-purple-950",
    badge: "bg-purple-100 text-purple-900 border border-purple-200/80",
    dot: "bg-purple-600",
  },
  campus_competition: {
    label: "竞赛 / 大赛",
    cellBar: "border-l-red-500 bg-red-50/90 text-red-950",
    badge: "bg-red-100 text-red-900 border border-red-200/80",
    dot: "bg-red-500",
  },
  campus_symposium: {
    label: "研讨会 / 论坛",
    cellBar: "border-l-blue-600 bg-blue-50/90 text-blue-950",
    badge: "bg-blue-100 text-blue-900 border border-blue-200/80",
    dot: "bg-blue-600",
  },
  grad_study: {
    label: "升学 / 宣讲",
    cellBar: "border-l-sky-500 bg-sky-50/90 text-sky-950",
    badge: "bg-sky-100 text-sky-900 border border-sky-200/80",
    dot: "bg-sky-500",
  },
  workshop: {
    label: "技能工作坊",
    cellBar: "border-l-violet-500 bg-violet-50/90 text-violet-950",
    badge: "bg-violet-100 text-violet-900 border border-violet-200/80",
    dot: "bg-violet-500",
  },
  industry_talk: {
    label: "行业 / 嘉宾分享",
    cellBar: "border-l-rose-500 bg-rose-50/90 text-rose-950",
    badge: "bg-rose-100 text-rose-900 border border-rose-200/80",
    dot: "bg-rose-500",
  },
  career_series: {
    label: "招聘季 / 职业周",
    cellBar: "border-l-teal-500 bg-teal-50/90 text-teal-950",
    badge: "bg-teal-100 text-teal-900 border border-teal-200/80",
    dot: "bg-teal-500",
  },
  consulting: {
    label: "咨询辅导",
    cellBar: "border-l-cyan-500 bg-cyan-50/90 text-cyan-950",
    badge: "bg-cyan-100 text-cyan-900 border border-cyan-200/80",
    dot: "bg-cyan-500",
  },
  campus_event: {
    label: "校园活动",
    cellBar: "border-l-emerald-500 bg-emerald-50/90 text-emerald-950",
    badge: "bg-emerald-100 text-emerald-900 border border-emerald-200/80",
    dot: "bg-emerald-500",
  },
  careers_other: {
    label: "就业活动",
    cellBar: "border-l-indigo-500 bg-indigo-50/90 text-indigo-950",
    badge: "bg-indigo-100 text-indigo-900 border border-indigo-200/80",
    dot: "bg-indigo-500",
  },
  timetable: {
    label: "课表",
    cellBar: "border-l-orange-500 bg-orange-50/90 text-orange-950",
    badge: "bg-orange-100 text-orange-900 border border-orange-200/80",
    dot: "bg-orange-500",
  },
  other: {
    label: "其他",
    cellBar: "border-l-slate-400 bg-slate-50/90 text-slate-800",
    badge: "bg-slate-100 text-slate-700 border border-slate-200/80",
    dot: "bg-slate-400",
  },
};

export function countByActivityKind(
  events: ClassifiableEvent[],
): Record<ActivityKind, number> {
  const counts: Record<ActivityKind, number> = {
    exam_mock: 0,
    campus_graduation: 0,
    campus_open_day: 0,
    campus_inclusion: 0,
    campus_competition: 0,
    campus_symposium: 0,
    grad_study: 0,
    workshop: 0,
    industry_talk: 0,
    career_series: 0,
    consulting: 0,
    campus_event: 0,
    careers_other: 0,
    timetable: 0,
    other: 0,
  };
  for (const ev of events) {
    counts[classifyActivity(ev)] += 1;
  }
  return counts;
}
