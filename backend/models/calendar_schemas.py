"""
统一日历 / iCal 融合 / 活动推荐 —— API 契约（可与 RFC 5545 VEVENT 字段对齐）。

后续实现要点：
- POST /calendar/import/ical：解析 .ics，写入用户/会话级课表 busy 段；
- GET /calendar/merged：校园活动 + 用户课表统一为 CalendarEvent；
- POST /calendar/recommendations：在空闲时间内过滤、排序可参加活动。
"""

from __future__ import annotations

from enum import StrEnum
from typing import Optional

from pydantic import BaseModel, Field


class CalendarSource(StrEnum):
    """条目来源，便于合并与展示分层。"""

    UNNC_EVENTS = "unnc_events"  # 官网活动列表
    CAREERS_LECTURE = "careers_lecture"  # careers 就业讲座等
    CAREERS_JOBFAIR = "careers_jobfair"  # careers 招聘会
    CAREERS_TEACHIN = "careers_teachin"  # careers 企业宣讲会
    ICAL_TIMETABLE = "ical_timetable"  # 宁诺课表等 iCal 导入
    USER_CUSTOM = "user_custom"  # 用户手动添加
    WECHAT_EVENT = "wechat_event"  # 微信公众号文章 AI 抽取的活动


class CalendarEvent(BaseModel):
    """
    统一日历事件。时间与 iCal 一致时建议用带时区的 ISO-8601 字符串。
    """

    uid: str = Field(..., description="唯一标识，可与 VEVENT UID 或自建稳定 id 对齐")
    title: str
    start_iso: Optional[str] = Field(
        None, description="开始时间 ISO-8601，含时区时优先（如 2026-03-28T14:00:00+08:00）"
    )
    end_iso: Optional[str] = Field(None, description="结束时间 ISO-8601")
    all_day: bool = Field(False, description="是否全日事件")
    busy: bool = Field(
        False,
        description="True 表示占用时间（课表/考试），推荐算法应视为不可参加其他线下活动",
    )
    source: CalendarSource = Field(..., description="数据来源")
    location: str = ""
    url: str = ""
    description: str = ""
    categories: list[str] = Field(
        default_factory=list,
        description="可选标签，对应 iCal CATEGORIES 或业务标签",
    )


class ICalImportRequest(BaseModel):
    """导入课表等 iCal 的请求体（预留：可二选一或同时传）。"""

    ics_url: Optional[str] = Field(None, description="远程 .ics 地址")
    ics_text: Optional[str] = Field(None, description="原始 .ics 文本")
    user_id: Optional[str] = Field(
        None, description="登录用户 id；未登录时可配合 session_id"
    )
    session_id: Optional[str] = Field(None, description="匿名会话 id，用于开发阶段")
    timezone: str = Field(
        "Asia/Shanghai",
        description="解析无时区 VEVENT 时使用的默认时区",
    )


class ICalImportResult(BaseModel):
    """导入结果（实现后返回解析条数与可选警告）。"""

    import_id: str = Field(..., description="本次导入任务或存储批次 id")
    status: str = Field(..., description="accepted | processing | failed | stub")
    message: str = ""
    events_parsed: int = 0
    events: list[CalendarEvent] = Field(
        default_factory=list,
        description="解析出的课表条目预览（实现后可截断）",
    )


class MergedCalendarQuery(BaseModel):
    """GET 合并日历的查询参数（也可用 Query 逐项声明）。"""

    range_start: Optional[str] = Field(
        None, description="区间起点 ISO-8601，含时区"
    )
    range_end: Optional[str] = Field(
        None, description="区间终点 ISO-8601，含时区"
    )
    include_sources: Optional[list[CalendarSource]] = Field(
        None,
        description="仅返回指定来源；默认可返回全部已实现来源",
    )


class MergedCalendarResponse(BaseModel):
    """合并后的时间轴视图。"""

    events: list[CalendarEvent]
    total: int
    by_source: dict[str, int] = Field(
        default_factory=dict,
        description="各来源条数，便于调试与 UI 图例",
    )


class ActivityRecommendationRequest(BaseModel):
    """根据空闲时间推荐可参加的活动（课表融合后使用）。"""

    user_id: Optional[str] = None
    session_id: Optional[str] = None
    range_start: Optional[str] = Field(None, description="推荐窗口起点")
    range_end: Optional[str] = Field(None, description="推荐窗口终点")
    max_results: int = Field(20, ge=1, le=100)
    preference_tags: list[str] = Field(
        default_factory=list,
        description="可选：行业/类型偏好，与活动标签粗匹配",
    )
    exclude_busy: bool = Field(
        True,
        description="True 时与已导入课表 busy 段求无交集（需已 import ical）",
    )


class RecommendedActivity(BaseModel):
    """推荐结果中单条活动，带可解释性字段。"""

    event: CalendarEvent
    fits_free_slot: bool = Field(
        ...,
        description="是否与当前推断的空闲时段兼容（实现后由算法写入）",
    )
    reason: str = Field("", description="简短说明，如「周三下午无课且与讲座无重叠」")
    score: Optional[float] = Field(
        None,
        description="可选排序分，融合偏好与时间适配度",
    )


class ActivityRecommendationResponse(BaseModel):
    recommended: list[RecommendedActivity]
    total_candidates: int = Field(0, description="窗口内活动总数")
    message: str = ""
