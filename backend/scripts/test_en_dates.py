"""
测试加入英文日期格式后的误匹配情况。
重点检查：原来✗的20篇，加了英文正则后能正确识别几篇，误匹配几篇。
"""
import json
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DATA = r"e:\Desktop\hack\intern-match\backend\data\wechat_articles.json"

# ---- 中文日期正则（原有）----
PAT_FULL = re.compile(
    r"(20\d{2})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*[日号]"
    r"(?:\s*[至到~\-—–]\s*(\d{1,2})\s*[日号])?",
    re.UNICODE,
)
PAT_ISO = re.compile(r"(?<!\d)(20\d{2})[-/](\d{1,2})[-/](\d{1,2})(?!\d)")
PAT_NOYR_CN = re.compile(r"(?<!\d)(\d{1,2})\s*月\s*(\d{1,2})\s*[日号]")

# ---- 新增英文日期正则 ----
# M.DD 或 MM.DD，如 4.24、10.22（前后不能有数字，避免版本号误匹配）
# 限制：月1-12，日1-31
PAT_DOT = re.compile(r"(?<!\d)([1-9]|1[0-2])\.([1-9]|[12]\d|3[01])(?!\d)")
# Month DD 或 Month DD-DD，如 April 24、Nov 29
MONTHS = {
    "january":1,"february":2,"march":3,"april":4,"may":5,"june":6,
    "july":7,"august":8,"september":9,"october":10,"november":11,"december":12,
    "jan":1,"feb":2,"mar":3,"apr":4,"jun":6,"jul":7,
    "aug":8,"sep":9,"sept":9,"oct":10,"nov":11,"dec":12,
}
PAT_EN_MONTH = re.compile(
    r"\b(january|february|march|april|may|june|july|august|september|october|november|december"
    r"|jan|feb|mar|apr|jun|jul|aug|sep|sept|oct|nov|dec)\b[\s.]*(\d{1,2})(?:\s*[-–]\s*(\d{1,2}))?",
    re.IGNORECASE,
)


def extract_dates_v2(text: str, pub_year: int | None):
    """返回 (date_start, date_end, source_pattern, confidence)
    confidence: 'high' = 带四位年份; 'med' = 月日+发布年补全; 'low' = 英文点格式
    """
    if not text:
        return "", "", "无内容", "none"

    # 1. 中文全日期（最可靠）
    m = PAT_FULL.search(text)
    if m:
        y = int(m.group(1))
        mo = int(m.group(2))
        d1 = int(m.group(3))
        d2 = int(m.group(4)) if m.group(4) else d1
        return (f"{y:04d}-{mo:02d}-{d1:02d}", f"{y:04d}-{mo:02d}-{d2:02d}", "中文全日期", "high")

    # 2. ISO 日期
    m = PAT_ISO.search(text)
    if m:
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        return (f"{y:04d}-{mo:02d}-{d:02d}", f"{y:04d}-{mo:02d}-{d:02d}", "ISO日期", "high")

    # 3. 中文月日（无年份）
    m = PAT_NOYR_CN.search(text)
    if m and pub_year:
        mo, d = int(m.group(1)), int(m.group(2))
        if 1 <= mo <= 12 and 1 <= d <= 31:
            return (
                f"{pub_year:04d}-{mo:02d}-{d:02d}",
                f"{pub_year:04d}-{mo:02d}-{d:02d}",
                f"中文月日(发布年{pub_year}补全)",
                "med",
            )

    # 4. 英文月名
    m = PAT_EN_MONTH.search(text)
    if m and pub_year:
        mo = MONTHS.get(m.group(1).lower(), 0)
        d1 = int(m.group(2))
        d2 = int(m.group(3)) if m.group(3) else d1
        if mo and 1 <= d1 <= 31:
            return (
                f"{pub_year:04d}-{mo:02d}-{d1:02d}",
                f"{pub_year:04d}-{mo:02d}-{d2:02d}",
                f"英文月名(发布年{pub_year}补全)",
                "med",
            )

    # 5. M.DD 点格式（最容易误匹配，放最后）
    # 只在正文前500字（活动公告通常日期在前面）
    m = PAT_DOT.search(text[:500])
    if m and pub_year:
        mo, d = int(m.group(1)), int(m.group(2))
        # 额外验证：前后文要有"time"/"时间"/"date"/"活动"等关键词
        ctx_start = max(0, m.start() - 60)
        ctx_end = min(len(text), m.end() + 60)
        ctx = text[ctx_start:ctx_end].lower()
        keywords = ["time","date","event","activity","venue","location","时间","活动","地点","日期"]
        if any(k in ctx for k in keywords):
            return (
                f"{pub_year:04d}-{mo:02d}-{d:02d}",
                f"{pub_year:04d}-{mo:02d}-{d:02d}",
                f"M.DD点格式(发布年{pub_year}补全)",
                "low",
            )

    return "", "", "未找到日期", "none"


d = json.load(open(DATA, encoding="utf-8"))
arts = [a for a in d.get("articles", []) if a.get("account", "") == "HealthyUunnc"]

# 只看原来✗的那些（加英文后的变化）
print("=== 原来「未找到日期」的文章，加英文正则后的变化 ===\n")
new_found = 0
for i, a in enumerate(arts):
    title = a.get("title", "")
    pub = a.get("publish_date", "") or ""
    pub_year = int(pub[:4]) if len(pub) >= 4 and pub[:4].isdigit() else None
    content = (a.get("content") or a.get("summary") or "").strip()
    ds, de, pat, conf = extract_dates_v2(content, pub_year)

    # 打印所有结果，标注置信度
    icon = {"high":"✓✓","med":"✓ ","low":"⚠ ","none":"✗ "}[conf]
    print(f"[{i+1:02d}]{icon} {title[:52]}")
    print(f"      发布:{pub or '(无)'}  →  {ds or '(未知)'}  [{pat}]  conf={conf}")
    if conf == "low":
        # 显示上下文帮助判断是否误匹配
        c_preview = content[:400].replace("\n", " ")
        print(f"      ⚠️ 低置信，正文预览: {c_preview[:150]}")
    print()

high_med = sum(
    1 for a in arts
    if extract_dates_v2(
        (a.get("content") or a.get("summary") or "").strip(),
        int(p[:4]) if len(p:=a.get("publish_date","")or"") >= 4 and p[:4].isdigit() else None
    )[3] in ("high","med")
)
low_conf = sum(
    1 for a in arts
    if extract_dates_v2(
        (a.get("content") or a.get("summary") or "").strip(),
        int(p[:4]) if len(p:=a.get("publish_date","")or"") >= 4 and p[:4].isdigit() else None
    )[3] == "low"
)
none_conf = sum(
    1 for a in arts
    if extract_dates_v2(
        (a.get("content") or a.get("summary") or "").strip(),
        int(p[:4]) if len(p:=a.get("publish_date","")or"") >= 4 and p[:4].isdigit() else None
    )[3] == "none"
)
print(f"{'='*60}")
print(f"总计 {len(arts)} 篇:")
print(f"  ✓✓ 高置信(带年份):  {sum(1 for a in arts if extract_dates_v2((a.get('content') or a.get('summary') or '').strip(), int(p[:4]) if len(p:=a.get('publish_date','')or'')>=4 and p[:4].isdigit() else None)[3]=='high')} 篇")
print(f"  ✓  中置信(月日补全): {sum(1 for a in arts if extract_dates_v2((a.get('content') or a.get('summary') or '').strip(), int(p[:4]) if len(p:=a.get('publish_date','')or'')>=4 and p[:4].isdigit() else None)[3]=='med')} 篇")
print(f"  ⚠  低置信(点格式):   {low_conf} 篇")
print(f"  ✗  未找到日期:       {none_conf} 篇")
