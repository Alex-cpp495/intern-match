"""
完整刷新：爬取所有关键词 + 正则活动提取，写入缓存文件。
"""
import sys, json, logging, os
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

logging.basicConfig(level=logging.INFO, format='%(levelname)s %(name)s: %(message)s',
                    stream=sys.stdout)

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / '.env')

from scraper.wechat_articles import refresh_wechat_cache
from scraper.wechat_event_extractor import refresh_wechat_events_cache

print("===== 第1步：爬取所有关键词的文章 =====\n")
articles = refresh_wechat_cache(fetch_content=True)
print(f"\n爬取完成，共 {len(articles)} 篇文章已写入缓存")

# 按 account 统计
from collections import Counter
acct = Counter(a.get('account','(未知)') for a in articles)
print("\n按公众号分布:")
for name, cnt in acct.most_common():
    print(f"  {name}: {cnt} 篇")

print("\n===== 第2步：正则活动提取 =====\n")
events = refresh_wechat_events_cache()
print(f"\n提取完成，共 {len(events)} 条活动已写入缓存")

# 按 account 统计活动
ev_acct = Counter(e.get('account','(未知)') for e in events)
print("\n活动按公众号分布:")
for name, cnt in ev_acct.most_common():
    print(f"  {name}: {cnt} 条")

print("\n===== 活动明细 =====\n")
for e in events:
    ds = e.get('date_start','')
    de = e.get('date_end','')
    date_str = ds if ds == de else f"{ds} ~ {de}"
    ts = e.get('time_start','')
    te = e.get('time_end','')
    time_str = f" {ts}~{te}" if ts else ""
    acct_name = e.get('account','')
    pat = e.get('_date_pattern','')
    print(f"[{acct_name[:8]:8s}] {e.get('title','')[:45]}")
    print(f"           日期:{date_str or '(待定)'}  [{pat}]{time_str}")
