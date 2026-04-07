"""
对3个新公众号的文章跑正则活动提取，不覆盖缓存。
"""
import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from scraper.wechat_event_extractor import (
    _is_event, _extract_date, _extract_times, _pub_year,
    _infer_categories, _build_description,
)

DATA = Path(__file__).parent.parent / 'data' / 'wechat_articles.json'
d = json.load(open(DATA, encoding='utf-8'))
all_arts = d.get('articles', [])

# 只看3个新公众号（通过关键词匹配标题或account）
new_kw = ['宁波诺丁汉大学学生事务', '宁波诺丁汉大学理工学院', '宁波诺丁汉大学图书馆']

# 这些文章还没在缓存里（因为只是测试脚本爬了，没写入主缓存）
# 直接用之前爬取脚本存在内存里的临时数据再跑一遍
# 改为直接从刚爬的临时结果文件读取——但那只是打印的
# 最简单的做法：从主缓存里用搜索词匹配

# 由于测试脚本没写入缓存，我们直接再用 scrape_multi_query_articles 的结果
# 但那要重新爬太慢。改为：从现有缓存中看有没有重叠的文章

print("检查主缓存中3个新公众号的文章数（可能因还未合并而为0）:")
for kw in new_kw:
    count = sum(1 for a in all_arts if kw in (a.get('account','') or a.get('search_query','')))
    print(f"  {kw}: {count} 篇")

# 如果缓存里没有就说明需要先完整刷新
print()
print("由于测试脚本未写入主缓存，需要触发一次完整刷新才能看到。")
print("建议在前端点击'刷新'按钮，或手动调用 refresh_wechat_cache()。")
