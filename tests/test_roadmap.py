#!/usr/bin/env python3
"""
技术路线图 SVG 生成测试

用法:
    export DEEPSEEK_API_KEY=sk-xxx
    python tests/test_roadmap.py
    # 生成的 SVG 会保存到 tests/output/ 目录
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from geomind_sdk import GeoMindClient, SearchEngine
from geomind_sdk.roadmap import RoadmapGenerator

# ============================================================
# 测试用例
# ============================================================

TEST_CASES = [
    {
        "name": "GNN水质预测",
        "direction": "基于图神经网络的流域水质时空预测方法研究",
        "innovation": (
            "1) 提出GATCN模型，融合图注意力机制与时空卷积，捕捉站点间动态关联\n"
            "2) 引入GNNExplainer实现水质预测的可解释性分析\n"
            "3) 珠江流域多站点实证，构建流域水系拓扑图"
        ),
        "phases": 5,
    },
    {
        "name": "遥感水质反演",
        "direction": "基于深度学习与多源遥感数据融合的内陆水体水质参数反演研究",
        "innovation": (
            "1) 提出光谱-空间联合注意力网络(SSANet)融合Sentinel-2多光谱与无人机高光谱\n"
            "2) 构建物理约束损失函数，嵌入水体辐射传输先验知识"
        ),
        "phases": 4,
    },
    {
        "name": "滑坡易发性评估",
        "direction": "基于InSAR时序形变与机器学习的区域滑坡易发性动态评估",
        "innovation": "",
        "phases": 5,
    },
]


def main():
    api_key = os.environ.get("DEEPSEEK_API_KEY", "")
    if not api_key:
        print("❌ 请设置 DEEPSEEK_API_KEY")
        sys.exit(1)

    output_dir = os.path.join(os.path.dirname(__file__), "output")
    os.makedirs(output_dir, exist_ok=True)

    client = GeoMindClient()
    engine = SearchEngine(client)
    generator = RoadmapGenerator(engine, deepseek_api_key=api_key)

    for case in TEST_CASES:
        print(f"\n{'='*60}")
        print(f"  测试: {case['name']}")
        print(f"{'='*60}")

        try:
            result = generator.generate(
                case["direction"],
                innovation_points=case["innovation"],
                num_phases=case["phases"],
                verbose=True,
            )

            svg = result.get("svg", "")
            if not svg:
                print(f"  ❌ 未生成 SVG")
                continue

            # 保存 SVG
            safe_name = case["name"].replace("/", "_")
            svg_path = os.path.join(output_dir, f"roadmap_{safe_name}.svg")
            with open(svg_path, "w", encoding="utf-8") as f:
                f.write(svg)
            print(f"\n  ✅ SVG 已保存: {svg_path}")
            print(f"     大小: {len(svg):,} 字节")

            # 打印路线图摘要
            phases = result.get("phases", [])
            print(f"     阶段数: {len(phases)}")
            for p in phases:
                tasks = p.get("tasks", [])
                methods = p.get("methods", [])
                print(f"     Phase {p.get('id','?')}: {p.get('name','?')} "
                      f"({len(tasks)} 任务, {len(methods)} 方法)")

            innovations = result.get("key_innovations", [])
            if innovations:
                print(f"     创新点: {len(innovations)} 个")

            expected = result.get("expected_results", [])
            if expected:
                print(f"     预期成果: {len(expected)} 条")

        except Exception as e:
            print(f"  ❌ 失败: {e}")
            import traceback
            traceback.print_exc()

    print(f"\n{'='*60}")
    print(f"  所有 SVG 保存在: {output_dir}/")
    print(f"  用浏览器打开 .svg 文件即可查看效果")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
