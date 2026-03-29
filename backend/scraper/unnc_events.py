"""
UNNC 官网活动爬虫
数据来源：https://www.nottingham.edu.cn/cn/events/event-listing.aspx
爬取内容：活动标题、日期、时间、地点、详情链接、活动描述
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Optional

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

BASE_URL = "https://www.nottingham.edu.cn"
LIST_URL = "https://www.nottingham.edu.cn/cn/events/event-listing.aspx"
CACHE_FILE = Path(__file__).parent.parent / "data" / "unnc_events.json"
MAX_PAGES = 21
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Referer": "https://www.nottingham.edu.cn/cn/events/event-listing.aspx",
}

MONTH_MAP = {
    "一月": 1, "二月": 2, "三月": 3, "四月": 4,
    "五月": 5, "六月": 6, "七月": 7, "八月": 8,
    "九月": 9, "十月": 10, "十一月": 11, "十二月": 12,
}


def _parse_date_text(raw: str) -> dict:
    """
    解析形如 "四月2026 11 08:30 - 16:00" 或多行日期的文本
    返回 {date_start, date_end, time_start, time_end}
    """
    raw = raw.strip()
    result = {"date_start": "", "date_end": "", "time_start": "", "time_end": ""}

    # 提取时间范围 "08:30 - 16:00"
    time_match = re.search(r"(\d{1,2}:\d{2})\s*[-–]\s*(\d{1,2}:\d{2})", raw)
    if time_match:
        result["time_start"] = time_match.group(1)
        result["time_end"] = time_match.group(2)
    elif re.search(r"\d{1,2}:\d{2}", raw):
        t = re.search(r"(\d{1,2}:\d{2})", raw)
        if t:
            result["time_start"] = t.group(1)

    # 提取月份+年+日
    lines = [l.strip() for l in re.split(r"\n|-\n", raw) if l.strip()]
    dates_found = []
    for line in lines:
        for month_cn, month_num in MONTH_MAP.items():
            m = re.search(rf"{month_cn}(\d{{4}})\s+(\d{{1,2}})", line)
            if m:
                try:
                    d = datetime(int(m.group(1)), month_num, int(m.group(2)))
                    dates_found.append(d.strftime("%Y-%m-%d"))
                except ValueError:
                    pass
    if dates_found:
        result["date_start"] = dates_found[0]
        result["date_end"] = dates_found[-1] if len(dates_found) > 1 else dates_found[0]

    return result


def _parse_schema_datetime_content(content: str) -> Optional[datetime]:
    """解析列表页 itemprop=startDate/endDate 的 content（如 2025/11/15 8:00:0 或 2025-12-01T08:30）。"""
    if not content or not str(content).strip():
        return None
    s = str(content).strip()
    if "T" in s:
        raw = s.split("+")[0].strip().replace("Z", "")
        if len(raw) == 10:
            try:
                return datetime.strptime(raw, "%Y-%m-%d")
            except ValueError:
                pass
        try:
            return datetime.fromisoformat(raw[:19])
        except ValueError:
            pass
    m = re.match(
        r"^(\d{4})/(\d{1,2})/(\d{1,2})(?:\s+(\d{1,2}):(\d{2})(?::(\d{1,2}))?)?$",
        s,
    )
    if m:
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        hh = int(m.group(4)) if m.group(4) is not None else 9
        mm = int(m.group(5)) if m.group(5) is not None else 0
        try:
            return datetime(y, mo, d, hh, mm)
        except ValueError:
            return None
    return None


def _parse_time_range_in_span(text: str) -> tuple[str, str]:
    if not text:
        return "", ""
    text = text.strip()
    m = re.match(r"(\d{1,2}:\d{2})\s*[-–]\s*(\d{1,2}:\d{2})", text)
    if m:
        return m.group(1), m.group(2)
    m2 = re.match(r"^(\d{1,2}:\d{2})$", text)
    if m2:
        t = m2.group(1)
        return t, t
    return "", ""


def _parse_event_listing_item(li) -> Optional[dict]:
    """解析 ul.event-listing 中一条 schema.org Event（含跨日 half-width）。"""
    title_a = li.select_one("h2.event-listing__content--title a")
    if not title_a:
        title_a = li.select_one("h2.summary a, h2 a")
    title = title_a.get_text(strip=True) if title_a else ""
    href = (title_a.get("href") or "").strip() if title_a else ""
    link = href if href.startswith("http") else (BASE_URL + href if href else "")

    loc_el = li.select_one('[itemprop="location"], p.location')
    location = loc_el.get_text(strip=True) if loc_el else ""

    start_el = li.select_one('[itemprop="startDate"]')
    if not start_el or not start_el.get("content"):
        return None
    end_el = li.select_one('[itemprop="endDate"]')

    date_start = ""
    date_end = ""
    time_start = ""
    time_end = ""

    if end_el and end_el.get("content"):
        sdt = _parse_schema_datetime_content(start_el["content"])
        edt = _parse_schema_datetime_content(end_el["content"])
        if sdt and edt:
            date_start = sdt.strftime("%Y-%m-%d")
            time_start = sdt.strftime("%H:%M")
            date_end = edt.strftime("%Y-%m-%d")
            time_end = edt.strftime("%H:%M")
    else:
        sdt = _parse_schema_datetime_content(start_el["content"])
        if sdt:
            date_start = date_end = sdt.strftime("%Y-%m-%d")
            time_start = time_end = sdt.strftime("%H:%M")
        time_span = start_el.select_one(".event-listing__info--time")
        if time_span:
            t0, t1 = _parse_time_range_in_span(time_span.get_text(strip=True))
            if t0:
                time_start = t0
            if t1:
                time_end = t1
            elif t0:
                time_end = t0

    if not title or not date_start:
        return None

    if not date_end:
        date_end = date_start
    if not time_end:
        time_end = time_start

    return {
        "title": title,
        "location": location,
        "link": link,
        "date_start": date_start,
        "date_end": date_end,
        "time_start": time_start,
        "time_end": time_end,
        "description": "",
    }


def _parse_events_microdata(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "lxml")
    items = soup.select("ul.event-listing > li.event-listing__item")
    if not items:
        return []
    events: list[dict] = []
    for li in items:
        ev = _parse_event_listing_item(li)
        if ev:
            events.append(ev)
    return events


def _fetch_page(page_index: int, retries: int = 2) -> Optional[str]:
    """获取活动列表页 HTML"""
    params = {} if page_index == 1 else {"EVTPageIndex": page_index}
    for attempt in range(retries + 1):
        try:
            resp = requests.get(LIST_URL, params=params, headers=HEADERS, timeout=15)
            resp.encoding = "utf-8"
            if resp.status_code == 200:
                return resp.text
            logger.warning(f"页面 {page_index} 返回 {resp.status_code}")
        except Exception as e:
            if attempt < retries:
                time.sleep(1.5)
            else:
                logger.warning(f"页面 {page_index} 获取失败: {e}")
    return None


def _fetch_detail(url: str) -> str:
    """获取活动详情页的正文描述"""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=12)
        resp.encoding = "utf-8"
        soup = BeautifulSoup(resp.text, "lxml")
        # 尝试找正文区域
        for selector in [
            ".sys-event-body",
            ".event-body",
            ".news-detail",
            "article",
            ".main-content",
        ]:
            el = soup.select_one(selector)
            if el:
                text = el.get_text(" ", strip=True)
                return text[:600]
        # 兜底：取 main 区域的段落
        main = soup.find("main") or soup.find("div", {"id": "main"})
        if main:
            paras = [p.get_text(" ", strip=True) for p in main.find_all("p") if p.get_text(strip=True)]
            return " ".join(paras)[:600]
    except Exception as e:
        logger.debug(f"详情页获取失败 {url}: {e}")
    return ""


def _parse_events_from_html(html: str) -> list[dict]:
    """从列表页 HTML 解析活动卡片（专为 UNNC 活动页结构优化）"""
    # ── 策略零：官网新版 ul.event-listing + schema.org microdata ──
    md_events = _parse_events_microdata(html)
    if md_events:
        return md_events

    soup = BeautifulSoup(html, "lxml")
    events = []

    # ── 策略一：标准卡片选择器 ──
    cards = (
        soup.select(".event-item")
        or soup.select(".sys-event-list li")
        or soup.select("ul.events li")
        or soup.select(".event-listing-item")
    )

    if cards:
        for card in cards:
            title_el = card.find(["h2", "h3", "h4"])
            title = title_el.get_text(strip=True) if title_el else ""
            if not title:
                continue
            text_block = card.get_text("\n", strip=True)
            date_info = _parse_date_text(text_block)
            location = ""
            loc_el = card.select_one(".location, .venue, .place")
            if loc_el:
                location = loc_el.get_text(strip=True)
            link = ""
            a_tag = card.find("a")
            if a_tag and a_tag.get("href"):
                href = a_tag["href"]
                link = href if href.startswith("http") else BASE_URL + href
            events.append({"title": title, "location": location, "link": link, **date_info})
        return events

    # ── 策略二：UNNC 专用解析（日期在 h2 前面的兄弟节点）──
    headings = soup.find_all(["h2", "h3"])
    for h in headings:
        title = h.get_text(strip=True)
        if not title or len(title) < 3:
            continue

        # 收集 h2 之前的兄弟节点文本（最多往前找 6 个）作为日期候选
        date_text = ""
        count = 0
        for sib in h.previous_siblings:
            if count >= 6:
                break
            t = sib.get_text(" ", strip=True) if hasattr(sib, "get_text") else str(sib).strip()
            t = t.strip()
            if not t:
                continue
            # 找到包含中文月份的文本就停下
            if any(m in t for m in MONTH_MAP):
                date_text = t
                break
            count += 1

        # 如果前置兄弟找不到，尝试父级元素整体文本
        if not date_text:
            date_text = h.parent.get_text("\n", strip=True) if h.parent else ""

        date_info = _parse_date_text(date_text)

        # 地点：h2 之后的第一个非空短文本
        location = ""
        for sib in h.next_siblings:
            t = sib.get_text(strip=True) if hasattr(sib, "get_text") else str(sib).strip()
            if t and len(t) < 60 and t != title:
                location = t
                break

        # 链接
        link = ""
        a_tag = h.find("a") or (h.parent.find("a") if h.parent else None)
        if a_tag and a_tag.get("href"):
            href = a_tag["href"]
            link = href if href.startswith("http") else BASE_URL + href

        events.append({"title": title, "location": location, "link": link, **date_info})

    return events


def scrape_unnc_events(max_pages: int = MAX_PAGES, fetch_details: bool = False) -> list[dict]:
    """
    爬取 UNNC 活动列表，可选是否获取详情页描述。
    返回活动列表，每项包含：title, date_start, date_end, time_start, time_end, location, link, description
    """
    logger.info(f"开始爬取 UNNC 活动，最多 {max_pages} 页...")
    all_events: list[dict] = []

    for page in range(1, max_pages + 1):
        html = _fetch_page(page)
        if not html:
            logger.warning(f"第 {page} 页获取失败，停止")
            break
        events = _parse_events_from_html(html)
        if not events:
            logger.info(f"第 {page} 页无活动，停止")
            break
        all_events.extend(events)
        logger.info(f"第 {page} 页获取到 {len(events)} 条活动，累计 {len(all_events)} 条")
        time.sleep(0.8)  # 礼貌性延迟

    # 去重（按标题+日期）
    seen = set()
    unique_events = []
    for e in all_events:
        key = (e["title"], e["date_start"])
        if key not in seen:
            seen.add(key)
            unique_events.append(e)

    # 可选：并发获取详情页描述
    if fetch_details and unique_events:
        logger.info("开始获取活动详情...")
        with ThreadPoolExecutor(max_workers=4) as pool:
            futures = {
                pool.submit(_fetch_detail, e["link"]): i
                for i, e in enumerate(unique_events) if e.get("link")
            }
            for future in as_completed(futures):
                idx = futures[future]
                try:
                    unique_events[idx]["description"] = future.result()
                except Exception:
                    unique_events[idx]["description"] = ""
    else:
        for e in unique_events:
            e.setdefault("description", "")

    logger.info(f"爬取完成，共 {len(unique_events)} 条活动")
    return unique_events


# ─────────────────────────────────────────────
# 缓存管理
# ─────────────────────────────────────────────

def refresh_events_cache(fetch_details: bool = False) -> list[dict]:
    """重新爬取并更新缓存文件"""
    events = scrape_unnc_events(fetch_details=fetch_details)
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "updated_at": datetime.now().isoformat(),
        "count": len(events),
        "events": events,
    }
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    logger.info(f"活动缓存已更新：{CACHE_FILE}，共 {len(events)} 条")
    return events


def get_cached_events() -> list[dict]:
    """读取缓存，不存在时触发爬取"""
    if CACHE_FILE.exists():
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data.get("events", [])
        except Exception:
            pass
    return refresh_events_cache()
