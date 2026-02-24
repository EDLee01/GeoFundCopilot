"""
创新点查重 / 新颖度评估
双源检索 + 4维度重叠分析
"""

from __future__ import annotations

import json
import hashlib
from openai import OpenAI
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from geomind_sdk.search import SearchEngine

from geomind_sdk.crossref import CrossRefClient


class NoveltyChecker:

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

    def check(
        self,
        innovation_point: str,
        qdrant_top_k: int = 30,
        crossref_rows: int = 15,
        verbose: bool = True,
        on_progress=None,
    ) -> dict:

        total_steps = 3
        def _progress(step, msg):
            if on_progress:
                on_progress(step, total_steps, msg)

        # Step 1: 提取关键词
        _progress(1, "🧠 解析创新点，提取检索关键词...")
        if verbose:
            print(f"\n🧠 [分析] 解析创新点...")
        keywords = self._extract_keywords(innovation_point)
        if verbose:
            print(f"   关键词: {keywords.get('search_queries', [])}")

        # Step 2: 双源召回
        _progress(2, "🔍 双源检索相似论文...")
        if verbose:
            print(f"\n🔍 [检索] 寻找相似论文...")
        candidates = self._retrieve(
            keywords.get("search_queries", []),
            qdrant_top_k=qdrant_top_k,
            crossref_rows=crossref_rows,
        )
        if verbose:
            print(f"   找到 {len(candidates)} 篇候选")

        if not candidates:
            return {
                "innovation_point": innovation_point,
                "novelty_score": 9,
                "verdict": "高度新颖（未找到相似论文）",
                "overlap_analysis": {},
                "most_threatening": [],
                "suggestions": [],
                "all_similar": [],
            }

        # Step 3: LLM 深度评估
        _progress(3, f"📊 LLM 深度比对 {len(candidates)} 篇论文...")
        if verbose:
            print(f"\n📊 [评估] LLM 深度比对...")
        report = self._evaluate(innovation_point, keywords, candidates)
        if verbose:
            score = report.get("novelty_score", 0)
            verdict = report.get("verdict", "")
            print(f"   新颖度: {score}/10 — {verdict}")

        return report

    def _extract_keywords(self, innovation_point):
        prompt = f"""分析以下创新点，提取检索关键词。

创新点: "{innovation_point}"

返回 JSON（不要 markdown 代码块）:
{{
    "method": "核心方法（英文）",
    "application": "应用场景（英文）",
    "region": "研究区域（英文，如无则空）",
    "data_source": "数据源（英文，如无则空）",
    "search_queries": [
        "英文检索词1（精确匹配核心内容）",
        "英文检索词2（方法角度）",
        "英文检索词3（应用角度）"
    ]
}}"""

        resp = self._chat(prompt)
        return self._parse_json(resp)

    def _retrieve(self, queries, qdrant_top_k=30, crossref_rows=15):
        seen = {}
        for query in queries:
            try:
                results = self.engine.search(query, top_k=qdrant_top_k)
                for p in results:
                    p["source"] = "qdrant"
                    key = self._paper_key(p)
                    if key not in seen or p.get("score", 0) > seen[key].get("score", 0):
                        seen[key] = p
            except Exception:
                pass

            try:
                cr_results = self.crossref.search(query, rows=crossref_rows)
                for p in cr_results:
                    p["source"] = "crossref"
                    p["score"] = 0.5
                    key = self._paper_key(p)
                    if key not in seen:
                        seen[key] = p
            except Exception:
                pass

        return sorted(seen.values(), key=lambda x: (x.get("score", 0), x.get("cited_by", 0)), reverse=True)

    def _evaluate(self, innovation_point, keywords, candidates):
        batch = candidates[:25]

        paper_list = []
        for i, p in enumerate(batch):
            first = p.get("first_author", "Unknown")
            n = p.get("authors_count", 0)

            meta_parts = []
            if p.get("journal"):
                meta_parts.append(p["journal"])
            if p.get("year"):
                meta_parts.append(str(p["year"]))
            meta_parts.append(f"Cited:{p.get('cited_by', 0)}")
            meta = " | ".join(meta_parts)

            entry = (
                f"[{i}] {p.get('title', '?')}\n"
                f"    {first} et al. ({n}人) | {meta}\n"
                f"    摘要: {p.get('abstract', '')[:300]}"
            )
            paper_list.append(entry)

        papers_text = "\n\n".join(paper_list)
        method = keywords.get("method", "")
        application = keywords.get("application", "")
        region = keywords.get("region", "")
        data_source = keywords.get("data_source", "")

        prompt = f"""你是学术创新性审查专家。评估创新点与已有文献的重叠程度。

创新点: "{innovation_point}"
- 方法: {method}
- 应用: {application}
- 区域: {region}
- 数据: {data_source}

相似论文:
{papers_text}

===== 重要规则 =====

1. 只基于论文摘要内容判断重叠，不要猜测
2. 如果摘要与创新点明显不相关，该论文不构成威胁
3. 单维度重叠（只有方法或只有应用相同）很正常，不算严重
4. 只有多维度同时重叠才算"严重威胁"

返回 JSON（不要 markdown 代码块）:
{{
    "novelty_score": 1-10,
    "verdict": "高度新颖/较为新颖/有一定重叠/新颖度不足",
    "overlap_analysis": {{
        "method": "方法重叠分析（中文）",
        "application": "应用重叠分析（中文）",
        "region": "区域重叠分析（中文）",
        "data_source": "数据重叠分析（中文）"
    }},
    "most_threatening": [
        {{
            "index": N,
            "threat_level": "high/medium/low",
            "overlap_dimensions": ["重叠维度"],
            "analysis": "威胁分析（中文）"
        }}
    ],
    "unique_aspects": ["创新点独特之处（中文）"],
    "suggestions": ["改写建议（中文）"]
}}

评分: 9-10高度新颖, 7-8较新颖, 5-6有重叠, 3-4不足, 1-2高度重叠
most_threatening 选最多 3 篇。"""

        resp = self._chat(prompt, temperature=0.2)
        report = self._parse_json(resp)
        report["innovation_point"] = innovation_point

        # 补充论文信息
        for t in report.get("most_threatening", []):
            idx = t.get("index", -1)
            if 0 <= idx < len(batch):
                t["paper"] = {
                    "title": batch[idx].get("title", ""),
                    "first_author": batch[idx].get("first_author", ""),
                    "journal": batch[idx].get("journal", ""),
                    "year": batch[idx].get("year", 0),
                    "cited_by": batch[idx].get("cited_by", 0),
                    "doi": batch[idx].get("doi", ""),
                }

        report["all_similar"] = [
            {"title": p.get("title", ""), "year": p.get("year", 0),
             "journal": p.get("journal", ""), "cited_by": p.get("cited_by", 0),
             "score": p.get("score", 0), "source": p.get("source", "")}
            for p in batch[:15]
        ]
        return report

    def _chat(self, prompt, temperature=0.3):
        response = self.llm.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "你是学术创新性审查专家。严格按 JSON 格式返回，不要 markdown 代码块。"},
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

    @staticmethod
    def _paper_key(paper):
        doi = paper.get("doi", "")
        if doi:
            return doi.lower().strip()
        title = paper.get("title", "")
        return hashlib.md5(title.lower().encode()).hexdigest()
