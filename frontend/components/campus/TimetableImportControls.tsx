"use client";

import { useState } from "react";
import axios from "axios";
import { BookOpen, Loader2, RefreshCw, Trash2, X } from "lucide-react";
import type { MergedCalendarEvent } from "@/components/campus/CampusActivityCalendar";
import { normalizeImportedEvent } from "@/lib/timetableStorage";

type Mode = "url" | "paste";

export function TimetableImportControls({
  timetableCount,
  savedUrl,
  onImported,
  onClear,
  onResynced,
}: {
  timetableCount: number;
  savedUrl: string;
  onImported: (events: MergedCalendarEvent[], url?: string) => void;
  onClear: () => void;
  onResynced?: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [mode, setMode] = useState<Mode>("url");
  const [url, setUrl] = useState("");
  const [paste, setPaste] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [barError, setBarError] = useState("");

  const runImport = async (
    body: { ics_url?: string; ics_text?: string },
    opts?: { silentUi?: boolean },
  ) => {
    setLoading(true);
    setError("");
    setBarError("");
    try {
      const res = await axios.post("/api/calendar/import/ical", body);
      const data = res.data as {
        status?: string;
        message?: string;
        events?: unknown[];
      };
      if (data.status !== "accepted" || !Array.isArray(data.events)) {
        const msg = data.message || "导入失败";
        if (opts?.silentUi) setBarError(msg);
        else setError(msg);
        return;
      }
      const events = data.events
        .map((e) => normalizeImportedEvent(e))
        .filter((x): x is MergedCalendarEvent => x !== null);
      if (events.length === 0) {
        const msg = data.message || "未解析到任何课程事件";
        if (opts?.silentUi) setBarError(msg);
        else setError(msg);
        return;
      }
      const urlToSave = body.ics_url?.trim();
      onImported(events, urlToSave);
      if (!opts?.silentUi) {
        setOpen(false);
        setUrl("");
        setPaste("");
      }
      onResynced?.();
    } catch (e: unknown) {
      let msg = "请求失败";
      if (axios.isAxiosError(e)) {
        msg =
          (e.response?.data as { message?: string })?.message ||
          e.message ||
          msg;
      }
      if (opts?.silentUi) setBarError(msg);
      else setError(msg);
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = () => {
    if (mode === "url") {
      const u = url.trim();
      if (!u) {
        setError("请粘贴 Scientia 复制的订阅链接（webcal:// 或 https://）");
        return;
      }
      void runImport({ ics_url: u });
    } else {
      const t = paste.trim();
      if (!t) {
        setError("请粘贴 .ics 文件全文");
        return;
      }
      void runImport({ ics_text: t });
    }
  };

  const handleResync = () => {
    const u = savedUrl.trim();
    if (!u) {
      setBarError("没有已保存的链接，请先通过「导入」保存一次订阅地址");
      return;
    }
    void runImport({ ics_url: u }, { silentUi: true });
  };

  return (
    <>
      <div className="flex flex-wrap items-center gap-2 mb-4">
        <button
          type="button"
          onClick={() => {
            setOpen(true);
            setError("");
            setBarError("");
            setMode("url");
          }}
          className="inline-flex items-center gap-2 px-4 py-2 rounded-full text-sm font-medium bg-orange-100/90 text-orange-900 border border-orange-200/80 hover:bg-orange-100 transition-colors"
        >
          <BookOpen size={16} />
          导入 Scientia 课表
        </button>
        {timetableCount > 0 && (
          <>
            <button
              type="button"
              onClick={() => void handleResync()}
              disabled={loading}
              className="inline-flex items-center gap-1.5 px-3 py-2 rounded-full text-xs font-medium text-slate-600 bg-white/60 backdrop-blur-md border border-stone-200/60 hover:border-orange-200 disabled:opacity-50"
            >
              <RefreshCw size={14} className={loading ? "animate-spin" : ""} />
              从已保存链接更新
            </button>
            <button
              type="button"
              onClick={onClear}
              className="inline-flex items-center gap-1.5 px-3 py-2 rounded-full text-xs font-medium text-slate-500 hover:text-red-600 hover:bg-red-50/80 border border-transparent hover:border-red-100"
            >
              <Trash2 size={14} />
              清除课表
            </button>
            <span className="text-xs text-slate-500">
              已合并 <strong className="text-orange-700">{timetableCount}</strong>{" "}
              节课表时段
            </span>
          </>
        )}
        {barError ? (
          <p className="w-full text-xs text-red-600 bg-red-50/80 rounded-lg px-3 py-2 border border-red-100">
            {barError}
          </p>
        ) : null}
      </div>

      {open && (
        <div
          className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-slate-900/40 backdrop-blur-sm"
          role="dialog"
          aria-modal="true"
          aria-labelledby="timetable-import-title"
        >
          <div className="w-full max-w-lg rounded-[1.5rem] bg-white shadow-xl border border-stone-200/80 overflow-hidden">
            <div className="flex items-center justify-between px-5 py-4 border-b border-stone-100">
              <h2
                id="timetable-import-title"
                className="text-base font-semibold text-slate-900"
              >
                导入个人课表
              </h2>
              <button
                type="button"
                onClick={() => setOpen(false)}
                className="p-2 rounded-full text-slate-400 hover:bg-stone-100 hover:text-slate-700"
                aria-label="关闭"
              >
                <X size={18} />
              </button>
            </div>
            <div className="px-5 pt-3 flex gap-2">
              <button
                type="button"
                onClick={() => {
                  setMode("url");
                  setError("");
                }}
                className={`px-3 py-1.5 rounded-full text-xs font-medium transition-colors ${
                  mode === "url"
                    ? "bg-slate-900 text-white"
                    : "bg-stone-100 text-slate-600"
                }`}
              >
                Scientia 链接
              </button>
              <button
                type="button"
                onClick={() => {
                  setMode("paste");
                  setError("");
                }}
                className={`px-3 py-1.5 rounded-full text-xs font-medium transition-colors ${
                  mode === "paste"
                    ? "bg-slate-900 text-white"
                    : "bg-stone-100 text-slate-600"
                }`}
              >
                粘贴 .ics 全文
              </button>
            </div>
            <div className="px-5 py-4 space-y-3">
              <p className="text-xs text-slate-500 leading-relaxed">
                {mode === "url"
                  ? "在 Scientia 学生端复制「个人日历」订阅地址（webcal:// 或 https://），粘贴到下方。链接仅在后端向 *.scientia.com.cn 请求，不会写入服务器数据库，只保存在本浏览器。"
                  : "若已下载 .ics 文件，可用记事本打开，将全文粘贴到下方。适用于本地文件导入。"}
              </p>
              {mode === "url" ? (
                <textarea
                  value={url}
                  onChange={(e) => setUrl(e.target.value)}
                  placeholder="webcal://unnc-ss-api.scientia.com.cn/api/Activity/Personal/.../ics"
                  rows={3}
                  className="w-full rounded-xl border border-stone-200 px-3 py-2 text-sm text-slate-800 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-orange-200"
                />
              ) : (
                <textarea
                  value={paste}
                  onChange={(e) => setPaste(e.target.value)}
                  placeholder="BEGIN:VCALENDAR..."
                  rows={8}
                  className="w-full rounded-xl border border-stone-200 px-3 py-2 text-sm font-mono text-slate-800 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-orange-200"
                />
              )}
              {error && (
                <p className="text-xs text-red-600 bg-red-50/80 rounded-lg px-3 py-2">
                  {error}
                </p>
              )}
            </div>
            <div className="px-5 py-4 bg-stone-50/80 flex justify-end gap-2 border-t border-stone-100">
              <button
                type="button"
                onClick={() => setOpen(false)}
                className="px-4 py-2 rounded-full text-sm text-slate-600 hover:bg-stone-200/60"
              >
                取消
              </button>
              <button
                type="button"
                disabled={loading}
                onClick={() => void handleSubmit()}
                className="inline-flex items-center gap-2 px-4 py-2 rounded-full text-sm font-medium bg-orange-600 text-white hover:bg-orange-700 disabled:opacity-50"
              >
                {loading ? (
                  <Loader2 size={16} className="animate-spin" />
                ) : null}
                解析并合并到月历
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
