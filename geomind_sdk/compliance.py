"""
AI 使用合规声明生成

根据 2026 年国自然基金申请 AI 使用规范，为每个功能模块
生成规范化的 AI 使用声明和人工核实清单。
"""

from __future__ import annotations

# 各模块的 AI 使用声明模板
DISCLOSURE_TEMPLATES = {
    "recommend": {
        "tool_name": "GeoFund Copilot 文献推荐模块",
        "ai_role": "基于 127 万篇地球科学论文向量数据库（OpenAlex/Qdrant）进行语义检索，"
                   "并通过大语言模型（DeepSeek）对候选论文进行相关性评分和分类推荐",
        "ai_scope": [
            "生成多角度英文检索策略",
            "对候选论文进行主题相关性评分（1-10 分）",
            "将论文分为「必引经典/前沿进展/方法借鉴/潜在评审人」四类",
        ],
        "human_required": [
            "精读每篇推荐论文的全文，核实其与本研究的实际相关性",
            "验证论文元数据（作者、年份、期刊）的准确性",
            "根据研究需要调整分类，删除不相关论文并补充遗漏文献",
            "撰写参考文献的引用叙述，确保准确反映原文观点",
        ],
        "disclosure_text": (
            "本申请使用 GeoFund Copilot 文献检索工具辅助文献调研。"
            "该工具基于 OpenAlex 地球科学文献数据库（127 万篇）进行语义向量检索，"
            "并通过 CrossRef API 补充最新文献及验证 DOI 真实性。"
            "AI 仅用于文献初筛和分类框架建议，所有推荐文献均经申请人逐篇精读全文后，"
            "根据研究实际需要进行筛选、重新分类和引用叙述撰写。"
            "最终参考文献列表及引用内容由申请人独立确定。"
        ),
    },
    "novelty": {
        "tool_name": "GeoFund Copilot 创新点查重模块",
        "ai_role": "检索与创新点相关的已有文献，从方法、应用、区域、数据四个维度分析重叠程度",
        "ai_scope": [
            "提取创新点关键词并检索相似论文",
            "从四个维度评估与已有工作的重叠程度",
            "识别最相似的已有工作并分析威胁等级",
        ],
        "human_required": [
            "精读 AI 识别的「最相似论文」全文，确认重叠判断的准确性",
            "基于文献精读结果，独立判断创新点的真实新颖度",
            "根据查重结果调整创新点表述，确保科学价值由申请人确定",
            "团队讨论论证创新点的成立性和可行性",
        ],
        "disclosure_text": (
            "本申请使用 GeoFund Copilot 创新点查重工具辅助新颖度评估。"
            "AI 从方法、应用、区域、数据四个维度检索相似文献并初步评估重叠程度。"
            "申请人逐篇精读 AI 标记的高相似度论文，独立判断创新点的新颖度，"
            "并经研究团队讨论论证后确定最终创新点表述。"
            "AI 仅提供文献对比参考，创新点的科学价值判断由申请人主导完成。"
        ),
    },
    "trends": {
        "tool_name": "GeoFund Copilot 研究趋势分析模块",
        "ai_role": "基于文献检索结果的年份聚合和大语言模型总结，分析研究方向的发展趋势",
        "ai_scope": [
            "检索相关论文并按年份统计分布",
            "识别各年度高引用里程碑论文",
            "生成趋势总结和热点方向建议",
        ],
        "human_required": [
            "核实里程碑论文的实际影响力和代表性",
            "结合自身学术积累判断趋势分析的准确性",
            "独立撰写「国内外研究现状」，不直接沿用 AI 生成内容",
            "补充 AI 可能遗漏的重要学术事件和转折点",
        ],
        "disclosure_text": (
            "本申请使用 GeoFund Copilot 趋势分析工具辅助了解领域发展脉络。"
            "AI 基于文献数据库统计发文趋势并生成分析框架。"
            "申请人在此框架基础上精读核心文献、核实关键节点后独立重写研究现状综述。"
            "最终「国内外研究现状」内容由申请人根据文献精读结果撰写，"
            "AI 生成的趋势框架仅作为调研参考，未直接使用。"
        ),
    },
    "reviewer": {
        "tool_name": "GeoFund Copilot 评审视角模拟模块",
        "ai_role": "基于领域文献检索结果，模拟评审专家视角提出问题和建议",
        "ai_scope": [
            "模拟评审专家可能提出的问题",
            "分析研究方案的潜在不足",
            "生成改进建议",
        ],
        "human_required": [
            "逐条审视 AI 提出的问题，判断其与本研究的实际相关性",
            "针对有价值的问题制定具体的应对策略",
            "独立完善研究方案，确保方案可行性由申请人判断",
            "请团队成员或同行专家进一步审阅",
        ],
        "disclosure_text": (
            "本申请使用 GeoFund Copilot 评审模拟工具辅助完善申请书。"
            "AI 基于领域文献模拟评审视角提出潜在问题。"
            "申请人逐条审视后，针对有价值的反馈独立完善研究方案。"
            "最终研究方案由申请人及团队讨论确定，AI 仅提供自查参考。"
        ),
    },
    "roadmap": {
        "tool_name": "GeoFund Copilot 技术路线图生成模块",
        "ai_role": "基于领域文献分析常见方法链，生成技术路线图初稿（SVG 格式）",
        "ai_scope": [
            "检索相关论文了解该方向的常见研究方法和流程",
            "生成技术路线图的阶段划分、任务和方法建议",
            "渲染 SVG 格式的路线图初稿",
        ],
        "human_required": [
            "核实每个阶段的任务设置是否符合实际研究条件",
            "根据实验室现有设备、数据和技术基础调整方案",
            "使用专业绘图软件（Visio/PPT/Adobe Illustrator）重绘终稿",
            "经导师或团队审核确认技术路线的可行性",
            "不可直接将 AI 生成的 SVG 作为申请书终稿图片",
        ],
        "disclosure_text": (
            "本申请的技术路线图设计过程中，使用 GeoFund Copilot 工具辅助分析"
            "该领域常见研究方法和实验流程，生成路线图初稿框架。"
            "申请人根据实验室实际条件和研究基础对技术路线进行了全面调整，"
            "并使用专业绘图软件重新绘制。最终技术路线图经团队讨论审核后确定。"
            "AI 生成的初稿仅作为框架参考，终稿由申请人独立完成。"
        ),
    },
    "rationale": {
        "tool_name": "GeoFund Copilot 立项依据辅助模块",
        "ai_role": "基于文献检索和聚类分析，辅助梳理研究脉络、识别知识缺口",
        "ai_scope": [
            "检索该方向相关文献并按主题聚类",
            "生成研究现状框架和脉络梳理建议",
            "识别潜在的知识缺口和研究切入点",
        ],
        "human_required": [
            "精读 AI 检索到的每篇核心文献全文",
            "核实 AI 生成的研究脉络框架与实际文献内容是否一致",
            "独立撰写立项依据全文，不直接沿用 AI 生成内容",
            "基于文献精读补充 AI 遗漏的重要工作和学术观点",
            "确保知识缺口分析基于文献事实而非 AI 推测",
            "团队讨论论证研究切入点的科学合理性",
        ],
        "disclosure_text": (
            "本申请立项依据撰写过程中，使用 GeoFund Copilot 工具辅助文献调研。"
            "AI 基于 OpenAlex 数据库检索相关文献并生成研究脉络框架建议。"
            "申请人在 AI 框架基础上精读全部核心文献（共 XX 篇），"
            "核实各研究观点后独立撰写立项依据全文。"
            "AI 生成的框架和知识缺口建议仅作为调研起点，"
            "最终立项依据内容、学术观点和研究切入点由申请人根据文献精读结果独立确定。"
        ),
    },
}


def generate_disclosure(module: str, extra_info: dict = None) -> dict:
    """
    生成指定模块的 AI 使用合规声明

    返回:
        {
            "tool_name": str,
            "ai_scope": [str],
            "human_required": [str],         # 人工核实清单
            "disclosure_text": str,           # 可直接插入申请书的声明文本
            "checklist_markdown": str,        # Markdown 格式的核实清单
        }
    """
    template = DISCLOSURE_TEMPLATES.get(module, {})
    if not template:
        return {"error": f"未知模块: {module}"}

    result = {
        "tool_name": template["tool_name"],
        "ai_role": template["ai_role"],
        "ai_scope": template["ai_scope"],
        "human_required": template["human_required"],
        "disclosure_text": template["disclosure_text"],
    }

    # 生成 Markdown 核实清单
    lines = [
        f"### AI 使用声明 — {template['tool_name']}",
        "",
        "**AI 参与范围：**",
    ]
    for item in template["ai_scope"]:
        lines.append(f"- {item}")
    lines.append("")
    lines.append("**人工核实清单（申请人必须完成）：**")
    for item in template["human_required"]:
        lines.append(f"- [ ] {item}")
    lines.append("")
    lines.append("**建议插入申请书的声明：**")
    lines.append("")
    lines.append(f"> {template['disclosure_text']}")

    result["checklist_markdown"] = "\n".join(lines)
    return result


def generate_full_disclosure(modules_used: list[str]) -> str:
    """
    生成整份申请书的完整 AI 使用声明（汇总多个模块）
    """
    lines = [
        "## AI 工具使用声明",
        "",
        "根据国家自然科学基金委员会关于 AI 工具使用的相关规定，"
        "本申请书撰写过程中使用了以下 AI 辅助工具，具体说明如下：",
        "",
    ]

    for i, module in enumerate(modules_used, 1):
        template = DISCLOSURE_TEMPLATES.get(module, {})
        if not template:
            continue
        lines.append(f"### {i}. {template['tool_name']}")
        lines.append("")
        lines.append(f"**工具用途：** {template['ai_role']}")
        lines.append("")
        lines.append("**AI 参与环节：**")
        for item in template["ai_scope"]:
            lines.append(f"- {item}")
        lines.append("")
        lines.append("**人工核实过程：**")
        for item in template["human_required"]:
            lines.append(f"- {item}")
        lines.append("")
        lines.append(f"**声明：** {template['disclosure_text']}")
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append(
        "以上所有 AI 工具仅用于辅助文献调研和方案框架参考。"
        "本申请书的学术观点、创新点、研究方案和技术路线"
        "均由申请人及研究团队独立确定，AI 不参与科学判断和学术决策。"
    )

    return "\n".join(lines)
