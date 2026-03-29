import re
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from fastapi import APIRouter, HTTPException
from models.schemas import (
    MatchRequest,
    MatchResponse,
    ParseScheduleRequest,
    ParseScheduleResponse,
    FeedbackRequest,
)
from core.schedule_parser import parse_schedule
from core.matcher import rank_jobs
from core.explainer import batch_generate
from core.advisor import generate_advice
from scraper.shixiseng import get_all_jobs

logger = logging.getLogger(__name__)
router = APIRouter()

FEEDBACK_FILE = Path(__file__).resolve().parent.parent / "data" / "feedback.json"


def _estimate_free_hours_from_days(schedule_text: str) -> float | None:
    """
    从"每周X天"之类的自然语言估算每周空闲小时数。
    返回 None 表示无法识别，由 schedule_parser 兜底。
    """
    text = schedule_text.lower()
    # 匹配 "3-4天", "3到4天", "3天", "三四天" 等
    m = re.search(r"(\d+)\s*[-到~]\s*(\d+)\s*[天日]", text)
    if m:
        days = (int(m.group(1)) + int(m.group(2))) / 2
        return days * 9  # 每天约 9 小时有效工作
    m = re.search(r"(\d+)\s*[天日]", text)
    if m:
        return int(m.group(1)) * 9
    # 汉字数字
    cn = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7}
    for ch, n in cn.items():
        if ch + "天" in text or ch + "日" in text:
            return n * 9
    return None


@router.post("/match", response_model=MatchResponse)
async def match_jobs(req: MatchRequest):
    """主匹配接口：接收用户画像，返回排序后的岗位推荐列表"""
    # 1. 解析课程表，获取空闲时间
    schedule_result = parse_schedule(req.schedule_text)
    free_hours = schedule_result.get("free_hours_per_week", 20.0)
    free_slots = schedule_result.get("free_slots", {})

    # 暑期/寒假时学生基本全天可用（每周约 80 小时），直接覆盖
    intern_period = req.intern_period or ""
    if intern_period in ("暑期", "寒假"):
        free_hours = 80.0
        free_slots = {}   # 暑期不需要具体时间槽
    elif intern_period == "在读" and free_hours <= 14:
        # schedule_parser 对"一周3-4天"类简短描述解析不准确，尝试直接估算
        est = _estimate_free_hours_from_days(req.schedule_text)
        if est:
            free_hours = est
            logger.info(f"在读用户天数估算 free_hours={free_hours}")
        else:
            # 兜底：在读兼职默认 3 天 × 9h = 27h
            free_hours = 27.0

    # 2. 构建用户画像
    user_profile = {
        "skills": req.skills,
        "interests": req.interests,
        "grade": req.grade,
        "major": req.major,
        "has_project": req.has_project,
        "intern_period": intern_period,
        "free_hours": free_hours,
        "preferences": req.preferences.model_dump(),
    }

    # 3. 加载岗位数据
    jobs = get_all_jobs()
    if not jobs:
        raise HTTPException(status_code=503, detail="岗位数据暂时不可用，请稍后重试")

    # 4. 运行匹配算法
    ranked = rank_jobs(user_profile, jobs)

    # 5. 为前10条生成推荐理由（节省 API 调用）
    ranked_with_explain = batch_generate(user_profile, ranked, top_n=5)

    # 6. 格式化返回
    job_results = []
    for job in ranked_with_explain:
        job_results.append({
            "id": job.get("id", ""),
            "title": job.get("title", ""),
            "company": job.get("company", ""),
            "location": job.get("location", "宁波"),
            "salary": job.get("salary", "面议"),
            "work_type": job.get("work_type", "兼职"),
            "weekly_hours": job.get("weekly_hours", 20),
            "is_remote": job.get("is_remote", False),
            "industry": job.get("industry", "") or "",
            "tags": job.get("tags", [])[:6],
            "description": job.get("description", "")[:200],
            "source": job.get("source", ""),
            "source_url": job.get("source_url", ""),
            "total_score": job.get("total_score", 0),
            "dimensions": job.get("dimensions", {
                "d1_skill": 0, "d2_time": 0, "d3_interest": 0,
                "d4_ability": 0, "d5_culture": 0
            }),
            "weights_used": job.get("weights_used"),
            "explanation": job.get("explanation", ""),
        })

    # 7. 生成提升建议
    try:
        advice = generate_advice(user_profile, ranked_with_explain, top_n=10)
    except Exception as e:
        logger.warning(f"提升建议生成失败: {e}")
        advice = None

    return MatchResponse(
        jobs=job_results,
        free_hours_per_week=free_hours,
        free_slots=free_slots,
        total_jobs_scanned=len(jobs),
        advice=advice,
    )


@router.post("/parse-schedule", response_model=ParseScheduleResponse)
async def parse_schedule_api(req: ParseScheduleRequest):
    """单独解析课程表，前端实时预览用"""
    result = parse_schedule(req.schedule_text)
    return ParseScheduleResponse(**result)


@router.post("/feedback")
async def submit_feedback(req: FeedbackRequest):
    """记录用户对单条推荐结果的反馈，追加写入本地 JSON"""
    FEEDBACK_FILE.parent.mkdir(parents=True, exist_ok=True)
    existing: list = []
    if FEEDBACK_FILE.exists():
        try:
            existing = json.loads(FEEDBACK_FILE.read_text(encoding="utf-8"))
            if not isinstance(existing, list):
                existing = []
        except Exception:
            existing = []
    entry = {
        **req.model_dump(),
        "ts": datetime.now(timezone.utc).isoformat(),
    }
    existing.append(entry)
    FEEDBACK_FILE.write_text(
        json.dumps(existing, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    logger.info("feedback: job=%s helpful=%s", req.job_id, req.helpful)
    return {"ok": True}
