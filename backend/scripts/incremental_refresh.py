"""
增量合并：读取现有缓存，把新爬到的文章合并进去（不删除旧的），然后重新提取活动。
"""
import sys, json, logging, os, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
logging.basicConfig(level=logging.INFO, format='%(levelname)s %(name)s: %(message)s',
                    stream=sys.stdout)

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / '.env')

from scraper.wechat_articles import scrape_multi_query_articles, CACHE_FILE
from scraper.wechat_event_extractor import refresh_wechat_events_cache
from datetime import datetime
from collections import Counter

# 读取现有缓存
existing = []
if CACHE_FILE.exists():
    d = json.load(open(CACHE_FILE, encoding='utf-8'))
    existing = d.get('articles', [])
print(f"现有缓存: {len(existing)} 篇")

# 只爬新增3个公众号
new_queries = [
    {"query": "宁波诺丁汉大学学生事务", "label": "宁波诺丁汉大学学生事务", "max_pages": 3},
    {"query": "宁波诺丁汉大学理工学院", "label": "宁波诺丁汉大学理工学院", "max_pages": 3},
    {"query": "宁波诺丁汉大学图书馆", "label": "宁波诺丁汉大学图书馆", "max_pages": 3},
]
print("\n开始爬取新增3个公众号...\n")
new_arts = scrape_multi_query_articles(queries=new_queries, fetch_content=True)
print(f"\n新爬到: {len(new_arts)} 篇")

# 增量合并：按标题去重
seen_titles = set()
merged = []
for a in existing:
    t = a.get('title','').strip()
    if t and t not in seen_titles:
        seen_titles.add(t)
        merged.append(a)
added = 0
for a in new_arts:
    t = a.get('title','').strip()
    if t and t not in seen_titles:
        seen_titles.add(t)
        merged.append(a)
        added += 1

print(f"\n增量合并: 原 {len(existing)} + 新增 {added} = 共 {len(merged)} 篇")

acct = Counter(a.get('account','(未知)') for a in merged)
print("\n按公众号分布:")
for name, cnt in acct.most_common():
    print(f"  {name}: {cnt} 篇")

# 写入缓存
payload = {
    "updated_at": datetime.now().isoformat(),
    "count": len(merged),
    "articles": merged,
}
with open(CACHE_FILE, "w", encoding="utf-8") as f:
    json.dump(payload, f, ensure_ascii=False, indent=2)
print(f"\n缓存已更新: {CACHE_FILE}")

# 正则活动提取
print("\n===== 正则活动提取 =====\n")
events = refresh_wechat_events_cache()

ev_acct = Counter(e.get('account','(未知)') for e in events)
print(f"\n共 {len(events)} 条活动:")
for name, cnt in ev_acct.most_common():
    print(f"  {name}: {cnt} 条")

new_accts = {'宁波诺丁汉大学学生事务', '宁波诺丁汉大学理工学院', '宁波诺丁汉大学图书馆'}
new_evts = [e for e in events if e.get('account','') in new_accts]
if new_evts:
    print(f"\n===== 新增公众号活动明细 ({len(new_evts)} 条) =====\n")
    for e in new_evts:
        ds = e.get('date_start','')
        de = e.get('date_end','')
        date_str = ds if ds == de else f"{ds} ~ {de}"
        ts = e.get('time_start','')
        te = e.get('time_end','')
        time_str = f" {ts}~{te}" if ts else ""
        pat = e.get('_date_pattern','')
        print(f"[{e.get('account',''):8s}] {e.get('title','')[:50]}")
        print(f"           日期:{date_str or '(待定)'}  [{pat}]{time_str}")
else:
    print("\n新增公众号暂未提取到活动（可能搜狗限流导致未爬到文章）")
