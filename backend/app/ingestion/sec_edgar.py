"""Ingester per filing SEC EDGAR (form 8-K).

Gli 8-K sono "current reports" obbligatori per eventi materiali: M&A, cambi
leadership, earnings, bankruptcy, accordi definitivi, regulatory actions.
Sono fonte primaria con qualità alta (azienda comunica direttamente).

SEC richiede User-Agent identificabile (TOS) e impone rate limit di 10
richieste/secondo. Il polling default è ogni 10 minuti.
"""

from __future__ import annotations

import re
from collections.abc import AsyncIterator
from datetime import UTC, datetime

import feedparser
import httpx
from loguru import logger

from app.ingestion.base import IngestedItem, NewsIngester

SEC_EDGAR_8K_ATOM_URL = (
    "https://www.sec.gov/cgi-bin/browse-edgar"
    "?action=getcurrent&type=8-K&owner=include&count=40&output=atom"
)

# SEC TOS: User-Agent must include identifiable contact info.
SEC_USER_AGENT = "NewsFinance research andrea@newsfinance.app"

# Estrae il ticker o nome azienda dal titolo Atom (formato: "8-K - COMPANY NAME (NUMBER) (Filer)").
_COMPANY_RE = re.compile(
    r"8-K\s*[-–]\s*(.+?)\s*\(.*?\)\s*\((Filer|Reporting)\)",  # noqa: RUF001
    re.IGNORECASE,
)


class SECEdgarIngester(NewsIngester):
    source_name = "sec_edgar"
    source_quality = "primary"

    async def fetch(self) -> AsyncIterator[IngestedItem]:
        async with httpx.AsyncClient(
            timeout=20.0,
            headers={
                "User-Agent": SEC_USER_AGENT,
                "Accept-Encoding": "gzip, deflate",
                "Host": "www.sec.gov",
            },
            follow_redirects=True,
        ) as client:
            try:
                response = await client.get(SEC_EDGAR_8K_ATOM_URL)
                response.raise_for_status()
            except httpx.HTTPError as exc:
                logger.warning("sec_fetch_failed", error=str(exc))
                return

            parsed = feedparser.parse(response.content)
            if parsed.bozo and not parsed.entries:
                logger.warning("sec_parse_failed")
                return

            for entry in parsed.entries:
                title = (entry.get("title") or "").strip()
                link = (entry.get("link") or "").strip()
                if not title or not link:
                    continue

                company = self._extract_company(title)
                published = self._parse_published(entry)
                summary = (entry.get("summary") or "").strip()

                yield IngestedItem(
                    source="sec_edgar:8k",
                    source_quality=self.source_quality,
                    headline=title,
                    body=summary or None,
                    source_url=link,
                    published_at=published,
                    raw_meta={
                        "company": company,
                        "form_type": "8-K",
                        "accession": self._extract_accession(link),
                    },
                )

    @staticmethod
    def _extract_company(title: str) -> str | None:
        match = _COMPANY_RE.search(title)
        return match.group(1).strip() if match else None

    @staticmethod
    def _extract_accession(url: str) -> str | None:
        """Estrae il numero accession dal link tipo /Archives/.../000XXXX.html."""
        match = re.search(r"(\d{10}-\d{2}-\d{6})", url)
        return match.group(1) if match else None

    @staticmethod
    def _parse_published(entry) -> datetime | None:
        from time import mktime

        for key in ("published_parsed", "updated_parsed"):
            parsed = entry.get(key)
            if parsed:
                return datetime.fromtimestamp(mktime(parsed), tz=UTC)
        return None
