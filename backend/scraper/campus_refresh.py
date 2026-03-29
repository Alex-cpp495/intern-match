"""
校园活动相关缓存的统一刷新：官网活动 + Careers 讲座 / 招聘会 / 宣讲会。
供定时任务与 POST /api/campus/refresh-all 调用。
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

logger = logging.getLogger(__name__)


def refresh_all_campus_caches() -> None:
    """顺序执行各爬虫并写本地 JSON，失败项记录日志但不中断后续步骤。"""
    from scraper.unnc_events import refresh_events_cache
    from scraper.careers_lectures import refresh_careers_cache
    from scraper.careers_jobfairs import refresh_jobfairs_cache
    from scraper.careers_teachins import refresh_teachins_cache
    from scraper.wechat_articles import refresh_wechat_cache

    steps: list[tuple[str, Callable[[], Any]]] = [
        ("官网活动", refresh_events_cache),
        ("Careers 讲座", refresh_careers_cache),
        ("招聘会", refresh_jobfairs_cache),
        ("宣讲会", refresh_teachins_cache),
        ("微信公众号文章", refresh_wechat_cache),
    ]
    for name, fn in steps:
        try:
            fn()
            logger.info("校园缓存刷新：%s 已完成", name)
        except Exception:
            logger.exception("校园缓存刷新：%s 失败", name)
