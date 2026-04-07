"""
只爬取新增的3个公众号关键词，打印结果，不覆盖现有缓存。
"""
import sys, json, logging
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

logging.basicConfig(level=logging.INFO, format='%(levelname)s %(name)s: %(message)s',
                    stream=sys.stdout)

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / '.env')

from scraper.wechat_articles import scrape_multi_query_articles

new_queries = [
    {"query": "宁波诺丁汉大学学生事务", "label": "宁波诺丁汉大学学生事务", "max_pages": 3},
    {"query": "宁波诺丁汉大学理工学院", "label": "宁波诺丁汉大学理工学院", "max_pages": 3},
    {"query": "宁波诺丁汉大学图书馆", "label": "宁波诺丁汉大学图书馆", "max_pages": 3},
]

print("开始爬取新增3个公众号...\n")
articles = scrape_multi_query_articles(queries=new_queries, fetch_content=True)

print(f"\n{'='*60}")
print(f"共抓取 {len(articles)} 篇文章")
print()

# 按 account 分组
from collections import Counter
acct_count = Counter(a.get('account','(未知)') for a in articles)
print("按公众号分布:")
for acct, cnt in acct_count.most_common():
    print(f"  {acct}: {cnt} 篇")
print()

for i, a in enumerate(articles[:30]):
    title = a.get('title','')[:55]
    pub = a.get('publish_date','') or ''
    acct = a.get('account','')
    clen = len(a.get('content','') or '')
    print(f"[{i+1:02d}] {title}")
    print(f"      账号:{acct}  发布:{pub or '(无)'}  正文:{clen}字")
