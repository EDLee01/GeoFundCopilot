"""
Qdrant 连接管理

⚠️ 公共 API Key 有效期至 2026-03-15，届时将撤回。
   之后请在 config/config.json 中配置自己的 Key。
"""

from __future__ import annotations

import json
from pathlib import Path
from qdrant_client import QdrantClient

# ============================================================
# 默认配置（公共体验，2026-03-15 后失效）
# ============================================================
DEFAULTS = {
    "qdrant": {
        "url": "https://eec5ae99-7f4a-4de3-b0ae-754cf6306c95.us-east4-0.gcp.cloud.qdrant.io:6333",
        "api_key": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhY2Nlc3MiOiJtIn0.MD5vOsUTXmGxSqMob2HsYno_2UyfVNPqgTmI-2p8cZc",
        "collection": "geomind_papers",
        "timeout": 60,
    },
    "embedding": {
        "model": "BAAI/bge-base-en-v1.5",
        "dimension": 768,
    },
}

CONFIG_PATHS = [
    Path("config/config.json"),
    Path(__file__).parent.parent / "config/config.json",
    Path.home() / ".geofund/config.json",
]


def load_config(config_path: str | Path = None) -> dict:
    """加载配置: config.json > 硬编码默认值"""
    if config_path:
        p = Path(config_path)
        if p.exists():
            return json.loads(p.read_text())

    for p in CONFIG_PATHS:
        if p.exists():
            return json.loads(p.read_text())

    return DEFAULTS.copy()


class GeoMindClient:
    """
    GeoMind 客户端

    用法:
        client = GeoMindClient()          # 内置公共 Key
        client = GeoMindClient("my.json") # 自定义配置
    """

    def __init__(self, config_path: str | Path = None):
        self.config = load_config(config_path)
        qcfg = self.config["qdrant"]

        self.qdrant = QdrantClient(
            url=qcfg["url"],
            api_key=qcfg["api_key"],
            timeout=qcfg.get("timeout", 60),
        )
        self.collection = qcfg["collection"]
        self.embedding_model = self.config.get("embedding", {}).get(
            "model", "BAAI/bge-base-en-v1.5"
        )
        self.embedding_dim = self.config.get("embedding", {}).get("dimension", 768)

    def info(self) -> dict:
        col = self.qdrant.get_collection(self.collection)
        return {
            "collection": self.collection,
            "points_count": col.points_count,
            "vector_size": col.config.params.vectors.size,
            "distance": str(col.config.params.vectors.distance),
            "status": str(col.status),
        }

    def health_check(self) -> bool:
        try:
            self.qdrant.get_collections()
            return True
        except Exception:
            return False
