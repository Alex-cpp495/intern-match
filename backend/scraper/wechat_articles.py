"""
微信公众号文章爬虫（多关键词版）
数据来源：搜狗微信搜索（weixin.sogou.com）
流程：搜狗搜索列表 → 同 Session 跟进跳转链接 → 微信文章原页面正文

支持配置多组搜索关键词，分别爬取后合并缓存。
"""

from __future__ import annotations

import json
import logging
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

SOGOU_SEARCH_URL = "https://weixin.sogou.com/weixin"
CACHE_FILE = Path(__file__).parent.parent / "data" / "wechat_articles.json"
MAX_PAGES = 10
QUERY = "HealthyUunnc"

SEARCH_QUERIES: list[dict] = [
    {"query": "HealthyUunnc", "label": "HealthyUunnc", "max_pages": 10},
    {"query": "宁波诺丁汉大学", "label": "宁波诺丁汉大学", "max_pages": 3},
    {"query": "UNNC学生会", "label": "UNNC学生会", "max_pages": 3},
    {"query": "宁诺就业", "label": "宁诺就业", "max_pages": 3},
    {"query": "宁诺校园活动", "label": "宁诺校园活动", "max_pages": 2},
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Referer": "https://weixin.sogou.com/",
}

# ─────────────────────────────────────────────
# 搜狗搜索层
# ─────────────────────────────────────────────

def _fetch_sogou_page(page: int, session: requests.Session, retries: int = 2, query: str = "") -> Optional[str]:
    """获取搜狗微信搜索结果页 HTML（使用共享 Session 保留 cookies）"""
    params = {"type": "2", "query": query or QUERY, "ie": "utf8", "page": page}
    for attempt in range(retries + 1):
        try:
            resp = session.get(SOGOU_SEARCH_URL, params=params, timeout=15)
            resp.encoding = "utf-8"
            if resp.status_code == 200:
                if "请输入验证码" in resp.text or "请完成验证" in resp.text:
                    logger.warning(f"搜狗第 {page} 页触发验证码，停止翻页")
                    return None
                return resp.text
            logger.warning(f"搜狗第 {page} 页返回 {resp.status_code}")
        except Exception as e:
            if attempt < retries:
                time.sleep(2)
            else:
                logger.warning(f"搜狗第 {page} 页获取失败: {e}")
    return None


def _parse_sogou_results(html: str) -> list[dict]:
    """从搜狗搜索结果页提取文章元数据（标题、摘要、日期、Sogou 链接）"""
    soup = BeautifulSoup(html, "lxml")
    articles = []

    items = soup.select("ul.news-list li") or soup.select(".news-list-content li")
    if not items:
        items = [li for li in soup.find_all("li") if li.find("h3")]

    for item in items:
        title_tag = item.find("h3")
        if not title_tag:
            continue
        a_tag = title_tag.find("a")
        if not a_tag:
            continue

        title = a_tag.get_text(strip=True)
        sogou_link = a_tag.get("href", "")
        if sogou_link and not sogou_link.startswith("http"):
            sogou_link = "https://weixin.sogou.com" + sogou_link

        # 摘要
        summary = ""
        p_tag = item.find("p", class_=re.compile(r"txt|summary|content|detail"))
        if not p_tag:
            p_tag = item.find("p")
        if p_tag:
            summary = p_tag.get_text(strip=True)

        # 日期：用正则从整个 li 文字中提取 YYYY-M-D
        full_text = item.get_text(separator=" ", strip=True)
        date_str = ""
        date_m = re.search(r"\d{4}-\d{1,2}-\d{1,2}", full_text)
        if date_m:
            date_str = date_m.group(0)

        # 公众号名
        account_name = QUERY
        sp_tag = item.find(class_=re.compile(r"s-p|account|author"))
        if sp_tag:
            a_in_sp = sp_tag.find("a")
            if a_in_sp:
                account_name = a_in_sp.get_text(strip=True) or account_name

        # 封面图
        img_url = ""
        img_tag = item.find("img")
        if img_tag:
            img_url = img_tag.get("src") or img_tag.get("data-src") or ""

        if title:
            articles.append({
                "title": title,
                "date": date_str,
                "summary": summary[:200],
                "account": account_name,
                "sogou_link": sogou_link,
                "img_url": img_url,
                "content": summary[:200],  # 先用摘要占位，后续替换为正文
                "wechat_url": sogou_link,  # 先用 sogou_link 占位
            })

    return articles


# ─────────────────────────────────────────────
# 微信文章层（需要共享 Session）
# ─────────────────────────────────────────────

def _extract_wechat_url_from_sogou_jump_page(html: str) -> str:
    """
    搜狗 /link 中间页常返回短 HTML：用 JS 把真实地址拆成多段 `url += '...'` 再 location.replace。
    无 HTTP 302，故必须从页面脚本里拼出 mp.weixin.qq.com 链接。
    """
    parts = re.findall(r"url\s*\+=\s*'([^']*)'", html, flags=re.I)
    if not parts:
        parts = re.findall(r'url\s*\+=\s*"([^"]*)"', html, flags=re.I)
    if not parts:
        return ""
    url = "".join(parts)
    url = url.replace("@", "")
    if "mp.weixin.qq.com" in url:
        # 去掉可能尾随的噪声字符
        url = url.split("#", 1)[0].strip()
        return url
    return ""


def _resolve_wechat_url(sogou_link: str, session: requests.Session) -> str:
    """
    用共享 Session（携带 Sogou cookies）请求搜狗跳转链，
    得到真实的 mp.weixin.qq.com/... URL。
    必须在同一 Session 获取搜索页之后立即调用，否则 cookies 可能失效。
    """
    try:
        resp = session.get(sogou_link, timeout=10, allow_redirects=True)
        final_url = resp.url
        if "mp.weixin.qq.com" in final_url:
            u = final_url.split("#", 1)[0].strip()
            logger.debug(f"跳转成功: {u[:60]}")
            return u
        # 中间页：JS 拼接 URL（多为 s?src=11&timestamp&signature 短时链，不宜给前端直链）
        js_url = _extract_wechat_url_from_sogou_jump_page(resp.text)
        if js_url:
            logger.debug(f"从 JS 拼接得到: {js_url[:70]}...")
            return js_url
        # 兜底：整页里直接出现的微信文章链
        m = re.search(r"https?://mp\.weixin\.qq\.com/s[^\s\"'<>]+", resp.text)
        if m:
            raw = m.group(0).rstrip("\\\"'")
            return raw.split("#", 1)[0].strip()
        logger.debug(f"未解析出微信 URL，最终 URL: {final_url[:80]}")
    except Exception as e:
        logger.debug(f"跟进跳转链接失败: {e}")
    return ""


def _fetch_article_content(wechat_url: str) -> str:
    """
    获取微信文章正文。
    mp.weixin.qq.com 文章无需登录，用桌面 UA 可直接访问。
    """
    try:
        resp = requests.get(wechat_url, headers=HEADERS, timeout=15)
        resp.encoding = "utf-8"
        if "环境异常" in resp.text or "请在微信客户端打开" in resp.text:
            logger.debug(f"文章被拦截: {wechat_url[:60]}")
            return ""
        soup = BeautifulSoup(resp.text, "lxml")
        content_el = (
            soup.select_one("#js_content")
            or soup.select_one(".rich_media_content")
            or soup.select_one("article")
        )
        if content_el:
            for tag in content_el.find_all(["script", "style"]):
                tag.decompose()
            text = content_el.get_text("\n", strip=True)
            text = re.sub(r"\n{3,}", "\n\n", text)
            return text[:2000]
    except Exception as e:
        logger.debug(f"获取文章正文失败: {e}")
    return ""


# ─────────────────────────────────────────────
# 主爬取流程
# ─────────────────────────────────────────────

def _scrape_one_query(
    query: str,
    max_pages: int = MAX_PAGES,
    fetch_content: bool = True,
    label: str = "",
) -> list[dict]:
    """
    爬取单个关键词的公众号文章。
    用共享 Session 在每页搜索结果拿到后立即跟进跳转链接。
    """
    tag = label or query
    logger.info(f"开始爬取「{tag}」文章，最多 {max_pages} 页...")
    all_articles: list[dict] = []

    session = requests.Session()
    session.headers.update(HEADERS)

    for page in range(1, max_pages + 1):
        html = _fetch_sogou_page(page, session=session, query=query)
        if not html:
            logger.info(f"「{tag}」第 {page} 页获取失败或触发验证码，停止")
            break

        articles = _parse_sogou_results(html)
        if not articles:
            logger.info(f"「{tag}」第 {page} 页无结果，停止")
            break

        for a in articles:
            a["search_query"] = query

        logger.info(f"「{tag}」第 {page} 页解析 {len(articles)} 篇，立即跟进跳转链接...")

        if fetch_content:
            for article in articles:
                sogou_link = article.get("sogou_link", "")
                if sogou_link and "weixin.sogou.com" in sogou_link:
                    wx_url = _resolve_wechat_url(sogou_link, session=session)
                    if wx_url:
                        article["wechat_url"] = wx_url
                    time.sleep(0.55)

        all_articles.extend(articles)
        logger.info(f"「{tag}」第 {page} 页完成，累计 {len(all_articles)} 篇")

        if page < max_pages:
            time.sleep(1.5)

    return all_articles


def scrape_healthyu_articles(max_pages: int = MAX_PAGES, fetch_content: bool = True) -> list[dict]:
    """向后兼容：只爬 HealthyUunnc。"""
    return _scrape_one_query(QUERY, max_pages=max_pages, fetch_content=fetch_content, label="HealthyUunnc")


def scrape_multi_query_articles(
    queries: list[dict] | None = None,
    fetch_content: bool = True,
) -> list[dict]:
    """
    多关键词爬取，合并去重，统一抓取正文。
    queries 格式: [{"query": "...", "label": "...", "max_pages": 3}, ...]
    """
    if queries is None:
        queries = SEARCH_QUERIES

    all_articles: list[dict] = []
    for q in queries:
        query_str = q["query"]
        label = q.get("label", query_str)
        mp = q.get("max_pages", 3)
        batch = _scrape_one_query(query_str, max_pages=mp, fetch_content=False, label=label)
        all_articles.extend(batch)
        time.sleep(1.0)

    seen: set[str] = set()
    unique: list[dict] = []
    for a in all_articles:
        if a["title"] not in seen:
            seen.add(a["title"])
            unique.append(a)

    if fetch_content:
        wx_list = [a for a in unique if "mp.weixin.qq.com" in a.get("wechat_url", "")]
        logger.info(f"共 {len(wx_list)} 篇已有微信真实链接，开始抓取正文...")
        for i, article in enumerate(wx_list):
            content = _fetch_article_content(article["wechat_url"])
            if content:
                article["content"] = content
                logger.info(
                    f"  [{i+1}/{len(wx_list)}] {article['title'][:25]}... "
                    f"正文 {len(content)} 字"
                )
            else:
                logger.info(f"  [{i+1}/{len(wx_list)}] {article['title'][:25]}... 正文获取失败，保留摘要")
            time.sleep(0.6)

    logger.info(
        f"多关键词爬取完成，共 {len(unique)} 篇"
        f"（其中 {sum(1 for a in unique if 'mp.weixin.qq.com' in a.get('wechat_url',''))} 篇有真实微信链接）"
    )
    return unique


# ─────────────────────────────────────────────
# 缓存管理
# ─────────────────────────────────────────────

def refresh_wechat_cache(fetch_content: bool = True) -> list[dict]:
    """重新爬取所有关键词并更新缓存文件"""
    articles = scrape_multi_query_articles(fetch_content=fetch_content)
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "updated_at": datetime.now().isoformat(),
        "count": len(articles),
        "queries": [q["query"] for q in SEARCH_QUERIES],
        "articles": articles,
    }
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    logger.info(f"缓存已更新：{CACHE_FILE}，共 {len(articles)} 篇")
    return articles


def repair_wechat_urls_from_cache() -> list[dict]:
    """
    不重爬搜狗列表，仅对已缓存条目重新请求搜狗跳转页，从 JS 拼接页解析 mp 链（供正文抓取等）。
    前端「阅读原文」应走 /api/articles/open-sogou 使用 sogou_link，勿直链缓存中的短时 mp 参数。
    """
    if not CACHE_FILE.exists():
        return refresh_wechat_cache(fetch_content=True)

    with open(CACHE_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    articles: list[dict] = data.get("articles", [])

    session = requests.Session()
    session.headers.update(HEADERS)
    if not _fetch_sogou_page(1, session=session):
        logger.warning("repair_wechat_urls: 无法获取搜狗搜索页，跳过修复")
        return articles

    fixed = 0
    n = 0
    for article in articles:
        w = article.get("wechat_url") or ""
        if "mp.weixin.qq.com" in w:
            continue
        sl = article.get("sogou_link") or ""
        if not sl or "weixin.sogou.com" not in sl:
            continue
        # 周期性重访搜索页，降低长时间连续请求 /link 被限速的概率
        if n > 0 and n % 12 == 0:
            _fetch_sogou_page(1, session=session)
            time.sleep(1.0)
        wx_url = _resolve_wechat_url(sl, session=session)
        if wx_url:
            article["wechat_url"] = wx_url
            fixed += 1
        n += 1
        time.sleep(0.55)

    data["articles"] = articles
    data["updated_at"] = datetime.now().isoformat()
    data["count"] = len(articles)
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    logger.info(f"repair_wechat_urls: 已补全 {fixed} 条微信原文链接")
    return articles


def get_cached_articles() -> list[dict]:
    """读取缓存，不存在时触发爬取"""
    if CACHE_FILE.exists():
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data.get("articles", [])
        except Exception:
            pass
    return refresh_wechat_cache()
