"""Ingester Polygon News API.

Polygon aggrega news da publisher multipli (Benzinga, Zacks, MarketWatch,
SeekingAlpha, GlobeNewswire, ...) già taggate per ticker. Qualità nostra
"secondary"; in raw_meta salviamo il publisher originale per poter
distinguere fra fonti primarie (press release) e aggregatori in classifier.

Polling default: ogni 60s. Starter plan: unlimited API calls.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import datetime

import httpx
from loguru import logger

from app.core.config import get_settings
from app.ingestion.base import IngestedItem, NewsIngester

POLYGON_NEWS_URL = "https://api.polygon.io/v2/reference/news"


class PolygonNewsIngester(NewsIngester):
    source_name = "polygon_news"
    source_quality = "secondary"

    def __init__(self, session, limit: int = 100) -> None:
        super().__init__(session)
        self.limit = limit
        self.api_key = get_settings().polygon_api_key

    async def fetch(self) -> AsyncIterator[IngestedItem]:
        if not self.api_key:
            logger.warning("polygon_news_no_api_key")
            return

        params = {
            "order": "desc",
            "limit": str(self.limit),
            "apiKey": self.api_key,
        }

        async with httpx.AsyncClient(timeout=20.0) as client:
            try:
                response = await client.get(POLYGON_NEWS_URL, params=params)
                response.raise_for_status()
            except httpx.HTTPError as exc:
                logger.warning("polygon_news_fetch_failed", error=str(exc))
                return

            payload = response.json()
            if payload.get("status") != "OK":
                logger.warning("polygon_news_bad_response", payload=payload)
                return

            for item in payload.get("results", []):
                title = (item.get("title") or "").strip()
                url = (item.get("article_url") or "").strip()
                if not title or not url:
                    continue

                published = self._parse_iso(item.get("published_utc"))
                publisher_name = (item.get("publisher") or {}).get("name") or "unknown"

                yield IngestedItem(
                    source=f"polygon:{publisher_name.lower().replace(' ', '_')}",
                    source_quality=self.source_quality,
                    headline=title,
                    body=(item.get("description") or "").strip() or None,
                    source_url=url,
                    published_at=published,
                    raw_meta={
                        "polygon_id": item.get("id"),
                        "publisher": publisher_name,
                        "publisher_homepage": (item.get("publisher") or {}).get("homepage_url"),
                        "author": item.get("author"),
                        "tickers": item.get("tickers") or [],
                        "keywords": item.get("keywords") or [],
                        "image_url": item.get("image_url"),
                        "amp_url": item.get("amp_url"),
                    },
                )

    @staticmethod
    def _parse_iso(value: str | None) -> datetime | None:
        if not value:
            return None
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
