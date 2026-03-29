"""
一次性补丁脚本：修复现有 wechat_articles.json 缓存中的空字段
- account -> HealthyUunnc
- wechat_url -> sogou_link (在浏览器中可跳转到微信文章)
- content -> summary (摘要作为预览内容)
运行：cd backend && python patch_cache.py
"""
import json
from pathlib import Path

cache_file = Path(__file__).parent / "data" / "wechat_articles.json"

with open(cache_file, "r", encoding="utf-8") as f:
    data = json.load(f)

articles = data.get("articles", [])
fixed = 0
for a in articles:
    changed = False
    if not a.get("account"):
        a["account"] = "HealthyUunnc"
        changed = True
    if not a.get("wechat_url") and a.get("sogou_link"):
        a["wechat_url"] = a["sogou_link"]
        changed = True
    if not a.get("content") and a.get("summary"):
        a["content"] = a["summary"]
        changed = True
    if changed:
        fixed += 1

with open(cache_file, "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print(f"Done: patched {fixed}/{len(articles)} articles")
