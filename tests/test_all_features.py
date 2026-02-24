#!/usr/bin/env python3
"""
GeoFund Copilot — 功能测试脚本

用法:
    export DEEPSEEK_API_KEY=sk-xxx
    python tests/test_all_features.py              # 跑全部测试
    python tests/test_all_features.py --quick      # 只跑快速测试（不调 LLM）
    python tests/test_all_features.py --feature recommend  # 只测某个功能
"""

import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from geomind_sdk import (
    GeoMindClient, SearchEngine, CitationFormatter,
    TrendAnalyzer, ReviewerSimulator,
)
from geomind_sdk.copilot import GeoFundCopilot
from geomind_sdk.novelty import NoveltyChecker

# ============================================================
# 测试用例
# ============================================================

# --- 文献推荐测试 ---
RECOMMEND_CASES = [
    {
        "name": "水质预测-GNN",
        "query": "用图神经网络预测珠江流域溶解氧浓度",
        "expect_categories": ["foundational", "cutting_edge", "methodological"],
        "expect_min_total": 5,
    },
    {
        "name": "遥感反演",
        "query": "基于Sentinel-2遥感影像的湖泊叶绿素a浓度反演方法",
        "expect_categories": ["foundational", "cutting_edge"],
        "expect_min_total": 5,
    },
    {
        "name": "地震预测-深度学习",
        "query": "deep learning earthquake early warning seismology",
        "expect_categories": ["foundational"],
        "expect_min_total": 3,
    },
    {
        "name": "碳通量估算",
        "query": "全球陆地生态系统碳通量的机器学习估算与不确定性分析",
        "expect_categories": ["foundational", "methodological"],
        "expect_min_total": 5,
    },
    {
        "name": "边界测试-模糊输入",
        "query": "水",
        "expect_categories": [],
        "expect_min_total": 0,
        "may_reject": True,
    },
]

# --- 创新点查重测试 ---
NOVELTY_CASES = [
    {
        "name": "GATCN可解释预测",
        "innovation": "结合图注意力时空卷积网络(GATCN)和GNNExplainer实现珠江流域溶解氧的可解释时空预测",
        "expect_score_range": [4, 9],
        "expect_has_threats": True,
    },
    {
        "name": "高度新颖-跨域融合",
        "innovation": "利用大语言模型自动解析地质钻孔报告，构建三维地质知识图谱并融合InSAR形变数据进行滑坡易发性动态评估",
        "expect_score_range": [6, 10],
        "expect_has_threats": False,
    },
    {
        "name": "低新颖度-已有大量工作",
        "innovation": "使用LSTM预测水质参数",
        "expect_score_range": [1, 5],
        "expect_has_threats": True,
    },
]

# --- 研究趋势测试 ---
TREND_CASES = [
    {
        "name": "深度学习水质",
        "query": "deep learning water quality prediction",
        "year_from": 2015,
        "year_to": 2025,
        "expect_min_papers": 10,
        "expect_has_milestones": True,
    },
    {
        "name": "InSAR地面沉降",
        "query": "InSAR ground subsidence monitoring",
        "year_from": 2010,
        "year_to": 2025,
        "expect_min_papers": 10,
        "expect_has_milestones": True,
    },
]

# --- 评审视角测试 ---
REVIEWER_CASES = [
    {
        "name": "标准评审",
        "direction": "基于图神经网络的流域水质时空预测方法研究",
        "innovation": "1) 提出GATCN融合图注意力与时空卷积 2) GNNExplainer实现可解释性",
        "expect_has_questions": True,
        "expect_has_suggestions": True,
    },
    {
        "name": "无创新点评审",
        "direction": "利用深度强化学习优化城市排水管网的实时调度策略",
        "innovation": "",
        "expect_has_questions": True,
        "expect_has_suggestions": True,
    },
]


# ============================================================
# 测试运行器
# ============================================================

class TestRunner:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.client = GeoMindClient()
        self.engine = SearchEngine(self.client)
        self.results = []

    def log(self, status, name, msg="", elapsed=0):
        icon = {"PASS": "✅", "FAIL": "❌", "SKIP": "⏭️", "WARN": "⚠️"}[status]
        time_str = f" ({elapsed:.1f}s)" if elapsed else ""
        print(f"  {icon} [{status}] {name}{time_str}")
        if msg:
            print(f"       {msg}")
        self.results.append({"status": status, "name": name, "msg": msg})

    # --- 快速测试（不调 LLM）---

    def test_sdk_connection(self):
        """测试 Qdrant 连接"""
        print("\n📡 SDK 连接测试")
        try:
            info = self.client.info()
            count = info.get("points_count", 0)
            if count > 0:
                self.log("PASS", "Qdrant连接", f"论文数: {count:,}")
            else:
                self.log("FAIL", "Qdrant连接", "论文数为0")
        except Exception as e:
            self.log("FAIL", "Qdrant连接", str(e))

    def test_search_basic(self):
        """测试基础搜索"""
        print("\n🔍 基础搜索测试")
        queries = [
            "dissolved oxygen prediction river",
            "remote sensing water quality",
            "earthquake early warning deep learning",
        ]
        for q in queries:
            t0 = time.time()
            try:
                results = self.engine.search(q, top_k=10)
                elapsed = time.time() - t0
                if len(results) > 0:
                    top_title = results[0].get("title", "?")[:60]
                    self.log("PASS", f"搜索: {q[:40]}", f"{len(results)} 篇, top1: {top_title}", elapsed)
                else:
                    self.log("WARN", f"搜索: {q[:40]}", "返回 0 篇", elapsed)
            except Exception as e:
                self.log("FAIL", f"搜索: {q[:40]}", str(e))

    def test_formatter(self):
        """测试引用格式化"""
        print("\n📎 格式化测试")
        fmt = CitationFormatter()
        fake_paper = {
            "title": "Test Paper Title",
            "first_author": "Zhang San",
            "authors_count": 3,
            "journal": "Water Research",
            "year": 2024,
            "doi": "https://doi.org/10.1016/j.watres.2024.000001",
        }
        style_fn = {"gbt7714": fmt.gbt7714, "bibtex": fmt.bibtex, "apa": fmt.apa}
        for style, fn in style_fn.items():
            try:
                text = fn(fake_paper)
                if text and len(text) > 10:
                    self.log("PASS", f"格式化-{style}", text[:80])
                else:
                    self.log("FAIL", f"格式化-{style}", f"输出太短: {text}")
            except Exception as e:
                self.log("FAIL", f"格式化-{style}", str(e))

    # --- 功能测试（需要 LLM）---

    def test_recommend(self):
        """测试文献推荐"""
        print("\n📚 文献推荐测试")
        copilot = GeoFundCopilot(self.engine, deepseek_api_key=self.api_key)

        for case in RECOMMEND_CASES:
            t0 = time.time()
            try:
                result = copilot.recommend(
                    case["query"], top_k=10, verify=False, verbose=False,
                )
                elapsed = time.time() - t0
                total = result.get("total", 0)
                rejected = result.get("rejected", False)

                if case.get("may_reject") and rejected:
                    self.log("PASS", f"推荐-{case['name']}", "正确拒绝模糊输入", elapsed)
                    continue

                if total >= case["expect_min_total"]:
                    cats = [k for k, v in result.get("recommendations", {}).items()
                            if isinstance(v, list) and len(v) > 0]
                    self.log("PASS", f"推荐-{case['name']}",
                             f"{total} 篇, 类别: {cats}", elapsed)
                else:
                    self.log("WARN", f"推荐-{case['name']}",
                             f"只有 {total} 篇 (期望 ≥{case['expect_min_total']})", elapsed)
            except Exception as e:
                self.log("FAIL", f"推荐-{case['name']}", str(e))

    def test_novelty(self):
        """测试创新点查重"""
        print("\n🔬 创新点查重测试")
        checker = NoveltyChecker(self.engine, deepseek_api_key=self.api_key)

        for case in NOVELTY_CASES:
            t0 = time.time()
            try:
                report = checker.check(case["innovation"], verbose=False)
                elapsed = time.time() - t0
                score = report.get("novelty_score", -1)
                lo, hi = case["expect_score_range"]

                has_overlap = bool(report.get("overlap_analysis"))
                has_threats = len(report.get("most_threatening", [])) > 0
                has_suggestions = len(report.get("suggestions", [])) > 0

                issues = []
                if not (lo <= score <= hi):
                    issues.append(f"评分 {score} 不在预期 [{lo},{hi}]")
                if case["expect_has_threats"] and not has_threats:
                    issues.append("期望有威胁论文但没有")
                if not has_overlap:
                    issues.append("缺少重叠分析")

                if not issues:
                    self.log("PASS", f"查重-{case['name']}",
                             f"评分: {score}/10, 威胁: {has_threats}, 建议: {has_suggestions}", elapsed)
                else:
                    self.log("WARN", f"查重-{case['name']}",
                             f"评分: {score}/10, 问题: {'; '.join(issues)}", elapsed)
            except Exception as e:
                self.log("FAIL", f"查重-{case['name']}", str(e))

    def test_trends(self):
        """测试研究趋势分析"""
        print("\n📈 趋势分析测试")
        analyzer = TrendAnalyzer(self.engine, deepseek_api_key=self.api_key)

        for case in TREND_CASES:
            t0 = time.time()
            try:
                result = analyzer.analyze(
                    case["query"],
                    year_from=case["year_from"],
                    year_to=case["year_to"],
                    top_k=100,
                    verbose=False,
                )
                elapsed = time.time() - t0

                total = result.get("total_papers", 0)
                has_dist = bool(result.get("year_distribution"))
                has_milestones = len(result.get("milestones", [])) > 0
                has_summary = bool(result.get("trend_summary"))
                has_hot = len(result.get("hot_topics", [])) > 0

                issues = []
                if total < case["expect_min_papers"]:
                    issues.append(f"论文数 {total} < {case['expect_min_papers']}")
                if not has_dist:
                    issues.append("缺少年份分布")
                if case["expect_has_milestones"] and not has_milestones:
                    issues.append("缺少里程碑论文")
                if not has_summary:
                    issues.append("缺少趋势总结")

                if not issues:
                    self.log("PASS", f"趋势-{case['name']}",
                             f"{total} 篇, 里程碑: {len(result.get('milestones', []))}, "
                             f"热点: {len(result.get('hot_topics', []))}", elapsed)
                else:
                    self.log("WARN", f"趋势-{case['name']}",
                             f"问题: {'; '.join(issues)}", elapsed)
            except Exception as e:
                self.log("FAIL", f"趋势-{case['name']}", str(e))

    def test_reviewer(self):
        """测试评审视角模拟"""
        print("\n👨‍🏫 评审视角测试")
        reviewer = ReviewerSimulator(self.engine, deepseek_api_key=self.api_key)

        for case in REVIEWER_CASES:
            t0 = time.time()
            try:
                result = reviewer.review(
                    case["direction"],
                    innovation_points=case["innovation"],
                    verbose=False,
                )
                elapsed = time.time() - t0

                has_score = "overall_score" in result
                has_questions = len(result.get("critical_questions", [])) > 0
                has_suggestions = len(result.get("improvement_suggestions", [])) > 0
                has_strengths = len(result.get("strengths", [])) > 0

                issues = []
                if not has_score:
                    issues.append("缺少总评")
                if case["expect_has_questions"] and not has_questions:
                    issues.append("缺少尖锐问题")
                if case["expect_has_suggestions"] and not has_suggestions:
                    issues.append("缺少改进建议")

                if not issues:
                    self.log("PASS", f"评审-{case['name']}",
                             f"评分: {result.get('overall_score', '?')}, "
                             f"问题: {len(result.get('critical_questions', []))}, "
                             f"建议: {len(result.get('improvement_suggestions', []))}", elapsed)
                else:
                    self.log("WARN", f"评审-{case['name']}",
                             f"问题: {'; '.join(issues)}", elapsed)
            except Exception as e:
                self.log("FAIL", f"评审-{case['name']}", str(e))

    # --- 汇总 ---

    def summary(self):
        print(f"\n{'=' * 60}")
        total = len(self.results)
        passed = sum(1 for r in self.results if r["status"] == "PASS")
        warned = sum(1 for r in self.results if r["status"] == "WARN")
        failed = sum(1 for r in self.results if r["status"] == "FAIL")
        skipped = sum(1 for r in self.results if r["status"] == "SKIP")

        print(f"  测试结果: {total} 项 — ✅ {passed} 通过 | ⚠️ {warned} 警告 | ❌ {failed} 失败 | ⏭️ {skipped} 跳过")
        print(f"{'=' * 60}")

        if failed > 0:
            print("\n失败项:")
            for r in self.results:
                if r["status"] == "FAIL":
                    print(f"  ❌ {r['name']}: {r['msg']}")

        return failed == 0


# ============================================================
# 主入口
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="GeoFund Copilot 功能测试")
    parser.add_argument("--quick", action="store_true", help="只跑快速测试（不调 LLM）")
    parser.add_argument("--feature", choices=["recommend", "novelty", "trends", "reviewer"],
                        help="只测试某个功能")
    args = parser.parse_args()

    api_key = os.environ.get("DEEPSEEK_API_KEY", "")
    if not api_key and not args.quick:
        print("❌ 未设置 DEEPSEEK_API_KEY，只能跑 --quick 模式")
        args.quick = True

    print("🔬 GeoFund Copilot 功能测试")
    print(f"   模式: {'快速 (无LLM)' if args.quick else '完整'}")
    if args.feature:
        print(f"   功能: {args.feature}")

    runner = TestRunner(api_key)

    # 快速测试（始终执行）
    runner.test_sdk_connection()
    runner.test_search_basic()
    runner.test_formatter()

    if not args.quick:
        if args.feature:
            getattr(runner, f"test_{args.feature}")()
        else:
            runner.test_recommend()
            runner.test_novelty()
            runner.test_trends()
            runner.test_reviewer()

    success = runner.summary()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
