// localStorage / sessionStorage：按登录用户 ID 分桶，避免多账号共用一台电脑时数据串号

const LEGACY_PROFILE = "intern_profile";
const LEGACY_SAVED_JOBS = "intern_saved_jobs";
const LEGACY_LAST_MATCH = "intern_last_match";
const LEGACY_CHAT_DRAFT = "intern_chat_draft";
const LEGACY_SS_MATCH = "matchResult";
const LEGACY_SS_PROFILE = "userProfile";

function keyProfile(uid: number) {
  return `intern_profile_u${uid}`;
}
function keySavedJobs(uid: number) {
  return `intern_saved_jobs_u${uid}`;
}
function keyLastMatch(uid: number) {
  return `intern_last_match_u${uid}`;
}
function keyChatDraft(uid: number) {
  return `intern_chat_draft_u${uid}`;
}
function keySessionMatch(uid: number) {
  return `matchResult_u${uid}`;
}
function keySessionProfile(uid: number) {
  return `userProfile_u${uid}`;
}

/** 本地持久化的对话草稿（用于恢复上次对话） */
export interface ChatDraft {
  sessionId: string;
  messages: { role: "user" | "assistant"; content: string }[];
  collectedFields: string[];
  profile: Record<string, unknown> | null;
  ready: boolean;
  awaitingConfirm: boolean;
  updatedAt: string;
}

export interface StoredProfile {
  major: string;
  grade: string;
  skills: string[];
  interests: string[];
  intern_period: string;
  schedule_text: string;
  has_project: boolean;
  preferences: {
    company_size: string;
    industry: string;
    work_env: string;
  };
}

export interface SavedJob {
  id: string;
  title: string;
  company: string;
  location: string;
  salary: string;
  work_type: string;
  is_remote: boolean;
  tags: string[];
  source: string;
  source_url: string;
  total_score: number;
  savedAt: string;
}

// ── 用户画像 ──────────────────────────────────────

export function saveProfile(userId: number, p: StoredProfile): void {
  try {
    localStorage.setItem(keyProfile(userId), JSON.stringify(p));
  } catch {
    /* SSR / 配额 */
  }
}

export function loadProfile(userId: number): StoredProfile | null {
  try {
    const k = keyProfile(userId);
    const scoped = localStorage.getItem(k);
    if (scoped) return JSON.parse(scoped) as StoredProfile;
    const leg = localStorage.getItem(LEGACY_PROFILE);
    if (leg) {
      localStorage.setItem(k, leg);
      localStorage.removeItem(LEGACY_PROFILE);
      return JSON.parse(leg) as StoredProfile;
    }
    return null;
  } catch {
    return null;
  }
}

export function clearProfile(userId: number): void {
  try {
    localStorage.removeItem(keyProfile(userId));
  } catch {
    /* SSR */
  }
}

// ── 岗位收藏 ──────────────────────────────────────

export function getSavedJobs(userId: number): SavedJob[] {
  try {
    const k = keySavedJobs(userId);
    const scoped = localStorage.getItem(k);
    if (scoped) return JSON.parse(scoped) as SavedJob[];
    const leg = localStorage.getItem(LEGACY_SAVED_JOBS);
    if (leg) {
      localStorage.setItem(k, leg);
      localStorage.removeItem(LEGACY_SAVED_JOBS);
      return JSON.parse(leg) as SavedJob[];
    }
    return [];
  } catch {
    return [];
  }
}

export function isJobSaved(userId: number, id: string): boolean {
  return getSavedJobs(userId).some((j) => j.id === id);
}

/** 切换收藏状态，返回 true=已收藏 false=已取消 */
export function toggleSavedJob(userId: number, job: SavedJob): boolean {
  const jobs = getSavedJobs(userId);
  const idx = jobs.findIndex((j) => j.id === job.id);
  if (idx >= 0) {
    jobs.splice(idx, 1);
    try {
      localStorage.setItem(keySavedJobs(userId), JSON.stringify(jobs));
    } catch {
      /* */
    }
    return false;
  }
  jobs.unshift({ ...job, savedAt: new Date().toISOString() });
  try {
    localStorage.setItem(keySavedJobs(userId), JSON.stringify(jobs));
  } catch {
    /* */
  }
  return true;
}

export function removeSavedJob(userId: number, id: string): void {
  const jobs = getSavedJobs(userId).filter((j) => j.id !== id);
  try {
    localStorage.setItem(keySavedJobs(userId), JSON.stringify(jobs));
  } catch {
    /* */
  }
}

// ── 上次匹配结果 ──────────────────────────────────

export function saveLastMatch(
  userId: number,
  result: unknown,
  profile: unknown,
): void {
  try {
    localStorage.setItem(
      keyLastMatch(userId),
      JSON.stringify({
        result,
        profile,
        timestamp: new Date().toISOString(),
      }),
    );
    sessionStorage.setItem(keySessionMatch(userId), JSON.stringify(result));
    sessionStorage.setItem(keySessionProfile(userId), JSON.stringify(profile));
  } catch {
    /* */
  }
}

export function clearLastMatch(userId: number): void {
  try {
    localStorage.removeItem(keyLastMatch(userId));
  } catch {
    /* */
  }
}

export function loadLastMatch(userId: number): {
  result: unknown;
  profile: unknown;
  timestamp: string;
} | null {
  try {
    const k = keyLastMatch(userId);
    const scoped = localStorage.getItem(k);
    if (scoped) return JSON.parse(scoped);
    const leg = localStorage.getItem(LEGACY_LAST_MATCH);
    if (leg) {
      localStorage.setItem(k, leg);
      localStorage.removeItem(LEGACY_LAST_MATCH);
      return JSON.parse(leg);
    }
    return null;
  } catch {
    return null;
  }
}

// ── 上次智能活动筛选（校园日历 Agent）────────────────────

function keySmartCalendarLast(userId: number) {
  return `intern_smart_cal_last_u${userId}`;
}

export interface LastSmartCalendarSession {
  thread_id: string;
  summary: string;
  event_count: number;
  updatedAt: string;
}

export function saveLastSmartCalendarSession(
  userId: number,
  s: LastSmartCalendarSession,
): void {
  try {
    localStorage.setItem(keySmartCalendarLast(userId), JSON.stringify(s));
  } catch {
    /* */
  }
}

export function loadLastSmartCalendarSession(
  userId: number,
): LastSmartCalendarSession | null {
  try {
    const raw = localStorage.getItem(keySmartCalendarLast(userId));
    if (!raw) return null;
    return JSON.parse(raw) as LastSmartCalendarSession;
  } catch {
    return null;
  }
}

export function clearLastSmartCalendarSession(userId: number): void {
  try {
    localStorage.removeItem(keySmartCalendarLast(userId));
  } catch {
    /* */
  }
}

// ── 对话草稿（恢复上次聊天）─────────────────────────────

export function saveChatDraft(userId: number, d: ChatDraft): void {
  try {
    localStorage.setItem(keyChatDraft(userId), JSON.stringify(d));
  } catch {
    /* */
  }
}

export function loadChatDraft(userId: number): ChatDraft | null {
  try {
    const k = keyChatDraft(userId);
    const scoped = localStorage.getItem(k);
    if (scoped) return JSON.parse(scoped) as ChatDraft;
    const leg = localStorage.getItem(LEGACY_CHAT_DRAFT);
    if (leg) {
      localStorage.setItem(k, leg);
      localStorage.removeItem(LEGACY_CHAT_DRAFT);
      return JSON.parse(leg) as ChatDraft;
    }
    return null;
  } catch {
    return null;
  }
}

export function clearChatDraft(userId: number): void {
  try {
    localStorage.removeItem(keyChatDraft(userId));
  } catch {
    /* */
  }
}

/** 读取当前标签页内的匹配快照（优先当前用户，兼容旧 key） */
export function getMatchSessionStorage(userId: number): {
  result: string | null;
  profile: string | null;
} {
  try {
    const result =
      sessionStorage.getItem(keySessionMatch(userId)) ??
      sessionStorage.getItem(LEGACY_SS_MATCH);
    const profile =
      sessionStorage.getItem(keySessionProfile(userId)) ??
      sessionStorage.getItem(LEGACY_SS_PROFILE);
    return { result, profile };
  } catch {
    return { result: null, profile: null };
  }
}

/** 清除该用户在 sessionStorage 中的匹配快照（用于「我的」里一键清理） */
export function clearMatchSession(userId: number): void {
  try {
    sessionStorage.removeItem(keySessionMatch(userId));
    sessionStorage.removeItem(keySessionProfile(userId));
    sessionStorage.removeItem(LEGACY_SS_MATCH);
    sessionStorage.removeItem(LEGACY_SS_PROFILE);
  } catch {
    /* */
  }
}
