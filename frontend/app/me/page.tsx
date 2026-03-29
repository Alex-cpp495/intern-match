"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  User, GraduationCap, Wrench, Heart, Clock, Briefcase,
  ChevronRight, Trash2, Sparkles, Target, ArrowRight, Mail,
  CalendarDays,
} from "lucide-react";
import Link from "next/link";
import {
  loadProfile,
  clearProfile,
  clearLastMatch,
  loadLastMatch,
  getSavedJobs,
  type StoredProfile,
  clearChatDraft,
  clearMatchSession,
  loadLastSmartCalendarSession,
  clearLastSmartCalendarSession,
} from "@/lib/storage";
import { MATCH_ENTRY } from "@/lib/routes";
import { useAuth } from "@/hooks/useAuth";

interface LastMatch {
  result: { jobs: { title: string; company: string; total_score: number }[]; total_jobs_scanned: number };
  profile: StoredProfile;
  timestamp: string;
}

function ProfileSection({ profile }: { profile: StoredProfile }) {
  return (
    <div className="card p-5">
      <div className="flex items-center gap-3 mb-4">
        <div className="w-12 h-12 rounded-full bg-gradient-to-br from-indigo-500 to-purple-500 flex items-center justify-center">
          <User size={22} className="text-white" />
        </div>
        <div>
          <h2 className="font-bold text-slate-900">{profile.major || "未填写专业"} {profile.grade}</h2>
          <p className="text-xs text-slate-500">
            {profile.intern_period ? `${profile.intern_period}实习` : "未设置实习时间"}
            {profile.has_project && " · 有项目经验"}
          </p>
        </div>
      </div>

      {profile.skills.length > 0 && (
        <div className="mb-3">
          <div className="flex items-center gap-1.5 text-xs text-slate-500 mb-1.5">
            <Wrench size={12} /> 技能
          </div>
          <div className="flex flex-wrap gap-1.5">
            {profile.skills.map((s) => (
              <span key={s} className="text-xs bg-indigo-50 text-indigo-700 border border-indigo-100 px-2.5 py-1 rounded-full">
                {s}
              </span>
            ))}
          </div>
        </div>
      )}

      {profile.interests.length > 0 && (
        <div className="mb-3">
          <div className="flex items-center gap-1.5 text-xs text-slate-500 mb-1.5">
            <Target size={12} /> 兴趣方向
          </div>
          <div className="flex flex-wrap gap-1.5">
            {profile.interests.map((s) => (
              <span key={s} className="text-xs bg-emerald-50 text-emerald-700 border border-emerald-100 px-2.5 py-1 rounded-full">
                {s}
              </span>
            ))}
          </div>
        </div>
      )}

      {(profile.preferences.company_size || profile.preferences.industry || profile.preferences.work_env) && (
        <div>
          <div className="flex items-center gap-1.5 text-xs text-slate-500 mb-1.5">
            <Briefcase size={12} /> 偏好
          </div>
          <div className="flex flex-wrap gap-1.5">
            {profile.preferences.company_size && (
              <span className="text-xs bg-amber-50 text-amber-700 border border-amber-100 px-2.5 py-1 rounded-full">
                {profile.preferences.company_size}
              </span>
            )}
            {profile.preferences.industry && (
              <span className="text-xs bg-amber-50 text-amber-700 border border-amber-100 px-2.5 py-1 rounded-full">
                {profile.preferences.industry}
              </span>
            )}
            {profile.preferences.work_env && (
              <span className="text-xs bg-amber-50 text-amber-700 border border-amber-100 px-2.5 py-1 rounded-full">
                {profile.preferences.work_env}
              </span>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

export default function MePage() {
  const router = useRouter();
  const { user, loading: authLoading } = useAuth();
  const [profile, setProfile] = useState<StoredProfile | null>(null);
  const [lastMatch, setLastMatch] = useState<LastMatch | null>(null);
  const [savedCount, setSavedCount] = useState(0);
  const [lastSmartCal, setLastSmartCal] = useState(
    null as ReturnType<typeof loadLastSmartCalendarSession>,
  );

  useEffect(() => {
    if (!user) return;
    const uid = user.id;
    setProfile(loadProfile(uid));
    setLastMatch(loadLastMatch(uid) as LastMatch | null);
    setSavedCount(getSavedJobs(uid).length);
    setLastSmartCal(loadLastSmartCalendarSession(uid));
  }, [user]);

  const handleClear = () => {
    if (!user) return;
    const uid = user.id;
    if (confirm("确定清除当前账号在本机的画像、匹配记录与对话草稿？收藏不会被删除。")) {
      clearProfile(uid);
      clearChatDraft(uid);
      clearLastMatch(uid);
      clearMatchSession(uid);
      clearLastSmartCalendarSession(uid);
      setProfile(null);
      setLastMatch(null);
      setLastSmartCal(null);
    }
  };

  const matchTime = lastMatch?.timestamp
    ? new Date(lastMatch.timestamp).toLocaleString("zh-CN", {
        month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit",
      })
    : null;

  if (authLoading) {
    return (
      <div className="min-h-[40vh] flex items-center justify-center">
        <p className="text-slate-400 text-sm">加载中…</p>
      </div>
    );
  }

  if (!user) {
    return null;
  }

  return (
    <div className="min-h-screen py-6 px-4">
      <div className="max-w-2xl mx-auto">
        <h1 className="text-xl font-bold text-slate-900 mb-5">我的</h1>

        <div className="card p-5 mb-4 border-unnc-blue/15 bg-gradient-to-br from-slate-50 to-white">
          <div className="flex items-start gap-3">
            <div className="w-11 h-11 rounded-full bg-unnc-blue flex items-center justify-center shrink-0">
              <User size={20} className="text-white" />
            </div>
            <div className="min-w-0 flex-1">
              <p className="font-semibold text-slate-900 truncate">{user.username}</p>
              <p className="text-xs text-slate-500 flex items-center gap-1.5 mt-1">
                <Mail size={12} className="shrink-0" />
                <span className="truncate">{user.email}</span>
              </p>
              <p className="text-[11px] text-slate-400 mt-2">
                下方画像、匹配与收藏均与当前登录账号绑定，仅保存在本机浏览器。
              </p>
            </div>
          </div>
        </div>

        {profile ? (
          <ProfileSection profile={profile} />
        ) : (
          <div className="card p-6 text-center">
            <GraduationCap size={36} className="mx-auto mb-3 text-slate-300" />
            <p className="text-sm text-slate-500 mb-3">还没有个人画像</p>
            <button
              onClick={() => router.push(MATCH_ENTRY)}
              className="inline-flex items-center gap-1.5 text-sm bg-indigo-600 text-white px-5 py-2.5 rounded-xl hover:bg-indigo-700 transition font-medium"
            >
              <Sparkles size={14} /> 开始 AI 对话建立画像
            </button>
          </div>
        )}

        <div className="mt-4">
          <h2 className="text-sm font-semibold text-slate-700 mb-2 flex items-center gap-1.5">
            <Clock size={14} /> 上次匹配
          </h2>
          {lastMatch?.result ? (
            <button
              onClick={() => router.push("/results")}
              className="card p-4 w-full text-left hover:shadow-md transition-shadow group"
            >
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-semibold text-slate-800">
                    {lastMatch.result.jobs?.length || 0} 个推荐岗位
                  </p>
                  <p className="text-xs text-slate-500 mt-0.5">
                    {matchTime} · 共扫描 {lastMatch.result.total_jobs_scanned} 条
                  </p>
                  {lastMatch.result.jobs?.[0] && (
                    <p className="text-xs text-indigo-600 mt-1">
                      Top 1: {lastMatch.result.jobs[0].title} @ {lastMatch.result.jobs[0].company}
                      （{Math.round(lastMatch.result.jobs[0].total_score * 100)}分）
                    </p>
                  )}
                </div>
                <ChevronRight size={16} className="text-slate-300 group-hover:text-indigo-500 transition-colors" />
              </div>
            </button>
          ) : (
            <div className="card p-4 text-center text-sm text-slate-400">
              暂无匹配记录
            </div>
          )}
        </div>

        <div className="mt-4">
          <h2 className="text-sm font-semibold text-slate-700 mb-2 flex items-center gap-1.5">
            <CalendarDays size={14} /> 智能活动筛选
          </h2>
          {lastSmartCal ? (
            <Link
              href="/campus/smart-calendar"
              className="card p-4 w-full text-left hover:shadow-md transition-shadow group block"
            >
              <div className="flex items-center justify-between gap-2">
                <div className="min-w-0">
                  <p className="text-sm font-semibold text-slate-800">
                    上次筛选 · {lastSmartCal.event_count} 条活动
                  </p>
                  <p className="text-xs text-slate-500 mt-1 line-clamp-2">
                    {lastSmartCal.summary}
                  </p>
                  <p className="text-[11px] text-slate-400 mt-1">
                    {new Date(lastSmartCal.updatedAt).toLocaleString("zh-CN", {
                      month: "numeric",
                      day: "numeric",
                      hour: "2-digit",
                      minute: "2-digit",
                    })}
                  </p>
                </div>
                <ChevronRight size={16} className="text-slate-300 group-hover:text-violet-500 shrink-0" />
              </div>
            </Link>
          ) : (
            <div className="card p-4 text-center text-sm text-slate-400">
              暂无记录，可在{" "}
              <Link href="/campus" className="text-violet-600 hover:underline">
                校园动态
              </Link>{" "}
              进入智能活动筛选
            </div>
          )}
        </div>

        <div className="mt-4 space-y-2">
          <button
            onClick={() => router.push("/saved")}
            className="card p-4 w-full text-left hover:shadow-md transition-shadow flex items-center justify-between group"
          >
            <div className="flex items-center gap-3">
              <Heart size={18} className="text-rose-500" />
              <span className="text-sm font-medium text-slate-800">我的收藏</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-xs text-slate-400">{savedCount} 条</span>
              <ChevronRight size={16} className="text-slate-300 group-hover:text-indigo-500 transition-colors" />
            </div>
          </button>

          {profile && (
            <button
              onClick={() => router.push(MATCH_ENTRY)}
              className="card p-4 w-full text-left hover:shadow-md transition-shadow flex items-center justify-between group"
            >
              <div className="flex items-center gap-3">
                <Sparkles size={18} className="text-indigo-500" />
                <span className="text-sm font-medium text-slate-800">重新匹配</span>
              </div>
              <div className="flex items-center gap-1 text-xs text-indigo-500">
                进入匹配 <ArrowRight size={12} />
              </div>
            </button>
          )}
        </div>

        <div className="mt-8">
          <button
            onClick={handleClear}
            className="flex items-center gap-2 text-xs text-slate-400 hover:text-red-500 transition mx-auto"
          >
            <Trash2 size={12} />
            清除本账号的画像与匹配记录
          </button>
        </div>

        <p className="text-center text-xs text-slate-400 mt-6">
          NottFind · 当前账号 {user.username} · 数据仅保存在本机浏览器
        </p>
      </div>
    </div>
  );
}
