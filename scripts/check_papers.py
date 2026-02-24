#!/usr/bin/env python3
"""
检查特定论文是否在 Qdrant 数据库中

用法:
    python scripts/check_papers.py
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from qdrant_client.models import Filter, FieldCondition, MatchValue
from geomind_sdk import GeoMindClient, SearchEngine

client = GeoMindClient()
engine = SearchEngine(client)

# ── 要检查的论文 ──
papers_to_check = [
    {
        "label": "Wei Zhi - EST 2021",
        "doi": "https://doi.org/10.1021/acs.est.0c06783",
        "title": "From Hydrometeorology to River Water Quality: Can a Deep Learning Model Predict Dissolved Oxygen at the Continental Scale?",
    },
    {
        "label": "Wei Zhi - Nature Water 2023",
        "doi": "https://doi.org/10.1038/s44221-023-00038-z",
        "title": "Temperature outweighs light and flow as the predominant driver of dissolved oxygen in US rivers",
    },
]

print(f"📊 论文库: {client.info()['points_count']} 篇")
print(f"{'='*70}\n")

for p in papers_to_check:
    print(f"🔍 {p['label']}")
    print(f"   DOI: {p['doi']}")
    found = False

    # 方法1: DOI 精确匹配
    for doi_variant in [p["doi"], p["doi"].replace("https://doi.org/", "")]:
        try:
            results, _ = client.qdrant.scroll(
                collection_name=client.collection,
                scroll_filter=Filter(must=[
                    FieldCondition(key="doi", match=MatchValue(value=doi_variant))
                ]),
                limit=3,
                with_payload=True,
            )
            if results:
                found = True
                r = results[0]
                pl = r.payload
                print(f"   ✅ DOI 匹配命中! (id={r.id})")
                print(f"      title: {pl.get('title', '?')[:80]}")
                print(f"      doi: {pl.get('doi', '?')}")
                print(f"      year: {pl.get('publication_year', '?')}")
                print(f"      journal: {pl.get('journal_name', '?')}")
                print(f"      cited_by: {pl.get('cited_by_count', '?')}")
                print(f"      authors: {pl.get('authors', '?')[:100] if pl.get('authors') else '?'}")
                print(f"      doi_verified: {pl.get('doi_verified', '?')}")
                break
        except Exception as e:
            print(f"   ⚠️ DOI scroll error: {e}")

    if not found:
        print(f"   ❌ DOI 未命中，尝试语义检索...")

        # 方法2: 向量语义检索（用标题）
        try:
            results = engine.search(p["title"], top_k=5)
            print(f"   语义 Top5:")
            for i, r in enumerate(results):
                score = r.get("score", 0)
                title = r.get("title", "?")[:70]
                doi = r.get("doi", "无DOI")
                year = r.get("year", "?")
                marker = "⭐" if p["title"].lower()[:30] in title.lower() else "  "
                print(f"   {marker} [{i+1}] score={score:.3f} | {year} | {title}")
                print(f"         doi: {doi}")
        except Exception as e:
            print(f"   ⚠️ 语义检索失败: {e}")

    print()

print(f"{'='*70}")
print("完成")
