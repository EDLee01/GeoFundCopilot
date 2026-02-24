"""
元数据查询
批量获取、统计、滚动遍历
"""

from __future__ import annotations

from qdrant_client import models
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from geomind_sdk.client import GeoMindClient


class MetadataStore:
    """
    论文元数据查询

    用法:
        store = MetadataStore(client)
        papers = store.batch_get([0, 1, 2])
        count = store.count(year_from=2020, jcr_zone="Q1")
    """

    def __init__(self, client: GeoMindClient):
        self.client = client
        self.qdrant = client.qdrant
        self.collection = client.collection

    def batch_get(self, paper_ids: list[int | str]) -> list[dict]:
        """批量获取论文完整元数据"""
        from geomind_sdk.search import SearchEngine

        points = self.qdrant.retrieve(
            collection_name=self.collection,
            ids=paper_ids,
            with_payload=True,
            with_vectors=False,
        )

        return [
            {**SearchEngine._format_payload(p.payload), "id": p.id}
            for p in points
        ]

    def get_one(self, paper_id: int | str) -> dict | None:
        results = self.batch_get([paper_id])
        return results[0] if results else None

    def count(
        self,
        year_from: int = None,
        year_to: int = None,
        journal: str = None,
        cas_zone: int = None,
        jcr_zone: str = None,
    ) -> int:
        """统计满足条件的论文数量"""
        conditions = []
        if year_from is not None:
            conditions.append(
                models.FieldCondition(key="publication_year", range=models.Range(gte=year_from))
            )
        if year_to is not None:
            conditions.append(
                models.FieldCondition(key="publication_year", range=models.Range(lte=year_to))
            )
        if journal is not None:
            conditions.append(
                models.FieldCondition(key="journal_name", match=models.MatchValue(value=journal))
            )
        if cas_zone is not None:
            conditions.append(
                models.FieldCondition(key="cas_zone", match=models.MatchValue(value=cas_zone))
            )
        if jcr_zone is not None:
            conditions.append(
                models.FieldCondition(key="jcr_zone", match=models.MatchValue(value=jcr_zone))
            )

        count_filter = models.Filter(must=conditions) if conditions else None

        result = self.qdrant.count(
            collection_name=self.collection,
            count_filter=count_filter,
            exact=False,
        )
        return result.count
