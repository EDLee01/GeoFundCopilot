"""
评审视角模拟
模拟国自然评审专家，对研究方向提出问题和建议
"""

from __future__ import annotations

import json
from openai import OpenAI
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from geomind_sdk.search import SearchEngine

from geomind_sdk.crossref import CrossRefClient


class ReviewerSimulator:

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

    def review(
        self,
        research_direction: str,
        innovation_points: str = "",
        verbose: bool = True,
        on_progress=None,
    ) -> dict:

        def _progress(step, total, msg):
            if on_progress:
                on_progress(step, total, msg)

        # Step 1: 检索相关论文以了解领域现状
        _progress(1, 2, "🔍 检索相关论文，了解领域现状...")
        if verbose:
            print(f"\n🔍 [检索] 了解领域现状...")
        papers = self.engine.search(research_direction, top_k=30)
        if verbose:
            print(f"   找到 {len(papers)} 篇相关论文")

        # CrossRef 补充最新论文
        try:
            cr_papers = self.crossref.search(research_direction, rows=10)
        except Exception:
            cr_papers = []

        # Step 2: LLM 模拟评审
        _progress(2, 2, "👨‍🏫 LLM 模拟评审专家意见...")
        if verbose:
            print(f"\n👨‍🏫 [评审] 模拟专家评审视角...")
        report = self._simulate_review(research_direction, innovation_points, papers, cr_papers)

        return report

    def _simulate_review(self, research_direction, innovation_points, papers, cr_papers):
        # 构建论文摘要
        paper_summaries = []
        for i, p in enumerate(papers[:20]):
            summary = (
                f"[{i}] {p.get('title', '?')}\n"
                f"    {p.get('first_author', '?')} | {p.get('journal', '?')} | "
                f"{p.get('year', '?')} | Cited:{p.get('cited_by', 0)}\n"
                f"    摘要: {p.get('abstract', '')[:200]}"
            )
            paper_summaries.append(summary)

        for i, p in enumerate(cr_papers[:5], len(papers[:20])):
            summary = (
                f"[{i}] {p.get('title', '?')}\n"
                f"    {p.get('first_author', '?')} | {p.get('journal', '?')} | "
                f"{p.get('year', '?')} | Cited:{p.get('cited_by', 0)}"
            )
            paper_summaries.append(summary)

        papers_text = "\n\n".join(paper_summaries)

        innovation_section = ""
        if innovation_points:
            innovation_section = f"\n申请人提出的创新点:\n{innovation_points}\n"

        prompt = f"""你是一位资深的国家自然科学基金评审专家（地球科学领域），正在评审一份基金申请书。
请从评审专家的角度，对以下研究方向提出建设性的意见。

研究方向: "{research_direction}"
{innovation_section}
该领域近期相关论文:
{papers_text}

===== 评审要求 =====

请从以下维度进行评审，模拟真实的国自然评审意见:

1. **立项依据评审**: 研究意义是否充分？国内外研究现状是否全面？
2. **研究内容评审**: 研究方案是否可行？技术路线是否合理？
3. **创新性评审**: 创新点是否成立？是否已有类似工作？
4. **可能的质疑**: 评审专家最可能提出哪些尖锐问题？
5. **改进建议**: 如何增强申请书的竞争力？

返回 JSON（不要 markdown 代码块）:
{{
    "overall_score": "A/B/C（A=优秀 B=良好 C=一般）",
    "overall_comment": "一段总体评价（中文，100-200字）",
    "strengths": ["研究方向的优势（中文，3-5条）"],
    "weaknesses": ["潜在的不足（中文，3-5条）"],
    "critical_questions": ["评审专家最可能提出的尖锐问题（中文，3-5个）"],
    "missing_literature": ["可能遗漏的重要文献方向或课题组（中文，2-4条）"],
    "improvement_suggestions": ["具体改进建议（中文，3-5条）"],
    "feasibility_concerns": ["可行性方面的顾虑（中文，2-3条）"],
    "recommended_references": ["建议补充引用的论文类型或具体方向（中文，2-4条）"]
}}

⚠️ 要求:
- 模拟真实评审语气，直接、具体、有建设性
- 基于检索到的论文来判断领域现状，不要凭空编造
- 尖锐问题要有针对性，像真实评审一样犀利
- 改进建议要具体可操作"""

        resp = self._chat(prompt, temperature=0.4)
        report = self._parse_json(resp)
        report["research_direction"] = research_direction
        if innovation_points:
            report["innovation_points"] = innovation_points
        return report

    def _chat(self, prompt, temperature=0.3):
        response = self.llm.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "你是资深国自然评审专家。严格按 JSON 格式返回。"},
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
