"use client";

import { useState } from "react";
import {
  ChevronDown,
  ChevronUp,
  ExternalLink,
  MessageCircle,
  User,
} from "lucide-react";

export interface WechatArticle {
  title: string;
  date: string;
  summary: string;
  account: string;
  sogou_link: string;
  img_url: string;
  content: string;
  wechat_url: string;
  search_query?: string;
}

const CARD_COLORS = [
  "from-emerald-100/55 to-teal-50/45 border-emerald-200/40",
  "from-sky-100/55 to-blue-50/45 border-sky-200/40",
  "from-amber-100/55 to-yellow-50/45 border-amber-200/40",
  "from-fuchsia-100/55 to-pink-50/45 border-fuchsia-200/40",
  "from-lime-100/55 to-green-50/45 border-lime-200/40",
  "from-indigo-100/55 to-violet-50/45 border-indigo-200/40",
] as const;

function resolveArticleUrl(article: WechatArticle): string {
  if (article.sogou_link && article.sogou_link.includes("weixin.sogou.com")) {
    return `/api/articles/open-sogou?url=${encodeURIComponent(article.sogou_link)}`;
  }
  if (article.wechat_url && article.wechat_url.includes("mp.weixin.qq.com")) {
    return article.wechat_url;
  }
  return article.sogou_link || "#";
}

function resolveImgUrl(raw: string): string {
  if (!raw) return "";
  if (raw.startsWith("//")) return `https:${raw}`;
  return raw;
}

export function WechatArticleCard({
  article,
  index,
}: {
  article: WechatArticle;
  index: number;
}) {
  const [expanded, setExpanded] = useState(false);
  const hasContent =
    !!article.content &&
    article.content.length > 30 &&
    article.content !== article.summary;
  const shell = CARD_COLORS[index % CARD_COLORS.length];
  const url = resolveArticleUrl(article);
  const imgSrc = resolveImgUrl(article.img_url);

  return (
    <article
      className={`rounded-[1.75rem] bg-gradient-to-br ${shell} backdrop-blur-md border shadow-sm hover:shadow-md transition-shadow overflow-hidden flex flex-col`}
    >
      {imgSrc && (
        <div className="relative h-36 overflow-hidden">
          <img
            src={imgSrc}
            alt=""
            className="w-full h-full object-cover"
            loading="lazy"
            referrerPolicy="no-referrer"
          />
          <div className="absolute inset-0 bg-gradient-to-t from-black/30 to-transparent" />
        </div>
      )}

      <div className="p-5 flex flex-col flex-1 min-h-0">
        <div className="flex items-start justify-between gap-2 mb-3">
          <span className="inline-flex items-center gap-1.5 text-[11px] font-medium px-2.5 py-1 rounded-full bg-emerald-100 text-emerald-800">
            <MessageCircle size={11} />
            公众号
          </span>
          {article.date && (
            <span className="text-[11px] text-slate-500 shrink-0">
              {article.date}
            </span>
          )}
        </div>

        <h3 className="text-base font-semibold text-slate-900 leading-snug line-clamp-3 min-h-[3rem]">
          {article.title}
        </h3>

        {article.summary && (
          <p className="text-xs text-slate-600 mt-2 line-clamp-2 leading-relaxed">
            {article.summary}
          </p>
        )}

        <div className="flex items-center gap-2 mt-2 text-xs text-slate-500">
          <User size={11} className="opacity-50 shrink-0" />
          <span className="truncate">{article.account || "未知公众号"}</span>
        </div>

        <div className="flex flex-wrap items-center gap-2 mt-4 pt-3 border-t border-white/50">
          {hasContent && (
            <button
              type="button"
              onClick={() => setExpanded((v) => !v)}
              className="text-xs text-slate-500 hover:text-violet-700 flex items-center gap-1"
            >
              {expanded ? (
                <>
                  收起 <ChevronUp size={12} />
                </>
              ) : (
                <>
                  预览正文 <ChevronDown size={12} />
                </>
              )}
            </button>
          )}
          <a
            href={url}
            target="_blank"
            rel="noopener noreferrer"
            className="ml-auto inline-flex items-center gap-1 text-xs font-medium text-slate-800 bg-white/90 hover:bg-white px-3 py-1.5 rounded-full border border-slate-200/80 shadow-sm"
          >
            阅读原文
            <ExternalLink size={11} />
          </a>
        </div>
      </div>

      {expanded && hasContent && (
        <div className="px-5 pb-5 -mt-1">
          <div className="rounded-2xl bg-white/80 border border-white/90 px-4 py-3 text-sm text-slate-700 leading-relaxed whitespace-pre-line max-h-64 overflow-y-auto">
            {article.content}
          </div>
        </div>
      )}
    </article>
  );
}
