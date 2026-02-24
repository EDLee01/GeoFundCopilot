"""
语义检索引擎
"""

from __future__ import annotations

import re
import numpy as np
from qdrant_client import models
from sklearn.cluster import KMeans
from collections import Counter
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from geomind_sdk.client import GeoMindClient


def strip_html(text: str) -> str:
    """去掉 HTML 标签"""
    if not text:
        return ""
    return re.sub(r"<[^>]+>", "", text).strip()


class SearchEngine:

    def __init__(self, client: GeoMindClient, encoder=None):
        self.client = client
        self.qdrant = client.qdrant
        self.collection = client.collection
        self._encoder = encoder

    @property
    def encoder(self):
        if self._encoder is None:
            from sentence_transformers import SentenceTransformer
            print(f"🔄 加载模型 {self.client.embedding_model}...")
            self._encoder = SentenceTransformer(self.client.embedding_model)
            print("✅ 模型加载完成")
        return self._encoder

    def encode(self, text: str) -> list[float]:
        return self.encoder.encode(text).tolist()

    def search(
        self,
        query: str,
        top_k: int = 50,
        year_from: int = None,
        year_to: int = None,
        journal: str = None,
        min_citations: int = None,
        cas_zone: int = None,
        jcr_zone: str = None,
        field: str = None,
    ) -> list[dict]:
        query_vector = self.encode(query)
        return self.search_by_vector(
            query_vector, top_k=top_k, year_from=year_from, year_to=year_to,
            journal=journal, min_citations=min_citations, cas_zone=cas_zone,
            jcr_zone=jcr_zone, field=field,
        )

    def search_by_vector(
        self,
        vector: list[float],
        top_k: int = 50,
        year_from: int = None,
        year_to: int = None,
        journal: str = None,
        min_citations: int = None,
        cas_zone: int = None,
        jcr_zone: str = None,
        field: str = None,
    ) -> list[dict]:
        conditions = []
        if year_from is not None:
            conditions.append(models.FieldCondition(key="publication_year", range=models.Range(gte=year_from)))
        if year_to is not None:
            conditions.append(models.FieldCondition(key="publication_year", range=models.Range(lte=year_to)))
        if journal is not None:
            conditions.append(models.FieldCondition(key="journal_name", match=models.MatchValue(value=journal)))
        if min_citations is not None:
            conditions.append(models.FieldCondition(key="cited_by_count", range=models.Range(gte=min_citations)))
        if cas_zone is not None:
            conditions.append(models.FieldCondition(key="cas_zone", match=models.MatchValue(value=cas_zone)))
        if jcr_zone is not None:
            conditions.append(models.FieldCondition(key="jcr_zone", match=models.MatchValue(value=jcr_zone)))
        if field is not None:
            conditions.append(models.FieldCondition(key="field", match=models.MatchValue(value=field)))

        query_filter = models.Filter(must=conditions) if conditions else None

        response = self.qdrant.query_points(
            collection_name=self.collection,
            query=vector,
            query_filter=query_filter,
            limit=top_k,
            with_payload=True,
        )

        return [self._format_hit(hit) for hit in response.points]

    def get_similar(self, paper_id: int | str, top_k: int = 10) -> list[dict]:
        points = self.qdrant.retrieve(
            collection_name=self.collection, ids=[paper_id],
            with_vectors=True, with_payload=True,
        )
        if not points:
            return []
        vector = points[0].vector
        if isinstance(vector, dict):
            vector = list(vector.values())[0]
        results = self.search_by_vector(vector, top_k=top_k + 1)
        return [r for r in results if r["id"] != paper_id][:top_k]

    def cluster(self, papers: list[dict], n_clusters: int = 5) -> list[dict]:
        if len(papers) < n_clusters:
            n_clusters = max(1, len(papers))
        paper_ids = [p["id"] for p in papers]
        points = self.qdrant.retrieve(
            collection_name=self.collection, ids=paper_ids,
            with_vectors=True, with_payload=True,
        )
        if not points:
            return []

        id_to_payload = {p.id: p.payload for p in points}
        vectors, valid_ids = [], []
        for p in points:
            vec = p.vector
            if isinstance(vec, dict):
                vec = list(vec.values())[0]
            vectors.append(vec)
            valid_ids.append(p.id)

        kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
        labels = kmeans.fit_predict(np.array(vectors))

        clusters = []
        for i in range(n_clusters):
            mask = labels == i
            cluster_ids = [valid_ids[j] for j in range(len(valid_ids)) if mask[j]]
            cluster_payloads = [id_to_payload[pid] for pid in cluster_ids]
            cluster_payloads.sort(key=lambda x: x.get("cited_by_count", 0), reverse=True)
            clusters.append({
                "cluster_id": i,
                "paper_count": len(cluster_payloads),
                "top_concepts": self._extract_concepts(cluster_payloads),
                "top_journals": self._extract_journals(cluster_payloads),
                "key_papers": [self._format_payload(p) for p in cluster_payloads[:5]],
            })
        clusters.sort(key=lambda x: x["paper_count"], reverse=True)
        return clusters

    # ============================================================
    # 格式化
    # ============================================================

    def _format_hit(self, hit) -> dict:
        result = self._format_payload(hit.payload)
        result["id"] = hit.id
        result["score"] = round(hit.score, 4)
        return result

    @staticmethod
    def _format_payload(p: dict) -> dict:
        """
        payload → 统一 dict
        兼容多种格式，清理 HTML，容错缺失字段
        """
        # 标题/摘要: 清理 HTML
        title = strip_html(p.get("title", "") or "")
        abstract = strip_html(p.get("abstract", "") or "")

        # 作者: 兼容 list[dict] 和 list[str]
        authors_raw = p.get("authors", []) or []
        author_names = []
        first_author = ""
        last_author = ""

        if authors_raw:
            if isinstance(authors_raw[0], dict):
                for a in authors_raw:
                    name = a.get("name", "")
                    if name:
                        author_names.append(name)
                    if a.get("position") == "first":
                        first_author = name
                    elif a.get("position") == "last":
                        last_author = name
            elif isinstance(authors_raw[0], str):
                author_names = [a for a in authors_raw if a]

        if not first_author and author_names:
            first_author = author_names[0]
        if not last_author and len(author_names) > 1:
            last_author = author_names[-1]

        # authors_count: 优先字段值，fallback 列表长度
        authors_count = p.get("authors_count", 0) or 0
        if authors_count == 0 and author_names:
            authors_count = len(author_names)

        # 概念
        concepts_raw = p.get("concepts", []) or []
        concept_names = []
        if concepts_raw:
            if isinstance(concepts_raw[0], dict):
                concept_names = [c.get("name", "") for c in concepts_raw if c.get("name")]
            elif isinstance(concepts_raw[0], str):
                concept_names = concepts_raw

        # 基本字段
        year = p.get("publication_year", 0) or 0
        cited_by = p.get("cited_by_count", 0) or 0
        journal = strip_html(p.get("journal_name", "") or "")
        cas_zone = p.get("cas_zone", 0) or 0
        jcr_zone = p.get("jcr_zone", "") or ""

        return {
            "openalex_id": p.get("id", "") or "",
            "doi": p.get("doi", "") or "",
            "title": title,
            "abstract": abstract,
            "year": int(year) if year else 0,
            "cited_by": int(cited_by) if cited_by else 0,
            "journal": journal,
            "cas_zone": int(cas_zone) if isinstance(cas_zone, (int, float)) else 0,
            "jcr_zone": jcr_zone if isinstance(jcr_zone, str) else "",
            "field": p.get("field", "") or "",
            "primary_topic": p.get("primary_topic", "") or "",
            "authors": author_names,
            "first_author": first_author,
            "last_author": last_author,
            "authors_count": int(authors_count),
            "concepts": concept_names,
            "referenced_works": p.get("referenced_works", []) or [],
            "doi_verified": bool(p.get("doi_verified", False)),
        }

    @staticmethod
    def _extract_concepts(papers, top_k=8):
        all_concepts = []
        for p in papers:
            for c in (p.get("concepts", []) or []):
                if isinstance(c, dict) and c.get("score", 0) > 0.5:
                    all_concepts.append(c["name"])
                elif isinstance(c, str):
                    all_concepts.append(c)
        return [name for name, _ in Counter(all_concepts).most_common(top_k)]

    @staticmethod
    def _extract_journals(papers, top_k=5):
        journals = [p.get("journal_name", "") for p in papers if p.get("journal_name")]
        return [j for j, _ in Counter(journals).most_common(top_k)]
