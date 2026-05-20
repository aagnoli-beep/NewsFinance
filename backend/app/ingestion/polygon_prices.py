"""Ingester Polygon prezzi giornalieri (daily OHLCV).

Due flussi:
- backfill(start, end, tickers): scarica la storia daily per i ticker dati.
- update_recent(days_back): pull degli ultimi N giorni per il nostro universe,
  utile come job giornaliero.

Polygon Stocks Starter ha unlimited API calls quindi facciamo una chiamata
per ticker. Tempo backfill 1 anno per ~100 ticker: 1-2 minuti. Tutti i prezzi
finiscono in `prices` (interval='1d') con upsert su (ticker, ts, interval).
"""

from __future__ import annotations

import asyncio
from datetime import date, datetime, timedelta
from typing import Any

import httpx
from loguru import logger
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.data.universe import UNIVERSE
from app.models.market import Price

POLYGON_AGG_URL = "https://api.polygon.io/v2/aggs/ticker/{ticker}/range/1/day/{start}/{end}"


class PolygonPricesIngester:
    def __init__(self, session: AsyncSession, concurrency: int = 5) -> None:
        self.session = session
        self.api_key = get_settings().polygon_api_key
        self.concurrency = concurrency

    async def backfill(
        self,
        tickers: list[str] | None = None,
        start: date | None = None,
        end: date | None = None,
    ) -> dict[str, int]:
        """Scarica daily bars per ogni ticker nel range [start, end].

        Strategia: HTTP fetch in parallelo (Polygon Starter ha unlimited calls),
        DB writes serializzati a fine raccolta (SQLAlchemy async non è task-safe).

        Default: ultimi 365 giorni per tutto l'UNIVERSE.
        """
        if not self.api_key:
            logger.error("polygon_prices_no_api_key")
            return {}

        tickers = tickers or UNIVERSE
        end = end or date.today()
        start = start or (end - timedelta(days=365))

        sem = asyncio.Semaphore(self.concurrency)
        all_rows: list[dict[str, Any]] = []
        counts: dict[str, int] = {}

        async with httpx.AsyncClient(timeout=30.0) as client:
            async def fetch_one(ticker: str) -> None:
                async with sem:
                    rows = await self._fetch_ticker_bars(client, ticker, start, end)
                    counts[ticker] = len(rows)
                    all_rows.extend(rows)

            await asyncio.gather(*[fetch_one(t) for t in tickers])

        if all_rows:
            await self._upsert_bars(all_rows)

        total = sum(counts.values())
        logger.info(
            "polygon_backfill_complete",
            tickers=len(tickers),
            total_bars=total,
            start=start.isoformat(),
            end=end.isoformat(),
        )
        return counts

    async def _fetch_ticker_bars(
        self, client: httpx.AsyncClient, ticker: str, start: date, end: date
    ) -> list[dict[str, Any]]:
        url = POLYGON_AGG_URL.format(
            ticker=ticker, start=start.isoformat(), end=end.isoformat()
        )
        params = {
            "adjusted": "true",
            "sort": "asc",
            "limit": "50000",
            "apiKey": self.api_key,
        }

        try:
            response = await client.get(url, params=params)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            logger.warning("polygon_price_fetch_failed", ticker=ticker, error=str(exc))
            return []

        payload = response.json()
        if payload.get("status") not in {"OK", "DELAYED"}:
            logger.warning(
                "polygon_price_bad_response", ticker=ticker, payload_status=payload.get("status")
            )
            return []

        bars = payload.get("results", []) or []
        return [
            {
                "ticker": ticker,
                "ts": datetime.fromtimestamp(bar["t"] / 1000.0),
                "open": bar["o"],
                "high": bar["h"],
                "low": bar["l"],
                "close": bar["c"],
                "volume": int(bar["v"]),
                "interval": "1d",
            }
            for bar in bars
        ]

    async def _upsert_bars(self, rows: list[dict[str, Any]], chunk_size: int = 2000) -> None:
        """Upsert in batch — chunked per non sforare il limit di parametri Postgres."""
        for i in range(0, len(rows), chunk_size):
            chunk = rows[i : i + chunk_size]
            stmt = insert(Price).values(chunk)
            stmt = stmt.on_conflict_do_update(
                constraint="uq_price_ticker_ts_interval",
                set_={
                    "open": stmt.excluded.open,
                    "high": stmt.excluded.high,
                    "low": stmt.excluded.low,
                    "close": stmt.excluded.close,
                    "volume": stmt.excluded.volume,
                },
            )
            await self.session.execute(stmt)
        await self.session.commit()
