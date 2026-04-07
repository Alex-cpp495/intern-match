"""
微信公众号文章获取 —— 基于 wxmp（微信公众平台后台 API）。

优于搜狗搜索的关键点：
  - 全量历史文章（不限 10 条）
  - 完整正文 + 精确发布时间（不靠 HTML 解析）
  - 无搜狗验证码/反爬
  - 增量更新：只拉取上次缓存之后的新文章

前提：需要一个微信公众号管理员扫码登录，获取 Cookie 后配置到
  backend/data/wxmp_cookies.json
Cookie 约 4 天过期，需要定期更新。
"""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent.parent / "data"
COOKIES_FILE = DATA_DIR / "wxmp_cookies.json"
ARTICLES_CACHE = DATA_DIR / "wechat_articles.json"

_ACCOUNTS_TO_MONITOR: list[str] = [
    "HealthyUunnc",
    "宁波诺丁汉大学",
    "宁波诺丁汉大学学生事务",
    "宁波诺丁汉大学理工学院",
    "宁波诺丁汉大学图书馆",
    "UNNC学生会",
]


def _load_cookies() -> dict[str, str] | None:
    if not COOKIES_FILE.exists():
        logger.warning(
            "wxmp cookies 文件不存在: %s — 请先扫码登录微信公众平台获取 Cookie",
            COOKIES_FILE,
        )
        return None
    try:
        with open(COOKIES_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict) or not data:
            return None
        return data
    except Exception as e:
        logger.warning("读取 wxmp cookies 失败: %s", e)
        return None


def _article_html_to_text(url: str) -> str:
    """从微信文章 URL 获取纯文本正文。"""
    try:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
        }
        resp = requests.get(url, headers=headers, timeout=15)
        resp.encoding = "utf-8"
        if resp.status_code != 200:
            return ""
        soup = BeautifulSoup(resp.text, "lxml")
        content_el = (
            soup.select_one("#js_content")
            or soup.select_one(".rich_media_content")
            or soup.select_one("article")
        )
        if not content_el:
            return ""
        for tag in content_el.find_all(["script", "style"]):
            tag.decompose()
        text = content_el.get_text("\n", strip=True)
        import re
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text[:300_000]
    except Exception as e:
        logger.debug("获取文章正文失败 %s: %s", url[:60], e)
        return ""


def is_wxmp_available() -> bool:
    """检查 wxmp cookies 是否存在且 wxmp 库可用。"""
    cookies = _load_cookies()
    if not cookies:
        return False
    try:
        from wxmp import WxMPAPI
        return True
    except ImportError:
        logger.warning("wxmp 库未安装，pip install wxmp")
        return False


def check_wxmp_session_valid() -> dict[str, Any]:
    """
    检查当前 wxmp session 是否有效。
    返回 {"valid": bool, "message": str}
    """
    cookies = _load_cookies()
    if not cookies:
        return {"valid": False, "message": "Cookie 文件不存在，请扫码登录"}
    try:
        from wxmp import WxMPAPI
        api = WxMPAPI(cookies)
        resp = api.fetch_fakeid("test")
        return {"valid": True, "message": "Session 有效"}
    except Exception as e:
        msg = str(e)
        if "token" in msg.lower() or "login" in msg.lower() or "expired" in msg.lower():
            return {"valid": False, "message": f"Session 已过期，请重新扫码登录: {msg}"}
        return {"valid": False, "message": f"检查失败: {msg}"}


def fetch_articles_via_wxmp(
    accounts: list[str] | None = None,
    max_articles_per_account: int = 50,
    fetch_content: bool = True,
) -> list[dict[str, Any]]:
    """
    通过 wxmp 获取指定公众号的文章列表。

    返回与 wechat_articles.py 兼容的 article dict 列表。
    """
    cookies = _load_cookies()
    if not cookies:
        raise RuntimeError("wxmp cookies 未配置，无法获取文章")

    from wxmp import WxMPAPI

    api = WxMPAPI(cookies)
    target_accounts = accounts or _ACCOUNTS_TO_MONITOR
    all_articles: list[dict[str, Any]] = []

    for account_name in target_accounts:
        logger.info("wxmp: 搜索公众号「%s」...", account_name)
        try:
            search_resp = api.fetch_fakeid(account_name)
        except Exception as e:
            logger.warning("wxmp: 搜索「%s」失败: %s", account_name, e)
            continue

        if not search_resp.arr:
            logger.warning("wxmp: 未找到公众号「%s」", account_name)
            continue

        biz = search_resp.arr[0]
        fakeid = biz.fakeid
        nickname = biz.nickname
        logger.info("wxmp: 找到「%s」(fakeid=%s)，开始拉取文章...", nickname, fakeid[:8])

        begin = 0
        count = 5
        fetched = 0

        while fetched < max_articles_per_account:
            try:
                articles_resp = api.fetch_articles(fakeid, begin=begin, count=count)
            except Exception as e:
                logger.warning(
                    "wxmp: 拉取「%s」文章失败 (begin=%d): %s",
                    nickname, begin, e,
                )
                break

            items = articles_resp.app_msg_list if hasattr(articles_resp, "app_msg_list") else []
            if not items:
                break

            for item in items:
                title = getattr(item, "title", "") or ""
                link = getattr(item, "link", "") or ""
                create_time = getattr(item, "create_time", 0) or 0
                cover = getattr(item, "cover", "") or ""

                pub_date = ""
                if create_time:
                    try:
                        pub_date = datetime.fromtimestamp(int(create_time)).strftime("%Y-%m-%d")
                    except (ValueError, OSError):
                        pass

                content = ""
                if fetch_content and link:
                    content = _article_html_to_text(link)
                    time.sleep(0.3)

                article = {
                    "title": title.strip(),
                    "date": pub_date,
                    "publish_date": pub_date,
                    "summary": content[:200] if content else "",
                    "account": nickname,
                    "sogou_link": "",
                    "wechat_url": link,
                    "img_url": cover,
                    "content": content,
                    "search_query": account_name,
                    "source": "wxmp",
                }
                all_articles.append(article)
                fetched += 1

            begin += count
            time.sleep(1.0)

        logger.info("wxmp: 「%s」共拉取 %d 篇文章", nickname, fetched)

    logger.info("wxmp: 全部完成，共 %d 篇文章", len(all_articles))
    return all_articles


def refresh_articles_via_wxmp(fetch_content: bool = True) -> list[dict[str, Any]] | None:
    """
    用 wxmp 刷新文章缓存。成功返回文章列表，wxmp 不可用返回 None。
    与 wechat_articles.py 的增量合并逻辑配合使用。
    """
    if not is_wxmp_available():
        return None

    try:
        return fetch_articles_via_wxmp(fetch_content=fetch_content)
    except Exception:
        logger.exception("wxmp 文章获取失败")
        return None
