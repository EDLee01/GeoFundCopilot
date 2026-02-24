"""
引用格式化
GB/T 7714 / BibTeX / APA / 行内引用 / 论文卡片
"""

from __future__ import annotations


class CitationFormatter:

    # ── 行内引用 ──

    @staticmethod
    def inline(paper: dict) -> str:
        year = paper.get("year", 0) or "n.d."
        authors = paper.get("authors", [])
        first = paper.get("first_author", "")
        if not first and authors:
            first = authors[0]
        if not first:
            title = paper.get("title", "Unknown")
            first = title.split()[0] if title else "Unknown"

        surname = first.split()[-1] if first else "Unknown"
        n = len(authors) if authors else paper.get("authors_count", 1) or 1

        if n == 1:
            return f"[{surname}, {year}]"
        elif n == 2:
            second = authors[1] if len(authors) > 1 else ""
            surname2 = second.split()[-1] if second else ""
            if surname2:
                return f"[{surname} and {surname2}, {year}]"
            return f"[{surname} et al., {year}]"
        else:
            return f"[{surname} et al., {year}]"

    # ── GB/T 7714-2015 ──

    @staticmethod
    def gbt7714(paper: dict) -> str:
        authors = paper.get("authors", [])
        year = paper.get("year", 0) or ""
        title = paper.get("title", "Untitled")
        journal = paper.get("journal", "")
        doi = paper.get("doi", "")

        author_str = CitationFormatter._format_authors_gbt(authors)

        parts = []
        if author_str:
            parts.append(author_str)
        parts.append(f" {title}[J].")
        if journal:
            parts.append(f" {journal}")
        if year:
            parts.append(f", {year}")
        parts.append(".")
        if doi:
            parts.append(f" {doi}.")
        return "".join(parts)

    @staticmethod
    def _format_authors_gbt(authors, max_authors=3):
        if not authors:
            return ""
        formatted = [CitationFormatter._name_to_gbt(a) for a in authors[:max_authors]]
        result = ", ".join(formatted)
        if len(authors) > max_authors:
            result += ", et al"
        return result + "."

    @staticmethod
    def _name_to_gbt(full_name):
        if not full_name:
            return ""
        if any("\u4e00" <= ch <= "\u9fff" for ch in full_name):
            return full_name
        parts = full_name.replace(".", "").split()
        if len(parts) == 1:
            return parts[0]
        surname = parts[-1]
        initials = " ".join(p[0].upper() for p in parts[:-1])
        return f"{surname} {initials}"

    # ── BibTeX ──

    @staticmethod
    def bibtex(paper: dict) -> str:
        authors = paper.get("authors", [])
        title = paper.get("title", "Untitled")
        journal = paper.get("journal", "")
        year = paper.get("year", 0) or ""
        doi = paper.get("doi", "")
        paper_id = paper.get("id", paper.get("openalex_id", "unknown"))

        first = paper.get("first_author", "")
        if not first and authors:
            first = authors[0]
        surname = first.split()[-1].lower() if first else "unknown"
        key = f"{surname}{year}_{paper_id}"

        author_str = " and ".join(
            CitationFormatter._name_to_bibtex(a) for a in authors
        ) if authors else ""

        lines = [f"@article{{{key},"]
        if author_str:
            lines.append(f"  author = {{{author_str}}},")
        lines.append(f"  title = {{{title}}},")
        if journal:
            lines.append(f"  journal = {{{journal}}},")
        if year:
            lines.append(f"  year = {{{year}}},")
        if doi:
            clean_doi = doi.replace("https://doi.org/", "")
            lines.append(f"  doi = {{{clean_doi}}},")
        lines.append("}")
        return "\n".join(lines)

    @staticmethod
    def _name_to_bibtex(full_name):
        parts = full_name.split()
        if len(parts) <= 1:
            return full_name
        return f"{parts[-1]}, {' '.join(parts[:-1])}"

    # ── APA 7th ──

    @staticmethod
    def apa(paper: dict) -> str:
        authors = paper.get("authors", [])
        title = paper.get("title", "Untitled")
        journal = paper.get("journal", "")
        year = paper.get("year", 0) or "n.d."
        doi = paper.get("doi", "")

        author_str = CitationFormatter._format_authors_apa(authors)

        parts = []
        if author_str:
            parts.append(author_str)
        parts.append(f" ({year}).")
        parts.append(f" {title}.")
        if journal:
            parts.append(f" *{journal}*.")
        if doi:
            parts.append(f" {doi}")
        return "".join(parts)

    @staticmethod
    def _format_authors_apa(authors, max_authors=20):
        if not authors:
            return ""
        formatted = []
        for name in authors[:max_authors]:
            parts = name.split()
            if len(parts) <= 1:
                formatted.append(name)
            else:
                surname = parts[-1]
                initials = " ".join(f"{p[0]}." for p in parts[:-1])
                formatted.append(f"{surname}, {initials}")
        if len(formatted) == 1:
            return formatted[0]
        elif len(formatted) == 2:
            return f"{formatted[0]}, & {formatted[1]}"
        return ", ".join(formatted[:-1]) + f", & {formatted[-1]}"

    # ── 批量 ──

    def format_list(self, papers, style="gbt7714"):
        fn = {"gbt7714": self.gbt7714, "bibtex": self.bibtex, "apa": self.apa}.get(style, self.gbt7714)
        lines = []
        for i, paper in enumerate(papers, 1):
            if style == "bibtex":
                lines.append(fn(paper))
                lines.append("")
            else:
                lines.append(f"[{i}] {fn(paper)}")
        return "\n".join(lines)

    # ── 论文卡片 ──

    @staticmethod
    def paper_card(paper: dict) -> str:
        title = paper.get("title", "Untitled")
        authors = paper.get("authors", [])
        first = paper.get("first_author", authors[0] if authors else "Unknown")
        n = paper.get("authors_count", len(authors))
        journal = paper.get("journal", "")
        year = paper.get("year", 0)
        cited = paper.get("cited_by", 0)
        jcr = paper.get("jcr_zone", "")
        cas = paper.get("cas_zone", 0)
        topic = paper.get("primary_topic", "")
        doi = paper.get("doi", "")
        concepts = paper.get("concepts", [])

        lines = [f"📄 {title}"]

        if n > 2:
            lines.append(f"👤 {first} et al. ({n} authors)")
        elif authors:
            lines.append(f"👤 {', '.join(authors)}")

        meta = []
        if journal:
            meta.append(journal)
        if year:
            meta.append(str(year))
        meta.append(f"Cited: {cited}")
        lines.append(f"📖 {' | '.join(meta)}")

        tags = []
        if jcr:
            tags.append(jcr)
        if cas:
            cas_label = {1: "一区", 2: "二区", 3: "三区", 4: "四区"}.get(cas, "")
            if cas_label:
                tags.append(f"中科院{cas_label}")
        if topic:
            tags.append(topic)
        if tags:
            lines.append(f"🏷️ {' | '.join(tags)}")

        if concepts:
            lines.append(f"💡 {', '.join(concepts[:5])}")
        if doi:
            lines.append(f"🔗 {doi}")

        return "\n".join(lines)
