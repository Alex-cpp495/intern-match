/**
 * 从实习匹配画像 + 匹配结果生成「智能活动筛选」表单的预填内容。
 * 通过 sessionStorage 一次性传递给 /campus/smart-calendar?from=match
 */
import type { StoredProfile } from "@/lib/storage";

export const SMART_CALENDAR_PREFILL_SESSION_KEY =
  "intern-match-smart-calendar-prefill-v1";

export interface SmartCalendarPrefillPayload {
  goals: string;
  focus: string;
  grade: string;
  horizon_days: number;
  source: "match_results";
  savedAt: string;
}

interface AdviceLike {
  skill_gaps?: { skill: string }[];
  summary?: string;
}

interface JobLike {
  title: string;
  company: string;
  industry?: string;
  tags?: string[];
}

interface MatchResultLike {
  jobs?: JobLike[];
  advice?: AdviceLike | null;
}

export function buildSmartCalendarPrefillFromMatch(
  profile: StoredProfile | null,
  matchResult: MatchResultLike | null,
): SmartCalendarPrefillPayload {
  const lines: string[] = [];
  lines.push(
    "【来自实习匹配】希望筛选与目标岗位、技能短板相关的校园活动（宣讲会、工作坊、就业讲座、招聘会等），并结合课表避免冲突。",
  );

  if (profile) {
    const head = [profile.major, profile.grade].filter(Boolean).join(" ").trim();
    if (head) lines.push(`专业与年级：${head}`);
    if (profile.skills?.length)
      lines.push(`已具备技能：${profile.skills.join("、")}`);
    if (profile.interests?.length)
      lines.push(`兴趣与方向：${profile.interests.join("、")}`);
    if (profile.intern_period)
      lines.push(`期望实习时段：${profile.intern_period}`);
    const { company_size, industry, work_env } = profile.preferences || {};
    const prefs = [company_size, industry, work_env].filter(Boolean).join("；");
    if (prefs) lines.push(`实习偏好：${prefs}`);
    const st = profile.schedule_text?.trim();
    if (st)
      lines.push(
        `时间安排说明：${st.slice(0, 280)}${st.length > 280 ? "…" : ""}`,
      );
    if (profile.has_project) lines.push("有项目/实践经历，希望活动能强化可迁移能力。");
  }

  const advice = matchResult?.advice;
  if (advice?.skill_gaps?.length) {
    lines.push(
      `匹配报告建议补充的技能：${advice.skill_gaps.map((g) => g.skill).join("、")}`,
    );
  }
  if (advice?.summary?.trim()) {
    lines.push(
      `提升建议摘要：${advice.summary.trim().slice(0, 450)}${advice.summary.length > 450 ? "…" : ""}`,
    );
  }

  if (matchResult?.jobs?.length) {
    const top = matchResult.jobs.slice(0, 5);
    lines.push(
      `近期匹配到的岗位方向参考：${top.map((j) => `${j.title}（${j.company}）`).join("；")}`,
    );
  }

  const goals = lines.join("\n");

  const focusParts: string[] = [];
  if (profile?.interests?.length) focusParts.push(...profile.interests);
  if (profile?.skills?.length) focusParts.push(...profile.skills.slice(0, 8));
  if (profile?.preferences?.industry) focusParts.push(profile.preferences.industry);
  if (advice?.skill_gaps?.length)
    focusParts.push(...advice.skill_gaps.slice(0, 6).map((g) => g.skill));
  const inds = new Set<string>();
  matchResult?.jobs?.slice(0, 10).forEach((j) => {
    if (j.industry) inds.add(j.industry);
    j.tags?.slice(0, 3).forEach((t) => inds.add(t));
  });
  inds.forEach((i) => focusParts.push(i));

  const focus = Array.from(new Set(focusParts.map((s) => s.trim()).filter(Boolean)))
    .slice(0, 20)
    .join("，");

  const grade = profile?.grade?.trim() || "";

  return {
    goals,
    focus,
    grade,
    horizon_days: 21,
    source: "match_results",
    savedAt: new Date().toISOString(),
  };
}

export function saveSmartCalendarPrefillToSession(
  payload: SmartCalendarPrefillPayload,
): void {
  try {
    sessionStorage.setItem(
      SMART_CALENDAR_PREFILL_SESSION_KEY,
      JSON.stringify(payload),
    );
  } catch {
    /* ignore */
  }
}

export function consumeSmartCalendarPrefillFromSession(): SmartCalendarPrefillPayload | null {
  try {
    const raw = sessionStorage.getItem(SMART_CALENDAR_PREFILL_SESSION_KEY);
    if (!raw) return null;
    sessionStorage.removeItem(SMART_CALENDAR_PREFILL_SESSION_KEY);
    const data = JSON.parse(raw) as SmartCalendarPrefillPayload;
    if (!data || typeof data.goals !== "string") return null;
    return data;
  } catch {
    return null;
  }
}
