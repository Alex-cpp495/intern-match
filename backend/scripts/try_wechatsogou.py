#!/usr/bin/env python3
"""
手动验证 chyroc/wechatsogou 是否仍可用（不启动 FastAPI）。

用法（在 backend 目录）:
  .\\.venv\\Scripts\\python.exe scripts\\try_wechatsogou.py

说明：库最后更新面向多年前的搜狗 HTML；当前页面结构变化会导致解析失败或空结果。
"""

from __future__ import annotations

import os
import sys

# 保证可导入 scraper.*
_BACKEND_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND_ROOT not in sys.path:
    sys.path.insert(0, _BACKEND_ROOT)


def main() -> None:
    from scraper.wechatsogou_compat import install_wechatsogou_werkzeug_shim

    install_wechatsogou_werkzeug_shim()
    import wechatsogou

    ws = wechatsogou.WechatSogouAPI(captcha_break_time=1)
    kw = "HealthyUunnc"

    print("=== search_gzh ===")
    try:
        gz = list(ws.search_gzh(kw))
        print("count:", len(gz))
        if gz:
            print("first keys:", gz[0].keys())
    except Exception as e:
        print("error:", e)

    print("\n=== search_article (page=1) ===")
    try:
        arts = list(ws.search_article(kw, page=1))
        print("count:", len(arts))
        if arts:
            a = arts[0].get("article", {})
            print("title:", a.get("title", "")[:60])
            print("url:", (a.get("url") or "")[:90])
    except Exception as e:
        print("error:", type(e).__name__, e)

    print("\n=== get_gzh_article_by_history ===")
    try:
        h = ws.get_gzh_article_by_history(kw)
        n = len(h.get("article", [])) if isinstance(h, dict) else 0
        print("article count:", n, "gzh keys:", list(h.keys()) if isinstance(h, dict) else h)
    except Exception as e:
        print("error:", type(e).__name__, e)


if __name__ == "__main__":
    main()
