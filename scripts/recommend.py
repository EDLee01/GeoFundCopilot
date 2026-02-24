#!/usr/bin/env python3
"""
GeoFund 文献推荐 — nanobot ExecTool 入口

用法:
    python scripts/recommend.py "研究方向描述"
    python scripts/recommend.py "graph neural network water quality" --top_k 20
    python scripts/recommend.py "遥感水质反演" --no-verify
    python scripts/recommend.py "dissolved oxygen prediction" --json
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from geomind_sdk import GeoMindClient, SearchEngine, CitationFormatter
from geomind_sdk.copilot import GeoFundCopilot


def main():
    parser = argparse.ArgumentParser(description="GeoFund 智能文献推荐")
    parser.add_argument("query", help="研究方向描述（中英文均可）")
    parser.add_argument("--top_k", type=int, default=15, help="推荐论文数量")
    parser.add_argument("--no-verify", action="store_true", help="跳过 DOI 验证")
    parser.add_argument("--json", action="store_true", help="输出 JSON 格式")
    args = parser.parse_args()

    # DeepSeek API Key
    api_key = os.environ.get("DEEPSEEK_API_KEY", "")
    if not api_key:
        # 尝试从 nanobot config 读取
        nanobot_config = os.path.expanduser("~/.nanobot/config.json")
        if os.path.exists(nanobot_config):
            try:
                with open(nanobot_config) as f:
                    cfg = json.load(f)
                api_key = cfg.get("providers", {}).get("deepseek", {}).get("apiKey", "")
            except Exception:
                pass
    if not api_key:
        print("ERROR: 未找到 DeepSeek API Key")
        print("设置方式: export DEEPSEEK_API_KEY=sk-xxx")
        sys.exit(1)

    # 初始化
    client = GeoMindClient()
    engine = SearchEngine(client)
    copilot = GeoFundCopilot(engine, deepseek_api_key=api_key)
    fmt = CitationFormatter()

    # 执行推荐
    result = copilot.recommend(
        args.query,
        top_k=args.top_k,
        verify=not args.no_verify,
        verbose=True,
    )

    # JSON 输出
    if args.json:
        # 清理不可序列化的字段
        output = {
            "query": result.get("query", ""),
            "total": result.get("total", 0),
            "rejected": result.get("rejected", False),
            "reject_reason": result.get("reject_reason", ""),
            "recommendations": {},
        }
        for cat, papers in result.get("recommendations", {}).items():
            if isinstance(papers, list):
                output["recommendations"][cat] = [
                    {
                        "title": p.get("title", ""),
                        "first_author": p.get("first_author", ""),
                        "authors_count": p.get("authors_count", 0),
                        "journal": p.get("journal", ""),
                        "year": p.get("year", 0),
                        "cited_by": p.get("cited_by", 0),
                        "doi": p.get("doi", ""),
                        "jcr_zone": p.get("jcr_zone", ""),
                        "cas_zone": p.get("cas_zone", 0),
                        "reason": p.get("reason", ""),
                        "verified": p.get("verified", False),
                        "source": p.get("source", ""),
                    }
                    for p in papers
                ]
        print(json.dumps(output, ensure_ascii=False, indent=2))
        return

    # 文本输出
    if result.get("rejected"):
        print(f"\n⚠️ 未找到匹配的论文")
        print(f"原因: {result.get('reject_reason', '候选论文与需求不匹配')}")
        print(f"建议: 请更具体地描述你的研究方向，包含方法、应用场景、研究区域")
        return

    if result["total"] == 0:
        print("\n⚠️ 未找到相关论文，请尝试更具体的描述")
        return

    # 验证统计
    vs = result.get("verification_summary", {})
    if vs:
        print(f"\n✅ 验证: {vs.get('verified', 0)}/{vs.get('total', 0)} 篇通过", end="")
        if vs.get("failed", 0) > 0:
            print(f" | ❌ {vs['failed']} 篇未通过（已移除）", end="")
        print()

    # 分类展示
    categories = [
        ("foundational", "📖 必引经典", "领域奠基性工作，不引会被评审质疑"),
        ("cutting_edge", "🔬 前沿进展", "近年最新研究，展现对前沿的把握"),
        ("methodological", "⚙️ 方法借鉴", "与你拟用方法直接相关"),
        ("reviewer_relevant", "👤 潜在评审人", "该方向活跃学者，引用可提升好感"),
    ]

    recs = result["recommendations"]
    for cat_key, cat_title, cat_desc in categories:
        papers = recs.get(cat_key, [])
        if not papers:
            continue

        print(f"\n{'─' * 60}")
        print(f"  {cat_title}  ({len(papers)} 篇)")
        print(f"  {cat_desc}")
        print(f"{'─' * 60}")

        for i, p in enumerate(papers, 1):
            source_icon = "📦" if p.get("source") == "qdrant" else "🌐"
            verified_icon = "✅" if p.get("verified") else "⚠️"
            print(f"\n  {i}. {source_icon}{verified_icon} {p.get('title', 'Untitled')[:70]}")

            # 作者
            first = p.get("first_author", "")
            n = p.get("authors_count", 0)
            if first:
                author_str = f"{first} et al. ({n}人)" if n > 2 else first
                print(f"     👤 {author_str}")

            # 元数据
            meta = []
            if p.get("journal"):
                meta.append(p["journal"])
            if p.get("year"):
                meta.append(str(p["year"]))
            meta.append(f"Cited: {p.get('cited_by', 0)}")
            if p.get("jcr_zone"):
                meta.append(p["jcr_zone"])
            if p.get("cas_zone"):
                cas_label = {1: "一区", 2: "二区", 3: "三区", 4: "四区"}.get(p["cas_zone"], "")
                if cas_label:
                    meta.append(f"中科院{cas_label}")
            print(f"     📖 {' | '.join(meta)}")

            if p.get("reason"):
                print(f"     💬 {p['reason']}")
            if p.get("doi"):
                print(f"     🔗 {p['doi']}")

    # 参考文献列表（去重）
    all_papers = []
    seen_dois = set()
    for cat_key, _, _ in categories:
        for p in recs.get(cat_key, []):
            doi = p.get("doi", "").lower().strip()
            title_key = p.get("title", "").lower().strip()[:80]
            dedup_key = doi if doi else title_key
            if dedup_key and dedup_key not in seen_dois:
                seen_dois.add(dedup_key)
                all_papers.append(p)

    if all_papers:
        print(f"\n{'=' * 60}")
        print(f"  📎 参考文献列表 (GB/T 7714) — 共 {len(all_papers)} 篇")
        print(f"{'=' * 60}")
        print(fmt.format_list(all_papers, style="gbt7714"))


if __name__ == "__main__":
    main()
