"""
五维度匹配算法 —— 数学升级版

D1 技能匹配 (30%): IDF加权二部图最优覆盖 + 硬性技能乘法惩罚
   D1 = [Σ_j idf(r_j) · max_i cos(u_i, r_j)] / Σ_j idf(r_j)
   × ∏_k (1 - α·I(hard_k ∉ U))

D2 时间适配 (25%): Sigmoid 平滑覆盖率 + 实习时间段感知
   ratio = h_free / h_required
   D2 = σ(κ·(ratio - θ)),  κ=8, θ=0.8
   远程岗位: D2 = max(D2, 0.9)
   暑期匹配: 岗位含"暑期实习"标签 → D2 = max(D2, 0.92); 截止日期在暑期前 → D2 ×= 0.35
   在读兼职: 岗位含"兼职/在读"标签 → D2 = max(D2, 0.80); 全职坐班+空闲不足 → D2 ×= 0.65
   过期岗位: deadline < today → D2 ×= 0.15

D3 兴趣契合 (20%): SIF加权 Jaccard + SIF加权语义余弦
   sif(t) = α/(α + p(t)),  α=0.001, p(t)=该标签在语料中的频率
   D3 = 0.35·Jaccard_SIF + 0.65·cos(v_user_SIF, v_job_SIF)

D4 能力水平 (15%): Logistic函数主体 + 高斯项目加成
   D4_base = σ(k·ΔL),  k=1.5, ΔL = L_user - L_required
   D4_bonus = 0.3·exp(-ΔL²/2) · I(has_project)
   D4 = clamp(D4_base + D4_bonus, 0, 1)

D5 企业适配 (10%): RBF核(高斯核)相似度
   K_size(x,y) = exp(-|x-y|²/2σ²),  σ=1.0

总分: TOPSIS + 熵权法(Entropy Weight Method)动态校正
   d+ = √[Σ w_i·(v_i-1)²],  d- = √[Σ w_i·v_i²]
   TOPSIS = d- / (d+ + d-)
   W_final = 0.6·W_static + 0.4·W_entropy  (熵权法动态修正)

参考文献:
  - Hwang & Yoon (1981): TOPSIS
  - Shannon (1948): Entropy Weight
  - Arora et al. (2017): SIF Embeddings (https://arxiv.org/abs/1703.02507)
  - IDF: Robertson & Jones (1976)
"""

from __future__ import annotations

import math
import logging
from typing import Any

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity as sk_cosine_matrix
from scipy.optimize import linear_sum_assignment  # noqa: F401  (Hungarian, 备用)

from core.embedder import embed, embed_single, cosine_sim

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# 静态先验权重 (基于领域知识 AHP 层次分析法估计)
# ─────────────────────────────────────────────
W_STATIC = np.array([0.30, 0.25, 0.20, 0.15, 0.10])

GRADE_LEVEL: dict[str, int] = {
    "大一": 1, "大二": 2, "大三": 3, "大四": 4, "研究生": 5
}

# 公司规模的连续量化 (用于 RBF 核)
COMPANY_SIZE_SCALE: dict[str, float] = {
    "初创": 1.0, "小型企业": 2.0, "高校": 2.5,
    "中型企业": 3.0, "大型企业": 3.5, "大厂": 4.0,
}

# ─────────────────────────────────────────────
# 工具函数
# ─────────────────────────────────────────────

def _sigmoid(x: float, k: float = 1.0) -> float:
    """标准 Sigmoid: σ(kx) = 1 / (1 + e^{-kx})"""
    return 1.0 / (1.0 + math.exp(-k * x))


def _rbf_kernel(x: float, y: float, sigma: float = 1.0) -> float:
    """高斯 RBF 核: K(x,y) = exp(-|x-y|² / 2σ²)"""
    return math.exp(-((x - y) ** 2) / (2 * sigma ** 2))


def _idf(skill: str, corpus: list[list[str]]) -> float:
    """
    IDF(t) = log[(N+1) / (df(t)+1)] + 1  (平滑 IDF，参考 sklearn TfidfTransformer)
    corpus: 所有岗位的 required_skills 列表
    """
    N = len(corpus)
    df = sum(1 for doc in corpus if skill.lower() in [s.lower() for s in doc])
    return math.log((N + 1) / (df + 1)) + 1.0


def _sif_weight(tag: str, tag_freq: dict[str, float], alpha: float = 0.001) -> float:
    """
    Smooth Inverse Frequency 权重 (Arora et al. 2017)
    w(t) = α / (α + p(t))
    p(t): 标签在语料中出现的概率 (频率)
    """
    p = tag_freq.get(tag.lower(), 1e-4)
    return alpha / (alpha + p)


# ─────────────────────────────────────────────
# D1: 技能匹配 — IDF加权二部图最优覆盖
# ─────────────────────────────────────────────

def _d1_skill(
    user_skills: list[str],
    job: dict[str, Any],
    skill_corpus: list[list[str]],
) -> float:
    """
    算法: IDF 加权的单向最优覆盖 (employer-side coverage)

    对于每个岗位需求技能 r_j:
      contribution(r_j) = idf(r_j) · max_i cos_sim(embed(u_i), embed(r_j))

    D1_raw = Σ_j contribution(r_j) / Σ_j idf(r_j)

    硬性技能乘法惩罚 (每缺失一项必要技能乘以惩罚因子):
      penalty = ∏_k exp(-β · I(hard_k ∉ U))   β=0.7
    """
    job_skills: list[str] = job.get("required_skills", [])
    hard_required: list[str] = job.get("hard_required_skills", [])

    if not user_skills:
        return 0.20
    if not job_skills:
        return 0.50

    # 预计算所有 embedding
    user_vecs = embed(user_skills)           # shape (|U|, dim)
    job_vecs = embed(job_skills)             # shape (|R|, dim)

    # 余弦相似矩阵: shape (|U|, |R|)
    sim_matrix = sk_cosine_matrix(user_vecs, job_vecs)  # [i,j] = cos(u_i, r_j)

    # 对每个岗位技能取最佳用户技能的相似度
    best_match = sim_matrix.max(axis=0)          # shape (|R|,), max over users

    # IDF 权重向量
    idf_weights = np.array([_idf(s, skill_corpus) for s in job_skills])
    idf_sum = idf_weights.sum()

    # IDF 加权覆盖率
    d1_raw = float(np.dot(idf_weights, best_match) / idf_sum) if idf_sum > 0 else 0.0

    # 硬性技能乘法惩罚
    # penalty = ∏_k exp(-0.7 · I(hard_k ∉ U))
    if hard_required:
        user_lower = {s.lower() for s in user_skills}
        missing_count = sum(
            1 for s in hard_required if s.lower() not in user_lower
        )
        penalty = math.exp(-0.7 * missing_count)
        d1_raw *= penalty

    return float(np.clip(d1_raw, 0.0, 1.0))


# ─────────────────────────────────────────────
# D2: 时间适配 — Sigmoid 平滑覆盖率
# ─────────────────────────────────────────────

def _d2_time(free_hours: float, job: dict[str, Any], intern_period: str = "") -> float:
    """
    算法: Sigmoid 平滑的时间覆盖率 + 实习时间段匹配

    ratio = h_free / h_required
    D2 = σ(κ·(ratio - θ))    κ=8 (陡峭度), θ=0.8 (满足度阈值)

    直觉:
      ratio < 0.5 → D2 ≈ 0.02  (严重不足)
      ratio = 0.8 → D2 = 0.50  (刚好满足)
      ratio = 1.0 → D2 ≈ 0.88  (充裕)
      ratio > 1.5 → D2 ≈ 0.98  (非常充裕)

    全职岗位额外用阶跃惩罚乘以 sigmoid(κ'·(h-35))
    远程岗位: D2 = max(D2, 0.9)

    intern_period 修正:
      暑期/寒假 → 岗位标签含"暑期实习" → D2 = max(D2, 0.92)；截止日期在假期前已过 → 惩罚
      在读     → 全职但不接受灵活安排 → 额外惩罚
    """
    import re
    from datetime import date

    required_hours: float = float(job.get("weekly_hours", 20))
    work_type: str = job.get("work_type", "兼职")
    is_remote: bool = job.get("is_remote", False)

    if required_hours <= 0:
        return 1.0

    ratio = free_hours / required_hours

    # Sigmoid 平滑: κ=8, θ=0.8
    d2 = _sigmoid(8.0 * (ratio - 0.8))

    # 全职岗位额外惩罚 (需要连续整块时间)
    if work_type == "全职":
        fulltime_factor = _sigmoid(5.0 * (free_hours - 35))
        d2 *= fulltime_factor

    # 远程加成
    if is_remote:
        d2 = max(d2, 0.9)

    # ── 实习时间段修正 ──
    job_tags_lower = [t.lower() for t in job.get("tags", [])]
    job_desc_lower = job.get("description", "").lower()
    today = date.today()

    # 截止日期检测
    deadline_str = job.get("deadline", "")
    deadline_date: date | None = None
    if deadline_str:
        try:
            m = re.match(r"(\d{4})-(\d{1,2})-(\d{1,2})", deadline_str)
            if m:
                deadline_date = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except Exception:
            pass

    if intern_period in ("暑期", "寒假"):
        # 假期实习：time 已被 router 覆盖为 80，ratio 会很高，base D2 已大
        # 额外：岗位有"暑期实习"标签 → 完美匹配
        if any("暑期" in t for t in job_tags_lower) or "暑期" in job_desc_lower:
            d2 = max(d2, 0.92)
        if any("寒假" in t for t in job_tags_lower) and intern_period == "寒假":
            d2 = max(d2, 0.92)

        # 截止日期惩罚：暑期约 7 月开始，寒假约 1 月开始
        if deadline_date:
            if deadline_date < today:
                # 已过截止日，几乎没机会
                d2 *= 0.15
            elif intern_period == "暑期":
                summer_start = date(today.year, 7, 1)
                if deadline_date < summer_start:
                    # 截止日在暑期前，届时岗位已关闭
                    d2 *= 0.35
            elif intern_period == "寒假":
                # 寒假约为次年 1 月
                winter_start = date(today.year + 1, 1, 1) if today.month >= 7 else date(today.year, 1, 1)
                if deadline_date < winter_start:
                    d2 *= 0.35

    elif intern_period == "在读":
        # 在读兼职：兼职/远程/灵活 > 全职坐班
        if any("在读" in t for t in job_tags_lower) or any("兼职" in t for t in job_tags_lower):
            d2 = max(d2, 0.80)
        if work_type == "全职" and not is_remote and free_hours < 35:
            # 全职坐班但空闲不足，额外惩罚
            d2 *= 0.65

        # 已过截止日
        if deadline_date and deadline_date < today:
            d2 *= 0.15

    elif intern_period == "随时":
        # 随时可以，不对时间段做额外限制，只惩罚过期岗位
        if deadline_date and deadline_date < today:
            d2 *= 0.15
    else:
        # 未指定时间段，只惩罚过期岗位
        if deadline_date and deadline_date < today:
            d2 *= 0.5

    return float(np.clip(d2, 0.0, 1.0))


# ─────────────────────────────────────────────
# D3: 兴趣契合 — SIF加权 Jaccard + 语义余弦
# ─────────────────────────────────────────────

def _build_tag_freq(all_jobs: list[dict]) -> dict[str, float]:
    """
    统计语料库中标签频率 p(t) = count(t) / total_tags
    用于 SIF 权重计算
    """
    counter: dict[str, int] = {}
    total = 0
    for job in all_jobs:
        for tag in job.get("tags", []):
            key = tag.lower()
            counter[key] = counter.get(key, 0) + 1
            total += 1
    return {t: c / max(total, 1) for t, c in counter.items()}


_TAG_FREQ_CACHE: dict[str, float] = {}


def _d3_interest(
    user_interests: list[str],
    job: dict[str, Any],
    tag_freq: dict[str, float],
) -> float:
    """
    算法: SIF加权 Jaccard + SIF加权语义余弦混合

    ① SIF加权 Jaccard:
       w(t) = α/(α+p(t))
       J_SIF = Σ_t min(w_u(t), w_j(t)) / Σ_t max(w_u(t), w_j(t))

    ② SIF加权语义向量:
       v_SIF = Σ_i w(t_i)·embed(t_i) / Σ_i w(t_i)  (然后 L2 normalize)

    D3 = 0.35·J_SIF + 0.65·cos(v_user_SIF, v_job_SIF)
    """
    job_tags: list[str] = job.get("tags", [])
    job_desc: str = job.get("description", "")

    if not user_interests:
        return 0.5

    alpha = 0.001

    # ── ① SIF加权 Jaccard ──
    all_tags = set(t.lower() for t in user_interests) | set(t.lower() for t in job_tags)
    user_set = {t.lower() for t in user_interests}
    job_set = {t.lower() for t in job_tags}

    numerator = 0.0
    denominator = 0.0
    for t in all_tags:
        w = _sif_weight(t, tag_freq, alpha)
        u_weight = w if t in user_set else 0.0
        j_weight = w if t in job_set else 0.0
        numerator += min(u_weight, j_weight)
        denominator += max(u_weight, j_weight)
    jaccard_sif = numerator / denominator if denominator > 0 else 0.0

    # ── ② SIF加权语义向量 ──
    def sif_embed(terms: list[str]) -> np.ndarray:
        if not terms:
            return np.zeros(384)
        vecs = embed(terms)  # (n, dim)
        weights = np.array([_sif_weight(t, tag_freq, alpha) for t in terms])
        w_sum = weights.sum()
        if w_sum < 1e-10:
            return vecs.mean(axis=0)
        vec = (vecs * weights[:, None]).sum(axis=0) / w_sum
        norm = np.linalg.norm(vec)
        return vec / norm if norm > 1e-10 else vec

    user_vec = sif_embed(user_interests)
    # 岗位侧：优先用 tags + description 文字
    job_side = job_tags + ([job_desc[:200]] if job_desc else [])
    job_vec = sif_embed(job_side) if job_side else embed_single(job.get("title", ""))

    semantic = cosine_sim(user_vec, job_vec)

    d3 = 0.35 * jaccard_sif + 0.65 * semantic
    return float(np.clip(d3, 0.0, 1.0))


# ─────────────────────────────────────────────
# D4: 能力水平 — Logistic + Gaussian 项目加成
# ─────────────────────────────────────────────

def _d4_ability(user_grade: str, has_project: bool, job: dict[str, Any]) -> float:
    """
    算法: Logistic 主体 + Gaussian 项目经验加成

    ΔL = L_user - L_required  ∈ {-4,...,+4}

    D4_base = σ(k·ΔL),  k=1.5
      ΔL = +2 → D4_base ≈ 0.95  (远超要求)
      ΔL =  0 → D4_base = 0.50  (刚好满足)
      ΔL = -1 → D4_base ≈ 0.18  (差一级)
      ΔL = -2 → D4_base ≈ 0.05  (差两级)

    Gaussian 项目加成 (加成在 ΔL=0 时最大):
      D4_bonus = 0.35 · exp(-ΔL²/2) · I(has_project)

    D4 = clamp(D4_base + D4_bonus, 0, 1)
    """
    required_grade: str = job.get("min_grade", "大二")
    user_level = GRADE_LEVEL.get(user_grade, 2)
    req_level = GRADE_LEVEL.get(required_grade, 2)

    delta_l = user_level - req_level  # 差值

    # Logistic 主体, k=1.5
    d4_base = _sigmoid(1.5 * delta_l)

    # Gaussian 项目加成: 加成在 delta_l 接近0时最大
    d4_bonus = 0.0
    if has_project:
        # exp(-ΔL²/2): ΔL=0→1.0, ΔL=±1→0.61, ΔL=±2→0.14
        d4_bonus = 0.35 * math.exp(-(delta_l ** 2) / 2.0)

    d4 = d4_base + d4_bonus
    return float(np.clip(d4, 0.0, 1.0))


# ─────────────────────────────────────────────
# D5: 企业适配 — RBF核 + 语义余弦
# ─────────────────────────────────────────────

def _d5_culture(user_prefs: dict[str, Any], job: dict[str, Any]) -> float:
    """
    算法: 高斯RBF核相似度 (公司规模) + 语义余弦 (行业) + 语义余弦 (氛围)

    公司规模 (连续化量化后的 RBF):
      K_size(x,y) = exp(-|x-y|² / 2σ²),  σ=1.0

    行业 / 工作氛围:
      cos_sim(embed(pref), embed(job_attr))

    D5 = (α·K_size + β·cos_industry + γ·cos_env) / (α+β+γ)
    有效子项权重: α=0.4, β=0.35, γ=0.25
    """
    pref_size = user_prefs.get("company_size", "")
    pref_industry = user_prefs.get("industry", "")
    pref_env = user_prefs.get("work_env", "")

    job_size = job.get("company_size", "")
    job_industry = job.get("industry", "")
    job_env = job.get("work_env", "")

    contributions = []
    weights_used = []

    # ── 公司规模: RBF核 ──
    if pref_size and job_size and pref_size in COMPANY_SIZE_SCALE and job_size in COMPANY_SIZE_SCALE:
        x = COMPANY_SIZE_SCALE[pref_size]
        y = COMPANY_SIZE_SCALE[job_size]
        k_size = _rbf_kernel(x, y, sigma=1.0)
        contributions.append(k_size)
        weights_used.append(0.40)

    # ── 行业: 语义余弦 ──
    if pref_industry and job_industry:
        sim = cosine_sim(embed_single(pref_industry), embed_single(job_industry))
        contributions.append(sim)
        weights_used.append(0.35)

    # ── 工作氛围: 语义余弦 (比 exact-match 更宽容) ──
    if pref_env and job_env:
        sim = cosine_sim(embed_single(pref_env), embed_single(job_env))
        contributions.append(sim)
        weights_used.append(0.25)

    if not contributions:
        return 0.70  # 无偏好时给默认中等分

    total_w = sum(weights_used)
    d5 = sum(c * w for c, w in zip(contributions, weights_used)) / total_w
    return float(np.clip(d5, 0.0, 1.0))


# ─────────────────────────────────────────────
# 熵权法 (Entropy Weight Method) 动态修正权重
# ─────────────────────────────────────────────

def _entropy_weights(score_matrix: np.ndarray) -> np.ndarray:
    """
    熵权法 (Shannon 1948 + 多准则决策领域应用)

    输入: score_matrix, shape=(n_jobs, 5), 各岗位五维度得分
    输出: entropy_weights, shape=(5,)

    步骤:
      1. 归一化: p_ij = v_ij / Σ_i v_ij
      2. 信息熵: E_j = -1/ln(n) · Σ_i p_ij·ln(p_ij)  (p_ij=0时项为0)
      3. 差异系数: d_j = 1 - E_j
      4. 归一化权重: w_j = d_j / Σ_j d_j

    含义: 某维度在各岗位间得分差异越大 → 信息量越高 → 权重越大
    """
    n, m = score_matrix.shape
    if n < 2:
        return W_STATIC.copy()

    col_sums = score_matrix.sum(axis=0)
    col_sums[col_sums < 1e-10] = 1e-10
    P = score_matrix / col_sums  # shape (n, m)

    # 计算熵, 0·ln(0) 定义为 0
    with np.errstate(divide="ignore", invalid="ignore"):
        log_P = np.where(P > 1e-12, np.log(P), 0.0)
    entropy = -(1.0 / math.log(n)) * (P * log_P).sum(axis=0)  # shape (m,)

    diversity = 1.0 - entropy
    diversity = np.maximum(diversity, 1e-10)
    entropy_w = diversity / diversity.sum()
    return entropy_w


# ─────────────────────────────────────────────
# TOPSIS 多准则决策排名
# ─────────────────────────────────────────────

def _topsis_score(v: np.ndarray, weights: np.ndarray) -> float:
    """
    TOPSIS (Hwang & Yoon, 1981)

    正理想解 v+ = (1,1,1,1,1), 负理想解 v- = (0,0,0,0,0)
    (因为所有维度已标准化到 [0,1] 且方向一致: 越大越好)

    加权欧氏距离:
      d+ = √[Σ_i w_i·(v_i - 1)²]
      d- = √[Σ_i w_i·v_i²]

    相对贴近度 (Relative Closeness):
      C* = d- / (d+ + d-)   ∈ (0, 1]
      越接近1说明越靠近正理想解
    """
    w = weights
    d_pos = math.sqrt(float(np.sum(w * (v - 1.0) ** 2)))
    d_neg = math.sqrt(float(np.sum(w * v ** 2)))
    denom = d_pos + d_neg
    if denom < 1e-12:
        return 0.5
    return d_neg / denom


# ─────────────────────────────────────────────
# 主入口
# ─────────────────────────────────────────────

def compute_match(
    user_profile: dict[str, Any],
    job: dict[str, Any],
    skill_corpus: list[list[str]],
    tag_freq: dict[str, float],
) -> dict[str, Any]:
    """
    计算单个用户画像与单个岗位的五维度得分。

    user_profile 字段:
        skills       list[str]   技能列表
        interests    list[str]   兴趣列表
        grade        str         年级
        has_project  bool        是否有相关项目经验
        free_hours   float       每周空闲小时数
        preferences  dict        偏好 (company_size, industry, work_env)

    skill_corpus: 所有岗位 required_skills 列表 (用于计算 IDF)
    tag_freq:     标签语料频率字典 (用于 SIF)
    """
    skills = user_profile.get("skills", [])
    interests = user_profile.get("interests", [])
    grade = user_profile.get("grade", "大二")
    has_project = bool(user_profile.get("has_project", False))
    free_hours = float(user_profile.get("free_hours", 20))
    intern_period = user_profile.get("intern_period", "")
    prefs = user_profile.get("preferences", {})

    d1 = _d1_skill(skills, job, skill_corpus)
    d2 = _d2_time(free_hours, job, intern_period)
    d3 = _d3_interest(interests, job, tag_freq)
    d4 = _d4_ability(grade, has_project, job)
    d5 = _d5_culture(prefs, job)

    return {
        "job_id": job.get("id", ""),
        "_dim_vec": np.array([d1, d2, d3, d4, d5]),
        "dimensions": {
            "d1_skill": round(d1, 4),
            "d2_time": round(d2, 4),
            "d3_interest": round(d3, 4),
            "d4_ability": round(d4, 4),
            "d5_culture": round(d5, 4),
        },
    }


def rank_jobs(
    user_profile: dict[str, Any],
    jobs: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    对所有岗位打分，用 TOPSIS + 熵权法 综合排序。

    流程:
      1. 计算每个岗位的五维度原始得分
      2. 用熵权法从得分矩阵动态计算权重
      3. 最终权重 = 0.6·W_static + 0.4·W_entropy
      4. 用 TOPSIS 计算每个岗位的综合贴近度
      5. 按贴近度降序排列
    """
    if not jobs:
        return []

    # ── 预计算语料统计量 ──
    skill_corpus = [job.get("required_skills", []) for job in jobs]
    tag_freq = _build_tag_freq(jobs)

    # ── Step 1: 计算五维度原始得分 ──
    raw_results = []
    for job in jobs:
        res = compute_match(user_profile, job, skill_corpus, tag_freq)
        raw_results.append(res)

    # ── Step 2: 熵权法动态权重 ──
    score_matrix = np.stack([r["_dim_vec"] for r in raw_results])  # (n, 5)
    # 加小量避免全零列导致熵权崩溃
    score_matrix = np.clip(score_matrix + 1e-6, 0, 1)
    w_entropy = _entropy_weights(score_matrix)

    # ── Step 3: 混合权重 ──
    alpha = 0.6  # 静态权重信任度
    w_final = alpha * W_STATIC + (1 - alpha) * w_entropy
    w_final = w_final / w_final.sum()  # 归一化

    logger.info(
        f"权重 | 静态={W_STATIC} | 熵权={np.round(w_entropy,3)} | 最终={np.round(w_final,3)}"
    )

    # ── Step 4: TOPSIS 综合贴近度 ──
    results = []
    for job, res in zip(jobs, raw_results):
        v = res["_dim_vec"]
        topsis = _topsis_score(v, w_final)
        merged = {
            **job,
            "job_id": res["job_id"],
            "total_score": round(topsis, 4),
            "dimensions": res["dimensions"],
            "weights_used": {
                "d1_skill": round(w_final[0], 4),
                "d2_time": round(w_final[1], 4),
                "d3_interest": round(w_final[2], 4),
                "d4_ability": round(w_final[3], 4),
                "d5_culture": round(w_final[4], 4),
            },
        }
        results.append(merged)

    results.sort(key=lambda x: x["total_score"], reverse=True)
    return results
