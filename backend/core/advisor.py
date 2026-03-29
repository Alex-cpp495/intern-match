"""
提升建议模块：分析用户与 Top 岗位的差距，生成可执行的技能提升建议。

逻辑：
  1. 取匹配分最高的前 N 个岗位
  2. 统计这些岗位中频繁出现但用户缺失的技能
  3. 分析五维度中拉分最多的维度
  4. 用 DeepSeek 生成自然语言建议（可降级为规则版）
"""

import logging
import os
from collections import Counter
from typing import Any
from openai import OpenAI

logger = logging.getLogger(__name__)


def _find_skill_gaps(user_skills: list[str], top_jobs: list[dict]) -> list[dict]:
    """找出 Top 岗位中高频出现但用户缺失的技能"""
    user_lower = {s.lower() for s in user_skills}
    required_counter: Counter = Counter()
    for job in top_jobs:
        for skill in job.get("required_skills", []):
            required_counter[skill] += 1

    gaps = []
    for skill, count in required_counter.most_common(20):
        if skill.lower() not in user_lower:
            gaps.append({
                "skill": skill,
                "demand_count": count,
                "demand_ratio": round(count / max(len(top_jobs), 1), 2),
            })
    return gaps[:8]


def _find_weak_dimensions(top_jobs: list[dict]) -> list[dict]:
    """找出 Top 岗位中平均最弱的维度"""
    dim_keys = ["d1_skill", "d2_time", "d3_interest", "d4_ability", "d5_culture"]
    dim_labels = {
        "d1_skill": "技能匹配",
        "d2_time": "时间适配",
        "d3_interest": "兴趣契合",
        "d4_ability": "能力水平",
        "d5_culture": "企业适配",
    }
    dim_tips = {
        "d1_skill": "补充岗位高频要求的技能，可以通过在线课程或项目实践快速提升",
        "d2_time": "调整课程安排或考虑远程/兼职岗位，增加可用时间",
        "d3_interest": "拓宽求职方向，尝试关注更多相关领域的岗位",
        "d4_ability": "积累项目经验、参加竞赛或实验室科研来提升能力评估",
        "d5_culture": "适当放宽企业偏好，尝试不同规模和文化的公司",
    }

    if not top_jobs:
        return []

    dim_avgs = {}
    for key in dim_keys:
        values = [j.get("dimensions", {}).get(key, 0) for j in top_jobs]
        dim_avgs[key] = sum(values) / max(len(values), 1)

    sorted_dims = sorted(dim_avgs.items(), key=lambda x: x[1])
    weak = []
    for key, avg in sorted_dims:
        if avg < 0.7:
            weak.append({
                "dimension": key,
                "label": dim_labels[key],
                "avg_score": round(avg, 3),
                "tip": dim_tips[key],
            })
    return weak[:3]


def generate_advice(
    user_profile: dict[str, Any],
    ranked_jobs: list[dict[str, Any]],
    top_n: int = 10,
) -> dict:
    """
    生成提升建议。返回：
    {
      "skill_gaps": [...],
      "weak_dimensions": [...],
      "summary": "自然语言总结"
    }
    """
    top_jobs = ranked_jobs[:top_n]
    skill_gaps = _find_skill_gaps(user_profile.get("skills", []), top_jobs)
    weak_dims = _find_weak_dimensions(top_jobs)

    summary = _generate_summary(user_profile, skill_gaps, weak_dims)

    return {
        "skill_gaps": skill_gaps,
        "weak_dimensions": weak_dims,
        "summary": summary,
    }


def _generate_summary(
    user_profile: dict,
    skill_gaps: list[dict],
    weak_dims: list[dict],
) -> str:
    """用 DeepSeek 生成自然语言建议，失败时降级为规则版"""
    api_key = os.getenv("DEEPSEEK_API_KEY", "")

    gap_text = "、".join(g["skill"] for g in skill_gaps[:5]) if skill_gaps else "无明显缺口"
    weak_text = "、".join(f"{w['label']}({w['avg_score']:.0%})" for w in weak_dims) if weak_dims else "各维度表现均衡"
    grade = user_profile.get("grade", "")
    major = user_profile.get("major", "")

    if not api_key:
        return _rule_summary(major, grade, skill_gaps, weak_dims)

    try:
        client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
        prompt = f"""学生背景：{major} {grade}，已有技能：{', '.join(user_profile.get('skills', []))}

根据匹配分析：
- 岗位高频要求但该学生缺少的技能：{gap_text}
- 匹配中较弱的维度：{weak_text}

请生成 3-4 条简洁、可执行的提升建议（每条 1-2 句话），帮助学生提高实习匹配度。
语气积极鼓励，像学长给学弟学妹的建议。只返回建议文字，用序号列出。"""

        resp = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": "你是一位资深校园求职导师，给大学生提供简洁实用的提升建议。"},
                {"role": "user", "content": prompt},
            ],
            temperature=0.7,
            max_tokens=400,
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        logger.warning(f"DeepSeek 建议生成失败: {e}")
        return _rule_summary(major, grade, skill_gaps, weak_dims)


def _rule_summary(major: str, grade: str, skill_gaps: list[dict], weak_dims: list[dict]) -> str:
    parts = []
    if skill_gaps:
        top3 = [g["skill"] for g in skill_gaps[:3]]
        parts.append(f"建议优先学习 {', '.join(top3)}，这些是目标岗位最常要求的技能")
    if weak_dims:
        for w in weak_dims[:2]:
            parts.append(w["tip"])
    if not parts:
        parts.append("你的综合匹配度不错，保持现有优势，多投递尝试")
    return "。\n".join(parts) + "。"
