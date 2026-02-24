"""
GeoFund Copilot — 交互式演示

修复:
- 区分菜单命令 vs 研究方向输入
- 缺失字段的友好显示
- rejected 状态处理
- 调试信息（score 分布）
"""

import os
import sys
sys.path.insert(0, ".")

from geomind_sdk import GeoMindClient, SearchEngine, CitationFormatter
from geomind_sdk.copilot import GeoFundCopilot
from geomind_sdk.novelty import NoveltyChecker

# ============================================================
# 初始化
# ============================================================

print("=" * 64)
print("  GeoFund Copilot — 地球科学基金申请智能助手")
print("  📚 文献推荐  |  🔬 创新点查重")
print("=" * 64)

api_key = os.environ.get("DEEPSEEK_API_KEY", "")
if not api_key:
    api_key = input("\n🔑 DeepSeek API Key: ").strip()
    if not api_key:
        print("❌ 未提供 API Key")
        sys.exit(1)

client = GeoMindClient()
info = client.info()
print(f"\n📊 论文库: {info['points_count']:,} 篇 | 状态: {'✅ 正常' if info['status'] == 'green' else info['status']}")

engine = SearchEngine(client)
copilot = GeoFundCopilot(engine, deepseek_api_key=api_key)
checker = NoveltyChecker(engine, deepseek_api_key=api_key)
fmt = CitationFormatter()

# ============================================================
# 辅助显示
# ============================================================

def display_paper(i, p):
    """显示一篇论文，友好处理缺失字段"""
    # 来源和验证
    source_icon = "📦" if p.get("source") == "qdrant" else "🌐"
    verified_icon = "✅" if p.get("verified") else "⚠️"

    # 标题
    print(f"\n  {i}. {source_icon}{verified_icon} {p.get('title', 'Untitled')[:70]}")

    # 作者
    first = p.get("first_author", "")
    n = p.get("authors_count", 0)
    if first:
        if n > 2:
            print(f"     👤 {first} et al. ({n}人)")
        elif n == 2:
            authors = p.get("authors", [])
            print(f"     👤 {', '.join(authors[:2])}")
        else:
            print(f"     👤 {first}")
    else:
        print(f"     👤 未知作者")

    # 元数据行
    meta = []
    journal = p.get("journal", "")
    if journal:
        meta.append(journal)
    year = p.get("year", 0)
    if year:
        meta.append(str(year))
    cited = p.get("cited_by", 0)
    meta.append(f"Cited: {cited}")

    jcr = p.get("jcr_zone", "")
    if jcr:
        meta.append(jcr)
    cas = p.get("cas_zone", 0)
    if cas:
        cas_label = {1: "一区", 2: "二区", 3: "三区", 4: "四区"}.get(cas, "")
        if cas_label:
            meta.append(f"中科院{cas_label}")

    print(f"     📖 {' | '.join(meta)}")

    # 推荐理由
    if p.get("reason"):
        print(f"     💬 {p['reason']}")

    # DOI
    if p.get("doi"):
        print(f"     🔗 {p['doi']}")


def is_menu_command(text):
    """判断输入是菜单命令还是研究方向"""
    commands = [
        "智能文献推荐", "文献推荐", "推荐文献", "推荐",
        "创新点查重", "查重", "新颖度",
        "帮助", "help", "功能",
    ]
    return text.strip() in commands


# ============================================================
# 交互
# ============================================================

print(f"\n{'─'*64}")
print("使用方式:")
print("  输入研究方向  → 智能文献推荐")
print("    例: 用图神经网络预测珠江流域的溶解氧浓度")
print("    例: remote sensing total nitrogen concentration machine learning")
print("  /novel        → 创新点查重")
print("  /debug        → 检查一条 Qdrant 数据的完整字段")
print("  q             → 退出")
print(f"{'─'*64}")

while True:
    user_input = input("\n🔍 > ").strip()

    if user_input.lower() in ("q", "quit", "exit"):
        print("👋 退出")
        break

    if not user_input:
        continue

    # ── 菜单命令拦截 ──
    if is_menu_command(user_input):
        print("\n⚠️ 请直接输入你的研究方向，而不是功能名称。")
        print("   例: 用图神经网络预测珠江流域的溶解氧浓度")
        print("   例: remote sensing water quality deep learning")
        continue

    # ── 调试: 看一条完整数据 ──
    if user_input.lower() == "/debug":
        import json
        sample, _ = client.qdrant.scroll(
            collection_name=client.collection, limit=1,
            with_payload=True, with_vectors=False,
        )
        if sample:
            p = sample[0]
            print(f"\n📋 ID: {p.id}")
            print(f"   字段数: {len(p.payload)}")
            for key, val in p.payload.items():
                val_str = json.dumps(val, ensure_ascii=False) if isinstance(val, (list, dict)) else str(val)
                if len(val_str) > 120:
                    val_str = val_str[:120] + "..."
                print(f"   {key}: {val_str}")
        continue

    # ── 创新点查重 ──
    if user_input.lower() == "/novel":
        print("\n📝 请输入你的创新点描述:")
        innovation = input("   > ").strip()
        if not innovation:
            continue

        report = checker.check(innovation, verbose=True)

        score = report.get("novelty_score", 0)
        verdict = report.get("verdict", "")

        if score >= 8:
            score_bar = "🟢" * score + "⚪" * (10 - score)
        elif score >= 5:
            score_bar = "🟡" * score + "⚪" * (10 - score)
        else:
            score_bar = "🔴" * score + "⚪" * (10 - score)

        print(f"\n{'='*64}")
        print(f"  🔬 创新点新颖度评估报告")
        print(f"{'='*64}")
        print(f"\n  评分: {score}/10  {score_bar}")
        print(f"  结论: {verdict}")

        overlap = report.get("overlap_analysis", {})
        if overlap:
            print(f"\n  📊 重叠分析:")
            for dim, analysis in overlap.items():
                label = {"method": "方法", "application": "应用", "region": "区域", "data_source": "数据"}.get(dim, dim)
                if analysis:
                    print(f"    {label}: {analysis}")

        threats = report.get("most_threatening", [])
        if threats:
            print(f"\n  ⚠️ 最相似的 {len(threats)} 篇论文:")
            for t in threats:
                paper = t.get("paper", {})
                level = t.get("threat_level", "?")
                level_icon = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(level, "⚪")
                dims = ", ".join(t.get("overlap_dimensions", []))
                print(f"    {level_icon} [{level}] {paper.get('title', '?')[:60]}")
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
                print(f"       {t.get('analysis', '')}")

        unique = report.get("unique_aspects", [])
        if unique:
            print(f"\n  ✨ 独特之处:")
            for u in unique:
                print(f"    • {u}")

        suggestions = report.get("suggestions", [])
        if suggestions:
            print(f"\n  💡 改写建议:")
            for s in suggestions:
                print(f"    • {s}")

        continue

    # ── 智能文献推荐 ──
    result = copilot.recommend(user_input, top_k=15, verbose=True)

    # 被拒绝
    if result.get("rejected"):
        print(f"\n⚠️ 未找到与你研究方向匹配的论文。")
        print(f"   原因: {result.get('reject_reason', '候选论文与需求不匹配')}")
        print(f"   建议: 尝试更具体的描述，包含方法、应用场景、研究区域")
        continue

    if result["total"] == 0:
        print("\n⚠️ 未找到相关论文，请换个描述试试")
        continue

    # 验证摘要
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

        print(f"\n{'─'*64}")
        print(f"  {cat_title}  ({len(papers)} 篇)")
        print(f"  {cat_desc}")
        print(f"{'─'*64}")

        for i, p in enumerate(papers, 1):
            display_paper(i, p)

    # 参考文献（去重）
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
        print(f"\n{'='*64}")
        print(f"  📎 参考文献列表 (GB/T 7714) — 共 {len(all_papers)} 篇")
        print(f"{'='*64}")
        print(fmt.format_list(all_papers, style="gbt7714"))
