"""临时爬虫脚本，带实时进度输出"""
import logging
import sys

# 配置日志输出到终端
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
    force=True,
)

print("=" * 50)
print("开始爬取实习岗位...")
print("=" * 50)

from scraper.shixiseng import refresh_cache

jobs = refresh_cache(force_scrape=True)

print("=" * 50)
print(f"✅ 完成！共获取 {len(jobs)} 条岗位")
from collections import Counter
sources = Counter(j.get("source", "未知") for j in jobs)
for src, cnt in sources.items():
    print(f"   {src}: {cnt} 条")
print("=" * 50)
