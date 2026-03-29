"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  ArrowLeft, Heart, MapPin, ExternalLink, Trash2, Briefcase,
} from "lucide-react";
import { getSavedJobs, removeSavedJob, type SavedJob } from "@/lib/storage";
import { MATCH_ENTRY } from "@/lib/routes";
import { useAuth } from "@/hooks/useAuth";

export default function SavedJobsPage() {
  const router = useRouter();
  const { user, loading: authLoading } = useAuth();
  const [jobs, setJobs] = useState<SavedJob[]>([]);

  useEffect(() => {
    if (!user) return;
    setJobs(getSavedJobs(user.id));
  }, [user]);

  const handleRemove = (id: string) => {
    if (!user) return;
    removeSavedJob(user.id, id);
    setJobs(getSavedJobs(user.id));
  };

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
    <div className="min-h-screen py-8 px-4">
      <div className="max-w-2xl mx-auto">
        <button
          type="button"
          onClick={() => router.push("/")}
          className="flex items-center gap-2 text-sm text-slate-500 hover:text-indigo-600 transition mb-6"
        >
          <ArrowLeft size={16} />
          返回首页
        </button>

        <div className="flex items-center gap-2 mb-2">
          <Heart size={22} className="text-rose-500 fill-rose-500" />
          <h1 className="text-xl font-bold text-slate-900">已收藏的岗位</h1>
        </div>
        <p className="text-sm text-slate-500 mb-6">
          共 {jobs.length} 条 · 与账号 {user.username} 绑定，保存在本机浏览器
        </p>

        {jobs.length === 0 ? (
          <div className="card p-12 text-center text-slate-400">
            <Briefcase size={40} className="mx-auto mb-3 opacity-30" />
            <p>还没有收藏，去首页匹配后可以点星标收藏</p>
            <button
              type="button"
              onClick={() => router.push(MATCH_ENTRY)}
              className="mt-4 text-sm text-indigo-600 font-medium hover:underline"
            >
              开始匹配
            </button>
          </div>
        ) : (
          <ul className="space-y-3">
            {jobs.map((j) => (
              <li
                key={j.id}
                className="card p-4 flex gap-3 items-start"
              >
                <div className="flex-1 min-w-0">
                  <h2 className="font-semibold text-slate-900 text-sm leading-tight">
                    {j.title}
                  </h2>
                  <p className="text-xs text-slate-500 mt-0.5">{j.company}</p>
                  <div className="flex flex-wrap gap-x-3 gap-y-1 mt-2 text-xs text-slate-500">
                    <span className="flex items-center gap-1">
                      <MapPin size={11} /> {j.location}
                    </span>
                    <span className="text-emerald-600 font-medium">{j.salary}</span>
                    {j.is_remote && (
                      <span className="text-indigo-600">可远程</span>
                    )}
                  </div>
                  <div className="flex flex-wrap gap-1 mt-2">
                    {j.tags.slice(0, 4).map((t) => (
                      <span
                        key={t}
                        className="text-[10px] bg-slate-50 border border-slate-200 text-slate-600 px-2 py-0.5 rounded-full"
                      >
                        {t}
                      </span>
                    ))}
                  </div>
                </div>
                <div className="flex flex-col gap-2 shrink-0">
                  {j.source_url ? (
                    <a
                      href={j.source_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center justify-center gap-1 text-xs bg-indigo-600 text-white px-3 py-2 rounded-lg hover:bg-indigo-700 transition"
                    >
                      投递 <ExternalLink size={12} />
                    </a>
                  ) : null}
                  <button
                    type="button"
                    onClick={() => handleRemove(j.id)}
                    className="inline-flex items-center justify-center gap-1 text-xs text-slate-500 hover:text-red-600 border border-slate-200 px-3 py-2 rounded-lg hover:border-red-200 transition"
                    title="取消收藏"
                  >
                    <Trash2 size={12} />
                    移除
                  </button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
