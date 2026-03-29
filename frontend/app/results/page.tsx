"use client";

import {
  Suspense,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import axios from "axios";
import {
  RadarChart, Radar, PolarGrid, PolarAngleAxis,
  ResponsiveContainer, Tooltip,
} from "recharts";
import {
  MapPin, Clock, Briefcase, Building2, ExternalLink,
  ArrowLeft, Sparkles, Wifi, RefreshCw, Trophy, ChevronDown,
  ChevronUp, Heart, ThumbsUp, ThumbsDown, Search, SlidersHorizontal,
  TrendingUp, AlertCircle, Lightbulb, CalendarDays,
} from "lucide-react";
import {
  toggleSavedJob,
  isJobSaved,
  loadLastMatch,
  loadProfile,
  getMatchSessionStorage,
  type SavedJob,
} from "@/lib/storage";
import {
  buildSmartCalendarPrefillFromMatch,
  saveSmartCalendarPrefillToSession,
} from "@/lib/matchToCalendarPrefill";
import { useAuth } from "@/hooks/useAuth";

interface DimensionScores {
  d1_skill: number;
  d2_time: number;
  d3_interest: number;
  d4_ability: number;
  d5_culture: number;
}

interface JobResult {
  id: string;
  title: string;
  company: string;
  location: string;
  salary: string;
  work_type: string;
  weekly_hours: number;
  is_remote: boolean;
  industry?: string;
  tags: string[];
  description: string;
  source: string;
  source_url: string;
  total_score: number;
  dimensions: DimensionScores;
  explanation: string;
}

interface SkillGap {
  skill: string;
  demand_count: number;
  demand_ratio: number;
}

interface WeakDimension {
  dimension: string;
  label: string;
  avg_score: number;
  tip: string;
}

interface Advice {
  skill_gaps: SkillGap[];
  weak_dimensions: WeakDimension[];
  summary: string;
}

interface MatchResponse {
  jobs: JobResult[];
  free_hours_per_week: number;
  total_jobs_scanned: number;
  advice?: Advice;
}

const DIMENSION_LABELS: Record<keyof DimensionScores, string> = {
  d1_skill: "技能匹配",
  d2_time: "时间适配",
  d3_interest: "兴趣契合",
  d4_ability: "能力水平",
  d5_culture: "企业适配",
};

const DIMENSION_COLORS: Record<keyof DimensionScores, string> = {
  d1_skill: "#6366f1",
  d2_time: "#22c55e",
  d3_interest: "#f59e0b",
  d4_ability: "#ec4899",
  d5_culture: "#14b8a6",
};

function jobToSaved(job: JobResult): Omit<SavedJob, "savedAt"> {
  return {
    id: job.id,
    title: job.title,
    company: job.company,
    location: job.location,
    salary: job.salary,
    work_type: job.work_type,
    is_remote: job.is_remote,
    tags: job.tags,
    source: job.source,
    source_url: job.source_url,
    total_score: job.total_score,
  };
}

function ScoreCircle({ score }: { score: number }) {
  const pct = Math.round(score * 100);
  const color =
    pct >= 80 ? "#22c55e" : pct >= 65 ? "#f59e0b" : "#94a3b8";
  const label =
    pct >= 80 ? "强烈推荐" : pct >= 65 ? "推荐" : "可尝试";

  return (
    <div className="flex flex-col items-center">
      <div
        className="w-16 h-16 rounded-full flex items-center justify-center font-bold text-xl border-4 text-white"
        style={{ backgroundColor: color, borderColor: color + "33" }}
      >
        {pct}
      </div>
      <span className="text-xs mt-1 font-medium" style={{ color }}>
        {label}
      </span>
    </div>
  );
}

function DimensionBar({
  label,
  value,
  color,
}: {
  label: string;
  value: number;
  color: string;
}) {
  return (
    <div className="flex items-center gap-3">
      <span className="text-xs text-slate-500 w-16 shrink-0">{label}</span>
      <div className="flex-1 bg-slate-100 rounded-full h-2 overflow-hidden">
        <div
          className="h-full rounded-full transition-all duration-700"
          style={{ width: `${value * 100}%`, backgroundColor: color }}
        />
      </div>
      <span className="text-xs font-medium text-slate-600 w-8 text-right">
        {Math.round(value * 100)}
      </span>
    </div>
  );
}

function RadarViz({ dimensions }: { dimensions: DimensionScores }) {
  const data = (Object.keys(DIMENSION_LABELS) as (keyof DimensionScores)[]).map(
    (key) => ({
      subject: DIMENSION_LABELS[key],
      score: Math.round(dimensions[key] * 100),
    })
  );
  return (
    <ResponsiveContainer width="100%" height={200}>
      <RadarChart data={data} margin={{ top: 10, right: 20, bottom: 10, left: 20 }}>
        <PolarGrid stroke="#e2e8f0" />
        <PolarAngleAxis
          dataKey="subject"
          tick={{ fontSize: 11, fill: "#64748b" }}
        />
        <Radar
          name="匹配度"
          dataKey="score"
          stroke="#6366f1"
          fill="#6366f1"
          fillOpacity={0.3}
          strokeWidth={2}
        />
        <Tooltip formatter={(v: number) => [`${v}分`, "匹配度"]} />
      </RadarChart>
    </ResponsiveContainer>
  );
}

function AdviceCard({ advice }: { advice: Advice }) {
  const [expanded, setExpanded] = useState(false);
  if (!advice || (!advice.skill_gaps.length && !advice.weak_dimensions.length && !advice.summary)) {
    return null;
  }

  return (
    <div className="card overflow-hidden">
      <button
        onClick={() => setExpanded((v) => !v)}
        className="w-full p-4 flex items-center justify-between hover:bg-slate-50 transition-colors"
      >
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-lg bg-amber-50 flex items-center justify-center">
            <Lightbulb size={16} className="text-amber-500" />
          </div>
          <div className="text-left">
            <span className="text-sm font-semibold text-slate-800">提升建议</span>
            <p className="text-xs text-slate-500">了解如何提高你的匹配分数</p>
          </div>
        </div>
        {expanded ? <ChevronUp size={16} className="text-slate-400" /> : <ChevronDown size={16} className="text-slate-400" />}
      </button>

      {expanded && (
        <div className="border-t border-slate-100 p-4 space-y-4">
          {advice.skill_gaps.length > 0 && (
            <div>
              <div className="flex items-center gap-1.5 text-xs font-semibold text-slate-600 mb-2">
                <TrendingUp size={13} />
                建议补充的技能
              </div>
              <div className="flex flex-wrap gap-2">
                {advice.skill_gaps.map((g) => (
                  <div
                    key={g.skill}
                    className="flex items-center gap-1.5 bg-amber-50 border border-amber-200 text-amber-800 text-xs px-3 py-1.5 rounded-full"
                  >
                    <AlertCircle size={11} />
                    {g.skill}
                    <span className="text-amber-500 font-medium">{Math.round(g.demand_ratio * 100)}%岗位需要</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {advice.weak_dimensions.length > 0 && (
            <div>
              <div className="flex items-center gap-1.5 text-xs font-semibold text-slate-600 mb-2">
                <AlertCircle size={13} />
                待提升维度
              </div>
              <div className="space-y-2">
                {advice.weak_dimensions.map((w) => (
                  <div key={w.dimension} className="bg-slate-50 rounded-xl p-3">
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-xs font-medium text-slate-700">{w.label}</span>
                      <span className="text-xs text-slate-400">平均 {Math.round(w.avg_score * 100)}分</span>
                    </div>
                    <p className="text-xs text-slate-500">{w.tip}</p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {advice.summary && (
            <div className="bg-indigo-50 rounded-xl p-4">
              <div className="flex items-center gap-1.5 text-indigo-600 text-xs font-semibold mb-2">
                <Sparkles size={13} />
                AI 提升建议
              </div>
              <p className="text-sm text-indigo-700 leading-relaxed whitespace-pre-line">
                {advice.summary}
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function JobCard({
  job,
  rank,
  favorited,
  onToggleFavorite,
  onFeedback,
  feedbackDone,
}: {
  job: JobResult;
  rank: number;
  favorited: boolean;
  onToggleFavorite: () => void;
  onFeedback: (helpful: boolean) => void;
  feedbackDone: boolean;
}) {
  const [expanded, setExpanded] = useState(rank <= 1);

  return (
    <div
      className={`card overflow-hidden transition-all ${
        rank === 1 ? "ring-2 ring-indigo-500 ring-offset-2" : ""
      }`}
    >
      {rank <= 3 && (
        <div
          className={`h-1 w-full ${
            rank === 1
              ? "bg-gradient-to-r from-indigo-500 to-purple-500"
              : rank === 2
              ? "bg-gradient-to-r from-emerald-400 to-teal-500"
              : "bg-gradient-to-r from-amber-400 to-orange-400"
          }`}
        />
      )}

      <div className="p-5">
        <div className="flex gap-4">
          <ScoreCircle score={job.total_score} />
          <div className="flex-1 min-w-0">
            <div className="flex items-start justify-between gap-2">
              <div>
                <h3 className="font-semibold text-slate-900 text-base leading-tight">
                  {rank === 1 && (
                    <Trophy size={14} className="inline text-yellow-500 mr-1" />
                  )}
                  {job.title}
                </h3>
                <p className="text-sm text-slate-500 mt-0.5 flex items-center gap-1 flex-wrap">
                  <Building2 size={12} className="shrink-0 opacity-60" />
                  {job.company}
                  {job.industry ? (
                    <span className="text-xs text-slate-400">· {job.industry}</span>
                  ) : null}
                </p>
              </div>
              <div className="flex items-center gap-1.5 shrink-0">
                <button
                  type="button"
                  onClick={onToggleFavorite}
                  className={`p-1.5 rounded-lg border transition ${
                    favorited
                      ? "bg-rose-50 border-rose-200 text-rose-600"
                      : "bg-white border-slate-200 text-slate-400 hover:border-rose-200 hover:text-rose-500"
                  }`}
                  title={favorited ? "取消收藏" : "收藏"}
                >
                  <Heart size={16} className={favorited ? "fill-current" : ""} />
                </button>
                {job.source_url ? (
                  <a
                    href={job.source_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className={`text-xs px-2 py-0.5 rounded-full font-medium flex items-center gap-1 hover:opacity-80 transition-opacity ${
                      job.source === "UNNC"
                        ? "bg-purple-100 text-purple-600"
                        : job.source === "Boss直聘"
                        ? "bg-blue-100 text-blue-600"
                        : "bg-slate-100 text-slate-500"
                    }`}
                  >
                    {job.source}
                    <ExternalLink size={10} />
                  </a>
                ) : (
                  <span
                    className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                      job.source === "UNNC"
                        ? "bg-purple-100 text-purple-600"
                        : job.source === "Boss直聘"
                        ? "bg-blue-100 text-blue-600"
                        : "bg-slate-100 text-slate-500"
                    }`}
                  >
                    {job.source}
                  </span>
                )}
              </div>
            </div>

            <div className="flex flex-wrap gap-x-4 gap-y-1 mt-2 text-xs text-slate-500">
              <span className="flex items-center gap-1">
                <MapPin size={11} /> {job.location}
              </span>
              <span className="flex items-center gap-1">
                <Clock size={11} /> {job.weekly_hours}h/周
              </span>
              {job.is_remote && (
                <span className="flex items-center gap-1 text-emerald-600">
                  <Wifi size={11} /> 远程可
                </span>
              )}
              <span className="font-medium text-emerald-600">{job.salary}</span>
            </div>

            <div className="flex flex-wrap gap-1.5 mt-3">
              {job.tags.slice(0, 5).map((tag) => (
                <span
                  key={tag}
                  className="bg-slate-50 text-slate-600 border border-slate-200 text-xs px-2 py-0.5 rounded-full"
                >
                  {tag}
                </span>
              ))}
            </div>
          </div>
        </div>

        <div className="flex items-center justify-center gap-4 mt-3">
          <button
            type="button"
            onClick={() => setExpanded((v) => !v)}
            className="flex-1 flex items-center justify-center gap-1 text-xs text-slate-400 hover:text-indigo-600 transition-colors"
          >
            {expanded ? (
              <>收起详情 <ChevronUp size={13} /></>
            ) : (
              <>查看详情 <ChevronDown size={13} /></>
            )}
          </button>
        </div>

        {expanded && (
          <div className="mt-4 border-t border-slate-100 pt-4 space-y-4">
            <div className="flex items-center justify-center gap-2">
              <span className="text-xs text-slate-400">这条推荐对你有用吗？</span>
              <button
                type="button"
                disabled={feedbackDone}
                onClick={() => onFeedback(true)}
                className="inline-flex items-center gap-1 text-xs px-2 py-1 rounded-lg border border-slate-200 hover:bg-emerald-50 hover:border-emerald-200 disabled:opacity-40"
              >
                <ThumbsUp size={12} /> 有用
              </button>
              <button
                type="button"
                disabled={feedbackDone}
                onClick={() => onFeedback(false)}
                className="inline-flex items-center gap-1 text-xs px-2 py-1 rounded-lg border border-slate-200 hover:bg-amber-50 hover:border-amber-200 disabled:opacity-40"
              >
                <ThumbsDown size={12} /> 一般
              </button>
              {feedbackDone && (
                <span className="text-xs text-emerald-600">已记录，感谢反馈</span>
              )}
            </div>

            <RadarViz dimensions={job.dimensions} />

            <div className="space-y-2">
              {(Object.keys(DIMENSION_LABELS) as (keyof DimensionScores)[]).map(
                (key) => (
                  <DimensionBar
                    key={key}
                    label={DIMENSION_LABELS[key]}
                    value={job.dimensions[key]}
                    color={DIMENSION_COLORS[key]}
                  />
                )
              )}
            </div>

            {job.explanation && (
              <div className="bg-indigo-50 rounded-xl p-4">
                <div className="flex items-center gap-1.5 text-indigo-600 text-xs font-semibold mb-2">
                  <Sparkles size={13} />
                  AI 推荐理由
                </div>
                <p className="text-sm text-indigo-700 leading-relaxed">
                  {job.explanation}
                </p>
              </div>
            )}

            {job.description && (
              <div>
                <p className="text-xs font-medium text-slate-500 mb-1.5">岗位描述</p>
                <p className="text-sm text-slate-600 leading-relaxed">
                  {job.description}
                </p>
              </div>
            )}

            {job.source_url && (
              <a
                href={job.source_url}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center justify-center gap-2 w-full py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-700 active:bg-indigo-800 text-white text-sm font-semibold transition-colors"
              >
                <ExternalLink size={14} />
                立即投递 · {job.source}
              </a>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function ResultsInner() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const { user, loading: authLoading } = useAuth();
  const [result, setResult] = useState<MatchResponse | null>(null);
  const [profile, setProfile] = useState<Record<string, unknown> | null>(null);
  const [activeTab, setActiveTab] = useState<"all" | "remote" | "parttime">("all");
  const [keyword, setKeyword] = useState("");
  const [industryFilter, setIndustryFilter] = useState("");
  const [sortBy, setSortBy] = useState<"score" | "hours">("score");
  const [, forceFavRender] = useState(0);
  const [feedbackSent, setFeedbackSent] = useState<Set<string>>(new Set());

  const urlSynced = useRef(false);
  const replaceTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (authLoading || !user) return;
    const uid = user.id;
    const ss = getMatchSessionStorage(uid);
    let raw = ss.result;
    let profileRaw = ss.profile;
    if (!raw) {
      const lm = loadLastMatch(uid);
      if (lm?.result) {
        raw = JSON.stringify(lm.result);
        if (lm.profile) profileRaw = JSON.stringify(lm.profile);
      }
    }
    if (!raw) {
      router.replace("/");
      return;
    }
    setResult(JSON.parse(raw) as MatchResponse);
    if (profileRaw) setProfile(JSON.parse(profileRaw));

    const q = searchParams.get("q") || "";
    const ind = searchParams.get("ind") || "";
    const sort = searchParams.get("sort");
    const tab = searchParams.get("tab");
    setKeyword(q);
    setIndustryFilter(ind);
    if (sort === "hours" || sort === "score") setSortBy(sort);
    if (tab === "remote" || tab === "parttime") setActiveTab(tab);
    urlSynced.current = true;
    // 仅首屏从 URL 读筛选条件，避免因本页 router.replace 触发重复初始化
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [router, authLoading, user]);

  const syncUrl = useCallback(() => {
    if (!urlSynced.current) return;
    const p = new URLSearchParams();
    if (keyword.trim()) p.set("q", keyword.trim());
    if (industryFilter) p.set("ind", industryFilter);
    if (sortBy !== "score") p.set("sort", sortBy);
    if (activeTab !== "all") p.set("tab", activeTab);
    const qs = p.toString();
    router.replace(qs ? `${pathname}?${qs}` : pathname, { scroll: false });
  }, [activeTab, industryFilter, keyword, pathname, router, sortBy]);

  useEffect(() => {
    if (replaceTimer.current) clearTimeout(replaceTimer.current);
    replaceTimer.current = setTimeout(syncUrl, 400);
    return () => {
      if (replaceTimer.current) clearTimeout(replaceTimer.current);
    };
  }, [keyword, industryFilter, sortBy, activeTab, syncUrl]);

  const industries = useMemo(() => {
    if (!result) return [];
    const s = new Set<string>();
    result.jobs.forEach((j) => {
      if (j.industry) s.add(j.industry);
    });
    return Array.from(s).sort();
  }, [result]);

  const filteredSortedJobs = useMemo(() => {
    if (!result) return [];
    let list = result.jobs.filter((job) => {
      if (activeTab === "remote") return job.is_remote;
      if (activeTab === "parttime") return job.work_type === "兼职";
      return true;
    });
    if (industryFilter) {
      list = list.filter((j) => (j.industry || "") === industryFilter);
    }
    if (keyword.trim()) {
      const q = keyword.trim().toLowerCase();
      list = list.filter(
        (j) =>
          j.title.toLowerCase().includes(q) ||
          j.company.toLowerCase().includes(q) ||
          j.tags.some((t) => t.toLowerCase().includes(q)) ||
          (j.description || "").toLowerCase().includes(q)
      );
    }
    const sorted = [...list];
    if (sortBy === "hours") {
      sorted.sort((a, b) => a.weekly_hours - b.weekly_hours);
    } else {
      sorted.sort((a, b) => b.total_score - a.total_score);
    }
    return sorted;
  }, [result, activeTab, industryFilter, keyword, sortBy]);

  const bumpFavorites = () => forceFavRender((n) => n + 1);

  const goSmartCalendarFromMatch = useCallback(() => {
    if (!user || !result) return;
    const p = loadProfile(user.id);
    const payload = buildSmartCalendarPrefillFromMatch(p, result);
    saveSmartCalendarPrefillToSession(payload);
    router.push("/campus/smart-calendar?from=match");
  }, [router, user, result]);

  const submitFeedback = async (job: JobResult, helpful: boolean) => {
    if (feedbackSent.has(job.id)) return;
    try {
      await axios.post("/api/feedback", {
        job_id: job.id,
        job_title: job.title,
        company: job.company,
        helpful,
        total_score: job.total_score,
      });
      setFeedbackSent((prev) => new Set(prev).add(job.id));
    } catch {
      setFeedbackSent((prev) => new Set(prev).add(job.id));
    }
  };

  if (authLoading || !user || !result) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="w-8 h-8 border-4 border-indigo-500 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div className="min-h-screen py-8 px-4">
      <div className="max-w-2xl mx-auto">
        <div className="flex items-center justify-between gap-2 mb-6">
          <button
            type="button"
            onClick={() => router.push("/")}
            className="flex items-center gap-2 text-sm text-slate-500 hover:text-indigo-600 transition"
          >
            <ArrowLeft size={16} />
            重新匹配
          </button>
          <button
            type="button"
            onClick={() => router.push("/saved")}
            className="text-xs text-slate-400 hover:text-indigo-600 flex items-center gap-1"
          >
            <Heart size={12} />
            我的收藏
          </button>
        </div>

        <div className="card p-5 mb-6">
          <div className="flex items-center justify-between mb-3">
            <h1 className="text-xl font-bold text-slate-900">匹配结果</h1>
            <span className="text-xs text-slate-400">
              扫描了 {result.total_jobs_scanned} 个岗位
            </span>
          </div>
          <div className="grid grid-cols-3 gap-3 text-center">
            <div className="bg-indigo-50 rounded-xl p-3">
              <div className="text-2xl font-bold text-indigo-600">
                {result.jobs.length}
              </div>
              <div className="text-xs text-slate-500 mt-0.5">推荐岗位</div>
            </div>
            <div className="bg-emerald-50 rounded-xl p-3">
              <div className="text-2xl font-bold text-emerald-600">
                {result.free_hours_per_week}h
              </div>
              <div className="text-xs text-slate-500 mt-0.5">每周空闲</div>
            </div>
            <div className="bg-amber-50 rounded-xl p-3">
              <div className="text-2xl font-bold text-amber-600">
                {result.jobs.length > 0
                  ? Math.round(result.jobs[0].total_score * 100)
                  : 0}
              </div>
              <div className="text-xs text-slate-500 mt-0.5">最高匹配分</div>
            </div>
          </div>
          {profile && (
            <div className="mt-3 flex flex-wrap gap-2">
              {((profile.skills as string[]) || []).slice(0, 4).map((s) => (
                <span
                  key={s}
                  className="bg-white border border-slate-200 text-xs text-slate-600 px-2 py-0.5 rounded-full"
                >
                  {s}
                </span>
              ))}
              {((profile.skills as string[]) || []).length > 4 && (
                <span className="text-xs text-slate-400">
                  +{((profile.skills as string[]) || []).length - 4} 项
                </span>
              )}
            </div>
          )}
        </div>

        {result.advice && (
          <div className="mb-4">
            <AdviceCard advice={result.advice} />
          </div>
        )}

        <div className="card p-5 mb-4 border-violet-200/60 bg-gradient-to-br from-violet-50/80 to-white">
          <div className="flex items-start gap-3">
            <div className="w-10 h-10 rounded-xl bg-violet-600 flex items-center justify-center shrink-0">
              <CalendarDays size={20} className="text-white" />
            </div>
            <div className="min-w-0 flex-1">
              <h2 className="text-sm font-semibold text-slate-900">
                联动校园日历
              </h2>
              <p className="text-xs text-slate-600 mt-1 leading-relaxed">
                根据本次匹配画像与提升建议，一键预填「智能活动筛选」；结合你在校园页导入的课表，生成可编辑的专属活动日历（宣讲会、讲座、工作坊等）。
              </p>
              <button
                type="button"
                onClick={goSmartCalendarFromMatch}
                className="mt-3 w-full sm:w-auto inline-flex items-center justify-center gap-2 rounded-xl bg-slate-900 text-white text-sm font-medium px-5 py-2.5 hover:bg-slate-800 transition-colors"
              >
                <Sparkles size={16} />
                生成校园活动日历
              </button>
            </div>
          </div>
        </div>

        <div className="card p-4 mb-4 space-y-3">
          <div className="flex items-center gap-2 text-xs font-medium text-slate-600">
            <SlidersHorizontal size={14} />
            筛选与排序
          </div>
          <div className="relative">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
            <input
              type="search"
              value={keyword}
              onChange={(e) => setKeyword(e.target.value)}
              placeholder="搜索岗位、公司、标签…"
              className="w-full pl-9 pr-3 py-2 text-sm border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
          </div>
          <div className="flex flex-wrap gap-2 items-center">
            <select
              value={industryFilter}
              onChange={(e) => setIndustryFilter(e.target.value)}
              className="text-sm border border-slate-200 rounded-lg px-2 py-1.5 bg-white text-slate-700"
            >
              <option value="">全部行业</option>
              {industries.map((ind) => (
                <option key={ind} value={ind}>
                  {ind}
                </option>
              ))}
            </select>
            <select
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value as "score" | "hours")}
              className="text-sm border border-slate-200 rounded-lg px-2 py-1.5 bg-white text-slate-700"
            >
              <option value="score">按匹配分</option>
              <option value="hours">按每周工时（升序）</option>
            </select>
          </div>
        </div>

        <div className="flex gap-2 mb-4 flex-wrap items-center">
          {(
            [
              { key: "all" as const, label: "全部", count: result.jobs.length },
              {
                key: "parttime" as const,
                label: "兼职",
                count: result.jobs.filter((j) => j.work_type === "兼职").length,
              },
              {
                key: "remote" as const,
                label: "远程",
                count: result.jobs.filter((j) => j.is_remote).length,
              },
            ] as const
          ).map((tab) => (
            <button
              key={tab.key}
              type="button"
              onClick={() => setActiveTab(tab.key)}
              className={`px-4 py-1.5 rounded-full text-sm font-medium transition ${
                activeTab === tab.key
                  ? "bg-indigo-600 text-white"
                  : "bg-white text-slate-600 border border-slate-200 hover:border-indigo-400"
              }`}
            >
              {tab.label}
              <span className="ml-1.5 text-xs opacity-70">{tab.count}</span>
            </button>
          ))}
          <button
            type="button"
            onClick={() => router.push("/")}
            className="ml-auto flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium bg-white border border-slate-200 text-slate-500 hover:border-indigo-400 hover:text-indigo-600 transition"
          >
            <RefreshCw size={12} />
            重新匹配
          </button>
        </div>

        <p className="text-xs text-slate-500 mb-3">
          当前列表 {filteredSortedJobs.length} 条
          {keyword.trim() || industryFilter || activeTab !== "all"
            ? "（已筛选）"
            : ""}
        </p>

        <div className="space-y-4">
          {filteredSortedJobs.length === 0 ? (
            <div className="card p-12 text-center text-slate-400">
              <Briefcase size={40} className="mx-auto mb-3 opacity-30" />
              <p>暂无符合筛选条件的岗位</p>
            </div>
          ) : (
            filteredSortedJobs.map((job, i) => (
              <JobCard
                key={job.id}
                job={job}
                rank={i + 1}
                favorited={isJobSaved(user.id, job.id)}
                onToggleFavorite={() => {
                  const row: SavedJob = {
                    ...jobToSaved(job),
                    savedAt: new Date().toISOString(),
                  };
                  toggleSavedJob(user.id, row);
                  bumpFavorites();
                }}
                onFeedback={(helpful) => submitFeedback(job, helpful)}
                feedbackDone={feedbackSent.has(job.id)}
              />
            ))
          )}
        </div>

        <div className="sticky bottom-0 z-10 mt-6 -mx-1 px-1 pt-2 pb-1 bg-gradient-to-t from-slate-50 via-slate-50/95 to-transparent">
          <div className="card p-4 shadow-lg border-indigo-200/50 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
            <div className="flex items-center gap-2 min-w-0">
              <CalendarDays size={18} className="text-indigo-600 shrink-0" />
              <p className="text-sm text-slate-700">
                投递之余，把校园活动排进日历？
              </p>
            </div>
            <button
              type="button"
              onClick={goSmartCalendarFromMatch}
              className="shrink-0 inline-flex items-center justify-center gap-2 rounded-xl bg-indigo-600 text-white text-sm font-medium px-5 py-2.5 hover:bg-indigo-700 transition-colors"
            >
              <Sparkles size={16} />
              生成校园活动日历
            </button>
          </div>
        </div>

        <p className="text-center text-xs text-slate-400 mt-8 mb-4">
          数据来源：实习僧 & 牛客网（全国）· NottFind
        </p>
      </div>
    </div>
  );
}

export default function ResultsPage() {
  return (
    <Suspense
      fallback={
        <div className="min-h-screen flex items-center justify-center">
          <div className="w-8 h-8 border-4 border-indigo-500 border-t-transparent rounded-full animate-spin" />
        </div>
      }
    >
      <ResultsInner />
    </Suspense>
  );
}
