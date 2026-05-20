"""Ingester Finnhub: general news + earnings calendar.

Free tier: 60 req/min, condivisibile fra endpoints. Usiamo:
- /news?category=general per news finanziarie
- /calendar/earnings per earnings dei prossimi N giorni

Gli earnings non finiscono in raw_events; finiscono in raw_meta dell'evento
calendario (qualità "primary", il company stesso). Le date EPS estimate
verranno usate dall'expectation engine in Fase 3.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, date, datetime, timedelta

import httpx
from loguru import logger

from app.core.config import get_settings
from app.ingestion.base import IngestedItem, NewsIngester

FINNHUB_NEWS_URL = "https://finnhub.io/api/v1/news"
FINNHUB_EARNINGS_URL = "https://finnhub.io/api/v1/calendar/earnings"


class FinnhubNewsIngester(NewsIngester):
    source_name = "finnhub_news"
    source_quality = "secondary"

    def __init__(self, session, category: str = "general") -> None:
        super().__init__(session)
        self.category = category
        self.api_key = get_settings().finnhub_api_key

    async def fetch(self) -> AsyncIterator[IngestedItem]:
        if not self.api_key:
            logger.warning("finnhub_no_api_key")
            return

        params = {"category": self.category, "token": self.api_key}

        async with httpx.AsyncClient(timeout=20.0) as client:
            try:
                response = await client.get(FINNHUB_NEWS_URL, params=params)
                response.raise_for_status()
            except httpx.HTTPError as exc:
                logger.warning("finnhub_news_fetch_failed", error=str(exc))
                return

            data = response.json()
            if not isinstance(data, list):
                logger.warning("finnhub_news_bad_response")
                return

            for item in data:
                headline = (item.get("headline") or "").strip()
                url = (item.get("url") or "").strip()
                if not headline or not url:
                    continue

                published = self._parse_unix(item.get("datetime"))

                yield IngestedItem(
                    source=f"finnhub:{(item.get('source') or 'unknown').lower().replace(' ', '_')}",
                    source_quality=self.source_quality,
                    headline=headline,
                    body=(item.get("summary") or "").strip() or None,
                    source_url=url,
                    published_at=published,
                    raw_meta={
                        "finnhub_id": item.get("id"),
                        "category": item.get("category"),
                        "image": item.get("image") or None,
                        "related": item.get("related"),
                        "source_name": item.get("source"),
                    },
                )

    @staticmethod
    def _parse_unix(value) -> datetime | None:
        if not value:
            return None
        try:
            return datetime.fromtimestamp(int(value), tz=UTC)
        except (ValueError, TypeError):
            return None


class FinnhubEarningsCalendarIngester(NewsIngester):
    """Earnings calendar → ognuno è un raw_event con tipo 'earnings_upcoming'."""

    source_name = "finnhub_earnings"
    source_quality = "primary"

    def __init__(self, session, days_ahead: int = 14) -> None:
        super().__init__(session)
        self.days_ahead = days_ahead
        self.api_key = get_settings().finnhub_api_key

    async def fetch(self) -> AsyncIterator[IngestedItem]:
        if not self.api_key:
            logger.warning("finnhub_no_api_key")
            return

        today = date.today()
        params = {
            "from": today.isoformat(),
            "to": (today + timedelta(days=self.days_ahead)).isoformat(),
            "token": self.api_key,
        }

        async with httpx.AsyncClient(timeout=20.0) as client:
            try:
                response = await client.get(FINNHUB_EARNINGS_URL, params=params)
                response.raise_for_status()
            except httpx.HTTPError as exc:
                logger.warning("finnhub_earnings_fetch_failed", error=str(exc))
                return

            payload = response.json()
            for entry in payload.get("earningsCalendar", []) or []:
                symbol = entry.get("symbol")
                ev_date = entry.get("date")
                if not symbol or not ev_date:
                    continue

                # URL sintetico per dedup determinstico (no source_url reale).
                synthetic_url = f"finnhub://earnings/{symbol}/{ev_date}"
                hour = entry.get("hour") or "amc"  # bmo=before market open, amc=after market close
                headline = f"{symbol} earnings scheduled for {ev_date} ({hour})"
                eps_est = entry.get("epsEstimate")
                rev_est = entry.get("revenueEstimate")

                yield IngestedItem(
                    source="finnhub:earnings_calendar",
                    source_quality=self.source_quality,
                    headline=headline,
                    body=f"EPS estimate: {eps_est}; Revenue estimate: {rev_est}",
                    source_url=synthetic_url,
                    published_at=datetime.fromisoformat(ev_date).replace(tzinfo=UTC),
                    raw_meta={
                        "event_type": "earnings_upcoming",
                        "symbol": symbol,
                        "date": ev_date,
                        "hour": hour,
                        "eps_estimate": eps_est,
                        "revenue_estimate": rev_est,
                        "eps_actual": entry.get("epsActual"),
                        "revenue_actual": entry.get("revenueActual"),
                        "year": entry.get("year"),
                        "quarter": entry.get("quarter"),
                    },
                )
