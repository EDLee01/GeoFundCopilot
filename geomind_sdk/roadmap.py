"""
技术路线图生成
LLM 生成结构化路线 → SVG 渲染
"""

from __future__ import annotations

import json
import textwrap
from openai import OpenAI
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from geomind_sdk.search import SearchEngine


class RoadmapGenerator:

    # 阶段配色方案（最多 6 个阶段）
    PHASE_COLORS = [
        ("#3B82F6", "#DBEAFE"),  # 蓝
        ("#10B981", "#D1FAE5"),  # 绿
        ("#F59E0B", "#FEF3C7"),  # 橙
        ("#8B5CF6", "#EDE9FE"),  # 紫
        ("#EF4444", "#FEE2E2"),  # 红
        ("#06B6D4", "#CFFAFE"),  # 青
    ]

    def __init__(
        self,
        engine: SearchEngine,
        deepseek_api_key: str,
        deepseek_base_url: str = "https://api.deepseek.com",
        deepseek_model: str = "deepseek-chat",
    ):
        self.engine = engine
        self.model = deepseek_model
        self.llm = OpenAI(api_key=deepseek_api_key, base_url=deepseek_base_url)

    def generate(
        self,
        research_direction: str,
        innovation_points: str = "",
        num_phases: int = 5,
        verbose: bool = True,
        on_progress=None,
    ) -> dict:
        """生成技术路线图数据 + SVG"""

        def _progress(step, total, msg):
            if on_progress:
                on_progress(step, total, msg)

        # Step 1: 检索相关论文了解方法链
        _progress(1, 3, "🔍 检索相关论文，分析方法链...")
        if verbose:
            print(f"\n🔍 [检索] 分析该方向常见方法链...")
        papers = self.engine.search(research_direction, top_k=20)
        if verbose:
            print(f"   找到 {len(papers)} 篇参考论文")

        # Step 2: LLM 生成结构化路线图
        _progress(2, 3, "🧠 LLM 规划技术路线图结构...")
        if verbose:
            print(f"\n🧠 [规划] 生成技术路线图...")
        roadmap_data = self._plan_roadmap(research_direction, innovation_points, papers, num_phases)
        if verbose:
            phases = roadmap_data.get("phases", [])
            print(f"   生成 {len(phases)} 个阶段")

        # Step 3: 渲染 SVG
        _progress(3, 3, "🎨 渲染 SVG 技术路线图...")
        if verbose:
            print(f"\n🎨 [渲染] 生成 SVG...")
        svg = self.render_svg(roadmap_data)
        roadmap_data["svg"] = svg

        return roadmap_data

    def _plan_roadmap(self, direction, innovation, papers, num_phases):
        paper_summaries = []
        for p in papers[:10]:
            paper_summaries.append(
                f"- {p.get('title', '?')[:80]} ({p.get('year', '?')}, {p.get('journal', '?')})"
            )
        papers_text = "\n".join(paper_summaries) if paper_summaries else "（无参考论文）"

        innovation_section = ""
        if innovation:
            innovation_section = f"\n申请人创新点:\n{innovation}\n"

        prompt = f"""你是地球科学研究方案设计专家。根据研究方向，设计一个完整的技术路线图。

研究方向: "{direction}"
{innovation_section}
参考论文（供了解该领域常见方法）:
{papers_text}

请设计 {num_phases} 个阶段的技术路线图。

返回 JSON（不要 markdown 代码块）:
{{
    "title": "技术路线图标题（中文，简短）",
    "subtitle": "一句话描述研究目标",
    "phases": [
        {{
            "id": 1,
            "name": "阶段名称（如：数据获取与预处理）",
            "duration": "时间（如：第1-6个月）",
            "tasks": ["具体任务1", "具体任务2", "具体任务3"],
            "methods": ["使用的方法/工具"],
            "output": "该阶段预期产出"
        }}
    ],
    "key_innovations": ["在路线图中体现的创新点（1-3个）"],
    "expected_results": ["最终预期成果（2-4条）"]
}}

要求:
- 每个阶段 2-4 个 tasks，每个 task 不超过 20 字
- methods 是该阶段用到的核心方法/工具，1-3 个，每个不超过 15 字
- output 不超过 25 字
- 阶段之间有明确的逻辑递进关系
- name 不超过 15 字
- 路线图要体现研究的科学性和系统性
- 适合放在国自然申请书中"""

        resp = self._chat(prompt)
        data = self._parse_json(resp)
        data["research_direction"] = direction
        return data

    def render_svg(self, data: dict) -> str:
        """将结构化数据渲染为 SVG 技术路线图"""
        phases = data.get("phases", [])
        if not phases:
            return "<svg></svg>"

        title = data.get("title", "技术路线图")
        subtitle = data.get("subtitle", "")
        expected = data.get("expected_results", [])
        innovations = data.get("key_innovations", [])

        n = len(phases)

        # ── 布局参数 ──
        margin_x = 40
        margin_top = 30
        phase_w = 260
        phase_gap = 60
        arrow_len = phase_gap
        title_h = 70
        subtitle_h = 25 if subtitle else 0
        innovation_h = 50 if innovations else 0
        result_h = 80 if expected else 0

        # 计算每个 phase 的高度
        phase_heights = []
        for p in phases:
            tasks = p.get("tasks", [])
            methods = p.get("methods", [])
            # header(40) + duration(20) + tasks(22*n) + gap(10) + methods_header(20) + methods(20*n) + output(25) + padding(20)
            h = 40 + 20 + len(tasks) * 22 + 10 + 20 + len(methods) * 20 + 30 + 20
            phase_heights.append(max(h, 180))

        max_phase_h = max(phase_heights)
        # 统一高度
        phase_heights = [max_phase_h] * n

        total_w = margin_x * 2 + n * phase_w + (n - 1) * phase_gap
        total_h = margin_top + title_h + subtitle_h + innovation_h + max_phase_h + result_h + 60

        parts = []
        parts.append(f'<svg xmlns="http://www.w3.org/2000/svg" '
                     f'viewBox="0 0 {total_w} {total_h}" '
                     f'width="{total_w}" height="{total_h}" '
                     f'style="font-family: \'Microsoft YaHei\', \'PingFang SC\', \'Noto Sans CJK SC\', sans-serif;">')

        # 背景
        parts.append(f'<rect width="{total_w}" height="{total_h}" fill="#FAFBFC" rx="12"/>')

        # ── 标题 ──
        ty = margin_top + 28
        parts.append(f'<text x="{total_w/2}" y="{ty}" text-anchor="middle" '
                     f'font-size="20" font-weight="bold" fill="#1E293B">{_esc(title)}</text>')

        if subtitle:
            ty += 26
            parts.append(f'<text x="{total_w/2}" y="{ty}" text-anchor="middle" '
                         f'font-size="13" fill="#64748B">{_esc(subtitle)}</text>')

        # ── 创新点标注 ──
        content_top = margin_top + title_h + subtitle_h
        if innovations:
            iy = content_top + 18
            inno_text = "  |  ".join(innovations[:3])
            # 背景条
            bar_w = min(total_w - 80, len(inno_text) * 14 + 80)
            bar_x = (total_w - bar_w) / 2
            parts.append(f'<rect x="{bar_x}" y="{iy - 16}" width="{bar_w}" height="28" '
                         f'fill="#FEF3C7" rx="14" stroke="#F59E0B" stroke-width="1"/>')
            parts.append(f'<text x="{total_w/2}" y="{iy + 2}" text-anchor="middle" '
                         f'font-size="11" fill="#92400E">★ {_esc(inno_text)}</text>')
            content_top += innovation_h

        # ── 阶段框 ──
        phase_top = content_top + 15
        for i, phase in enumerate(phases):
            x = margin_x + i * (phase_w + phase_gap)
            y = phase_top
            h = phase_heights[i]
            border_color, bg_color = self.PHASE_COLORS[i % len(self.PHASE_COLORS)]

            # 阴影
            parts.append(f'<rect x="{x+3}" y="{y+3}" width="{phase_w}" height="{h}" '
                         f'fill="#E2E8F0" rx="10" opacity="0.5"/>')
            # 主框
            parts.append(f'<rect x="{x}" y="{y}" width="{phase_w}" height="{h}" '
                         f'fill="white" rx="10" stroke="{border_color}" stroke-width="2"/>')
            # 标题栏
            parts.append(f'<rect x="{x}" y="{y}" width="{phase_w}" height="38" '
                         f'fill="{border_color}" rx="10"/>')
            parts.append(f'<rect x="{x}" y="{y+28}" width="{phase_w}" height="10" '
                         f'fill="{border_color}"/>')

            # 阶段编号 + 名称
            name = phase.get("name", f"阶段 {i+1}")
            parts.append(f'<text x="{x + phase_w/2}" y="{y + 25}" text-anchor="middle" '
                         f'font-size="13" font-weight="bold" fill="white">'
                         f'Phase {i+1}: {_esc(name)}</text>')

            # 时间
            cy = y + 55
            duration = phase.get("duration", "")
            if duration:
                parts.append(f'<text x="{x + phase_w/2}" y="{cy}" text-anchor="middle" '
                             f'font-size="10" fill="#94A3B8">⏱ {_esc(duration)}</text>')
                cy += 18

            # 任务列表
            tasks = phase.get("tasks", [])
            for t_text in tasks:
                parts.append(f'<text x="{x + 20}" y="{cy}" font-size="11" fill="#334155">'
                             f'• {_esc(t_text[:28])}</text>')
                cy += 22

            # 方法/工具
            methods = phase.get("methods", [])
            if methods:
                cy += 8
                parts.append(f'<text x="{x + 15}" y="{cy}" font-size="10" '
                             f'font-weight="bold" fill="{border_color}">方法/工具:</text>')
                cy += 18
                for m in methods:
                    parts.append(f'<rect x="{x + 15}" y="{cy - 12}" width="{len(m) * 12 + 16}" '
                                 f'height="18" fill="{bg_color}" rx="9"/>')
                    parts.append(f'<text x="{x + 23}" y="{cy}" font-size="10" '
                                 f'fill="{border_color}">{_esc(m[:20])}</text>')
                    cy += 20

            # 产出
            output = phase.get("output", "")
            if output:
                cy = y + h - 25
                parts.append(f'<line x1="{x + 15}" y1="{cy - 8}" x2="{x + phase_w - 15}" y2="{cy - 8}" '
                             f'stroke="#E2E8F0" stroke-width="1"/>')
                parts.append(f'<text x="{x + phase_w/2}" y="{cy + 10}" text-anchor="middle" '
                             f'font-size="10" fill="#64748B">→ {_esc(output[:30])}</text>')

            # ── 阶段间箭头 ──
            if i < n - 1:
                ax1 = x + phase_w
                ax2 = ax1 + arrow_len
                ay = y + h / 2
                parts.append(f'<line x1="{ax1}" y1="{ay}" x2="{ax2 - 8}" y2="{ay}" '
                             f'stroke="#94A3B8" stroke-width="2" stroke-dasharray="6,3"/>')
                # 箭头头部
                parts.append(f'<polygon points="{ax2 - 8},{ay - 5} {ax2},{ay} {ax2 - 8},{ay + 5}" '
                             f'fill="#94A3B8"/>')

        # ── 预期成果 ──
        if expected:
            ry = phase_top + max_phase_h + 30
            result_w = total_w - margin_x * 2
            parts.append(f'<rect x="{margin_x}" y="{ry}" width="{result_w}" height="50" '
                         f'fill="#F0FDF4" rx="10" stroke="#22C55E" stroke-width="1.5"/>')
            parts.append(f'<text x="{margin_x + 20}" y="{ry + 20}" '
                         f'font-size="12" font-weight="bold" fill="#166534">预期成果</text>')
            results_text = "  |  ".join(expected[:4])
            parts.append(f'<text x="{margin_x + 20}" y="{ry + 38}" '
                         f'font-size="11" fill="#15803D">{_esc(results_text)}</text>')

        parts.append('</svg>')
        return "\n".join(parts)

    def _chat(self, prompt, temperature=0.3):
        response = self.llm.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "你是地球科学研究方案设计专家。严格按 JSON 格式返回。"},
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


def _esc(text: str) -> str:
    """XML 转义"""
    return (text
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&#39;"))
