/** 进入首页 AI 实习匹配对话的 URL（与首页 searchParams 联动） */
export const MATCH_ENTRY = "/?match=1" as const;

/** 强制新会话：清除本地草稿并重新拉开场白 */
export const MATCH_ENTRY_FRESH = "/?match=1&fresh=1" as const;
