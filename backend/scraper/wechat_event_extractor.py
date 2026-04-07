"""
从微信公众号文章正文中用正则抽取结构化活动信息，写入 wechat_events.json。
供合并日历与学生资讯「公众号活动」筛选使用。

不依赖 AI，纯规则抽取：速度快、日期准确、无幻觉。
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

ARTICLES_FILE = Path(__file__).parent.parent / "data" / "wechat_articles.json"
EVENTS_CACHE = Path(__file__).parent.parent / "data" / "wechat_events.json"

# ---------------------------------------------------------------------------
# 日期正则（优先级从高到低）
# ---------------------------------------------------------------------------

# 1. 中文全日期，可选跨天：2023年11月4日  /  2023年4月8日-12日
_PAT_CN_FULL = re.compile(
    r"(20\d{2})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*[日号]"
    r"(?:\s*[至到~\-—–]\s*(\d{1,2})\s*[日号])?",
    re.UNICODE,
)

# 2. ISO / 斜线格式：2023-11-04  /  2023/11/04
_PAT_ISO = re.compile(r"(?<!\d)(20\d{2})[-/](\d{1,2})[-/](\d{1,2})(?!\d)")

# 3a. 明确标注的点格式日期（高可信）：Event Time: 4.24 / Time：10.22
#     需要在前 30 字内出现 time/date/举办时间 等强信号词
_PAT_DOT_LABELED = re.compile(r"(?<!\d)([1-9]|1[0-2])\.([1-9]|[12]\d|3[01])(?!\d)")
_DOT_STRONG_LABELS = re.compile(
    r"(?:event\s*time|time\s*[：:]\s*|举办时间|活动时间|activity\s*time)",
    re.IGNORECASE,
)

# 3b. 中文月日（无年份）：4月24日  /  10月22号
#     前面不能直接跟年份数字（避免把「2023年」里的3识别成月份）
_PAT_CN_MD = re.compile(r"(?<!\d)(\d{1,2})\s*月\s*(\d{1,2})\s*[日号]")

# 4. 英文月名：April 24  /  Nov 29  /  Apr 8-12
_MONTH_MAP = {
    "january": 1, "february": 2, "march": 3, "april": 4,
    "may": 5, "june": 6, "july": 7, "august": 8,
    "september": 9, "october": 10, "november": 11, "december": 12,
    "jan": 1, "feb": 2, "mar": 3, "apr": 4,
    "jun": 6, "jul": 7, "aug": 8,
    "sep": 9, "sept": 9, "oct": 10, "nov": 11, "dec": 12,
}
_EN_MONTH_PAT = "|".join(_MONTH_MAP.keys())
_PAT_EN_MONTH = re.compile(
    rf"\b({_EN_MONTH_PAT})\b[\s.]*(\d{{1,2}})(?:\s*[-–]\s*(\d{{1,2}}))?",
    re.IGNORECASE,
)

# 5. M.DD 点格式（普通，仅前后有宽泛活动关键词时采信）
_PAT_DOT = re.compile(r"(?<!\d)([1-9]|1[0-2])\.([1-9]|[12]\d|3[01])(?!\d)")
_DOT_KEYWORDS = frozenset([
    "time", "date", "event", "activity", "venue", "location",
    "时间", "活动", "地点", "日期", "举办", "报名",
])

# ---------------------------------------------------------------------------
# 时间正则
# ---------------------------------------------------------------------------

# 活动时间段标记（出现后优先读其后的时间）
_PAT_ACTIVITY_TIME_LABEL = re.compile(
    r"(?:活动时间|activity\s*time|举办时间|时间[：:]\s*$)",
    re.IGNORECASE,
)
# 报名/投票时间标记（出现后跳过其后的时间）
_PAT_SKIP_TIME_LABEL = re.compile(
    r"(?:报名时间|registration\s*time|voting\s*time|评选时间|截止时间|deadline)",
    re.IGNORECASE,
)
# HH:MM 时间
_PAT_TIME = re.compile(r"(\d{1,2})[:\：点](\d{2})(?!\d)")

# ---------------------------------------------------------------------------
# 活动判定关键词
# 标题或正文前 300 字含这些词则视为「可能是活动推文」
# ---------------------------------------------------------------------------
_EVENT_TITLE_KEYWORDS = frozenset([
    "activity", "lecture", "workshop", "recruitment", "招新", "讲座",
    "活动", "工作坊", "比赛", "拾味", "正念", "t台", "open day", "开放日",
    "招生", "宣讲", "招募", "面试", "比赛", "展", "论坛", "峰会",
    "orientation", "seminar", "fair", "招聘会",
])
_NON_EVENT_TITLE_KEYWORDS = frozenset([
    "回顾", "review", "总结", "报告", "通讯", "newsletter", "招生简章",
    "名单公布", "介绍", "introduction", "在职硕士", "博士招生", "毕业生",
    "校友", "科普", "了解", "知识", "指南",
])


# ---------------------------------------------------------------------------
# 核心函数
# ---------------------------------------------------------------------------

def _pub_year(article: dict[str, Any]) -> int | None:
    pub = (article.get("publish_date") or "").strip()
    if len(pub) >= 4 and pub[:4].isdigit():
        y = int(pub[:4])
        if 2010 <= y <= 2100:
            return y
    return None


def _extract_date(text: str, ref_year: int | None) -> tuple[str, str, str]:
    """
    返回 (date_start, date_end, pattern_name)。
    date_start/date_end 均为 'YYYY-MM-DD' 或 ''。

    优先级：
      1. 中文全日期（带年份）
      2. ISO 日期（带年份）
      3. 明确标注的点格式（Event Time: 4.24 等强标记）← 比无标注中文月日优先
      4. 中文月日（用 ref_year 补全）
      5. 英文月名（用 ref_year 补全）
      6. 普通点格式（宽泛关键词）
    """
    if not text:
        return "", "", "无内容"

    # 1. 中文全日期（最可靠）
    m = _PAT_CN_FULL.search(text)
    if m:
        y = int(m.group(1))
        mo = int(m.group(2))
        d1 = int(m.group(3))
        d2 = int(m.group(4)) if m.group(4) else d1
        if 1 <= mo <= 12 and 1 <= d1 <= 31 and 1 <= d2 <= 31:
            return (
                f"{y:04d}-{mo:02d}-{d1:02d}",
                f"{y:04d}-{mo:02d}-{d2:02d}",
                "中文全日期",
            )

    # 2. ISO 日期
    m = _PAT_ISO.search(text)
    if m:
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if 1 <= mo <= 12 and 1 <= d <= 31:
            return f"{y:04d}-{mo:02d}-{d:02d}", f"{y:04d}-{mo:02d}-{d:02d}", "ISO日期"

    # 3. 明确标注的点格式（Event Time: / Time： 紧跟 M.DD）
    #    在前 800 字内扫描，找到强标签后的第一个 M.DD
    if ref_year:
        search_zone = text[:800]
        label_m = _DOT_STRONG_LABELS.search(search_zone)
        if label_m:
            after_label = search_zone[label_m.end():]
            dot_m = _PAT_DOT_LABELED.search(after_label[:120])  # 标签后 120 字内（覆盖换行）
            if dot_m:
                mo, d = int(dot_m.group(1)), int(dot_m.group(2))
                if 1 <= mo <= 12 and 1 <= d <= 31:
                    return (
                        f"{ref_year:04d}-{mo:02d}-{d:02d}",
                        f"{ref_year:04d}-{mo:02d}-{d:02d}",
                        f"标注点格式(发布年{ref_year}补全)",
                    )

    # 4. 中文月日（无年份，用 ref_year 补全）
    if ref_year:
        m = _PAT_CN_MD.search(text)
        if m:
            # 确保前面没有紧跟年份数字（避免把「2023年」中的「3年11月」误匹配）
            pre = text[max(0, m.start()-4):m.start()]
            if not re.search(r"\d{4}\s*年\s*$", pre):
                mo, d = int(m.group(1)), int(m.group(2))
                if 1 <= mo <= 12 and 1 <= d <= 31:
                    return (
                        f"{ref_year:04d}-{mo:02d}-{d:02d}",
                        f"{ref_year:04d}-{mo:02d}-{d:02d}",
                        f"中文月日(发布年{ref_year}补全)",
                    )

    # 5. 英文月名
    if ref_year:
        m = _PAT_EN_MONTH.search(text)
        if m:
            mo = _MONTH_MAP.get(m.group(1).lower(), 0)
            d1 = int(m.group(2))
            d2 = int(m.group(3)) if m.group(3) else d1
            if mo and 1 <= d1 <= 31:
                return (
                    f"{ref_year:04d}-{mo:02d}-{d1:02d}",
                    f"{ref_year:04d}-{mo:02d}-{d2:02d}",
                    f"英文月名(发布年{ref_year}补全)",
                )

    # 6. 普通 M.DD 点格式（前后宽泛关键词，最后兜底）
    if ref_year:
        m = _PAT_DOT.search(text[:600])
        if m:
            ctx_s = max(0, m.start() - 80)
            ctx_e = min(len(text), m.end() + 80)
            ctx = text[ctx_s:ctx_e].lower()
            if any(k in ctx for k in _DOT_KEYWORDS):
                mo, d = int(m.group(1)), int(m.group(2))
                return (
                    f"{ref_year:04d}-{mo:02d}-{d:02d}",
                    f"{ref_year:04d}-{mo:02d}-{d:02d}",
                    f"M.DD点格式(发布年{ref_year}补全)",
                )

    return "", "", "未找到日期"


def _extract_times(text: str) -> tuple[str, str]:
    """
    提取活动时间（time_start, time_end）。

    策略：
    1. 优先找「活动时间/Activity time」标签后的时间
    2. 跳过「报名时间/Registration time」等标签后的时间段
    3. fallback：取文中前两个合法时间点
    """
    # 把文本按行/短句切分，标记每段是否是「跳过区」
    # 简化实现：找到 SKIP 标签位置，将其后 60 字打标为跳过
    skip_ranges: list[tuple[int, int]] = []
    for sm in _PAT_SKIP_TIME_LABEL.finditer(text[:3000]):
        skip_ranges.append((sm.start(), sm.end() + 60))

    def in_skip(pos: int) -> bool:
        return any(s <= pos < e for s, e in skip_ranges)

    # 先尝试「活动时间」标签后的时间
    activity_label = _PAT_ACTIVITY_TIME_LABEL.search(text[:3000])
    if activity_label:
        zone = text[activity_label.end(): activity_label.end() + 120]
        times_in_zone = []
        for m in _PAT_TIME.finditer(zone):
            h, mi = int(m.group(1)), int(m.group(2))
            if 6 <= h <= 23 and 0 <= mi <= 59:  # 排除深夜/凌晨异常值
                t = f"{h:02d}:{mi:02d}"
                if t not in times_in_zone:
                    times_in_zone.append(t)
                if len(times_in_zone) == 2:
                    break
        if times_in_zone:
            ts = times_in_zone[0]
            te = times_in_zone[1] if len(times_in_zone) > 1 else ""
            return ts, te

    # fallback：全文扫描，跳过报名时间段，只取 6:00-23:59 范围
    seen: list[str] = []
    for m in _PAT_TIME.finditer(text[:4000]):
        if in_skip(m.start()):
            continue
        h, mi = int(m.group(1)), int(m.group(2))
        if 6 <= h <= 23 and 0 <= mi <= 59:
            t = f"{h:02d}:{mi:02d}"
            if t not in seen:
                seen.append(t)
        if len(seen) == 2:
            break

    ts = seen[0] if seen else ""
    te = seen[1] if len(seen) > 1 else ""
    return ts, te


def _is_event(title: str, content: str) -> bool:
    """
    粗判断：标题或正文前 300 字是否像一篇活动推文。
    有活动关键词且无非活动关键词 → True。
    """
    t_lower = title.lower()
    c_lower = content[:300].lower()
    combined = t_lower + " " + c_lower

    # 非活动信号优先
    for kw in _NON_EVENT_TITLE_KEYWORDS:
        if kw in t_lower:
            return False

    for kw in _EVENT_TITLE_KEYWORDS:
        if kw in combined:
            return True

    return False


def _infer_categories(title: str, content: str) -> list[str]:
    t = title.lower()
    c = content[:200].lower()
    cats = []
    if any(k in t or k in c for k in ["lecture", "讲座", "seminar"]):
        cats.append("讲座")
    if any(k in t or k in c for k in ["recruitment", "招新", "招募"]):
        cats.append("招新")
    if any(k in t or k in c for k in ["workshop", "工作坊", "mindfulness", "正念"]):
        cats.append("社团活动")
    if any(k in t or k in c for k in ["open day", "开放日", "fair", "展", "招聘会"]):
        cats.append("校园活动")
    if not cats:
        cats.append("校园活动")
    return cats[:2]


def _build_description(title: str, content: str) -> str:
    """取正文前 120 字作简介，去掉多余空白。"""
    raw = content[:300].strip().replace("\n", " ")
    # 去掉重复空格
    raw = re.sub(r" {2,}", " ", raw)
    return raw[:120]


# ---------------------------------------------------------------------------
# 公开接口
# ---------------------------------------------------------------------------

def _load_articles() -> list[dict[str, Any]]:
    if not ARTICLES_FILE.exists():
        return []
    try:
        with open(ARTICLES_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("articles", []) if isinstance(data, dict) else []
    except Exception as e:
        logger.warning("读取 wechat_articles.json 失败: %s", e)
        return []


def refresh_wechat_events_cache() -> list[dict[str, Any]]:
    """
    读取文章缓存，用正则逐篇提取活动信息，写出 wechat_events.json。
    不需要 API Key，速度快，日期准确。
    """
    articles = _load_articles()
    if not articles:
        logger.info("无微信公众号文章缓存，跳过活动提取")
        payload = {
            "updated_at": datetime.now().isoformat(),
            "count": 0,
            "events": [],
        }
        EVENTS_CACHE.parent.mkdir(parents=True, exist_ok=True)
        with open(EVENTS_CACHE, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        return []

    events: list[dict[str, Any]] = []
    skipped_no_content = 0
    skipped_not_event = 0

    for art in articles:
        title = (art.get("title") or "").strip()
        content = (art.get("content") or art.get("summary") or "").strip()
        if not title or len(content) < 20:
            skipped_no_content += 1
            continue

        if not _is_event(title, content):
            skipped_not_event += 1
            continue

        ref_year = _pub_year(art)
        ds, de, pat = _extract_date(content, ref_year)
        ts, te = _extract_times(content)
        desc = _build_description(title, content)
        cats = _infer_categories(title, content)

        sogou = (art.get("sogou_link") or "").strip()
        account = (art.get("account") or "").strip()

        events.append(
            {
                "title": title,
                "date_start": ds,
                "date_end": de,
                "time_start": ts,
                "time_end": te,
                "location": "",
                "description": desc,
                "categories": cats,
                "sogou_link": sogou,
                "account": account,
                "source_article_title": title,
                "_date_pattern": pat,  # 调试用，不影响前端展示
            }
        )

    logger.info(
        "公众号活动提取完成：共 %d 条活动，跳过无内容 %d 篇，跳过非活动 %d 篇",
        len(events),
        skipped_no_content,
        skipped_not_event,
    )

    payload = {
        "updated_at": datetime.now().isoformat(),
        "count": len(events),
        "events": events,
    }
    EVENTS_CACHE.parent.mkdir(parents=True, exist_ok=True)
    with open(EVENTS_CACHE, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return events


def get_cached_wechat_events() -> list[dict[str, Any]]:
    """读取 wechat_events.json；不存在则返回空列表。"""
    if not EVENTS_CACHE.exists():
        return []
    try:
        with open(EVENTS_CACHE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("events", []) if isinstance(data, dict) else []
    except Exception:
        return []
