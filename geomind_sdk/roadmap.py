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
- 每个阶段 2-4 个 tasks，每个 task 不超过 30 字
- methods 是该阶段用到的核心方法/工具，1-3 个，每个不超过 18 字
- output 不超过 35 字
- 阶段之间有明确的逻辑递进关系
- name 不超过 18 字
- 路线图要体现研究的科学性和系统性
- 适合放在国自然申请书中"""

        resp = self._chat(prompt)
        data = self._parse_json(resp)
        data["research_direction"] = direction
        return data

    def render_svg(self, data: dict) -> str:
        """将结构化数据渲染为高质量 SVG 技术路线图（竖版流程图）"""
        phases = data.get("phases", [])
        if not phases:
            return "<svg></svg>"

        title = data.get("title", "技术路线图")
        subtitle = data.get("subtitle", "")
        expected = data.get("expected_results", [])
        innovations = data.get("key_innovations", [])
        n = len(phases)

        # ── 布局常量 ──
        W = 780                     # SVG 宽度（适合 A4）
        MX = 50                     # 左右边距
        CW = W - MX * 2            # 内容区宽 680
        HDR_H = 48                  # 阶段标题栏高度
        TASK_LH = 28               # 任务行高
        METHOD_H = 32              # 方法标签行高
        OUT_H = 38                 # 产出区高度
        PAD = 16                   # 内边距
        ARROW = 52                 # 阶段间箭头区
        LEFT_W = int(CW * 0.58)   # 左列（任务）宽度
        RIGHT_X = MX + LEFT_W     # 右列（方法）起点

        # ── 计算每个阶段高度 ──
        ph_data = []
        for p in phases:
            tasks = p.get("tasks", [])
            methods = p.get("methods", [])
            task_h = PAD + 20 + len(tasks) * TASK_LH + PAD
            meth_h = PAD + 20 + len(methods) * METHOD_H + PAD
            body_h = max(task_h, meth_h, 90)
            h = HDR_H + body_h + (OUT_H if p.get("output") else 0)
            ph_data.append({"p": p, "h": h, "body_h": body_h})

        # ── 计算总高 ──
        title_h = 54 + (26 if subtitle else 0)
        inno_h = 56 if innovations else 0
        phases_h = sum(d["h"] for d in ph_data) + max(0, n - 1) * ARROW
        exp_rows = (len(expected) + 1) // 2 if expected else 0
        result_h = (40 + exp_rows * 28 + 20) if expected else 0
        H = 32 + title_h + inno_h + 16 + phases_h + 24 + result_h + 32

        s = []  # SVG 行

        # ── SVG 根元素 ──
        s.append(
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" '
            f'width="{W}" height="{H}" '
            f'style="font-family:\'Microsoft YaHei\',\'PingFang SC\','
            f'\'Noto Sans CJK SC\',sans-serif;">'
        )

        # ── defs: 阴影 / 渐变 / 箭头 ──
        s.append('<defs>')
        s.append(
            '<filter id="sh" x="-3%" y="-2%" width="106%" height="110%">'
            '<feDropShadow dx="0" dy="3" stdDeviation="5" '
            'flood-color="#94A3B8" flood-opacity="0.22"/></filter>'
        )
        s.append(
            '<filter id="shL" x="-2%" y="-2%" width="104%" height="108%">'
            '<feDropShadow dx="0" dy="2" stdDeviation="3" '
            'flood-color="#CBD5E1" flood-opacity="0.3"/></filter>'
        )
        s.append(
            '<marker id="arr" markerWidth="12" markerHeight="9" '
            'refX="12" refY="4.5" orient="auto">'
            '<polygon points="0 0,12 4.5,0 9" fill="#94A3B8"/></marker>'
        )
        for i, (pri, _) in enumerate(self.PHASE_COLORS):
            s.append(
                f'<linearGradient id="g{i}" x1="0%" y1="0%" x2="100%" y2="0%">'
                f'<stop offset="0%" stop-color="{pri}"/>'
                f'<stop offset="100%" stop-color="{pri}" stop-opacity="0.75"/>'
                f'</linearGradient>'
            )
        s.append('</defs>')

        # ── 背景 ──
        s.append(f'<rect width="{W}" height="{H}" fill="#F8FAFC" rx="16"/>')
        s.append(f'<rect width="{W}" height="{H}" fill="none" rx="16" '
                 f'stroke="#E2E8F0" stroke-width="1"/>')

        y = 32

        # ── 标题 ──
        s.append(f'<text x="{W / 2}" y="{y + 34}" text-anchor="middle" '
                 f'font-size="22" font-weight="bold" fill="#0F172A">'
                 f'{_esc(title)}</text>')
        y += 44
        if subtitle:
            s.append(f'<text x="{W / 2}" y="{y + 10}" text-anchor="middle" '
                     f'font-size="13" fill="#64748B">{_esc(subtitle)}</text>')
            y += 26
        y += 10

        # ── 创新亮点条 ──
        if innovations:
            s.append(f'<rect x="{MX}" y="{y}" width="{CW}" height="42" '
                     f'fill="#FFFBEB" rx="8" stroke="#FCD34D" stroke-width="1"/>')
            ix = MX + 18
            for inno in innovations[:3]:
                t = f"★ {inno}"
                s.append(f'<text x="{ix}" y="{y + 27}" font-size="12.5" '
                         f'fill="#92400E">{_esc(t)}</text>')
                ix += _text_w(t, 12.5) + 28
            y += 56

        y += 16

        # ── 阶段框（竖向排列）──
        for i, d in enumerate(ph_data):
            phase = d["p"]
            ph = d["h"]
            body_h = d["body_h"]
            pri, light = self.PHASE_COLORS[i % len(self.PHASE_COLORS)]

            # 白色主框 + 阴影
            s.append(f'<rect x="{MX}" y="{y}" width="{CW}" height="{ph}" '
                     f'fill="white" rx="10" filter="url(#sh)"/>')

            # 渐变色标题栏（圆角顶部 + 方角底部）
            s.append(f'<rect x="{MX}" y="{y}" width="{CW}" height="{HDR_H}" '
                     f'fill="url(#g{i % len(self.PHASE_COLORS)})" rx="10"/>')
            s.append(f'<rect x="{MX}" y="{y + HDR_H - 10}" width="{CW}" '
                     f'height="10" fill="url(#g{i % len(self.PHASE_COLORS)})"/>')

            # 左侧彩色标识条
            s.append(f'<rect x="{MX}" y="{y + HDR_H}" width="5" '
                     f'height="{ph - HDR_H}" fill="{pri}"/>')
            # 修补左下角圆角
            s.append(f'<rect x="{MX}" y="{y + ph - 10}" width="10" '
                     f'height="10" fill="white"/>')
            s.append(f'<rect x="{MX}" y="{y + ph - 10}" width="5" '
                     f'height="10" fill="{pri}"/>')
            # 描边覆盖（整体圆角边框）
            s.append(f'<rect x="{MX}" y="{y}" width="{CW}" height="{ph}" '
                     f'fill="none" rx="10" stroke="#E2E8F0" stroke-width="0.5"/>')

            # 编号圆
            cx_c = MX + 30
            cy_c = y + HDR_H / 2
            s.append(f'<circle cx="{cx_c}" cy="{cy_c}" r="16" '
                     f'fill="rgba(255,255,255,0.25)"/>')
            s.append(f'<text x="{cx_c}" y="{cy_c + 6}" text-anchor="middle" '
                     f'font-size="16" font-weight="bold" fill="white">{i + 1}</text>')

            # 阶段名称
            name = phase.get("name", f"阶段{i + 1}")
            s.append(f'<text x="{cx_c + 26}" y="{cy_c + 6}" font-size="16" '
                     f'font-weight="bold" fill="white">{_esc(name)}</text>')

            # 时间标签
            dur = phase.get("duration", "")
            if dur:
                dur_t = f"⏱ {dur}"
                dtw = _text_w(dur_t, 11) + 24
                dx = MX + CW - dtw - 16
                s.append(f'<rect x="{dx}" y="{cy_c - 13}" width="{dtw}" '
                         f'height="26" fill="rgba(255,255,255,0.22)" rx="13"/>')
                s.append(f'<text x="{dx + 12}" y="{cy_c + 4}" font-size="11" '
                         f'fill="white">{_esc(dur_t)}</text>')

            # ── 任务列（左 60%）──
            ty = y + HDR_H + PAD
            s.append(f'<text x="{MX + 24}" y="{ty + 14}" font-size="11.5" '
                     f'font-weight="bold" fill="{pri}">主要任务</text>')
            ty += 24
            for task_text in phase.get("tasks", []):
                s.append(f'<text x="{MX + 36}" y="{ty + 4}" font-size="13" '
                         f'fill="#334155">▸ {_esc(task_text[:35])}</text>')
                ty += TASK_LH

            # ── 方法列（右 42%）──
            methods = phase.get("methods", [])
            if methods:
                my = y + HDR_H + PAD
                s.append(f'<text x="{RIGHT_X + 18}" y="{my + 14}" font-size="11.5" '
                         f'font-weight="bold" fill="{pri}">方法 / 工具</text>')
                my += 26
                for m in methods:
                    mt = m[:20]
                    mtw = _text_w(mt, 12) + 28
                    s.append(
                        f'<rect x="{RIGHT_X + 16}" y="{my - 4}" width="{mtw}" '
                        f'height="26" fill="{light}" rx="13" '
                        f'stroke="{pri}" stroke-width="0.7" stroke-opacity="0.5"/>'
                    )
                    s.append(f'<text x="{RIGHT_X + 30}" y="{my + 12}" font-size="12" '
                             f'fill="{pri}">{_esc(mt)}</text>')
                    my += METHOD_H

            # 列间虚线
            sep_x = RIGHT_X - 8
            s.append(f'<line x1="{sep_x}" y1="{y + HDR_H + 10}" '
                     f'x2="{sep_x}" y2="{y + HDR_H + body_h - 10}" '
                     f'stroke="#E2E8F0" stroke-width="1" stroke-dasharray="3,3"/>')

            # ── 产出 ──
            output = phase.get("output", "")
            if output:
                oy = y + HDR_H + body_h
                s.append(f'<line x1="{MX + 20}" y1="{oy + 4}" '
                         f'x2="{MX + CW - 20}" y2="{oy + 4}" '
                         f'stroke="#E2E8F0" stroke-width="1"/>')
                s.append(f'<text x="{MX + 28}" y="{oy + 26}" font-size="12" '
                         f'fill="#64748B">📎 产出: {_esc(output[:45])}</text>')

            y += ph

            # ── 阶段间箭头 ──
            if i < n - 1:
                amid = W / 2
                ay1 = y + 8
                ay2 = y + ARROW - 10
                s.append(f'<line x1="{amid}" y1="{ay1}" x2="{amid}" y2="{ay2}" '
                         f'stroke="#94A3B8" stroke-width="2.5" '
                         f'marker-end="url(#arr)"/>')
                y += ARROW

        # ── 预期成果 ──
        if expected:
            y += 24
            rh = 40 + exp_rows * 28 + 20
            s.append(f'<rect x="{MX}" y="{y}" width="{CW}" height="{rh}" '
                     f'fill="#F0FDF4" rx="10" stroke="#86EFAC" '
                     f'stroke-width="1.5" filter="url(#shL)"/>')
            s.append(f'<text x="{MX + 22}" y="{y + 28}" font-size="14" '
                     f'font-weight="bold" fill="#166534">🎯 预期成果</text>')
            col_w = CW / 2
            for j, exp_text in enumerate(expected[:6]):
                col = j % 2
                row = j // 2
                ex = MX + 30 + col * col_w
                ey = y + 56 + row * 28
                s.append(f'<text x="{ex}" y="{ey}" font-size="12.5" '
                         f'fill="#15803D">✓ {_esc(exp_text[:38])}</text>')

        s.append('</svg>')
        return "\n".join(s)

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


def _text_w(text: str, font_size: float = 12) -> float:
    """估算文本像素宽度（CJK ≈ 字号, Latin ≈ 字号×0.6）"""
    return sum(font_size if ord(c) > 0x7F else font_size * 0.6 for c in text)
