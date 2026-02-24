#!/usr/bin/env python3
"""
GeoFund 引用格式化 — nanobot ExecTool 入口

用法:
    python scripts/format_refs.py --doi "10.1016/j.watres.2023.120001" --style gbt7714
    python scripts/format_refs.py --doi "10.1000/xxx" --doi "10.1000/yyy" --style bibtex
    python scripts/format_refs.py --doi "10.1000/xxx" --style apa
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from geomind_sdk import CitationFormatter
from geomind_sdk.crossref import CrossRefClient


def main():
    parser = argparse.ArgumentParser(description="GeoFund 引用格式化")
    parser.add_argument("--doi", action="append", required=True, help="DOI（可多次指定）")
    parser.add_argument("--style", default="gbt7714", choices=["gbt7714", "bibtex", "apa"],
                        help="引用格式，默认 gbt7714")
    args = parser.parse_args()

    cr = CrossRefClient()
    fmt = CitationFormatter()
    papers = []

    print(f"🔍 正在查询 {len(args.doi)} 篇论文...")

    for doi in args.doi:
        doi = doi.strip()
        paper = cr.get_by_doi(doi)
        if paper:
            papers.append(paper)
            print(f"  ✅ {paper.get('title', 'Untitled')[:60]}")
        else:
            print(f"  ❌ DOI 未找到: {doi}")

    if not papers:
        print("\n⚠️ 没有成功查询到任何论文")
        return

    print(f"\n{'=' * 60}")
    print(f"  📎 参考文献 ({args.style.upper()} 格式)")
    print(f"{'=' * 60}")
    print(fmt.format_list(papers, style=args.style))


if __name__ == "__main__":
    main()
