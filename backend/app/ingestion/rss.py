"""Ingester per RSS feed di testate finanziarie.

Sorgenti gratuite, polling ogni ~5 minuti. Le headline arrivate qui hanno
qualità "secondary" e finiscono poi nel cluster engine per dedup semantico
contro altre fonti (Polygon, Marketaux, ...).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from time import mktime

import feedparser
import httpx
from loguru import logger

from app.ingestion.base import IngestedItem, NewsIngester

RSS_FEEDS: list[tuple[str, str]] = [
    # Reuters: l'RSS ufficiale è deprecato dal 2020 → usiamo Google News come proxy.
    ("reuters_via_gnews", "https://news.google.com/rss/search?q=site:reuters.com+business&hl=en-US&gl=US&ceid=US:en"),
    ("bloomberg_via_gnews", "https://news.google.com/rss/search?q=site:bloomberg.com+markets&hl=en-US&gl=US&ceid=US:en"),
    ("ft_via_gnews", "https://news.google.com/rss/search?q=site:ft.com+companies&hl=en-US&gl=US&ceid=US:en"),
    ("cnbc_top_news", "https://www.cnbc.com/id/100003114/device/rss/rss.html"),
    ("cnbc_markets", "https://www.cnbc.com/id/15839069/device/rss/rss.html"),
    ("cnbc_business", "https://www.cnbc.com/id/10001147/device/rss/rss.html"),
    ("cnbc_earnings", "https://www.cnbc.com/id/15839135/device/rss/rss.html"),
    ("marketwatch_top", "http://feeds.marketwatch.com/marketwatch/topstories/"),
    ("marketwatch_real_time", "http://feeds.marketwatch.com/marketwatch/realtimeheadlines/"),
    ("wsj_markets", "https://feeds.a.dj.com/rss/RSSMarketsMain.xml"),
    ("yahoo_finance", "https://finance.yahoo.com/news/rssindex"),
    ("investing_news", "https://www.investing.com/rss/news_25.rss"),
    ("seekingalpha_market", "https://seekingalpha.com/market_currents.xml"),
]


class RSSIngester(NewsIngester):
    source_name = "rss"
    source_quality = "secondary"

    def __init__(self, session, feeds: list[tuple[str, str]] | None = None) -> None:
        super().__init__(session)
        self.feeds = feeds or RSS_FEEDS

    async def fetch(self) -> AsyncIterator[IngestedItem]:
        async with httpx.AsyncClient(
            timeout=15.0,
            headers={"User-Agent": "NewsFinance/0.1 (research; +https://news-finance-xi.vercel.app)"},
            follow_redirects=True,
        ) as client:
            for slug, url in self.feeds:
                try:
                    response = await client.get(url)
                    response.raise_for_status()
                except httpx.HTTPError as exc:
                    logger.warning("rss_fetch_failed", feed=slug, url=url, error=str(exc))
                    continue

                parsed = feedparser.parse(response.content)
                if parsed.bozo and not parsed.entries:
                    logger.warning("rss_parse_failed", feed=slug, url=url)
                    continue

                for entry in parsed.entries:
                    headline = (entry.get("title") or "").strip()
                    link = (entry.get("link") or "").strip()
                    if not headline or not link:
                        continue

                    published = self._parse_published(entry)
                    summary = (entry.get("summary") or entry.get("description") or "").strip()
                    body = self._strip_html(summary) if summary else None

                    yield IngestedItem(
                        source=f"rss:{slug}",
                        source_quality=self.source_quality,
                        headline=headline,
                        body=body,
                        source_url=link,
                        published_at=published,
                        raw_meta={
                            "feed": slug,
                            "tags": [t.get("term") for t in entry.get("tags", []) if t.get("term")],
                            "author": entry.get("author"),
                        },
                    )

    @staticmethod
    def _parse_published(entry) -> datetime | None:
        for key in ("published_parsed", "updated_parsed"):
            parsed = entry.get(key)
            if parsed:
                return datetime.fromtimestamp(mktime(parsed), tz=UTC)
        return None

    @staticmethod
    def _strip_html(text: str) -> str:
        """Strip leggero degli HTML tag — non serve nulla di sofisticato qui."""
        import re

        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text)
        return text.strip()
