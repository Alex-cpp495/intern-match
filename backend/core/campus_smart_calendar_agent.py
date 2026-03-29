"""
校园「智能日历」— 高相关度活动筛选。

性能：不再使用 LangGraph 多轮工具循环（此前会触发多次 DeepSeek 调用 + 超大工具返回，极易超时）。
改为：Python 端拉取并压缩活动列表 → **单次** LLM 调用，只让模型输出 event_uid + 分数 + 理由，
服务端用本地缓存的活动字典补全字段，保证与数据库一致、响应快。
"""

from __future__ import annotations

import json
import logging
import os
import re
import uuid
from datetime import datetime, timedelta
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from models.smart_calendar_schemas import (
    FilteredEventOut,
    SmartCalendarPlanRequest,
    SmartCalendarPlanResponse,
    SmartFilterResult,
)
from routers.calendar import _filter_by_range, collect_merged_calendar_events

logger = logging.getLogger(__name__)

os.environ.setdefault("LANGCHAIN_TRACING_V2", "false")

DEFAULT_TZ = __import__("zoneinfo").ZoneInfo("Asia/Shanghai")

MAX_EVENTS_FOR_LLM = 48
GOALS_MAX_IN_PROMPT = 3200
FOCUS_MAX_IN_PROMPT = 600


def _now_local_iso() -> str:
    return datetime.now(DEFAULT_TZ).isoformat()


def _window_end_iso(days: int) -> str:
    return (datetime.now(DEFAULT_TZ) + timedelta(days=days)).isoformat()


def _check_conflict_inline(
    start_iso: str,
    busy: dict[str, list[list[str]]],
) -> bool:
    if not busy or not start_iso:
        return False
    try:
        dt = datetime.fromisoformat(start_iso.replace("Z", "+00:00")).astimezone(DEFAULT_TZ)
        day_names = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
        day = day_names[dt.weekday()]
        t_min = dt.hour * 60 + dt.minute
        for slot in busy.get(day, []):
            if len(slot) == 2:
                s = int(slot[0].split(":")[0]) * 60 + int(slot[0].split(":")[1])
                e = int(slot[1].split(":")[0]) * 60 + int(slot[1].split(":")[1])
                if s <= t_min < e:
                    return True
    except Exception:
        pass
    return False


def _full_event_dict(ev: Any, busy: dict[str, list[list[str]]] | None) -> dict[str, Any]:
    """供补全 FilteredEventOut 的完整字段。"""
    d: dict[str, Any] = {
        "uid": ev.uid,
        "title": ev.title,
        "start_iso": ev.start_iso or "",
        "end_iso": ev.end_iso or "",
        "all_day": ev.all_day,
        "busy": ev.busy,
        "source": ev.source.value,
        "location": ev.location or "",
        "url": (ev.url or "")[:300],
        "description": (ev.description or "")[:400],
        "categories": ev.categories or [],
    }
    if busy:
        d["timetable_conflict"] = _check_conflict_inline(d["start_iso"], busy)
    return d


def _compact_row_for_llm(ev: Any, busy: dict[str, list[list[str]]] | None) -> dict[str, Any]:
    """给 LLM 的极窄行，减小 token 与延迟。"""
    title = (ev.title or "")[:120]
    desc = (ev.description or "").replace("\n", " ")[:100]
    loc = (ev.location or "")[:60]
    conflict = bool(busy and _check_conflict_inline(ev.start_iso or "", busy))
    return {
        "uid": ev.uid,
        "title": title,
        "start": (ev.start_iso or "")[:32],
        "end": (ev.end_iso or "")[:32],
        "src": ev.source.value,
        "loc": loc,
        "note": desc,
        "课表冲突": conflict,
    }


def _collect_window_and_maps(
    horizon_days: int,
    busy: dict[str, list[list[str]]] | None,
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    days = int(max(7, min(horizon_days, 21)))
    events = collect_merged_calendar_events()
    filtered = _filter_by_range(events, _now_local_iso(), _window_end_iso(days))
    by_uid: dict[str, dict[str, Any]] = {}
    rows: list[dict[str, Any]] = []
    for ev in filtered[:MAX_EVENTS_FOR_LLM]:
        by_uid[ev.uid] = _full_event_dict(ev, busy)
        rows.append(_compact_row_for_llm(ev, busy))
    return rows, by_uid


def _get_plain_llm() -> ChatOpenAI:
    api_key = (os.getenv("DEEPSEEK_API_KEY") or "").strip()
    if not api_key:
        raise RuntimeError("未配置 DEEPSEEK_API_KEY")
    return ChatOpenAI(
        model="deepseek-chat",
        api_key=api_key,
        base_url="https://api.deepseek.com",
        temperature=0.25,
        timeout=90.0,
        max_retries=1,
        max_tokens=4096,
    )


_llm_plain: ChatOpenAI | None = None


def _llm() -> ChatOpenAI:
    global _llm_plain
    if _llm_plain is None:
        _llm_plain = _get_plain_llm()
    return _llm_plain


SYSTEM_SINGLE = """你是 NottFind「智能活动筛选」助手，服务宁波诺丁汉大学学生。

用户会提供目标描述 + 一段**压缩后的校园活动 JSON 数组**（每项含 uid/title/start/src/loc/note/课表冲突）。
你的任务：从中挑出与用户目标**相关度高**的活动。

硬性规则：
1. **禁止编造** uid；`event_uid` 必须来自列表中的 `uid`。
2. 选 **5～18** 条即可，按相关度从高到低在数组中排序。
3. `relevance_score` 取 0～1；`reason` 中文一句，若 `课表冲突` 为 true 须在 reason 里点明「与课表时间冲突」。
4. **只输出一个 JSON 对象**，不要 markdown、不要代码块、不要其它说明文字。

输出格式（严格遵守键名）：
{"summary":"一句话说明筛选思路","picks":[{"event_uid":"...","relevance_score":0.85,"reason":"..."}]}
"""


def _extract_json_object(text: str) -> dict[str, Any] | None:
    if not text or not isinstance(text, str):
        return None
    block = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    raw = block.group(1).strip() if block else None
    if not raw:
        i = text.find("{")
        if i >= 0:
            raw = text[i:]
    if not raw:
        return None
    try:
        return json.loads(raw)
    except Exception:
        return None


def _hydrate_from_picks(
    summary: str,
    picks: list[Any],
    by_uid: dict[str, dict[str, Any]],
) -> SmartFilterResult:
    out: list[FilteredEventOut] = []
    if not isinstance(picks, list):
        picks = []
    for p in picks[:50]:
        if not isinstance(p, dict):
            continue
        uid = str(p.get("event_uid") or p.get("uid") or "").strip()
        if not uid or uid not in by_uid:
            continue
        base = by_uid[uid]
        try:
            score = float(p.get("relevance_score", 0.5))
        except (TypeError, ValueError):
            score = 0.5
        score = max(0.0, min(1.0, score))
        reason = str(p.get("reason", ""))[:500]
        out.append(
            FilteredEventOut(
                event_uid=uid,
                title=str(base.get("title", "")),
                start_iso=str(base.get("start_iso", "")),
                end_iso=str(base.get("end_iso", "")),
                all_day=bool(base.get("all_day")),
                source=str(base.get("source", "")),
                location=str(base.get("location", "")),
                url=str(base.get("url", "")),
                description=str(base.get("description", "")),
                categories=list(base.get("categories") or []),
                relevance_score=score,
                reason=reason,
            )
        )
    out.sort(key=lambda x: -x.relevance_score)
    summ = (summary or "已根据你的描述完成筛选。")[:800]
    return SmartFilterResult(summary=summ, filtered_events=out)


def _try_full_smart_result(
    data: dict[str, Any],
    by_uid: dict[str, dict[str, Any]],
) -> SmartFilterResult | None:
    """若模型仍返回完整 filtered_events，则校验并尽量采纳。"""
    if "filtered_events" not in data:
        return None
    try:
        r = SmartFilterResult.model_validate(data)
    except Exception:
        return None
    fixed: list[FilteredEventOut] = []
    for fe in r.filtered_events:
        if fe.event_uid in by_uid:
            base = by_uid[fe.event_uid]
            fixed.append(
                FilteredEventOut(
                    event_uid=fe.event_uid,
                    title=base.get("title", fe.title),
                    start_iso=base.get("start_iso", fe.start_iso),
                    end_iso=base.get("end_iso", fe.end_iso),
                    all_day=base.get("all_day", fe.all_day),
                    source=base.get("source", fe.source),
                    location=base.get("location", fe.location),
                    url=base.get("url", fe.url),
                    description=base.get("description", fe.description),
                    categories=list(base.get("categories") or fe.categories),
                    relevance_score=fe.relevance_score,
                    reason=fe.reason,
                )
            )
    return SmartFilterResult(summary=r.summary, filtered_events=fixed)


def run_smart_calendar_plan(
    req: SmartCalendarPlanRequest,
    thread_id: str | None = None,
    timetable_busy: dict[str, list[list[str]]] | None = None,
) -> SmartCalendarPlanResponse:
    tid = (thread_id or "").strip() or uuid.uuid4().hex
    busy = timetable_busy or {}

    rows, by_uid = _collect_window_and_maps(req.horizon_days, busy if busy else None)
    if not rows:
        return SmartCalendarPlanResponse(
            result=SmartFilterResult(
                summary="当前时间窗口内没有可展示的校园活动数据。",
                filtered_events=[],
            ),
            agent_steps=0,
            model="deepseek-chat",
            thread_id=tid,
        )

    goals = (req.goals or "").strip()[:GOALS_MAX_IN_PROMPT]
    focus = "、".join(req.focus_areas) if req.focus_areas else "（未指定）"
    focus = focus[:FOCUS_MAX_IN_PROMPT]
    grade = (req.grade or "").strip() or "未填写"
    fu = (req.followup or "").strip()

    events_json = json.dumps(rows, ensure_ascii=False)
    if fu:
        human = (
            f"【用户追加要求】\n{fu[:900]}\n\n"
            f"【原目标摘要】\n{goals}\n\n"
            f"【关注方向】{focus}\n【年级】{grade}\n"
            f"【规划天数】约 {req.horizon_days} 天\n\n"
            f"【活动列表】\n{events_json}"
        )
    else:
        human = (
            f"【用户目标】\n{goals}\n\n"
            f"【关注方向】{focus}\n【年级】{grade}\n"
            f"【规划天数】约 {req.horizon_days} 天\n"
        )
        if busy:
            human += "\n（用户已导入课表；列表中「课表冲突」为 true 表示该活动开始时间落在课表时段内。）\n"
        human += f"\n【活动列表】\n{events_json}"

    try:
        resp = _llm().invoke(
            [
                SystemMessage(content=SYSTEM_SINGLE),
                HumanMessage(content=human),
            ]
        )
    except Exception:
        logger.exception("智能日历：LLM 调用失败")
        return SmartCalendarPlanResponse(
            result=SmartFilterResult(
                summary="模型请求失败，请稍后重试或缩短目标描述。",
                filtered_events=[],
            ),
            agent_steps=1,
            model="deepseek-chat",
            thread_id=tid,
        )

    content = getattr(resp, "content", None) or ""
    if isinstance(content, list):
        content = "".join(
            str(x) if not isinstance(x, dict) else str(x.get("text", ""))
            for x in content
        )

    data = _extract_json_object(str(content))
    result: SmartFilterResult | None = None
    if data:
        if isinstance(data.get("picks"), list):
            summary = str(data.get("summary") or "筛选完成。")
            result = _hydrate_from_picks(summary, data["picks"], by_uid)
        else:
            result = _try_full_smart_result(data, by_uid)

    if result is None or not result.filtered_events:
        logger.warning("智能日历：未能解析 picks 或结果为空，尝试兜底")
        if data and isinstance(data.get("picks"), list):
            result = _hydrate_from_picks(
                str(data.get("summary") or "解析不完整。"),
                data["picks"],
                by_uid,
            )
    if result is None or not result.filtered_events:
        result = SmartFilterResult(
            summary="未能解析模型输出，请稍后重试或简化「目标/关注方向」描述。",
            filtered_events=[],
        )

    return SmartCalendarPlanResponse(
        result=result,
        agent_steps=1,
        model="deepseek-chat",
        thread_id=tid,
    )
