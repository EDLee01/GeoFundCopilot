"""
研究趋势分析
基于 Qdrant 向量检索 + 年份聚合，分析关键词的发文趋势和里程碑论文
"""

from __future__ import annotations

import json
from collections import defaultdict
from openai import OpenAI
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from geomind_sdk.search import SearchEngine

from geomind_sdk.crossref import CrossRefClient


class TrendAnalyzer:

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

    def analyze(
        self,
        query: str,
        year_from: int = 2010,
        year_to: int = 2025,
        top_k: int = 300,
        verbose: bool = True,
        on_progress=None,
    ) -> dict:

        def _progress(step, total, msg):
            if on_progress:
                on_progress(step, total, msg)

        _progress(1, 2, "🔍 语义检索相关论文并按年份聚合...")
        if verbose:
            print(f"\n🔍 [检索] 搜索相关论文...")

        papers = self.engine.search(query, top_k=top_k)

        if verbose:
            print(f"   找到 {len(papers)} 篇相关论文")

        # 按年份聚合
        year_papers = defaultdict(list)
        for p in papers:
            y = p.get("year", 0)
            if year_from <= y <= year_to:
                year_papers[y].append(p)

        # 年份分布
        year_distribution = {}
        for y in range(year_from, year_to + 1):
            year_distribution[y] = len(year_papers.get(y, []))

        # 每年最高引论文（里程碑）
        milestones = []
        for y in sorted(year_papers.keys()):
            if not year_papers[y]:
                continue
            top_paper = max(year_papers[y], key=lambda x: x.get("cited_by", 0))
            if top_paper.get("cited_by", 0) > 10:
                milestones.append({
                    "year": y,
                    "title": top_paper.get("title", ""),
                    "first_author": top_paper.get("first_author", ""),
                    "journal": top_paper.get("journal", ""),
                    "cited_by": top_paper.get("cited_by", 0),
                    "doi": top_paper.get("doi", ""),
                })

        # Top 期刊分布
        journal_count = defaultdict(int)
        for p in papers:
            j = p.get("journal", "")
            if j:
                journal_count[j] += 1
        top_journals = sorted(journal_count.items(), key=lambda x: x[1], reverse=True)[:10]

        # LLM 趋势总结
        _progress(2, 2, "🧠 LLM 分析趋势，生成报告...")
        if verbose:
            print(f"\n🧠 [分析] 生成趋势报告...")

        trend_summary = self._summarize(query, year_distribution, milestones, top_journals)

        return {
            "query": query,
            "year_range": [year_from, year_to],
            "total_papers": len(papers),
            "year_distribution": year_distribution,
            "milestones": milestones,
            "top_journals": [{"journal": j, "count": c} for j, c in top_journals],
            "trend_summary": trend_summary.get("summary", ""),
            "hot_topics": trend_summary.get("hot_topics", []),
            "future_directions": trend_summary.get("future_directions", []),
        }

    def _summarize(self, query, year_distribution, milestones, top_journals):
        dist_text = ", ".join(f"{y}:{c}" for y, c in sorted(year_distribution.items()))
        milestone_text = "\n".join(
            f"- {m['year']}: {m['title'][:80]} ({m['journal']}, Cited:{m['cited_by']})"
            for m in milestones[:10]
        )
        journal_text = "\n".join(f"- {j}: {c} 篇" for j, c in top_journals[:8])

        prompt = f"""你是地球科学研究趋势分析专家。分析以下研究方向的发展趋势。

研究方向: "{query}"

年份-论文数分布（相关性加权）:
{dist_text}

里程碑论文:
{milestone_text}

主要发表期刊:
{journal_text}

返回 JSON（不要 markdown 代码块）:
{{
    "summary": "200-300字的中文趋势总结，包含：1)整体发展脉络 2)关键转折点 3)近年热点",
    "hot_topics": ["当前3-5个热点子方向（中文）"],
    "future_directions": ["3-5个未来可能的研究方向（中文）"]
}}"""

        resp = self._chat(prompt)
        return self._parse_json(resp)

    def _chat(self, prompt, temperature=0.3):
        response = self.llm.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "你是地球科学研究趋势分析专家。严格按 JSON 格式返回。"},
                {"role": "user", "content": prompt},
            ],
            temperature=temperature,
            max_tokens=2048,
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
            return {"summary": text[:500], "hot_topics": [], "future_directions": []}
