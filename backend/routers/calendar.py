"""
日历融合预留 API：校园活动 + iCal 课表 + 空闲时段活动推荐。

当前行为：
- GET /calendar/merged 将已有官网活动映射为统一 CalendarEvent；
- POST /calendar/import/ical 仅校验契约并返回 stub，待接入 icalendar / 存储；
- POST /calendar/recommendations 返回说明性占位，待接入空闲时间推理。
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Optional
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response

from models.smart_calendar_schemas import (
    SmartCalendarPlanRequest,
    SmartCalendarPlanResponse,
)
from models.calendar_schemas import (
    ActivityRecommendationRequest,
    ActivityRecommendationResponse,
    CalendarEvent,
    CalendarSource,
    ICalImportRequest,
    ICalImportResult,
    MergedCalendarResponse,
    RecommendedActivity,
)
from ical_import import import_from_ics_text, import_from_url
from scraper.unnc_events import get_cached_events
from scraper.careers_lectures import get_cached_lectures
from scraper.careers_jobfairs import get_cached_jobfairs
from scraper.careers_teachins import get_cached_teachins

logger = logging.getLogger(__name__)
router = APIRouter()
DEFAULT_TZ = ZoneInfo("Asia/Shanghai")


def _stable_uid(source: CalendarSource, title: str, date_start: str, time_start: str) -> str:
    raw = f"{source.value}|{title}|{date_start}|{time_start}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def _unnc_event_to_calendar(e: dict) -> Optional[CalendarEvent]:
    title = (e.get("title") or "").strip()
    date_start = (e.get("date_start") or "").strip()
    date_end = (e.get("date_end") or date_start).strip()
    time_start = (e.get("time_start") or "").strip() or "09:00"
    time_end = (e.get("time_end") or "").strip() or time_start
    if not title or not date_start:
        return None
    start_iso: Optional[str] = None
    end_iso: Optional[str] = None
    try:
        ds = datetime.strptime(f"{date_start} {time_start}", "%Y-%m-%d %H:%M").replace(
            tzinfo=DEFAULT_TZ
        )
        start_iso = ds.isoformat()
        de = datetime.strptime(f"{date_end} {time_end}", "%Y-%m-%d %H:%M").replace(
            tzinfo=DEFAULT_TZ
        )
        end_iso = de.isoformat()
    except ValueError:
        logger.debug("无法解析活动时间: %s %s", date_start, time_start)
    return CalendarEvent(
        uid=_stable_uid(CalendarSource.UNNC_EVENTS, title, date_start, time_start),
        title=title,
        start_iso=start_iso,
        end_iso=end_iso,
        all_day=False,
        busy=False,
        source=CalendarSource.UNNC_EVENTS,
        location=e.get("location") or "",
        url=e.get("link") or "",
        description=e.get("description") or "",
    )


def _filter_by_range(
    events: list[CalendarEvent],
    range_start: Optional[str],
    range_end: Optional[str],
) -> list[CalendarEvent]:
    if not range_start and not range_end:
        return events
    out: list[CalendarEvent] = []
    for ev in events:
        if not ev.start_iso:
            out.append(ev)
            continue
        try:
            s = datetime.fromisoformat(ev.start_iso.replace("Z", "+00:00"))
        except ValueError:
            out.append(ev)
            continue
        ok = True
        if range_start:
            try:
                rs = datetime.fromisoformat(range_start.replace("Z", "+00:00"))
                if s < rs:
                    ok = False
            except ValueError:
                pass
        if ok and range_end:
            try:
                re = datetime.fromisoformat(range_end.replace("Z", "+00:00"))
                if s > re:
                    ok = False
            except ValueError:
                pass
        if ok:
            out.append(ev)
    return out


def _careers_lecture_to_calendar(lec: dict) -> Optional[CalendarEvent]:
    title = (lec.get("title") or "").strip()
    date_start = (lec.get("date_start") or "").strip()
    date_end = (lec.get("date_end") or date_start).strip()
    time_start = (lec.get("time_start") or "").strip()
    time_end = (lec.get("time_end") or "").strip() or time_start
    if not title or not date_start:
        return None
    start_iso: Optional[str] = None
    end_iso: Optional[str] = None
    try:
        fmt = "%Y-%m-%d %H:%M" if time_start else "%Y-%m-%d"
        ds = datetime.strptime(
            f"{date_start} {time_start}" if time_start else date_start, fmt
        ).replace(tzinfo=DEFAULT_TZ)
        start_iso = ds.isoformat()
        de = datetime.strptime(
            f"{date_end} {time_end}" if time_end else date_end,
            "%Y-%m-%d %H:%M" if time_end else "%Y-%m-%d",
        ).replace(tzinfo=DEFAULT_TZ)
        end_iso = de.isoformat()
    except ValueError:
        logger.debug("无法解析讲座时间: %s %s", date_start, time_start)

    categories: list[str] = []
    organizer = (lec.get("organizer") or "").strip()
    if organizer:
        categories.append(organizer)

    return CalendarEvent(
        uid=_stable_uid(CalendarSource.CAREERS_LECTURE, title, date_start, time_start or "00:00"),
        title=title,
        start_iso=start_iso,
        end_iso=end_iso,
        all_day=not bool(time_start),
        busy=False,
        source=CalendarSource.CAREERS_LECTURE,
        location=lec.get("location") or "",
        url=lec.get("link") or "",
        description=lec.get("description") or "",
        categories=categories,
    )


def _jobfair_to_calendar(jf: dict) -> Optional[CalendarEvent]:
    title = (jf.get("title") or "").strip()
    date_start = (jf.get("date_start") or "").strip()
    date_end = (jf.get("date_end") or date_start).strip()
    time_start = (jf.get("time_start") or "").strip()
    time_end = (jf.get("time_end") or "").strip() or time_start
    if not title or not date_start:
        return None
    start_iso: Optional[str] = None
    end_iso: Optional[str] = None
    try:
        fmt = "%Y-%m-%d %H:%M" if time_start else "%Y-%m-%d"
        ds = datetime.strptime(
            f"{date_start} {time_start}" if time_start else date_start, fmt
        ).replace(tzinfo=DEFAULT_TZ)
        start_iso = ds.isoformat()
        de = datetime.strptime(
            f"{date_end} {time_end}" if time_end else date_end,
            "%Y-%m-%d %H:%M" if time_end else "%Y-%m-%d",
        ).replace(tzinfo=DEFAULT_TZ)
        end_iso = de.isoformat()
    except ValueError:
        logger.debug("无法解析招聘会时间: %s %s", date_start, time_start)

    status = (jf.get("status") or "").strip()
    categories = [status] if status else []

    return CalendarEvent(
        uid=_stable_uid(CalendarSource.CAREERS_JOBFAIR, title, date_start, time_start or "00:00"),
        title=title,
        start_iso=start_iso,
        end_iso=end_iso,
        all_day=not bool(time_start),
        busy=False,
        source=CalendarSource.CAREERS_JOBFAIR,
        location=jf.get("location") or "",
        url=jf.get("link") or "",
        description="",
        categories=categories,
    )


def _teachin_to_calendar(ti: dict) -> Optional[CalendarEvent]:
    title = (ti.get("title") or "").strip()
    date_start = (ti.get("date_start") or "").strip()
    date_end = (ti.get("date_end") or date_start).strip()
    time_start = (ti.get("time_start") or "").strip()
    time_end = (ti.get("time_end") or "").strip() or time_start
    if not title or not date_start:
        return None
    start_iso: Optional[str] = None
    end_iso: Optional[str] = None
    try:
        fmt = "%Y-%m-%d %H:%M" if time_start else "%Y-%m-%d"
        ds = datetime.strptime(
            f"{date_start} {time_start}" if time_start else date_start, fmt
        ).replace(tzinfo=DEFAULT_TZ)
        start_iso = ds.isoformat()
        de = datetime.strptime(
            f"{date_end} {time_end}" if time_end else date_end,
            "%Y-%m-%d %H:%M" if time_end else "%Y-%m-%d",
        ).replace(tzinfo=DEFAULT_TZ)
        end_iso = de.isoformat()
    except ValueError:
        logger.debug("无法解析宣讲会时间: %s %s", date_start, time_start)

    status = (ti.get("status") or "").strip()
    categories = [status] if status else []

    return CalendarEvent(
        uid=_stable_uid(CalendarSource.CAREERS_TEACHIN, title, date_start, time_start or "00:00"),
        title=title,
        start_iso=start_iso,
        end_iso=end_iso,
        all_day=not bool(time_start),
        busy=False,
        source=CalendarSource.CAREERS_TEACHIN,
        location=ti.get("location") or "",
        url=ti.get("link") or "",
        description="",
        categories=categories,
    )


def collect_merged_calendar_events() -> list[CalendarEvent]:
    """官网活动 + Careers 讲座 + 招聘会 + 宣讲会 → 统一 CalendarEvent 列表。"""
    events: list[CalendarEvent] = []
    for row in get_cached_events():
        ce = _unnc_event_to_calendar(row)
        if ce:
            events.append(ce)
    for lec in get_cached_lectures():
        ce = _careers_lecture_to_calendar(lec)
        if ce:
            events.append(ce)
    for jf in get_cached_jobfairs():
        ce = _jobfair_to_calendar(jf)
        if ce:
            events.append(ce)
    for ti in get_cached_teachins():
        ce = _teachin_to_calendar(ti)
        if ce:
            events.append(ce)
    events.sort(key=lambda e: e.start_iso or "")
    return events


def _ics_escape(text: str, max_len: int = 1800) -> str:
    if not text:
        return ""
    s = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    s = (
        s.replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\n", "\\n")
    )
    return s[:max_len]


def _parse_iso_to_aware(s: str) -> Optional[datetime]:
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None


def _build_merged_ics(events: list[CalendarEvent]) -> str:
    """生成 RFC 5545 文本（官网 + Careers，便于导入系统日历）。"""
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    lines: list[str] = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//UNNC//InternMatch Campus Calendar//ZH",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "X-WR-CALNAME:宁诺校园活动（官网+Careers）",
        "X-WR-TIMEZONE:Asia/Shanghai",
    ]
    for ev in events:
        if not ev.start_iso:
            continue
        start = _parse_iso_to_aware(ev.start_iso)
        if not start:
            continue
        end = _parse_iso_to_aware(ev.end_iso) if ev.end_iso else None
        if not end or end <= start:
            end = start + timedelta(hours=1)
        src = "官网" if ev.source == CalendarSource.UNNC_EVENTS else "Careers"
        summary = _ics_escape(f"[{src}] {ev.title}", 900)
        loc = _ics_escape(ev.location or "", 500)
        desc = _ics_escape(ev.description or "", 1200)
        url = _ics_escape(ev.url or "", 500)

        lines.append("BEGIN:VEVENT")
        lines.append(f"UID:{ev.uid}@intern-match.unnc")
        lines.append(f"DTSTAMP:{stamp}")
        if ev.all_day:
            sd = start.astimezone(DEFAULT_TZ).date()
            ed = end.astimezone(DEFAULT_TZ).date()
            if ed < sd:
                ed = sd
            dtend_day = ed + timedelta(days=1)
            lines.append(f"DTSTART;VALUE=DATE:{sd.strftime('%Y%m%d')}")
            lines.append(f"DTEND;VALUE=DATE:{dtend_day.strftime('%Y%m%d')}")
        else:
            st = start.astimezone(DEFAULT_TZ).strftime("%Y%m%dT%H%M%S")
            en = end.astimezone(DEFAULT_TZ).strftime("%Y%m%dT%H%M%S")
            lines.append(f"DTSTART;TZID=Asia/Shanghai:{st}")
            lines.append(f"DTEND;TZID=Asia/Shanghai:{en}")
        lines.append(f"SUMMARY:{summary}")
        if loc:
            lines.append(f"LOCATION:{loc}")
        if desc:
            lines.append(f"DESCRIPTION:{desc}")
        if url:
            lines.append(f"URL:{url}")
        lines.append("END:VEVENT")
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines)


@router.post("/calendar/smart-plan", response_model=SmartCalendarPlanResponse)
async def smart_calendar_plan(body: SmartCalendarPlanRequest):
    """
    LangGraph 手动编排 Agent：多工具拉取活动 → 课表冲突检测 → 结构化 JSON 日历。
    支持 thread_id 多轮对话 / followup 追问 / timetable_busy 课表冲突。
    """
    from core.campus_smart_calendar_agent import run_smart_calendar_plan as run_plan

    try:
        return await asyncio.to_thread(
            run_plan,
            body,
            thread_id=body.thread_id,
            timetable_busy=body.timetable_busy,
        )
    except RuntimeError as e:
        logger.warning("smart-plan 不可用: %s", e)
        raise HTTPException(status_code=503, detail=str(e)) from e
    except Exception:
        logger.exception("smart-plan 执行失败")
        raise HTTPException(
            status_code=500,
            detail="智能日历生成失败，请稍后重试",
        ) from None


@router.get("/calendar/merged", response_model=MergedCalendarResponse)
async def get_merged_calendar(
    range_start: Optional[str] = Query(None, description="区间起点 ISO-8601"),
    range_end: Optional[str] = Query(None, description="区间终点 ISO-8601"),
):
    """
    合并视图：官网活动 + Careers 讲座；课表需在导入接口实现后从存储层并入。
    """
    events = collect_merged_calendar_events()
    events = _filter_by_range(events, range_start, range_end)
    counts = Counter(e.source.value for e in events)
    return MergedCalendarResponse(
        events=events,
        total=len(events),
        by_source=dict(counts),
    )


@router.get("/calendar/merged.ics")
async def get_merged_calendar_ics():
    """
    合并日历的 iCal 文件：官网活动 + Careers 讲座。
    可下载后导入 Apple / Google / Outlook 等「合并到系统日历」。
    """
    events = collect_merged_calendar_events()
    body = _build_merged_ics(events)
    return Response(
        content=body.encode("utf-8"),
        media_type="text/calendar; charset=utf-8",
        headers={
            "Content-Disposition": 'attachment; filename="unnc-campus-merged.ics"',
            "Cache-Control": "no-store",
        },
    )


@router.post("/calendar/import/ical", response_model=ICalImportResult)
async def import_ical(body: ICalImportRequest):
    """
    拉取或粘贴 .ics，解析为 `ICAL_TIMETABLE`（busy=True）。
    - ics_url：仅允许 *.scientia.com.cn（宁诺 Scientia 个人订阅），自动将 webcal:// 转为 https://
    - ics_text：任意 .ics 原文（供本地上传文件内容），由用户自行负责来源
    """
    if not body.ics_url and not body.ics_text:
        return ICalImportResult(
            import_id="",
            status="failed",
            message="请提供 ics_url 或 ics_text",
            events_parsed=0,
            events=[],
        )

    err: Optional[str] = None
    import_id = ""
    events: list[CalendarEvent] = []

    if body.ics_url and body.ics_url.strip():
        import_id, events, err = import_from_url(body.ics_url.strip())
    elif body.ics_text and body.ics_text.strip():
        import_id, events, err = import_from_ics_text(body.ics_text.strip())

    if err:
        return ICalImportResult(
            import_id="",
            status="failed",
            message=err,
            events_parsed=0,
            events=[],
        )

    return ICalImportResult(
        import_id=import_id,
        status="accepted",
        message=f"已解析 {len(events)} 条课表事件（未来约 200 天内重复已展开）",
        events_parsed=len(events),
        events=events,
    )


@router.post(
    "/calendar/recommendations",
    response_model=ActivityRecommendationResponse,
)
async def recommend_activities(body: ActivityRecommendationRequest):
    """
    预留：在 range 内筛选与课表 busy 无冲突、且可选匹配 preference_tags 的活动。
    """
    events = collect_merged_calendar_events()
    events = _filter_by_range(events, body.range_start, body.range_end)
    activities = [e for e in events if e.source != CalendarSource.ICAL_TIMETABLE]
    # 尚无课表数据时：全部标为待确认适配
    recs: list[RecommendedActivity] = []
    for ev in activities[: body.max_results]:
        recs.append(
            RecommendedActivity(
                event=ev,
                fits_free_slot=False,
                reason="待接入课表 busy 与空闲时段计算；当前为占位推荐列表。",
                score=None,
            )
        )
    return ActivityRecommendationResponse(
        recommended=recs,
        total_candidates=len(activities),
        message="个性化空闲推荐需在 import ical + 时间冲突算法完成后启用。",
    )
