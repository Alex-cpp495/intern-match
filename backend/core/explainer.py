"""
推荐理由生成模块：使用 DeepSeek API，根据五维度得分生成个性化推荐文字。
"""

import os
import logging
from openai import OpenAI

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """你是一位专业的校园求职顾问，语气亲切、专业。
根据学生的个人信息和岗位匹配得分，生成简洁的个性化推荐理由（2-3句话，不超过100字）。
要具体指出匹配的优势和需要注意的不足，语气积极鼓励。只返回推荐理由文字，不要有其他内容。"""


def _get_client() -> OpenAI:
    api_key = os.getenv("DEEPSEEK_API_KEY", "")
    return OpenAI(api_key=api_key, base_url="https://api.deepseek.com")


def _rule_based_explain(user_profile: dict, job: dict, scores: dict) -> str:
    """备用规则生成，无需 API"""
    d1 = scores.get("d1_skill", 0)
    d2 = scores.get("d2_time", 0)
    d4 = scores.get("d4_ability", 0)
    total = scores.get("total_score", 0)

    parts = []
    if d1 >= 0.7:
        parts.append("你的技能与该岗位高度匹配")
    elif d1 >= 0.5:
        parts.append("你的技能与该岗位基本匹配")
    else:
        parts.append("该岗位对你是一次技能拓展机会")

    if d2 >= 0.8:
        parts.append("时间安排也非常契合")
    elif d2 >= 0.5:
        parts.append("时间安排勉强可以满足岗位要求")
    else:
        parts.append("注意该岗位时间要求较高，需合理规划课表")

    if d4 < 0.7:
        parts.append("经验尚不完全满足要求，但可以用项目经历弥补")

    grade = user_profile.get("grade", "")
    job_title = job.get("title", "该岗位")
    return f"{'，'.join(parts)}。综合评分 {total*100:.0f} 分，{'强烈' if total >= 0.75 else ''}推荐你申请《{job_title}》。"


def generate_explanation(user_profile: dict, job: dict, score_result: dict) -> str:
    """为单个岗位匹配结果生成推荐理由"""
    api_key = os.getenv("DEEPSEEK_API_KEY", "")
    dimensions = score_result.get("dimensions", {})
    total = score_result.get("total_score", 0)

    if not api_key:
        return _rule_based_explain(user_profile, job, {**dimensions, "total_score": total})

    try:
        client = _get_client()
        prompt = f"""学生信息：
- 专业/年级：{user_profile.get('major', '未知')} {user_profile.get('grade', '')}
- 技能：{', '.join(user_profile.get('skills', []))}
- 兴趣：{', '.join(user_profile.get('interests', []))}
- 每周空闲：{user_profile.get('free_hours', 20)} 小时

目标岗位：{job.get('title', '')} @ {job.get('company', '')}
岗位要求：{', '.join(job.get('required_skills', []))}
工作类型：{job.get('work_type', '')}，每周 {job.get('weekly_hours', 0)} 小时

匹配得分（满分1.0）：
- 技能匹配：{dimensions.get('d1_skill', 0):.2f}
- 时间适配：{dimensions.get('d2_time', 0):.2f}
- 兴趣契合：{dimensions.get('d3_interest', 0):.2f}
- 能力水平：{dimensions.get('d4_ability', 0):.2f}
- 企业适配：{dimensions.get('d5_culture', 0):.2f}
- 综合评分：{total:.2f}

请生成个性化推荐理由："""

        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0.7,
            max_tokens=200,
        )
        explanation = response.choices[0].message.content.strip()
        logger.info(f"生成推荐理由成功：{job.get('title', '')}")
        return explanation

    except Exception as e:
        logger.warning(f"DeepSeek 生成推荐理由失败: {e}，使用规则备用")
        return _rule_based_explain(user_profile, job, {**dimensions, "total_score": total})


def batch_generate(user_profile: dict, ranked_jobs: list[dict], top_n: int = 5) -> list[dict]:
    """为前 top_n 个岗位批量生成推荐理由"""
    results = []
    for job in ranked_jobs[:top_n]:
        explanation = generate_explanation(user_profile, job, job)
        results.append({**job, "explanation": explanation})
    # 剩余岗位用规则生成
    for job in ranked_jobs[top_n:]:
        dimensions = job.get("dimensions", {})
        total = job.get("total_score", 0)
        explanation = _rule_based_explain(user_profile, job, {**dimensions, "total_score": total})
        results.append({**job, "explanation": explanation})
    return results
