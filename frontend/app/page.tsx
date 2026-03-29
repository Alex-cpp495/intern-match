"use client";

import { useState, useEffect, useRef, useCallback, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import Image from "next/image";
import axios from "axios";
import { UNNC_HERO_IMAGES } from "@/lib/unnc-brand";
import { MATCH_ENTRY, MATCH_ENTRY_FRESH } from "@/lib/routes";
import {
  Send, Sparkles, CheckCircle2, Circle, Loader2, ChevronRight,
  Pencil, X, Check, Heart, ArrowRight, Zap, Target, Briefcase,
  TrendingUp, Clock, Brain, BookOpen, Lock, LogIn, UserPlus,
} from "lucide-react";
import { useAuth, type AuthUser } from "@/hooks/useAuth";
import { motion } from "framer-motion";
import {
  saveProfile,
  saveLastMatch,
  loadProfile,
  clearProfile,
  saveChatDraft,
  loadChatDraft,
  clearChatDraft,
  type StoredProfile,
} from "@/lib/storage";

interface Message {
  role: "user" | "assistant";
  content: string;
}

interface Profile {
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

const ALL_FIELDS = ["专业年级", "技能", "兴趣方向", "时间安排"];

function isProgressFieldDone(field: string, collected: string[]): boolean {
  if (field === "时间安排") {
    return collected.includes("时间安排") || collected.some((c) => c.startsWith("实习时间段"));
  }
  return collected.includes(field);
}

// ─────────────────────────────────────────────
// Chat Sub-components (unchanged logic)
// ─────────────────────────────────────────────

function TypingDots() {
  return (
    <div className="flex items-center gap-1 px-4 py-3">
      {[0, 1, 2].map((i) => (
        <span
          key={i}
          className="w-2 h-2 bg-unnc-gold rounded-full animate-bounce"
          style={{ animationDelay: `${i * 0.15}s` }}
        />
      ))}
    </div>
  );
}

function MessageBubble({
  msg, index, onEdit,
}: {
  msg: Message;
  index: number;
  onEdit?: (index: number, newContent: string) => void;
}) {
  const isUser = msg.role === "user";
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(msg.content);
  const editRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (editing) {
      setDraft(msg.content);
      setTimeout(() => editRef.current?.focus(), 50);
    }
  }, [editing, msg.content]);

  const commitEdit = () => {
    if (draft.trim() && draft.trim() !== msg.content) onEdit?.(index, draft.trim());
    setEditing(false);
  };

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"} mb-3 group`}>
      {!isUser && (
        <div className="w-8 h-8 rounded-full bg-unnc-blue flex items-center justify-center mr-2 shrink-0 mt-1">
          <Sparkles size={14} className="text-white" />
        </div>
      )}
      <div className={`max-w-[78%] ${isUser ? "flex flex-col items-end gap-1" : ""}`}>
        {editing ? (
          <div className="w-full">
            <textarea
              ref={editRef}
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); commitEdit(); }
                if (e.key === "Escape") setEditing(false);
              }}
              rows={3}
              className="w-full text-sm text-slate-800 border-2 border-unnc-blue rounded-xl px-3 py-2 resize-none focus:outline-none focus:ring-2 focus:ring-unnc-blue bg-white"
            />
            <div className="flex gap-1.5 mt-1 justify-end">
              <button onClick={commitEdit} className="flex items-center gap-1 text-xs bg-unnc-blue text-white px-2.5 py-1 rounded-lg hover:bg-unnc-navy transition">
                <Check size={11} /> 确认
              </button>
              <button onClick={() => setEditing(false)} className="flex items-center gap-1 text-xs bg-slate-200 text-slate-600 px-2.5 py-1 rounded-lg hover:bg-slate-300 transition">
                <X size={11} /> 取消
              </button>
            </div>
          </div>
        ) : (
          <div className="relative">
            <div className={`rounded-2xl px-4 py-3 text-sm leading-relaxed whitespace-pre-wrap ${
              isUser
                ? "bg-unnc-blue text-white rounded-tr-sm"
                : "bg-white text-slate-800 shadow-sm border border-slate-100 rounded-tl-sm"
            }`}>
              {msg.content}
            </div>
            {isUser && onEdit && (
              <button
                onClick={() => setEditing(true)}
                className="absolute -left-7 top-1/2 -translate-y-1/2 opacity-0 group-hover:opacity-100 transition-opacity w-5 h-5 flex items-center justify-center text-slate-400 hover:text-unnc-blue"
                title="编辑此消息"
              >
                <Pencil size={12} />
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function CollectedField({ label, done }: { label: string; done: boolean }) {
  return (
    <div className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium transition-all ${
      done
        ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
        : "bg-slate-50 text-slate-400 border border-slate-200"
    }`}>
      {done ? <CheckCircle2 size={12} className="text-emerald-500" /> : <Circle size={12} />}
      {label}
    </div>
  );
}

const HERO_SLIDE_MS = 6500;

function useHeroCarousel() {
  const [index, setIndex] = useState(0);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const armTimer = useCallback(() => {
    if (typeof window === "undefined") return;
    if (timerRef.current) clearInterval(timerRef.current);
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    timerRef.current = setInterval(() => {
      setIndex((i) => (i + 1) % UNNC_HERO_IMAGES.length);
    }, HERO_SLIDE_MS);
  }, []);

  useEffect(() => {
    armTimer();
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [armTimer]);

  const goTo = useCallback(
    (i: number) => {
      setIndex(i);
      armTimer();
    },
    [armTimer],
  );

  return { index, goTo };
}

function HeroCarouselImages({ index }: { index: number }) {
  return (
    <div className="absolute inset-0" aria-hidden>
      {UNNC_HERO_IMAGES.map((src, i) => (
        <Image
          key={src}
          src={src}
          alt=""
          fill
          sizes="100vw"
          className={`object-cover object-center pointer-events-none transition-opacity duration-[1100ms] ease-in-out ${
            i === index ? "opacity-100 z-[1]" : "opacity-0 z-0"
          }`}
          priority={i === 0}
        />
      ))}
    </div>
  );
}

function HeroCarouselDots({
  index,
  onSelect,
  className,
}: {
  index: number;
  onSelect: (i: number) => void;
  className?: string;
}) {
  return (
    <div
      className={`flex justify-center gap-2 pointer-events-auto ${className ?? ""}`}
      role="tablist"
      aria-label="切换校园主图"
    >
      {UNNC_HERO_IMAGES.map((_, i) => (
        <button
          key={i}
          type="button"
          role="tab"
          aria-selected={i === index}
          aria-label={`第 ${i + 1} 张`}
          onClick={() => onSelect(i)}
          className={`h-1.5 rounded-full transition-all duration-300 ${
            i === index
              ? "w-7 bg-unnc-goldbright shadow-sm"
              : "w-1.5 bg-white/40 hover:bg-white/70"
          }`}
        />
      ))}
    </div>
  );
}

// ─────────────────────────────────────────────
// Hero Section (website style)
// ─────────────────────────────────────────────

function HeroSection({
  savedProfile,
  totalJobs,
  onResumeMatch,
  onClearProfile,
}: {
  savedProfile: StoredProfile | null;
  totalJobs: number;
  onResumeMatch: () => void;
  onClearProfile: () => void;
}) {
  const router = useRouter();
  const { index: heroIndex, goTo: heroGoTo } = useHeroCarousel();

  const features = [
    { icon: <Brain size={24} className="text-unnc-blue" />, title: "AI 对话采集", desc: "自然聊天，AI 自动提取你的画像信息" },
    { icon: <Target size={24} className="text-emerald-600" />, title: "五维度匹配", desc: "技能 · 时间 · 兴趣 · 能力 · 企业文化" },
    { icon: <TrendingUp size={24} className="text-unnc-gold" />, title: "提升建议", desc: "告诉你补什么技能，匹配分能涨多少" },
    { icon: <Zap size={24} className="text-unnc-navy" />, title: "一键投递", desc: "直达实习僧、牛客网岗位原始页面" },
  ];

  return (
    <div className="relative overflow-hidden bg-[#003056]">
      {/* Hero 区：背景图保持原尺寸，固定在顶部 */}
      <div className="relative min-h-[100vh] flex flex-col">
        {/* 背景图层：固定高度，不拉伸 */}
        <div className="absolute inset-x-0 top-0 h-[min(56vh,560px)] z-0">
          <HeroCarouselImages index={heroIndex} />
          <div
            className="absolute inset-0 z-[2] bg-gradient-to-b from-black/50 via-[#003056]/70 to-[#003056] pointer-events-none"
            aria-hidden
          />
        </div>
        {/* 图片下方延伸的纯色，填满剩余高度 */}
        <div
          className="absolute inset-x-0 top-[min(56vh,560px)] bottom-0 z-0 bg-[#003056]"
          aria-hidden
        />

        <div className="relative z-10 flex-1 flex flex-col items-center justify-center text-center container max-w-7xl mx-auto px-4 md:px-8 py-16 md:py-24 pb-20 md:pb-24">
          <p className="text-unnc-goldbright/95 text-xs md:text-sm font-medium tracking-[0.2em] uppercase mb-4 fade-in-up">
            University of Nottingham Ningbo China
          </p>
          <div className="space-y-4 fade-in-up max-w-3xl">
            <h1 className="text-4xl sm:text-5xl md:text-6xl font-bold tracking-tight text-white drop-shadow-sm">
              实习与校园，一站为伴
            </h1>
            <p className="text-white/85 text-lg md:text-xl leading-relaxed max-w-2xl mx-auto">
              专为宁诺同学打造：AI 对话采集画像，五维度从{" "}
              <span className="text-unnc-goldbright font-semibold">{totalJobs > 0 ? `${totalJobs}+` : "海量"}</span>{" "}
              全国岗位中推荐实习；校园动态聚合讲座与活动，支持课表导入与智能活动筛选，信息集中、好安排。
            </p>
          </div>

          <div className="flex flex-col sm:flex-row flex-wrap justify-center gap-4 mt-10 fade-in-up">
            {savedProfile ? (
              <>
                <button
                  type="button"
                  onClick={onResumeMatch}
                  className="unnc-hero-cta px-10 py-4 rounded-xl flex items-center justify-center gap-2 text-base"
                >
                  <Zap size={18} />
                  用上次画像直接匹配
                </button>
                <Link
                  href={MATCH_ENTRY_FRESH}
                  className="bg-white/10 backdrop-blur-sm border border-white/40 text-white hover:bg-white/20 font-semibold px-10 py-4 rounded-xl flex items-center justify-center gap-2 text-base transition"
                >
                  <Sparkles size={18} />
                  重新对话
                </Link>
                <Link
                  href="/campus"
                  className="bg-white/10 backdrop-blur-sm border border-white/40 text-white hover:bg-white/20 font-semibold px-10 py-4 rounded-xl flex items-center justify-center gap-2 text-base transition"
                >
                  <BookOpen size={18} />
                  校园动态
                </Link>
              </>
            ) : (
              <>
                <Link
                  href={MATCH_ENTRY}
                  className="unnc-hero-cta font-bold px-12 py-4 rounded-xl inline-flex items-center justify-center gap-2 text-lg"
                >
                  <Sparkles size={20} />
                  开始实习匹配
                  <ChevronRight size={18} />
                </Link>
                <Link
                  href="/campus"
                  className="bg-white/10 backdrop-blur-sm border border-white/40 text-white hover:bg-white/20 font-semibold px-10 py-4 rounded-xl inline-flex items-center justify-center gap-2 text-base transition"
                >
                  <BookOpen size={18} />
                  校园动态
                </Link>
              </>
            )}
          </div>
        </div>

        {/* 轮播指示器：锚定整屏 hero 底部，避免与居中标题重叠 */}
        <div className="pointer-events-none absolute bottom-5 md:bottom-7 left-0 right-0 z-[20] flex justify-center px-4">
          <div className="pointer-events-auto">
            <HeroCarouselDots index={heroIndex} onSelect={heroGoTo} />
          </div>
        </div>
      </div>

      <section className="relative unnc-mesh-section overflow-hidden">
        <div
          className="pointer-events-none absolute inset-x-0 top-0 h-32 bg-gradient-to-b from-white/80 to-transparent"
          aria-hidden
        />
        <div className="relative container max-w-7xl mx-auto px-4 md:px-8 py-16 md:py-24">
          <div className="flex flex-col items-stretch w-full max-w-5xl mx-auto space-y-12 md:space-y-14">

            {savedProfile && (
              <motion.div
                initial={{ opacity: 0, y: 14 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true, amount: 0.2 }}
                transition={{ duration: 0.45 }}
                className="unnc-feature-card p-5 md:p-6 max-w-lg w-full mx-auto md:mx-0 text-left"
              >
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-2">
                    <CheckCircle2 size={14} className="text-emerald-600" />
                    <span className="text-sm font-semibold text-emerald-800">上次画像</span>
                  </div>
                  <button type="button" onClick={onClearProfile} className="text-xs text-slate-400 hover:text-slate-600 transition">清除</button>
                </div>
                <div className="flex flex-wrap gap-1.5">
                  {savedProfile.major && (
                    <span className="text-xs bg-unnc-sky/80 border border-unnc-blue/15 text-unnc-navy px-2.5 py-1 rounded-full">
                      {savedProfile.major} {savedProfile.grade}
                    </span>
                  )}
                  {(savedProfile.skills || []).slice(0, 4).map((s) => (
                    <span key={s} className="text-xs bg-slate-50 border border-slate-200/80 text-slate-600 px-2.5 py-1 rounded-full">{s}</span>
                  ))}
                  {savedProfile.intern_period && (
                    <span className="text-xs bg-amber-50/90 border border-amber-200/60 text-amber-800 px-2.5 py-1 rounded-full">{savedProfile.intern_period}</span>
                  )}
                </div>
              </motion.div>
            )}

            <div className="text-center md:text-left space-y-2 md:space-y-3 px-1">
              <p className="text-[11px] md:text-xs font-semibold tracking-[0.22em] uppercase text-unnc-goldbright">
                数据概览
              </p>
              <h2 className="text-2xl md:text-3xl font-bold text-slate-900 tracking-tight">
                连接岗位与成长路径
              </h2>
              <p className="text-slate-500 text-sm md:text-[15px] max-w-xl md:max-w-2xl mx-auto md:mx-0 leading-relaxed">
                先呈现规模与能力支点，再展开每一项服务——信息分层更清晰，阅读节奏更自然。
              </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-12 gap-4 md:gap-5 w-full items-stretch">
              <motion.div
                initial={{ opacity: 0, y: 22 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true, amount: 0.25 }}
                transition={{ duration: 0.5 }}
                className="md:col-span-7 relative rounded-3xl border border-slate-200/70 bg-white/90 backdrop-blur-sm pl-7 pr-8 py-8 md:py-10 border-l-[3px] border-l-unnc-gold shadow-[0_4px_28px_-8px_rgba(0,48,86,0.12)]"
              >
                <p className="text-unnc-blue/85 text-[11px] font-semibold tracking-widest uppercase mb-3">岗位池</p>
                <p className="text-4xl sm:text-5xl font-bold tracking-tight tabular-nums leading-none">
                  <span className="stat-number">{totalJobs > 0 ? `${totalJobs}+` : "500+"}</span>
                </p>
                <p className="text-slate-600 mt-4 text-sm md:text-base leading-relaxed max-w-md">
                  全国实习岗位持续聚合，多城市、多赛道，便于宁诺同学一站式浏览与匹配。
                </p>
              </motion.div>
              <div className="md:col-span-5 flex flex-col gap-4 justify-center">
                <motion.div
                  initial={{ opacity: 0, y: 18 }}
                  whileInView={{ opacity: 1, y: 0 }}
                  viewport={{ once: true, amount: 0.2 }}
                  transition={{ duration: 0.45, delay: 0.05 }}
                  className="unnc-stat-compact rounded-2xl md:rounded-3xl px-6 py-5 md:py-6 md:translate-y-1"
                >
                  <p className="text-3xl md:text-4xl font-bold tabular-nums">
                    <span className="stat-number">5</span>
                  </p>
                  <p className="text-slate-500 text-sm mt-2 leading-snug">匹配维度 · 技能、时间、兴趣、能力与文化</p>
                </motion.div>
                <motion.div
                  initial={{ opacity: 0, y: 18 }}
                  whileInView={{ opacity: 1, y: 0 }}
                  viewport={{ once: true, amount: 0.2 }}
                  transition={{ duration: 0.45, delay: 0.1 }}
                  className="unnc-stat-compact rounded-2xl md:rounded-3xl px-6 py-5 md:py-6 md:-translate-y-1"
                >
                  <p className="text-3xl md:text-4xl font-bold tracking-tight">
                    <span className="stat-number">AI+</span>
                  </p>
                  <p className="text-slate-500 text-sm mt-2 leading-snug">对话采集画像与智能建议，减轻你整理投递材料的负担</p>
                </motion.div>
              </div>
            </div>

            <div className="pt-4 md:pt-2 space-y-6 w-full">
              <div className="text-center md:text-left space-y-2 md:space-y-3 px-1">
                <p className="text-[11px] md:text-xs font-semibold tracking-[0.22em] uppercase text-unnc-goldbright">
                  能力矩阵
                </p>
                <h3 className="text-xl md:text-2xl font-bold text-slate-900 tracking-tight">
                  从聊天到投递，一步一环
                </h3>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-5 lg:gap-6 w-full">
                {features.map((f, i) => (
                  <motion.div
                    key={f.title}
                    initial={{ opacity: 0, y: 20 }}
                    whileInView={{ opacity: 1, y: 0 }}
                    viewport={{ once: true, amount: 0.15 }}
                    transition={{ duration: 0.42, delay: i * 0.06 }}
                    className={`unnc-feature-card p-6 md:p-7 text-left ${i % 2 === 1 ? "sm:mt-4 lg:mt-6" : ""}`}
                  >
                    <div className="mb-4 inline-flex h-12 w-12 items-center justify-center rounded-2xl bg-gradient-to-br from-unnc-sky/90 to-white text-unnc-blue shadow-sm ring-1 ring-unnc-blue/10 [&>svg]:h-6 [&>svg]:w-6">
                      {f.icon}
                    </div>
                    <h4 className="font-semibold text-slate-900 text-[15px] md:text-base leading-snug">{f.title}</h4>
                    <p className="text-slate-500 text-[13px] md:text-sm mt-2 leading-relaxed">{f.desc}</p>
                  </motion.div>
                ))}
              </div>
            </div>

            <div className="flex flex-wrap justify-center md:justify-start gap-3 pt-6 mt-2 border-t border-slate-200/60 w-full">
              <button
                type="button"
                onClick={() => router.push("/campus")}
                className="group inline-flex items-center gap-2 rounded-full border border-slate-200/90 bg-white/80 px-4 py-2.5 text-sm text-slate-600 shadow-sm transition hover:border-unnc-blue/25 hover:bg-white hover:text-unnc-blue hover:shadow-md"
              >
                <BookOpen size={15} className="text-slate-400 group-hover:text-unnc-blue transition-colors" />
                校园动态
                <ArrowRight size={14} className="opacity-40 transition-all group-hover:translate-x-0.5 group-hover:opacity-90" />
              </button>
              <button
                type="button"
                onClick={() => router.push("/saved")}
                className="group inline-flex items-center gap-2 rounded-full border border-slate-200/90 bg-white/80 px-4 py-2.5 text-sm text-slate-600 shadow-sm transition hover:border-unnc-blue/25 hover:bg-white hover:text-unnc-blue hover:shadow-md"
              >
                <Heart size={15} className="text-slate-400 group-hover:text-rose-500 transition-colors" />
                已收藏岗位
                <ArrowRight size={14} className="opacity-40 transition-all group-hover:translate-x-0.5 group-hover:opacity-90" />
              </button>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}

// ─────────────────────────────────────────────
// Main Page
// ─────────────────────────────────────────────

const SUGGESTIONS = ["计算机大三", "数学/统计专业", "商科大二", "设计类专业"];

/** 未登录：仅展示平台介绍与登录入口，不发起对话/匹配 */
function GuestPreview() {
  const { index: heroIndex, goTo: heroGoTo } = useHeroCarousel();
  const previewBlocks = [
    {
      icon: <Sparkles size={22} className="text-unnc-blue" />,
      title: "AI 实习匹配",
      desc: "对话采集画像，五维度算法从岗位池中推荐适合你的实习，并生成理由与提升建议。",
    },
    {
      icon: <BookOpen size={22} className="text-emerald-600" />,
      title: "校园动态",
      desc: "讲座、招聘会、校园活动与日历融合，集中浏览宁诺相关资讯。",
    },
    {
      icon: <Heart size={22} className="text-rose-500" />,
      title: "收藏与我的",
      desc: "保存心仪岗位、查看匹配历史与个人中心，数据随账号同步（登录后可用）。",
    },
  ];

  return (
    <div className="relative overflow-hidden bg-[#003056]">
      <div className="relative min-h-[100vh] flex flex-col">
        <div className="absolute inset-x-0 top-0 h-[min(52vh,520px)] z-0">
          <HeroCarouselImages index={heroIndex} />
          <div
            className="absolute inset-0 z-[2] bg-gradient-to-b from-black/50 via-[#003056]/75 to-[#003056] pointer-events-none"
            aria-hidden
          />
        </div>
        <div
          className="absolute inset-x-0 top-[min(52vh,520px)] bottom-0 z-0 bg-[#003056]"
          aria-hidden
        />

        <div className="relative z-10 flex-1 flex flex-col items-center justify-center text-center container max-w-7xl mx-auto px-4 md:px-8 py-16 md:py-20 pb-20 md:pb-24">
          <p className="text-unnc-goldbright/95 text-xs md:text-sm font-medium tracking-[0.2em] uppercase mb-4">
            University of Nottingham Ningbo China
          </p>
          <h1 className="text-3xl sm:text-4xl md:text-5xl font-bold tracking-tight text-white drop-shadow-sm max-w-3xl">
            NottFind · 宁诺实习与校园一站平台
          </h1>
          <p className="text-white/85 text-base md:text-lg leading-relaxed max-w-xl mx-auto mt-5">
            登录后可使用 AI 智能匹配、校园活动聚合与收藏等功能。预览页仅作介绍，不保存你的对话与画像。
          </p>

          <div className="flex flex-col sm:flex-row gap-3 mt-10 w-full max-w-md sm:max-w-none sm:w-auto justify-center">
            <Link
              href="/login?callbackUrl=%2F%3Fmatch%3D1"
              className="unnc-hero-cta font-semibold px-10 py-3.5 rounded-xl inline-flex items-center justify-center gap-2 text-base"
            >
              <LogIn size={18} />
              登录后开始使用
            </Link>
            <Link
              href="/register"
              className="bg-white/10 backdrop-blur-sm border border-white/45 text-white hover:bg-white/20 font-semibold px-10 py-3.5 rounded-xl inline-flex items-center justify-center gap-2 text-base transition"
            >
              <UserPlus size={18} />
              注册账号
            </Link>
          </div>
          <p className="text-white/55 text-xs mt-6 max-w-md">
            注册需使用 <span className="text-unnc-goldbright/90">@nottingham.edu.cn</span> 邮箱
          </p>
        </div>

        <div className="pointer-events-none absolute bottom-5 md:bottom-7 left-0 right-0 z-[20] flex justify-center px-4">
          <div className="pointer-events-auto">
            <HeroCarouselDots index={heroIndex} onSelect={heroGoTo} />
          </div>
        </div>
      </div>

      <section className="relative unnc-mesh-section overflow-hidden">
        <div
          className="pointer-events-none absolute inset-x-0 top-0 h-28 bg-gradient-to-b from-white/80 to-transparent"
          aria-hidden
        />
        <div className="relative container max-w-7xl mx-auto px-4 md:px-8 py-14 md:py-20">
          <div className="text-center max-w-2xl mx-auto mb-10 md:mb-12">
            <p className="text-[11px] font-semibold tracking-[0.22em] uppercase text-unnc-goldbright mb-2">
              功能预览
            </p>
            <h2 className="text-2xl md:text-3xl font-bold text-slate-900 tracking-tight">
              登录后解锁全部能力
            </h2>
            <p className="text-slate-500 text-sm mt-2">
              以下为平台能力说明，实际操作需在登录后进行。
            </p>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-5 lg:gap-6 max-w-5xl mx-auto">
            {previewBlocks.map((b, i) => (
              <motion.div
                key={b.title}
                initial={{ opacity: 0, y: 16 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true, amount: 0.2 }}
                transition={{ duration: 0.4, delay: i * 0.06 }}
                className="relative unnc-feature-card p-6 text-left overflow-hidden"
              >
                <span className="absolute top-3 right-3 inline-flex items-center gap-1 text-[10px] font-semibold uppercase tracking-wide text-slate-400 bg-slate-100/90 px-2 py-0.5 rounded-full border border-slate-200/80">
                  <Lock size={10} />
                  登录后
                </span>
                <div className="mb-3 inline-flex h-11 w-11 items-center justify-center rounded-2xl bg-gradient-to-br from-unnc-sky/90 to-white text-unnc-blue shadow-sm ring-1 ring-unnc-blue/10">
                  {b.icon}
                </div>
                <h3 className="font-semibold text-slate-900 text-[15px] leading-snug pr-16">
                  {b.title}
                </h3>
                <p className="text-slate-500 text-[13px] mt-2 leading-relaxed">{b.desc}</p>
              </motion.div>
            ))}
          </div>
          <div className="flex justify-center mt-12">
            <Link
              href="/login"
              className="inline-flex items-center gap-2 text-sm font-medium text-unnc-blue hover:text-unnc-navy transition"
            >
              已有账号？前往登录
              <ChevronRight size={16} />
            </Link>
          </div>
        </div>
      </section>
    </div>
  );
}

function AuthenticatedHome({ user }: { user: AuthUser }) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const uid = user.id;
  const [view, setView] = useState<"landing" | "chat">("landing");
  const [savedProfile, setSavedProfile] = useState<StoredProfile | null>(null);
  const [totalJobs, setTotalJobs] = useState(0);

  const [messages, setMessages] = useState<Message[]>([]);
  const [sessionId, setSessionId] = useState<string>("");
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [matching, setMatching] = useState(false);
  const [collectedFields, setCollectedFields] = useState<string[]>([]);
  const [profile, setProfile] = useState<Profile | null>(null);
  const [ready, setReady] = useState(false);
  const [awaitingConfirm, setAwaitingConfirm] = useState(false);
  const [pendingMatchProfile, setPendingMatchProfile] = useState<Profile | null>(null);
  const [error, setError] = useState("");
  const [chatInited, setChatInited] = useState(false);
  const [showResumeTip, setShowResumeTip] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const matchInFlightRef = useRef(false);

  useEffect(() => {
    const p = loadProfile(uid);
    setSavedProfile(p);
    axios.get("/api/jobs/count").then((res) => setTotalJobs(res.data.total || 0)).catch(() => {});
  }, [uid]);

  useEffect(() => {
    setChatInited(false);
  }, [uid]);

  useEffect(() => {
    if (searchParams.get("match") === "1") {
      setView("chat");
    } else {
      setView("landing");
    }
  }, [searchParams]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  useEffect(() => {
    if (view === "landing") setChatInited(false);
  }, [view]);

  useEffect(() => {
    if (view !== "chat" || chatInited) return;
    let cancelled = false;

    const run = async () => {
      const fresh = searchParams.get("fresh") === "1";
      try {
        if (fresh) {
          clearChatDraft(uid);
          const res = await axios.get("/api/chat/greeting");
          if (cancelled) return;
          setSessionId(res.data.session_id);
          setMessages([{ role: "assistant", content: res.data.reply }]);
          setCollectedFields([]);
          setProfile(null);
          setReady(false);
          setAwaitingConfirm(false);
          setError("");
          setShowResumeTip(false);
          router.replace(MATCH_ENTRY, { scroll: false });
          setChatInited(true);
          return;
        }

        const draft = loadChatDraft(uid);
        if (draft && draft.messages.length > 0) {
          try {
            const r = await axios.get(`/api/chat/session/${encodeURIComponent(draft.sessionId)}`);
            if (!cancelled && r.data?.ok) {
              const hist = r.data.history as { role: string; content: string }[];
              setSessionId(r.data.session_id);
              setMessages(
                hist.map((m) => ({
                  role: m.role as "user" | "assistant",
                  content: m.content,
                }))
              );
              setProfile(r.data.profile as Profile);
              setReady(!!r.data.ready);
              setAwaitingConfirm(!!r.data.awaiting_confirm);
              setCollectedFields((r.data.collected_fields as string[]) || []);
              setError("");
              setShowResumeTip(true);
              setChatInited(true);
              return;
            }
          } catch {
            /* 会话已过期，尝试 restore */
          }

          try {
            const r2 = await axios.post("/api/chat/restore", { messages: draft.messages });
            if (cancelled) return;
            if (r2.data?.ok) {
              setSessionId(r2.data.session_id);
              setMessages(draft.messages);
              setProfile(r2.data.profile as Profile);
              setReady(!!r2.data.ready);
              setAwaitingConfirm(!!r2.data.awaiting_confirm);
              setCollectedFields((r2.data.collected_fields as string[]) || []);
              setError("");
              setShowResumeTip(true);
              setChatInited(true);
              return;
            }
          } catch {
            clearChatDraft(uid);
          }
        }

        const res = await axios.get("/api/chat/greeting");
        if (cancelled) return;
        setSessionId(res.data.session_id);
        setMessages([{ role: "assistant", content: res.data.reply }]);
        setCollectedFields([]);
        setProfile(null);
        setReady(false);
        setAwaitingConfirm(false);
        setError("");
        setShowResumeTip(false);
        setChatInited(true);
      } catch {
        if (!cancelled) {
          setError("无法连接对话服务，请检查网络或后端");
          setShowResumeTip(false);
        }
        setChatInited(true);
      }
    };

    void run();
    return () => {
      cancelled = true;
    };
  }, [view, chatInited, searchParams, router, uid]);

  useEffect(() => {
    if (view !== "chat" || !sessionId || messages.length === 0) return;
    saveChatDraft(uid, {
      sessionId,
      messages,
      collectedFields,
      profile: profile ? { ...profile } as unknown as Record<string, unknown> : null,
      ready,
      awaitingConfirm,
      updatedAt: new Date().toISOString(),
    });
  }, [view, sessionId, messages, collectedFields, profile, ready, awaitingConfirm, uid]);

  const handleStartMatch = async (profileOverride?: Profile) => {
    const p = profileOverride ?? profile;
    if (!p) return;
    if (matchInFlightRef.current) return;
    matchInFlightRef.current = true;
    setMatching(true);
    setError("");
    try {
      const res = await axios.post("/api/match", {
        schedule_text: p.schedule_text, major: p.major, grade: p.grade || "大二",
        skills: p.skills, interests: p.interests, has_project: p.has_project,
        intern_period: p.intern_period || "", preferences: p.preferences,
      }, { timeout: 120000 });
      saveProfile(uid, p as StoredProfile);
      saveLastMatch(uid, res.data, p);
      setSavedProfile(p as StoredProfile);
      clearChatDraft(uid);
      router.push("/results");
    } catch (err: unknown) {
      console.error("匹配失败详情:", err);
      setError("匹配请求失败，请稍后重试");
      setMatching(false);
    } finally {
      matchInFlightRef.current = false;
    }
  };

  const handleResumeMatch = async () => {
    if (!savedProfile) return;
    router.replace(MATCH_ENTRY);
    setView("chat");
    await handleStartMatch(savedProfile as unknown as Profile);
  };

  const goBackHome = () => {
    setView("landing");
    router.replace("/");
  };

  const handleClearProfile = () => {
    clearProfile(uid);
    clearChatDraft(uid);
    setSavedProfile(null);
  };

  useEffect(() => {
    if (pendingMatchProfile) {
      handleStartMatch(pendingMatchProfile);
      setPendingMatchProfile(null);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pendingMatchProfile]);

  const handleEditMessage = useCallback(
    async (editIndex: number, newContent: string) => {
      const prevMessages = messages.slice(0, editIndex);
      const historyOverride = prevMessages.map((m) => ({ role: m.role, content: m.content }));
      setMessages([...prevMessages, { role: "user", content: newContent }]);
      setCollectedFields([]); setProfile(null); setReady(false); setAwaitingConfirm(false); setError(""); setLoading(true);
      try {
        const res = await axios.post("/api/chat", { session_id: sessionId, message: newContent, history_override: historyOverride });
        const data = res.data;
        setSessionId(data.session_id); setCollectedFields(data.collected_fields); setProfile(data.profile);
        setReady(data.ready); setAwaitingConfirm(data.awaiting_confirm ?? false);
        setMessages((prev) => [...prev, { role: "assistant", content: data.reply }]);
        if (data.action === "start_match") setPendingMatchProfile(data.profile);
      } catch { setError("发送失败，请检查网络或后端服务"); }
      finally { setLoading(false); }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [messages, sessionId]
  );

  const sendMessage = useCallback(
    async (text?: string) => {
      const content = (text ?? input).trim();
      if (!content || loading || matching) return;
      setInput(""); setError("");
      setMessages((prev) => [...prev, { role: "user", content }]);
      setLoading(true);
      try {
        const res = await axios.post("/api/chat", { session_id: sessionId, message: content });
        const data = res.data;
        setSessionId(data.session_id); setCollectedFields(data.collected_fields); setProfile(data.profile);
        setReady(data.ready); setAwaitingConfirm(data.awaiting_confirm ?? false);
        setMessages((prev) => [...prev, { role: "assistant", content: data.reply }]);
        if (data.action === "start_match") { setPendingMatchProfile(data.profile); return; }
      } catch { setError("发送失败，请检查网络或后端服务"); }
      finally { setLoading(false); inputRef.current?.focus(); }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [input, loading, matching, sessionId]
  );

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendMessage(); }
  };

  const requiredDone = ALL_FIELDS.every((f) => isProgressFieldDone(f, collectedFields));

  if (view === "landing") {
    return (
      <HeroSection
        savedProfile={savedProfile}
        totalJobs={totalJobs}
        onResumeMatch={handleResumeMatch}
        onClearProfile={handleClearProfile}
      />
    );
  }

  // ── Chat view (inside website layout) ──
  return (
    <div className="min-h-[80vh] bg-gradient-to-b from-slate-50 to-white">
      <div className="max-w-2xl mx-auto px-4 py-8">
        {/* Header */}
        <div className="text-center mb-5">
          <button type="button" onClick={goBackHome} className="inline-flex items-center gap-2 bg-unnc-sky text-unnc-navy px-4 py-1.5 rounded-full text-sm font-medium mb-3 hover:bg-unnc-sky/80 transition border border-unnc-blue/10">
            <Sparkles size={14} /> NottFind · AI 顾问
          </button>
          <h1 className="text-2xl font-bold text-slate-900">告诉我你的情况</h1>
          <p className="text-slate-500 text-sm mt-1">和 AI 自由对话，我会帮你找到最适合的实习</p>
          {showResumeTip && (
            <p className="text-xs text-emerald-800 bg-emerald-50/90 border border-emerald-100 rounded-lg px-3 py-2 mt-3 max-w-md mx-auto leading-relaxed">
              已为你恢复上次对话记录，可直接继续输入。
            </p>
          )}
        </div>

        {/* Collected fields */}
        <div className="flex flex-wrap gap-2 justify-center mb-4">
          {ALL_FIELDS.map((f) => (
            <CollectedField key={f} label={f} done={isProgressFieldDone(f, collectedFields)} />
          ))}
          <CollectedField label="企业偏好（可选）" done={collectedFields.includes("企业偏好")} />
        </div>

        {/* Chat area */}
        <div className="bg-white/80 backdrop-blur-sm rounded-2xl border border-slate-200 shadow-sm overflow-hidden flex flex-col">
          <div className="flex-1 overflow-y-auto p-4 min-h-[380px] max-h-[480px]">
            {messages.map((msg, i) => (
              <MessageBubble key={i} msg={msg} index={i} onEdit={!loading && !matching ? handleEditMessage : undefined} />
            ))}
            {loading && (
              <div className="flex justify-start mb-3">
                <div className="w-8 h-8 rounded-full bg-unnc-blue flex items-center justify-center mr-2 shrink-0 mt-1">
                  <Sparkles size={14} className="text-white" />
                </div>
                <div className="bg-white rounded-2xl rounded-tl-sm border border-slate-100 shadow-sm">
                  <TypingDots />
                </div>
              </div>
            )}
            <div ref={bottomRef} />
          </div>

          {messages.filter((m) => m.role === "user").length === 0 && (
            <div className="px-4 pb-2">
              <p className="text-xs text-slate-400 mb-1.5">快速选择专业方向：</p>
              <div className="flex flex-wrap gap-2">
                {SUGGESTIONS.map((s) => (
                  <button key={s} onClick={() => sendMessage(s)} className="text-xs bg-unnc-sky text-unnc-blue border border-unnc-blue/20 px-3 py-1.5 rounded-full hover:bg-white transition">
                    {s}
                  </button>
                ))}
              </div>
            </div>
          )}

          {awaitingConfirm && !matching && (
            <div className="px-4 pb-3 flex gap-2">
              <button onClick={() => sendMessage("是，开始匹配！")} className="flex-1 glow-button text-white text-sm font-semibold py-2.5 rounded-xl flex items-center justify-center gap-1.5">
                <Sparkles size={14} /> 是，开始匹配！
              </button>
              <button onClick={() => { setAwaitingConfirm(false); sendMessage("我再补充一下信息"); }} className="flex-1 bg-slate-100 text-slate-600 text-sm font-medium py-2.5 rounded-xl hover:bg-slate-200 transition">
                再补充一下
              </button>
            </div>
          )}

          <div className="border-t border-slate-100 p-3 flex gap-2 items-end bg-white">
            <textarea
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              disabled={loading || matching}
              placeholder="描述你的情况，按 Enter 发送..."
              rows={2}
              className="flex-1 resize-none text-sm text-slate-800 placeholder-slate-400 border border-slate-200 rounded-xl px-3 py-2.5 focus:outline-none focus:ring-2 focus:ring-unnc-blue focus:border-transparent disabled:bg-slate-50 disabled:text-slate-400"
            />
            <button
              onClick={() => sendMessage()}
              disabled={!input.trim() || loading || matching}
              className="w-10 h-10 bg-unnc-blue hover:bg-unnc-navy disabled:opacity-40 disabled:cursor-not-allowed text-white rounded-xl flex items-center justify-center transition shrink-0"
            >
              <Send size={16} />
            </button>
          </div>
        </div>

        {error && (
          <div className="mt-3 p-3 bg-red-50 border border-red-100 rounded-xl text-sm text-red-600">{error}</div>
        )}

        <div className="mt-4">
          {matching ? (
            <div className="w-full rounded-2xl border border-indigo-200 bg-indigo-50/90 px-4 py-4 text-center">
              <div className="flex items-center justify-center gap-2 text-indigo-900 font-semibold text-base">
                <Loader2 size={18} className="animate-spin shrink-0" />
                匹配中，请稍候…
              </div>
              <p className="text-xs text-indigo-800/80 mt-2 leading-relaxed">
                正在扫描岗位并生成解读，通常需 <span className="font-medium">30–90 秒</span>
                （与岗位量、模型响应有关）。此期间页面会停在这里，属正常现象，请勿关闭标签页。
              </p>
            </div>
          ) : !awaitingConfirm && (ready || requiredDone) ? (
            <button onClick={() => handleStartMatch()} className="w-full glow-button text-white font-semibold py-4 rounded-2xl flex items-center justify-center gap-2 text-base">
              <Sparkles size={18} /> 开始智能匹配 <ChevronRight size={18} />
            </button>
          ) : !awaitingConfirm ? (
            <div className="w-full bg-gray-100 text-gray-400 font-medium py-4 rounded-2xl text-center text-sm">
              还差{" "}
              <span className="text-unnc-blue font-semibold">
                {ALL_FIELDS.filter((f) => !isProgressFieldDone(f, collectedFields)).join("、")}
              </span>{" "}
              信息，继续对话补全
            </div>
          ) : null}
        </div>

        <p className="text-center text-xs text-gray-400 mt-3">信息仅用于本次实习匹配，不会被存储或上传</p>
      </div>
    </div>
  );
}

function HomePageContent() {
  const { user, loading: authLoading } = useAuth();

  if (authLoading) {
    return (
      <div className="min-h-[50vh] bg-[#003056]/5 flex flex-col items-center justify-center gap-3">
        <Loader2 className="w-8 h-8 text-unnc-blue animate-spin" />
        <p className="text-slate-500 text-sm">加载会话…</p>
      </div>
    );
  }

  if (!user) {
    return <GuestPreview />;
  }

  return <AuthenticatedHome user={user} />;
}

export default function HomePage() {
  return (
    <Suspense fallback={<div className="min-h-[40vh] bg-[#f7f9fc]" aria-hidden />}>
      <HomePageContent />
    </Suspense>
  );
}
