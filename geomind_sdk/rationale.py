"""
立项依据辅助生成
文献脉络梳理 + 知识缺口分析 + 研究切入点建议

⚠️ 合规提示: 输出内容为调研框架，申请人必须精读文献后独立撰写立项依据
"""

from __future__ import annotations

import json
from collections import defaultdict
from openai import OpenAI
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from geomind_sdk.search import SearchEngine

from geomind_sdk.crossref import CrossRefClient
from geomind_sdk.compliance import generate_disclosure


class RationaleGenerator:

    def __init__(
        self,
        engine: SearchEngine,
        deepseek_api_key: str,
        deepseek_base_url: str = "https://api.deepseek.com",
        deepseek_model: str = "deepseek-chat",
    ):
        self.engine = engine
        self.crossref = CrossRefClient()
        self.model = deepseek_model
        self.llm = OpenAI(api_key=deepseek_api_key, base_url=deepseek_base_url)

    def generate(
        self,
        research_direction: str,
        innovation_points: str = "",
        verbose: bool = True,
        on_progress=None,
    ) -> dict:

        total_steps = 4
        def _progress(step, msg):
            if on_progress:
                on_progress(step, total_steps, msg)

        # Step 1: 多角度文献检索
        _progress(1, "🔍 多角度文献检索...")
        if verbose:
            print(f"\n🔍 [检索] 多角度文献检索...")

        queries = self._generate_queries(research_direction)
        papers = self._multi_search(queries, verbose=verbose)

        if verbose:
            print(f"   共检索到 {len(papers)} 篇去重后论文")

        # Step 2: 文献脉络梳理（按主题聚类）
        _progress(2, "📚 文献脉络梳理与主题聚类...")
        if verbose:
            print(f"\n📚 [梳理] 文献脉络分析...")

        literature_review = self._analyze_literature(research_direction, papers)

        if verbose:
            themes = literature_review.get("themes", [])
            print(f"   识别出 {len(themes)} 个研究主题")

        # Step 3: 知识缺口分析
        _progress(3, "🔬 知识缺口分析与研究切入点识别...")
        if verbose:
            print(f"\n🔬 [分析] 知识缺口与研究切入点...")

        gap_analysis = self._analyze_gaps(
            research_direction, innovation_points, literature_review, papers
        )

        if verbose:
            gaps = gap_analysis.get("knowledge_gaps", [])
            print(f"   识别出 {len(gaps)} 个知识缺口")

        # Step 4: 生成立项依据框架
        _progress(4, "📝 生成立项依据框架...")
        if verbose:
            print(f"\n📝 [生成] 立项依据框架...")

        rationale_framework = self._generate_framework(
            research_direction, innovation_points, literature_review, gap_analysis
        )

        # 合规声明
        compliance = generate_disclosure("rationale")

        # 汇总需要人工精读的核心文献
        core_papers = self._extract_core_papers(papers, literature_review)

        return {
            "research_direction": research_direction,
            "innovation_points": innovation_points,
            "literature_review": literature_review,
            "gap_analysis": gap_analysis,
            "rationale_framework": rationale_framework,
            "core_papers": core_papers,
            "total_papers_searched": len(papers),
            "compliance": compliance,
        }

    def _generate_queries(self, direction):
        """生成多角度检索词"""
        prompt = f"""你是地球科学文献检索专家。为以下研究方向生成多角度英文检索词。

研究方向: "{direction}"

返回 JSON（不要 markdown 代码块）:
{{
    "queries": [
        {{"query": "英文检索词 3-8 词", "angle": "检索角度（中文）"}}
    ]
}}

要求:
- 生成 5-8 条 query
- 角度覆盖: 核心问题、研究方法、应用领域、理论基础、经典综述、最新进展
- query 必须英文，3-8 词"""

        resp = self._chat(prompt)
        data = self._parse_json(resp)
        return data.get("queries", [{"query": direction, "angle": "核心"}])

    def _multi_search(self, queries, verbose=False):
        """多角度检索并去重"""
        seen = {}
        for q in queries:
            query_text = q.get("query", "")
            if not query_text:
                continue

            # Qdrant
            try:
                results = self.engine.search(query_text, top_k=30)
                for p in results:
                    p["source"] = "qdrant"
                    p["search_angle"] = q.get("angle", "")
                    key = (p.get("doi", "") or p.get("title", "").lower()[:60])
                    if key and (key not in seen or p.get("score", 0) > seen[key].get("score", 0)):
                        seen[key] = p
            except Exception:
                pass

            # CrossRef
            try:
                cr_results = self.crossref.search(query_text, rows=10)
                for p in cr_results:
                    p["source"] = "crossref"
                    p["search_angle"] = q.get("angle", "")
                    key = (p.get("doi", "") or p.get("title", "").lower()[:60])
                    if key and key not in seen:
                        seen[key] = p
            except Exception:
                pass

        return sorted(seen.values(), key=lambda x: x.get("cited_by", 0), reverse=True)

    def _analyze_literature(self, direction, papers):
        """文献脉络梳理 — 按主题聚类"""
        paper_list = []
        for i, p in enumerate(papers[:30]):
            entry = (
                f"[{i}] {p.get('title', '?')}\n"
                f"    {p.get('first_author', '?')} | {p.get('journal', '?')} | "
                f"{p.get('year', '?')} | Cited:{p.get('cited_by', 0)}\n"
                f"    摘要: {p.get('abstract', '')[:250]}"
            )
            paper_list.append(entry)

        papers_text = "\n\n".join(paper_list)

        prompt = f"""你是地球科学文献综述专家。分析以下论文，梳理研究脉络。

研究方向: "{direction}"

论文列表:
{papers_text}

请将这些论文按研究主题聚类，梳理该领域的发展脉络。

返回 JSON（不要 markdown 代码块）:
{{
    "field_overview": "该领域一段概述（中文，100-150字）",
    "themes": [
        {{
            "theme_name": "主题名称（中文，如'基于深度学习的水质预测'）",
            "description": "该主题的研究内容概述（中文，50-100字）",
            "development": "发展脉络（中文，50-100字，从早期到最新）",
            "key_paper_indices": [相关论文的index],
            "status": "成熟/活跃/新兴"
        }}
    ],
    "timeline": [
        {{
            "period": "2015-2018",
            "milestone": "该时期的关键进展（中文）"
        }}
    ],
    "dominant_methods": ["该领域主流方法（中文）"],
    "active_groups": ["活跃的研究团队或学者（如有）"]
}}

要求:
- themes 3-6 个，按逻辑顺序排列
- 只基于论文内容分析，不要编造
- timeline 覆盖近 10 年的关键节点"""

        resp = self._chat(prompt, temperature=0.2)
        return self._parse_json(resp)

    def _analyze_gaps(self, direction, innovation, lit_review, papers):
        """知识缺口分析"""
        themes_text = ""
        for t in lit_review.get("themes", []):
            themes_text += f"- {t.get('theme_name', '?')}: {t.get('description', '')}\n"

        innovation_section = ""
        if innovation:
            innovation_section = f"\n申请人拟提出的创新点:\n{innovation}\n"

        prompt = f"""你是学术研究方向分析专家。基于文献综述结果，分析知识缺口和研究切入点。

研究方向: "{direction}"
{innovation_section}
已梳理的研究主题:
{themes_text}

领域概述: {lit_review.get('field_overview', '')}
主流方法: {', '.join(lit_review.get('dominant_methods', []))}

请分析该领域存在的知识缺口和潜在研究切入点。

返回 JSON（不要 markdown 代码块）:
{{
    "knowledge_gaps": [
        {{
            "gap": "知识缺口描述（中文，一句话）",
            "evidence": "支撑这个缺口存在的证据（中文，基于文献分析）",
            "importance": "high/medium",
            "related_theme": "相关主题名称"
        }}
    ],
    "entry_points": [
        {{
            "point": "研究切入点（中文）",
            "rationale": "为什么从这里切入（中文）",
            "feasibility": "可行性分析（中文）"
        }}
    ],
    "unsolved_problems": ["该领域尚未解决的关键科学问题（中文）"],
    "methodology_gaps": ["方法论层面的不足（中文）"]
}}

⚠️ 要求:
- 知识缺口必须基于文献分析的客观事实，不要凭空推测
- 标注每个缺口的证据来源
- 切入点要具体可操作
- 区分「确实缺乏研究」和「研究较少但已有进展」"""

        resp = self._chat(prompt, temperature=0.2)
        return self._parse_json(resp)

    def _generate_framework(self, direction, innovation, lit_review, gap_analysis):
        """生成立项依据写作框架"""
        gaps_text = "\n".join(
            f"- {g.get('gap', '')}" for g in gap_analysis.get("knowledge_gaps", [])
        )
        themes_text = "\n".join(
            f"- {t.get('theme_name', '')}: {t.get('description', '')}"
            for t in lit_review.get("themes", [])
        )

        innovation_section = ""
        if innovation:
            innovation_section = f"\n创新点: {innovation}\n"

        prompt = f"""你是国自然基金申请书撰写辅导专家。根据文献分析结果，生成立项依据的写作框架。

研究方向: "{direction}"
{innovation_section}
研究主题:
{themes_text}

知识缺口:
{gaps_text}

请生成一个结构化的立项依据写作框架，供申请人参考后独立撰写。

返回 JSON（不要 markdown 代码块）:
{{
    "title_suggestion": "立项依据建议标题（中文）",
    "sections": [
        {{
            "heading": "小节标题（中文）",
            "purpose": "这一节要说明什么（中文）",
            "key_points": ["需要涵盖的要点（中文）"],
            "suggested_refs": "建议引用的文献类型（如'该方向的综述论文'）",
            "writing_tips": "写作建议（中文）"
        }}
    ],
    "logical_flow": "整体逻辑线索（中文，一段话描述从背景→现状→问题→切入的逻辑）",
    "word_count_suggestion": {{
        "total": "建议总字数",
        "per_section": ["每节建议字数"]
    }}
}}

⚠️ 框架要求:
- 遵循国自然申请书立项依据的标准结构
- 逻辑清晰: 背景意义 → 国内外现状 → 存在问题 → 本项目切入点
- 每个 section 的 key_points 要具体到可以直接展开写
- 标注哪些地方需要引用文献
- 这只是框架建议，申请人必须独立撰写全文"""

        resp = self._chat(prompt, temperature=0.3)
        return self._parse_json(resp)

    def _extract_core_papers(self, papers, lit_review):
        """提取需要申请人精读的核心文献"""
        core_indices = set()
        for theme in lit_review.get("themes", []):
            for idx in theme.get("key_paper_indices", []):
                core_indices.add(idx)

        core_papers = []
        for idx in sorted(core_indices):
            if 0 <= idx < len(papers):
                p = papers[idx]
                core_papers.append({
                    "title": p.get("title", ""),
                    "first_author": p.get("first_author", ""),
                    "journal": p.get("journal", ""),
                    "year": p.get("year", 0),
                    "cited_by": p.get("cited_by", 0),
                    "doi": p.get("doi", ""),
                    "read_status": "待精读",
                })

        # 补充高引论文
        for p in papers[:20]:
            doi = p.get("doi", "")
            if doi and not any(c.get("doi") == doi for c in core_papers):
                if p.get("cited_by", 0) > 50:
                    core_papers.append({
                        "title": p.get("title", ""),
                        "first_author": p.get("first_author", ""),
                        "journal": p.get("journal", ""),
                        "year": p.get("year", 0),
                        "cited_by": p.get("cited_by", 0),
                        "doi": p.get("doi", ""),
                        "read_status": "待精读",
                    })

        return core_papers[:20]

    def _chat(self, prompt, temperature=0.3):
        response = self.llm.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "你是地球科学基金申请专家。严格按 JSON 格式返回。"},
                {"role": "user", "content": prompt},
            ],
            temperature=temperature,
            max_tokens=4096,
        )
        return response.choices[0].message.content

    @staticmethod
    def _parse_json(text):
        text = text.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            lines = [l for l in lines if not l.strip().startswith("```")]
            text = "\n".join(lines)
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            start = text.find("{")
            end = text.rfind("}") + 1
            if start >= 0 and end > start:
                try:
                    return json.loads(text[start:end])
                except json.JSONDecodeError:
                    pass
            return {"error": "JSON 解析失败", "raw": text[:500]}
