import logging
import os
from typing import List

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

_model = None


def _configure_hf_hub() -> None:
    """
    在首次拉取模型前生效（避免 huggingface.co 连接超时）。
    - .env 里设置 HF_ENDPOINT=https://hf-mirror.com（或其它镜像）
    - 或设置 USE_HF_MIRROR=1 自动使用 hf-mirror.com
    """
    if os.environ.get("USE_HF_MIRROR", "").lower() in ("1", "true", "yes"):
        os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
        logger.info("USE_HF_MIRROR=1 → HF_ENDPOINT=%s", os.environ["HF_ENDPOINT"])

    ep = os.environ.get("HF_ENDPOINT", "").strip()
    if ep:
        logger.info("使用 Hugging Face 端点: %s", ep)

    # 弱网下拉长下载超时（秒）；可自行在环境变量里覆盖
    os.environ.setdefault("HF_HUB_DOWNLOAD_TIMEOUT", "120")


def get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        _configure_hf_hub()
        logger.info("Loading sentence-transformers model...")
        _model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
        logger.info("Model loaded.")
    return _model

def embed(texts: List[str]) -> np.ndarray:
    """将文本列表转为 embedding 向量矩阵，shape=(n, dim)"""
    model = get_model()
    return model.encode(texts, normalize_embeddings=True)

def embed_single(text: str) -> np.ndarray:
    """单条文本转向量"""
    return embed([text])[0]

def cosine_sim(vec_a: np.ndarray, vec_b: np.ndarray) -> float:
    """计算两个向量的余弦相似度，返回 [0, 1] 的浮点数"""
    a = vec_a.reshape(1, -1)
    b = vec_b.reshape(1, -1)
    score = cosine_similarity(a, b)[0][0]
    return float(np.clip(score, 0.0, 1.0))

def avg_pool_embed(texts: List[str]) -> np.ndarray:
    """多条文本 embedding 取均值，代表整体语义"""
    if not texts:
        return np.zeros(384)
    vecs = embed(texts)
    return np.mean(vecs, axis=0)
