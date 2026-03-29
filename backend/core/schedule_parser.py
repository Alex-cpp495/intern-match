"""
课程表解析模块：使用 DeepSeek API 将自然语言课程表转为结构化空闲时间数据。

输入示例：
  "周一3-4节高数，周三全天实验，周五上午英语"

输出：
  {
    "schedule": {
      "周一": [["08:00","09:40"],["09:55","11:35"]],
      "周三": [["08:00","18:00"]],
      "周五": [["08:00","12:00"]]
    },
    "free_slots": {
      "周二": [["08:00","22:00"]],
      "周四": [["08:00","22:00"]],
      "周六": [["08:00","22:00"]],
      "周日": [["08:00","22:00"]]
    },
    "free_hours_per_week": 56
  }
"""

import json
import logging
import os
from openai import OpenAI

logger = logging.getLogger(__name__)

ALL_DAYS = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]

# 节次 → 时间段映射（标准大学作息）
PERIOD_MAP = {
    1: ("08:00", "08:50"),
    2: ("08:55", "09:45"),
    3: ("10:05", "10:55"),
    4: ("11:00", "11:50"),
    5: ("14:00", "14:50"),
    6: ("14:55", "15:45"),
    7: ("16:05", "16:55"),
    8: ("17:00", "17:50"),
    9: ("19:00", "19:50"),
    10: ("19:55", "20:45"),
}

SYSTEM_PROMPT = """你是一个课程表解析助手。用户会用自然语言描述他们的课程安排，
你需要将其转换为结构化 JSON 格式。

你必须返回一个合法的 JSON 对象，格式如下：
{
  "busy_slots": {
    "周一": [["08:00", "09:40"], ["10:05", "11:50"]],
    "周三": [["08:00", "18:00"]],
    "周五": [["08:00", "12:00"]]
  },
  "notes": "解析备注（可选）"
}

规则：
- 只包含有课的天，没有课的天不要出现在 busy_slots 中
- 时间格式为 HH:MM
- "全天" = ["08:00","18:00"]
- "上午" = ["08:00","12:00"]
- "下午" = ["13:00","18:00"]
- "晚上" = ["19:00","22:00"]
- 节次对应：1-2节=08:00-09:45，3-4节=10:05-11:50，5-6节=14:00-15:45，7-8节=16:05-17:50，9-10节=19:00-20:45
- 只返回 JSON，不要有其他文字
"""


def _get_client() -> OpenAI:
    api_key = os.getenv("DEEPSEEK_API_KEY", "")
    return OpenAI(api_key=api_key, base_url="https://api.deepseek.com")


def _time_to_minutes(t: str) -> int:
    h, m = map(int, t.split(":"))
    return h * 60 + m


def _calc_slot_hours(slots: list[list[str]]) -> float:
    total = 0
    for slot in slots:
        if len(slot) == 2:
            start = _time_to_minutes(slot[0])
            end = _time_to_minutes(slot[1])
            total += max(0, end - start)
    return total / 60


def _invert_to_free(busy_slots: dict[str, list]) -> tuple[dict[str, list], float]:
    """将忙碌时间段反转为空闲时间段，并计算每周总空闲小时数"""
    free_slots = {}
    total_free = 0.0
    day_start = "08:00"
    day_end = "22:00"

    for day in ALL_DAYS:
        if day not in busy_slots or not busy_slots[day]:
            free_slots[day] = [[day_start, day_end]]
            total_free += _calc_slot_hours([[day_start, day_end]])
            continue

        busy = sorted(busy_slots[day], key=lambda x: _time_to_minutes(x[0]))
        free = []
        cursor = _time_to_minutes(day_start)

        for slot in busy:
            slot_start = _time_to_minutes(slot[0])
            if cursor < slot_start:
                free.append([
                    f"{cursor // 60:02d}:{cursor % 60:02d}",
                    f"{slot_start // 60:02d}:{slot_start % 60:02d}"
                ])
            cursor = max(cursor, _time_to_minutes(slot[1]))

        day_end_min = _time_to_minutes(day_end)
        if cursor < day_end_min:
            free.append([
                f"{cursor // 60:02d}:{cursor % 60:02d}",
                day_end
            ])

        if free:
            free_slots[day] = free
            total_free += _calc_slot_hours(free)

    return free_slots, round(total_free, 1)


def parse_schedule(schedule_text: str) -> dict:
    """
    解析自然语言课程表，返回结构化空闲时间数据。
    若 DeepSeek API 不可用，使用备用简单规则解析。
    """
    if not schedule_text or not schedule_text.strip():
        free_slots, free_hours = _invert_to_free({})
        return {
            "busy_slots": {},
            "free_slots": free_slots,
            "free_hours_per_week": free_hours
        }

    busy_slots = {}

    # 尝试 DeepSeek 解析
    api_key = os.getenv("DEEPSEEK_API_KEY", "")
    if api_key:
        try:
            client = _get_client()
            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": f"请解析以下课程表：\n{schedule_text}"},
                ],
                temperature=0.1,
                max_tokens=800,
            )
            raw = response.choices[0].message.content.strip()
            # 提取 JSON
            if "```" in raw:
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            parsed = json.loads(raw)
            busy_slots = parsed.get("busy_slots", {})
            logger.info(f"DeepSeek 解析课程表成功，忙碌天数: {len(busy_slots)}")
        except Exception as e:
            logger.warning(f"DeepSeek 解析失败，使用规则解析: {e}")
            busy_slots = _rule_based_parse(schedule_text)
    else:
        logger.info("未设置 DEEPSEEK_API_KEY，使用规则解析")
        busy_slots = _rule_based_parse(schedule_text)

    free_slots, free_hours = _invert_to_free(busy_slots)
    return {
        "busy_slots": busy_slots,
        "free_slots": free_slots,
        "free_hours_per_week": free_hours
    }


def _rule_based_parse(text: str) -> dict[str, list]:
    """备用规则解析：处理简单格式"""
    import re
    busy: dict[str, list] = {}
    day_aliases = {
        "周一": "周一", "星期一": "周一", "monday": "周一",
        "周二": "周二", "星期二": "周二", "tuesday": "周二",
        "周三": "周三", "星期三": "周三", "wednesday": "周三",
        "周四": "周四", "星期四": "周四", "thursday": "周四",
        "周五": "周五", "星期五": "周五", "friday": "周五",
        "周六": "周六", "星期六": "周六", "saturday": "周六",
        "周日": "周日", "周天": "周日", "星期日": "周日", "sunday": "周日",
    }

    for alias, day in day_aliases.items():
        if alias in text:
            if day not in busy:
                busy[day] = []
            # 全天判断
            if "全天" in text[text.find(alias):text.find(alias) + 20]:
                busy[day] = [["08:00", "18:00"]]
            elif "上午" in text[text.find(alias):text.find(alias) + 20]:
                busy[day].append(["08:00", "12:00"])
            elif "下午" in text[text.find(alias):text.find(alias) + 20]:
                busy[day].append(["13:00", "18:00"])
            else:
                # 默认占用半天
                busy[day].append(["08:00", "12:00"])

    return busy
