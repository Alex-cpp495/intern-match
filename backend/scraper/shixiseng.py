"""
实习僧爬虫 v2 —— 列表页提取链接 + 详情页解析
目标: https://www.shixiseng.com/interns?keyword={kw}&city=宁波&page=1
策略:
  1. 列表页仅提取岗位详情页 URL (列表页标题使用自定义字体加密，不可直接解析)
  2. 批量并发请求详情页 (详情页为正常可读 HTML)
  3. 解析详情页得到完整结构化数据
"""

import re
import json
import time
import logging
import random
from datetime import date
from pathlib import Path
from typing import Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent.parent / "data"
CACHE_FILE = DATA_DIR / "jobs_cache.json"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Referer": "https://www.shixiseng.com/",
}

# ── 搜索关键词 ──
# 分成「技术」和「非技术」两组；爬取时交替执行，保证非技术方向有足够覆盖。
_KW_TECH = [
    # 开发
    "Python", "Java", "Go", "前端开发", "后端开发", "全栈开发",
    "C++", "安卓开发", "iOS开发",
    # 算法/AI/数据
    "算法工程师", "机器学习", "深度学习", "NLP",
    "数据分析", "数据挖掘", "大数据",
    # 基础设施
    "云计算", "网络安全", "嵌入式", "测试开发",
    # 综合技术
    "软件工程师",
]

_KW_NON_TECH = [
    # ── 金融 / 财会 / 投资 ──
    "金融分析", "会计", "审计", "投行", "证券", "基金",
    "风险控制", "投资研究", "量化研究", "金融科技",
    "信贷", "保险", "银行", "资产管理", "理财",
    "财务", "税务", "出纳",
    # ── 咨询 / 管理 ──
    "咨询", "管理咨询", "战略咨询", "商业分析",
    "项目管理", "企业管理",
    # ── 市场 / 营销 / 品牌 ──
    "市场营销", "品牌", "市场策划", "广告",
    "公关", "活动策划", "会展",
    "电商运营", "直播运营", "社群运营",
    # ── 运营 / 新媒体 ──
    "运营", "新媒体运营", "内容运营", "社区运营",
    "用户运营", "内容创作", "短视频运营", "小红书运营",
    # ── 产品 / 设计 ──
    "产品经理", "产品运营", "产品助理",
    "UI设计", "UX设计", "视觉设计", "交互设计", "平面设计",
    "工业设计", "室内设计", "建筑设计",
    # ── 人力资源 / 行政 / 法务 ──
    "人力资源", "招聘", "培训", "薪酬绩效",
    "行政", "前台", "文秘", "办公室助理",
    "法务", "合规", "知识产权", "律师助理",
    # ── 供应链 / 物流 / 采购 ──
    "供应链", "物流", "采购", "仓储管理", "报关",
    "国际贸易", "外贸", "跨境电商", "货代",
    # ── 传媒 / 文化 / 内容 ──
    "记者", "编辑", "编导", "摄影", "新闻",
    "翻译", "英语翻译", "日语翻译", "同声传译",
    "文案", "策划", "出版",
    # ── 教育 / 学术 ──
    "教育", "助教", "教学", "课程设计",
    "科研助理", "实验室助理", "学术",
    # ── 生物 / 医药 / 化学 ──
    "生物", "制药", "医药", "临床", "化学",
    "食品", "质检", "检验",
    # ── 工程 / 制造 / 能源 ──
    "机械", "电气", "自动化", "新能源",
    "环保", "土木", "建筑", "测绘",
    "质量管理", "工艺",
    # ── 综合 / 通用 ──
    "暑期实习", "寒假实习", "管培生", "实习",
]

KEYWORDS = _KW_NON_TECH + _KW_TECH

# 搜索城市（全国主要城市 + 远程）
CITIES = [
    "全国", "宁波", "上海", "杭州", "北京", "深圳", "广州",
    "南京", "成都", "武汉", "西安", "苏州", "厦门", "长沙",
]

# 公司规模推断关键词
BIG_COMPANY_KEYWORDS = [
    "字节", "阿里", "腾讯", "百度", "京东", "华为", "小米",
    "网易", "海康", "吉利", "舜宇", "拓普", "中控",
]


def _get(url: str, timeout: int = 10) -> Optional[requests.Response]:
    """带重试的 GET 请求"""
    for attempt in range(2):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=timeout)
            if resp.status_code == 200:
                return resp
            logger.warning(f"HTTP {resp.status_code}: {url}")
        except Exception as e:
            logger.warning(f"请求失败 (attempt {attempt+1}): {url} — {e}")
            time.sleep(1)
    return None


# ─────────────────────────────────────────────
# Step 1: 从列表页提取岗位 URL
# ─────────────────────────────────────────────

def _extract_job_urls(keyword: str, city: str = "宁波", max_pages: int = 3) -> list[str]:
    """
    从搜索列表页提取所有岗位详情页 URL。
    列表页的标题使用自定义字体加密，不解析文字，只提取链接。
    """
    urls = []
    for page in range(1, max_pages + 1):
        url = (
            f"https://www.shixiseng.com/interns"
            f"?keyword={keyword}&city={city}&page={page}"
        )
        resp = _get(url)
        if not resp:
            break

        soup = BeautifulSoup(resp.text, "lxml")
        links = soup.select("a[href*='/intern/inn_']")
        page_urls = []
        for a in links:
            href = a.get("href", "")
            clean = href.split("?")[0]
            if clean not in urls and clean not in page_urls:
                page_urls.append(clean)

        logger.info(f"关键词 '{keyword}' 城市 '{city}' 第{page}页 → {len(page_urls)} 个链接")
        urls.extend(page_urls)

        if not page_urls:
            break
        time.sleep(random.uniform(0.6, 1.2))

    return list(dict.fromkeys(urls))


# ─────────────────────────────────────────────
# Step 2: 解析岗位详情页
# ─────────────────────────────────────────────

def _parse_salary(text: str) -> str:
    """从页面文本中提取薪资，格式如 '150-200/天'"""
    m = re.search(r"(\d+[-~]\d+)[/／]天", text)
    if m:
        return m.group(0)
    m2 = re.search(r"(\d+)[/／]天", text)
    if m2:
        return m2.group(0)
    return "面议"


def _parse_weekly_days(text: str) -> int:
    """从文本提取每周工作天数"""
    m = re.search(r"(\d+)[天日][/／]周", text)
    return int(m.group(1)) if m else 3


def _infer_skills(title: str, desc: str) -> list[str]:
    """从标题和描述推断相关技能标签"""
    combined = title + " " + desc
    skill_map = {
        # ── 技术 ──
        "Python": ["python", "pandas", "numpy", "django", "flask", "fastapi"],
        "Java": ["java", "spring", "springboot", "mybatis", "maven"],
        "JavaScript": ["javascript", "js", "vue", "react", "node", "前端"],
        "数据分析": ["数据分析", "data analysis", "bi", "tableau", "powerbi"],
        "机器学习": ["机器学习", "深度学习", "pytorch", "tensorflow"],
        "SQL": ["sql", "mysql", "数据库", "postgresql"],
        "C++": ["c++", "cpp", "嵌入式", "单片机"],
        # ── 设计 ──
        "Figma": ["figma", "ui", "ux", "sketch", "prototype"],
        "设计": ["设计", "ps", "photoshop", "illustrator", "ai设计",
                 "indesign", "cad", "3dmax"],
        # ── 财会金融 ──
        "财务会计": ["会计", "财务", "审计", "税务", "出纳", "报表",
                    "核算", "账务", "用友", "金蝶"],
        "金融分析": ["金融", "投资", "估值", "风控", "尽调", "ipo",
                    "cfa", "cpa"],
        "Excel": ["excel", "wps", "表格", "数据透视"],
        # ── 市场 / 运营 ──
        "市场营销": ["市场", "营销", "推广", "sem", "seo", "投放"],
        "新媒体": ["公众号", "微信", "小红书", "抖音", "短视频",
                   "社群", "直播"],
        "文案写作": ["文案", "copywriting", "内容创作", "撰稿", "编辑"],
        "活动策划": ["策划", "活动", "会展", "展览"],
        # ── 人力 / 行政 / 法务 ──
        "人力资源": ["人力", "hr", "招聘", "薪酬", "绩效", "培训"],
        "行政管理": ["行政", "前台", "文秘", "档案", "办公"],
        "法律合规": ["法务", "合规", "法律", "合同", "知识产权"],
        # ── 供应链 / 贸易 ──
        "供应链": ["供应链", "采购", "物流", "仓储", "报关"],
        "外贸": ["外贸", "国际贸易", "跨境", "b2b", "货代"],
        # ── 语言 / 翻译 ──
        "英语": ["英语", "english", "英文", "雅思", "托福", "六级"],
        "翻译": ["翻译", "口译", "笔译", "同传", "本地化"],
        "日语": ["日语", "日文", "n1", "n2"],
        # ── 通识 ──
        "沟通协作": ["沟通", "协调", "团队", "合作", "跨部门"],
        "PPT演示": ["ppt", "演示", "presentation", "汇报"],
        "项目管理": ["项目管理", "pmp", "甘特", "进度"],
        # ── 理工 / 工程 ──
        "实验操作": ["实验", "化学", "生物", "临床", "检验", "质检"],
        "工程制图": ["solidworks", "autocad", "catia", "机械制图"],
    }
    found = []
    combined_lower = combined.lower()
    for skill, keywords in skill_map.items():
        if any(kw in combined_lower for kw in keywords):
            found.append(skill)
    return found[:8]


def _infer_grade(desc: str) -> str:
    """从描述推断最低学历要求"""
    if any(k in desc for k in ["研究生", "硕士", "master"]):
        return "研究生"
    if any(k in desc for k in ["大四", "应届", "应/往届"]):
        return "大三"
    if any(k in desc for k in ["大三", "大二", "大一", "在校", "在读"]):
        return "大二"
    return "大二"


def _parse_detail_page(job_url: str, idx: int) -> Optional[dict]:
    """
    解析实习僧岗位详情页，提取结构化字段。
    详情页为正常可读 HTML，无自定义字体加密。
    """
    resp = _get(job_url, timeout=12)
    if not resp:
        return None

    soup = BeautifulSoup(resp.text, "lxml")
    full_text = soup.get_text(separator=" ", strip=True)

    # ── 标题：从 <title> 提取（格式：XXX实习招聘-公司名实习生招聘-实习僧）
    title_tag = soup.find("title")
    title = "实习岗位"
    company = "未知公司"
    if title_tag:
        raw_title = title_tag.get_text(strip=True)
        # "python实习生实习招聘-社科赛斯实习生招聘-实习僧"
        parts = raw_title.split("-")
        if len(parts) >= 2:
            title = parts[0].replace("实习招聘", "").replace("实习生", "").strip()
            company_raw = parts[1].replace("实习生招聘", "").strip()
            if company_raw and company_raw != "实习僧":
                company = company_raw

    # ── 薪资
    salary = _parse_salary(full_text)

    # ── 工作天数 / 时长
    weekly_days = _parse_weekly_days(full_text)
    weekly_hours = weekly_days * 8

    # ── 是否远程
    is_remote = any(k in full_text for k in ["远程实习", "线上实习", "全国职位"])

    # ── 地点
    location = "宁波"
    if "全国" in full_text and "宁波" not in full_text:
        location = "全国/远程"

    # ── 工作类型（按天数判断）
    work_type = "全职" if weekly_days >= 5 else "兼职"

    # ── 标签：从包含"实习"的短语中提取
    tags_raw = re.findall(r"[\u4e00-\u9fa5]+实习|远程实习|可转正|暑期|寒假|[\u4e00-\u9fa5]{2,6}奖", full_text)
    tags = list(dict.fromkeys(t for t in tags_raw if 2 <= len(t) <= 8))[:8]

    # ── 岗位描述（取职位描述段落）
    desc = ""
    desc_marker = soup.find(string=re.compile("职位描述|岗位职责|工作内容"))
    if desc_marker:
        parent = desc_marker.find_parent()
        if parent:
            desc_text = parent.find_next_sibling()
            if desc_text:
                desc = desc_text.get_text(strip=True)[:400]
    if not desc:
        # 备用：从全文截取
        m = re.search(r"职位描述[：:]?\s*(.{50,400})", full_text)
        if m:
            desc = m.group(1).strip()

    # ── 截止日期
    deadline = ""
    m_deadline = re.search(r"截止日期[：:]\s*(\d{4}-\d{2}-\d{2})", full_text)
    if m_deadline:
        deadline = m_deadline.group(1)

    # ── 技能推断
    required_skills = _infer_skills(title, desc)

    # ── 最低年级
    min_grade = _infer_grade(full_text)

    # ── 公司规模推断
    company_size = "中型企业"
    if any(k in company for k in BIG_COMPANY_KEYWORDS):
        company_size = "大厂"
    elif any(k in full_text for k in ["初创", "创业", "startup"]):
        company_size = "初创"

    # ── 行业推断
    industry = _infer_industry(title + " " + desc + " " + company)

    logger.debug(f"解析完成: {title} @ {company} | {salary}")

    return {
        "id": f"shx-{idx:04d}",
        "title": title if title else "实习岗位",
        "company": company,
        "location": location,
        "salary": salary,
        "work_type": work_type,
        "weekly_hours": weekly_hours,
        "is_remote": is_remote,
        "min_grade": min_grade,
        "company_size": company_size,
        "industry": industry,
        "work_env": _infer_work_env(full_text),
        "tags": tags,
        "required_skills": required_skills,
        "hard_required_skills": [],
        "description": desc,
        "deadline": deadline,
        "source": "实习僧",
        "source_url": job_url,
    }


def _infer_industry(text: str) -> str:
    text_lower = text.lower()
    mapping = [
        # 非技术行业排在前面，避免被「互联网/AI」截走
        ("金融", ["金融", "银行", "证券", "基金", "投资", "量化", "信贷",
                  "保险", "理财", "资产管理", "信托", "期货"]),
        ("财会审计", ["会计", "审计", "税务", "财务", "出纳"]),
        ("咨询", ["咨询", "战略", "管理咨询"]),
        ("法律", ["法务", "律师", "合规", "知识产权", "法律"]),
        ("教育", ["教育", "学校", "培训", "家教", "留学", "助教", "教学"]),
        ("传媒文化", ["新闻", "记者", "编辑", "编导", "出版", "传媒",
                     "摄影", "影视"]),
        ("翻译语言", ["翻译", "口译", "笔译", "同传"]),
        ("医疗健康", ["医疗", "健康", "制药", "医药", "药", "医院",
                     "临床", "生物", "化学"]),
        ("物流贸易", ["物流", "供应链", "采购", "报关", "外贸",
                     "国际贸易", "货代", "仓储", "跨境"]),
        ("快消零售", ["快消", "零售", "日化", "食品饮料"]),
        ("汽车制造", ["汽车", "新能源车", "吉利", "宁德", "比亚迪"]),
        ("工程建筑", ["土木", "建筑", "测绘", "施工", "工程造价", "工程管理"]),
        ("机械能源", ["机械", "电气", "自动化", "新能源", "环保",
                     "质量管理"]),
        ("智能硬件", ["硬件", "嵌入式", "IOT", "传感", "海康"]),
        ("设计创意", ["设计", "UI", "UX", "视觉", "创意", "美术",
                     "室内设计", "工业设计", "平面设计"]),
        ("市场营销", ["市场营销", "广告", "公关", "活动策划", "会展",
                     "品牌", "市场推广"]),
        ("运营", ["运营", "新媒体运营", "内容运营", "用户运营",
                  "社区运营", "社群运营"]),
        ("人力行政", ["人力", "HR", "招聘", "行政", "前台", "文秘"]),
        ("食品农业", ["食品", "质检", "农业"]),
        # 技术行业放在后面
        ("AI人工智能", ["人工智能", "机器学习", "深度学习", "大模型",
                       "计算机视觉", "自然语言处理"]),
        ("互联网", ["互联网", "Web", "App", "软件", "游戏", "IT",
                   "SaaS"]),
    ]
    for industry, keywords in mapping:
        if any(k.lower() in text_lower for k in keywords):
            return industry
    return "综合"


def _infer_work_env(text: str) -> str:
    text_lower = text.lower()
    checks = [
        ("扁平快节奏", ["扁平", "初创", "创业", "快节奏", "startup"]),
        ("金融商务", ["银行", "证券", "基金", "金融", "会计", "审计",
                     "投资", "咨询"]),
        ("市场运营", ["市场", "营销", "运营", "品牌", "电商", "广告",
                     "公关"]),
        ("行政管理", ["行政", "人力", "hr", "前台", "文秘", "法务"]),
        ("教育学术", ["学校", "高校", "学术", "科研", "教育", "培训"]),
        ("创意设计", ["设计", "创意", "美术", "摄影", "影视"]),
        ("工程制造", ["工厂", "制造", "工程", "质量", "车间", "产线"]),
        ("技术研发", ["技术", "研发", "开发", "算法", "代码", "编程"]),
        ("稳定体制", ["国企", "稳定", "事业单位", "保险"]),
    ]
    for env, keywords in checks:
        if any(k.lower() in text_lower for k in keywords):
            return env
    return "综合"


# ─────────────────────────────────────────────
# 主爬虫入口
# ─────────────────────────────────────────────

def scrape_shixiseng(max_jobs: int = 500) -> list[dict]:
    """
    两阶段爬取:
    1. 从各关键词 × 城市 列表页收集岗位 URL
    2. 并发请求详情页解析完整数据
    """
    # ── 阶段 1: 收集 URL ──
    all_urls: list[str] = []
    for city in CITIES:
        for kw in KEYWORDS:
            if len(all_urls) >= max_jobs * 2:
                break
            urls = _extract_job_urls(kw, city=city, max_pages=3)
            new_count = 0
            for u in urls:
                if u not in all_urls:
                    all_urls.append(u)
                    new_count += 1
            time.sleep(random.uniform(0.3, 0.7))

    # 确保有绝对 URL
    all_urls = [
        (f"https://www.shixiseng.com{u}" if u.startswith("/") else u)
        for u in all_urls
    ]
    all_urls = all_urls[:max_jobs]
    logger.info(f"共收集到 {len(all_urls)} 个岗位 URL，开始解析详情页...")

    # ── 阶段 2: 并发抓取详情页 (5 并发) ──
    results: list[dict] = []
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {
            executor.submit(_parse_detail_page, url, idx): idx
            for idx, url in enumerate(all_urls)
        }
        for future in as_completed(futures):
            job = future.result()
            if job and job.get("title") and job["title"] not in ("实习岗位", ""):
                results.append(job)
            time.sleep(random.uniform(0.1, 0.3))

    # 按 id 重新编号保证唯一
    for i, job in enumerate(results):
        job["id"] = f"shx-{i:04d}"

    logger.info(f"实习僧共解析 {len(results)} 条有效岗位")
    return results


# ─────────────────────────────────────────────
# 缓存管理
# ─────────────────────────────────────────────

def refresh_cache(force_scrape: bool = False) -> list[dict]:
    """刷新岗位缓存：合并实习僧 + 牛客网爬取数据"""
    if not force_scrape and CACHE_FILE.exists():
        try:
            with open(CACHE_FILE, encoding="utf-8") as f:
                cached = json.load(f)
            if cached:
                logger.info(f"使用缓存数据，共 {len(cached)} 条")
                return cached
        except Exception:
            pass

    all_jobs: list[dict] = []

    # ── 来源一：实习僧 ──
    try:
        shx_jobs = scrape_shixiseng(max_jobs=500)
        logger.info(f"实习僧抓取完成，{len(shx_jobs)} 条")
        all_jobs.extend(shx_jobs)
    except Exception as e:
        logger.error(f"实习僧爬虫失败: {e}")

    # ── 来源二：牛客网 ──
    try:
        from scraper.nowcoder import scrape_nowcoder
        nc_jobs = scrape_nowcoder(max_jobs=300)
        logger.info(f"牛客网抓取完成，{len(nc_jobs)} 条")
        all_jobs.extend(nc_jobs)
    except Exception as e:
        logger.error(f"牛客网爬虫失败（不影响实习僧数据）: {e}")

    if not all_jobs:
        logger.warning("所有爬虫均未获取到数据，返回空列表")
        return []

    # ── 去重（按 title+company 组合）──
    seen: set[str] = set()
    deduped: list[dict] = []
    for job in all_jobs:
        key = f"{job.get('title', '')}|{job.get('company', '')}"
        if key not in seen:
            seen.add(key)
            deduped.append(job)

    # ── 重新编号 ──
    for i, job in enumerate(deduped):
        src_prefix = "shx" if job.get("source") == "实习僧" else "nc"
        job["id"] = f"{src_prefix}-{i:04d}"

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(deduped, f, ensure_ascii=False, indent=2)

    logger.info(f"缓存已更新，共 {len(deduped)} 条（去重后）")
    return deduped


def filter_expired_jobs(jobs: list[dict]) -> list[dict]:
    """剔除 deadline 已早于今天的岗位（无 deadline 或无法解析的保留）"""
    today = date.today()
    active: list[dict] = []
    for j in jobs:
        d = (j.get("deadline") or "").strip()
        if not d:
            active.append(j)
            continue
        try:
            normalized = d.replace("/", "-")
            parts = normalized.split("-")
            if len(parts) >= 3:
                end = date(int(parts[0]), int(parts[1]), int(parts[2]))
                if end < today:
                    continue
        except (ValueError, IndexError):
            pass
        active.append(j)
    return active


def get_all_jobs() -> list[dict]:
    """获取所有岗位（优先读缓存，不存在则初始化；读缓存时过滤已过期 deadline）"""
    if CACHE_FILE.exists():
        try:
            with open(CACHE_FILE, encoding="utf-8") as f:
                jobs = json.load(f)
            if jobs:
                return filter_expired_jobs(jobs)
        except Exception:
            pass
    return filter_expired_jobs(refresh_cache())
