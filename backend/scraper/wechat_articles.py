"""
微信公众号文章爬虫（多关键词版）
数据来源：搜狗微信搜索（weixin.sogou.com）
流程：搜狗搜索列表 → 同 Session 跟进跳转链接 → 微信文章原页面正文

支持配置多组搜索关键词，分别爬取后合并缓存。
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlparse, urlunparse

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# 单篇微信正文最大保留字数（绝大多数推文远低于此；活动日期一般在全文前中段也会出现）
_MAX_MP_ARTICLE_TEXT_CHARS = 300_000

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
    {"query": "宁波诺丁汉大学学生事务", "label": "宁波诺丁汉大学学生事务", "max_pages": 3},
    {"query": "宁波诺丁汉大学理工学院", "label": "宁波诺丁汉大学理工学院", "max_pages": 3},
    {"query": "宁波诺丁汉大学图书馆", "label": "宁波诺丁汉大学图书馆", "max_pages": 3},
]

# 用户在前端添加的搜狗搜索关键词（与内置列表合并后爬取）
CUSTOM_QUERIES_FILE = Path(__file__).parent.parent / "data" / "wechat_custom_queries.json"


def load_custom_queries() -> list[dict[str, Any]]:
    """读取用户自定义关键词；每项含 query, label, max_pages。"""
    if not CUSTOM_QUERIES_FILE.exists():
        return []
    try:
        with open(CUSTOM_QUERIES_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        raw = data.get("items", [])
        if not isinstance(raw, list):
            return []
        out: list[dict[str, Any]] = []
        for it in raw:
            if not isinstance(it, dict):
                continue
            q = str(it.get("query", "")).strip()
            if not q:
                continue
            lb = str(it.get("label", "") or q).strip()[:64] or q
            try:
                mp = int(it.get("max_pages", 3))
            except (TypeError, ValueError):
                mp = 3
            mp = min(10, max(1, mp))
            out.append({"query": q, "label": lb, "max_pages": mp})
        return out
    except Exception as e:
        logger.warning("读取 wechat_custom_queries.json 失败: %s", e)
        return []


def save_custom_queries(items: list[dict[str, Any]]) -> None:
    CUSTOM_QUERIES_FILE.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "updated_at": datetime.now().isoformat(),
        "items": items,
    }
    with open(CUSTOM_QUERIES_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def add_custom_wechat_query(query: str, label: str = "", max_pages: int = 3) -> list[dict[str, Any]]:
    """新增或更新一条自定义关键词（同 query 则更新 label/max_pages）。"""
    q = (query or "").strip()
    if len(q) < 1:
        raise ValueError("关键词不能为空")
    if len(q) > 80:
        raise ValueError("关键词过长（最多 80 字）")
    mp = min(10, max(1, int(max_pages)))
    lb = (label or "").strip()[:64] or q
    items = load_custom_queries()
    for it in items:
        if str(it.get("query", "")).strip() == q:
            it["label"] = lb
            it["max_pages"] = mp
            save_custom_queries(items)
            return items
    items.append({"query": q, "label": lb, "max_pages": mp})
    save_custom_queries(items)
    return items


def remove_custom_wechat_query(query: str) -> list[dict[str, Any]]:
    q = (query or "").strip()
    items = [it for it in load_custom_queries() if str(it.get("query", "")).strip() != q]
    save_custom_queries(items)
    return items


def get_effective_search_queries() -> list[dict[str, Any]]:
    """内置关键词 + 自定义关键词合并；同 query 只保留内置那条。"""
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for q in SEARCH_QUERIES:
        k = str(q.get("query", "")).strip()
        if not k or k in seen:
            continue
        seen.add(k)
        out.append(
            {
                "query": k,
                "label": str(q.get("label", k) or k),
                "max_pages": min(10, max(1, int(q.get("max_pages", 3)))),
            }
        )
    for it in load_custom_queries():
        k = str(it.get("query", "")).strip()
        if not k or k in seen:
            continue
        seen.add(k)
        out.append(
            {
                "query": k,
                "label": str(it.get("label", k) or k),
                "max_pages": min(10, max(1, int(it.get("max_pages", 3)))),
            }
        )
    return out


def _sogou_seed_query() -> str:
    """打开搜狗首页拿 cookie 时用的首个搜索词。"""
    eq = get_effective_search_queries()
    if eq:
        return str(eq[0]["query"])
    return QUERY


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Referer": "https://weixin.sogou.com/",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}


def _get_sogou_headers() -> dict:
    """构建请求头，若配置了 SOGOU_COOKIE 则注入，降低 antispider 触发率。"""
    h = {**HEADERS}
    cookie = os.getenv("SOGOU_COOKIE", "").strip()
    if cookie:
        h["Cookie"] = cookie
        logger.debug("搜狗请求已注入 Cookie（%d 字符）", len(cookie))
    else:
        logger.debug("未配置 SOGOU_COOKIE，以匿名方式请求搜狗")
    return h


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


def _parse_sogou_results(html: str, fallback_account: str = "") -> list[dict]:
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
        account_name = fallback_account or QUERY
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
        logger.warning(f"未解析出微信 URL，最终 URL: {final_url[:80]}, 状态码: {resp.status_code}")
    except Exception as e:
        logger.warning(f"跟进跳转链接失败: {e}")
    return ""


def _strip_mp_to_path_only(url: str) -> str:
    """若已是 /s/xxx 路径形态，去掉查询串里易过期的签名参数。"""
    try:
        p = urlparse(url)
        if not p.netloc.endswith("mp.weixin.qq.com"):
            return url
        if not p.path.startswith("/s/") or len(p.path) < 6:
            return url
        q = (p.query or "").lower()
        if "signature" in q or "src=11" in q:
            return urlunparse(("https", "mp.weixin.qq.com", p.path, "", "", ""))
        return url.split("#")[0].strip()
    except Exception:
        return url


def _extract_canonical_mp_from_html(html: str) -> str:
    """从微信正文 HTML 取出 canonical / og:url 等永久链接。"""
    if not html or "链接已过期" in html or "链接不存在" in html:
        return ""
    try:
        soup = BeautifulSoup(html, "lxml")
        link = soup.select_one('link[rel="canonical"]')
        if link and link.get("href"):
            u = link["href"].strip().replace("&amp;", "&")
            if "mp.weixin.qq.com" in u and "/s/" in u and "signature" not in u.lower():
                return _strip_mp_to_path_only(u)
        og = soup.select_one('meta[property="og:url"]')
        if og and og.get("content"):
            u = og["content"].strip().replace("&amp;", "&")
            if "mp.weixin.qq.com" in u and "/s/" in u and "signature" not in u.lower():
                return _strip_mp_to_path_only(u)
        m = re.search(
            r'msg_link\s*[=:]\s*["\'](https://mp\.weixin\.qq\.com/s[^"\']+)["\']',
            html,
            re.I,
        )
        if m:
            u = m.group(1).replace("&amp;", "&")
            if "signature" not in u.lower():
                return _strip_mp_to_path_only(u)
    except Exception as e:
        logger.debug("_extract_canonical_mp_from_html: %s", e)
    return ""


def _upgrade_signed_mp_url(mp_url: str, session: requests.Session) -> str:
    """
    短时链 s?src=11&signature=... 给用户几乎必过期。
    服务端立刻 GET 该页，从 HTML 提取 canonical 永久链接。
    """
    if not mp_url or "mp.weixin.qq.com" not in mp_url:
        return mp_url
    u0 = mp_url.split("#")[0].strip()
    lower = u0.lower()
    if "signature" not in lower and "src=11" not in lower:
        return _strip_mp_to_path_only(u0)

    hdrs = {**HEADERS, "Referer": "https://weixin.sogou.com/"}
    try:
        r = session.get(u0, timeout=20, allow_redirects=True, headers=hdrs)
        r.encoding = r.apparent_encoding or "utf-8"
        final = (r.url or "").split("#")[0].strip()
        if final and "mp.weixin.qq.com" in final:
            pq = urlparse(final)
            fq = (pq.query or "").lower()
            if pq.path.startswith("/s/") and "signature" not in fq and "src=11" not in fq:
                return _strip_mp_to_path_only(final)
        canon = _extract_canonical_mp_from_html(r.text)
        if canon:
            return canon
        stripped = _strip_mp_to_path_only(final or u0)
        if stripped != u0 and "signature" not in stripped.lower():
            return stripped
    except Exception as e:
        logger.warning("_upgrade_signed_mp_url 请求失败: %s", e)
    return u0


def _parse_publish_date(html: str) -> str:
    """从 mp.weixin.qq.com 页面 HTML 提取发布日期 YYYY-MM-DD，失败返回空串。"""
    if not html:
        return ""
    # 方法 1: JS 变量 var ct = "1620000000" 或 var create_time = "..."
    for pat in (
        r'var\s+(?:ct|create_time|oriCreateTime)\s*=\s*["\'](\d{10,13})["\']',
        r'"createTime"\s*:\s*["\']?(\d{10,13})["\']?',
        r'"create_time"\s*:\s*["\']?(\d{10,13})["\']?',
    ):
        m = re.search(pat, html)
        if m:
            try:
                ts = int(m.group(1))
                if ts > 9_999_999_999:
                    ts //= 1000
                dt = datetime.utcfromtimestamp(ts)
                if 2010 <= dt.year <= 2100:
                    return dt.strftime("%Y-%m-%d")
            except (ValueError, OSError):
                pass
    # 方法 2: meta 标签
    m2 = re.search(
        r'property\s*=\s*"article:published_time"\s+content\s*=\s*"([^"]+)"',
        html,
    )
    if m2:
        raw = m2.group(1).strip()[:10]
        dm = re.match(r"(\d{4})-(\d{1,2})-(\d{1,2})", raw)
        if dm and 2010 <= int(dm.group(1)) <= 2100:
            return f"{int(dm.group(1)):04d}-{int(dm.group(2)):02d}-{int(dm.group(3)):02d}"
    # 方法 3: id="publish_time" 元素
    m3 = re.search(r'id="publish_time"[^>]*>([^<]+)<', html)
    if m3:
        raw = m3.group(1).strip()
        dm = re.search(r"(\d{4})-(\d{1,2})-(\d{1,2})", raw)
        if dm and 2010 <= int(dm.group(1)) <= 2100:
            return f"{int(dm.group(1)):04d}-{int(dm.group(2)):02d}-{int(dm.group(3)):02d}"
    return ""


def _fetch_article_content(wechat_url: str) -> tuple[str, str]:
    """
    获取微信文章正文与发布日期。
    返回 (正文文本, publish_date YYYY-MM-DD)。
    """
    try:
        resp = requests.get(wechat_url, headers=HEADERS, timeout=15)
        resp.encoding = "utf-8"
        html = resp.text
        if "环境异常" in html or "请在微信客户端打开" in html:
            logger.debug(f"文章被拦截: {wechat_url[:60]}")
            return "", ""
        pub_date = _parse_publish_date(html)
        soup = BeautifulSoup(html, "lxml")
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
            if len(text) > _MAX_MP_ARTICLE_TEXT_CHARS:
                logger.debug(
                    "正文过长已截断: %d -> %d 字",
                    len(text),
                    _MAX_MP_ARTICLE_TEXT_CHARS,
                )
                text = text[:_MAX_MP_ARTICLE_TEXT_CHARS]
            return text, pub_date
        return "", pub_date
    except Exception as e:
        logger.debug(f"获取文章正文失败: {e}")
    return "", ""


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
    session.headers.update(_get_sogou_headers())

    for page in range(1, max_pages + 1):
        html = _fetch_sogou_page(page, session=session, query=query)
        if not html:
            logger.info(f"「{tag}」第 {page} 页获取失败或触发验证码，停止")
            break

        articles = _parse_sogou_results(html, fallback_account=tag)
        if not articles:
            logger.info(f"「{tag}」第 {page} 页无结果，停止")
            break

        for a in articles:
            a["search_query"] = query

        logger.info(f"「{tag}」第 {page} 页解析 {len(articles)} 篇，立即跟进跳转链接...")

        if fetch_content:
            resolved = 0
            failed = 0
            for article in articles:
                sogou_link = article.get("sogou_link", "")
                if sogou_link and "weixin.sogou.com" in sogou_link:
                    wx_url = _resolve_wechat_url(sogou_link, session=session)
                    if wx_url:
                        article["wechat_url"] = wx_url
                        resolved += 1
                    else:
                        failed += 1
                    time.sleep(0.55)
            logger.info(
                f"「{tag}」第 {page} 页跳转解析: {resolved} 成功, {failed} 失败"
            )

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
        queries = get_effective_search_queries()

    all_articles: list[dict] = []
    for q in queries:
        query_str = q["query"]
        label = q.get("label", query_str)
        mp = q.get("max_pages", 3)
        # fetch_content=True：在同一 Session（搜索页 cookie 仍有效时）就地解析跳转链接
        batch = _scrape_one_query(query_str, max_pages=mp, fetch_content=True, label=label)
        all_articles.extend(batch)
        time.sleep(1.0)

    seen: set[str] = set()
    unique: list[dict] = []
    for a in all_articles:
        if a["title"] not in seen:
            seen.add(a["title"])
            unique.append(a)

    # 就地解析后，已有 mp 链的文章数量
    mp_count = sum(1 for a in unique if "mp.weixin.qq.com" in a.get("wechat_url", ""))
    logger.info(f"合并去重后 {len(unique)} 篇，其中 {mp_count} 篇已有微信真实链接")

    if fetch_content:
        wx_list = [
            a for a in unique
            if "mp.weixin.qq.com" in a.get("wechat_url", "")
            and len(a.get("content") or "") < 300
        ]
        if wx_list:
            logger.info(f"开始抓取 {len(wx_list)} 篇尚无完整正文的文章...")
            for i, article in enumerate(wx_list):
                content, pub_date = _fetch_article_content(article["wechat_url"])
                if content:
                    article["content"] = content
                if pub_date:
                    article["publish_date"] = pub_date
                if content:
                    logger.info(
                        f"  [{i+1}/{len(wx_list)}] {article['title'][:25]}... "
                        f"正文 {len(content)} 字, 发布 {pub_date or '未知'}"
                    )
                else:
                    logger.info(f"  [{i+1}/{len(wx_list)}] {article['title'][:25]}... 正文获取失败，保留摘要")
                time.sleep(0.6)

    logger.info(
        f"多关键词爬取完成，共 {len(unique)} 篇"
        f"（其中 {sum(1 for a in unique if 'mp.weixin.qq.com' in a.get('wechat_url',''))} 篇有真实微信链接，"
        f"{sum(1 for a in unique if len(a.get('content','')) > 300)} 篇有完整正文）"
    )
    return unique


# ─────────────────────────────────────────────
# 缓存管理
# ─────────────────────────────────────────────

def refresh_wechat_cache(fetch_content: bool = True) -> list[dict]:
    """重新爬取所有关键词并更新缓存文件"""
    effective = get_effective_search_queries()
    articles = scrape_multi_query_articles(queries=effective, fetch_content=fetch_content)
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "updated_at": datetime.now().isoformat(),
        "count": len(articles),
        "queries": [q["query"] for q in effective],
        "builtin_queries": [q["query"] for q in SEARCH_QUERIES],
        "custom_queries": load_custom_queries(),
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
    session.headers.update(_get_sogou_headers())
    if not _fetch_sogou_page(1, session=session, query=_sogou_seed_query()):
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
            _fetch_sogou_page(1, session=session, query=_sogou_seed_query())
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


def resolve_fresh_wechat_url_from_sogou(sogou_link: str) -> str:
    """
    用户点击「阅读原文」时调用：新建 Session，先访问搜狗搜索页拿到 cookie，
    再跟进 sogou_link，解析当前可用的 mp.weixin.qq.com URL。
    避免仅 302 到过期 token 的 sogou 链或缓存里已失效的短时 mp 链。
    """
    link = (sogou_link or "").strip()
    if not link or "weixin.sogou.com" not in link:
        return ""
    session = requests.Session()
    session.headers.update(_get_sogou_headers())
    q0 = _sogou_seed_query()
    if not _fetch_sogou_page(1, session=session, query=q0):
        _fetch_sogou_page(1, session=session, query=QUERY)
    time.sleep(0.25)
    try:
        wx = _resolve_wechat_url(link, session=session)
        if wx and "mp.weixin.qq.com" in wx:
            wx = wx.split("#", 1)[0].strip()
            wx = _upgrade_signed_mp_url(wx, session)
            logger.info("open-sogou 最终跳转: %s", wx[:96])
            return wx
    except Exception as e:
        logger.warning("resolve_fresh_wechat_url_from_sogou 失败: %s", e)
    return ""


def proxy_wechat_html_from_sogou(sogou_link: str) -> str:
    """
    代理模式：服务端获取微信文章完整 HTML 并返回。
    浏览器直接展示此 HTML，绕过微信对 Referer 的校验。
    """
    link = (sogou_link or "").strip()
    if not link or "weixin.sogou.com" not in link:
        return ""
    session = requests.Session()
    session.headers.update(_get_sogou_headers())
    q0 = _sogou_seed_query()
    if not _fetch_sogou_page(1, session=session, query=q0):
        _fetch_sogou_page(1, session=session, query=QUERY)
    time.sleep(0.25)
    try:
        wx = _resolve_wechat_url(link, session=session)
        if not wx or "mp.weixin.qq.com" not in wx:
            logger.warning("proxy: 未能解析到微信链接")
            return ""
        wx = wx.split("#", 1)[0].strip()
        hdrs = {**HEADERS, "Referer": "https://weixin.sogou.com/"}
        r = session.get(wx, timeout=20, allow_redirects=True, headers=hdrs)
        r.encoding = r.apparent_encoding or "utf-8"
        if r.status_code == 200 and len(r.text) > 500:
            html = r.text
            html = html.replace(
                "</head>",
                '<base target="_blank"><meta name="referrer" content="never"></head>',
            )
            logger.info("proxy: 成功获取文章 HTML (%d bytes)", len(html))
            return html
        logger.warning("proxy: 文章页返回 %d, 长度 %d", r.status_code, len(r.text))
    except Exception as e:
        logger.warning("proxy_wechat_html_from_sogou 失败: %s", e)
    return ""


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
