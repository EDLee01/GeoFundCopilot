#!/usr/bin/env python3
"""
GeoFund 创新点查重 — nanobot ExecTool 入口

用法:
    python scripts/novelty_check.py "创新点描述"
    python scripts/novelty_check.py "利用GATCN预测珠江流域溶解氧" --json
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from geomind_sdk import GeoMindClient, SearchEngine
from geomind_sdk.novelty import NoveltyChecker


def main():
    parser = argparse.ArgumentParser(description="GeoFund 创新点查重")
    parser.add_argument("innovation", help="创新点描述（中英文均可）")
    parser.add_argument("--json", action="store_true", help="输出 JSON 格式")
    args = parser.parse_args()

    # DeepSeek API Key
    api_key = os.environ.get("DEEPSEEK_API_KEY", "")
    if not api_key:
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
    checker = NoveltyChecker(engine, deepseek_api_key=api_key)

    # 执行查重
    report = checker.check(args.innovation, verbose=True)

    # JSON 输出
    if args.json:
        output = {
            "innovation_point": report.get("innovation_point", ""),
            "novelty_score": report.get("novelty_score", 0),
            "verdict": report.get("verdict", ""),
            "overlap_analysis": report.get("overlap_analysis", {}),
            "most_threatening": [
                {
                    "threat_level": t.get("threat_level", ""),
                    "overlap_dimensions": t.get("overlap_dimensions", []),
                    "analysis": t.get("analysis", ""),
                    "paper": t.get("paper", {}),
                }
                for t in report.get("most_threatening", [])
            ],
            "unique_aspects": report.get("unique_aspects", []),
            "suggestions": report.get("suggestions", []),
        }
        print(json.dumps(output, ensure_ascii=False, indent=2))
        return

    # 文本输出
    score = report.get("novelty_score", 0)
    verdict = report.get("verdict", "")

    if score >= 8:
        bar = "🟢" * score + "⚪" * (10 - score)
    elif score >= 5:
        bar = "🟡" * score + "⚪" * (10 - score)
    else:
        bar = "🔴" * score + "⚪" * (10 - score)

    print(f"\n{'=' * 60}")
    print(f"  🔬 创新点新颖度评估报告")
    print(f"{'=' * 60}")
    print(f"\n  创新点: {args.innovation}")
    print(f"\n  评分: {score}/10  {bar}")
    print(f"  结论: {verdict}")

    # 重叠分析
    overlap = report.get("overlap_analysis", {})
    if overlap:
        print(f"\n  📊 四维度重叠分析:")
        labels = {"method": "🔧 方法", "application": "🎯 应用", "region": "🌍 区域", "data_source": "📊 数据"}
        for dim, analysis in overlap.items():
            label = labels.get(dim, dim)
            if analysis:
                print(f"    {label}: {analysis}")

    # 最威胁论文
    threats = report.get("most_threatening", [])
    if threats:
        print(f"\n  ⚠️ 最相似的 {len(threats)} 篇论文:")
        for t in threats:
            paper = t.get("paper", {})
            level = t.get("threat_level", "?")
            level_icon = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(level, "⚪")
            dims = ", ".join(t.get("overlap_dimensions", []))

            print(f"\n    {level_icon} [{level}] {paper.get('title', '?')[:60]}")
            meta = []
            if paper.get("first_author"):
                meta.append(paper["first_author"])
            if paper.get("journal"):
                meta.append(paper["journal"])
            if paper.get("year"):
                meta.append(str(paper["year"]))
            meta.append(f"Cited:{paper.get('cited_by', 0)}")
            print(f"       {' | '.join(meta)}")
            print(f"       重叠维度: {dims}")
            if t.get("analysis"):
                print(f"       分析: {t['analysis']}")

    # 独特之处
    unique = report.get("unique_aspects", [])
    if unique:
        print(f"\n  ✨ 独特之处:")
        for u in unique:
            print(f"    • {u}")

    # 建议
    suggestions = report.get("suggestions", [])
    if suggestions:
        print(f"\n  💡 改写建议:")
        for s in suggestions:
            print(f"    • {s}")


if __name__ == "__main__":
    main()
