"""
UNNC Careers 招聘会爬虫
数据来源：https://careers.nottingham.edu.cn/jobfair
页面通过 Base64+zlib 压缩嵌入 JS，需先解码再解析 HTML。
"""

from __future__ import annotations

import base64
import json
import logging
import re
import time
import zlib
from datetime import datetime
from pathlib import Path
from typing import Optional

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

BASE_URL = "https://careers.nottingham.edu.cn"
LIST_URL = BASE_URL + "/jobfair"
PAGE_URL_TPL = (
    BASE_URL
    + "/jobfair/index/ddo/careers.nottingham.edu.cn/domain/careersatunnc/page/{page}"
)
CACHE_FILE = Path(__file__).parent.parent / "data" / "careers_jobfairs.json"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}

MAX_PAGES = 5


def _fetch_page(page: int, retries: int = 2) -> Optional[str]:
    url = LIST_URL if page == 1 else PAGE_URL_TPL.format(page=page)
    for attempt in range(retries + 1):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=15)
            resp.encoding = "utf-8"
            if resp.status_code == 200:
                return resp.text
            logger.warning("招聘会列表第 %d 页返回 %d", page, resp.status_code)
        except Exception as e:
            if attempt < retries:
                time.sleep(1.5)
            else:
                logger.warning("招聘会列表第 %d 页获取失败: %s", page, e)
    return None


def _decode_js_content(html_text: str) -> str:
    """解码页面中 Base64 + zlib 压缩的嵌入内容。"""
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


def _parse_time_field(raw: str) -> dict:
    """解析招聘会的时间文本。"""
    raw = re.sub(r"\s+", " ", raw).strip()
    result = {"date_start": "", "date_end": "", "time_start": "", "time_end": ""}

    # 跨日：2026-03-11 — 2026-03-26
    m_range = re.match(
        r"(\d{4}-\d{2}-\d{2})\s*[—~～\-]\s*(\d{4}-\d{2}-\d{2})", raw
    )
    if m_range:
        result["date_start"] = m_range.group(1)
        result["date_end"] = m_range.group(2)
        return result

    # 单日+时间：2026-04-22 13:30-17:00 （周三）
    m_single = re.match(
        r"(\d{4}-\d{2}-\d{2})\s+(\d{1,2}:\d{2})-(\d{1,2}:\d{2})", raw
    )
    if m_single:
        result["date_start"] = m_single.group(1)
        result["date_end"] = m_single.group(1)
        result["time_start"] = m_single.group(2)
        result["time_end"] = m_single.group(3)
        return result

    # 单日仅时间：2024-09-07 14:00 （周六）
    m_dt = re.match(r"(\d{4}-\d{2}-\d{2})\s+(\d{1,2}:\d{2})", raw)
    if m_dt:
        result["date_start"] = m_dt.group(1)
        result["date_end"] = m_dt.group(1)
        result["time_start"] = m_dt.group(2)
        return result

    # 兜底
    m_date = re.search(r"(\d{4}-\d{2}-\d{2})", raw)
    if m_date:
        result["date_start"] = m_date.group(1)
        result["date_end"] = m_date.group(1)

    return result


def _parse_list_html(decoded_html: str) -> list[dict]:
    soup = BeautifulSoup(decoded_html, "lxml")
    fairs: list[dict] = []
    for ul in soup.select("ul.infoList.jobfairList"):
        title_a = ul.select_one("li.span9 a")
        if not title_a:
            continue
        title = (title_a.get("title") or title_a.get_text(strip=True)).strip()
        href = title_a.get("href", "")
        link = href if href.startswith("http") else BASE_URL + href

        loc_el = ul.select_one("li.span4")
        location = loc_el.get_text(strip=True) if loc_el else ""

        time_el = ul.select_one("li.span8")
        time_raw = time_el.get_text(strip=True) if time_el else ""
        time_info = _parse_time_field(time_raw)

        status_el = ul.select_one("span.status-text")
        status = status_el.get_text(strip=True) if status_el else ""

        fair_id = ""
        id_match = re.search(r"/id/(\d+)", href)
        if id_match:
            fair_id = id_match.group(1)

        fairs.append(
            {
                "id": fair_id,
                "title": title,
                "location": location,
                "link": link,
                "status": status,
                "type": "jobfair",
                **time_info,
            }
        )
    return fairs


def scrape_careers_jobfairs(max_pages: int = MAX_PAGES) -> list[dict]:
    logger.info("开始爬取 Careers 招聘会，最多 %d 页...", max_pages)
    all_fairs: list[dict] = []

    for page in range(1, max_pages + 1):
        html = _fetch_page(page)
        if not html:
            logger.warning("第 %d 页获取失败，停止", page)
            break
        decoded = _decode_js_content(html)
        if not decoded:
            logger.warning("第 %d 页解码失败，停止", page)
            break
        fairs = _parse_list_html(decoded)
        if not fairs:
            logger.info("第 %d 页无数据，停止", page)
            break
        all_fairs.extend(fairs)
        logger.info(
            "第 %d 页获取到 %d 条招聘会，累计 %d 条",
            page,
            len(fairs),
            len(all_fairs),
        )
        time.sleep(0.8)

    # 去重
    seen: set[str] = set()
    unique: list[dict] = []
    for f in all_fairs:
        key = f.get("id") or (f["title"] + f["date_start"])
        if key not in seen:
            seen.add(key)
            unique.append(f)

    logger.info("Careers 招聘会爬取完成，共 %d 条", len(unique))
    return unique


# ─────────────────────────────────────────
# 缓存管理
# ─────────────────────────────────────────


def refresh_jobfairs_cache() -> list[dict]:
    fairs = scrape_careers_jobfairs()
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "updated_at": datetime.now().isoformat(),
        "count": len(fairs),
        "jobfairs": fairs,
    }
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    logger.info("Careers 招聘会缓存已更新：%s，共 %d 条", CACHE_FILE, len(fairs))
    return fairs


def get_cached_jobfairs() -> list[dict]:
    if CACHE_FILE.exists():
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data.get("jobfairs", [])
        except Exception:
            pass
    return refresh_jobfairs_cache()
