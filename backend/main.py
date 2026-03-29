import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from db.database import init_db
from routers import auth, calendar, chat, events, jobs, match

load_dotenv()                          # 读 .env
load_dotenv(".env.example", override=False)  # 兜底：.env 没有时读 .env.example

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    Path(__file__).resolve().parent.joinpath("data").mkdir(parents=True, exist_ok=True)
    init_db()

    # 启动时预加载 embedding（可设置 SKIP_EMBEDDER_WARMUP=1 跳过，便于先起服务再配镜像）
    skip_warm = os.environ.get("SKIP_EMBEDDER_WARMUP", "").lower() in ("1", "true", "yes")
    if skip_warm:
        logger.info("已跳过启动时 embedding 预加载（SKIP_EMBEDDER_WARMUP=1），首次匹配时再加载模型")
    else:
        logger.info("预加载 sentence-transformers 模型...")
        from core.embedder import get_model

        get_model()
    # 初始化岗位缓存（加载 UNNC 预置数据）
    from scraper.shixiseng import get_all_jobs
    jobs_list = get_all_jobs()
    logger.info(f"已加载 {len(jobs_list)} 条岗位数据")

    # 每日定时全量爬取更新缓存（APScheduler，本地时间 03:00）
    scheduler = None
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        from apscheduler.triggers.cron import CronTrigger

        def run_scheduled_refresh():
            try:
                from scraper.shixiseng import refresh_cache

                refresh_cache(force_scrape=True)
                logger.info("定时岗位缓存刷新已完成")
            except Exception as e:
                logger.exception("定时爬虫失败: %s", e)

        def run_scheduled_campus_refresh():
            try:
                from scraper.campus_refresh import refresh_all_campus_caches

                refresh_all_campus_caches()
                logger.info("定时校园活动缓存刷新已完成")
            except Exception as e:
                logger.exception("定时校园活动刷新失败: %s", e)

        scheduler = BackgroundScheduler()
        scheduler.add_job(
            run_scheduled_refresh,
            CronTrigger(hour=3, minute=0),
            id="daily_jobs_refresh",
            replace_existing=True,
        )
        # 与岗位错开，减轻瞬时外网压力；数据源与 GET /calendar/merged 一致
        scheduler.add_job(
            run_scheduled_campus_refresh,
            CronTrigger(hour=4, minute=0),
            id="daily_campus_refresh",
            replace_existing=True,
        )
        scheduler.start()
        logger.info("已启动定时任务：每日 03:00 刷新岗位缓存，04:00 刷新校园活动缓存")
    except Exception as e:
        logger.warning("APScheduler 未启用: %s", e)

    yield

    if scheduler is not None:
        try:
            scheduler.shutdown(wait=False)
        except Exception:
            pass
    logger.info("服务关闭")


app = FastAPI(
    title="校园实习智能匹配 API",
    description="基于五维度算法 + AI 的校园实习推荐系统",
    version="1.0.0",
    lifespan=lifespan,
)

_raw_origins = os.environ.get("ALLOWED_ORIGINS", "").strip()
_allowed_origins = [o.strip() for o in _raw_origins.split(",") if o.strip()] if _raw_origins else ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api", tags=["认证"])
app.include_router(match.router, prefix="/api", tags=["匹配"])
app.include_router(jobs.router, prefix="/api", tags=["岗位"])
app.include_router(chat.router, prefix="/api", tags=["对话"])
app.include_router(events.router, prefix="/api", tags=["校园活动"])
app.include_router(calendar.router, prefix="/api", tags=["日历融合"])


@app.get("/")
async def root():
    return {"message": "校园实习智能匹配 API 运行中", "docs": "/docs"}


@app.get("/health")
async def health():
    return {"status": "ok"}
