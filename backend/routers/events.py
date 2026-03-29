import logging
from urllib.parse import urlparse, unquote

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from typing import Optional
from scraper.unnc_events import get_cached_events, refresh_events_cache
from scraper.wechat_articles import (
    get_cached_articles,
    refresh_wechat_cache,
    repair_wechat_urls_from_cache,
)
from scraper.careers_lectures import get_cached_lectures, refresh_careers_cache
from scraper.careers_jobfairs import get_cached_jobfairs, refresh_jobfairs_cache
from scraper.careers_teachins import get_cached_teachins, refresh_teachins_cache
from scraper.campus_refresh import refresh_all_campus_caches

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/campus/refresh-all")
async def refresh_all_campus(background_tasks: BackgroundTasks):
    """
    后台一次性刷新：官网活动、Careers 讲座、招聘会、宣讲会（与日历合并数据源一致）。
    与每日定时任务相同逻辑，供前端「刷新」或手动触发。
    """
    background_tasks.add_task(refresh_all_campus_caches)
    return {
        "message": "校园活动数据已在后台刷新（官网 + Careers），完成后刷新页面或稍候再点刷新即可看到更新",
    }


class EventItem(BaseModel):
    title: str
    date_start: str
    date_end: str
    time_start: str
    time_end: str
    location: str
    link: str
    description: str


class EventsResponse(BaseModel):
    events: list[EventItem]
    total: int


class LectureItem(BaseModel):
    id: str = ""
    title: str
    date_start: str
    date_end: str
    time_start: str
    time_end: str
    location: str
    link: str
    status: str
    description: str
    organizer: str = ""


class LecturesResponse(BaseModel):
    lectures: list[LectureItem]
    total: int


class ArticleItem(BaseModel):
    title: str
    date: str
    summary: str
    account: str
    sogou_link: str
    img_url: str
    content: str
    wechat_url: str
    search_query: str = ""


class ArticlesResponse(BaseModel):
    articles: list[ArticleItem]
    total: int


@router.get("/events", response_model=EventsResponse)
async def list_events():
    """获取 UNNC 校园活动列表（读缓存，首次自动爬取）"""
    events = get_cached_events()
    return EventsResponse(events=[EventItem(**e) for e in events], total=len(events))


@router.post("/events/refresh")
async def refresh_events(background_tasks: BackgroundTasks):
    """后台刷新活动缓存"""
    background_tasks.add_task(refresh_events_cache)
    return {"message": "活动缓存刷新已在后台启动"}


@router.get("/lectures", response_model=LecturesResponse)
async def list_lectures():
    """获取 Careers 就业讲座列表（仅未举办的活动，读缓存，首次自动爬取）"""
    lectures = get_cached_lectures()
    return LecturesResponse(
        lectures=[LectureItem(**lec) for lec in lectures],
        total=len(lectures),
    )


@router.post("/lectures/refresh")
async def refresh_lectures(background_tasks: BackgroundTasks):
    """后台刷新 Careers 讲座缓存"""
    background_tasks.add_task(refresh_careers_cache)
    return {"message": "Careers 讲座缓存刷新已在后台启动"}


class JobfairItem(BaseModel):
    id: str = ""
    title: str
    date_start: str
    date_end: str
    time_start: str = ""
    time_end: str = ""
    location: str
    link: str
    status: str
    type: str = "jobfair"


class JobfairsResponse(BaseModel):
    jobfairs: list[JobfairItem]
    total: int


@router.get("/jobfairs", response_model=JobfairsResponse)
async def list_jobfairs():
    """获取 Careers 招聘会列表（读缓存，首次自动爬取）"""
    fairs = get_cached_jobfairs()
    return JobfairsResponse(
        jobfairs=[JobfairItem(**f) for f in fairs],
        total=len(fairs),
    )


@router.post("/jobfairs/refresh")
async def refresh_jobfairs(background_tasks: BackgroundTasks):
    """后台刷新招聘会缓存"""
    background_tasks.add_task(refresh_jobfairs_cache)
    return {"message": "招聘会缓存刷新已在后台启动"}


class TeachinItem(BaseModel):
    id: str = ""
    title: str
    date_start: str
    date_end: str
    time_start: str = ""
    time_end: str = ""
    location: str
    link: str
    status: str
    type: str = "teachin"


class TeachinsResponse(BaseModel):
    teachins: list[TeachinItem]
    total: int


@router.get("/teachins", response_model=TeachinsResponse)
async def list_teachins():
    """获取 Careers 企业宣讲会列表（读缓存，首次自动爬取）"""
    items = get_cached_teachins()
    return TeachinsResponse(
        teachins=[TeachinItem(**t) for t in items],
        total=len(items),
    )


@router.post("/teachins/refresh")
async def refresh_teachins(background_tasks: BackgroundTasks):
    """后台刷新宣讲会缓存"""
    background_tasks.add_task(refresh_teachins_cache)
    return {"message": "宣讲会缓存刷新已在后台启动"}


@router.get("/articles/open-sogou")
async def open_article_via_sogou(url: str = Query(..., min_length=24, max_length=4096)):
    """
    浏览器打开搜狗微信中转链，由搜狗页面 JS 生成短时 mp 链再跳转。
    勿把缓存里的 mp?s?src=11&signature=... 直链给用户（会过期）；应优先走本接口。
    """
    raw = unquote(url).strip()
    parsed = urlparse(raw)
    if parsed.scheme not in ("http", "https"):
        raise HTTPException(status_code=400, detail="invalid scheme")
    host = (parsed.hostname or "").lower()
    if host != "weixin.sogou.com":
        raise HTTPException(status_code=400, detail="invalid host")
    path = parsed.path or ""
    if "/link" not in path:
        raise HTTPException(status_code=400, detail="invalid path")
    return RedirectResponse(url=raw, status_code=302)


@router.get("/articles", response_model=ArticlesResponse)
async def list_articles():
    """获取 HealthyUunnc 微信公众号文章列表（读缓存，首次自动爬取）"""
    articles = get_cached_articles()
    return ArticlesResponse(articles=[ArticleItem(**a) for a in articles], total=len(articles))


@router.post("/articles/refresh")
async def refresh_articles(background_tasks: BackgroundTasks):
    """后台刷新微信文章缓存"""
    background_tasks.add_task(refresh_wechat_cache)
    return {"message": "文章缓存刷新已在后台启动"}


@router.post("/articles/repair-links")
async def repair_article_wechat_links(background_tasks: BackgroundTasks):
    """不重爬列表，仅根据已有 sogou_link 补全 wechat_url（供正文抓取等）；阅读原文请用 /articles/open-sogou"""
    background_tasks.add_task(repair_wechat_urls_from_cache)
    return {"message": "微信公众号链接修复已在后台启动，完成后刷新页面即可"}
