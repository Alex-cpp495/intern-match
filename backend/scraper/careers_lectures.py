"""
UNNC Careers 就业讲座 / 活动爬虫
数据来源：https://careers.nottingham.edu.cn/lecture
爬取内容：活动标题、日期时间、地点、状态、详情页链接、详情正文、主办方
仅保留「活动未举办」的条目（即尚未举办的活动），用于日历融合与推荐。
"""

from __future__ import annotations

import base64
import json
import logging
import re
import time
import zlib
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Optional

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

BASE_URL = "https://careers.nottingham.edu.cn"
LIST_URL = BASE_URL + "/lecture"
PAGE_URL_TPL = BASE_URL + "/lecture/index/ddo/careers.nottingham.edu.cn/domain/careersatunnc/page/{page}"
CACHE_FILE = Path(__file__).parent.parent / "data" / "careers_lectures.json"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}

MAX_PAGES = 25
UPCOMING_STATUS = "活动未举办"


def _fetch_list_page(page: int, retries: int = 2) -> Optional[str]:
    url = LIST_URL if page == 1 else PAGE_URL_TPL.format(page=page)
    for attempt in range(retries + 1):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=15)
            resp.encoding = "utf-8"
            if resp.status_code == 200:
                return resp.text
            logger.warning("讲座列表第 %d 页返回 %d", page, resp.status_code)
        except Exception as e:
            if attempt < retries:
                time.sleep(1.5)
            else:
                logger.warning("讲座列表第 %d 页获取失败: %s", page, e)
    return None


def _parse_time_field(raw: str) -> dict:
    """
    解析 careers 页面 .span4 的 title 属性。
    格式示例：
      "2026-03-29  10:00-11:30 （周日）"
      "2026-04-07 11:00 ~ 2026-04-09 20:00"
    """
    raw = raw.strip()
    result = {"date_start": "", "date_end": "", "time_start": "", "time_end": ""}

    # 跨日格式：2026-04-07 11:00 ~ 2026-04-09 20:00
    m_range = re.match(
        r"(\d{4}-\d{2}-\d{2})\s+(\d{1,2}:\d{2})\s*[~～]\s*(\d{4}-\d{2}-\d{2})\s+(\d{1,2}:\d{2})",
        raw,
    )
    if m_range:
        result["date_start"] = m_range.group(1)
        result["time_start"] = m_range.group(2)
        result["date_end"] = m_range.group(3)
        result["time_end"] = m_range.group(4)
        return result

    # 单日格式：2026-03-29  10:00-11:30 （周日）
    m_single = re.match(r"(\d{4}-\d{2}-\d{2})\s+(\d{1,2}:\d{2})-(\d{1,2}:\d{2})", raw)
    if m_single:
        result["date_start"] = m_single.group(1)
        result["date_end"] = m_single.group(1)
        result["time_start"] = m_single.group(2)
        result["time_end"] = m_single.group(3)
        return result

    # 兜底：至少提取日期
    m_date = re.search(r"(\d{4}-\d{2}-\d{2})", raw)
    if m_date:
        result["date_start"] = m_date.group(1)
        result["date_end"] = m_date.group(1)
    m_time = re.search(r"(\d{1,2}:\d{2})", raw)
    if m_time:
        result["time_start"] = m_time.group(1)

    return result


def _parse_list_page(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "lxml")
    items = soup.select("ul.infoList.teachinList")
    lectures: list[dict] = []
    for ul in items:
        a_tag = ul.select_one("li.span1 a")
        if not a_tag:
            continue
        title = (a_tag.get("title") or a_tag.get_text(strip=True)).strip()
        href = a_tag.get("href", "")
        link = href if href.startswith("http") else BASE_URL + href

        loc_el = ul.select_one("li.span3")
        location = loc_el.get_text(strip=True) if loc_el else ""

        time_el = ul.select_one("li.span4")
        time_raw = (time_el.get("title") or time_el.get_text(strip=True)) if time_el else ""
        time_info = _parse_time_field(time_raw)

        status_el = ul.select_one("li.span5")
        status = status_el.get_text(strip=True) if status_el else ""

        lecture_id = ""
        id_match = re.search(r"/id/(\d+)", href)
        if id_match:
            lecture_id = id_match.group(1)

        lectures.append({
            "id": lecture_id,
            "title": title,
            "location": location,
            "link": link,
            "status": status,
            "description": "",
            "organizer": "",
            **time_info,
        })
    return lectures


def _decode_js_content(html_text: str) -> str:
    """
    解码详情页中 JS 嵌入的 Base64 + zlib 压缩内容。
    页面使用 Base64.decode(unzip("...").substr(N1)).substr(N2) 异步渲染正文。
    """
    soup = BeautifulSoup(html_text, "lxml")
    for script in soup.find_all("script"):
        s = script.string
        if not s:
            continue
        m = re.search(r'unzip\("([A-Za-z0-9+/=]+)"\)', s)
        if not m:
            continue
        encoded = m.group(1)
        subs = re.findall(r"\.substr\((\d+)\)", s)
        try:
            raw = base64.b64decode(encoded)
            decompressed = zlib.decompress(raw, 15).decode("utf-8", errors="replace")
            s1 = int(subs[0]) if subs else 0
            after_sub1 = decompressed[s1:]
            decoded_bytes = base64.b64decode(after_sub1)
            html_content = decoded_bytes.decode("utf-8", errors="replace")
            s2 = int(subs[1]) if len(subs) > 1 else 0
            return html_content[s2:]
        except Exception:
            continue
    return ""


def _fetch_detail(url: str) -> dict:
    """获取讲座详情页的描述和主办方。"""
    extra: dict = {"description": "", "organizer": ""}
    try:
        resp = requests.get(url, headers=HEADERS, timeout=12)
        resp.encoding = "utf-8"

        soup = BeautifulSoup(resp.text, "lxml")

        for li in soup.select("ul.infoUl li"):
            text = li.get_text(strip=True)
            if "主办" in text:
                extra["organizer"] = text.replace("主办方：", "").replace("主办：", "").strip()
                break

        # 解码 JS 异步渲染的正文内容
        decoded_html = _decode_js_content(resp.text)
        if decoded_html:
            desc_text = BeautifulSoup(decoded_html, "lxml").get_text(" ", strip=True)
            extra["description"] = desc_text[:800]
        else:
            content_div = soup.select_one(".vContent .aContent")
            if content_div:
                text = content_div.get_text(" ", strip=True)
                extra["description"] = text[:800]
    except Exception as e:
        logger.debug("讲座详情页获取失败 %s: %s", url, e)
    return extra


def scrape_careers_lectures(
    max_pages: int = MAX_PAGES,
    only_upcoming: bool = True,
    fetch_details: bool = True,
) -> list[dict]:
    """
    爬取 careers 讲座列表。
    - only_upcoming=True 时仅保留状态为「活动未举办」的条目。
    - fetch_details=True 时并发获取详情页描述与主办方。
    """
    logger.info("开始爬取 Careers 讲座，最多 %d 页...", max_pages)
    all_lectures: list[dict] = []

    for page in range(1, max_pages + 1):
        html = _fetch_list_page(page)
        if not html:
            logger.warning("第 %d 页获取失败，停止", page)
            break
        lectures = _parse_list_page(html)
        if not lectures:
            logger.info("第 %d 页无讲座数据，停止", page)
            break
        all_lectures.extend(lectures)
        logger.info("第 %d 页获取到 %d 条讲座，累计 %d 条", page, len(lectures), len(all_lectures))

        # 如果本页全是已举办，后续页也不用爬了
        if only_upcoming and all(l["status"] != UPCOMING_STATUS for l in lectures):
            logger.info("第 %d 页全部已举办，停止翻页", page)
            break
        time.sleep(0.8)

    # 去重
    seen: set[str] = set()
    unique: list[dict] = []
    for lec in all_lectures:
        key = lec.get("id") or (lec["title"] + lec["date_start"])
        if key not in seen:
            seen.add(key)
            unique.append(lec)

    if only_upcoming:
        unique = [l for l in unique if l["status"] == UPCOMING_STATUS]

    # 并发获取详情
    if fetch_details and unique:
        logger.info("开始获取 %d 条讲座详情...", len(unique))
        with ThreadPoolExecutor(max_workers=4) as pool:
            futures = {
                pool.submit(_fetch_detail, lec["link"]): i
                for i, lec in enumerate(unique) if lec.get("link")
            }
            for future in as_completed(futures):
                idx = futures[future]
                try:
                    detail = future.result()
                    unique[idx]["description"] = detail.get("description", "")
                    unique[idx]["organizer"] = detail.get("organizer", "")
                except Exception:
                    pass

    logger.info("Careers 讲座爬取完成，共 %d 条%s", len(unique), "（仅未举办）" if only_upcoming else "")
    return unique


# ─────────────────────────────────────────
# 缓存管理
# ─────────────────────────────────────────

def refresh_careers_cache(
    only_upcoming: bool = True,
    fetch_details: bool = True,
) -> list[dict]:
    lectures = scrape_careers_lectures(
        only_upcoming=only_upcoming,
        fetch_details=fetch_details,
    )
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "updated_at": datetime.now().isoformat(),
        "count": len(lectures),
        "lectures": lectures,
    }
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    logger.info("Careers 讲座缓存已更新：%s，共 %d 条", CACHE_FILE, len(lectures))
    return lectures


def get_cached_lectures() -> list[dict]:
    if CACHE_FILE.exists():
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data.get("lectures", [])
        except Exception:
            pass
    return refresh_careers_cache()
