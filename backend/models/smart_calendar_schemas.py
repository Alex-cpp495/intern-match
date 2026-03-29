"""智能日历 API 契约 — Agent 智能筛选高相关度活动。"""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class SmartCalendarPlanRequest(BaseModel):
    goals: str = Field(
        ...,
        min_length=1,
        max_length=8000,
        description="用户自述：想提升什么、是否不确定实习方向等（支持从实习匹配预填长文）",
    )
    focus_areas: list[str] = Field(
        default_factory=list,
        description="关注标签，如 数据分析、宣讲会、软技能、行业探索",
    )
    horizon_days: int = Field(
        14,
        ge=7,
        le=21,
        description="向前规划天数，7～21",
    )
    grade: str = Field("", max_length=32, description="年级，可空")
    thread_id: str | None = Field(
        None,
        max_length=64,
        description="会话 ID，传入同一值可多轮对话追加调优",
    )
    timetable_busy: dict[str, list[list[str]]] | None = Field(
        None,
        description='课表 busy 时段，如 {"周一":[["08:00","09:45"]]}',
    )
    followup: str | None = Field(
        None,
        max_length=1000,
        description="多轮追问，如 '只看宣讲会' / '去掉周三的活动'",
    )


class FilteredEventOut(BaseModel):
    event_uid: str = Field(..., description="必须与工具返回的 uid 一致")
    title: str = Field(...)
    start_iso: str = Field(..., description="ISO-8601")
    end_iso: str = Field("", description="ISO-8601，可空")
    all_day: bool = Field(False)
    source: str = Field(...)
    location: str = Field("")
    url: str = Field("")
    description: str = Field("")
    categories: list[str] = Field(default_factory=list)
    relevance_score: float = Field(0.5, ge=0, le=1, description="0-1 相关度")
    reason: str = Field("", max_length=500, description="为什么与用户需求相关")


class SmartFilterResult(BaseModel):
    summary: str = Field(
        ...,
        max_length=800,
        description="一句话概括筛选策略",
    )
    filtered_events: list[FilteredEventOut] = Field(
        default_factory=list,
        description="按相关度排序的活动列表",
    )

    @field_validator("filtered_events")
    @classmethod
    def cap_events(cls, v: list[FilteredEventOut]) -> list[FilteredEventOut]:
        return v[:50]


class SmartCalendarPlanResponse(BaseModel):
    result: SmartFilterResult
    agent_steps: int = Field(0, description="模型-工具往返轮次近似值")
    model: str = Field("deepseek-chat", description="所用模型 id")
    thread_id: str = Field("", description="会话 ID，前端可缓存用于多轮追问")