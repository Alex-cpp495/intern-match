"""
牛客网实习爬虫（2026‑03 适配版）
API:  https://www.nowcoder.com/nccommon/intern/list

旧版 gw.nowcoder.com/apiproxy 已下线，新版 gw-c 的 /u/ 路径需要登录。
当前使用仍可匿名访问的 nccommon/intern/list 接口全量分页抓取。

策略:
  1. 遍历分页，一次 32 条，最多 max_pages 页
  2. 过滤掉测试/无效岗位
  3. 利用 city 参数按热门城市分批爬取以提高覆盖率
  4. 标准化为与实习僧相同的字段格式
"""

import json
import time
import logging
import random
import re
from typing import Optional

import requests

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9",
}

API_URL = "https://www.nowcoder.com/nccommon/intern/list"

HOT_CITIES = [
    "",  # 全部
    "北京", "上海", "杭州", "深圳", "广州",
    "南京", "成都", "武汉", "西安", "厦门",
    "合肥", "长沙", "苏州", "天津", "重庆",
]

_BIG_COMPANIES = [
    "字节", "阿里", "腾讯", "百度", "京东", "华为", "小米",
    "网易", "美团", "滴滴", "拼多多", "快手", "微博", "360",
    "招商", "平安", "中信", "顺丰", "大疆", "vivo", "oppo",
]

# ── 行业推断（与 shixiseng 保持一致，非技术优先）──
_INDUSTRY_MAP = [
    ("金融", ["金融", "银行", "证券", "基金", "投资", "量化", "信贷",
              "保险", "理财", "资产管理", "信托", "期货"]),
    ("财会审计", ["会计", "审计", "税务", "财务", "出纳"]),
    ("咨询", ["咨询", "战略", "管理咨询"]),
    ("法律", ["法务", "律师", "合规", "知识产权", "法律"]),
    ("教育", ["教育", "学校", "培训", "家教", "留学", "edtech"]),
    ("传媒文化", ["新闻", "记者", "编辑", "编导", "出版", "传媒"]),
    ("翻译语言", ["翻译", "口译", "笔译", "同传"]),
    ("医疗健康", ["医疗", "健康", "制药", "药", "医院", "生物", "化学"]),
    ("物流贸易", ["物流", "供应链", "采购", "外贸", "国际贸易", "货代", "跨境"]),
    ("快消零售", ["快消", "零售", "日化", "食品饮料"]),
    ("汽车制造", ["汽车", "新能源车", "吉利", "宁德"]),
    ("工程建筑", ["土木", "建筑", "测绘", "施工", "工程造价", "工程管理"]),
    ("机械能源", ["机械", "电气", "自动化", "新能源", "环保"]),
    ("智能硬件", ["硬件", "嵌入式", "iot", "传感", "芯片"]),
    ("设计创意", ["设计", "ui", "ux", "视觉设计", "品牌", "创意", "产品设计"]),
    ("市场营销", ["市场营销", "广告", "公关", "活动策划", "品牌", "市场推广"]),
    ("运营", ["运营", "新媒体运营", "内容运营", "社群运营"]),
    ("人力行政", ["人力", "hr", "招聘", "行政", "前台"]),
    ("AI人工智能", ["人工智能", "机器学习", "深度学习", "大模型",
                   "计算机视觉", "nlp"]),
    ("互联网", ["互联网", "web", "app", "软件", "游戏", "it", "saas"]),
]

_WORK_ENV_MAP = [
    ("扁平快节奏", ["扁平", "初创", "创业", "快节奏", "startup"]),
    ("金融商务", ["银行", "证券", "基金", "金融", "会计", "审计",
                 "投资", "咨询"]),
    ("市场运营", ["市场", "营销", "运营", "品牌", "电商", "广告"]),
    ("行政管理", ["行政", "人力", "hr", "前台", "文秘", "法务"]),
    ("教育学术", ["学校", "高校", "学术", "科研", "教育", "培训"]),
    ("创意设计", ["设计", "创意", "美术", "摄影"]),
    ("工程制造", ["工厂", "制造", "工程", "质量", "车间"]),
    ("技术研发", ["技术", "研发", "开发", "算法", "代码"]),
    ("稳定体制", ["国企", "稳定", "事业单位", "保险"]),
]


def _infer_industry(text: str) -> str:
    t = text.lower()
    for industry, keywords in _INDUSTRY_MAP:
        if any(k.lower() in t for k in keywords):
            return industry
    return "综合"


def _infer_work_env(text: str) -> str:
    t = text.lower()
    for env, keywords in _WORK_ENV_MAP:
        if any(k.lower() in t for k in keywords):
            return env
    return "综合"


def _infer_company_size(company: str, scale: str) -> str:
    if any(k in company for k in _BIG_COMPANIES):
        return "大厂"
    scale_l = scale.lower()
    if any(k in scale_l for k in ["上市", "ipo", "10000", "万人", "大型"]):
        return "大厂"
    if any(k in scale_l for k in ["初创", "startup", "天使", "种子", "0-20"]):
        return "初创"
    return "中型企业"


def _infer_skills(title: str) -> list[str]:
    combined = title.lower()
    skill_map = {
        "Python": ["python"],
        "Java": ["java"],
        "JavaScript": ["javascript", "前端", "vue", "react"],
        "C++": ["c++", "嵌入式"],
        "Go": ["golang", "go开发"],
        "数据分析": ["数据分析", "数据"],
        "机器学习": ["机器学习", "深度学习", "算法"],
        "SQL": ["sql", "数据库"],
        "Excel": ["excel", "财务", "会计"],
        "Figma": ["figma", "ui", "设计"],
        "英语": ["英语", "翻译"],
        "沟通能力": ["运营", "市场", "hr", "行政"],
    }
    found = []
    for skill, keywords in skill_map.items():
        if any(kw in combined for kw in keywords):
            found.append(skill)
    return found[:6]


def _fetch_page(page: int, city: str = "") -> Optional[dict]:
    """请求牛客网实习列表 API 的单页"""
    params: dict = {"page": page}
    if city:
        params["city"] = city
    try:
        resp = requests.get(
            API_URL,
            params=params,
            headers=HEADERS,
            timeout=12,
        )
        if resp.status_code != 200:
            logger.warning(f"牛客 API 返回 {resp.status_code}")
            return None
        data = resp.json()
        if data.get("code") != 0:
            logger.warning(f"牛客 API code={data.get('code')}, msg={data.get('msg')}")
            return None
        return data.get("data", {})
    except Exception as e:
        logger.warning(f"牛客请求失败 page={page} city={city}: {e}")
        return None


def _parse_job(item: dict, idx: int) -> Optional[dict]:
    """将牛客网单条岗位数据标准化"""
    try:
        title = item.get("jobName") or ""
        company = item.get("companyName") or ""
        if not title or title == "实习职位":
            return None
        if not company or company == "线上测试2":
            return None

        city = item.get("jobCity") or item.get("city") or "全国"
        salary_display = item.get("salaryDayDisplay") or "面议"
        company_scale = item.get("companyScale") or ""
        company_category = item.get("companyCategory") or ""
        job_type = item.get("jobType") or ""
        week_days = int(item.get("weekDay") or 3)
        weekly_hours = week_days * 8
        work_type = "全职" if week_days >= 5 else "兼职"
        job_id = item.get("id") or idx
        project_id = item.get("recruitProjectId") or item.get("projectId") or ""

        is_remote = any(k in city for k in ["远程", "线上", "全国", "不限"])
        location = city.split(",")[0] if city else "全国/远程"
        if is_remote and location in ("", "全国"):
            location = "全国/远程"

        combined = f"{title} {company} {company_category} {job_type}"
        industry = _infer_industry(combined)
        work_env = _infer_work_env(combined)
        company_size = _infer_company_size(company, company_scale)
        required_skills = _infer_skills(title)

        if any(k in title for k in ["研究生", "硕士"]):
            min_grade = "研究生"
        elif any(k in title for k in ["大四", "应届"]):
            min_grade = "大三"
        else:
            min_grade = "大二"

        tags = [t for t in [job_type, company_category] if t]
        if is_remote:
            tags.append("远程")

        detail_url = ""
        if project_id:
            detail_url = f"https://www.nowcoder.com/jobs/school/jobs"

        return {
            "id": f"nc-{idx:04d}",
            "title": title,
            "company": company,
            "location": location,
            "salary": salary_display,
            "work_type": work_type,
            "weekly_hours": weekly_hours,
            "is_remote": is_remote,
            "min_grade": min_grade,
            "company_size": company_size,
            "industry": industry,
            "work_env": work_env,
            "tags": tags[:7],
            "required_skills": required_skills,
            "hard_required_skills": [],
            "description": f"{title} - {company} ({company_category})",
            "deadline": "",
            "source": "牛客网",
            "source_url": detail_url,
        }
    except Exception as e:
        logger.warning(f"牛客岗位解析失败 idx={idx}: {e}")
        return None


def scrape_nowcoder(max_jobs: int = 300) -> list[dict]:
    """
    爬取牛客网实习岗位。
    按城市分批遍历分页，直到达到 max_jobs 或数据耗尽。
    """
    seen_ids: set = set()
    all_parsed: list[dict] = []
    idx = 0

    for city in HOT_CITIES:
        if len(all_parsed) >= max_jobs:
            break
        city_label = city or "全部"
        max_pages = 10 if city == "" else 3

        for page in range(1, max_pages + 1):
            if len(all_parsed) >= max_jobs:
                break
            data = _fetch_page(page, city)
            if not data:
                break

            jobs = data.get("jobs") or []
            if not jobs:
                break

            new = 0
            for item in jobs:
                uid = item.get("id")
                if uid in seen_ids:
                    continue
                seen_ids.add(uid)

                job = _parse_job(item, idx)
                if job:
                    all_parsed.append(job)
                    idx += 1
                    new += 1

            logger.info(f"牛客 city='{city_label}' page={page} → {new} 新 (共 {len(all_parsed)})")

            if len(jobs) < 20:
                break
            time.sleep(random.uniform(0.3, 0.7))

        time.sleep(random.uniform(0.2, 0.4))

    for i, job in enumerate(all_parsed):
        job["id"] = f"nc-{i:04d}"

    logger.info(f"牛客网共解析 {len(all_parsed)} 条有效岗位")
    return all_parsed
