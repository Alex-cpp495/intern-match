"""
从 Scientia / UNNC 个人课表等 iCal 拉取并解析为 CalendarEvent。
- webcal:// 会规范为 https://
- 仅允许 *.scientia.com.cn，防止开放 URL 时的 SSRF
"""

from __future__ import annotations

import hashlib
import logging
import re
from datetime import date, datetime, timedelta
from typing import Optional
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

import icalendar
import recurring_ical_events
import requests

from models.calendar_schemas import CalendarEvent, CalendarSource

logger = logging.getLogger(__name__)

DEFAULT_TZ = ZoneInfo("Asia/Shanghai")
# 宁诺课表 API 所在域；勿扩大为任意公网，避免 SSRF
ALLOWED_ICAL_HOST_SUFFIXES = (".scientia.com.cn",)
MAX_ICS_BYTES = 6 * 1024 * 1024
DEFAULT_EXPAND_DAYS = 200
MAX_EVENTS_RETURN = 800


def normalize_ics_url(raw: str) -> str:
    u = (raw or "").strip()
    if u.lower().startswith("webcal://"):
        return "https://" + u[9:]
    return u


def is_allowed_ical_fetch_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
    except Exception:
        return False
    if parsed.scheme not in ("http", "https"):
        return False
    host = (parsed.hostname or "").lower()
    return any(host.endswith(sfx) for sfx in ALLOWED_ICAL_HOST_SUFFIXES)


def fetch_ics_text(url: str, timeout: float = 30.0) -> str:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "text/calendar, text/plain, */*",
    }
    resp = requests.get(url, headers=headers, timeout=timeout, allow_redirects=True)
    resp.raise_for_status()
    raw = resp.content
    if len(raw) > MAX_ICS_BYTES:
        raise ValueError("日历文件过大")
    return raw.decode(resp.encoding or "utf-8", errors="replace")


def _ensure_aware(dt: datetime | date, default_tz: ZoneInfo) -> datetime:
    if isinstance(dt, date) and not isinstance(dt, datetime):
        return datetime(dt.year, dt.month, dt.day, tzinfo=default_tz)
    if isinstance(dt, datetime):
        if dt.tzinfo is None:
            return dt.replace(tzinfo=default_tz)
        return dt.astimezone(default_tz)
    raise TypeError(type(dt))


def _text_from_ical(val) -> str:
    if val is None:
        return ""
    s = str(val)
    return re.sub(r"\s+", " ", s).strip()


def parse_ics_text_to_events(
    ics_text: str,
    default_tz: ZoneInfo = DEFAULT_TZ,
    expand_days: int = DEFAULT_EXPAND_DAYS,
) -> list[CalendarEvent]:
    cal = icalendar.Calendar.from_ical(ics_text)
    now = datetime.now(default_tz)
    range_end = now + timedelta(days=expand_days)
    out: list[CalendarEvent] = []

    try:
        expanded = recurring_ical_events.of(cal).between(now, range_end)
    except Exception as e:
        logger.warning("recurring_ical_events 展开失败，尝试仅解析顶层 VEVENT: %s", e)
        expanded = []
        for c in cal.walk("VEVENT"):
            expanded.append(c)

    for comp in expanded:
        if comp.name != "VEVENT":
            continue
        try:
            dtstart = comp.get("dtstart")
            if dtstart is None:
                continue
            start_raw = dtstart.dt
            all_day = isinstance(start_raw, date) and not isinstance(start_raw, datetime)

            start_dt = _ensure_aware(start_raw, default_tz)

            dtend = comp.get("dtend")
            dur = comp.get("duration")
            if dtend is not None:
                end_raw = dtend.dt
                end_dt = _ensure_aware(end_raw, default_tz)
            elif dur is not None:
                end_dt = start_dt + dur.dt
            else:
                if all_day:
                    end_dt = start_dt + timedelta(days=1)
                else:
                    end_dt = start_dt + timedelta(hours=1)

            if end_dt <= start_dt:
                end_dt = start_dt + (timedelta(days=1) if all_day else timedelta(hours=1))

            title = _text_from_ical(comp.get("summary")) or "课表"
            loc = _text_from_ical(comp.get("location"))
            desc = _text_from_ical(comp.get("description"))
            uid_raw = _text_from_ical(comp.get("uid")) or title
            uid_key = f"{uid_raw}|{start_dt.isoformat()}"
            uid = hashlib.sha256(uid_key.encode("utf-8")).hexdigest()[:32]

            cats: list[str] = []
            cat = comp.get("categories")
            if cat is not None:
                try:
                    raw_cats = getattr(cat, "cats", None)
                    if raw_cats is not None:
                        cats = [str(x).strip() for x in raw_cats if str(x).strip()]
                    else:
                        cats = [x.strip() for x in str(cat).split(",") if x.strip()]
                except Exception:
                    cats = []

            out.append(
                CalendarEvent(
                    uid=uid,
                    title=title,
                    start_iso=start_dt.isoformat(),
                    end_iso=end_dt.isoformat(),
                    all_day=all_day,
                    busy=True,
                    source=CalendarSource.ICAL_TIMETABLE,
                    location=loc,
                    url="",
                    description=desc,
                    categories=cats,
                )
            )
        except Exception as ex:
            logger.debug("跳过无效 VEVENT: %s", ex)
            continue

    out.sort(key=lambda e: e.start_iso or "")
    return out


def import_from_url(ics_url: str, expand_days: int = DEFAULT_EXPAND_DAYS) -> tuple[str, list[CalendarEvent], Optional[str]]:
    """
    拉取并解析。返回 (import_id, events, error_message)。
    """
    url = normalize_ics_url(ics_url)
    if not is_allowed_ical_fetch_url(url):
        return "", [], "仅允许订阅宁诺 Scientia 课表域名（*.scientia.com.cn）"
    try:
        text = fetch_ics_text(url)
    except requests.RequestException as e:
        logger.info("拉取 iCal 失败: %s", type(e).__name__)
        return "", [], f"无法拉取日历链接：{e!s}"
    except Exception as e:
        return "", [], str(e)

    try:
        events = parse_ics_text_to_events(text, expand_days=expand_days)
    except Exception as e:
        logger.exception("解析 iCal 失败")
        return "", [], f"解析日历失败：{e!s}"

    import_id = hashlib.sha256(
        f"{url}|{len(events)}|{events[0].start_iso if events else ''}".encode()
    ).hexdigest()[:16]
    return import_id, events[:MAX_EVENTS_RETURN], None


def import_from_ics_text(
    ics_text: str,
    expand_days: int = DEFAULT_EXPAND_DAYS,
) -> tuple[str, list[CalendarEvent], Optional[str]]:
    """解析用户粘贴的 .ics 全文（不做域名校验）。"""
    if not (ics_text or "").strip():
        return "", [], "ics_text 为空"
    try:
        events = parse_ics_text_to_events(ics_text.strip(), expand_days=expand_days)
    except Exception as e:
        logger.exception("解析粘贴的 iCal 失败")
        return "", [], f"解析日历失败：{e!s}"
    import_id = hashlib.sha256(
        f"paste|{len(events)}|{events[0].start_iso if events else ''}".encode()
    ).hexdigest()[:16]
    return import_id, events[:MAX_EVENTS_RETURN], None
