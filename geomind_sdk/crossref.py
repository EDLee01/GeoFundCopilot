"""
CrossRef API 客户端
Polite Pool: edwardlee5423@gmail.com
"""

from __future__ import annotations

import re
import time
import requests
from typing import Optional


def strip_html(text: str) -> str:
    if not text:
        return ""
    return re.sub(r"<[^>]+>", "", text).strip()


class CrossRefClient:

    BASE_URL = "https://api.crossref.org"
    EMAIL = "edwardlee5423@gmail.com"

    def __init__(self, email: str = None):
        self.email = email or self.EMAIL
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": f"GeoFundCopilot/1.0 (mailto:{self.email})",
        })
        self._last_request_time = 0

    def _polite_wait(self):
        elapsed = time.time() - self._last_request_time
        if elapsed < 0.5:
            time.sleep(0.5 - elapsed)
        self._last_request_time = time.time()

    def search(
        self,
        query: str,
        rows: int = 20,
        sort: str = "relevance",
        year_from: int = None,
        year_to: int = None,
    ) -> list[dict]:
        self._polite_wait()

        params = {
            "query": query,
            "rows": rows,
            "sort": sort,
            "select": "DOI,title,author,container-title,published,is-referenced-by-count,abstract,subject",
            "mailto": self.email,
        }

        if year_from or year_to:
            filters = []
            if year_from:
                filters.append(f"from-pub-date:{year_from}")
            if year_to:
                filters.append(f"until-pub-date:{year_to}")
            params["filter"] = ",".join(filters)

        try:
            resp = self.session.get(f"{self.BASE_URL}/works", params=params, timeout=30)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            print(f"   ⚠️ CrossRef 请求失败: {e}")
            return []

        items = data.get("message", {}).get("items", [])
        return [self._format_item(item) for item in items]

    def get_by_doi(self, doi: str) -> Optional[dict]:
        self._polite_wait()
        doi = self._clean_doi(doi)
        if not doi:
            return None
        try:
            resp = self.session.get(
                f"{self.BASE_URL}/works/{doi}",
                params={"mailto": self.email}, timeout=15,
            )
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            item = resp.json().get("message", {})
            return self._format_item(item)
        except Exception:
            return None

    def verify_doi(self, doi: str) -> dict:
        doi = self._clean_doi(doi)
        if not doi:
            return {"valid": False, "crossref_data": None, "match_details": {"doi_exists": False}}

        paper = self.get_by_doi(doi)
        if paper:
            return {
                "valid": True,
                "crossref_data": paper,
                "match_details": {
                    "doi_exists": True,
                    "title_from_crossref": paper.get("title", ""),
                    "year_from_crossref": paper.get("year", 0),
                    "journal_from_crossref": paper.get("journal", ""),
                },
            }
        return {"valid": False, "crossref_data": None, "match_details": {"doi_exists": False}}

    @staticmethod
    def _clean_doi(doi: str) -> str:
        if not doi:
            return ""
        doi = doi.strip()
        for prefix in ["https://doi.org/", "http://doi.org/", "doi:"]:
            if doi.lower().startswith(prefix):
                doi = doi[len(prefix):]
        if "#" in doi:
            doi = doi.split("#")[0]
        return doi

    @staticmethod
    def _format_item(item: dict) -> dict:
        titles = item.get("title", [])
        title = strip_html(titles[0] if titles else "")

        authors_raw = item.get("author", [])
        authors = []
        first_author = ""
        last_author = ""
        for i, a in enumerate(authors_raw):
            given = a.get("given", "")
            family = a.get("family", "")
            name = f"{given} {family}".strip()
            if name:
                authors.append(name)
                if i == 0:
                    first_author = name
                if i == len(authors_raw) - 1:
                    last_author = name

        journals = item.get("container-title", [])
        journal = journals[0].upper() if journals else ""

        published = item.get("published", {})
        date_parts = published.get("date-parts", [[]])
        year = date_parts[0][0] if date_parts and date_parts[0] else 0

        doi = item.get("DOI", "")
        cited_by = item.get("is-referenced-by-count", 0)
        abstract = strip_html(item.get("abstract", ""))
        subjects = item.get("subject", [])

        return {
            "title": title,
            "doi": f"https://doi.org/{doi}" if doi else "",
            "authors": authors,
            "first_author": first_author,
            "last_author": last_author,
            "authors_count": len(authors),
            "journal": journal,
            "year": year,
            "cited_by": cited_by,
            "abstract": abstract,
            "concepts": subjects,
            "source": "crossref",
            "cas_zone": 0,
            "jcr_zone": "",
            "field": "",
            "primary_topic": "",
            "openalex_id": "",
            "referenced_works": [],
            "doi_verified": True,
        }
