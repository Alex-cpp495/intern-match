import logging
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional
from fastapi.responses import JSONResponse

from core.conversation import (
    chat_turn,
    new_session,
    get_greeting,
    get_session_snapshot,
    restore_session_from_history,
)

logger = logging.getLogger(__name__)
router = APIRouter()


class ChatRequest(BaseModel):
    session_id: Optional[str] = None
    message: str
    history_override: Optional[list] = None


class RestoreChatRequest(BaseModel):
    messages: list


class ChatResponse(BaseModel):
    session_id: str
    reply: str
    profile: dict
    ready: bool
    awaiting_confirm: bool = False
    action: Optional[str] = None
    collected_fields: list[str]


@router.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    """对话式信息收集接口"""
    sid = req.session_id or new_session()
    result = chat_turn(sid, req.message, history_override=req.history_override)
    return ChatResponse(**result)


@router.get("/chat/greeting")
async def greeting():
    """获取开场白"""
    sid = new_session()
    return {"session_id": sid, "reply": get_greeting()}


@router.get("/chat/session/{session_id}")
async def get_chat_session(session_id: str):
    """若会话仍在服务端内存且未过期，返回完整状态供前端恢复。"""
    snap = get_session_snapshot(session_id)
    if not snap:
        return JSONResponse({"ok": False}, status_code=404)
    return {"ok": True, **snap}


@router.post("/chat/restore")
async def restore_chat(req: RestoreChatRequest):
    """会话过期后根据客户端保存的消息列表重建 session。"""
    try:
        data = restore_session_from_history(list(req.messages))
        return {"ok": True, **data}
    except Exception as e:
        logger.exception("restore_chat 失败: %s", e)
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)
