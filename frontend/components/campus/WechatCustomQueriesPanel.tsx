"use client";

import { useCallback, useEffect, useState } from "react";
import axios from "axios";
import { Loader2, Plus, Search, Trash2 } from "lucide-react";

export type WechatQueryRow = {
  query: string;
  label: string;
  max_pages: number;
};

type SearchQueriesResponse = {
  builtin: WechatQueryRow[];
  custom: WechatQueryRow[];
  effective_query_count: number;
};

export function WechatCustomQueriesPanel({
  onAfterChange,
}: {
  /** 配置变更后回调（例如重新拉文章列表） */
  onAfterChange?: () => void;
}) {
  const [builtin, setBuiltin] = useState<WechatQueryRow[]>([]);
  const [custom, setCustom] = useState<WechatQueryRow[]>([]);
  const [effectiveCount, setEffectiveCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [q, setQ] = useState("");
  const [label, setLabel] = useState("");
  const [maxPages, setMaxPages] = useState(3);
  const [submitting, setSubmitting] = useState(false);
  const [hint, setHint] = useState("");

  const load = useCallback(() => {
    setLoading(true);
    axios
      .get<SearchQueriesResponse>("/api/articles/search-queries")
      .then((res) => {
        setBuiltin(res.data.builtin || []);
        setCustom(res.data.custom || []);
        setEffectiveCount(res.data.effective_query_count ?? 0);
      })
      .catch(() => {
        setHint("无法加载关键词配置，请确认后端已启动");
      })
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const submit = (refreshArticlesNow: boolean) => {
    const query = q.trim();
    if (!query) {
      setHint("请先输入搜索关键词");
      return;
    }
    setSubmitting(true);
    setHint("");
    axios
      .post<{ message: string; custom: WechatQueryRow[] }>(
        "/api/articles/custom-query",
        {
          query,
          label: label.trim(),
          max_pages: maxPages,
          refresh_articles_now: refreshArticlesNow,
        },
      )
      .then((res) => {
        setHint(res.data.message);
        setCustom(res.data.custom || []);
        setQ("");
        setLabel("");
        load();
        onAfterChange?.();
      })
      .catch((err: unknown) => {
        const detail = axios.isAxiosError(err)
          ? err.response?.data?.detail
          : undefined;
        setHint(
          typeof detail === "string"
            ? detail
            : "添加失败，请检查关键词长度或网络",
        );
      })
      .finally(() => setSubmitting(false));
  };

  const removeRow = (queryStr: string) => {
    axios
      .delete<{ custom: WechatQueryRow[] }>("/api/articles/custom-query", {
        params: { query: queryStr },
      })
      .then((res) => {
        setCustom(res.data.custom || []);
        setHint("已删除该关键词");
        load();
        onAfterChange?.();
      })
      .catch(() => setHint("删除失败"));
  };

  return (
    <div className="rounded-2xl bg-violet-50/40 backdrop-blur-md border border-violet-200/50 p-4 sm:p-5 mb-6">
      <div className="flex flex-wrap items-center gap-2 mb-3">
        <Search size={18} className="text-violet-600 shrink-0" />
        <h2 className="text-sm sm:text-base font-semibold text-slate-800">
          自定义搜狗关键词
        </h2>
        <span className="text-[11px] sm:text-xs text-slate-500">
          合并后当前共 {effectiveCount} 个爬取关键词
          {loading ? " …" : ""}
        </span>
      </div>
      <p className="text-xs text-slate-500 mb-4 leading-relaxed">
        在搜狗微信里怎么搜，这里就怎么填（公众号名、学校名、活动主题等）。与内置关键词合并去重；若与内置完全相同则以内置为准，不会重复爬取。保存后需点页面右上角「刷新」拉取文章，或选「保存并后台爬取」。
      </p>

      <div className="flex flex-col sm:flex-row flex-wrap gap-2 sm:items-end mb-4">
        <label className="flex-1 min-w-[140px]">
          <span className="text-[11px] text-slate-500 block mb-1">关键词</span>
          <input
            type="text"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="例如：某社团公众号名"
            className="w-full rounded-xl border border-stone-200/80 bg-white/90 px-3 py-2 text-sm"
            maxLength={80}
          />
        </label>
        <label className="flex-1 min-w-[120px]">
          <span className="text-[11px] text-slate-500 block mb-1">
            展示标签（可选）
          </span>
          <input
            type="text"
            value={label}
            onChange={(e) => setLabel(e.target.value)}
            placeholder="默认同关键词"
            className="w-full rounded-xl border border-stone-200/80 bg-white/90 px-3 py-2 text-sm"
            maxLength={64}
          />
        </label>
        <label className="w-full sm:w-24">
          <span className="text-[11px] text-slate-500 block mb-1">翻页数</span>
          <input
            type="number"
            min={1}
            max={10}
            value={maxPages}
            onChange={(e) =>
              setMaxPages(
                Math.min(10, Math.max(1, Number(e.target.value) || 3)),
              )
            }
            className="w-full rounded-xl border border-stone-200/80 bg-white/90 px-3 py-2 text-sm"
          />
        </label>
        <div className="flex flex-wrap gap-2 w-full sm:w-auto">
          <button
            type="button"
            disabled={submitting}
            onClick={() => submit(false)}
            className="inline-flex items-center justify-center gap-1.5 rounded-xl bg-slate-800 text-white px-4 py-2 text-sm font-medium hover:bg-slate-900 disabled:opacity-50"
          >
            {submitting ? (
              <Loader2 size={16} className="animate-spin" />
            ) : (
              <Plus size={16} />
            )}
            保存
          </button>
          <button
            type="button"
            disabled={submitting}
            onClick={() => submit(true)}
            className="inline-flex items-center justify-center gap-1.5 rounded-xl bg-violet-600 text-white px-4 py-2 text-sm font-medium hover:bg-violet-700 disabled:opacity-50"
          >
            保存并后台爬取
          </button>
        </div>
      </div>

      {hint ? (
        <p className="text-xs text-violet-800 bg-violet-100/50 border border-violet-200/60 rounded-lg px-3 py-2 mb-3">
          {hint}
        </p>
      ) : null}

      <div className="grid gap-4 sm:grid-cols-2 text-xs">
        <div>
          <p className="font-medium text-slate-600 mb-2">内置（代码配置）</p>
          <ul className="space-y-1 text-slate-500 max-h-32 overflow-y-auto">
            {builtin.map((row) => (
              <li key={row.query}>
                <span className="text-slate-700">{row.label || row.query}</span>
                <span className="text-slate-400 ml-1">
                  · {row.query} · {row.max_pages} 页
                </span>
              </li>
            ))}
          </ul>
        </div>
        <div>
          <p className="font-medium text-slate-600 mb-2">你添加的</p>
          {custom.length === 0 ? (
            <p className="text-slate-400">暂无，可在上方添加</p>
          ) : (
            <ul className="space-y-1.5 max-h-40 overflow-y-auto">
              {custom.map((row) => (
                <li
                  key={row.query}
                  className="flex items-center justify-between gap-2 rounded-lg bg-white/70 border border-stone-200/60 px-2 py-1.5"
                >
                  <span className="text-slate-700 truncate">
                    {row.label || row.query}{" "}
                    <span className="text-slate-400 font-normal">
                      ({row.max_pages}页)
                    </span>
                  </span>
                  <button
                    type="button"
                    title="删除"
                    onClick={() => removeRow(row.query)}
                    className="shrink-0 p-1.5 rounded-lg text-slate-400 hover:text-red-600 hover:bg-red-50"
                  >
                    <Trash2 size={14} />
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
}
