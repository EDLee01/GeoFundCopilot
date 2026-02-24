#!/usr/bin/env python3
"""
GeoFund Copilot — Streamlit Web UI

启动方式:
    streamlit run app.py
"""

import os
import sys
import json
import streamlit as st
import plotly.graph_objects as go

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ============================================================
# 页面配置
# ============================================================

st.set_page_config(
    page_title="GeoFund Copilot",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ============================================================
# 侧边栏
# ============================================================

with st.sidebar:
    st.title("🔬 GeoFund Copilot")
    st.caption("地球科学基金申请智能文献助手")
    st.divider()

    api_key = st.text_input(
        "DeepSeek API Key",
        value=os.environ.get("DEEPSEEK_API_KEY", ""),
        type="password",
        help="从 https://platform.deepseek.com 获取",
    )

    st.divider()
    st.markdown("**📊 数据规模**")
    st.markdown("- 📚 127 万篇地球科学论文")
    st.markdown("- 🌐 CrossRef 实时补充")
    st.markdown("- 🔍 BGE 语义向量检索")
    st.divider()
    st.caption("MIT License | [GitHub](https://github.com/EDLee01/GeoFundCopilot)")

# ============================================================
# SDK 初始化（带缓存）
# ============================================================


@st.cache_resource(show_spinner="正在连接论文数据库...")
def init_sdk():
    from geomind_sdk import GeoMindClient, SearchEngine
    client = GeoMindClient()
    engine = SearchEngine(client)
    return client, engine


def get_copilot(engine, api_key):
    from geomind_sdk.copilot import GeoFundCopilot
    return GeoFundCopilot(engine, deepseek_api_key=api_key)


def get_checker(engine, api_key):
    from geomind_sdk.novelty import NoveltyChecker
    return NoveltyChecker(engine, deepseek_api_key=api_key)


def get_trend_analyzer(engine, api_key):
    from geomind_sdk.trends import TrendAnalyzer
    return TrendAnalyzer(engine, deepseek_api_key=api_key)


def get_reviewer(engine, api_key):
    from geomind_sdk.reviewer import ReviewerSimulator
    return ReviewerSimulator(engine, deepseek_api_key=api_key)


def get_roadmap_generator(engine, api_key):
    from geomind_sdk.roadmap import RoadmapGenerator
    return RoadmapGenerator(engine, deepseek_api_key=api_key)


def get_rationale_generator(engine, api_key):
    from geomind_sdk.rationale import RationaleGenerator
    return RationaleGenerator(engine, deepseek_api_key=api_key)


# ============================================================
# 工具函数
# ============================================================

def make_radar_chart(overlap_analysis: dict) -> go.Figure:
    """四维度重叠雷达图"""
    dimensions = {
        "method": "🔧 方法",
        "application": "🎯 应用",
        "region": "🌍 区域",
        "data_source": "📊 数据",
    }
    labels = list(dimensions.values())
    # 根据分析文本估算重叠程度
    scores = []
    for dim in dimensions:
        text = overlap_analysis.get(dim, "")
        if not text:
            scores.append(1)
            continue
        # 简单关键词匹配估算重叠程度
        high_words = ["高度重叠", "完全一致", "大量", "严重", "显著重叠", "高度相似"]
        medium_words = ["部分重叠", "一定程度", "有所重叠", "类似", "相近", "部分相同"]
        low_words = ["较少", "不同", "差异", "独特", "新颖", "无重叠", "未见", "较低"]
        score = 3  # 默认中等
        for w in high_words:
            if w in text:
                score = 5
                break
        for w in low_words:
            if w in text:
                score = 1
                break
        for w in medium_words:
            if w in text:
                score = 3
                break
        scores.append(score)

    # 闭合雷达图
    labels_closed = labels + [labels[0]]
    scores_closed = scores + [scores[0]]

    fig = go.Figure()
    fig.add_trace(go.Scatterpolar(
        r=scores_closed,
        theta=labels_closed,
        fill="toself",
        fillcolor="rgba(255, 107, 107, 0.3)",
        line=dict(color="rgb(255, 107, 107)", width=2),
        name="重叠程度",
    ))
    fig.update_layout(
        polar=dict(
            radialaxis=dict(visible=True, range=[0, 5], tickvals=[1, 2, 3, 4, 5],
                            ticktext=["极低", "低", "中", "高", "极高"]),
        ),
        showlegend=False,
        height=350,
        margin=dict(l=60, r=60, t=30, b=30),
    )
    return fig


def make_trend_chart(year_distribution: dict) -> go.Figure:
    """年份趋势折线图"""
    years = sorted(year_distribution.keys())
    counts = [year_distribution[y] for y in years]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=years, y=counts,
        marker_color="rgba(55, 128, 191, 0.7)",
        name="相关论文数",
    ))
    fig.add_trace(go.Scatter(
        x=years, y=counts,
        mode="lines+markers",
        line=dict(color="rgb(219, 64, 82)", width=2),
        marker=dict(size=6),
        name="趋势线",
    ))
    fig.update_layout(
        xaxis_title="年份",
        yaxis_title="相关论文数量",
        height=400,
        margin=dict(l=50, r=20, t=30, b=50),
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
    )
    return fig


def generate_bib_content(papers: list) -> str:
    """批量生成 BibTeX 内容"""
    from geomind_sdk.formatter import CitationFormatter
    return CitationFormatter().format_list(papers, style="bibtex")


def render_paper_card(paper: dict, index: int, category: str = ""):
    """渲染论文卡片"""
    source_icon = "📦" if paper.get("source") == "qdrant" else "🌐"
    verified_icon = "✅" if paper.get("verified") else "⚠️"

    title = paper.get("title", "Untitled")
    first_author = paper.get("first_author", "")
    n = paper.get("authors_count", 0)
    author_str = f"{first_author} et al. ({n}人)" if n > 2 else first_author

    meta_parts = []
    if paper.get("journal"):
        meta_parts.append(f"**{paper['journal']}**")
    if paper.get("year"):
        meta_parts.append(str(paper["year"]))
    meta_parts.append(f"Cited: {paper.get('cited_by', 0)}")
    if paper.get("jcr_zone"):
        meta_parts.append(f"`{paper['jcr_zone']}`")
    if paper.get("cas_zone"):
        cas_label = {1: "一区", 2: "二区", 3: "三区", 4: "四区"}.get(paper["cas_zone"], "")
        if cas_label:
            meta_parts.append(f"`中科院{cas_label}`")

    st.markdown(f"**{index}. {source_icon}{verified_icon} {title}**")
    st.markdown(f"👤 {author_str} &nbsp;|&nbsp; {' | '.join(meta_parts)}")
    if paper.get("reason"):
        st.markdown(f"💬 _{paper['reason']}_")
    if paper.get("doi"):
        st.markdown(f"🔗 [{paper['doi']}]({paper['doi']})")


def render_compliance_panel(module_name: str):
    """渲染 AI 使用合规声明面板"""
    from geomind_sdk.compliance import generate_disclosure
    disclosure = generate_disclosure(module_name)
    with st.expander("📋 AI 使用声明与人工核实清单（点击展开）", expanded=False):
        st.markdown(f"**工具:** {disclosure['tool_name']}")
        st.markdown("**AI 参与范围:**")
        for item in disclosure["ai_scope"]:
            st.markdown(f"- {item}")
        st.markdown("**人工核实清单（必须完成）:**")
        for item in disclosure["human_required"]:
            st.checkbox(item, value=False, key=f"chk_{module_name}_{item[:15]}")
        st.divider()
        st.markdown("**建议插入申请书的声明文本:**")
        st.code(disclosure["disclosure_text"], language=None)
        st.download_button(
            "📥 下载 AI 使用声明",
            disclosure["checklist_markdown"],
            file_name=f"ai_disclosure_{module_name}.md",
            mime="text/markdown",
            key=f"dl_compliance_{module_name}",
        )


# ============================================================
# 标签页
# ============================================================

tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "📚 文献推荐",
    "🔬 创新点查重",
    "📈 研究趋势",
    "👨‍🏫 评审视角",
    "🗺️ 技术路线图",
    "📝 立项依据",
])

# ── Tab 1: 文献推荐 ──────────────────────────────────────────

with tab1:
    st.header("📚 智能文献推荐")
    st.markdown("输入研究方向，获得按「必引经典 / 前沿进展 / 方法借鉴 / 潜在评审人」四类推荐的参考文献。")

    col1, col2 = st.columns([3, 1])
    with col1:
        rec_query = st.text_area(
            "研究方向",
            placeholder="例: 用图神经网络预测珠江流域溶解氧浓度",
            height=80,
            key="rec_query",
        )
    with col2:
        rec_top_k = st.slider("推荐数量", 5, 25, 15, key="rec_top_k")
        rec_verify = st.checkbox("DOI 验证", value=True, key="rec_verify")

    if st.button("🚀 开始推荐", key="btn_rec", type="primary", use_container_width=True):
        if not api_key:
            st.error("请在侧边栏输入 DeepSeek API Key")
        elif not rec_query.strip():
            st.warning("请输入研究方向")
        else:
            try:
                client, engine = init_sdk()
                copilot = get_copilot(engine, api_key)

                rec_progress = st.progress(0, text="准备中...")
                rec_status = st.container()

                def rec_on_progress(step, total, msg):
                    rec_progress.progress(step / total, text=msg)
                    rec_status.caption(f"Step {step}/{total}: {msg}")

                result = copilot.recommend(
                    rec_query.strip(),
                    top_k=rec_top_k,
                    verify=rec_verify,
                    verbose=False,
                    on_progress=rec_on_progress,
                )

                rec_progress.progress(1.0, text="✅ 推荐完成！")
                st.session_state["rec_result"] = result
            except Exception as e:
                st.error(f"推荐失败: {e}")

    # 渲染结果
    if "rec_result" in st.session_state:
        result = st.session_state["rec_result"]

        if result.get("rejected"):
            st.warning(f"⚠️ 未找到匹配论文: {result.get('reject_reason', '候选论文与需求不匹配')}")
        elif result.get("total", 0) == 0:
            st.warning("未找到相关论文，请尝试更具体的描述")
        else:
            # 验证统计
            vs = result.get("verification_summary", {})
            if vs:
                col_v1, col_v2, col_v3 = st.columns(3)
                col_v1.metric("推荐论文", f"{result['total']} 篇")
                col_v2.metric("通过验证", f"{vs.get('verified', 0)} 篇")
                col_v3.metric("验证未通过", f"{vs.get('failed', 0)} 篇")

            # 分类展示
            categories = [
                ("foundational", "📖 必引经典", "领域奠基性工作，不引会被评审质疑"),
                ("cutting_edge", "🔬 前沿进展", "近年最新研究，展现对前沿的把握"),
                ("methodological", "⚙️ 方法借鉴", "与你拟用方法直接相关"),
                ("reviewer_relevant", "👤 潜在评审人", "该方向活跃学者，引用可提升好感"),
            ]

            recs = result.get("recommendations", {})
            all_papers = []

            for cat_key, cat_title, cat_desc in categories:
                papers = recs.get(cat_key, [])
                if not papers:
                    continue
                with st.expander(f"{cat_title} ({len(papers)} 篇) — {cat_desc}", expanded=True):
                    for i, p in enumerate(papers, 1):
                        render_paper_card(p, i, cat_key)
                        st.divider()
                    all_papers.extend(papers)

            # 导出功能
            if all_papers:
                st.divider()
                st.subheader("📎 导出参考文献")
                export_col1, export_col2, export_col3 = st.columns(3)

                with export_col1:
                    from geomind_sdk.formatter import CitationFormatter
                    fmt = CitationFormatter()
                    gbt_text = fmt.format_list(all_papers, style="gbt7714")
                    st.download_button(
                        "📥 GB/T 7714 (.txt)",
                        gbt_text,
                        file_name="references_gbt7714.txt",
                        mime="text/plain",
                    )

                with export_col2:
                    bib_text = generate_bib_content(all_papers)
                    st.download_button(
                        "📥 BibTeX (.bib)",
                        bib_text,
                        file_name="references.bib",
                        mime="text/plain",
                    )

                with export_col3:
                    apa_text = fmt.format_list(all_papers, style="apa")
                    st.download_button(
                        "📥 APA (.txt)",
                        apa_text,
                        file_name="references_apa.txt",
                        mime="text/plain",
                    )

            render_compliance_panel("recommend")

# ── Tab 2: 创新点查重 ─────────────────────────────────────────

with tab2:
    st.header("🔬 创新点新颖度评估")
    st.markdown("输入创新点描述，获得四维度重叠分析 + 新颖度评分 + 雷达图诊断报告。")

    novelty_input = st.text_area(
        "创新点描述",
        placeholder="例: 结合图注意力时空卷积网络(GATCN)和GNNExplainer实现珠江流域溶解氧的可解释预测",
        height=80,
        key="novelty_input",
    )

    if st.button("🔍 开始查重", key="btn_novelty", type="primary", use_container_width=True):
        if not api_key:
            st.error("请在侧边栏输入 DeepSeek API Key")
        elif not novelty_input.strip():
            st.warning("请输入创新点描述")
        else:
            try:
                client, engine = init_sdk()
                checker = get_checker(engine, api_key)

                nov_progress = st.progress(0, text="准备中...")
                nov_status = st.container()

                def nov_on_progress(step, total, msg):
                    nov_progress.progress(step / total, text=msg)
                    nov_status.caption(f"Step {step}/{total}: {msg}")

                report = checker.check(
                    novelty_input.strip(), verbose=False,
                    on_progress=nov_on_progress,
                )

                nov_progress.progress(1.0, text="✅ 查重完成！")
                st.session_state["novelty_result"] = report
            except Exception as e:
                st.error(f"查重失败: {e}")

    # 渲染结果
    if "novelty_result" in st.session_state:
        report = st.session_state["novelty_result"]
        score = report.get("novelty_score", 0)
        verdict = report.get("verdict", "")

        # 评分展示
        if score >= 8:
            score_color = "green"
            score_emoji = "🟢"
        elif score >= 5:
            score_color = "orange"
            score_emoji = "🟡"
        else:
            score_color = "red"
            score_emoji = "🔴"

        st.divider()

        col_score, col_radar = st.columns([1, 1])

        with col_score:
            st.markdown(f"### {score_emoji} 新颖度评分: {score}/10")
            st.markdown(f"**结论:** {verdict}")

            # 评分进度条
            st.progress(score / 10)

            # 独特之处
            unique = report.get("unique_aspects", [])
            if unique:
                st.markdown("#### ✨ 独特之处")
                for u in unique:
                    st.markdown(f"- {u}")

            # 改写建议
            suggestions = report.get("suggestions", [])
            if suggestions:
                st.markdown("#### 💡 改写建议")
                for s in suggestions:
                    st.markdown(f"- {s}")

        with col_radar:
            st.markdown("#### 📊 四维度重叠分析")
            overlap = report.get("overlap_analysis", {})
            if overlap:
                fig = make_radar_chart(overlap)
                st.plotly_chart(fig, use_container_width=True)

                # 文字说明
                dim_labels = {
                    "method": "🔧 方法", "application": "🎯 应用",
                    "region": "🌍 区域", "data_source": "📊 数据",
                }
                for dim, label in dim_labels.items():
                    text = overlap.get(dim, "")
                    if text:
                        st.markdown(f"**{label}:** {text}")

        # 最威胁论文
        threats = report.get("most_threatening", [])
        if threats:
            st.divider()
            st.markdown("#### ⚠️ 最相似论文")
            for t in threats:
                paper = t.get("paper", {})
                level = t.get("threat_level", "?")
                level_icon = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(level, "⚪")
                dims = ", ".join(t.get("overlap_dimensions", []))

                with st.container():
                    st.markdown(
                        f"**{level_icon} [{level.upper()}] {paper.get('title', '?')}**\n\n"
                        f"{paper.get('first_author', '?')} | {paper.get('journal', '?')} | "
                        f"{paper.get('year', '?')} | Cited: {paper.get('cited_by', 0)}\n\n"
                        f"重叠维度: `{dims}`\n\n"
                        f"_{t.get('analysis', '')}_"
                    )
                    st.divider()

        render_compliance_panel("novelty")

# ── Tab 3: 研究趋势 ──────────────────────────────────────────

with tab3:
    st.header("📈 研究趋势分析")
    st.markdown("输入研究关键词，查看该方向近年发文趋势、里程碑论文和热点方向。")

    trend_col1, trend_col2, trend_col3 = st.columns([3, 1, 1])
    with trend_col1:
        trend_query = st.text_input(
            "研究关键词",
            placeholder="例: deep learning water quality prediction",
            key="trend_query",
        )
    with trend_col2:
        trend_year_from = st.number_input("起始年份", 2000, 2025, 2010, key="trend_from")
    with trend_col3:
        trend_year_to = st.number_input("结束年份", 2010, 2026, 2025, key="trend_to")

    if st.button("📊 分析趋势", key="btn_trend", type="primary", use_container_width=True):
        if not api_key:
            st.error("请在侧边栏输入 DeepSeek API Key")
        elif not trend_query.strip():
            st.warning("请输入研究关键词")
        else:
            try:
                client, engine = init_sdk()
                analyzer = get_trend_analyzer(engine, api_key)

                trend_progress = st.progress(0, text="准备中...")
                trend_status = st.container()

                def trend_on_progress(step, total, msg):
                    trend_progress.progress(step / total, text=msg)
                    trend_status.caption(f"Step {step}/{total}: {msg}")

                trend_result = analyzer.analyze(
                    trend_query.strip(),
                    year_from=trend_year_from,
                    year_to=trend_year_to,
                    verbose=False,
                    on_progress=trend_on_progress,
                )

                trend_progress.progress(1.0, text="✅ 趋势分析完成！")
                st.session_state["trend_result"] = trend_result
            except Exception as e:
                st.error(f"趋势分析失败: {e}")

    # 渲染结果
    if "trend_result" in st.session_state:
        trend = st.session_state["trend_result"]
        st.divider()

        # 总览
        t_col1, t_col2 = st.columns(2)
        t_col1.metric("检索到相关论文", f"{trend.get('total_papers', 0)} 篇")
        t_col2.metric("里程碑论文", f"{len(trend.get('milestones', []))} 篇")

        # 趋势图
        st.markdown("#### 📈 发文趋势")
        year_dist = trend.get("year_distribution", {})
        if year_dist:
            # 转换 key 为 int
            year_dist_int = {int(k): v for k, v in year_dist.items()}
            fig = make_trend_chart(year_dist_int)
            st.plotly_chart(fig, use_container_width=True)

        # 趋势总结
        summary = trend.get("trend_summary", "")
        if summary:
            st.markdown("#### 📝 趋势总结")
            st.info(summary)

        # 热点方向 + 未来展望
        hot_col, future_col = st.columns(2)
        with hot_col:
            hot_topics = trend.get("hot_topics", [])
            if hot_topics:
                st.markdown("#### 🔥 当前热点")
                for t in hot_topics:
                    st.markdown(f"- {t}")

        with future_col:
            future = trend.get("future_directions", [])
            if future:
                st.markdown("#### 🔮 未来方向")
                for f in future:
                    st.markdown(f"- {f}")

        # 里程碑论文
        milestones = trend.get("milestones", [])
        if milestones:
            st.markdown("#### 🏆 里程碑论文")
            for m in milestones:
                st.markdown(
                    f"- **{m['year']}** | {m['title'][:80]} | "
                    f"{m.get('journal', '')} | Cited: {m.get('cited_by', 0)}"
                )

        # Top 期刊
        journals = trend.get("top_journals", [])
        if journals:
            st.markdown("#### 📖 主要发表期刊")
            for j in journals[:8]:
                st.markdown(f"- **{j['journal']}** — {j['count']} 篇")

        render_compliance_panel("trends")

# ── Tab 4: 评审视角 ──────────────────────────────────────────

with tab4:
    st.header("👨‍🏫 评审视角模拟")
    st.markdown("模拟国自然评审专家视角，帮你提前发现申请书的薄弱环节。")

    review_direction = st.text_area(
        "研究方向",
        placeholder="例: 基于图神经网络的流域水质时空预测方法研究",
        height=80,
        key="review_direction",
    )
    review_innovation = st.text_area(
        "创新点 (可选)",
        placeholder="例: 1) 提出GATCN模型... 2) 利用GNNExplainer实现可解释预测...",
        height=80,
        key="review_innovation",
    )

    if st.button("👨‍🏫 模拟评审", key="btn_review", type="primary", use_container_width=True):
        if not api_key:
            st.error("请在侧边栏输入 DeepSeek API Key")
        elif not review_direction.strip():
            st.warning("请输入研究方向")
        else:
            try:
                client, engine = init_sdk()
                reviewer = get_reviewer(engine, api_key)

                rev_progress = st.progress(0, text="准备中...")
                rev_status = st.container()

                def rev_on_progress(step, total, msg):
                    rev_progress.progress(step / total, text=msg)
                    rev_status.caption(f"Step {step}/{total}: {msg}")

                review_result = reviewer.review(
                    review_direction.strip(),
                    innovation_points=review_innovation.strip(),
                    verbose=False,
                    on_progress=rev_on_progress,
                )

                rev_progress.progress(1.0, text="✅ 评审模拟完成！")
                st.session_state["review_result"] = review_result
            except Exception as e:
                st.error(f"评审模拟失败: {e}")

    # 渲染结果
    if "review_result" in st.session_state:
        review = st.session_state["review_result"]
        st.divider()

        # 总评
        overall_score = review.get("overall_score", "B")
        score_colors = {"A": "green", "B": "orange", "C": "red"}
        score_labels = {"A": "优秀", "B": "良好", "C": "一般"}

        st.markdown(f"### 总体评价: **{overall_score}** ({score_labels.get(overall_score, '')})")
        overall_comment = review.get("overall_comment", "")
        if overall_comment:
            st.info(overall_comment)

        # 优势 vs 不足
        str_col, weak_col = st.columns(2)
        with str_col:
            st.markdown("#### ✅ 优势")
            for s in review.get("strengths", []):
                st.markdown(f"- {s}")

        with weak_col:
            st.markdown("#### ⚠️ 潜在不足")
            for w in review.get("weaknesses", []):
                st.markdown(f"- {w}")

        # 尖锐问题
        questions = review.get("critical_questions", [])
        if questions:
            st.markdown("#### ❓ 评审可能提出的尖锐问题")
            for i, q in enumerate(questions, 1):
                st.error(f"**问题 {i}:** {q}")

        # 可行性顾虑
        feasibility = review.get("feasibility_concerns", [])
        if feasibility:
            st.markdown("#### 🔧 可行性顾虑")
            for f in feasibility:
                st.warning(f)

        # 改进建议
        improvements = review.get("improvement_suggestions", [])
        if improvements:
            st.markdown("#### 💡 改进建议")
            for i, s in enumerate(improvements, 1):
                st.success(f"**建议 {i}:** {s}")

        # 文献补充建议
        missing = review.get("missing_literature", [])
        rec_refs = review.get("recommended_references", [])
        if missing or rec_refs:
            st.markdown("#### 📚 文献补充建议")
            for m in missing:
                st.markdown(f"- 📖 {m}")
            for r in rec_refs:
                st.markdown(f"- 🔗 {r}")

        render_compliance_panel("reviewer")

# ── Tab 5: 技术路线图 ─────────────────────────────────────────

with tab5:
    st.header("🗺️ 技术路线图生成")
    st.markdown("输入研究方向和创新点，自动生成可用于申请书的 SVG 技术路线图。")

    roadmap_direction = st.text_area(
        "研究方向",
        placeholder="例: 基于图神经网络的流域水质时空预测方法研究",
        height=80,
        key="roadmap_direction",
    )
    roadmap_innovation = st.text_area(
        "创新点 (可选，会在路线图中标注)",
        placeholder="例: 1) 提出GATCN模型 2) GNNExplainer可解释分析 3) 珠江流域多站点验证",
        height=80,
        key="roadmap_innovation",
    )

    rm_col1, rm_col2 = st.columns([1, 3])
    with rm_col1:
        num_phases = st.slider("阶段数", 3, 6, 5, key="roadmap_phases")

    if st.button("🗺️ 生成路线图", key="btn_roadmap", type="primary", use_container_width=True):
        if not api_key:
            st.error("请在侧边栏输入 DeepSeek API Key")
        elif not roadmap_direction.strip():
            st.warning("请输入研究方向")
        else:
            try:
                client, engine = init_sdk()
                generator = get_roadmap_generator(engine, api_key)

                rm_progress = st.progress(0, text="准备中...")
                rm_status = st.container()

                def rm_on_progress(step, total, msg):
                    rm_progress.progress(step / total, text=msg)
                    rm_status.caption(f"Step {step}/{total}: {msg}")

                roadmap_result = generator.generate(
                    roadmap_direction.strip(),
                    innovation_points=roadmap_innovation.strip(),
                    num_phases=num_phases,
                    verbose=False,
                    on_progress=rm_on_progress,
                )

                rm_progress.progress(1.0, text="✅ 路线图生成完成！")
                st.session_state["roadmap_result"] = roadmap_result
            except Exception as e:
                st.error(f"路线图生成失败: {e}")

    # 渲染结果
    if "roadmap_result" in st.session_state:
        roadmap = st.session_state["roadmap_result"]
        st.divider()

        svg_content = roadmap.get("svg", "")
        if svg_content:
            # 渲染 SVG
            import base64
            b64 = base64.b64encode(svg_content.encode("utf-8")).decode("utf-8")
            st.markdown(
                f'<img src="data:image/svg+xml;base64,{b64}" style="width:100%;"/>',
                unsafe_allow_html=True,
            )

            # 下载按钮
            dl_col1, dl_col2 = st.columns(2)
            with dl_col1:
                st.download_button(
                    "📥 下载 SVG",
                    svg_content,
                    file_name="technical_roadmap.svg",
                    mime="image/svg+xml",
                )
            with dl_col2:
                roadmap_json = {k: v for k, v in roadmap.items() if k != "svg"}
                st.download_button(
                    "📥 下载 JSON 数据",
                    json.dumps(roadmap_json, ensure_ascii=False, indent=2),
                    file_name="roadmap_data.json",
                    mime="application/json",
                )

        # 文字版路线图
        phases = roadmap.get("phases", [])
        if phases:
            st.divider()
            st.markdown("#### 📋 路线图详情")
            for p in phases:
                with st.expander(f"Phase {p.get('id', '?')}: {p.get('name', '?')} — {p.get('duration', '')}"):
                    st.markdown("**任务:**")
                    for t in p.get("tasks", []):
                        st.markdown(f"- {t}")
                    methods = p.get("methods", [])
                    if methods:
                        st.markdown(f"**方法/工具:** {', '.join(methods)}")
                    output = p.get("output", "")
                    if output:
                        st.markdown(f"**产出:** {output}")

        # 预期成果
        expected = roadmap.get("expected_results", [])
        if expected:
            st.markdown("#### 🎯 预期成果")
            for e in expected:
                st.markdown(f"- {e}")

        render_compliance_panel("roadmap")

# ============================================================
# Tab 6 — 立项依据辅助
# ============================================================

with tab6:
    st.header("📝 立项依据辅助生成")
    st.markdown(
        "输入研究方向 → 多角度文献检索 → 文献脉络梳理 → 知识缺口分析 → 立项依据写作框架\n\n"
        "⚠️ **合规提示:** 输出内容为调研框架与文献线索，申请人**必须精读文献后独立撰写**立项依据。"
    )

    rat_direction = st.text_area(
        "研究方向 *",
        placeholder="例: 基于图神经网络的珠江流域溶解氧时空预测研究",
        height=80,
        key="rationale_direction",
    )
    rat_innovation = st.text_area(
        "创新点（可选，有助于精准分析知识缺口）",
        placeholder="例: 提出融合水文拓扑的时空图注意力网络...",
        height=80,
        key="rationale_innovation",
    )

    rat_run = st.button("🚀 生成立项依据框架", type="primary", key="btn_rationale")

    if rat_run:
        if not api_key:
            st.warning("请在左侧输入 DeepSeek API Key")
        elif not rat_direction.strip():
            st.warning("请输入研究方向")
        else:
            try:
                client, engine = init_sdk()
                rat_gen = get_rationale_generator(engine, api_key)

                rat_progress = st.progress(0, text="准备中...")
                rat_status = st.container()

                def rat_on_progress(step, total, msg):
                    rat_progress.progress(step / total, text=msg)
                    rat_status.caption(f"Step {step}/{total}: {msg}")

                rat_result = rat_gen.generate(
                    rat_direction.strip(),
                    innovation_points=rat_innovation.strip(),
                    verbose=False,
                    on_progress=rat_on_progress,
                )

                rat_progress.progress(1.0, text="✅ 立项依据框架生成完成！")
                st.session_state["rationale_result"] = rat_result
            except Exception as e:
                st.error(f"立项依据生成失败: {e}")

    # 渲染结果
    if "rationale_result" in st.session_state:
        result = st.session_state["rationale_result"]
        st.divider()

        # ── 文献脉络梳理 ──
        lit_review = result.get("literature_review", {})
        if lit_review:
            st.markdown("### 📚 文献脉络梳理")

            overview = lit_review.get("field_overview", "")
            if overview:
                st.info(overview)

            themes = lit_review.get("themes", [])
            if themes:
                st.markdown("#### 研究主题聚类")
                for t in themes:
                    status_icon = {"成熟": "🟢", "活跃": "🟡", "新兴": "🔵"}.get(
                        t.get("status", ""), "⚪"
                    )
                    with st.expander(
                        f"{status_icon} {t.get('theme_name', '?')} — {t.get('status', '?')}"
                    ):
                        st.markdown(f"**概述:** {t.get('description', '')}")
                        st.markdown(f"**发展脉络:** {t.get('development', '')}")

            timeline = lit_review.get("timeline", [])
            if timeline:
                st.markdown("#### 发展时间线")
                for tl in timeline:
                    st.markdown(f"- **{tl.get('period', '?')}**: {tl.get('milestone', '')}")

            methods = lit_review.get("dominant_methods", [])
            if methods:
                st.markdown(f"**主流方法:** {' · '.join(methods)}")

        st.divider()

        # ── 知识缺口分析 ──
        gap = result.get("gap_analysis", {})
        if gap:
            st.markdown("### 🔬 知识缺口分析")

            gaps = gap.get("knowledge_gaps", [])
            if gaps:
                st.markdown("#### 识别的知识缺口")
                for i, g in enumerate(gaps, 1):
                    importance = g.get("importance", "")
                    badge = "🔴" if importance == "high" else "🟡"
                    st.markdown(f"**{badge} 缺口 {i}: {g.get('gap', '')}**")
                    st.markdown(f"  - 证据: {g.get('evidence', '')}")
                    st.markdown(f"  - 相关主题: {g.get('related_theme', '')}")

            entry_points = gap.get("entry_points", [])
            if entry_points:
                st.markdown("#### 研究切入点建议")
                for ep in entry_points:
                    with st.expander(f"💡 {ep.get('point', '')}"):
                        st.markdown(f"**切入理由:** {ep.get('rationale', '')}")
                        st.markdown(f"**可行性:** {ep.get('feasibility', '')}")

            unsolved = gap.get("unsolved_problems", [])
            if unsolved:
                st.markdown("#### 尚未解决的关键科学问题")
                for u in unsolved:
                    st.markdown(f"- {u}")

            method_gaps = gap.get("methodology_gaps", [])
            if method_gaps:
                st.markdown("#### 方法论层面的不足")
                for mg in method_gaps:
                    st.markdown(f"- {mg}")

        st.divider()

        # ── 立项依据写作框架 ──
        framework = result.get("rationale_framework", {})
        if framework:
            st.markdown("### 📝 立项依据写作框架")

            title_sug = framework.get("title_suggestion", "")
            if title_sug:
                st.markdown(f"**建议标题:** {title_sug}")

            logical_flow = framework.get("logical_flow", "")
            if logical_flow:
                st.info(f"**逻辑线索:** {logical_flow}")

            sections = framework.get("sections", [])
            if sections:
                st.markdown("#### 章节结构")
                for i, sec in enumerate(sections, 1):
                    with st.expander(f"第 {i} 节: {sec.get('heading', '?')}"):
                        st.markdown(f"**目的:** {sec.get('purpose', '')}")
                        st.markdown("**要点:**")
                        for kp in sec.get("key_points", []):
                            st.markdown(f"- {kp}")
                        st.markdown(f"**建议引用:** {sec.get('suggested_refs', '')}")
                        st.markdown(f"**写作建议:** {sec.get('writing_tips', '')}")

            wc = framework.get("word_count_suggestion", {})
            if wc:
                st.markdown(f"**建议总字数:** {wc.get('total', '—')}")

        st.divider()

        # ── 核心文献（待精读）──
        core_papers = result.get("core_papers", [])
        if core_papers:
            st.markdown(f"### 📖 核心文献（共 {len(core_papers)} 篇，需精读）")
            st.caption("以下文献在多个研究主题中被标记为关键论文或高引论文，申请人须逐篇精读。")
            for i, cp in enumerate(core_papers, 1):
                doi = cp.get("doi", "")
                doi_link = f" | [DOI](https://doi.org/{doi})" if doi else ""
                st.markdown(
                    f"**{i}.** {cp.get('title', '?')}  \n"
                    f"   {cp.get('first_author', '')} | {cp.get('journal', '')} | "
                    f"{cp.get('year', '')} | Cited: {cp.get('cited_by', 0)}{doi_link}"
                )

        # 下载
        st.divider()
        dl1, dl2 = st.columns(2)
        with dl1:
            result_json = {k: v for k, v in result.items() if k != "compliance"}
            st.download_button(
                "📥 下载完整分析 (JSON)",
                json.dumps(result_json, ensure_ascii=False, indent=2),
                file_name="rationale_analysis.json",
                mime="application/json",
                key="dl_rationale_json",
            )
        with dl2:
            # 生成 Markdown 摘要
            md_lines = [f"# 立项依据框架 — {result.get('research_direction', '')}\n"]
            if lit_review.get("field_overview"):
                md_lines.append(f"## 领域概述\n{lit_review['field_overview']}\n")
            if gap.get("knowledge_gaps"):
                md_lines.append("## 知识缺口\n")
                for g in gap["knowledge_gaps"]:
                    md_lines.append(f"- **{g.get('gap', '')}** ({g.get('importance', '')})\n")
            if framework.get("sections"):
                md_lines.append("## 写作框架\n")
                for sec in framework["sections"]:
                    md_lines.append(f"### {sec.get('heading', '')}\n")
                    for kp in sec.get("key_points", []):
                        md_lines.append(f"- {kp}\n")
            md_content = "\n".join(md_lines)
            st.download_button(
                "📥 下载框架摘要 (Markdown)",
                md_content,
                file_name="rationale_framework.md",
                mime="text/markdown",
                key="dl_rationale_md",
            )

        st.markdown(f"📊 共检索 **{result.get('total_papers_searched', 0)}** 篇论文")

        render_compliance_panel("rationale")
