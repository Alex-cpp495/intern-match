"""
不用 AI，纯正则从 HealthyUunnc 文章正文提取活动日期，打印结果。
"""
import json
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DATA = r"e:\Desktop\hack\intern-match\backend\data\wechat_articles.json"

# ---- 日期正则 ----
# 模式1: 2023年11月4日  /  2023年11月4-6日
PAT_FULL = re.compile(
    r"(20\d{2})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*[日号]"
    r"(?:\s*[至到~\-—–]\s*(\d{1,2})\s*[日号])?",
    re.UNICODE,
)
# 模式2: 2023-11-04  /  2023/11/04
PAT_ISO = re.compile(r"(?<!\d)(20\d{2})[-/](\d{1,2})[-/](\d{1,2})(?!\d)")
# 模式3: 只有「4月24日」「4月24号」（无年份，需结合 publish_date 推断）
PAT_NOYR = re.compile(r"(?<!\d)(\d{1,2})\s*月\s*(\d{1,2})\s*[日号]")
# 模式4: 时间 HH:MM 或 HH点
PAT_TIME = re.compile(r"(\d{1,2})[:\：点](\d{2})?(?!\d)")


def extract_dates(text: str, pub_year: int | None):
    """返回 (date_start, date_end, source_pattern)"""
    # 优先找带年份的日期
    m = PAT_FULL.search(text)
    if m:
        y = int(m.group(1))
        mo = int(m.group(2))
        d1 = int(m.group(3))
        d2 = int(m.group(4)) if m.group(4) else d1
        return (
            f"{y:04d}-{mo:02d}-{d1:02d}",
            f"{y:04d}-{mo:02d}-{d2:02d}",
            "中文全日期",
        )
    m = PAT_ISO.search(text)
    if m:
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        return f"{y:04d}-{mo:02d}-{d:02d}", f"{y:04d}-{mo:02d}-{d:02d}", "ISO日期"
    # 无年份，用 publish_date 的年份补全
    m = PAT_NOYR.search(text)
    if m and pub_year:
        mo, d = int(m.group(1)), int(m.group(2))
        if 1 <= mo <= 12 and 1 <= d <= 31:
            return (
                f"{pub_year:04d}-{mo:02d}-{d:02d}",
                f"{pub_year:04d}-{mo:02d}-{d:02d}",
                f"月日(用发布年{pub_year}补全)",
            )
    return "", "", "未找到日期"


def extract_time(text: str):
    times = []
    for m in PAT_TIME.finditer(text[:3000]):
        h = int(m.group(1))
        mi = int(m.group(2)) if m.group(2) else 0
        if 0 <= h <= 23 and 0 <= mi <= 59:
            times.append(f"{h:02d}:{mi:02d}")
    # 去重保序，取前两个
    seen, result = set(), []
    for t in times:
        if t not in seen:
            seen.add(t)
            result.append(t)
        if len(result) == 2:
            break
    return result


d = json.load(open(DATA, encoding="utf-8"))
arts = [a for a in d.get("articles", []) if a.get("account", "") == "HealthyUunnc"]

print(f"HealthyUunnc 共 {len(arts)} 篇\n{'='*70}")

has_date = 0
for i, a in enumerate(arts):
    title = a.get("title", "")
    pub = a.get("publish_date", "") or ""
    pub_year = int(pub[:4]) if len(pub) >= 4 and pub[:4].isdigit() else None
    content = (a.get("content") or a.get("summary") or "").strip()

    ds, de, pat = extract_dates(content, pub_year)

    times = extract_time(content) if content else []
    t_str = " ~ ".join(times) if times else ""

    status = "✓" if ds else "✗"
    if ds:
        has_date += 1

    print(f"[{i+1:02d}] {status} {title[:52]}")
    print(f"      发布:{pub or '(无)'}  活动日期: {ds or '(未知)'}", end="")
    if de and de != ds:
        print(f" ~ {de}", end="")
    print(f"  [{pat}]")
    if t_str:
        print(f"      时间线索: {t_str}")
    # 显示正文前120字，帮助判断
    preview = content[:120].replace("\n", " ")
    if preview:
        print(f"      摘要: {preview}")
    print()

print(f"{'='*70}")
print(f"共 {len(arts)} 篇，其中 {has_date} 篇找到活动日期，{len(arts)-has_date} 篇未找到")
