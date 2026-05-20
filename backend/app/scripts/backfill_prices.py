"""CLI: backfill 1 anno prezzi daily per l'universe.

Uso:
    uv run python -m app.scripts.backfill_prices
    uv run python -m app.scripts.backfill_prices AAPL MSFT NVDA  # subset
"""

from __future__ import annotations

import asyncio
import sys

from loguru import logger

from app.core.db import SessionLocal
from app.ingestion.polygon_prices import PolygonPricesIngester


async def main(tickers: list[str] | None) -> int:
    async with SessionLocal() as session:
        ingester = PolygonPricesIngester(session)
        results = await ingester.backfill(tickers=tickers)
        ok = sum(1 for v in results.values() if v > 0)
        zero = sum(1 for v in results.values() if v == 0)
        total_bars = sum(results.values())
        logger.info(
            "backfill_summary",
            tickers_ok=ok,
            tickers_empty=zero,
            total_bars=total_bars,
        )
        # Top 5 ticker per numero di bar (sanity check copertura).
        top = sorted(results.items(), key=lambda x: x[1], reverse=True)[:5]
        print("\nTop 5 ticker per bar count:")
        for t, n in top:
            print(f"  {t}: {n} bars")
        empty = [t for t, n in results.items() if n == 0]
        if empty:
            print(f"\nTicker senza dati: {empty}")
    return 0


if __name__ == "__main__":
    args = sys.argv[1:] if len(sys.argv) > 1 else None
    sys.exit(asyncio.run(main(args)))
