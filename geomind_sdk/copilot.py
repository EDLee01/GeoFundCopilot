"""
GeoFund Copilot — 智能文献推荐 Agent

修复:
- Ranker 有拒绝能力（候选全部不相关时不强行推荐）
- CrossRef 结果不因 score=0 被排到最后
- 元数据完整传递
- 相关性阈值检查
"""

from __future__ import annotations

import json
import hashlib
from openai import OpenAI
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from geomind_sdk.search import SearchEngine

from geomind_sdk.crossref import CrossRefClient


class GeoFundCopilot:

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

    # ============================================================
    # 主入口
    # ============================================================

    def recommend(
        self,
        user_query: str,
        top_k: int = 15,
        recall_per_query: int = 30,
        crossref_per_query: int = 20,
        verify: bool = True,
        verbose: bool = True,
    ) -> dict:

        # Step 1: Planner
        if verbose:
            print(f"\n🧠 [Planner] 分析用户意图...")
        intent = self._planner(user_query)
        if verbose:
            print(f"   主题: {intent.get('topic', '?')}")
            for i, q in enumerate(intent.get("queries", []), 1):
                print(f"   策略{i}: {q['query']}  ({q['purpose']})")

        # Step 2: Retriever
        if verbose:
            print(f"\n🔍 [Retriever] 双源检索...")
        candidates = self._retrieve(
            intent.get("queries", []),
            recall_per_query=recall_per_query,
            crossref_per_query=crossref_per_query,
            verbose=verbose,
        )
        if verbose:
            qdrant_count = sum(1 for c in candidates if c.get("source") != "crossref")
            cr_count = sum(1 for c in candidates if c.get("source") == "crossref")
            print(f"   候选池: {len(candidates)} 篇 (Qdrant: {qdrant_count}, CrossRef: {cr_count})")

        if not candidates:
            return {"query": user_query, "recommendations": {}, "total": 0, "rejected": False}

        # Step 3: Ranker（含拒绝能力）
        if verbose:
            print(f"\n📊 [Ranker] LLM 精排 + 分类...")
        ranked, rejected = self._ranker(user_query, intent, candidates, top_k=top_k)

        if rejected:
            if verbose:
                print(f"   ⚠️ Ranker 判断候选论文与用户需求不相关，已拒绝推荐")
            return {"query": user_query, "recommendations": {}, "total": 0, "rejected": True,
                    "reject_reason": ranked.get("reject_reason", "候选论文与用户需求不匹配")}

        if verbose:
            for cat, papers in ranked.items():
                if isinstance(papers, list):
                    print(f"   {cat}: {len(papers)} 篇")
            filtered_total = sum(len(v) for v in ranked.values() if isinstance(v, list))
            print(f"   (相关性 ≥ 7 分筛选后: {filtered_total} 篇)")

        # Step 3.5: Supplement — 检查是否遗漏重要论文，补充检索
        if verbose:
            print(f"\n🔄 [Supplement] 检查是否遗漏重要论文...")
        ranked = self._supplement(user_query, intent, ranked, candidates, verbose=verbose)

        if verbose:
            total_after = sum(len(v) for v in ranked.values() if isinstance(v, list))
            print(f"   补充后总计: {total_after} 篇")

        # Step 4: Critic
        verification_summary = {}
        if verify:
            if verbose:
                print(f"\n🔎 [Critic] 验证文献真实性...")
            ranked, verification_summary = self._critic(ranked, verbose=verbose)

        total = sum(len(v) for v in ranked.values() if isinstance(v, list))
        return {
            "query": user_query,
            "intent": intent,
            "recommendations": ranked,
            "verification_summary": verification_summary,
            "total": total,
            "rejected": False,
        }

    # ============================================================
    # Step 1: Planner
    # ============================================================

    def _planner(self, user_query: str) -> dict:
        prompt = f"""你是地球科学文献检索专家。分析用户的研究方向，生成多角度英文检索策略。

用户输入: "{user_query}"

返回 JSON（不要 markdown 代码块）:
{{
    "topic": "一句话概括研究主题（中文）",
    "method_keywords": ["用户提到的方法，英文"],
    "domain_keywords": ["研究领域/区域，英文"],
    "queries": [
        {{"query": "英文检索词 3-8 词", "purpose": "目的（中文）"}}
    ]
}}

要求:
1. 生成 4-6 条 query，从不同角度覆盖
2. 必须覆盖: 核心匹配、方法检索、区域/应用、经典综述
3. 所有 query 必须英文（论文库全英文）
4. 每条 query 3-8 词，简洁精准
5. 如果用户输入不像是研究方向（太短、太模糊），仍然尽力理解并生成合理的检索策略"""

        resp = self._chat(prompt)
        return self._parse_json(resp)

    # ============================================================
    # Step 2: Retriever
    # ============================================================

    def _retrieve(self, queries, recall_per_query=30, crossref_per_query=10, verbose=False):
        qdrant_seen = {}
        crossref_seen = {}

        for q in queries:
            query_text = q["query"]
            purpose = q.get("purpose", "")

            # Qdrant
            try:
                qdrant_results = self.engine.search(query_text, top_k=recall_per_query)
                for paper in qdrant_results:
                    paper["source"] = "qdrant"
                    paper["recall_query"] = query_text
                    paper["recall_purpose"] = purpose
                    key = self._paper_key(paper)
                    if key not in qdrant_seen or paper.get("score", 0) > qdrant_seen[key].get("score", 0):
                        qdrant_seen[key] = paper
            except Exception as e:
                if verbose:
                    print(f"   ⚠️ Qdrant 检索失败 ({query_text}): {e}")

            # CrossRef
            try:
                cr_results = self.crossref.search(query_text, rows=crossref_per_query)
                for paper in cr_results:
                    paper["source"] = "crossref"
                    paper["recall_query"] = query_text
                    paper["recall_purpose"] = purpose
                    paper["score"] = 0.0  # CrossRef 没有向量分数
                    key = self._paper_key(paper)
                    if key not in crossref_seen:
                        crossref_seen[key] = paper
            except Exception as e:
                if verbose:
                    print(f"   ⚠️ CrossRef 检索失败 ({query_text}): {e}")

        # 去掉 CrossRef 中与 Qdrant 重复的（Qdrant 有向量分数，优先保留）
        for key in qdrant_seen:
            crossref_seen.pop(key, None)

        # 分别排序
        qdrant_list = sorted(
            qdrant_seen.values(),
            key=lambda x: x.get("score", 0),
            reverse=True,
        )
        crossref_list = sorted(
            crossref_seen.values(),
            key=lambda x: x.get("cited_by", 0),
            reverse=True,
        )

        if verbose:
            print(f"   Qdrant 去重后: {len(qdrant_list)} 篇", end="")
            if qdrant_list:
                top3 = [round(p.get("score", 0), 3) for p in qdrant_list[:3]]
                print(f" (top3 score: {top3})", end="")
            print(f" | CrossRef 去重后: {len(crossref_list)} 篇")

        # 交叉合并: 每 2 篇 Qdrant 插 1 篇 CrossRef，保证两源都有代表
        candidates = []
        qi, ci = 0, 0
        while qi < len(qdrant_list) or ci < len(crossref_list):
            # 取 2 篇 Qdrant
            for _ in range(2):
                if qi < len(qdrant_list):
                    candidates.append(qdrant_list[qi])
                    qi += 1
            # 取 1 篇 CrossRef
            if ci < len(crossref_list):
                candidates.append(crossref_list[ci])
                ci += 1

        return candidates

    # ============================================================
    # Step 3: Ranker（有拒绝能力）
    # ============================================================

    def _ranker(self, user_query, intent, candidates, top_k=15):
        max_candidates = min(len(candidates), top_k * 4, 50)
        batch = candidates[:max_candidates]

        paper_summaries = []
        for i, p in enumerate(batch):
            first = p.get("first_author", "Unknown")
            n = p.get("authors_count", 0)
            author_str = f"{first} et al." if n > 2 else (f"{first}" if n <= 1 else f"{first} et al.")

            # 构建元数据行（只显示有值的字段）
            meta_parts = []
            if p.get("journal"):
                meta_parts.append(p["journal"])
            if p.get("year"):
                meta_parts.append(str(p["year"]))
            meta_parts.append(f"Cited:{p.get('cited_by', 0)}")
            if p.get("jcr_zone"):
                meta_parts.append(p["jcr_zone"])
            if p.get("cas_zone"):
                meta_parts.append(f"CAS{p['cas_zone']}区")
            meta_line = " | ".join(meta_parts)

            abstract = p.get("abstract", "")[:300]
            source = p.get("source", "qdrant")
            score = p.get("score", 0)

            summary = (
                f"[{i}] {p['title']}\n"
                f"    作者: {author_str} ({n}人)\n"
                f"    {meta_line}\n"
                f"    来源: {source} (score={score:.3f})\n"
                f"    摘要: {abstract}"
            )
            paper_summaries.append(summary)

        papers_text = "\n\n".join(paper_summaries)
        methods = ", ".join(intent.get("method_keywords", []))

        prompt = f"""你是地球科学基金申请的文献推荐专家。

用户研究方向: "{user_query}"
研究方法: {methods}

候选论文:
{papers_text}

===== 任务 =====

你需要完成两步:

第一步: 对每篇候选论文打「主题相关性」分 (1-10):
- 9-10: 研究目标和方法都与用户完全一致
- 7-8: 研究目标一致，方法相关或可借鉴
- 5-6: 仅方法相关但研究对象不同（如用户研究水质但论文研究降雨/空气/植被）
- 3-4: 仅有表面关键词重叠
- 1-2: 完全不相关

⚠️ 关键判断原则:
- 如果用户研究的是「溶解氧预测」，那么研究「降雨预报」「空气质量」「植被氮」「遥感反演」的论文，即使用了相同的深度学习方法（LSTM/CNN），相关性也不超过 5 分
- 只有研究对象（如水质、溶解氧、河流水环境）确实匹配的才能 ≥ 7 分
- 方法相同不等于研究相关

第二步: 从相关性 ≥ 7 分的论文中，分 4 类推荐:

📖 foundational（必引经典 3-5篇）: 引用数高(>50)、领域奠基工作、权威综述，必须与研究主题直接相关
🔬 cutting_edge（前沿进展 3-5篇）: 2023年及以后、最新研究动态
⚙️ methodological（方法借鉴 2-4篇）: 与 {methods} 方法直接相关，且研究对象与用户相近
👤 reviewer_relevant（潜在评审人 2-4篇）: 该方向活跃学者的代表作

===== 返回格式 =====

如果相关性 ≥ 7 分的论文不足 5 篇，返回:
{{"rejected": true, "reject_reason": "说明为什么候选论文不匹配用户需求"}}

否则返回:
{{
    "rejected": false,
    "relevance_scores": [{{"index": N, "score": 8, "brief": "一句话说明相关性"}}],
    "foundational": [{{"index": N, "reason": "推荐理由"}}],
    "cutting_edge": [{{"index": N, "reason": "推荐理由"}}],
    "methodological": [{{"index": N, "reason": "推荐理由"}}],
    "reviewer_relevant": [{{"index": N, "reason": "推荐理由"}}]
}}

===== 严格要求 =====

- relevance_scores 只列出 ≥ 7 分的论文
- 四类推荐只能从 ≥ 7 分的论文中选
- 每篇论文只归入最合适的一类，同一个 index 不能出现在多个类别中
- 同一篇论文（相同标题或相同 DOI）只选一次
- 不要编造推荐理由，只基于摘要内容判断
- 宁缺毋滥：如果某类别找不到足够多的高相关性论文，少选几篇也可以
- 返回 JSON，不要 markdown 代码块"""

        resp = self._chat(prompt)
        ranking = self._parse_json(resp)

        # 检查是否被拒绝
        if ranking.get("rejected", False):
            return {"reject_reason": ranking.get("reject_reason", "候选论文不匹配")}, True

        # 构建相关性分数表（只有 ≥7 分的才能被选）
        valid_indices = set()
        relevance_scores = ranking.get("relevance_scores", [])
        for item in relevance_scores:
            idx = item.get("index", -1)
            score = item.get("score", 0)
            if score >= 7 and 0 <= idx < len(batch):
                valid_indices.add(idx)

        # 组装结果，确保每篇论文只出现在一个类别中，且通过相关性过滤
        result = {}
        used_indices = set()
        for category in ["foundational", "cutting_edge", "methodological", "reviewer_relevant"]:
            items = ranking.get(category, [])
            papers = []
            for item in items:
                idx = item.get("index", -1)
                # 必须: 有效索引 + 未使用 + 通过相关性过滤(如果有分数表的话)
                if 0 <= idx < len(batch) and idx not in used_indices:
                    if relevance_scores and idx not in valid_indices:
                        continue  # 相关性不足，跳过
                    paper = batch[idx].copy()
                    paper["reason"] = item.get("reason", "")
                    paper["category"] = category
                    papers.append(paper)
                    used_indices.add(idx)
            result[category] = papers

        return result, False

    # ============================================================
    # Step 3.5: Supplement — 补充遗漏的重要论文
    # ============================================================

    def _supplement(self, user_query, intent, ranked, existing_candidates, verbose=False):
        """让 LLM 审视当前推荐，判断是否遗漏重要论文，生成补充检索词"""

        # 收集已推荐论文的标题
        existing_titles = []
        existing_keys = set()
        for cat, papers in ranked.items():
            if not isinstance(papers, list):
                continue
            for p in papers:
                existing_titles.append(f"- {p.get('title', '?')} ({p.get('year', '?')})")
                existing_keys.add(self._paper_key(p))

        titles_text = "\n".join(existing_titles[:20])
        methods = ", ".join(intent.get("method_keywords", []))

        prompt = f"""你是地球科学文献检索专家。审查以下文献推荐结果，判断是否遗漏了该领域的重要论文。

用户研究方向: "{user_query}"
研究方法: {methods}

当前已推荐论文:
{titles_text}

请思考:
1. 该研究方向的高影响力论文（发表在 Nature, Science, Nature Water, EST, Water Research 等顶刊）是否被覆盖？
2. 该方法在该应用领域的开创性工作是否被覆盖？
3. 是否遗漏了重要的综述论文？

如果你认为推荐已经足够全面，返回:
{{"needs_supplement": false}}

如果你认为可能遗漏了重要论文，返回:
{{
    "needs_supplement": true,
    "reason": "为什么认为有遗漏（中文）",
    "supplement_queries": [
        {{"query": "英文检索词 3-8 词", "target": "想要找到什么类型的论文"}}
    ]
}}

要求:
- supplement_queries 最多 3 条
- query 必须英文，3-8 词，尽量精准
- 不要重复已有的检索策略
- 只在确实认为遗漏了重要论文时才补充
- 返回 JSON，不要 markdown 代码块"""

        resp = self._chat(prompt)
        result = self._parse_json(resp)

        if not result.get("needs_supplement", False):
            if verbose:
                print(f"   ✅ LLM 认为推荐已足够全面，无需补充")
            return ranked

        if verbose:
            print(f"   ⚠️ {result.get('reason', '可能遗漏重要论文')}")

        supplement_queries = result.get("supplement_queries", [])
        if not supplement_queries:
            return ranked

        # 用补充 query 搜索 CrossRef
        new_papers = []
        for sq in supplement_queries:
            query_text = sq.get("query", "")
            target = sq.get("target", "")
            if not query_text:
                continue

            if verbose:
                print(f"   🔍 补充检索: {query_text}  ({target})")

            try:
                cr_results = self.crossref.search(query_text, rows=15)
                for paper in cr_results:
                    paper["source"] = "crossref"
                    paper["recall_query"] = query_text
                    paper["recall_purpose"] = f"补充: {target}"
                    paper["score"] = 0.0
                    key = self._paper_key(paper)
                    if key not in existing_keys:
                        new_papers.append(paper)
                        existing_keys.add(key)
            except Exception as e:
                if verbose:
                    print(f"   ⚠️ 补充检索失败: {e}")

        if not new_papers:
            if verbose:
                print(f"   未找到新论文")
            return ranked

        if verbose:
            print(f"   找到 {len(new_papers)} 篇新候选")

        # 让 LLM 从新候选中筛选值得加入的
        ranked = self._supplement_rank(user_query, intent, ranked, new_papers, verbose=verbose)
        return ranked

    def _supplement_rank(self, user_query, intent, ranked, new_papers, verbose=False):
        """从补充候选中筛选值得加入推荐的论文"""

        paper_summaries = []
        for i, p in enumerate(new_papers[:30]):
            first = p.get("first_author", "Unknown")
            journal = p.get("journal", "?")
            year = p.get("year", "?")
            cited = p.get("cited_by", 0)
            abstract = p.get("abstract", "")[:300]

            summary = (
                f"[{i}] {p.get('title', 'Untitled')}\n"
                f"    {first} | {journal} | {year} | Cited:{cited}\n"
                f"    摘要: {abstract}"
            )
            paper_summaries.append(summary)

        papers_text = "\n\n".join(paper_summaries)
        methods = ", ".join(intent.get("method_keywords", []))

        # 收集已有论文标题供参考
        existing = []
        for cat, papers in ranked.items():
            if isinstance(papers, list):
                for p in papers:
                    existing.append(p.get("title", "?"))

        prompt = f"""你是地球科学文献推荐专家。以下是补充检索到的候选论文，请判断哪些值得加入推荐。

用户研究方向: "{user_query}"
研究方法: {methods}

已推荐论文（不要重复选择）:
{chr(10).join(f"- {t}" for t in existing[:15])}

补充候选论文:
{papers_text}

从候选中选出确实重要且与用户研究**主题直接相关**的论文（0-3篇），分配到合适的类别。

⚠️ 严格筛选标准:
- 论文的研究对象必须与用户研究对象一致（如用户研究水质/溶解氧，只选水质/溶解氧相关的）
- 仅仅方法相同（如同样用 LSTM）但研究对象不同（如降雨、空气、植被）的论文不选
- 优先选择: 高引用(>50)、顶刊(Nature/Science/EST/Water Research/Nature Water 等)
- 宁缺毋滥，没有高度相关的就返回空列表

返回 JSON:
{{
    "supplements": [
        {{"index": N, "relevance": 8, "category": "foundational|cutting_edge|methodological|reviewer_relevant", "reason": "推荐理由"}}
    ]
}}

只选 relevance ≥ 7 的论文。如果没有值得加入的论文，返回 {{"supplements": []}}
不要 markdown 代码块。"""

        resp = self._chat(prompt)
        result = self._parse_json(resp)

        supplements = result.get("supplements", [])
        added = 0
        for item in supplements:
            idx = item.get("index", -1)
            cat = item.get("category", "")
            reason = item.get("reason", "")
            relevance = item.get("relevance", 0)

            if relevance < 7:
                continue  # 相关性不足，跳过
            if 0 <= idx < len(new_papers) and cat in ranked:
                paper = new_papers[idx].copy()
                paper["reason"] = reason
                paper["category"] = cat
                paper["supplemented"] = True
                ranked[cat].append(paper)
                added += 1
                if verbose:
                    print(f"   ➕ [{cat}] {paper.get('title', '?')[:60]}")

        if verbose and added == 0:
            print(f"   补充候选中没有值得加入的论文")

        return ranked

    # ============================================================
    # Step 4: Critic
    # ============================================================

    def _critic(self, ranked, verbose=False):
        stats = {"total": 0, "verified": 0, "failed": 0, "no_doi": 0}
        verified_ranked = {}

        for category, papers in ranked.items():
            if not isinstance(papers, list):
                continue
            verified_papers = []

            for paper in papers:
                stats["total"] += 1
                doi = paper.get("doi", "")
                source = paper.get("source", "")

                # CrossRef 来源: 天然可信
                if source == "crossref":
                    paper["verified"] = True
                    paper["verify_method"] = "crossref_source"
                    stats["verified"] += 1
                    verified_papers.append(paper)
                    if verbose:
                        print(f"   ✅ [CrossRef源] {paper['title'][:50]}...")
                    continue

                # Qdrant + doi_verified=True + 有DOI
                if paper.get("doi_verified", False) and doi:
                    paper["verified"] = True
                    paper["verify_method"] = "qdrant_doi_verified"
                    stats["verified"] += 1
                    verified_papers.append(paper)
                    if verbose:
                        print(f"   ✅ [Qdrant验证] {paper['title'][:50]}...")
                    continue

                # 有 DOI 但未验证 → CrossRef 确认
                if doi:
                    cr_result = self.crossref.verify_doi(doi)
                    if cr_result["valid"]:
                        paper["verified"] = True
                        paper["verify_method"] = "crossref_doi_check"
                        # 用 CrossRef 数据补全缺失字段
                        cr_data = cr_result.get("crossref_data", {})
                        if cr_data:
                            self._enrich_from_crossref(paper, cr_data)
                        stats["verified"] += 1
                        verified_papers.append(paper)
                        if verbose:
                            print(f"   ✅ [DOI验证] {paper['title'][:50]}...")
                    else:
                        paper["verified"] = False
                        stats["failed"] += 1
                        if verbose:
                            print(f"   ❌ [DOI无效] {paper['title'][:50]}...")
                    continue

                # 无 DOI → 标题搜索
                stats["no_doi"] += 1
                title = paper.get("title", "")
                if title:
                    cr_search = self.crossref.search(title, rows=3)
                    matched = self._title_match(title, cr_search)
                    if matched:
                        paper["verified"] = True
                        paper["verify_method"] = "crossref_title_match"
                        paper["doi"] = matched.get("doi", "")
                        self._enrich_from_crossref(paper, matched)
                        stats["verified"] += 1
                        verified_papers.append(paper)
                        if verbose:
                            print(f"   ✅ [标题匹配] {paper['title'][:50]}...")
                    else:
                        paper["verified"] = False
                        stats["failed"] += 1
                        if verbose:
                            print(f"   ⚠️ [未找到] {paper['title'][:50]}...")

            verified_ranked[category] = verified_papers

        return verified_ranked, stats

    @staticmethod
    def _enrich_from_crossref(paper: dict, cr_data: dict):
        """用 CrossRef 数据补全缺失字段（不覆盖已有值）"""
        if not paper.get("authors") and cr_data.get("authors"):
            paper["authors"] = cr_data["authors"]
            paper["first_author"] = cr_data.get("first_author", "")
            paper["last_author"] = cr_data.get("last_author", "")
            paper["authors_count"] = cr_data.get("authors_count", 0)
        if not paper.get("journal") and cr_data.get("journal"):
            paper["journal"] = cr_data["journal"]
        if not paper.get("year") and cr_data.get("year"):
            paper["year"] = cr_data["year"]
        if not paper.get("cited_by") and cr_data.get("cited_by"):
            paper["cited_by"] = cr_data["cited_by"]
        if not paper.get("abstract") and cr_data.get("abstract"):
            paper["abstract"] = cr_data["abstract"]

    @staticmethod
    def _title_match(title, cr_results, threshold=0.85):
        title_lower = title.lower().strip()
        for cr in cr_results:
            cr_title = cr.get("title", "").lower().strip()
            if not cr_title:
                continue
            words1 = set(title_lower.split())
            words2 = set(cr_title.split())
            if not words1 or not words2:
                continue
            overlap = len(words1 & words2) / max(len(words1), len(words2))
            if overlap >= threshold:
                return cr
        return None

    # ============================================================
    # LLM
    # ============================================================

    def _chat(self, prompt, temperature=0.3):
        response = self.llm.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "你是地球科学领域的文献检索专家。严格按 JSON 格式返回，不要 markdown 代码块。"},
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
