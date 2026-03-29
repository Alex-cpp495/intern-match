from pydantic import BaseModel, Field
from typing import Optional


class UserPreferences(BaseModel):
    company_size: Optional[str] = ""   # 大厂 / 中型企业 / 初创 / 高校
    industry: Optional[str] = ""       # 互联网 / 金融 / 设计 / 教育 ...
    work_env: Optional[str] = ""       # 技术 / 创意 / 稳定 / 扁平快节奏


class MatchRequest(BaseModel):
    schedule_text: str = Field(default="", description="自然语言课程表描述")
    major: str = Field(default="计算机科学", description="专业")
    grade: str = Field(default="大二", description="年级：大一/大二/大三/大四/研究生")
    skills: list[str] = Field(default_factory=list, description="技能标签列表")
    interests: list[str] = Field(default_factory=list, description="兴趣方向列表")
    has_project: bool = Field(default=False, description="是否有相关项目经验")
    intern_period: str = Field(default="", description="实习时间段：暑期/寒假/在读/随时")
    preferences: UserPreferences = Field(default_factory=UserPreferences)


class DimensionScores(BaseModel):
    d1_skill: float
    d2_time: float
    d3_interest: float
    d4_ability: float
    d5_culture: float


class JobResult(BaseModel):
    id: str
    title: str
    company: str
    location: str
    salary: str
    work_type: str
    weekly_hours: float
    is_remote: bool
    industry: str = ""
    tags: list[str]
    description: str
    source: str
    source_url: str = ""
    total_score: float
    dimensions: DimensionScores
    weights_used: Optional[DimensionScores] = None
    explanation: str = ""


class SkillGap(BaseModel):
    skill: str
    demand_count: int
    demand_ratio: float

class WeakDimension(BaseModel):
    dimension: str
    label: str
    avg_score: float
    tip: str

class Advice(BaseModel):
    skill_gaps: list[SkillGap] = []
    weak_dimensions: list[WeakDimension] = []
    summary: str = ""

class MatchResponse(BaseModel):
    jobs: list[JobResult]
    free_hours_per_week: float
    free_slots: dict
    total_jobs_scanned: int
    advice: Optional[Advice] = None


class ParseScheduleRequest(BaseModel):
    schedule_text: str


class ParseScheduleResponse(BaseModel):
    busy_slots: dict
    free_slots: dict
    free_hours_per_week: float


class FeedbackRequest(BaseModel):
    job_id: str = ""
    job_title: str = ""
    company: str = ""
    helpful: bool = True
    comment: str = ""
    total_score: Optional[float] = None
