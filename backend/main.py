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
        try:
            from core.embedder import get_model

            get_model()
        except Exception:
            logger.exception(
                "启动时 embedding 预加载失败，进程继续运行；可设 SKIP_EMBEDDER_WARMUP=1 跳过，"
                "或稍后访问 GET /api/warmup / 首次匹配时再加载模型"
            )

    # 初始化岗位缓存（加载 UNNC 预置数据）
    try:
        from scraper.shixiseng import get_all_jobs

        jobs_list = get_all_jobs()
        logger.info("已加载 %d 条岗位数据", len(jobs_list))
    except Exception:
        logger.exception(
            "启动时加载岗位数据失败，进程继续运行；岗位列表可能为空，可检查 jobs_cache 或 POST /api/jobs/refresh"
        )

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
if os.environ.get("APP_ENV", "").lower() in ("production", "prod") and not _raw_origins:
    raise RuntimeError(
        "APP_ENV=production 时必须设置 ALLOWED_ORIGINS（逗号分隔的前端 HTTPS 域名，例如 https://app.example.com）"
    )

if _raw_origins:
    _allowed_origins = [o.strip() for o in _raw_origins.split(",") if o.strip()]
else:
    # 避免 allow_credentials=True 时与 Origin: * 组合带来的浏览器与安全策略问题
    _allowed_origins = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3001",
    ]
    logger.warning(
        "ALLOWED_ORIGINS 未设置：仅允许本地默认前端源 %s。生产环境请设置 ALLOWED_ORIGINS。",
        _allowed_origins,
    )

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


@app.get("/api/warmup")
async def warmup():
    """浏览器直接打开此地址即可预加载模型，展示前约等 1～3 分钟"""
    import asyncio
    from core.embedder import get_model
    await asyncio.to_thread(get_model)
    return {"status": "model_ready"}
