import logging
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks
from scraper.shixiseng import CACHE_FILE, refresh_cache, get_all_jobs

logger = logging.getLogger(__name__)
router = APIRouter()


def _cache_last_updated_iso() -> str | None:
    try:
        if CACHE_FILE.exists():
            return datetime.fromtimestamp(
                CACHE_FILE.stat().st_mtime, tz=timezone.utc
            ).isoformat()
    except OSError:
        pass
    return None


@router.get("/jobs/count")
async def jobs_count():
    """岗位总数与缓存更新时间（供首页展示）"""
    jobs = get_all_jobs()
    return {"total": len(jobs), "last_updated": _cache_last_updated_iso()}


@router.get("/jobs")
async def list_jobs():
    """获取当前缓存的所有岗位"""
    jobs = get_all_jobs()
    return {
        "total": len(jobs),
        "last_updated": _cache_last_updated_iso(),
        "jobs": jobs,
    }


@router.post("/jobs/refresh")
async def trigger_refresh(background_tasks: BackgroundTasks):
    """触发爬虫刷新岗位缓存（后台执行，避免超时）"""
    background_tasks.add_task(_do_refresh)
    return {"message": "爬虫任务已启动，请稍后刷新页面查看最新数据"}


def _do_refresh():
    try:
        jobs = refresh_cache(force_scrape=True)
        logger.info(f"岗位缓存刷新完成，共 {len(jobs)} 条")
    except Exception as e:
        logger.error(f"爬虫刷新失败: {e}")
