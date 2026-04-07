import asyncio
import logging
from urllib.parse import urlparse, unquote

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel, Field
from typing import Optional
from scraper.unnc_events import get_cached_events, refresh_events_cache
from scraper.wechat_articles import (
    SEARCH_QUERIES,
    add_custom_wechat_query,
    get_cached_articles,
    get_effective_search_queries,
    load_custom_queries,
    proxy_wechat_html_from_sogou,
    refresh_wechat_cache,
    remove_custom_wechat_query,
    repair_wechat_urls_from_cache,
    resolve_fresh_wechat_url_from_sogou,
)
from scraper.careers_lectures import get_cached_lectures, refresh_careers_cache
from scraper.careers_jobfairs import get_cached_jobfairs, refresh_jobfairs_cache
from scraper.careers_teachins import get_cached_teachins, refresh_teachins_cache
from scraper.campus_refresh import refresh_all_campus_caches
from scraper.wechat_event_extractor import (
    get_cached_wechat_events,
    refresh_wechat_events_cache,
)

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
        "message": "校园活动数据已在后台刷新（官网 + Careers + 微信文章 + 公众号活动 AI 抽取），完成后刷新页面或稍候再点刷新即可看到更新",
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


class WechatQueryRow(BaseModel):
    query: str
    label: str = ""
    max_pages: int = 3


class WechatSearchQueriesResponse(BaseModel):
    """内置搜狗关键词 + 用户自定义关键词（合并后用于爬取）。"""

    builtin: list[WechatQueryRow]
    custom: list[WechatQueryRow]
    effective_query_count: int


class WechatCustomQueryBody(BaseModel):
    query: str = Field(..., min_length=1, max_length=80, description="搜狗微信搜索关键词，如公众号名、学校名")
    label: str = Field("", max_length=64, description="展示用标签，默认同关键词")
    max_pages: int = Field(3, ge=1, le=10, description="该关键词最多翻页数")
    refresh_articles_now: bool = Field(
        False,
        description="为 true 时在后台立即重爬全部关键词（含新增项，耗时较长）",
    )


def _row_from_cfg(q: dict) -> WechatQueryRow:
    return WechatQueryRow(
        query=str(q.get("query", "")),
        label=str(q.get("label", q.get("query", "")) or q.get("query", "")),
        max_pages=int(q.get("max_pages", 3)),
    )


class WechatEventItem(BaseModel):
    title: str
    date_start: str = ""
    date_end: str = ""
    time_start: str = ""
    time_end: str = ""
    location: str = ""
    description: str = ""
    categories: list[str] = []
    sogou_link: str = ""
    account: str = ""
    source_article_title: str = ""


class WechatEventsResponse(BaseModel):
    events: list[WechatEventItem]
    total: int


def _wechat_event_item_from_dict(e: dict) -> WechatEventItem:
    cats = e.get("categories")
    if not isinstance(cats, list):
        cats = []
    return WechatEventItem(
        title=str(e.get("title") or ""),
        date_start=str(e.get("date_start") or ""),
        date_end=str(e.get("date_end") or ""),
        time_start=str(e.get("time_start") or ""),
        time_end=str(e.get("time_end") or ""),
        location=str(e.get("location") or ""),
        description=str(e.get("description") or ""),
        categories=[str(x) for x in cats if x is not None],
        sogou_link=str(e.get("sogou_link") or ""),
        account=str(e.get("account") or ""),
        source_article_title=str(e.get("source_article_title") or ""),
    )


@router.get("/wechat-events", response_model=WechatEventsResponse)
async def list_wechat_events():
    """从缓存读取 AI 抽取的公众号活动（与合并日历同源）。"""
    raw = get_cached_wechat_events()
    items: list[WechatEventItem] = []
    for e in raw:
        if not isinstance(e, dict):
            continue
        try:
            items.append(_wechat_event_item_from_dict(e))
        except Exception:
            logger.debug("跳过无效 wechat_event 条目", exc_info=True)
    return WechatEventsResponse(events=items, total=len(items))


@router.post("/wechat-events/refresh")
async def refresh_wechat_events(background_tasks: BackgroundTasks):
    """后台重新跑 DeepSeek 抽取（耗时与文章数成正比，需配置 DEEPSEEK_API_KEY）。"""
    background_tasks.add_task(refresh_wechat_events_cache)
    return {"message": "公众号活动 AI 抽取已在后台启动，完成后刷新校园页即可"}


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


def _normalize_sogou_query_url(url: str) -> str:
    raw = url.strip()
    while True:
        nxt = unquote(raw)
        if nxt == raw:
            break
        raw = nxt
    return raw


@router.get("/articles/open-sogou")
async def open_article_via_sogou(url: str = Query(..., min_length=24, max_length=8192)):
    """
    代理模式：服务端用搜狗 cookie 获取微信文章 HTML，直接返回给浏览器。
    避免 302 重定向后微信因 Referer 校验拒绝访问。
    """
    raw = _normalize_sogou_query_url(url)
    parsed = urlparse(raw)
    if parsed.scheme not in ("http", "https"):
        raise HTTPException(status_code=400, detail="invalid scheme")
    host = (parsed.hostname or "").lower()
    if host != "weixin.sogou.com":
        raise HTTPException(status_code=400, detail="invalid host")
    path_l = (parsed.path or "").lower()
    q = parsed.query or ""
    if "/link" not in path_l and "link" not in path_l and "url=" not in q:
        raise HTTPException(status_code=400, detail="invalid sogou url")

    try:
        html = await asyncio.to_thread(proxy_wechat_html_from_sogou, raw)
    except Exception as e:
        logger.warning("open-sogou 代理异常: %s", e)
        html = ""
    if html:
        return HTMLResponse(content=html, status_code=200)
    return HTMLResponse(
        content="<html><body><h2>无法加载文章，请稍后重试</h2>"
        f'<p><a href="{raw}" target="_blank">尝试直接访问搜狗链接</a></p>'
        "</body></html>",
        status_code=502,
    )


@router.get("/articles/search-queries", response_model=WechatSearchQueriesResponse)
async def get_article_search_queries():
    """内置与自定义搜狗搜索关键词；合并后的总数见 effective_query_count。"""
    custom_raw = load_custom_queries()
    builtin = [_row_from_cfg(q) for q in SEARCH_QUERIES]
    custom = [
        _row_from_cfg(x)
        for x in custom_raw
        if isinstance(x, dict) and str(x.get("query", "")).strip()
    ]
    return WechatSearchQueriesResponse(
        builtin=builtin,
        custom=custom,
        effective_query_count=len(get_effective_search_queries()),
    )


@router.post("/articles/custom-query")
async def post_article_custom_query(
    body: WechatCustomQueryBody,
    background_tasks: BackgroundTasks,
):
    """新增自定义搜狗关键词；与内置列表去重合并，下次爬取时纳入。"""
    try:
        add_custom_wechat_query(
            body.query.strip(),
            (body.label or "").strip(),
            body.max_pages,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if body.refresh_articles_now:
        background_tasks.add_task(refresh_wechat_cache, True)
        message = "已保存并已启动后台爬取微信文章，请数分钟后刷新本页查看。"
    else:
        message = "已保存。请点击本页右上角「刷新」以按新关键词爬取文章。"
    custom_raw = load_custom_queries()
    custom = [
        _row_from_cfg(x)
        for x in custom_raw
        if isinstance(x, dict) and str(x.get("query", "")).strip()
    ]
    return {"message": message, "custom": custom}


@router.delete("/articles/custom-query")
async def delete_article_custom_query(
    query: str = Query(..., min_length=1, max_length=80, description="要删除的关键词"),
):
    remove_custom_wechat_query(query)
    custom_raw = load_custom_queries()
    custom = [
        _row_from_cfg(x)
        for x in custom_raw
        if isinstance(x, dict) and str(x.get("query", "")).strip()
    ]
    return {"message": "已删除", "custom": custom}


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


# ─── wxmp 管理端点 ───


@router.get("/wxmp/status")
async def wxmp_status():
    """检查 wxmp（微信公众平台后台 API）的可用状态。"""
    from scraper.wechat_wxmp_adapter import is_wxmp_available, check_wxmp_session_valid

    available = is_wxmp_available()
    if not available:
        return {
            "available": False,
            "session_valid": False,
            "message": "wxmp 未配置（Cookie 文件不存在或 wxmp 库未安装），数据将 fallback 到搜狗爬虫",
        }
    session_info = await asyncio.to_thread(check_wxmp_session_valid)
    return {
        "available": True,
        "session_valid": session_info["valid"],
        "message": session_info["message"],
    }


class WxmpCookiesBody(BaseModel):
    cookies: dict = Field(..., description="微信公众平台 Cookie（JSON 对象，键值对形式）")


@router.post("/wxmp/cookies")
async def set_wxmp_cookies(body: WxmpCookiesBody):
    """
    保存微信公众平台 Cookie。

    获取方式：
    1. 浏览器登录 https://mp.weixin.qq.com
    2. F12 → Application → Cookies → 复制所有 cookie 为 JSON
    约 4 天后过期需重新获取。
    """
    import json as _json
    from scraper.wechat_wxmp_adapter import COOKIES_FILE, DATA_DIR

    if not body.cookies or not isinstance(body.cookies, dict):
        raise HTTPException(status_code=400, detail="cookies 必须是非空 JSON 对象")

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(COOKIES_FILE, "w", encoding="utf-8") as f:
        _json.dump(body.cookies, f, ensure_ascii=False, indent=2)
    logger.info("wxmp cookies 已保存到 %s", COOKIES_FILE)
    return {"message": "Cookie 已保存，可调用 GET /api/wxmp/status 验证是否生效"}
