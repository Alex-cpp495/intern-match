"""
分两批爬取：先爬新增3个公众号，再爬原有的，中间间隔让搜狗冷却。
最后合并结果并写入缓存。
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

# 第1批：新增3个公众号
batch1 = [
    {"query": "宁波诺丁汉大学学生事务", "label": "宁波诺丁汉大学学生事务", "max_pages": 3},
    {"query": "宁波诺丁汉大学理工学院", "label": "宁波诺丁汉大学理工学院", "max_pages": 3},
    {"query": "宁波诺丁汉大学图书馆", "label": "宁波诺丁汉大学图书馆", "max_pages": 3},
]
print("===== 第1批：新增3个公众号 =====\n")
arts1 = scrape_multi_query_articles(queries=batch1, fetch_content=True)
print(f"\n第1批完成，{len(arts1)} 篇\n")

print("等待 15 秒让搜狗冷却...\n")
time.sleep(15)

# 第2批：原有关键词
batch2 = [
    {"query": "HealthyUunnc", "label": "HealthyUunnc", "max_pages": 10},
    {"query": "宁波诺丁汉大学", "label": "宁波诺丁汉大学", "max_pages": 3},
    {"query": "UNNC学生会", "label": "UNNC学生会", "max_pages": 3},
    {"query": "宁诺就业", "label": "宁诺就业", "max_pages": 3},
    {"query": "宁诺校园活动", "label": "宁诺校园活动", "max_pages": 2},
]
print("===== 第2批：原有关键词 =====\n")
arts2 = scrape_multi_query_articles(queries=batch2, fetch_content=True)
print(f"\n第2批完成，{len(arts2)} 篇\n")

# 合并去重（按标题）
seen = set()
merged = []
for a in arts1 + arts2:
    key = a.get('title','').strip()
    if key and key not in seen:
        seen.add(key)
        merged.append(a)

print(f"合并去重后 {len(merged)} 篇")

# 按 account 统计
from collections import Counter
acct = Counter(a.get('account','(未知)') for a in merged)
print("\n按公众号分布:")
for name, cnt in acct.most_common():
    print(f"  {name}: {cnt} 篇")

# 写入缓存
all_queries = [q["query"] for q in batch1 + batch2]
payload = {
    "updated_at": datetime.now().isoformat(),
    "count": len(merged),
    "queries": all_queries,
    "articles": merged,
}
CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
with open(CACHE_FILE, "w", encoding="utf-8") as f:
    json.dump(payload, f, ensure_ascii=False, indent=2)
print(f"\n已写入缓存: {CACHE_FILE}")

# 正则活动提取
print("\n===== 正则活动提取 =====\n")
events = refresh_wechat_events_cache()
print(f"\n提取完成，共 {len(events)} 条活动")

ev_acct = Counter(e.get('account','(未知)') for e in events)
print("\n活动按公众号分布:")
for name, cnt in ev_acct.most_common():
    print(f"  {name}: {cnt} 条")

print("\n===== 新增公众号活动明细 =====\n")
new_accts = {'宁波诺丁汉大学学生事务', '宁波诺丁汉大学理工学院', '宁波诺丁汉大学图书馆'}
for e in events:
    if e.get('account','') in new_accts:
        ds = e.get('date_start','')
        de = e.get('date_end','')
        date_str = ds if ds == de else f"{ds} ~ {de}"
        ts = e.get('time_start','')
        te = e.get('time_end','')
        time_str = f" {ts}~{te}" if ts else ""
        pat = e.get('_date_pattern','')
        print(f"[{e.get('account','')[:8]:8s}] {e.get('title','')[:45]}")
        print(f"           日期:{date_str or '(待定)'}  [{pat}]{time_str}")
