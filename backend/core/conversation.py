"""
对话式信息收集引擎
使用 DeepSeek 驱动多轮对话，逐步收集用户实习偏好，信息充足时输出结构化画像。

每轮对话两步走：
  Step 1 — 从对话历史中提取结构化字段（DeepSeek）
  Step 2 — 生成引导式回复（DeepSeek）

状态：
  collecting → 信息不足，继续追问
  ready      → 信息足够，可触发匹配算法
"""

from __future__ import annotations

import json
import logging
import os
import uuid
import time
from typing import Optional
from openai import OpenAI

logger = logging.getLogger(__name__)

# ── 内存会话存储（黑客松够用） ──
_sessions: dict[str, dict] = {}
SESSION_TTL = 3600  # 1 小时过期

# ─────────────────────────────────────────────
# 系统提示词
# ─────────────────────────────────────────────

_CHAT_SYSTEM = """你是一位主动引导型的实习顾问，像真人顾问一样一步步帮大学生梳理实习需求。

== 你的引导节奏（严格按顺序推进） ==

阶段一【身份】：问专业和年级
阶段二【技能】：问掌握的具体技能（工具、语言、软件）
阶段三【方向】：问想从事什么类型的岗位/行业方向
阶段四【时间段】：问想什么时候开始实习——暑期、在读(课余兼职)、寒假，还是随时都可以
阶段五【时间量】：仅在以下情况才问——"在读"且对话里从未提及每周天数或课程安排。
   若阶段四是暑期/寒假/随时，跳过。若用户在任意之前的消息里提过"X天""X小时"或课表，跳过。
阶段六【偏好】（可选）：问公司规模/行业偏好，或是否接受远程
阶段七【确认】：信息齐了，做简短总结确认，在回复末尾单独一行输出 [PROFILE_READY]

== 已收集信息（必须遵守！） ==
{collected_summary}

⚠️ 重要规则：上面"已收集信息"里有的字段，绝对不能再问！
   - 已有专业年级 → 不能再问专业或年级
   - 已有技能 → 不能再问技能
   - 已有方向 → 不能再问方向
   - 已有实习时间段（暑期/在读等）→ 不能再问
   - 已有时间安排 → 不能再问时间
   用户刚才说的内容也要纳入，不能忽略。

== 回复格式规范 ==
1. 先用 1 句话自然回应/确认用户刚说的内容（要有实质呼应，不要只是"好的"）
2. 然后问当前阶段最重要的那 1 个问题，语气口语化、自然
3. 如果用户的回答含糊，先追问澄清，不要跳到下一个阶段
4. 每条回复控制在 2-4 句话，简洁干脆，不要列清单、不要加 emoji
5. 绝不在一条消息里问两个以上的问题
6. 当阶段一到三都有内容、且满足以下任一条件时，做简短总结并在末尾单独一行输出 [PROFILE_READY]：
   - 实习时间段是 暑期/寒假/随时
   - 实习时间段是 在读，且已知每周天数或课程安排
   - 未提时间段，但已知课程安排或每周天数
"""

_EXTRACT_SYSTEM = """从对话记录中提取用户的实习偏好信息，严格返回 JSON，不要有其他文字。

提取规则：
- major: 专业名称
- grade: 只能是 大一/大二/大三/大四/研究生 之一
- skills: 具体技能列表，如 Python/Java/SQL/Excel/Figma 等
- interests: 岗位方向列表，如 数据分析/量化交易/前端开发/产品经理/市场运营 等
- intern_period: 实习时间段，只能是以下之一：
    "暑期"（暑假/夏天/7-8月/summer）
    "寒假"（寒假/春节/1-2月/winter）
    "在读"（在学期间/课余/兼职/学期中）
    "随时"（随时/全职/毕业/不限）
    ""（未提及）
- schedule_text: 用户描述课程/时间安排的原话，保留自然语言
- has_project: 用户提到有项目经验/实习经历则为 true
- preferences.company_size: 大厂/中型企业/初创/高校/不限
- preferences.industry: 行业方向
- preferences.work_env: 技术/创意/稳定/扁平快节奏/学术/不限

没有提到的字段留空字符串或空数组，不要猜测。

输出格式（严格 JSON，无其他内容）：
{
  "major": "",
  "grade": "",
  "skills": [],
  "interests": [],
  "intern_period": "",
  "schedule_text": "",
  "has_project": false,
  "preferences": {
    "company_size": "",
    "industry": "",
    "work_env": ""
  }
}"""


# ─────────────────────────────────────────────
# 工具函数
# ─────────────────────────────────────────────

def _get_client() -> OpenAI:
    return OpenAI(
        api_key=os.getenv("DEEPSEEK_API_KEY", ""),
        base_url="https://api.deepseek.com",
    )


def _collected_summary(profile: dict) -> str:
    """将当前已收集信息格式化为简洁摘要，注入到系统提示词中"""
    lines = []
    if profile.get("major"):
        lines.append(f"专业年级: {profile['major']} {profile.get('grade', '')}")
    if profile.get("skills"):
        lines.append(f"技能: {', '.join(profile['skills'])}")
    if profile.get("interests"):
        lines.append(f"兴趣方向: {', '.join(profile['interests'])}")
    if profile.get("intern_period"):
        lines.append(f"实习时间段: {profile['intern_period']}")
    if profile.get("schedule_text"):
        lines.append(f"时间安排: {profile['schedule_text'][:60]}")
    if profile.get("has_project"):
        lines.append("有相关项目经验")
    prefs = profile.get("preferences", {})
    pref_parts = [v for v in prefs.values() if v and v != "不限"]
    if pref_parts:
        lines.append(f"企业偏好: {', '.join(pref_parts)}")
    return "\n".join(lines) if lines else "（尚未收集到任何信息）"


def _is_ready(profile: dict) -> bool:
    """判断是否已收集到足够信息可触发匹配"""
    has_identity = bool(profile.get("major") or profile.get("grade"))
    has_skills = len(profile.get("skills", [])) >= 1
    has_interests = len(profile.get("interests", [])) >= 1

    intern_period = profile.get("intern_period", "")
    has_schedule = bool(profile.get("schedule_text"))

    # 暑期/寒假/随时 不需要课程表
    if intern_period in ("暑期", "寒假", "随时"):
        has_time = True
    elif intern_period == "在读":
        # 在读时有课程表即可；若无课表但有时间段本身也算（天数由下游估算）
        has_time = has_schedule or True   # 说了"在读"就认为时间信息足够
    else:
        has_time = has_schedule

    return has_identity and has_skills and has_interests and has_time


def _merge_extracted(base: dict, extracted: dict) -> dict:
    """将 extracted 中非空字段合并到 base"""
    merged = dict(base)
    for key, val in extracted.items():
        if key == "preferences":
            merged_prefs = dict(merged.get("preferences", {}))
            for k, v in val.items():
                if v:
                    merged_prefs[k] = v
            merged["preferences"] = merged_prefs
        elif key == "skills" and val:
            existing = set(merged.get("skills", []))
            merged["skills"] = list(existing | set(val))
        elif key == "interests" and val:
            existing = set(merged.get("interests", []))
            merged["interests"] = list(existing | set(val))
        elif key == "has_project":
            merged["has_project"] = merged.get("has_project", False) or bool(val)
        elif val:
            merged[key] = val
    return merged


def _extract_profile(history: list[dict], current: dict) -> dict:
    """使用 DeepSeek 从对话历史中提取结构化字段，与当前 profile 增量合并。"""
    conv_text = "\n".join(
        f"{'用户' if m['role'] == 'user' else '助手'}: {m['content']}"
        for m in history
        if m["role"] in ("user", "assistant")
    )
    try:
        client = _get_client()
        resp = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": _EXTRACT_SYSTEM},
                {"role": "user", "content": f"对话记录：\n{conv_text}"},
            ],
            temperature=0.0,
            max_tokens=600,
        )
        raw = resp.choices[0].message.content.strip()
        if "```" in raw:
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        extracted: dict = json.loads(raw)
        logger.info(
            f"提取成功: major={extracted.get('major')}, grade={extracted.get('grade')}, "
            f"skills={extracted.get('skills')}, interests={extracted.get('interests')}, "
            f"intern_period={extracted.get('intern_period')}, "
            f"schedule={bool(extracted.get('schedule_text'))}"
        )
        return _merge_extracted(current, extracted)
    except Exception as e:
        logger.error(f"DeepSeek 信息提取失败: {e}")
        raise


# ─────────────────────────────────────────────
# 会话管理
# ─────────────────────────────────────────────

_CONFIRM_KEYWORDS = {
    "是", "好", "开始", "行", "可以", "对", "嗯", "确认",
    "匹配", "来", "去", "好的", "ok", "yes", "start", "go",
    "开始匹配", "现在", "马上", "就这样", "没问题",
}
_DENY_KEYWORDS = {
    "不", "等", "还", "先", "补充", "添加", "更多", "再",
    "no", "nope", "wait", "更新", "改",
}


def _is_confirm(text: str) -> bool:
    """判断用户是否在确认开始匹配"""
    t = text.lower().strip()
    # 明确拒绝则否
    if any(kw in t for kw in _DENY_KEYWORDS):
        return False
    return any(kw in t for kw in _CONFIRM_KEYWORDS) or len(t) <= 6


def new_session() -> str:
    sid = str(uuid.uuid4())
    _sessions[sid] = {
        "history": [],
        "profile": {
            "major": "",
            "grade": "",
            "skills": [],
            "interests": [],
            "intern_period": "",
            "schedule_text": "",
            "has_project": False,
            "preferences": {"company_size": "", "industry": "", "work_env": ""},
        },
        "ready": False,
        "awaiting_confirm": False,   # 是否正在等待用户确认开始匹配
        "created_at": time.time(),
    }
    return sid


def get_session(sid: str) -> Optional[dict]:
    sess = _sessions.get(sid)
    if sess and time.time() - sess["created_at"] < SESSION_TTL:
        return sess
    return None


def get_session_snapshot(sid: str) -> Optional[dict]:
    """供前端恢复：返回可序列化的会话快照；过期或不存在则 None。"""
    sess = get_session(sid)
    if not sess:
        return None
    return {
        "session_id": sid,
        "history": list(sess["history"]),
        "profile": dict(sess["profile"]),
        "ready": bool(sess.get("ready", False)),
        "awaiting_confirm": bool(sess.get("awaiting_confirm", False)),
        "collected_fields": _build_collected(sess["profile"]),
    }


def restore_session_from_history(messages: list[dict]) -> dict:
    """
    服务端会话过期后，用客户端保存的完整消息列表重建会话并重新提取画像。
    返回：session_id, profile, ready, awaiting_confirm, collected_fields
    """
    cleanup_sessions()
    sid = new_session()
    sess = _sessions[sid]
    clean_history: list[dict] = []
    for m in messages:
        role = m.get("role")
        content = m.get("content")
        if role in ("user", "assistant") and content is not None and str(content).strip():
            clean_history.append({"role": role, "content": str(content)})
    sess["history"] = clean_history
    empty_profile = {
        "major": "",
        "grade": "",
        "skills": [],
        "interests": [],
        "intern_period": "",
        "schedule_text": "",
        "has_project": False,
        "preferences": {"company_size": "", "industry": "", "work_env": ""},
    }
    if clean_history:
        try:
            profile = _extract_profile(clean_history, empty_profile)
        except Exception as e:
            logger.error(f"恢复会话时重新提取画像失败: {e}")
            profile = empty_profile
    else:
        profile = empty_profile
    sess["profile"] = profile
    is_ready = _is_ready(profile)
    sess["ready"] = is_ready
    sess["awaiting_confirm"] = False
    collected = _build_collected(profile)
    return {
        "session_id": sid,
        "profile": profile,
        "ready": is_ready,
        "awaiting_confirm": False,
        "collected_fields": collected,
    }


def cleanup_sessions():
    """清理过期会话"""
    now = time.time()
    expired = [sid for sid, s in _sessions.items() if now - s["created_at"] > SESSION_TTL]
    for sid in expired:
        del _sessions[sid]


# ─────────────────────────────────────────────
# 主对话接口
# ─────────────────────────────────────────────

def chat_turn(session_id: str, user_message: str, history_override: Optional[list] = None) -> dict:
    """
    处理一轮对话，返回：
    {
      "session_id": str,
      "reply": str,
      "profile": dict,
      "ready": bool,
      "awaiting_confirm": bool,
      "action": str | None,   # "start_match" 表示用户确认，前端应自动触发匹配
      "collected_fields": list[str]
    }
    """
    sess = get_session(session_id)
    if not sess:
        session_id = new_session()
        sess = get_session(session_id)

    # 编辑历史消息时：用前端传来的截断历史重置 session
    if history_override is not None:
        sess["history"] = list(history_override)
        sess["ready"] = False
        sess["awaiting_confirm"] = False
        # 从截断历史重新提取 profile
        empty_profile = {
            "major": "", "grade": "", "skills": [], "interests": [],
            "intern_period": "", "schedule_text": "", "has_project": False,
            "preferences": {"company_size": "", "industry": "", "work_env": ""},
        }
        try:
            sess["profile"] = _extract_profile(history_override, empty_profile) if history_override else empty_profile
        except Exception:
            sess["profile"] = empty_profile

    history: list[dict] = sess["history"]
    profile: dict = sess["profile"]
    awaiting_confirm: bool = sess.get("awaiting_confirm", False)

    history.append({"role": "user", "content": user_message})

    # ── 特殊路径：正在等待用户确认开始匹配 ──
    if awaiting_confirm and sess.get("ready", False):
        if _is_confirm(user_message):
            reply_clean = "好的，马上为你匹配最合适的实习机会，请稍候！"
            history.append({"role": "assistant", "content": reply_clean})
            collected = _build_collected(profile)
            return {
                "session_id": session_id,
                "reply": reply_clean,
                "profile": profile,
                "ready": True,
                "awaiting_confirm": False,
                "action": "start_match",
                "collected_fields": collected,
            }
        else:
            # 用户想补充更多信息，退出确认状态继续对话
            sess["awaiting_confirm"] = False
            awaiting_confirm = False

    # ── Step 1: DeepSeek 提取结构化信息 ──
    try:
        profile = _extract_profile(history, profile)
        sess["profile"] = profile
    except Exception as e:
        logger.error(f"信息提取异常，保持上一轮 profile: {e}")

    # ── Step 2: DeepSeek 生成引导回复 ──
    client = _get_client()
    system_content = _CHAT_SYSTEM.format(collected_summary=_collected_summary(profile))
    messages = [{"role": "system", "content": system_content}] + history
    resp = client.chat.completions.create(
        model="deepseek-chat",
        messages=messages,
        temperature=0.7,
        max_tokens=400,
    )
    reply = resp.choices[0].message.content.strip()
    logger.info(f"DeepSeek 回复成功，长度={len(reply)}")

    # ── Step 3: 检测 ready，进入确认阶段 ──
    profile_ready_in_reply = "[PROFILE_READY]" in reply
    reply_clean = reply.replace("[PROFILE_READY]", "").strip()
    is_ready = _is_ready(profile) or profile_ready_in_reply

    if is_ready and not sess.get("ready", False):
        # 首次变为 ready：进入等待确认状态
        sess["awaiting_confirm"] = True
    sess["ready"] = is_ready

    history.append({"role": "assistant", "content": reply_clean})

    collected = _build_collected(profile)

    return {
        "session_id": session_id,
        "reply": reply_clean,
        "profile": profile,
        "ready": is_ready,
        "awaiting_confirm": sess.get("awaiting_confirm", False),
        "action": None,
        "collected_fields": collected,
    }


def _build_collected(profile: dict) -> list[str]:
    """构建已收集字段列表"""
    collected = []
    if profile.get("major") or profile.get("grade"):
        collected.append("专业年级")
    if profile.get("skills"):
        collected.append("技能")
    if profile.get("interests"):
        collected.append("兴趣方向")
    if profile.get("intern_period"):
        collected.append(f"实习时间段({profile['intern_period']})")
    if profile.get("schedule_text"):
        collected.append("时间安排")
    if profile.get("preferences", {}).get("company_size") or \
       profile.get("preferences", {}).get("industry"):
        collected.append("企业偏好")
    return collected


def get_greeting() -> str:
    """首次进入时的开场白——直接用第一个问题开场"""
    return (
        "你好，我来帮你找合适的实习。\n\n"
        "先问你个基本情况——你是什么专业的，现在大几？"
    )
